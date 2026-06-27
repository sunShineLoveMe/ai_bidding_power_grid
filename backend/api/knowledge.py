"""
知识库路由模块。

负责（每条路由均双蓝图注册）：
  - POST /api/knowledge/upload + /api/bidding/knowledge/upload                上传知识文档
  - POST /api/knowledge/search + /api/bidding/knowledge/search                知识库检索问答
  - POST /api/knowledge/search/stream + /api/bidding/knowledge/search/stream  流式检索问答
  - POST /api/knowledge/followups + /api/bidding/knowledge/followups          生成追问建议
  - GET  /api/knowledge/documents + /api/bidding/knowledge/documents          查询文档列表
  - GET  /api/knowledge/documents/<id> + /api/bidding/knowledge/documents/<id> 查询文档详情

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any

from flask import Response, current_app, jsonify, request, stream_with_context

from backend.api._shared import bp, knowledge_bp
from backend.ai.qwen_client import call_dashscope_api
from backend.core.bid_volumes import asset_applicable_volumes
from backend.core.config import get_stage_model
from backend.core.llm_json_utils import strip_llm_json
from backend.core.security import UploadValidationError, safe_upload_filename, validate_uploaded_file
from backend.db.supabase_client import get_supabase_client
from backend.db.supabase_repo import (
    get_knowledge_overview_stats,
    get_knowledge_document_detail,
    list_knowledge_documents,
)
from backend.parsing.document_parser import write_parse_status
from backend.rag.ingestion import (
    create_knowledge_document,
    ingest_knowledge_document,
    update_knowledge_document_status,
)
from backend.rag.display_names import sanitize_knowledge_assets, sanitize_source_contexts
from backend.rag.retrieval import (
    generate_knowledge_answer,
    search_knowledge_assets,
    search_knowledge_base,
    stream_knowledge_answer,
)
from backend.rag.product_parameters import search_taichang_product_parameter_contexts
from backend.rag.project_performance import search_taichang_project_performance_contexts


CUSTOMER_SEED_CORPUS = "power_grid_customer_corpus"
PILOT_ENTERPRISE = "泰昌"
PILOT_ENTERPRISE_FILTER = {
    "enterprise": PILOT_ENTERPRISE,
    "source_domain": "enterprise_fact",
    "fact_source_allowed_for_enterprise": True,
    "reference_only": False,
}
CUSTOMER_SCOPE_TERMS = [
    "货物清单", "技术规范编码", "物料编码", "交货方式", "交货地点", "主招标文件",
    "招标编号", "资格预审", "评标办法", "专用资格", "包号", "包件", "分标编号",
]
DOC_ROLE_TERMS = {
    "goods_list": ["货物清单", "物料编码", "技术规范编码", "交货方式", "交货地点", "数量"],
    "technical_spec": ["技术规范", "技术参数", "镀锌层", "不锈钢", "电缆支架", "接地铁", "铁附件"],
    "tender_notice": ["招标公告", "资格预审公告", "资格要求", "招标编号"],
    "main_tender_file": ["主招标文件", "招标文件", "评标办法", "投标人须知", "专用资格"],
    "contract_special_terms": ["专用条款", "履约保证金", "交货条款"],
    "contract_general_terms": ["通用条款", "合同通用"],
    "bid_instructions": ["投标注意事项", "否决事项", "常见问题"],
}


def _safe_meta(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    return metadata if isinstance(metadata, dict) else {}


def _customer_scopes() -> list[dict[str, Any]]:
    try:
        rows = (
            get_supabase_client()
            .table("knowledge_documents")
            .select("id,title,metadata,status")
            .eq("status", "indexed")
            .limit(500)
            .execute()
        ).data or []
    except Exception:
        logging.exception("读取客户知识库范围失败")
        return []

    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        meta = _safe_meta(row)
        if meta.get("seed_corpus") != CUSTOMER_SEED_CORPUS:
            continue
        key = (
            str(meta.get("ingestion_batch_id") or ""),
            str(meta.get("province") or ""),
            str(meta.get("batch_no") or ""),
            str(meta.get("package_code") or ""),
        )
        scope = grouped.setdefault(
            key,
            {
                "seed_corpus": CUSTOMER_SEED_CORPUS,
                "ingestion_batch_id": key[0],
                "province": key[1],
                "batch_no": key[2],
                "package_code": key[3],
                "material_categories": set(),
                "doc_roles": set(),
                "documents": 0,
            },
        )
        if meta.get("material_category"):
            scope["material_categories"].add(str(meta.get("material_category")))
        if meta.get("doc_role"):
            scope["doc_roles"].add(str(meta.get("doc_role")))
        scope["documents"] += 1

    scopes = []
    for scope in grouped.values():
        material_categories = sorted(scope["material_categories"])
        scopes.append({
            **scope,
            "doc_roles": sorted(scope["doc_roles"]),
            "material_categories": material_categories,
            "material_category": "、".join(material_categories),
            "label": " / ".join(
                part for part in [scope.get("province"), scope.get("batch_no"), scope.get("package_code"), "、".join(material_categories)] if part
            ),
        })
    scopes.sort(key=lambda item: (item.get("province") or "", item.get("package_code") or "", item.get("material_category") or ""))
    return scopes


def _infer_doc_role_from_query(query: str) -> str | None:
    for doc_role, terms in DOC_ROLE_TERMS.items():
        if any(term in query for term in terms):
            return doc_role
    return None


def _infer_customer_filter(query: str, explicit_filter: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    explicit = {key: value for key, value in (explicit_filter or {}).items() if value not in (None, "", "all")}
    if explicit:
        return explicit, None

    scopes = _customer_scopes()
    if not scopes:
        return None, None

    query_text = query or ""
    candidates = []
    for scope in scopes:
        score = 0
        for key in ["province", "package_code", "material_category", "batch_no"]:
            value = str(scope.get(key) or "")
            if value and value in query_text:
                score += 3 if key == "package_code" else 2
        if any(role_term in query_text for role_terms in DOC_ROLE_TERMS.values() for role_term in role_terms):
            score += 1
        if score:
            candidates.append((score, scope))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score, best_scope = candidates[0]
        tied = [scope for score, scope in candidates if score == best_score]
        if len(tied) == 1:
            inferred = {
                "seed_corpus": CUSTOMER_SEED_CORPUS,
                "ingestion_batch_id": best_scope.get("ingestion_batch_id"),
                "province": best_scope.get("province"),
                "package_code": best_scope.get("package_code"),
            }
            doc_role = _infer_doc_role_from_query(query_text)
            if doc_role:
                inferred["doc_role"] = doc_role
            return {key: value for key, value in inferred.items() if value}, None

    looks_customer_specific = any(term in query_text for term in CUSTOMER_SCOPE_TERMS)
    looks_customer_specific = looks_customer_specific or any(str(scope.get("package_code") or "") in query_text for scope in scopes)
    looks_customer_specific = looks_customer_specific or any(str(scope.get("material_category") or "") in query_text for scope in scopes)
    if looks_customer_specific and len(scopes) > 1:
        return None, {
            "needs_clarification": True,
            "reason": "客户资料范围不明确",
            "message": "我检索到多个客户资料批次/包号。为避免把不同省份、包号或文件角色混在一起，请先选择要查询的范围，或在问题里补充省份、包号、物料类型。",
            "scopes": scopes[:8],
        }
    return None, None


def _pilot_enterprise_metadata_filter(explicit_filter: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata_filter = dict(PILOT_ENTERPRISE_FILTER)
    for key, value in (explicit_filter or {}).items():
        if value not in (None, "", "all"):
            metadata_filter[key] = value
    return metadata_filter


def _metadata_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return None


def _is_pilot_enterprise_context(context: dict[str, Any]) -> bool:
    meta = _safe_meta(context)
    has_enterprise_signal = (
        str(meta.get("enterprise") or "") == PILOT_ENTERPRISE
        or meta.get("source_domain") == "enterprise_fact"
        or _metadata_bool(meta.get("fact_source_allowed_for_enterprise")) is True
    )
    if not has_enterprise_signal:
        return False
    if meta.get("enterprise") and str(meta.get("enterprise")) != PILOT_ENTERPRISE:
        return False
    if meta.get("source_domain") and meta.get("source_domain") != "enterprise_fact":
        return False
    fact_allowed = _metadata_bool(meta.get("fact_source_allowed_for_enterprise"))
    if fact_allowed is False:
        return False
    reference_only = _metadata_bool(meta.get("reference_only"))
    if reference_only is True:
        return False
    return True


def _source_group_key(context: dict[str, Any]) -> str:
    meta = _safe_meta(context)
    if (
        context.get("retrieval_source") == "structured_product_parameter_json"
        or meta.get("retrieval_source") == "structured_product_parameter_json"
    ):
        return "|".join(
            str(part or "")
            for part in [
                meta.get("source_display_name") or meta.get("source_file"),
                meta.get("report_no"),
                meta.get("specification_model"),
            ]
        )
    return "|".join(
        str(part or "")
        for part in [
            meta.get("source_document_name")
            or meta.get("source_display_name")
            or meta.get("source_file")
            or meta.get("source_org")
            or meta.get("category_label")
            or meta.get("category"),
        ]
    )


def _enterprise_context_intent_bonus(query: str, context: dict[str, Any]) -> float:
    meta = _safe_meta(context)
    text = " ".join(
        str(value or "")
        for value in [
            meta.get("source_display_name"),
            meta.get("source_file"),
            meta.get("evidence_type"),
            meta.get("evidence_type_label"),
            context.get("content"),
        ]
    )
    bonus = 0.0
    if any(keyword in query for keyword in ["资质证书", "体系认证", "认证证书"]):
        if any(name in text for name in ["质量管理体系认证证书", "环境管理体系认证证书", "职业健康安全管理体系认证证书"]):
            bonus += 0.65
        elif "认证证书" in text or meta.get("evidence_type") == "certification":
            bonus += 0.3
        if any(name in text for name in ["ESG", "绿色发展规划"]):
            bonus -= 0.25
    if any(keyword in query for keyword in ["企业证明材料", "企业资信", "基础证照"]):
        if any(name in text for name in ["营业执照", "质量管理体系认证证书", "环境管理体系认证证书", "职业健康安全管理体系认证证书", "社保证明", "参保证明"]):
            bonus += 0.45
    if "社保" in query or "参保" in query:
        if "社保" in text or "参保" in text:
            bonus += 0.6
        if meta.get("evidence_type") in {"production_capacity", "testing_capacity"}:
            bonus -= 0.4
    if meta.get("is_asset_catalog"):
        bonus -= 0.15
    return bonus


def _is_certification_query(query: str) -> bool:
    return any(keyword in (query or "") for keyword in ["资质证书", "体系认证", "认证证书"])


def _query_evidence_scope(query: str) -> str | None:
    text = query or ""
    if _is_certification_query(text):
        return "formal_certification"
    if any(keyword in text for keyword in ["绿色低碳", "绿色发展", "绿色供应链", "ESG", "碳足迹", "废水废气", "废水废气废固"]):
        return "green_low_carbon"
    if any(keyword in text for keyword in ["人员证书", "社保证明", "参保证明", "劳动合同", "人员花名册"]):
        return "personnel_certificate"
    if any(keyword in text for keyword in ["检验报告", "检测报告", "型式试验报告"]):
        return "inspection_report"
    if any(keyword in text for keyword in ["生产制造能力", "生产能力", "生产线", "厂房", "车间"]):
        return "production_capacity"
    if any(keyword in text for keyword in ["试验检测设备", "检测设备", "试验设备"]):
        return "testing_capacity"
    if any(keyword in text for keyword in ["营业执照", "基础证照"]):
        return "business_license"
    return None


def _context_text_for_scope(context: dict[str, Any]) -> str:
    meta = _safe_meta(context)
    return " ".join(
        str(value or "")
        for value in [
            meta.get("source_display_name"),
            meta.get("source_document_name"),
            meta.get("source_file"),
            meta.get("evidence_type"),
            meta.get("evidence_type_label"),
            meta.get("category_label"),
            context.get("content"),
        ]
    )


def _context_matches_query_scope(context: dict[str, Any], scope: str | None) -> bool:
    if not scope:
        return True
    meta = _safe_meta(context)
    evidence_type = str(meta.get("evidence_type") or "")
    text = _context_text_for_scope(context)
    if scope == "formal_certification":
        return _is_formal_certification_context(context)
    if scope == "green_low_carbon":
        return evidence_type == "green_low_carbon" or any(
            keyword in text for keyword in ["绿色低碳", "绿色发展", "绿色供应链", "ESG", "碳足迹", "废水废气", "废水废气废固"]
        )
    if scope == "personnel_certificate":
        return evidence_type == "personnel_certificate" or any(keyword in text for keyword in ["人员证书", "社保证明", "参保证明", "劳动合同", "人员花名册"])
    if scope == "inspection_report":
        return evidence_type == "inspection_report" or any(keyword in text for keyword in ["检验报告", "检测报告", "型式试验"])
    if scope == "production_capacity":
        return evidence_type == "production_capacity" or any(keyword in text for keyword in ["生产制造能力", "生产线", "厂房", "车间"])
    if scope == "testing_capacity":
        return evidence_type == "testing_capacity" or any(keyword in text for keyword in ["试验检测设备", "检测设备", "试验设备"])
    if scope == "business_license":
        return evidence_type == "business_license" or "营业执照" in text
    return True


def _is_formal_certification_context(context: dict[str, Any]) -> bool:
    meta = _safe_meta(context)
    text = _context_text_for_scope(context)

    # 负向企业宣传/环保资料必须先拦截。线上存在被误标为 certification 的绿色发展、
    # ESG、废水废气废固资料，不能因为正文中出现泛化“认证证书”就进入资质证书回答。
    if any(name in text for name in ["ESG", "绿色发展规划", "绿色供应链", "碳足迹", "废水废气", "废水废气废固"]):
        return False

    formal_certificate_names = ["质量管理体系认证证书", "环境管理体系认证证书", "职业健康安全管理体系认证证书"]
    if any(name in text for name in formal_certificate_names):
        return True
    if meta.get("evidence_type") == "certification":
        return True
    return False


def _asset_as_source_context(asset: dict[str, Any]) -> dict[str, Any]:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    return {
        "content": " ".join(
            str(value or "")
            for value in [
                asset.get("title"),
                asset.get("description"),
                asset.get("searchable_text"),
                asset.get("category"),
                asset.get("file_name"),
            ]
        ),
        "metadata": {
            **metadata,
            "source_display_name": metadata.get("source_display_name") or asset.get("title"),
            "evidence_type": metadata.get("evidence_type") or asset.get("evidence_type"),
            "evidence_type_label": metadata.get("evidence_type_label") or asset.get("category"),
            "source_file": metadata.get("source_file") or asset.get("file_name"),
        },
    }


def _is_formal_certification_asset(asset: dict[str, Any]) -> bool:
    return _is_formal_certification_context(_asset_as_source_context(asset))


def _asset_matches_query_scope(asset: dict[str, Any], scope: str | None) -> bool:
    return _context_matches_query_scope(_asset_as_source_context(asset), scope)


def _filter_assets_for_query_scope(assets: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    scope = _query_evidence_scope(query)
    if not scope:
        return assets
    filtered = [asset for asset in assets if _asset_matches_query_scope(asset, scope)]
    if filtered or scope == "formal_certification":
        return filtered
    return assets
    return _is_formal_certification_context(context)


def _curate_pilot_enterprise_contexts(
    contexts: list[dict[str, Any]],
    limit: int = 5,
    query: str = "",
) -> list[dict[str, Any]]:
    curated: dict[str, dict[str, Any]] = {}
    for context in contexts or []:
        if not _is_pilot_enterprise_context(context):
            continue
        key = _source_group_key(context)
        if not key.strip("|"):
            key = str(context.get("id") or len(curated))
        current = curated.get(key)
        if current is None or float(context.get("similarity") or 0) > float(current.get("similarity") or 0):
            curated[key] = context

    ranked = sorted(
        curated.values(),
        key=lambda item: float(item.get("similarity") or 0) + _enterprise_context_intent_bonus(query, item),
        reverse=True,
    )
    scope = _query_evidence_scope(query)
    if scope:
        scoped_contexts = [item for item in ranked if _context_matches_query_scope(item, scope)]
        if scoped_contexts or scope == "formal_certification":
            return scoped_contexts[:limit]
    return ranked[:limit]


def _asset_metadata_filter_from_query(query: str, metadata_filter: dict[str, Any] | None, explicit_asset_filter: dict[str, Any] | None = None) -> dict[str, Any] | None:
    asset_filter = {key: value for key, value in (explicit_asset_filter or {}).items() if value not in (None, "", "all")}
    if metadata_filter:
        for key in ("enterprise", "doc_owner", "source_domain", "target_library", "evidence_type", "source_batch_id", "ingestion_batch_id"):
            value = metadata_filter.get(key)
            if value not in (None, "", "all"):
                asset_filter.setdefault(key, value)

    query_text = query or ""
    if "泰昌" in query_text:
        asset_filter.setdefault("enterprise", "泰昌")
        asset_filter.setdefault("source_domain", "enterprise_fact")
        asset_filter.setdefault("reference_only", False)
    return asset_filter or None


def _merge_asset_source_contexts(
    contexts: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    limit: int = 5,
    query: str = "",
) -> list[dict[str, Any]]:
    merged = list(contexts or [])
    for asset in assets or []:
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        merged.append(
            {
                "id": f"asset:{asset.get('id')}",
                "content": asset.get("description") or asset.get("title") or "",
                "similarity": float(asset.get("similarity") or 0),
                "retrieval_source": "knowledge_asset",
                "metadata": {
                    **metadata,
                    "source_display_name": metadata.get("source_display_name") or asset.get("title"),
                    "category_label": asset.get("category") or metadata.get("category_label"),
                    "retrieval_source": "knowledge_asset",
                },
            }
        )
    return _curate_pilot_enterprise_contexts(merged, limit=limit, query=query)


@knowledge_bp.route('/scopes', methods=['GET'])
@bp.route('/knowledge/scopes', methods=['GET'])
def get_knowledge_scopes():
    return jsonify({"customer_scopes": _customer_scopes()}), 200


def sync_and_parse_knowledge_in_background(file_path, original_filename, parse_id, document_id):
    try:
        write_parse_status(parse_id, {
            "parse_status": "mineru_submitted",
            "parser": "mineru",
            "source_file": file_path,
            "file_name": original_filename,
        })
        # For simplicity, we directly call mineru tasks here
        # Assuming parse_and_index_tender_file creates the mineru batch, but we want our own ingestion logic
        # So we can use the same run mineru logic but with custom ingestion
        from backend.parsing.document_parser import _run_mineru_parse_and_index, has_mineru_token, _should_use_mineru_first
        from backend.parsing.mineru_client import download_and_extract_zip, wait_for_batch_file_result, create_local_file_batch_task
        
        output_dir = Path("parsed_outputs") / parse_id
        
        task = create_local_file_batch_task(
            local_file_path=file_path,
            file_name=original_filename,
            data_id=parse_id,
        )
        
        def on_progress(result: dict) -> None:
            pass
            
        result = wait_for_batch_file_result(batch_id=task.batch_id, data_id=parse_id, on_progress=on_progress)
        full_zip_url = result.get("full_zip_url")
        if not full_zip_url:
            raise RuntimeError(f"MinerU finished without full_zip_url")
            
        artifacts = download_and_extract_zip(full_zip_url, output_dir)
        
        # Now call our custom ingestion
        ingest_knowledge_document(
            document_id=document_id,
            original_filename=original_filename,
            markdown_path=artifacts.get("markdown_path"),
            extract_dir=str(output_dir)
        )
        
    except Exception as e:
        logging.exception("知识库解析入库失败")
        update_knowledge_document_status(document_id, "failed")


@knowledge_bp.route('/upload', methods=['POST'])
@bp.route('/knowledge/upload', methods=['POST'])
def upload_knowledge():
    if 'file' not in request.files:
        return jsonify({'error': '未接收到知识库文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择知识库文件'}), 400
    try:
        validate_uploaded_file(file, kind="knowledge")
    except UploadValidationError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        original_filename = file.filename
        safe_filename = safe_upload_filename(original_filename, "knowledge")
        unique_filename = f"{uuid.uuid4()}-{safe_filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        # 1. Create Knowledge Document DB Record
        document_id = create_knowledge_document(
            title=original_filename,
            category="general",
            bucket="knowledge",
            object_path=f"temp/{unique_filename}",
            source_type=Path(original_filename).suffix.lstrip(".")
        )

        parse_id = str(uuid.uuid4())

        from backend.tasks.parse_tasks import sync_and_parse_knowledge

        sync_and_parse_knowledge.delay(file_path, original_filename, parse_id, document_id)

        return jsonify({
            'message': '知识文档已上传，正在后台提取图文特征',
            'documentId': document_id
        }), 201

    except Exception as e:
        logging.exception("知识库文件上传处理失败")
        return jsonify({'error': f'文件上传失败: {str(e)}'}), 500


@knowledge_bp.route('/search', methods=['POST'])
@bp.route('/knowledge/search', methods=['POST'])
def search_knowledge():
    data = request.get_json() or {}
    query = data.get('query')
    if not query:
        return jsonify({'error': '缺少检索问题 query'}), 400
        
    try:
        metadata_filter = _pilot_enterprise_metadata_filter(data.get("metadata_filter") or None)
        # 1. 向量化并检索 Supabase
        contexts = search_knowledge_base(
            query,
            match_threshold=0.3,
            match_count=15,
            scenario="qa",
            metadata_filter=metadata_filter,
            project_id=data.get("project_id") or None,
            return_parent=False,
        )
        parameter_contexts = search_taichang_product_parameter_contexts(query, limit=5)
        performance_contexts = search_taichang_project_performance_contexts(query, limit=3)
        contexts = _curate_pilot_enterprise_contexts(contexts, limit=5, query=query)
        contexts = (performance_contexts + parameter_contexts + contexts)[:5]
        contexts = sanitize_source_contexts(contexts)
        asset_metadata_filter = _asset_metadata_filter_from_query(
            query,
            metadata_filter,
            data.get("asset_metadata_filter") or None,
        )
        assets = sanitize_knowledge_assets(
            search_knowledge_assets(query, match_count=12, metadata_filter=asset_metadata_filter)[:8]
        )
        assets = _filter_assets_for_query_scope(assets, query)
        contexts = _merge_asset_source_contexts(contexts, assets, limit=5, query=query)
        
        # 2. RAG 生成回答
        result = generate_knowledge_answer(query, contexts, assets)
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.exception("知识库检索问答失败")
        return jsonify({'error': f'检索问答失败: {str(e)}'}), 500


@knowledge_bp.route('/search/stream', methods=['POST'])
@bp.route('/knowledge/search/stream', methods=['POST'])
def stream_search_knowledge():
    data = request.get_json() or {}
    query = (data.get('query') or '').strip()
    if not query:
        return jsonify({'error': '缺少检索问题 query'}), 400

    def is_relevant_knowledge_query(text: str) -> bool:
        keywords = [
            "电网", "电力", "国家电网", "南方电网", "输变电", "配网", "变电站", "线路",
            "电缆", "开关柜", "变压器", "箱变", "一次设备", "二次设备", "继电保护", "自动化",
            "调度", "通信", "计量", "试验", "调试", "运维", "检修", "供货", "技术规范书",
            "技术偏差表", "商务偏差表", "招标", "投标", "标书", "资格", "资质", "评标",
            "评分", "废标", "否决", "施工", "监理", "勘察", "设计", "EPC", "总承包",
            "工期", "质量", "安全", "环保", "合同", "报价", "工程量清单", "投标文件", "招标文件",
            "企业知识库", "企业资信", "资信库", "企业产品", "产品库", "标准话术", "政策法规",
            "电力标准", "章节", "正文", "图片", "附件", "材料", "样张", "业绩", "类似业绩",
            "营业执照", "执照", "许可证", "安全生产许可", "人员", "社保", "缴纳证明",
            "证书", "证件", "产品", "设备", "图册", "参考图", "配图",
        ]
        lowered = text.lower()
        ascii_keywords = ["bid", "tender", "rag", "qualification", "power", "grid", "electric", "substation", "product", "asset", "certificate"]
        return any(keyword in text for keyword in keywords) or any(keyword in lowered for keyword in ascii_keywords)

    def emit(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @stream_with_context
    def generate():
        yield emit({"type": "start"})
        try:
            metadata_filter = _pilot_enterprise_metadata_filter(data.get("metadata_filter") or None)
            yield emit({"type": "status", "message": "正在检索企业知识库和图片资产..."})
            contexts = search_knowledge_base(
                query,
                match_threshold=0.3,
                match_count=15,
                scenario="qa",
                metadata_filter=metadata_filter,
                project_id=data.get("project_id") or None,
                return_parent=False,
            )
            parameter_contexts = search_taichang_product_parameter_contexts(query, limit=5)
            performance_contexts = search_taichang_project_performance_contexts(query, limit=3)
            contexts = _curate_pilot_enterprise_contexts(contexts, limit=5, query=query)
            contexts = (performance_contexts + parameter_contexts + contexts)[:5]
            contexts = sanitize_source_contexts(contexts)
            asset_metadata_filter = _asset_metadata_filter_from_query(
                query,
                metadata_filter,
                data.get("asset_metadata_filter") or None,
            )
            assets = sanitize_knowledge_assets(
                search_knowledge_assets(query, match_count=12, metadata_filter=asset_metadata_filter)[:8]
            )
            assets = _filter_assets_for_query_scope(assets, query)
            contexts = _merge_asset_source_contexts(contexts, assets, limit=5, query=query)
            if not contexts and not assets and not is_relevant_knowledge_query(query):
                yield emit({
                    "type": "chunk",
                    "content": "抱歉，当前企业知识库主要服务于电网/电力招投标、技术规范书响应、商务/资格响应、企业资信、产品资料、业绩材料、人员证书、供货/施工/运维方案和废标风险等问题。这个问题与当前知识库范围不太相关，我暂时不能基于本知识库给出可靠回答。",
                })
                yield emit({"type": "done"})
                return
            yield emit({
                "type": "status",
                "message": f"已召回 {len(contexts)} 条资料、{len(assets)} 个图片资产，正在生成回答..."
            })
            for event in stream_knowledge_answer(query, contexts, assets):
                yield emit(event)
        except Exception as e:
            logging.exception("知识库流式检索问答失败")
            yield emit({"type": "error", "error": "检索问答失败，请查看后端日志。"})

    return Response(generate(), mimetype='text/event-stream')


def _compact_followup_assets(assets: list[dict]) -> list[dict]:
    compacted = []
    for index, asset in enumerate((assets or [])[:8], 1):
        compacted.append({
            "index": index,
            "title": asset.get("title"),
            "category": asset.get("category"),
            "asset_type": asset.get("asset_type"),
            "description": asset.get("description"),
            "tags": asset.get("tags") or [],
            "applicable_sections": asset.get("applicable_sections") or [],
            "applicable_volumes": asset_applicable_volumes(asset),
        })
    return compacted


def _compact_followup_sources(sources: list[dict]) -> list[dict]:
    compacted = []
    for index, source in enumerate((sources or [])[:5], 1):
        metadata = source.get("metadata") or {}
        compacted.append({
            "index": index,
            "title": metadata.get("source_org") or metadata.get("source_file") or metadata.get("category_label") or metadata.get("category"),
            "doc_type": metadata.get("doc_type"),
            "content_preview": str(source.get("content") or "").replace("\n", " ")[:240],
        })
    return compacted


def _normalize_followups(payload: dict) -> dict:
    intent = str(payload.get("intent") or "general_qa").strip() or "general_qa"
    followups = payload.get("followups")
    if not isinstance(followups, list):
        followups = []

    cleaned = []
    seen = set()
    for item in followups:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        if re.search(r"(?:目前|当前|泰昌).{0,12}(?:缺少|缺失|未提供|尚未提供)", text):
            continue
        if len(text) > 80:
            text = text[:80].rstrip("，。；;,. ") + "？"
        if not text.endswith(("?", "？")):
            text += "？"
        cleaned.append(text)
        seen.add(text)
        if len(cleaned) >= 3:
            break

    return {
        "intent": intent,
        "followups": cleaned,
    }


def _parse_followup_model_content(content) -> dict:
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        parsed = strip_llm_json(content)
        return parsed if isinstance(parsed, dict) else {}
    return {}


@knowledge_bp.route('/followups', methods=['POST'])
@bp.route('/knowledge/followups', methods=['POST'])
def generate_knowledge_followups():
    data = request.get_json() or {}
    question = str(data.get("question") or "").strip()
    answer = str(data.get("answer") or "").strip()
    if not question or not answer:
        return jsonify({"intent": "general_qa", "followups": []}), 200

    assets = data.get("assets") if isinstance(data.get("assets"), list) else []
    sources = data.get("sources") if isinstance(data.get("sources"), list) else []
    prompt_payload = {
        "user_question": question[:800],
        "assistant_answer": answer[:2600],
        "retrieved_assets": _compact_followup_assets(assets),
        "retrieved_sources": _compact_followup_sources(sources),
    }
    prompt = f"""你是 AI 标书系统的企业知识库问答意图识别器。
请根据用户问题、助手回答、召回资料和图片资产，判断用户下一步最可能需要什么，并生成 3 个专业、具体、可点击的后续问题。

要求：
1. 问题必须服务于电网/电力招投标、标书编制、企业资信、产品资料、业绩材料、风险核查或材料入库。
2. 问题要像业务人员自然会追问的话，不能泛泛而谈。
3. 如果回答涉及图片资产，要优先引导"图片适合放在哪个章节""哪些能插入正文/附件""还缺哪些原件或证明"。
4. 如果回答涉及资质、人员、社保、营业执照、许可证，要优先引导材料完整性和废标风险核查。
5. 如果回答涉及产品、设备、参数，要优先引导技术响应配图和参数匹配。
6. 只有当助手回答已经明确确认某项材料缺失时，后续问题才能复述该缺失；否则必须使用“是否具备”“能否检索到”等中性问法，不得写“目前缺少”“当前缺失”“未提供”等未经证实的结论。
7. 只输出 JSON，不要输出 Markdown，不要解释。

JSON 格式：
{{
  "intent": "asset_lookup | qualification_check | bid_writing | risk_check | product_matching | material_gap | general_qa",
  "followups": ["问题1", "问题2", "问题3"]
}}

输入：
{json.dumps(prompt_payload, ensure_ascii=False)}
"""
    try:
        response = call_dashscope_api(
            [
                {"role": "system", "content": "你只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            model=get_stage_model("knowledge_followup"),
            json_mode=True,
            usage_context={
                "stage": "knowledge_followup_generation",
                "operation_type": "text_generation",
            },
        )
        content = (
            response.get("output", {})
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _parse_followup_model_content(content)
        return jsonify(_normalize_followups(parsed)), 200
    except Exception:
        logging.exception("生成知识库追问建议失败")
        return jsonify({"intent": "general_qa", "followups": []}), 200


@knowledge_bp.route('/documents', methods=['GET'])
@bp.route('/knowledge/documents', methods=['GET'])
def get_knowledge_documents():
    try:
        docs = list_knowledge_documents()
        return jsonify(docs), 200
    except Exception as e:
        logging.exception("查询知识库文档列表失败")
        return jsonify({'error': f'查询失败: {str(e)}'}), 500


@knowledge_bp.route('/stats', methods=['GET'])
@bp.route('/knowledge/stats', methods=['GET'])
def get_knowledge_stats():
    try:
        return jsonify(get_knowledge_overview_stats()), 200
    except Exception as e:
        logging.exception("查询知识库统计失败")
        return jsonify({'error': f'查询失败: {str(e)}'}), 500


@knowledge_bp.route('/documents/<document_id>', methods=['GET'])
@bp.route('/knowledge/documents/<document_id>', methods=['GET'])
def get_knowledge_document(document_id):
    try:
        detail = get_knowledge_document_detail(document_id)
        if not detail:
            return jsonify({'error': '知识库文档不存在'}), 404
        return jsonify(detail), 200
    except Exception as e:
        logging.exception("查询知识库文档详情失败")
        return jsonify({'error': f'查询失败: {str(e)}'}), 500

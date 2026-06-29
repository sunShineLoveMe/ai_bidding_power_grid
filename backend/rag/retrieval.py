import json
import re
import threading
from pathlib import Path
from typing import Any, Iterator, List, Dict
from openai import OpenAI

from backend.db.supabase_client import get_supabase_client
from backend.rag.vector_store import init_ali_client, get_embeddings
from backend.ai.qwen_client import stream_dashscope_api
from backend.core.config import get_stage_model
from backend.ai.rerank_client import rerank_documents
from backend.core.bid_volumes import asset_applicable_volumes, asset_matches_volume, normalize_volume_type
from backend.rag.display_names import sanitize_knowledge_assets, sanitize_source_metadata, sanitize_visible_text

AUTHORITY_SCORE = {
    "law_or_standard": 0.18,
    "tender_file": 0.16,
    "enterprise_fact": 0.14,
    "sgcc_rule": 0.14,
    "standard_spec": 0.12,
    "reference_template": -0.08,
    "template": -0.05,
}

_CHUNK_KEYWORD_CACHE: list[dict[str, Any]] | None = None
_CHUNK_KEYWORD_CACHE_FINGERPRINT: tuple[int | None, str, str] | None = None
_CHUNK_KEYWORD_CACHE_LOCK = threading.Lock()
_CHUNK_KEYWORD_SCAN_LIMIT = 120000
_CHUNK_KEYWORD_PAGE_SIZE = 5000


def invalidate_chunk_keyword_cache(reason: str | None = None) -> None:
    """Clear the in-process keyword fallback cache after document chunk changes."""
    global _CHUNK_KEYWORD_CACHE, _CHUNK_KEYWORD_CACHE_FINGERPRINT
    with _CHUNK_KEYWORD_CACHE_LOCK:
        _CHUNK_KEYWORD_CACHE = None
        _CHUNK_KEYWORD_CACHE_FINGERPRINT = None


def _document_chunks_fingerprint(client) -> tuple[int | None, str, str] | None:
    try:
        response = (
            client.table("document_chunks")
            .select("id,created_at", count="exact")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        return None
    latest = (response.data or [{}])[0] if getattr(response, "data", None) else {}
    return (
        getattr(response, "count", None),
        str(latest.get("created_at") or ""),
        str(latest.get("id") or ""),
    )


def _load_chunk_keyword_cache(client) -> list[dict[str, Any]]:
    scanned: list[dict[str, Any]] = []
    for start in range(0, _CHUNK_KEYWORD_SCAN_LIMIT, _CHUNK_KEYWORD_PAGE_SIZE):
        batch = (
            client.table("document_chunks")
            .select("*")
            .order("id")
            .range(start, start + _CHUNK_KEYWORD_PAGE_SIZE - 1)
            .execute()
        ).data or []
        scanned.extend(batch)
        if len(batch) < _CHUNK_KEYWORD_PAGE_SIZE:
            break
    return scanned


def _get_chunk_keyword_cache_rows(client) -> list[dict[str, Any]]:
    global _CHUNK_KEYWORD_CACHE, _CHUNK_KEYWORD_CACHE_FINGERPRINT
    fingerprint = _document_chunks_fingerprint(client)
    with _CHUNK_KEYWORD_CACHE_LOCK:
        if _CHUNK_KEYWORD_CACHE is not None and (
            fingerprint is None or fingerprint == _CHUNK_KEYWORD_CACHE_FINGERPRINT
        ):
            return _CHUNK_KEYWORD_CACHE
        rows = _load_chunk_keyword_cache(client)
        _CHUNK_KEYWORD_CACHE = rows
        _CHUNK_KEYWORD_CACHE_FINGERPRINT = fingerprint
        return rows


def _normalize_query_text(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip())


def _query_terms(query: str) -> list[str]:
    text = _normalize_query_text(query)
    terms = set(re.findall(r"[A-Za-z]+/[A-Za-z]+\s*\d+(?:[-—]\d+)?(?:[-—]\d+)?|[A-Za-z]{1,8}[-—]?\d+[A-Za-z0-9-]*|[0-9]{4}[A-Z]{2}|[\u4e00-\u9fa5]{2,}", text))
    domain_terms = [
        "国家电网",
        "招标活动",
        "管理办法",
        "招标方式",
        "供应商管理",
        "供应商",
        "不良行为",
        "施工工艺",
        "配电网",
        "技术规范",
        "技术规范编码",
        "物料编码",
        "包号",
        "质量安全环保",
        "质量目标",
        "安全目标",
        "环保水保",
        "环保目标",
        "输电线路",
        "线路施工",
        "杆塔",
        "架线",
        "放线",
        "施工工序",
        "主要工序",
        "项目业绩",
        "类似业绩",
        "合同",
        "供货合同",
        "合同协议书",
        "中标",
        "中标通知书",
        "招标编号",
        "中标单位",
        "营业执照",
        "基础证照",
        "法定代表人",
        "法人代表",
        "统一社会信用代码",
        "注册资本",
        "成立日期",
        "注册地址",
        "企业信用报告",
        "工商登记",
    ]
    for term in domain_terms:
        if term in text:
            terms.add(term)
    synonym_map = {
        "招标方式": ["公开招标", "邀请招标", "竞争性谈判", "招标方式"],
        "供应商管理": ["供应商", "不良行为", "暂停中标资格", "列入黑名单"],
        "不良行为": ["不良行为", "暂停中标资格", "供应商"],
        "施工工艺": ["施工", "工艺", "施工工艺", "验收"],
        "配电网施工": ["配电网", "施工", "工艺"],
        "技术规范编码": ["技术规范编码", "固化ID", "物料编码"],
        "物料编码": ["物料编码", "技术规范编码"],
        "包号": ["包号", "包件", "package_code"],
        "质量安全环保": ["质量安全环保", "质量目标", "安全目标", "环保水保"],
        "质量目标": ["质量目标", "验收合格", "质量标准"],
        "安全目标": ["安全目标", "安全生产", "风险预控"],
        "输电线路": ["输电线路", "线路施工", "杆塔", "杆塔组立", "架线", "放线", "施工工序", "主要工序"],
        "线路施工": ["输电线路", "线路施工", "杆塔", "杆塔组立", "架线", "放线", "施工工序", "主要工序"],
        "施工工序": ["施工工序", "主要工序", "复测分坑", "基础开挖", "杆塔组立", "架线放线", "验收消缺"],
        "主要工序": ["施工工序", "主要工序", "复测分坑", "基础开挖", "杆塔组立", "架线放线", "验收消缺"],
        "项目业绩": ["项目业绩", "类似业绩", "合同", "合同协议书", "供货合同", "中标", "中标通知书"],
        "类似业绩": ["类似业绩", "项目业绩", "合同", "合同协议书", "供货合同", "中标", "中标通知书"],
        "合同": ["合同", "合同协议书", "供货合同", "甲方", "乙方"],
        "供货合同": ["供货合同", "合同协议书", "合同", "甲方", "乙方"],
        "合同协议书": ["合同协议书", "供货合同", "合同", "甲方", "乙方"],
        "中标通知书": ["中标通知书", "中标", "招标编号", "包号", "中标单位"],
        "中标": ["中标", "中标通知书", "招标编号", "包号", "中标单位"],
        "法定代表人": ["法定代表人", "法人代表", "法人", "营业执照", "统一社会信用代码", "企业信用报告", "工商登记", "基础证照"],
        "法人代表": ["法定代表人", "法人代表", "法人", "营业执照", "统一社会信用代码", "企业信用报告", "工商登记", "基础证照"],
        "法人": ["法定代表人", "法人代表", "法人", "营业执照", "统一社会信用代码", "企业信用报告", "工商登记", "基础证照"],
        "统一社会信用代码": ["统一社会信用代码", "营业执照", "企业信用报告", "工商登记", "基础证照"],
        "注册资本": ["注册资本", "营业执照", "企业信用报告", "工商登记", "基础证照"],
        "成立日期": ["成立日期", "营业执照", "企业信用报告", "工商登记", "基础证照"],
        "注册地址": ["注册地址", "公司地址", "营业执照", "企业信用报告", "工商登记", "基础证照"],
    }
    for key, values in synonym_map.items():
        if key in text:
            terms.update(values)
    return [term.strip() for term in terms if term and len(term.strip()) >= 2]


def _rewrite_query_for_embedding(query: str) -> str:
    terms = _query_terms(query)
    if not terms:
        return query
    extras = " ".join(term for term in terms if term not in query)
    return f"{query}\n检索关键词：{extras}" if extras else query


def _infer_doc_role_filter(query: str, scenario: str | None = None) -> str | None:
    text = query or ""
    lowered = text.lower()
    if any(token in text for token in ["法律", "法规", "合规", "废标", "否决", "无效", "串通", "责任"]):
        return "policy_regulation"
    if any(token in text for token in ["国家电网", "国网", "供应商管理", "招标活动管理", "物资采购标准"]):
        return "sgcc_rule"
    if any(token in text for token in ["标准", "规范", "规程", "导则", "试验", "施工工艺", "技术参数"]):
        return "standard_spec"
    if any(token in text for token in ["公告", "采购范围", "资格要求", "递交", "开标", "报价"]):
        return "tender_notice"
    if any(token in text for token in ["怎么写", "响应", "承诺", "模板", "话术", "检查清单"]) or "template" in lowered:
        return "self_phrase"
    if scenario == "compliance":
        return "policy_regulation"
    return None


def _build_filter_metadata(
    query: str,
    *,
    scenario: str | None,
    metadata_filter: dict[str, Any] | None,
) -> dict[str, Any]:
    filter_md = dict(metadata_filter or {})
    filter_md.setdefault("chunk_layer", "child")
    if "doc_role" not in filter_md:
        inferred_role = _infer_doc_role_filter(query, scenario)
        if inferred_role:
            filter_md["doc_role"] = inferred_role
    return filter_md


def _rpc_search_chunks(
    client,
    *,
    query_vector: list[float],
    match_threshold: float,
    match_count: int,
    filter_metadata: dict[str, Any],
    project_id: str | None,
) -> list[dict[str, Any]]:
    response = client.rpc(
        "match_knowledge_chunks_filtered",
        {
            "query_embedding": query_vector,
            "match_threshold": match_threshold,
            "match_count": match_count,
            "filter_metadata": filter_metadata,
            "filter_project_id": project_id,
        },
    ).execute()
    return response.data or []


def _metadata_matches_filter(metadata: dict[str, Any], metadata_filter: dict[str, Any] | None) -> bool:
    if not metadata_filter:
        return True
    for key, expected in metadata_filter.items():
        if expected in (None, "", "all"):
            continue
        candidate = metadata.get(key)
        expected_values = expected if isinstance(expected, list) else [expected]
        candidate_values = candidate if isinstance(candidate, list) else [candidate]
        if not any(str(item) == str(value) for item in candidate_values for value in expected_values):
            return False
    return True


def _metadata_excluded_from_retrieval(metadata: dict[str, Any]) -> bool:
    if metadata.get("exclude_from_rag") is True:
        return True
    if str(metadata.get("rag_visibility") or "").lower() in {"internal_only", "audit_only", "disabled"}:
        return True
    if str(metadata.get("status") or "").lower() in {"superseded", "disabled", "archived"}:
        return True
    return False


def _row_text(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    parts = [
        row.get("content"),
        row.get("source_section"),
        metadata.get("source_file"),
        metadata.get("source_org"),
        metadata.get("doc_type"),
        metadata.get("tags"),
        metadata.get("material_category"),
        metadata.get("package_code"),
        metadata.get("source_domain"),
        metadata.get("citation_policy"),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _source_context_prefix(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    source_name = Path(str(metadata.get("source_file") or "")).stem if metadata.get("source_file") else ""
    parts = [
        source_name,
        metadata.get("tags"),
        metadata.get("doc_type"),
        metadata.get("source_org"),
    ]
    text = "；".join(str(part) for part in parts if part)
    return f"资料来源信息：{text}\n" if text else ""


def _keyword_score(query: str, row: dict[str, Any]) -> float:
    terms = _query_terms(query)
    if not terms:
        return 0.0
    text = _row_text(row)
    score = 0.0
    for term in terms:
        normalized = term.lower().replace("—", "-")
        if normalized and normalized in text:
            score += 1.0 if len(normalized) >= 4 else 0.6
    return score / max(len(terms), 1)


def _authority_bonus(row: dict[str, Any]) -> float:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    authority = str(metadata.get("authority_level") or metadata.get("doc_role") or "")
    citation = str(metadata.get("citation_policy") or "")
    bonus = AUTHORITY_SCORE.get(authority, 0.0)
    if citation in {"law_or_standard_citable", "tender_requirement_citable", "enterprise_fact_citable"}:
        bonus += 0.03
    if metadata.get("evidence_type") == "business_license":
        bonus += 0.08
    if metadata.get("source_category") == "structured_enterprise_fact_pack":
        bonus += 0.12
    if citation == "reference_style_only":
        bonus -= 0.12
    if metadata.get("status") == "superseded":
        bonus -= 0.4
    return bonus


def _needs_keyword_supplement(query: str, rows: list[dict[str, Any]], match_count: int) -> bool:
    terms = _query_terms(query)
    if not terms:
        return False
    if len(rows) < match_count:
        return True
    best_keyword_score = max((_keyword_score(query, row) for row in rows), default=0.0)
    if best_keyword_score <= 0.0:
        return True
    required_intents = _required_evidence_intents(query)
    if required_intents:
        covered = _covered_evidence_intents(rows)
        return bool(required_intents - covered)
    return False


def _required_evidence_intents(query: str) -> set[str]:
    text = query or ""
    required: set[str] = set()
    if any(keyword in text for keyword in ["合同协议书", "供货合同", "合同"]):
        required.add("contract")
    if any(keyword in text for keyword in ["中标通知书", "中标"]):
        required.add("award_notice")
    if any(keyword in text for keyword in ["资质证书", "体系认证", "认证证书"]):
        required.update({"quality_certification", "environment_certification", "ohs_certification"})
    if any(keyword in text for keyword in ["企业证明材料", "企业资信", "基础证照"]):
        required.update({
            "business_license",
            "quality_certification",
            "environment_certification",
            "ohs_certification",
            "personnel_social_security",
        })
    if any(keyword in text for keyword in ["营业执照", "法定代表人", "法人代表", "法人是谁", "统一社会信用代码", "注册资本", "成立日期", "注册地址"]):
        required.add("business_license")
    if any(keyword in text for keyword in ["社保", "参保"]):
        required.add("personnel_social_security")
    if any(keyword in text for keyword in ["检验报告", "检测报告", "型式试验"]):
        required.add("inspection_report")
    return required


def _covered_evidence_intents(rows: list[dict[str, Any]]) -> set[str]:
    covered: set[str] = set()
    for row in rows or []:
        covered.update(_evidence_intents_from_text(_row_text(row)))
    return covered


def _evidence_intents_from_text(text: str) -> set[str]:
    intents: set[str] = set()
    if any(keyword in text for keyword in ["合同协议书", "供货合同", "合同"]):
        intents.add("contract")
    if any(keyword in text for keyword in ["中标通知书", "中标"]):
        intents.add("award_notice")
    if "质量管理体系认证证书" in text:
        intents.update({"quality_certification", "certification"})
    if "环境管理体系认证证书" in text:
        intents.update({"environment_certification", "certification"})
    if "职业健康安全管理体系认证证书" in text:
        intents.update({"ohs_certification", "certification"})
    if any(keyword in text for keyword in ["营业执照", "统一社会信用代码", "企业信用报告", "工商基础信息", "工商登记"]):
        intents.add("business_license")
    if "法定代表人" in text and any(keyword in text for keyword in ["企业名称", "统一社会信用代码", "注册资本", "成立日期", "注册地址"]):
        intents.add("business_license")
    if any(keyword in text for keyword in ["社保证明", "参保证明", "社保缴纳"]):
        intents.add("personnel_social_security")
    if any(keyword in text for keyword in ["检验报告", "检测报告", "型式试验报告"]):
        intents.add("inspection_report")
    return intents


def _select_with_required_evidence_coverage(
    query: str,
    rows: list[dict[str, Any]],
    *,
    text_getter,
    limit: int,
) -> list[dict[str, Any]]:
    required = _required_evidence_intents(query)
    if not required:
        return rows[:limit]
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def row_key(row: dict[str, Any]) -> str:
        return str(row.get("id") or row.get("storage_path") or f"{row.get('document_id')}:{row.get('chunk_index')}:{hash(text_getter(row))}")

    for intent in required:
        candidates = []
        for row in rows:
            key = row_key(row)
            if key in seen:
                continue
            if intent in _evidence_intents_from_text(text_getter(row)):
                title = str(row.get("title") or row.get("file_name") or "")
                title_bonus = 0
                if intent == "personnel_social_security" and any(word in title for word in ["社保", "参保"]):
                    title_bonus = 2
                elif intent == "business_license" and "营业执照" in title:
                    title_bonus = 2
                elif intent.endswith("_certification") and intent.split("_")[0] in {
                    "quality",
                    "environment",
                    "ohs",
                }:
                    expected = {
                        "quality_certification": "质量管理体系认证证书",
                        "environment_certification": "环境管理体系认证证书",
                        "ohs_certification": "职业健康安全管理体系认证证书",
                    }[intent]
                    title_bonus = 2 if expected in title else 0
                rank_score = _asset_rank_score(query, row) if text_getter is _asset_search_text else float(row.get("similarity") or 0)
                candidates.append((title_bonus, rank_score, row, key))
        if candidates:
            _, _, row, key = max(candidates, key=lambda item: (item[0], item[1]))
            selected.append(row)
            seen.add(key)
    for row in rows:
        if len(selected) >= limit:
            break
        key = row_key(row)
        if key in seen:
            continue
        selected.append(row)
        seen.add(key)
    return selected


def _asset_row_key(asset: dict[str, Any]) -> str:
    return str(asset.get("id") or asset.get("storage_path") or asset.get("public_url") or hash(_asset_search_text(asset)))


def _merge_and_rank_assets(query: str, assets: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for asset in assets:
        key = _asset_row_key(asset)
        existing = deduped.get(key)
        if existing is None or _asset_rank_score(query, asset) > _asset_rank_score(query, existing):
            deduped[key] = asset
    ranked = list(deduped.values())
    ranked.sort(key=lambda asset: _asset_rank_score(query, asset), reverse=True)
    return _select_with_required_evidence_coverage(
        query,
        ranked,
        text_getter=_asset_search_text,
        limit=limit,
    )


def _keyword_search_knowledge_chunks(
    client,
    *,
    query: str,
    match_count: int,
    metadata_filter: dict[str, Any],
) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    if not terms:
        return []
    try:
        rows = _get_chunk_keyword_cache_rows(client)
    except Exception:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if _metadata_excluded_from_retrieval(metadata):
            continue
        if not _metadata_matches_filter(metadata, metadata_filter):
            continue
        score = _keyword_score(query, row)
        if score <= 0:
            continue
        enriched = {
            **row,
            "content": f"{_source_context_prefix(row)}{row.get('content') or ''}",
            "similarity": max(float(row.get("similarity") or 0), min(0.99, 0.55 + score / 3)),
            "keyword_score": round(score, 4),
            "retrieval_source": "keyword",
        }
        scored.append((score + _authority_bonus(enriched), enriched))
    scored.sort(key=lambda item: item[0], reverse=True)
    limit = max(match_count * 2, match_count)
    return _select_with_required_evidence_coverage(
        query,
        [row for _, row in scored],
        text_getter=_row_text,
        limit=limit,
    )


def _merge_rows(primary: list[dict[str, Any]], supplemental: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in [*primary, *supplemental]:
        row_id = str(row.get("id") or "")
        key = row_id or f"{row.get('document_id')}:{row.get('chunk_index')}:{hash(row.get('content') or '')}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged


def _rank_rows(query: str, rows: list[dict[str, Any]], match_count: int) -> list[dict[str, Any]]:
    def score(row: dict[str, Any]) -> float:
        return (
            float(row.get("similarity") or 0)
            + min(_keyword_score(query, row), 1.0) * 0.18
            + _authority_bonus(row)
        )

    return sorted(rows, key=score, reverse=True)[:match_count]


def _attach_parent_context(client, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for row in rows:
        metadata = row.get("metadata") or {}
        parent_index = metadata.get("parent_index")
        document_id = row.get("document_id")
        if document_id and isinstance(parent_index, int):
            key = (str(document_id), parent_index)
            if key in seen:
                continue
            seen.add(key)
            try:
                parent_resp = client.rpc(
                    "get_parent_chunk",
                    {"p_document_id": document_id, "p_parent_index": parent_index},
                ).execute()
                parent = (parent_resp.data or [None])[0]
            except Exception:
                parent = None
            if parent:
                parent_meta = parent.get("metadata") or {}
                enriched.append({
                    **parent,
                    "similarity": row.get("similarity"),
                    "metadata": {
                        **parent_meta,
                        "retrieved_by_child": {
                            "id": row.get("id"),
                            "source_section": row.get("source_section"),
                            "metadata": metadata,
                        },
                    },
                })
                continue
        enriched.append(row)
    return enriched


def search_knowledge_base(
    query: str,
    match_threshold: float = 0.5,
    match_count: int = 5,
    *,
    scenario: str | None = "qa",
    metadata_filter: dict[str, Any] | None = None,
    project_id: str | None = None,
    return_parent: bool | None = None,
    rerank_enabled: bool | None = None,
    rerank_model: str | None = None,
) -> List[Dict[str, Any]]:
    """
    通过 pgvector RPC 检索知识库内容。

    默认走带 metadata/project 过滤的 `match_knowledge_chunks_filtered`。调用方可按
    qa / writing / compliance 场景传入 metadata_filter；写作场景可回溯父块返回更完整上下文。
    """
    ali_client = init_ali_client()
    client = get_supabase_client()
    
    rewritten_query = _rewrite_query_for_embedding(query)

    # 1. 向量化查询
    query_embeddings = get_embeddings(ali_client, [rewritten_query])
    if not query_embeddings:
        return []
    query_vector = query_embeddings[0]
    
    # 2. 调用带 metadata/project 过滤的 RPC。先按推断/显式过滤召回，不足时放宽 doc_role。
    rpc_count = max(match_count * 3, match_count)
    filter_md = _build_filter_metadata(query, scenario=scenario, metadata_filter=metadata_filter)
    rows = _rpc_search_chunks(
        client,
        query_vector=query_vector,
        match_threshold=match_threshold,
        match_count=rpc_count,
        filter_metadata=filter_md,
        project_id=project_id,
    )
    if len(rows) < match_count and "doc_role" in filter_md and "doc_role" not in (metadata_filter or {}):
        fallback_filter = {k: v for k, v in filter_md.items() if k != "doc_role"}
        fallback_rows = _rpc_search_chunks(
            client,
            query_vector=query_vector,
            match_threshold=match_threshold,
            match_count=rpc_count,
            filter_metadata=fallback_filter,
            project_id=project_id,
        )
        seen_ids = {str(row.get("id")) for row in rows if row.get("id")}
        rows.extend(row for row in fallback_rows if not row.get("id") or str(row.get("id")) not in seen_ids)

    rows = [
        row for row in rows
        if not _metadata_excluded_from_retrieval(row.get("metadata") if isinstance(row.get("metadata"), dict) else {})
    ]

    if _needs_keyword_supplement(query, rows, match_count):
        rows = _merge_rows(
            rows,
            _keyword_search_knowledge_chunks(
                client,
                query=query,
                match_count=match_count,
                metadata_filter=filter_md,
            ),
        )

    if return_parent is None:
        return_parent = scenario == "writing"
    if return_parent:
        rows = _attach_parent_context(client, rows)
    reranked = rerank_documents(
        rewritten_query,
        rows,
        text_key="content",
        top_n=max(match_count * 2, match_count),
        enabled=rerank_enabled,
        model=rerank_model,
        usage_context={"stage": "rag_text_recall", "project_id": project_id},
    )
    return _rank_rows(query, reranked, match_count)


def search_knowledge_assets(
    query: str,
    match_count: int = 8,
    volume_type: str | None = None,
    metadata_filter: dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    检索企业知识库中的图片/资质资产。
    图片本身不直接参与语义检索，检索的是 OCR、AI 描述、规格参数和适用章节组成的 searchable_text。
    """
    ali_client = init_ali_client()
    client = get_supabase_client()

    query_embeddings = get_embeddings(ali_client, [query])
    if not query_embeddings:
        return []

    target_volume = normalize_volume_type(volume_type) if volume_type else None
    rpc_payload = {
        "query_embedding": query_embeddings[0],
        "match_count": max(match_count * 3, match_count),
        "filter_category": None,
        "filter_asset_type": None,
    }
    if target_volume:
        rpc_payload["filter_applicable_volume"] = target_volume

    response = client.rpc(
        "match_knowledge_assets",
        rpc_payload,
    ).execute()

    rpc_rows = response.data or []
    if target_volume:
        rpc_rows = [asset for asset in rpc_rows if asset_matches_volume(asset, target_volume, allow_unscoped=True)]
    if metadata_filter:
        rpc_rows = [asset for asset in rpc_rows if _asset_matches_metadata_filter(asset, metadata_filter)]
    assets = rerank_documents(query, rpc_rows, text_key="searchable_text", top_n=match_count)
    assets.sort(key=lambda asset: _asset_rank_score(query, asset), reverse=True)
    # 过滤掉明显弱相关的资产，保留图片来源展示的准确性。
    strong_assets = [asset for asset in assets if float(asset.get("similarity") or 0) >= 0.28]
    if len(strong_assets) >= min(match_count, 3) and not _needs_asset_keyword_supplement(query, strong_assets):
        return strong_assets[:match_count]

    fallback_assets = _keyword_search_knowledge_assets(
        query,
        match_count=match_count,
        volume_type=target_volume,
        metadata_filter=metadata_filter,
    )
    return _merge_and_rank_assets(query, [*strong_assets, *fallback_assets], match_count)


def _keyword_search_knowledge_assets(
    query: str,
    match_count: int = 8,
    volume_type: str | None = None,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    企业资信库/产品库里经常是短标题、短说明和图片附件，纯向量召回可能偏弱。
    这里补一层轻量关键词召回，确保“营业执照图片、社保缴纳证明、类似业绩证明”等私有资产问题不会被误拒。
    """
    client = get_supabase_client()
    response = (
        client.table("knowledge_assets")
        .select("*")
        .eq("status", "indexed")
        .limit(500)
        .execute()
    )
    rows = response.data or []
    query_tokens = _asset_query_tokens(query)
    if not query_tokens:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for asset in rows:
        if volume_type and not asset_matches_volume(asset, volume_type, allow_unscoped=True):
            continue
        if metadata_filter and not _asset_matches_metadata_filter(asset, metadata_filter):
            continue
        text = _asset_search_text(asset)
        score = sum(1 for token in query_tokens if token and token in text)
        if volume_type and asset_matches_volume(asset, volume_type, allow_unscoped=False):
            score += 4
        if "图片" in query or "照片" in query or "附件" in query or "材料" in query:
            mime_type = str(asset.get("mime_type") or "")
            if mime_type.startswith("image/"):
                score += 2
        if any(token in query for token in ["资质", "资信", "证书", "执照", "许可", "社保", "人员"]):
            if str(asset.get("asset_type") or "") == "qualification_image":
                score += 3
        if any(token in query for token in ["产品", "设备", "材料", "生产", "生产线", "检测", "试验", "闸门", "水泵", "水轮机", "叶片"]):
            if str(asset.get("asset_type") or "") == "product_image":
                score += 3
        score += int((_asset_query_intent_bonus(query, asset) + _asset_visual_quality_bonus(query, asset)) * 20)
        if score > 0:
            enriched = {**asset, "similarity": max(float(asset.get("similarity") or 0), min(score / 10, 0.99))}
            scored.append((score, enriched))

    scored.sort(key=lambda item: item[0], reverse=True)
    return _select_with_required_evidence_coverage(
        query,
        [asset for _, asset in scored],
        text_getter=_asset_search_text,
        limit=match_count,
    )


def _needs_asset_keyword_supplement(query: str, assets: list[dict[str, Any]]) -> bool:
    required_intents = _required_evidence_intents(query)
    if required_intents:
        covered: set[str] = set()
        for asset in assets or []:
            covered.update(_evidence_intents_from_text(_asset_search_text(asset)))
        if required_intents - covered:
            return True

    combined_text = " ".join(_asset_search_text(asset) for asset in assets or [])
    return any(term not in combined_text for term in _distinctive_asset_query_terms(query))


def _distinctive_asset_query_terms(query: str) -> list[str]:
    stop_terms = {
        "查询",
        "产品",
        "图片",
        "照片",
        "资料",
        "材料",
        "适用章节",
        "适用场景",
        "技术标",
        "商务标",
        "资格文件",
        "泰昌",
    }
    terms: list[str] = []
    for token in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9_-]+", (query or "").lower()):
        token = token.strip("_-")
        if not token or token in stop_terms:
            continue
        has_digit_or_delimiter = any(ch.isdigit() for ch in token) or "-" in token or "_" in token
        if has_digit_or_delimiter or len(token) >= 4:
            terms.append(token)
    return terms[:8]


def _asset_metadata_value(asset: dict[str, Any], key: str) -> str:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    specs = asset.get("specs") if isinstance(asset.get("specs"), dict) else {}
    for container in (metadata, specs, asset):
        if isinstance(container, dict) and container.get(key) not in (None, ""):
            return str(container.get(key)).lower()
    return ""


def _asset_query_intent_bonus(query: str, asset: dict[str, Any]) -> float:
    text = query or ""
    evidence_type = _asset_metadata_value(asset, "evidence_type")
    target_library = _asset_metadata_value(asset, "target_library")
    bonus = 0.0
    if "营业执照" in text or "执照" in text:
        bonus += 0.35 if evidence_type == "business_license" else -0.08
    if any(keyword in text for keyword in ["绿色供应链", "绿色低碳", "低碳", "碳足迹", "废水废气", "环保"]):
        bonus += 0.35 if evidence_type == "green_low_carbon" else -0.08
    if any(keyword in text for keyword in ["生产线", "生产制造", "生产能力", "车间", "厂房"]):
        bonus += 0.35 if evidence_type == "production_capacity" else -0.08
    if any(keyword in text for keyword in ["试验检测", "检测设备", "试验设备", "电子天平", "万能试验机", "维卡", "锤击"]):
        bonus += 0.35 if evidence_type == "testing_capacity" else -0.08
    if any(keyword in text for keyword in ["检验报告", "检测报告", "型式试验", "内径250"]):
        bonus += 0.35 if evidence_type == "inspection_report" else -0.08
    if any(keyword in text for keyword in ["资信", "资质", "证书", "体系认证"]) and target_library == "qualification_library":
        bonus += 0.06
    if any(keyword in text for keyword in ["资质证书", "体系认证", "认证证书"]):
        bonus += 0.45 if evidence_type == "certification" else -0.12
        asset_text = _asset_search_text(asset)
        if any(name in asset_text for name in ["质量管理体系认证证书", "环境管理体系认证证书", "职业健康安全管理体系认证证书"]):
            bonus += 0.25
    if any(keyword in text for keyword in ["企业证明材料", "企业资信", "基础证照"]):
        if evidence_type in {"business_license", "certification", "personnel_certificate", "enterprise_evidence"}:
            bonus += 0.25
    if "社保" in text or "参保" in text:
        bonus += 0.5 if evidence_type == "personnel_certificate" else -0.15
    return bonus


def _asset_rank_score(query: str, asset: dict[str, Any]) -> float:
    return (
        float(asset.get("similarity") or 0)
        + _asset_query_intent_bonus(query, asset)
        + _asset_visual_quality_bonus(query, asset)
    )


def _asset_visual_quality_bonus(query: str, asset: dict[str, Any]) -> float:
    text = query or ""
    if not any(keyword in text for keyword in ["资质证书", "体系认证", "认证证书", "企业证明材料", "企业资信"]):
        return 0.0

    evidence_type = _asset_metadata_value(asset, "evidence_type")
    if evidence_type not in {"certification", "business_license", "personnel_certificate"}:
        return 0.0

    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    specs = asset.get("specs") if isinstance(asset.get("specs"), dict) else {}
    visual_type = str(metadata.get("asset_visual_type") or specs.get("asset_visual_type") or "").lower()
    source_type = str(asset.get("source_type") or "").lower()
    width = int(asset.get("width") or 0)
    height = int(asset.get("height") or 0)
    has_bbox = bool(specs.get("bbox") or metadata.get("bbox"))

    bonus = 0.0
    if visual_type in {"full_page_render", "full_page_certificate", "full_page_document_image", "customer_original_image"}:
        bonus += 0.45
    if source_type in {"customer_pdf_full_page_render", "customer_original_image"}:
        bonus += 0.35
    if source_type == "taichang_mvp_mineru_asset" or has_bbox:
        bonus -= 0.45
    if width and height and (width < 500 or height < 500):
        bonus -= 0.25
    return bonus


def _asset_search_text(asset: dict[str, Any]) -> str:
    parts = [
        asset.get("title"),
        asset.get("description"),
        asset.get("category"),
        asset.get("asset_type"),
        asset.get("searchable_text"),
        asset.get("ai_caption"),
        asset.get("file_name"),
        asset.get("attribution"),
    ]
    parts.extend(asset.get("tags") or [])
    parts.extend(asset.get("applicable_sections") or [])
    parts.extend(asset_applicable_volumes(asset))
    specs = asset.get("specs") or {}
    if isinstance(specs, dict):
        parts.extend(str(value) for value in specs.values() if value)
    metadata = asset.get("metadata") or {}
    if isinstance(metadata, dict):
        for value in metadata.values():
            if isinstance(value, list):
                parts.extend(str(item) for item in value if item)
            elif isinstance(value, (str, int, float, bool)):
                parts.append(str(value))
    return " ".join(str(part) for part in parts if part).lower()


def _asset_query_tokens(query: str) -> list[str]:
    synonym_tokens = {
        "业绩": ["业绩", "类似业绩", "合同", "中标", "验收", "证明材料"],
        "项目业绩": ["项目业绩", "类似业绩", "合同", "合同协议书", "供货合同", "中标", "中标通知书", "招标编号", "包号"],
        "类似业绩": ["类似业绩", "项目业绩", "合同", "合同协议书", "供货合同", "中标", "中标通知书", "招标编号", "包号"],
        "合同": ["合同", "合同协议书", "供货合同", "项目业绩", "证明材料"],
        "合同协议书": ["合同协议书", "供货合同", "合同", "项目业绩", "证明材料"],
        "中标": ["中标", "中标通知书", "招标编号", "包号", "中标单位", "项目业绩", "证明材料"],
        "中标通知书": ["中标通知书", "中标", "招标编号", "包号", "中标单位", "项目业绩", "证明材料"],
        "社保": ["社保", "缴纳", "参保", "人员", "证明"],
        "营业执照": ["营业执照", "执照", "基础证照", "企业证照"],
        "安全生产许可证": ["安全生产", "许可证", "安全生产许可", "资质证书"],
        "资质": ["资质", "证书", "资格", "资信", "许可"],
        "人员": ["人员", "项目经理", "技术负责人", "职称", "执业", "社保"],
        "产品": ["产品", "设备", "参数", "图册", "样张"],
        "生产": ["生产", "生产线", "产线", "车间", "厂房", "制造", "production_capacity"],
        "生产线": ["生产", "生产线", "产线", "车间", "厂房", "制造", "production_capacity"],
        "试验": ["试验", "检测", "试验设备", "检测设备", "电子天平", "万能试验机", "维卡", "锤击", "testing_capacity"],
        "检测": ["试验", "检测", "试验设备", "检测设备", "电子天平", "万能试验机", "维卡", "锤击", "testing_capacity"],
        "绿色供应链": ["绿色供应链", "绿色", "低碳", "esg", "碳足迹", "废水废气", "green_low_carbon"],
        "检验报告": ["检验报告", "检测报告", "型式试验", "cpvc", "mpp", "内径250", "inspection_report"],
        "图片": ["图片", "照片", "图", "附件", "材料", "样张"],
    }
    tokens = set(re.findall(r"[\u4e00-\u9fa5A-Za-z0-9_]+", query.lower()))
    for key, values in synonym_tokens.items():
        if key in query:
            tokens.update(value.lower() for value in values)
    return [token for token in tokens if token]


def _asset_matches_metadata_filter(asset: dict[str, Any], metadata_filter: dict[str, Any]) -> bool:
    if not metadata_filter:
        return True
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    specs = asset.get("specs") if isinstance(asset.get("specs"), dict) else {}

    def values_for(key: str) -> list[Any]:
        if key == "ingestion_batch_id":
            return [
                metadata.get("ingestion_batch_id"),
                metadata.get("source_batch_id"),
                specs.get("ingestion_batch_id"),
                specs.get("source_batch_id"),
                asset.get("ingestion_batch_id"),
            ]
        return [metadata.get(key), specs.get(key), asset.get(key)]

    ignored = {"chunk_layer", "doc_role", "package_code", "province", "batch_no", "material_category"}
    for key, expected in metadata_filter.items():
        if expected in (None, "", "all") or key in ignored:
            continue
        candidates = values_for(str(key))
        expected_values = expected if isinstance(expected, list) else [expected]
        matched = False
        for candidate in candidates:
            candidate_values = candidate if isinstance(candidate, list) else [candidate]
            if any(str(item) == str(value) for item in candidate_values for value in expected_values):
                matched = True
                break
        if not matched:
            return False
    return True


PUBLIC_METADATA_KEYS = {
    "source_display_name",
    "source_document_name",
    "category_label",
    "evidence_type_label",
    "doc_type",
    "report_no",
    "specification_model",
    "source_section",
}


def _public_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    safe = sanitize_source_metadata(metadata or {})
    return {key: safe.get(key) for key in PUBLIC_METADATA_KEYS if safe.get(key) not in (None, "")}


def _public_context_payload(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": context.get("id"),
        "content": sanitize_visible_text(context.get("content") or ""),
        "similarity": context.get("similarity"),
        "retrieval_source": context.get("retrieval_source"),
        "metadata": _public_metadata(context.get("metadata") if isinstance(context.get("metadata"), dict) else {}),
    }


def _public_asset_payload(asset: dict[str, Any]) -> dict[str, Any]:
    safe_assets = sanitize_knowledge_assets([asset])
    safe = safe_assets[0] if safe_assets else dict(asset)
    return {
        "id": safe.get("id"),
        "title": safe.get("title"),
        "description": sanitize_visible_text(safe.get("description") or ""),
        "category": safe.get("category"),
        "asset_type": safe.get("asset_type"),
        "mime_type": safe.get("mime_type"),
        "width": safe.get("width"),
        "height": safe.get("height"),
        "similarity": safe.get("similarity"),
        "url": f"/api/knowledge/assets/{safe.get('id')}/file" if safe.get("id") else safe.get("public_url"),
        "metadata": _public_metadata(safe.get("metadata") if isinstance(safe.get("metadata"), dict) else {}),
    }

def generate_knowledge_answer(
    query: str,
    contexts: List[Dict[str, Any]],
    assets: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """
    组装包含图片链接的 Prompt，让大模型基于知识库生成最终回答
    """
    prompt, images = build_knowledge_prompt(query, contexts, assets)

    from backend.ai.qwen_client import call_dashscope_api

    response = call_dashscope_api(
        [
            {"role": "system", "content": "你是一个严谨的 RAG 知识库问答助手。"},
            {"role": "user", "content": prompt}
        ],
        model=get_stage_model("knowledge"),
        json_mode=False,
        usage_context={
            "stage": "knowledge_answer",
            "operation_type": "text_generation",
            "metadata": {
                "contexts_count": len(contexts),
                "assets_count": len(assets or []),
            },
        },
    )
    answer = response.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content") or ""
    
    return {
        "answer": answer,
        "images": images,
        "assets": [_public_asset_payload(asset) for asset in (assets or [])],
        "raw_contexts": [_public_context_payload(context) for context in contexts],
    }


def build_knowledge_prompt(
    query: str,
    contexts: List[Dict[str, Any]],
    assets: List[Dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    text_contexts = []
    images = []

    for index, ctx in enumerate(contexts, 1):
        content = ctx.get("content", "")
        meta = sanitize_source_metadata(ctx.get("metadata", {}) or {})
        similarity = ctx.get("similarity", 0)
        source = meta.get("source_display_name") or meta.get("source_org") or meta.get("source_file") or "企业知识库"
        doc_type = meta.get("doc_type") or "知识片段"

        text_contexts.append(
            f"【资料{index}｜相关度 {similarity:.2f}｜来源 {source}｜类型 {doc_type}】\n{content}"
        )

        if meta.get("type") == "image" and meta.get("image_url"):
            images.append({
                "url": meta.get("image_url"),
                "alt": meta.get("alt", "未命名图片")
            })

    safe_assets = sanitize_knowledge_assets(assets or [])
    asset_contexts = []
    for index, asset in enumerate(safe_assets, 1):
        title = asset.get("title") or "未命名图片"
        category = asset.get("category") or "图片资产"
        similarity = float(asset.get("similarity") or 0)
        description = sanitize_visible_text(asset.get("description") or asset.get("searchable_text") or "")
        sections = "、".join(asset.get("applicable_sections") or [])
        public_url = f"/api/knowledge/assets/{asset.get('id')}/file" if asset.get("id") else (asset.get("public_url") or "")
        meta = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        is_redacted = bool(
            asset.get("anonymized")
            or meta.get("anonymized")
            or meta.get("is_redacted")
            or "脱敏" in str(title)
        )
        asset_contexts.append(
            f"【图片资产{index}｜相关度 {similarity:.2f}｜分类 {category}】\n"
            f"名称：{title}\n资料属性：{'脱敏样张' if is_redacted else '客户原始资料'}\n"
            f"适用章节：{sections}\n说明：{description}"
        )
        if public_url:
            images.append({
                "url": public_url,
                "alt": title,
            })

    context_str = "\n\n---\n\n".join(text_contexts)
    asset_context_str = "\n\n---\n\n".join(asset_contexts) or "无相关图片资产。"
    query_guidance = ""
    if any(keyword in query for keyword in ["企业证明材料", "企业资信材料", "企业资信"]):
        query_guidance = """
【本题业务口径】：
“企业证明材料”是广义企业事实集合，不是数据库中某一个同名分类。必须逐类核对并回答：
1. 基础证照，例如营业执照；
2. 正式体系认证，例如质量、环境、职业健康安全管理体系认证；
3. 人员与社保证明；
4. 项目业绩、场地、生产检测或企业现场材料（命中时再列出）。
只要资产清单中存在上述材料，就必须列出，不能把回答缩窄为“企业现场照片”。
本题不得主动对项目业绩、合同、中标通知书、检验报告、生产线等其他资料下“未发现”“未包含”或“缺少”的结论；用户未逐项询问时，只需回答已确认存在的企业证明材料。
"""
    elif any(keyword in query for keyword in ["资质证书", "体系认证", "认证证书"]):
        query_guidance = """
【本题业务口径】：
优先核对并逐项列出质量管理体系、环境管理体系、职业健康安全管理体系认证证书。
正式证书原件优先于企业宣传、ESG 或绿色发展类报告。
本题只回答已命中的资质证书和体系认证；不得主动扩展到营业执照、生产许可证、安全生产许可证或其他证照是否缺失。
如果用户没有询问“还缺什么”，不要输出“需要确认或补充”小节，也不要写“当前未提供/未发现/缺少某证照”。
如果某项资料只命中图片资产、没有可靠 OCR 正文，不得推断证书编号、有效期、覆盖范围或与其他证书的一致性，只能按资产名称说明“已命中该证书资料”。
不得把“已命中证书资料”扩展成“证书有效、合格有效、在有效期内、覆盖全部业务范围”等结论；除非资料片段明确给出对应文字。
"""
    elif any(keyword in query for keyword in ["检验报告", "检测报告", "型式试验报告"]):
        query_guidance = """
【本题业务口径】：
检验报告、检测报告和型式试验报告的覆盖范围必须绑定到产品族、规格型号、报告编号和原始资料。
如果资料只命中 CPVC 内径250 或规格 `DS 250×15×6000 SN16 PVC-C`，只能说明该报告覆盖该规格；不得写“已覆盖全部 CPVC 规格”“无需补充其他规格报告”或等价结论。
当用户只询问当前命中的内径250/该规格时，可以说明当前报告可作为该规格依据；其他规格必须提示“需补充对应规格报告或由客户确认”。
报告有效期、适用批次、覆盖产品范围只能来自资料明确文字；资料未说明时写“以报告原件、招标要求和客户确认口径为准”。
"""
    prompt = f"""你是一个专业的企业私有知识库与电网/电力招投标 RAG 问答助手。
你可以同时依据“企业知识库检索片段”和“相关图片/资质资产”回答用户问题。用户询问企业资信库、产品库、业绩材料、人员证书、社保缴纳证明、营业执照、产品图片等私有资产时，应优先基于相关图片/资质资产回答。
不要编造未出现在资料中的证书编号、人员姓名、合同金额或具体日期。

【知识库检索片段】：
{context_str}

【相关图片/资质资产】：
{asset_context_str}

【用户问题】：
{query}

{query_guidance}

回答要求：
1. 必须使用清晰 Markdown 结构回答，推荐固定为：
   - `## 结论`
   - `## 关键信息`
   - `## 操作建议`（如适用）
   - `## 需要确认或补充`（资料不足时必须出现）
   - `## 参考依据`
2. 每个小节下使用短段落或项目符号，避免超过 4 行的长段落。
3. 如果只有图片/资质资产命中、没有文本片段，也要基于资产标题、说明、标签和适用章节回答，并明确这些是“可参考/可插入的企业资料”。
4. 如果资料不足，不要硬答；先说明“当前资料不足以直接确认”，再列出需要补充或需要用户确认的范围。
5. 涉及投标材料、废标风险、施工组织设计等内容时，尽量给出可执行清单。
6. 如果相关图片/资质资产适合展示，只需在对应说明中引用“图片资产1、图片资产2”等编号；不要自行输出图片地址、Markdown 图片链接或占位地址，页面会自动展示对应原图。
7. 最多引用 3 张最相关图片。只有“资料属性”明确为“脱敏样张”时，才说明其不能替代正式法定文件；标记为“客户原始资料”的文件不得描述成脱敏样例、占位图或待替换材料。
8. 不要输出 Markdown 表格，图片建议用自然段和项目符号描述，避免表格在聊天窗口中换行错乱。
9. `## 参考依据` 小节最多引用相关度最高的 3 条资料来源，用“资料1、资料2...”和“图片资产1、图片资产2...”说明依据；图片资产只作为配图/材料建议，不要把它当成法规依据。
10. 当用户一次询问多个资料类型、证据类型或事项（例如“合同或中标通知书”“Logo和生产线图片”）时，必须逐项核对并分别回答；只要检索片段、来源文件名、图片资产名称或说明中出现某一项，就不得笼统回答“未发现”。
11. 禁止输出或复述任何内部技术字段、英文枚举、服务器路径、文件哈希、资产内部编号和 API 路径，只能使用中文业务名称。
12. 判断“缺少某项材料”前，必须同时核对知识片段和图片资产；只要任一处存在营业执照、体系认证、社保或其他原始材料，就不得声称该材料缺失。
13. 对资质证书问题，优先逐项列出质量管理体系、环境管理体系、职业健康安全管理体系等正式证书原件，不得用 ESG、宣传册或绿色发展报告替代正式证书来源。
14. 只回答用户询问的资料范围，不要主动列举无关材料并声称“未发现”或“缺少”；需要补充的项目必须与本次问题直接相关。
15. 证书编号、有效期、发证机构、覆盖范围等细节只能来自知识库检索片段中的明确文字；如果只来自图片资产标题或图片预览，不得自行解释图片内容或把局部印章、局部文字当成完整证书正文。
16. 对检验报告问题，报告覆盖范围必须绑定到具体规格型号和报告编号；不得把单一规格报告泛化为全部产品或全部规格已覆盖。
17. 对证书问题，不能把“存在/已命中证书资料”表述为“有效/合格有效/在有效期内”，除非资料片段明确写明证书状态或有效期。
18. 语言专业、客观、准确，适合非技术标书人员阅读。
"""
    return prompt, images


def stream_knowledge_answer(
    query: str,
    contexts: List[Dict[str, Any]],
    assets: List[Dict[str, Any]] | None = None,
) -> Iterator[Dict[str, Any]]:
    prompt, images = build_knowledge_prompt(query, contexts, assets)
    yield {
        "type": "retrieved",
        "contexts_count": len(contexts),
        "assets_count": len(assets or []),
        "images": images,
        "raw_contexts": [_public_context_payload(context) for context in contexts],
        "assets": [_public_asset_payload(asset) for asset in (assets or [])],
    }

    emitted = False
    try:
        for chunk in stream_dashscope_api(
            [
                {"role": "system", "content": "你是一个严谨的 RAG 知识库问答助手。"},
                {"role": "user", "content": prompt},
            ],
            model=get_stage_model("knowledge"),
            usage_context={
                "stage": "knowledge_answer_stream",
                "operation_type": "text_generation",
                "metadata": {
                    "contexts_count": len(contexts),
                    "assets_count": len(assets or []),
                },
            },
        ):
            emitted = True
            yield {
                "type": "chunk",
                "content": chunk,
            }
    except Exception:
        result = generate_knowledge_answer(query, contexts, assets)
        content = result.get("answer") or ""
        for start in range(0, len(content), 120):
            emitted = True
            yield {
                "type": "chunk",
                "content": content[start:start + 120],
            }

    if not emitted:
        yield {
            "type": "chunk",
            "content": "未能生成回答，请稍后重试或补充更多知识库资料。",
        }

    yield {
        "type": "done",
    }

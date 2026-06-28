"""
知识资产路由模块。

负责（每条路由均双蓝图注册）：
  - GET   /api/knowledge/assets + /api/bidding/knowledge/assets                    查询资产列表
  - GET   /api/knowledge/assets/<id> + /api/bidding/knowledge/assets/<id>          查询资产详情
  - GET   /api/knowledge/assets/<id>/file + /api/bidding/knowledge/assets/<id>/file 下载资产文件
  - POST  /api/knowledge/assets/upload + /api/bidding/knowledge/assets/upload       上传资产
  - PATCH /api/knowledge/assets/<id> + /api/bidding/knowledge/assets/<id>           更新资产

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from collections import OrderedDict
from pathlib import Path

import requests

from flask import Response, current_app, jsonify, request

from backend.api._shared import bp, knowledge_bp
from backend.core.bid_volumes import normalize_volume_list
from backend.core.security import UploadValidationError, safe_upload_filename, validate_uploaded_file
from backend.db.supabase_repo import (
    create_knowledge_asset,
    download_knowledge_asset_file_variant,
    get_knowledge_asset_stats,
    get_knowledge_asset_detail,
    get_knowledge_asset_signed_urls,
    list_knowledge_assets,
    list_knowledge_assets_page,
    update_knowledge_asset,
    upload_knowledge_asset_file,
)
from backend.rag.display_names import category_display_name, sanitize_visible_text
from backend.services.formal_asset_naming import caption_policy, clean_formal_asset_title, formal_asset_caption

# ---------------------------------------------------------------------------
# 进程内图片缓存（LRU，最多 200 条，缓解 Supabase Storage 串行下载瓶颈）
# key: (asset_id, variant)  value: (asset_dict, bytes)
# ---------------------------------------------------------------------------
_ASSET_FILE_CACHE_MAX = 200
_asset_file_cache: OrderedDict[tuple, tuple] = OrderedDict()
_asset_file_cache_lock = threading.Lock()

_VOLUME_LABELS = {
    "technical": "技术标",
    "qualification": "资格文件",
    "business": "商务标",
    "attachment": "附件",
}

_UPLOAD_EVIDENCE_FALLBACKS = {
    "authorization": "授权文件",
    "bid_award_notice": "中标通知书",
    "business_license": "基础证照资料",
    "certification": "资质证书资料",
    "contract": "合同证明",
    "enterprise_evidence": "企业证明材料",
    "finance": "财务资料",
    "green_low_carbon": "绿色低碳资料",
    "inspection_report": "检验报告资料",
    "personnel_certificate": "人员证书资料",
    "product_image": "产品实物图片",
    "production_capacity": "生产制造能力资料",
    "project_performance": "项目业绩资料",
    "product_parameter_table": "产品参数表",
    "social_security": "社保证明",
    "technical_response": "技术响应资料",
    "testing_capacity": "试验检测能力资料",
    "warehouse_capacity": "厂房仓储资料",
}

_SEARCHABLE_SPEC_KEYS = {
    "usage_note",
    "certificate_no",
    "issuer",
    "product_model",
    "formal_display_title",
    "formal_caption",
}

_QUALITY_TIER_LABELS = {
    "formal_bid_ready": "可用于正式标书",
    "knowledge_only": "仅用于知识库",
    "review_only": "需人工复核",
    "restricted": "禁止使用",
}

_IMAGE_FILE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
_STRUCTURED_FILE_EXTENSIONS = {"xls", "xlsx", "csv"}
_DOCUMENT_FILE_EXTENSIONS = {"pdf", "doc", "docx"}


def _get_cached_asset_file(asset_id: str, variant: str):
    key = (asset_id, variant)
    with _asset_file_cache_lock:
        if key in _asset_file_cache:
            _asset_file_cache.move_to_end(key)   # LRU：命中则移到末尾
            return _asset_file_cache[key]
    return None


def _put_cached_asset_file(asset_id: str, variant: str, value: tuple) -> None:
    key = (asset_id, variant)
    with _asset_file_cache_lock:
        _asset_file_cache[key] = value
        _asset_file_cache.move_to_end(key)
        if len(_asset_file_cache) > _ASSET_FILE_CACHE_MAX:
            _asset_file_cache.popitem(last=False)  # 淘汰最久未用的条目


def _split_form_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass
    return [item.strip() for item in re.split(r"[,，\n]", value) if item.strip()]


def _contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def _has_internal_display_trace(value: str) -> bool:
    return bool(
        re.search(
            r"页面[_\-\s]*\d+|原图|parsed_outputs|rag_seed|/api/knowledge/assets|"
            r"\btaichang_|[a-zA-Z]+_[a-zA-Z_]+|\b[a-f0-9]{8}-[a-f0-9-]{27,}\b",
            value or "",
            flags=re.I,
        )
    )


def _infer_upload_evidence_type(
    library_type: str,
    category: str,
    title: str,
    description: str,
    existing: dict | None = None,
) -> str:
    existing = existing or {}
    existing_meta = existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}
    existing_specs = existing.get("specs") if isinstance(existing.get("specs"), dict) else {}
    explicit = (
        request.form.get("evidence_type")
        or existing_meta.get("evidence_type")
        or existing_specs.get("evidence_type")
        or ""
    )
    if explicit:
        return str(explicit).strip()

    category_key = str(category or "").strip()
    if category_key in _UPLOAD_EVIDENCE_FALLBACKS:
        return category_key

    haystack = f"{category} {title} {description}"
    rules = [
        ("business_license", ("营业执照", "基础证照", "统一社会信用代码")),
        ("inspection_report", ("检验报告", "检测报告", "型式试验", "试验报告")),
        ("testing_capacity", ("试验检测", "检测设备", "试验设备", "电子天平", "万能试验机", "维卡")),
        ("production_capacity", ("生产制造", "制造能力", "生产线", "车间", "厂房", "仓储")),
        ("green_low_carbon", ("绿色", "低碳", "环保", "碳足迹", "排污", "废水", "废气")),
        ("project_performance", ("项目业绩", "合同", "中标", "成交通知", "订单", "验收")),
        ("finance", ("财务", "审计", "资产负债", "利润表")),
        ("personnel_certificate", ("人员", "社保", "身份证", "授权委托", "法定代表人")),
        ("certification", ("资质证书", "认证证书", "体系认证", "证书")),
        ("product_image", ("产品实物", "产品图片", "管材", "保护管")),
    ]
    for evidence_type, keywords in rules:
        if any(keyword in haystack for keyword in keywords):
            return evidence_type
    return "enterprise_evidence" if library_type == "qualification" else "product_image"


def _upload_title_fallback(evidence_type: str) -> str:
    return _UPLOAD_EVIDENCE_FALLBACKS.get(evidence_type) or category_display_name(evidence_type) or "企业资料"


def _normalize_uploaded_title(raw_title: str, evidence_type: str) -> str:
    fallback = _upload_title_fallback(evidence_type)
    title = clean_formal_asset_title(raw_title, "")
    title = re.sub(r"(?:上传回归|回归测试|测试样张|测试图片|测试资料|P\d+(?:-\d+)?)", "", title)
    title = re.sub(r"[，,。；;：:\-_\s]+$", "", title).strip()
    if not title or not _contains_chinese(title):
        title = fallback

    if evidence_type in {"production_capacity", "testing_capacity", "green_low_carbon", "product_image"}:
        if not title.endswith(("资料", "照片", "图片")):
            title = f"{title}资料"
    elif evidence_type == "certification" and "证书" not in title:
        title = f"{title}证书"
    elif evidence_type == "inspection_report" and "报告" not in title:
        title = f"{title}检验报告"

    if not title.startswith("泰昌"):
        title = f"泰昌{title}"
    return re.sub(r"\s+", "", title)


def _normalize_upload_category(category: str, evidence_type: str) -> str:
    clean_category = category_display_name(category)
    if not clean_category or clean_category in {"企业资信", "产品资料", "泰昌企业资料"} or _has_internal_display_trace(clean_category):
        clean_category = category_display_name(evidence_type) or _upload_title_fallback(evidence_type)
    return clean_category


def _sanitize_upload_tags(tags: list[str], category: str, evidence_type: str) -> list[str]:
    normalized: list[str] = []
    for tag in tags or []:
        value = category_display_name(str(tag).strip())
        if not value:
            continue
        if value.lower() == "taichang":
            value = "泰昌"
        if _has_internal_display_trace(value) and not _contains_chinese(value):
            continue
        if re.fullmatch(r"[a-zA-Z_]+", value) and not _contains_chinese(value):
            continue
        normalized.append(value)
    normalized.extend(["泰昌", category, category_display_name(evidence_type)])
    deduped: list[str] = []
    seen: set[str] = set()
    for tag in normalized:
        if tag and tag not in seen:
            seen.add(tag)
            deduped.append(tag)
    return deduped


def _build_upload_description(title: str, category: str, description: str) -> str:
    if description:
        cleaned = sanitize_visible_text(description)
        if cleaned and not _has_internal_display_trace(cleaned):
            return cleaned
    return f"河北泰昌电力器材科技有限公司{category}，用于企业知识库展示和正式投标文件引用。"


def _build_asset_searchable_text(payload: dict) -> str:
    parts = [
        payload.get("title"),
        payload.get("description"),
        payload.get("category"),
        payload.get("ai_caption"),
    ]
    parts.extend(payload.get("tags") or [])
    parts.extend(payload.get("applicable_sections") or [])
    parts.extend(_VOLUME_LABELS.get(str(volume), str(volume)) for volume in payload.get("applicable_volumes") or [])
    specs = payload.get("specs") or {}
    if isinstance(specs, dict):
        parts.extend(str(specs.get(key)) for key in _SEARCHABLE_SPEC_KEYS if specs.get(key))
    cleaned_parts = [sanitize_visible_text(part) for part in parts if str(part or "").strip()]
    return "\n".join(part.strip() for part in cleaned_parts if part.strip())


def _asset_file_ext(storage_info: dict | None = None, existing: dict | None = None) -> str:
    storage_info = storage_info or {}
    existing = existing or {}
    candidates = [
        storage_info.get("file_ext"),
        storage_info.get("file_name"),
        existing.get("file_ext"),
        existing.get("file_name"),
        existing.get("storage_path"),
        existing.get("public_url"),
    ]
    for value in candidates:
        text = str(value or "").strip().lower()
        if not text:
            continue
        suffix = Path(text).suffix.lower().lstrip(".")
        if suffix:
            return suffix
        if re.fullmatch(r"[a-z0-9]+", text):
            return text.lstrip(".")
    return ""


def _quality_tier_label(tier: str) -> str:
    return _QUALITY_TIER_LABELS.get(tier, "仅用于知识库")


def _downgrade_quality(current: str, candidate: str) -> str:
    order = {
        "formal_bid_ready": 0,
        "knowledge_only": 1,
        "review_only": 2,
        "restricted": 3,
    }
    return candidate if order.get(candidate, 1) > order.get(current, 1) else current


def _assess_upload_quality(
    *,
    storage_info: dict | None,
    existing: dict | None,
    evidence_type: str,
    title: str,
    raw_title: str,
    description: str,
    requested_allowed_for_bid: bool,
) -> tuple[str, list[str]]:
    storage_info = storage_info or {}
    existing = existing or {}
    ext = _asset_file_ext(storage_info, existing)
    mime_type = str(storage_info.get("mime_type") or existing.get("mime_type") or "").lower()
    file_size = storage_info.get("file_size") or existing.get("file_size")
    file_name = str(storage_info.get("file_name") or existing.get("file_name") or "")
    source_text = f"{file_name} {raw_title} {title} {description}"
    tier = "formal_bid_ready"
    notes: list[str] = []

    if not requested_allowed_for_bid:
        tier = _downgrade_quality(tier, "knowledge_only")
        notes.append("用户设置为仅检索，不自动插入正式标书。")

    if ext in _STRUCTURED_FILE_EXTENSIONS:
        tier = _downgrade_quality(tier, "knowledge_only")
        notes.append("表格资料用于结构化抽取和知识问答，不作为正式标书图片自动插入。")

    if evidence_type == "product_parameter_table" and ext not in _STRUCTURED_FILE_EXTENSIONS:
        tier = _downgrade_quality(tier, "review_only")
        notes.append("产品参数表建议上传原始 Excel 或 CSV，当前文件需人工复核后再用于参数抽取。")

    if ext in {"doc", "docx"}:
        tier = _downgrade_quality(tier, "knowledge_only")
        notes.append("可编辑文档优先用于知识库和结构化抽取，不自动作为标书配图。")

    if ext and ext not in (_IMAGE_FILE_EXTENSIONS | _DOCUMENT_FILE_EXTENSIONS | _STRUCTURED_FILE_EXTENSIONS):
        tier = _downgrade_quality(tier, "review_only")
        notes.append("文件格式不在正式投标资料推荐范围内，需人工确认用途。")

    is_image = mime_type.startswith("image/") or ext in _IMAGE_FILE_EXTENSIONS
    if is_image:
        try:
            if file_size is not None and int(file_size) < 30 * 1024:
                tier = _downgrade_quality(tier, "review_only")
                notes.append("图片文件较小，可能是二维码、截图或局部裁剪图，不自动进入正式标书。")
        except (TypeError, ValueError):
            pass

    if re.search(r"二维码|印章|签名|页脚|截图|局部|裁剪", source_text):
        tier = _downgrade_quality(tier, "review_only")
        notes.append("文件名或说明疑似局部截图、签章或无关切图，需人工复核。")

    if _has_internal_display_trace(source_text) and not _contains_chinese(source_text):
        notes.append("原始文件名缺少中文业务含义，系统已生成正式中文展示字段。")

    if not notes:
        notes.append("资料格式和命名符合正式入库要求，可作为正式标书候选素材。")
    return tier, notes


def _asset_library_type(asset: dict) -> str:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    specs = asset.get("specs") if isinstance(asset.get("specs"), dict) else {}
    for container in (metadata, specs, asset):
        value = str(container.get("library_type") or "").strip()
        if value in {"qualification", "product"}:
            return value
    target_library = str(metadata.get("target_library") or specs.get("target_library") or "").strip()
    if target_library == "qualification_library":
        return "qualification"
    if target_library == "product_library":
        return "product"
    asset_type = str(asset.get("asset_type") or "").strip()
    if asset_type == "qualification_image":
        return "qualification"
    if asset_type == "product_image":
        return "product"
    return ""


def _asset_matches_library_type(asset: dict, library_type: str | None) -> bool:
    if not library_type:
        return True
    return _asset_library_type(asset) == library_type


def _asset_response_payload(asset: dict | None) -> dict:
    item = dict(asset or {})
    item.pop("embedding", None)
    if item.get("searchable_text"):
        item["searchable_text"] = re.sub(r"\s*\n\s*", "；", sanitize_visible_text(item.get("searchable_text")))
    return item


def _asset_response_list(assets: list[dict] | None) -> list[dict]:
    return [_asset_response_payload(asset) for asset in assets or []]


def _parse_positive_int_arg(name: str, default: int, max_value: int | None = None) -> int:
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    value = max(1, value)
    if max_value is not None:
        value = min(value, max_value)
    return value


def _asset_payload_from_form(storage_info: dict | None = None, existing: dict | None = None) -> dict:
    existing = existing or {}
    storage_info = storage_info or {}
    library_type = request.form.get('library_type') or (existing.get("metadata") or {}).get("library_type") or (existing.get("specs") or {}).get("library_type") or 'qualification'
    if library_type not in {'qualification', 'product'}:
        raise ValueError('library_type 仅支持 qualification 或 product')

    asset_type = request.form.get('asset_type') or existing.get("asset_type") or ('qualification_image' if library_type == 'qualification' else 'product_image')
    raw_category = request.form.get('category') or existing.get("category") or ('企业资信' if library_type == 'qualification' else '产品资料')
    raw_title = (
        request.form.get('title')
        or existing.get("title")
        or storage_info.get("file_name")
        or ''
    ).strip()
    raw_description = (request.form.get('description') or existing.get("description") or '').strip()
    evidence_type = _infer_upload_evidence_type(library_type, raw_category, raw_title, raw_description, existing=existing)
    category = _normalize_upload_category(raw_category, evidence_type)
    title = _normalize_uploaded_title(raw_title, evidence_type)
    description = _build_upload_description(title, category, raw_description)
    tags = _split_form_list(request.form.get('tags')) if 'tags' in request.form else (existing.get("tags") or [])
    applicable_sections = _split_form_list(request.form.get('applicable_sections')) if 'applicable_sections' in request.form else (existing.get("applicable_sections") or [])
    fallback_volumes = (
        existing.get("applicable_volumes")
        or (existing.get("specs") or {}).get("applicable_volumes")
        or (existing.get("metadata") or {}).get("applicable_volumes")
        or (["technical"] if library_type == "product" else ["qualification", "business", "attachment"])
    )
    applicable_volumes = (
        normalize_volume_list(_split_form_list(request.form.get('applicable_volumes')))
        if 'applicable_volumes' in request.form
        else normalize_volume_list(fallback_volumes)
    )
    requested_allowed_for_bid = request.form.get('allowed_for_bid', str((existing.get("specs") or {}).get("user_requested_bid_usage", (existing.get("specs") or {}).get("allowed_for_bid", True)))).lower() in {'1', 'true', 'yes', 'on'}
    quality_tier, quality_notes = _assess_upload_quality(
        storage_info=storage_info,
        existing=existing,
        evidence_type=evidence_type,
        title=title,
        raw_title=raw_title,
        description=description,
        requested_allowed_for_bid=requested_allowed_for_bid,
    )
    allowed_for_bid = requested_allowed_for_bid and quality_tier == "formal_bid_ready"
    is_sensitive = request.form.get('is_sensitive', str(existing.get("is_sensitive", False))).lower() in {'1', 'true', 'yes', 'on'}
    anonymized = request.form.get('anonymized', str(existing.get("anonymized", True))).lower() in {'1', 'true', 'yes', 'on'}
    specs = {
        **(existing.get("specs") or {}),
        "library_type": library_type,
        "allowed_for_bid": allowed_for_bid,
        "user_requested_bid_usage": requested_allowed_for_bid,
        "applicable_volumes": applicable_volumes,
        "usage_note": request.form.get('usage_note') or (existing.get("specs") or {}).get("usage_note") or '',
        "certificate_no": request.form.get('certificate_no') or (existing.get("specs") or {}).get("certificate_no") or '',
        "issuer": request.form.get('issuer') or (existing.get("specs") or {}).get("issuer") or '',
        "product_model": request.form.get('product_model') or (existing.get("specs") or {}).get("product_model") or '',
        "evidence_type": evidence_type,
        "evidence_type_label": category_display_name(evidence_type),
        "quality_tier": quality_tier,
        "quality_tier_label": _quality_tier_label(quality_tier),
        "quality_notes": quality_notes,
        "target_library": "qualification_library" if library_type == "qualification" else "product_library",
        "target_library_label": "资信库资料" if library_type == "qualification" else "产品库资料",
        "category_label": category,
        "formal_display_title": title,
    }
    metadata = {
        **(existing.get("metadata") or {}),
        "library_type": library_type,
        "allowed_for_bid": allowed_for_bid,
        "user_requested_bid_usage": requested_allowed_for_bid,
        "applicable_volumes": applicable_volumes,
        "upload_source": "enterprise_library_page",
    }
    metadata.setdefault("enterprise", "泰昌")
    metadata.setdefault("doc_owner", "河北泰昌电力器材科技有限公司")
    metadata.setdefault("source_domain", "enterprise_fact")
    metadata.setdefault("reference_only", False)
    metadata.setdefault("fact_source_allowed_for_enterprise", True)
    metadata.setdefault("tenant_visibility", "taichang_only")
    metadata.setdefault("access_scope", "taichang_tenant_internal")
    metadata["target_library"] = "qualification_library" if library_type == "qualification" else "product_library"
    metadata["target_library_label"] = "资信库资料" if library_type == "qualification" else "产品库资料"
    metadata["evidence_type"] = evidence_type
    metadata["evidence_type_label"] = category_display_name(evidence_type)
    metadata["category_label"] = category
    metadata["quality_tier"] = quality_tier
    metadata["quality_tier_label"] = _quality_tier_label(quality_tier)
    metadata["quality_notes"] = quality_notes
    metadata["source_display_name"] = title
    metadata["source_document_name"] = title.removeprefix("泰昌")
    metadata["asset_visual_type"] = (
        "customer_original_image"
        if str(storage_info.get("mime_type") or existing.get("mime_type") or "").startswith("image/")
        else "customer_uploaded_document"
    )
    metadata["ui_name_policy"] = "domestic_chinese_friendly"
    metadata["display_language"] = "zh-CN"
    metadata["caption_policy"] = "formal_bid_clean"
    if storage_info:
        metadata.update({
            "thumbnail_storage_bucket": storage_info.get("thumbnail_bucket"),
            "thumbnail_storage_path": storage_info.get("thumbnail_path"),
            "thumbnail_mime_type": storage_info.get("thumbnail_mime_type"),
            "thumbnail_size": storage_info.get("thumbnail_size"),
        })

    payload = {
        "title": title,
        "description": description,
        "category": category,
        "asset_type": asset_type,
        "source_type": existing.get("source_type") or "user_upload",
        "license": request.form.get('license') or existing.get("license") or "企业自有资料",
        "attribution": request.form.get('attribution') or existing.get("attribution") or "用户上传",
        "is_synthetic": bool(existing.get("is_synthetic", False)),
        "is_sensitive": is_sensitive,
        "anonymized": anonymized,
        "industry": existing.get("industry") or "电网行业",
        "applicable_sections": applicable_sections,
        "applicable_volumes": applicable_volumes,
        "tags": _sanitize_upload_tags(tags, category, evidence_type),
        "specs": specs,
        "ai_caption": description,
        "status": "indexed",
        "metadata": metadata,
    }
    if storage_info:
        payload.update({
            "file_name": storage_info.get("file_name"),
            "file_ext": storage_info.get("file_ext"),
            "mime_type": storage_info.get("mime_type"),
            "file_size": storage_info.get("file_size"),
            "storage_bucket": storage_info.get("bucket"),
            "storage_path": storage_info.get("object_path"),
            "public_url": storage_info.get("public_url"),
        })
    formal_caption = formal_asset_caption(payload)
    if formal_caption:
        payload["metadata"]["formal_caption"] = formal_caption
        payload["specs"]["formal_caption"] = formal_caption
    payload["metadata"]["caption_policy"] = caption_policy(payload)
    payload["searchable_text"] = _build_asset_searchable_text(payload)
    return payload


def _maybe_attach_asset_embedding(payload: dict) -> None:
    try:
        from backend.rag.vector_store import init_ali_client, get_embeddings
        embeddings = get_embeddings(init_ali_client(), [payload["searchable_text"]])
        if embeddings:
            payload["embedding"] = embeddings[0]
    except Exception:
        logging.exception("知识资产 embedding 生成失败，将仅保存结构化资产")


@knowledge_bp.route('/assets', methods=['GET'])
@bp.route('/knowledge/assets', methods=['GET'])
def get_knowledge_assets():
    try:
        asset_type = request.args.get('asset_type')
        category = request.args.get('category')
        library_type = request.args.get('library_type')
        if library_type and library_type not in {"qualification", "product"}:
            return jsonify({'error': 'library_type 仅支持 qualification 或 product'}), 400
        use_pagination = any(key in request.args for key in ("page", "page_size", "limit", "offset"))
        if use_pagination:
            if request.args.get("offset") not in (None, ""):
                page_size = _parse_positive_int_arg("limit", 20, 100)
                try:
                    offset = max(0, int(request.args.get("offset") or 0))
                except (TypeError, ValueError):
                    offset = 0
                page = (offset // page_size) + 1
            else:
                page = _parse_positive_int_arg("page", 1)
                page_size = _parse_positive_int_arg("page_size", _parse_positive_int_arg("limit", 20, 100), 100)
            page_result = list_knowledge_assets_page(
                page=page,
                page_size=page_size,
                asset_type=asset_type,
                category=category,
                library_type=library_type,
            )
            if library_type:
                page_result["stats"] = get_knowledge_asset_stats(library_type)
            page_result["items"] = _asset_response_list(page_result.get("items") or [])
            return jsonify(page_result), 200
        assets = list_knowledge_assets(asset_type=asset_type, category=category)
        if library_type:
            assets = [asset for asset in assets if _asset_matches_library_type(asset, library_type)]
        return jsonify(_asset_response_list(assets)), 200
    except Exception as e:
        logging.exception("查询知识资产列表失败")
        return jsonify({'error': f'查询失败: {str(e)}'}), 500


@knowledge_bp.route('/assets/stats', methods=['GET'])
@bp.route('/knowledge/assets/stats', methods=['GET'])
def get_knowledge_assets_stats_api():
    try:
        library_type = request.args.get('library_type')
        if library_type and library_type not in {"qualification", "product"}:
            return jsonify({'error': 'library_type 仅支持 qualification 或 product'}), 400
        return jsonify(get_knowledge_asset_stats(library_type)), 200
    except Exception as e:
        logging.exception("查询知识资产统计失败")
        return jsonify({'error': f'查询失败: {str(e)}'}), 500


@knowledge_bp.route('/assets/<asset_id>', methods=['GET'])
@bp.route('/knowledge/assets/<asset_id>', methods=['GET'])
def get_knowledge_asset(asset_id):
    try:
        asset = get_knowledge_asset_detail(asset_id)
        if not asset:
            return jsonify({'error': '知识资产不存在'}), 404
        return jsonify(_asset_response_payload(asset)), 200
    except Exception as e:
        logging.exception("查询知识资产详情失败")
        return jsonify({'error': f'查询失败: {str(e)}'}), 500


@knowledge_bp.route('/assets/<asset_id>/file', methods=['GET'])
@bp.route('/knowledge/assets/<asset_id>/file', methods=['GET'])
def get_knowledge_asset_file(asset_id):
    try:
        variant = request.args.get("variant") or "original"

        # 先查进程内缓存，命中则直接返回，避免重复从 Supabase Storage 下载
        cached = _get_cached_asset_file(asset_id, variant)
        if cached:
            asset, data = cached
            mime_type = asset.get("mime_type") or "application/octet-stream"
            filename = asset.get("file_name") or asset.get("title") or asset_id
            return Response(
                data,
                mimetype=mime_type,
                headers={
                    "Content-Disposition": f"inline; filename*=UTF-8''{requests.utils.quote(str(filename))}",
                    "Cache-Control": "private, max-age=86400" if variant == "thumb" else "private, max-age=300",
                    "X-Cache": "HIT",
                },
            )

        result = download_knowledge_asset_file_variant(asset_id, variant=variant)
        if not result:
            return jsonify({'error': '知识资产文件不存在'}), 404

        asset, data = result
        # 写入缓存（只缓存合理大小的图片，超过 8 MB 的不缓存避免内存压力）
        if len(data) <= 8 * 1024 * 1024:
            _put_cached_asset_file(asset_id, variant, (asset, data))

        mime_type = asset.get("mime_type") or "application/octet-stream"
        filename = asset.get("file_name") or asset.get("title") or asset_id
        return Response(
            data,
            mimetype=mime_type,
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{requests.utils.quote(str(filename))}",
                "Cache-Control": "private, max-age=86400" if variant == "thumb" else "private, max-age=300",
                "X-Cache": "MISS",
            },
        )
    except Exception as e:
        logging.exception("读取知识资产文件失败")
        return jsonify({'error': f'读取文件失败: {str(e)}'}), 500


@knowledge_bp.route('/assets/signed-urls', methods=['POST'])
@bp.route('/knowledge/assets/signed-urls', methods=['POST'])
def get_knowledge_asset_signed_urls_api():
    """
    批量生成知识资产的前端可访问 URL。

    请求体：{ "assetIds": ["uuid1", "uuid2", ...], "expiresIn": 3600 }
    返回：{ "urls": { "uuid1": "https://...", "uuid2": "https://..." } }

    云端对象存储返回签名 URL；本地 storage 模式返回后端文件接口 URL。
    """
    try:
        payload = request.get_json(silent=True) or {}
        asset_ids = payload.get("assetIds") or []
        expires_in = int(payload.get("expiresIn") or 3600)
        expires_in = max(60, min(expires_in, 7 * 24 * 3600))  # 限制在 1 分钟到 7 天之间

        if not isinstance(asset_ids, list) or not asset_ids:
            return jsonify({"urls": {}}), 200

        # 最多一次处理 50 个，防止滥用
        asset_ids = [str(aid) for aid in asset_ids[:50] if aid]

        urls = get_knowledge_asset_signed_urls(asset_ids, expires_in=expires_in)
        return jsonify({"urls": urls}), 200
    except Exception as e:
        logging.exception("批量生成资产签名 URL 失败")
        return jsonify({"error": f"生成签名 URL 失败: {str(e)}"}), 500


@knowledge_bp.route('/assets/upload', methods=['POST'])
@bp.route('/knowledge/assets/upload', methods=['POST'])
def upload_knowledge_asset():
    try:
        file = request.files.get('file')
        if not file or not file.filename:
            return jsonify({'error': '请上传图片或附件文件'}), 400
        try:
            validate_uploaded_file(file, kind="asset")
        except UploadValidationError as exc:
            return jsonify({'error': str(exc)}), 400

        upload_dir = Path(current_app.config['UPLOAD_FOLDER'])
        upload_dir.mkdir(parents=True, exist_ok=True)
        original_filename = file.filename
        unique_filename = f"asset-{uuid.uuid4()}-{safe_upload_filename(original_filename, 'asset')}"
        local_path = upload_dir / unique_filename
        file.save(local_path)

        storage_info = upload_knowledge_asset_file(
            local_file_path=local_path,
            original_filename=original_filename,
            library_type=request.form.get('library_type') or 'qualification',
        )
        storage_info["file_name"] = original_filename

        payload = _asset_payload_from_form(storage_info=storage_info)
        _maybe_attach_asset_embedding(payload)

        asset = create_knowledge_asset(payload)
        return jsonify(_asset_response_payload(asset)), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.exception("上传知识资产失败")
        return jsonify({'error': f'上传失败: {str(e)}'}), 500


@knowledge_bp.route('/assets/<asset_id>', methods=['PATCH'])
@bp.route('/knowledge/assets/<asset_id>', methods=['PATCH'])
def update_knowledge_asset_api(asset_id):
    try:
        existing = get_knowledge_asset_detail(asset_id)
        if not existing:
            return jsonify({'error': '知识资产不存在'}), 404

        file = request.files.get('file')
        storage_info = None
        if file and file.filename:
            try:
                validate_uploaded_file(file, kind="asset")
            except UploadValidationError as exc:
                return jsonify({'error': str(exc)}), 400
            library_type = request.form.get('library_type') or (existing.get("metadata") or {}).get("library_type") or (existing.get("specs") or {}).get("library_type") or 'qualification'
            upload_dir = Path(current_app.config['UPLOAD_FOLDER'])
            upload_dir.mkdir(parents=True, exist_ok=True)
            original_filename = file.filename
            unique_filename = f"asset-{uuid.uuid4()}-{safe_upload_filename(original_filename, 'asset')}"
            local_path = upload_dir / unique_filename
            file.save(local_path)
            storage_info = upload_knowledge_asset_file(
                local_file_path=local_path,
                original_filename=original_filename,
                library_type=library_type,
            )
            storage_info["file_name"] = original_filename

        payload = _asset_payload_from_form(storage_info=storage_info, existing=existing)
        _maybe_attach_asset_embedding(payload)
        asset = update_knowledge_asset(asset_id, payload)
        return jsonify(_asset_response_payload(asset)), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.exception("更新知识资产失败")
        return jsonify({'error': f'更新失败: {str(e)}'}), 500

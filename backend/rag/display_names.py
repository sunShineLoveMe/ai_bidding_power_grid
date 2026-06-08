"""Chinese display-name helpers for RAG sources."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


INTERNAL_NAME_LABELS = {
    "taichang_business_license_private": "泰昌基础证照资料",
    "taichang_business_license_taichang_internal_private": "泰昌基础证照资料",
    "taichang_certification_private": "泰昌资质证书资料",
    "taichang_finance_taichang_internal_private": "泰昌财务资料",
    "taichang_green_low_carbon_private": "泰昌绿色低碳资料",
    "taichang_inspection_report_private": "泰昌检验报告资料",
    "taichang_production_capacity_private": "泰昌生产制造能力资料",
    "taichang_production_capacity_taichang_internal_private": "泰昌生产制造能力资料",
    "taichang_testing_capacity_private": "泰昌试验检测能力资料",
    "taichang_testing_capacity_taichang_internal_private": "泰昌试验检测能力资料",
    "technical_qualification_response_phrase": "技术资格响应标准话术",
    "power_grid_standards_catalog": "电网标准规范目录",
    "power_grid_section_library": "电网标书章节标准话术",
    "qualification_response_phrases": "资格响应标准话术",
    "business_response_phrases": "商务响应标准话术",
    "quality_safety_environment_phrases": "质量安全环保响应标准话术",
    "bid_document_checklist": "投标文件核查清单",
    "power_grid_rag_ingestion_notes": "电网RAG资料入库说明",
}

CATEGORY_LABELS = {
    "power_grid_tender_documents": "电网招投标资料",
    "power_grid_policy_regulations": "电网政策法规",
    "power_grid_standard_phrases": "电网标准话术",
    "01_tender_documents": "招标文件资料",
    "02_policy_regulations": "政策法规资料",
    "03_standards_specs": "标准规范资料",
    "04_standard_phrases": "标准话术资料",
    "05_enterprise_documents": "泰昌企业资料",
    "structured_product_parameter_json": "泰昌产品结构化参数",
}

EVIDENCE_TYPE_LABELS = {
    "business_license": "基础证照",
    "certification": "资质证书",
    "enterprise_evidence": "企业证明材料",
    "finance": "财务资料",
    "green_low_carbon": "绿色低碳资料",
    "inspection_report": "检验报告",
    "production_capacity": "生产制造能力",
    "testing_capacity": "试验检测能力",
}

TARGET_LIBRARY_LABELS = {
    "knowledge_library": "知识库资料",
    "product_library": "产品库资料",
    "qualification_library": "资信库资料",
    "reference_template_library": "参考模板资料",
}


def _basename(value: str) -> str:
    name = Path(value).name if "/" in value else value
    if name.endswith(".url.md"):
        name = name[:-7]
    else:
        name = re.sub(r"\.(md|pdf|docx?|xlsx?|csv|txt)$", "", name, flags=re.I)
    name = re.sub(r"_[0-9a-f]{6,}$", "", name, flags=re.I)
    name = re.sub(r"^\d+[._-]?", "", name).strip()
    return name


def _contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def _is_internal_name(value: str) -> bool:
    return bool(re.search(r"[a-zA-Z]+_[a-zA-Z_]+", value or ""))


def category_display_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return CATEGORY_LABELS.get(raw) or EVIDENCE_TYPE_LABELS.get(raw) or TARGET_LIBRARY_LABELS.get(raw) or raw


def source_display_name(metadata: dict[str, Any] | None, fallback_title: str | None = None) -> str:
    meta = metadata or {}
    explicit = str(meta.get("source_display_name") or "").strip()
    if explicit:
        return explicit

    for key in ("source_file", "source_org", "category_label", "category", "source_category", "target_library", "evidence_type"):
        value = str(meta.get(key) or "").strip()
        if not value:
            continue
        base = _basename(value)
        lowered = base.lower()
        if lowered in INTERNAL_NAME_LABELS:
            return INTERNAL_NAME_LABELS[lowered]
        if base in CATEGORY_LABELS:
            return CATEGORY_LABELS[base]
        if base in EVIDENCE_TYPE_LABELS:
            return f"泰昌{EVIDENCE_TYPE_LABELS[base]}"
        if base in TARGET_LIBRARY_LABELS:
            return TARGET_LIBRARY_LABELS[base]
        if _contains_chinese(base) and not _is_internal_name(base):
            return base

    title = _basename(str(fallback_title or ""))
    if title.lower() in INTERNAL_NAME_LABELS:
        return INTERNAL_NAME_LABELS[title.lower()]
    if _contains_chinese(title) and not _is_internal_name(title):
        return title
    return "企业知识库资料"


def sanitize_source_metadata(metadata: dict[str, Any] | None, fallback_title: str | None = None) -> dict[str, Any]:
    meta = dict(metadata or {})
    meta["source_display_name"] = source_display_name(meta, fallback_title=fallback_title)
    if meta.get("source_category") == "05_enterprise_documents" or meta.get("source_domain") == "enterprise_fact":
        meta["category_label"] = category_display_name(meta.get("source_category") or "05_enterprise_documents")
    elif meta.get("category_label"):
        meta["category_label"] = category_display_name(meta.get("category_label"))
    elif meta.get("category"):
        meta["category_label"] = category_display_name(meta.get("category"))
    elif meta.get("source_category"):
        meta["category_label"] = category_display_name(meta.get("source_category"))
    if meta.get("source_category"):
        meta["source_category_label"] = category_display_name(meta.get("source_category"))
    if meta.get("target_library"):
        meta["target_library_label"] = category_display_name(meta.get("target_library"))
    if meta.get("evidence_type"):
        meta["evidence_type_label"] = category_display_name(meta.get("evidence_type"))
    return meta


def sanitize_source_contexts(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for context in contexts or []:
        item = dict(context)
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        item["metadata"] = sanitize_source_metadata(metadata)
        sanitized.append(item)
    return sanitized

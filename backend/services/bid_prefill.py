from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from backend.db.supabase_repo import (
    get_project_interpretation,
    list_bid_sections,
    list_knowledge_assets,
    update_bid_analysis_project_meta,
    update_bid_section_content,
)
from backend.export.md_to_word import DOCX_BIDDER_FULL_NAME
from backend.services.taichang_bid_context import build_taichang_prefill_values


Status = str


@dataclass(frozen=True)
class PrefillFieldSpec:
    key: str
    label: str
    group: str
    value_type: str
    required_level: str
    risk_level: str
    source_policy: str
    editable: bool = True
    customer_decision: bool = False


PREFILL_SCHEMA_VERSION = "2026-06-16.v1"
PREFILL_META_KEY = "bid_prefill"
NON_FINAL_CONFIRMATION_MARKERS = (
    "内部测试",
    "模拟值",
    "非正式报价",
    "非正式保证金",
    "仅供测试",
    "test-only",
    "regression-only",
)
NON_FINAL_CONFIRMATION_RE = re.compile(r"(?:待|需).{0,8}确认|待补充")
PLACEHOLDER_RE = re.compile(r"【\s*待(?:补充|填写|确认|核对)\s*[：:]?\s*([^】]*)】")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIAONING_GOODS_ROWS_PATH = PROJECT_ROOT / (
    "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/"
    "goods_tables/goods_rows.json"
)
LIAONING_TECHNICAL_PARAMETER_ROWS_PATH = PROJECT_ROOT / (
    "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/"
    "staging/technical_parameters/technical_parameter_rows.json"
)
LIAONING_TECHNICAL_DEVIATION_ROWS_PATH = PROJECT_ROOT / (
    "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/"
    "staging/technical_parameters/technical_deviations/technical_deviation_rows.json"
)
TAICHANG_PRODUCT_PARAMETER_ROWS_PATH = PROJECT_ROOT / (
    "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/"
    "staging/taichang_product_parameters/taichang_product_parameter_rows.json"
)

PREFILL_FIELD_SPECS: tuple[PrefillFieldSpec, ...] = (
    PrefillFieldSpec("project_name", "项目名称", "项目信息", "text", "formal_required", "medium", "招标文件解析优先，用户确认"),
    PrefillFieldSpec("tender_no", "招标编号", "项目信息", "text", "formal_required", "medium", "招标文件解析优先，用户确认"),
    PrefillFieldSpec("tender_unit", "招标人", "项目信息", "text", "formal_required", "medium", "招标文件解析优先，用户确认"),
    PrefillFieldSpec("agency", "招标代理机构", "项目信息", "text", "recommended", "low", "招标文件解析优先"),
    PrefillFieldSpec("package_no", "包号", "包件/货物清单", "text", "formal_required", "high", "招标文件/货物清单识别后必须确认"),
    PrefillFieldSpec("package_name", "包名称", "包件/货物清单", "text", "formal_required", "high", "招标文件/货物清单识别后必须确认"),
    PrefillFieldSpec("material_category", "物料类别", "包件/货物清单", "text", "formal_required", "medium", "招标文件、货物清单或技术规范识别"),
    PrefillFieldSpec("goods_list_summary", "货物清单摘要", "包件/货物清单", "table_summary", "formal_required", "high", "货物清单结构化抽取，用户确认"),
    PrefillFieldSpec("delivery_place", "交货地点", "包件/货物清单", "text", "recommended", "medium", "招标文件或货物清单识别"),
    PrefillFieldSpec("bidder_name", "投标人名称", "投标主体", "text", "formal_required", "high", "企业资料固定事实，用户确认", editable=False),
    PrefillFieldSpec("unified_social_credit_code", "统一社会信用代码", "投标主体", "text", "formal_required", "medium", "营业执照/企业资信库带出"),
    PrefillFieldSpec("legal_representative", "法定代表人", "投标主体", "text", "formal_required", "medium", "营业执照/企业资信库带出"),
    PrefillFieldSpec("company_address", "企业地址", "投标主体", "text", "recommended", "low", "营业执照/企业资信库带出"),
    PrefillFieldSpec("total_bid_price", "投标总价", "商务报价", "money", "formal_required", "critical", "客户商务决策，禁止 AI 自动补", customer_decision=True),
    PrefillFieldSpec("total_bid_price_upper", "投标总价大写", "商务报价", "text", "formal_required", "critical", "客户商务决策，禁止 AI 自动补", customer_decision=True),
    PrefillFieldSpec("tax_rate", "税率", "商务报价", "percent", "formal_required", "critical", "客户商务决策，禁止 AI 自动补", customer_decision=True),
    PrefillFieldSpec("bid_bond_amount", "投标保证金金额", "保证金与账户", "money", "formal_required", "critical", "招标要求 + 客户财务确认，禁止 AI 自动补", customer_decision=True),
    PrefillFieldSpec("bid_bond_form", "投标保证金形式", "保证金与账户", "enum", "formal_required", "critical", "招标要求 + 客户财务确认，禁止 AI 自动补", customer_decision=True),
    PrefillFieldSpec("basic_account", "基本账户信息", "保证金与账户", "text", "recommended", "high", "开户资料/客户财务确认", customer_decision=True),
    PrefillFieldSpec("delivery_period", "交货期承诺", "投标承诺", "text", "formal_required", "critical", "招标要求识别后必须人工确认", customer_decision=True),
    PrefillFieldSpec("warranty_period", "质保期承诺", "投标承诺", "text", "formal_required", "critical", "招标要求识别后必须人工确认", customer_decision=True),
    PrefillFieldSpec("bid_validity_days", "投标有效期", "投标承诺", "number", "formal_required", "high", "招标文件识别后必须人工确认"),
    PrefillFieldSpec("after_sales_response_time", "售后响应时间", "投标承诺", "text", "recommended", "medium", "招标要求/企业服务承诺识别"),
    PrefillFieldSpec("authorized_representative", "授权代表", "授权签章", "text", "formal_required", "critical", "客户法务/投标经办确认，禁止 AI 自动补", customer_decision=True),
    PrefillFieldSpec("authorized_representative_id", "授权代表身份证号", "授权签章", "text", "formal_required", "critical", "客户法务/投标经办确认，禁止 AI 自动补", customer_decision=True),
    PrefillFieldSpec("authorized_representative_phone", "授权代表联系方式", "授权签章", "text", "recommended", "high", "客户法务/投标经办确认，禁止 AI 自动补", customer_decision=True),
    PrefillFieldSpec("signature_date", "签署日期", "授权签章", "date", "formal_required", "critical", "客户确认，不自动推断", customer_decision=True),
    PrefillFieldSpec("qualification_assets", "资信证照附件", "企业资信", "asset_list", "formal_required", "medium", "企业资信库带出，用户确认是否采用"),
    PrefillFieldSpec("inspection_reports", "检验报告附件", "检测报告", "asset_list", "formal_required", "medium", "企业产品库/资信库带出，用户确认适用型号"),
    PrefillFieldSpec("project_performance_cases", "项目业绩证明", "项目业绩", "asset_list", "recommended", "medium", "企业知识库/资信库带出，用户确认采用"),
    PrefillFieldSpec("product_models", "产品规格型号", "企业产品", "text_list", "formal_required", "high", "产品库/检验报告/货物清单识别后确认"),
    PrefillFieldSpec("technical_parameter_summary", "技术参数表候选摘要", "技术响应", "table_summary", "formal_required", "high", "技术参数表结构化抽取，客户确认"),
    PrefillFieldSpec("technical_deviation_candidates", "技术偏差表候选", "技术响应", "table_summary", "formal_required", "high", "结构化偏差辅助，客户确认，不自动写无偏差"),
    PrefillFieldSpec("taichang_parameter_match_summary", "泰昌参数佐证摘要", "企业产品", "table_summary", "recommended", "high", "泰昌检验报告结构化参数 + 辽宁需求 QA 比对"),
    PrefillFieldSpec("product_image_assets", "产品及生产能力图片", "企业产品", "asset_list", "recommended", "medium", "产品库图片资产带出，用户确认是否插图"),
)


def build_bid_prefill_report(project_id: str) -> dict[str, Any]:
    interpretation = get_project_interpretation(project_id)
    project_meta = _project_meta(interpretation)
    saved_prefill = project_meta.get(PREFILL_META_KEY) if isinstance(project_meta.get(PREFILL_META_KEY), dict) else {}
    confirmed_values = saved_prefill.get("confirmed_values") if isinstance(saved_prefill.get("confirmed_values"), dict) else {}
    assets = _safe_list_knowledge_assets()
    fields = [_build_field(spec, interpretation, assets, confirmed_values) for spec in PREFILL_FIELD_SPECS]
    section_candidates = _build_section_candidates(fields, _safe_list_bid_sections(project_id))
    status_counts = Counter(field["status"] for field in fields)
    required_gaps = [
        field for field in fields
        if field["requiredLevel"] == "formal_required" and field["status"] in {"customer_required", "manual_confirm"}
    ]

    return {
        "schemaVersion": PREFILL_SCHEMA_VERSION,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "project": interpretation.get("project") or {},
        "summary": {
            "totalFields": len(fields),
            "systemRecognized": status_counts.get("system_recognized", 0),
            "enterpriseLibrary": status_counts.get("enterprise_library", 0),
            "customerRequired": status_counts.get("customer_required", 0),
            "manualConfirm": status_counts.get("manual_confirm", 0),
            "formalRequiredGaps": len(required_gaps),
            "readonlyFirst": True,
            "affectsSectionsSnapshotExport": bool(saved_prefill.get("applied_at")),
            "readyForFormalExport": bool(saved_prefill.get("ready_for_formal_export")),
            "unresolvedPlaceholderCount": int(saved_prefill.get("unresolved_placeholder_count") or 0),
        },
        "groups": _group_fields(fields),
        "fields": fields,
        "sectionCandidates": section_candidates,
        "gapReport": {
            "title": "客户确认缺口报告",
            "formalRequiredGaps": required_gaps,
            "customerRequiredFields": [field for field in fields if field["status"] == "customer_required"],
            "manualConfirmFields": [field for field in fields if field["status"] == "manual_confirm"],
        },
        "sourceRules": [
            "招标文件解析字段只作为候选值，包号、货物清单、交货期等正式投标字段仍需确认。",
            "企业知识库、资信库、产品库只提供可追溯事实和附件候选，不自动代表本次投标采用。",
            "报价、保证金、授权代表、签署日期等客户决策字段禁止 AI 自动补全。",
            "确认值只在用户点击“确认并应用”后回填明确占位符，不覆盖用户已编辑的普通正文。",
        ],
        "confirmation": saved_prefill,
    }


def _build_field(
    spec: PrefillFieldSpec,
    interpretation: dict[str, Any],
    assets: list[dict[str, Any]],
    confirmed_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value, evidence, confidence = _candidate_value(spec.key, interpretation, assets)
    if spec.customer_decision and not value:
        status: Status = "customer_required"
    elif spec.key in {
        "package_no",
        "package_name",
        "goods_list_summary",
        "delivery_period",
        "warranty_period",
        "technical_parameter_summary",
        "technical_deviation_candidates",
        "taichang_parameter_match_summary",
    } and value:
        status = "manual_confirm"
    elif spec.key in {"qualification_assets", "inspection_reports", "project_performance_cases", "product_image_assets"}:
        status = "enterprise_library" if value else "manual_confirm"
    elif value and evidence.get("sourceType") in {"enterprise_library", "taichang_verified_fact_pack"}:
        status = "enterprise_library"
    elif value:
        status = "system_recognized"
    else:
        status = "manual_confirm"

    return {
        "key": spec.key,
        "label": spec.label,
        "group": spec.group,
        "valueType": spec.value_type,
        "requiredLevel": spec.required_level,
        "riskLevel": spec.risk_level,
        "sourcePolicy": spec.source_policy,
        "editable": spec.editable,
        "customerDecision": spec.customer_decision,
        "status": status,
        "statusLabel": _status_label(status),
        "value": value,
        "confirmedValue": (confirmed_values or {}).get(spec.key),
        "confidence": confidence,
        "evidence": evidence,
        "mapsTo": _maps_to(spec.key),
    }


def apply_bid_prefill_confirmation(project_id: str, values: dict[str, Any]) -> dict[str, Any]:
    """Persist confirmed variables and replace only explicit placeholders."""
    interpretation = get_project_interpretation(project_id)
    project_meta = _project_meta(interpretation)
    normalized = _normalize_confirmed_values(values)
    changed_sections: list[dict[str, Any]] = []
    replacement_count = 0
    initial_sections = list_bid_sections(project_id)
    section_candidates = _build_section_candidates(
        [_build_field(spec, interpretation, [], normalized) for spec in PREFILL_FIELD_SPECS],
        initial_sections,
    )

    for section in initial_sections:
        original = str(section.get("content") or "")
        updated, replacements = apply_confirmed_values_to_text(original, normalized)
        if updated == original:
            continue
        applied_at = datetime.now().isoformat(timespec="seconds")
        saved = update_bid_section_content(
            project_id,
            str(section.get("id") or ""),
            updated,
            "edited",
            section,
            metadata_patch={
                "prefill_schema_version": PREFILL_SCHEMA_VERSION,
                "prefill_applied_at": applied_at,
                "prefill_replacement_count": replacements,
            },
        )
        changed_sections.append({
            "id": saved.get("id") or section.get("id"),
            "title": saved.get("title") or section.get("title"),
            "replacements": replacements,
        })
        replacement_count += replacements

    final_sections = list_bid_sections(project_id)
    unresolved = _collect_unresolved_placeholders(final_sections)
    missing_required = _missing_required_confirmations(normalized)
    export_gate = _build_prefill_export_gate(final_sections, normalized, section_candidates)
    applied_at = datetime.now().isoformat(timespec="seconds")
    confirmation = {
        "schema_version": PREFILL_SCHEMA_VERSION,
        "confirmed_at": applied_at,
        "applied_at": applied_at,
        "confirmed_values": normalized,
        "changed_section_count": len(changed_sections),
        "replacement_count": replacement_count,
        "unresolved_placeholder_count": len(unresolved),
        "unresolved_placeholders": unresolved[:100],
        "missing_formal_required_fields": missing_required,
        "section_application_summary": export_gate["section_application_summary"],
        "export_gate": export_gate,
        "ready_for_formal_export": export_gate["ready"],
    }
    if not update_bid_analysis_project_meta(project_id, {**project_meta, PREFILL_META_KEY: confirmation}):
        raise RuntimeError("投标确认值持久化失败")
    return {**confirmation, "changed_sections": changed_sections}


def confirmed_prefill_context(project_meta: dict[str, Any]) -> dict[str, str]:
    saved = project_meta.get(PREFILL_META_KEY) if isinstance(project_meta.get(PREFILL_META_KEY), dict) else {}
    values = saved.get("confirmed_values") if isinstance(saved.get("confirmed_values"), dict) else {}
    return {str(key): str(value) for key, value in values.items() if str(value).strip()}


def formal_confirmation_issue(value: Any) -> str | None:
    """说明字段为何不能作为正式客户确认值。"""
    text = str(value or "").strip()
    if not text:
        return "未填写"
    normalized = re.sub(r"\s+", "", text).lower()
    for marker in NON_FINAL_CONFIRMATION_MARKERS:
        if marker.lower() in normalized:
            return f"包含非正式标记“{marker}”"
    match = NON_FINAL_CONFIRMATION_RE.search(normalized)
    if match:
        return f"仍需确认或补充（{match.group(0)}）"
    return None


def is_formal_confirmation_value(value: Any) -> bool:
    return formal_confirmation_issue(value) is None


def formal_required_confirmation_gaps(values: dict[str, Any] | None) -> list[dict[str, str]]:
    normalized = values if isinstance(values, dict) else {}
    return _missing_required_confirmations({str(key): str(value) for key, value in normalized.items()})


def apply_confirmed_values_to_text(text: str, values: dict[str, str]) -> tuple[str, int]:
    result = str(text or "")
    replacements = 0
    aliases = _field_aliases()
    for key, value in values.items():
        if not value:
            continue
        for token in (f"{{{{{key}}}}}", f"${{{key}}}", f"【{key}】"):
            count = result.count(token)
            if count:
                result = result.replace(token, value)
                replacements += count
        for alias in aliases.get(key, []):
            pattern = re.compile(rf"({re.escape(alias)}\s*[：:]\s*){PLACEHOLDER_RE.pattern}")
            result, count = pattern.subn(lambda match: f"{match.group(1)}{value}", result)
            replacements += count

    def replace_placeholder(match: re.Match[str]) -> str:
        nonlocal replacements
        description = match.group(1).strip()
        matched_keys = [
            key for key, names in aliases.items()
            if values.get(key) and any(name in description for name in names)
        ]
        if len(matched_keys) != 1:
            return match.group(0)
        replacements += 1
        return values[matched_keys[0]]

    result = PLACEHOLDER_RE.sub(replace_placeholder, result)
    return result, replacements


def _normalize_confirmed_values(values: dict[str, Any]) -> dict[str, str]:
    if not isinstance(values, dict):
        raise ValueError("confirmedValues 必须是对象")
    specs = {spec.key: spec for spec in PREFILL_FIELD_SPECS}
    unknown = sorted(set(values) - set(specs))
    if unknown:
        raise ValueError(f"包含未定义的投标字段: {', '.join(unknown)}")
    normalized: dict[str, str] = {}
    for key, raw in values.items():
        if isinstance(raw, list):
            value = "；".join(str(item).strip() for item in raw if str(item).strip())
        else:
            value = str(raw or "").strip()
        if len(value) > 10000:
            raise ValueError(f"{specs[key].label}超过长度限制")
        if value:
            normalized[key] = value
    for key, raw in build_taichang_prefill_values().items():
        if key in specs and not normalized.get(key):
            if isinstance(raw, list):
                value = "；".join(str(item).strip() for item in raw if str(item).strip())
            else:
                value = str(raw or "").strip()
            if value:
                normalized[key] = value
    bidder_name = normalized.get("bidder_name")
    if bidder_name and bidder_name != DOCX_BIDDER_FULL_NAME:
        raise ValueError(f"当前 MVP 投标主体必须为{DOCX_BIDDER_FULL_NAME}")
    normalized["bidder_name"] = DOCX_BIDDER_FULL_NAME
    return normalized


def _project_meta(interpretation: dict[str, Any]) -> dict[str, Any]:
    analysis = interpretation.get("analysis") if isinstance(interpretation.get("analysis"), dict) else {}
    meta = analysis.get("project_meta") if isinstance(analysis.get("project_meta"), dict) else {}
    return dict(meta)


def _collect_unresolved_placeholders(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for section in sections:
        for match in PLACEHOLDER_RE.finditer(str(section.get("content") or "")):
            unresolved.append({
                "section_id": section.get("id"),
                "section_title": section.get("title"),
                "placeholder": match.group(0),
            })
    return unresolved


def _missing_required_confirmations(values: dict[str, str]) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    for spec in PREFILL_FIELD_SPECS:
        if spec.required_level != "formal_required":
            continue
        issue = formal_confirmation_issue(values.get(spec.key))
        if issue:
            missing.append({"key": spec.key, "label": spec.label, "reason": issue})
    return missing


def _build_prefill_export_gate(
    sections: list[dict[str, Any]],
    values: dict[str, str],
    section_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    unresolved = _collect_unresolved_placeholders(sections)
    missing_required = _missing_required_confirmations(values)
    missing_by_key = {item["key"] for item in missing_required}
    section_summaries: list[dict[str, Any]] = []
    for candidate in section_candidates:
        candidate_fields = candidate.get("fields") if isinstance(candidate.get("fields"), list) else []
        confirmed_fields = [
            field for field in candidate_fields
            if is_formal_confirmation_value(values.get(str(field.get("key") or "")))
        ]
        missing_fields = [
            {
                "key": field.get("key"),
                "label": field.get("label"),
                "status": field.get("status"),
            }
            for field in candidate_fields
            if field.get("key") in missing_by_key
        ]
        section_summaries.append({
            "sectionId": candidate.get("sectionId"),
            "sectionTitle": candidate.get("sectionTitle"),
            "fieldCount": candidate.get("fieldCount") or len(candidate_fields),
            "confirmedFieldCount": len(confirmed_fields),
            "missingFormalRequiredCount": len(missing_fields),
            "missingFormalRequiredFields": missing_fields,
            "boundaryWarnings": candidate.get("boundaryWarnings") or [],
        })
    return {
        "ready": bool(sections) and not unresolved and not missing_required,
        "sectionCount": len(section_summaries),
        "confirmedSectionCount": sum(1 for item in section_summaries if item["confirmedFieldCount"] > 0),
        "unresolvedPlaceholderCount": len(unresolved),
        "unresolvedPlaceholders": unresolved[:100],
        "missingFormalRequiredFields": missing_required,
        "section_application_summary": section_summaries,
    }


def _candidate_value(key: str, interpretation: dict[str, Any], assets: list[dict[str, Any]]) -> tuple[Any, dict[str, Any], float]:
    taichang_values = build_taichang_prefill_values()
    if key in taichang_values:
        return taichang_values[key], _evidence("taichang_verified_fact_pack"), 0.94

    project = interpretation.get("project") or {}
    analysis = interpretation.get("analysis") or {}
    project_meta = analysis.get("project_meta") if isinstance(analysis.get("project_meta"), dict) else {}
    cover_fields = project_meta.get("cover_fields") if isinstance(project_meta.get("cover_fields"), dict) else {}
    ai_project = ((project_meta.get("ai_report") or {}).get("project_brief") or {}) if isinstance(project_meta.get("ai_report"), dict) else {}
    bid_outline = project_meta.get("bid_outline") if isinstance(project_meta.get("bid_outline"), dict) else {}

    direct_map = {
        "project_name": [project.get("project_name"), cover_fields.get("project_name"), ai_project.get("project_name"), bid_outline.get("project_name")],
        "tender_no": [project.get("project_no"), cover_fields.get("tender_no"), cover_fields.get("project_no"), ai_project.get("tender_no"), bid_outline.get("tender_no")],
        "tender_unit": [project.get("tender_unit"), cover_fields.get("tender_unit"), cover_fields.get("tenderer")],
        "agency": [project.get("agency"), cover_fields.get("agency")],
        "bidder_name": [DOCX_BIDDER_FULL_NAME],
    }
    if key in direct_map:
        value = _first_value(direct_map[key], "project_or_tender_extract")
        if value[0]:
            return value
        if key == "tender_unit":
            project_text = "\n".join(str(item or "") for item in [
                project.get("project_name"),
                project.get("project_no"),
                cover_fields.get("project_name"),
                cover_fields.get("tender_no"),
                cover_fields.get("project_no"),
            ])
            if "国网辽宁" in project_text or "辽宁电力" in project_text:
                return "国网辽宁省电力有限公司", _evidence("liaoning_tender_metadata_policy"), 0.78
        return value

    chunks = interpretation.get("documentChunks") or []
    requirements = interpretation.get("requirements") or []
    risks = interpretation.get("risks") or []
    all_text = "\n".join(
        str(item.get("content") or item.get("source_text") or "")
        for item in [*chunks, *requirements, *risks]
        if isinstance(item, dict)
    )
    structured_goods = _structured_goods_prefill_candidates(interpretation, all_text)
    structured_technical = _structured_technical_prefill_candidates(interpretation, all_text)

    if key == "package_no":
        if "package_no" in structured_goods:
            return structured_goods["package_no"]
        return _regex_value(all_text, [r"(?:包号|包件号|包件编号)[:：\s]*([A-Za-z0-9一二三四五六七八九十\-#号]+)"], "tender_text_regex")
    if key == "package_name":
        if "package_name" in structured_goods:
            return structured_goods["package_name"]
        return _regex_value(all_text, [r"(?:包名称|包件名称)[:：\s]*([^\n；;，,。]{2,40})"], "tender_text_regex")
    if key == "material_category":
        if "material_category" in structured_goods:
            return structured_goods["material_category"]
        return _keyword_value(all_text, ["CPVC电缆保护管", "MPP电缆保护管", "电缆保护管", "铁构件", "接地铁"], "tender_text_keyword")
    if key == "goods_list_summary":
        if "goods_list_summary" in structured_goods:
            return structured_goods["goods_list_summary"]
        value = _summarize_goods_list(all_text)
        return (value, _evidence("tender_goods_list_summary"), 0.58) if value else (None, {}, 0)
    if key == "delivery_place":
        return _regex_value(all_text, [r"(?:交货地点|交货地)[:：\s]*([^\n；;。]{2,50})"], "tender_text_regex")
    if key == "delivery_period":
        return _regex_value(all_text, [r"(?:交货期|交货时间|交付期)[:：\s]*([^\n；;。]{2,40})"], "tender_text_regex")
    if key == "warranty_period":
        return _regex_value(all_text, [r"(?:质保期|质量保证期)[:：\s]*([^\n；;。]{2,40})"], "tender_text_regex")
    if key == "bid_validity_days":
        return _regex_value(all_text, [r"投标有效期[^\d]{0,12}(\d{2,4})\s*天"], "tender_text_regex")
    if key == "after_sales_response_time":
        return _regex_value(all_text, [r"(?:售后响应|响应时间)[^\d\n]{0,12}(\d+\s*(?:小时|分钟|h))"], "tender_text_regex")
    if key in structured_technical:
        return structured_technical[key]

    asset_rules = {
        "qualification_assets": ["营业执照", "认证证书", "资质", "开户", "财务", "人员证书"],
        "inspection_reports": ["检验报告", "检测报告", "型式试验", "CPVC", "MPP"],
        "project_performance_cases": ["合同", "中标通知书", "成交通知书", "业绩"],
        "product_models": ["CPVC", "MPP", "电缆保护管"],
        "product_image_assets": ["生产线", "产品", "检测设备", "厂房", "仓库"],
        "unified_social_credit_code": ["营业执照", "统一社会信用代码"],
        "legal_representative": ["营业执照", "法定代表人"],
        "company_address": ["营业执照", "住所", "地址"],
    }
    if key in asset_rules:
        matched = _match_assets(assets, asset_rules[key], limit=8)
        if key in {"unified_social_credit_code", "legal_representative", "company_address"}:
            return _extract_asset_text_field(key, matched)
        if key == "product_models":
            models = _product_models_from_assets(matched)
            return (models, _asset_evidence(matched), 0.68) if models else (None, {}, 0)
        return ([ _asset_label(asset) for asset in matched ], _asset_evidence(matched), 0.72) if matched else (None, {}, 0)

    return (None, {}, 0)


def _safe_list_knowledge_assets() -> list[dict[str, Any]]:
    try:
        return list_knowledge_assets()
    except Exception:
        return []


def _safe_list_bid_sections(project_id: str) -> list[dict[str, Any]]:
    try:
        return list_bid_sections(project_id)
    except Exception:
        return []


def _first_value(values: list[Any], source_type: str) -> tuple[Any, dict[str, Any], float]:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip(), _evidence(source_type), 0.86
    return None, {}, 0


def _regex_value(text: str, patterns: list[str], source_type: str) -> tuple[Any, dict[str, Any], float]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" ：:，,。；;"), _evidence(source_type, snippet=match.group(0)[:160]), 0.62
    return None, {}, 0


def _keyword_value(text: str, keywords: list[str], source_type: str) -> tuple[Any, dict[str, Any], float]:
    found = [keyword for keyword in keywords if keyword in text]
    return ("、".join(dict.fromkeys(found)), _evidence(source_type), 0.58) if found else (None, {}, 0)


def _summarize_goods_list(text: str) -> str | None:
    product_terms = [term for term in ["CPVC电缆保护管", "MPP电缆保护管", "电缆保护管"] if term in text]
    quantity_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:米|m|根|套)", text, flags=re.IGNORECASE)
    if not product_terms and not quantity_match:
        return None
    parts = []
    if product_terms:
        parts.append("物料：" + "、".join(dict.fromkeys(product_terms)))
    if quantity_match:
        parts.append("疑似数量：" + quantity_match.group(0))
    return "；".join(parts)


def _structured_goods_prefill_candidates(
    interpretation: dict[str, Any],
    all_text: str,
) -> dict[str, tuple[Any, dict[str, Any], float]]:
    rows = _load_liaoning_goods_rows()
    if not rows:
        return {}

    project = interpretation.get("project") if isinstance(interpretation.get("project"), dict) else {}
    analysis = interpretation.get("analysis") if isinstance(interpretation.get("analysis"), dict) else {}
    project_meta = analysis.get("project_meta") if isinstance(analysis.get("project_meta"), dict) else {}
    cover_fields = project_meta.get("cover_fields") if isinstance(project_meta.get("cover_fields"), dict) else {}
    context_text = "\n".join(str(item or "") for item in [
        all_text,
        project.get("project_no"),
        project.get("project_name"),
        cover_fields.get("project_no"),
        cover_fields.get("tender_no"),
        cover_fields.get("package_no"),
        cover_fields.get("package_name"),
        cover_fields.get("material_category"),
    ])

    filtered = _filter_goods_rows(rows, context_text)
    summary = _summarize_structured_goods_rows(filtered or rows)
    if not summary:
        return {}

    evidence = _structured_goods_evidence(summary)
    candidates: dict[str, tuple[Any, dict[str, Any], float]] = {
        "goods_list_summary": (summary["summary_text"], evidence, 0.86),
    }

    package_from_context = _extract_package_from_context(context_text)
    if package_from_context:
        candidates["package_no"] = (package_from_context, evidence, 0.82)
    elif summary["packages"]:
        candidates["package_no"] = (f"候选包号：{'、'.join(summary['packages'])}（需确认目标包）", evidence, 0.78)

    material_categories = [f"电缆保护管{family}" for family in summary["material_families"] if family]
    if material_categories:
        candidates["material_category"] = ("、".join(material_categories), evidence, 0.84)
        if len(material_categories) == 1:
            candidates["package_name"] = (material_categories[0], evidence, 0.8)
        else:
            candidates["package_name"] = (f"{'、'.join(material_categories)}（需按目标包确认）", evidence, 0.76)

    return candidates


def _load_liaoning_goods_rows() -> list[dict[str, Any]]:
    return _load_json_rows(LIAONING_GOODS_ROWS_PATH)


def _load_liaoning_technical_parameter_rows() -> list[dict[str, Any]]:
    return _load_json_rows(LIAONING_TECHNICAL_PARAMETER_ROWS_PATH)


def _load_liaoning_technical_deviation_rows() -> list[dict[str, Any]]:
    return _load_json_rows(LIAONING_TECHNICAL_DEVIATION_ROWS_PATH)


def _load_taichang_product_parameter_rows() -> list[dict[str, Any]]:
    return _load_json_rows(TAICHANG_PRODUCT_PARAMETER_ROWS_PATH)


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _filter_goods_rows(rows: list[dict[str, Any]], context_text: str) -> list[dict[str, Any]]:
    filtered = rows
    package_code_matches = set(re.findall(r"\b\d{4}[A-Z]{2}\b", context_text, flags=re.IGNORECASE))
    if package_code_matches:
        filtered = [
            row for row in filtered
            if str(row.get("_package_code") or "").upper() in {item.upper() for item in package_code_matches}
            or any(str(row.get("分标编号") or "").upper().startswith(item.upper()) for item in package_code_matches)
        ] or filtered

    package_no = _extract_package_from_context(context_text)
    if package_no:
        filtered = [row for row in filtered if str(row.get("包名称") or "").strip() == package_no] or filtered

    material_matches = [family for family in ("CPVC", "MPP") if family in context_text.upper()]
    if len(material_matches) == 1:
        family = material_matches[0]
        filtered = [row for row in filtered if str(row.get("_material_family") or "").upper() == family] or filtered

    return filtered


def _extract_package_from_context(text: str) -> str | None:
    match = re.search(r"(?:包号|包件号|包名称|包件名称|包/包名称)?\s*[:：]?\s*(包\s*[0-9一二三四五六七八九十]+)", text)
    if not match:
        return None
    return re.sub(r"\s+", "", match.group(1))


def _summarize_structured_goods_rows(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    packages = sorted({str(row.get("包名称") or "").strip() for row in rows if str(row.get("包名称") or "").strip()})
    families = sorted({str(row.get("_material_family") or "").strip() for row in rows if str(row.get("_material_family") or "").strip()})
    specs = sorted({str(row.get("_spec") or "").strip() for row in rows if str(row.get("_spec") or "").strip()}, key=_spec_sort_key)
    places = sorted({str(row.get("交货地点") or "").strip() for row in rows if str(row.get("交货地点") or "").strip()})
    spec_codes = sorted({str(row.get("技术规范编码") or "").strip() for row in rows if str(row.get("技术规范编码") or "").strip()})
    package_totals: dict[str, Decimal] = {}
    for row in rows:
        package = str(row.get("包名称") or "未标包").strip() or "未标包"
        try:
            quantity = Decimal(str(row.get("数量") or "0").replace(",", ""))
        except (InvalidOperation, ValueError):
            quantity = Decimal(0)
        package_totals[package] = package_totals.get(package, Decimal(0)) + quantity

    parts = [
        f"辽宁 2025-03 2225AC 货物清单结构化行级记录：共 {len(rows)} 行需求",
    ]
    if packages:
        parts.append("包号：" + "、".join(packages[:8]))
    if families:
        parts.append("物料：" + "、".join(f"电缆保护管{family}" for family in families))
    if specs:
        parts.append("规格：" + "、".join(specs[:10]))
    if package_totals:
        totals = "、".join(f"{package} {_format_decimal(quantity)}米" for package, quantity in sorted(package_totals.items())[:8])
        parts.append("数量汇总：" + totals)
    if places:
        parts.append("交货地点示例：" + "、".join(places[:6]))
    if spec_codes:
        parts.append(f"技术规范编码 {len(spec_codes)} 个")

    return {
        "row_count": len(rows),
        "packages": packages,
        "material_families": families,
        "specs": specs,
        "delivery_places": places,
        "technical_spec_code_count": len(spec_codes),
        "summary_text": "；".join(parts),
        "source_file": "goods_tables/goods_rows.json",
    }


def _structured_goods_evidence(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceType": "structured_tender_goods_rows",
        "sourceLabel": "辽宁招标货物清单结构化行级记录",
        "sourceDomain": "tender_requirement",
        "factSourceAllowedForEnterprise": False,
        "rowCount": summary.get("row_count"),
        "packages": summary.get("packages", [])[:8],
        "materialFamilies": summary.get("material_families", [])[:8],
        "technicalSpecCodeCount": summary.get("technical_spec_code_count", 0),
        "sourceFile": summary.get("source_file"),
    }


def _spec_sort_key(value: str) -> tuple[int, str]:
    match = re.search(r"\d+", value)
    return (int(match.group(0)) if match else 999999, value)


def _format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f").rstrip("0").rstrip(".") if "." in format(normalized, "f") else format(normalized, "f")


def _structured_technical_prefill_candidates(
    interpretation: dict[str, Any],
    all_text: str,
) -> dict[str, tuple[Any, dict[str, Any], float]]:
    technical_rows = _load_liaoning_technical_parameter_rows()
    deviation_rows = _load_liaoning_technical_deviation_rows()
    product_rows = _load_taichang_product_parameter_rows()
    goods_rows = _load_liaoning_goods_rows()
    if not technical_rows and not deviation_rows and not product_rows:
        return {}

    context_text = _prefill_context_text(interpretation, all_text)
    filtered_technical = _filter_parameter_rows(technical_rows, context_text)
    filtered_deviations = _filter_parameter_rows(deviation_rows, context_text)
    filtered_goods = _filter_goods_rows(goods_rows, context_text)
    technical_summary = _summarize_technical_parameter_rows(filtered_technical or technical_rows)
    deviation_summary = _summarize_technical_deviation_rows(filtered_deviations or deviation_rows)
    product_summary = _summarize_taichang_parameter_match(product_rows, filtered_technical or technical_rows, filtered_goods or goods_rows)

    candidates: dict[str, tuple[Any, dict[str, Any], float]] = {}
    if technical_summary:
        candidates["technical_parameter_summary"] = (
            technical_summary["summary_text"],
            _structured_technical_evidence(
                "structured_technical_parameter_rows",
                "辽宁招标技术参数表结构化行级记录",
                technical_summary,
                fact_source_allowed=False,
            ),
            0.85,
        )
    if deviation_summary:
        candidates["technical_deviation_candidates"] = (
            deviation_summary["summary_text"],
            _structured_technical_evidence(
                "structured_technical_deviation_rows",
                "技术偏差辅助结构化候选",
                deviation_summary,
                fact_source_allowed=False,
            ),
            0.83,
        )
    if product_summary:
        candidates["taichang_parameter_match_summary"] = (
            product_summary["summary_text"],
            _structured_technical_evidence(
                "structured_taichang_parameter_match",
                "泰昌产品结构化参数与辽宁需求 QA 比对",
                product_summary,
                fact_source_allowed=True,
            ),
            0.82,
        )
    return candidates


def _prefill_context_text(interpretation: dict[str, Any], all_text: str) -> str:
    project = interpretation.get("project") if isinstance(interpretation.get("project"), dict) else {}
    analysis = interpretation.get("analysis") if isinstance(interpretation.get("analysis"), dict) else {}
    project_meta = analysis.get("project_meta") if isinstance(analysis.get("project_meta"), dict) else {}
    cover_fields = project_meta.get("cover_fields") if isinstance(project_meta.get("cover_fields"), dict) else {}
    return "\n".join(str(item or "") for item in [
        all_text,
        project.get("project_no"),
        project.get("project_name"),
        cover_fields.get("project_no"),
        cover_fields.get("tender_no"),
        cover_fields.get("package_no"),
        cover_fields.get("package_name"),
        cover_fields.get("material_category"),
    ])


def _filter_parameter_rows(rows: list[dict[str, Any]], context_text: str) -> list[dict[str, Any]]:
    filtered = rows
    package_code_matches = set(re.findall(r"\b\d{4}[A-Z]{2}\b", context_text, flags=re.IGNORECASE))
    if package_code_matches:
        filtered = [
            row for row in filtered
            if str(row.get("package_code") or "").upper() in {item.upper() for item in package_code_matches}
        ] or filtered

    package_no = _extract_package_from_context(context_text)
    if package_no:
        filtered = [row for row in filtered if str(row.get("package_no") or "").strip() == package_no] or filtered

    material_matches = [family for family in ("CPVC", "MPP") if family in context_text.upper()]
    if len(material_matches) == 1:
        family = material_matches[0]
        filtered = [row for row in filtered if family in str(row.get("material_category") or "").upper()] or filtered

    return filtered


def _summarize_technical_parameter_rows(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    packages = _sorted_nonempty(row.get("package_no") for row in rows)
    categories = _sorted_nonempty(row.get("material_category") for row in rows)
    table_types = Counter(str(row.get("table_type") or "unknown") for row in rows)
    diameters = sorted(
        {value for row in rows if (value := _normalize_diameter_value(row.get("nominal_inner_diameter")))},
        key=_spec_sort_key,
    )
    response_missing = sum(
        1 for row in rows
        if not str(row.get("bidder_response_value") or row.get("bidder_guaranteed_value") or "").strip()
        and _row_has_requirement(row)
    )
    examples = _parameter_examples(rows, limit=4)
    source_count = len({str(row.get("source_file") or "") for row in rows if row.get("source_file")})
    parts = [f"辽宁 2025-03 2225AC 技术参数表结构化记录：共 {len(rows)} 行"]
    if packages:
        parts.append("包号：" + "、".join(packages[:8]))
    if categories:
        parts.append("物料：" + "、".join(categories[:8]))
    if diameters:
        parts.append("公称内径：" + "、".join(diameters[:10]))
    if table_types:
        parts.append("表类型：" + "、".join(f"{name} {count}行" for name, count in table_types.most_common(5)))
    if response_missing:
        parts.append(f"待补投标响应/保证值 {response_missing} 行")
    if examples:
        parts.append("示例：" + "；".join(examples))
    parts.append("边界：辽宁技术参数是本次招标要求，不能自动作为泰昌企业事实或覆盖结论。")
    return {
        "row_count": len(rows),
        "packages": packages,
        "material_categories": categories,
        "table_types": dict(table_types),
        "nominal_inner_diameters": diameters,
        "response_missing_count": response_missing,
        "source_file_count": source_count,
        "summary_text": "；".join(parts),
        "source_file": "staging/technical_parameters/technical_parameter_rows.json",
    }


def _summarize_technical_deviation_rows(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    packages = _sorted_nonempty(row.get("package_no") for row in rows)
    categories = _sorted_nonempty(row.get("material_category") for row in rows)
    status_counts = Counter(str(row.get("deviation_status") or "unknown") for row in rows)
    risk_counts = Counter(str(row.get("risk_level") or "unknown") for row in rows)
    actionable = [
        row for row in rows
        if str(row.get("deviation_status") or "") in {"pending_response", "manual_review", "negative_deviation"}
        or str(row.get("risk_level") or "") in {"high", "medium"}
    ]
    examples = _deviation_examples(actionable or rows, limit=4)
    parts = [f"技术偏差辅助候选：共 {len(rows)} 行"]
    if packages:
        parts.append("包号：" + "、".join(packages[:8]))
    if categories:
        parts.append("物料：" + "、".join(categories[:8]))
    if status_counts:
        parts.append("状态：" + "、".join(f"{name} {count}行" for name, count in status_counts.most_common()))
    if risk_counts:
        parts.append("风险：" + "、".join(f"{name} {count}行" for name, count in risk_counts.most_common(4)))
    if examples:
        parts.append("待处理示例：" + "；".join(examples))
    parts.append("边界：偏差状态是辅助候选，不自动写入无偏差或正/负偏差结论，需客户确认响应值。")
    return {
        "row_count": len(rows),
        "packages": packages,
        "material_categories": categories,
        "status_counts": dict(status_counts),
        "risk_counts": dict(risk_counts),
        "actionable_count": len(actionable),
        "summary_text": "；".join(parts),
        "source_file": "staging/technical_parameters/technical_deviations/technical_deviation_rows.json",
    }


def _summarize_taichang_parameter_match(
    product_rows: list[dict[str, Any]],
    technical_rows: list[dict[str, Any]],
    goods_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not product_rows:
        return None
    families = _sorted_nonempty(row.get("product_family") for row in product_rows)
    specs = _sorted_nonempty(row.get("specification_model") for row in product_rows)
    report_numbers = _sorted_nonempty(row.get("report_no") for row in product_rows)
    product_diameters = sorted(
        {value for row in product_rows if (value := _normalize_diameter_value(row.get("nominal_inner_diameter")))},
        key=_spec_sort_key,
    )
    goods_diameters = sorted(
        {value for row in goods_rows if (value := _normalize_diameter_value(row.get("_spec") or row.get("物资描述") or row.get("物资名称")))},
        key=_spec_sort_key,
    )
    tender_diameters = goods_diameters or sorted(
        {value for row in technical_rows if (value := _normalize_diameter_value(row.get("nominal_inner_diameter")))},
        key=_spec_sort_key,
    )
    matched_diameters = [value for value in product_diameters if value in set(tender_diameters)]
    unmatched_tender = [value for value in tender_diameters if value not in set(product_diameters)]
    key_examples = _taichang_parameter_examples(product_rows)
    parts = [f"泰昌结构化检验报告参数：共 {len(product_rows)} 行，报告 {len(report_numbers)} 份"]
    if families:
        parts.append("产品：" + "、".join(families[:6]))
    if specs:
        parts.append("规格型号：" + "、".join(specs[:4]))
    if report_numbers:
        parts.append("报告编号：" + "、".join(report_numbers[:6]))
    if product_diameters:
        parts.append("泰昌已结构化公称内径：" + "、".join(product_diameters[:10]))
    if tender_diameters:
        if matched_diameters:
            parts.append("与辽宁需求内径交集：" + "、".join(matched_diameters[:10]))
        if unmatched_tender:
            basis = "货物清单规格" if goods_diameters else "技术参数表规格"
            parts.append(f"辽宁{basis}中未由现有泰昌结构化报告直接覆盖的内径：" + "、".join(unmatched_tender[:10]))
    if key_examples:
        parts.append("可引用实测示例：" + "；".join(key_examples))
    parts.append("边界：泰昌参数来自企业检验报告；辽宁需求仅作 QA/异常校验，不构成覆盖辽宁全部规格的结论。")
    return {
        "row_count": len(product_rows),
        "product_families": families,
        "specification_models": specs,
        "report_numbers": report_numbers,
        "product_diameters": product_diameters,
        "tender_diameters": tender_diameters,
        "matched_diameters": matched_diameters,
        "unmatched_tender_diameters": unmatched_tender,
        "summary_text": "；".join(parts),
        "source_file": "staging/taichang_product_parameters/taichang_product_parameter_rows.json",
    }


def _structured_technical_evidence(
    source_type: str,
    label: str,
    summary: dict[str, Any],
    *,
    fact_source_allowed: bool,
) -> dict[str, Any]:
    return {
        "sourceType": source_type,
        "sourceLabel": label,
        "sourceDomain": "enterprise_fact" if fact_source_allowed else "tender_requirement",
        "factSourceAllowedForEnterprise": fact_source_allowed,
        "rowCount": summary.get("row_count"),
        "packages": summary.get("packages", [])[:8],
        "materialCategories": summary.get("material_categories", [])[:8],
        "statusCounts": summary.get("status_counts", {}),
        "responseMissingCount": summary.get("response_missing_count"),
        "unmatchedTenderDiameters": summary.get("unmatched_tender_diameters", [])[:10],
        "sourceFile": summary.get("source_file"),
    }


def _row_has_requirement(row: dict[str, Any]) -> bool:
    if str(row.get("standard_value") or row.get("project_required_value") or "").strip():
        return True
    row_data = row.get("row_data") if isinstance(row.get("row_data"), dict) else {}
    return any(str(value or "").strip() for value in row_data.values())


def _normalize_diameter_value(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"\d{2,4}", text)
    if not match:
        return None
    return match.group(0)


def _sorted_nonempty(values: Any) -> list[str]:
    return sorted({str(value or "").strip() for value in values if str(value or "").strip()})


def _parameter_examples(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    examples: list[str] = []
    for row in rows:
        name = str(row.get("parameter_name") or "").strip()
        required = str(row.get("project_required_value") or row.get("standard_value") or "").strip()
        if not required:
            row_data = row.get("row_data") if isinstance(row.get("row_data"), dict) else {}
            required = "、".join(f"{key}={value}" for key, value in list(row_data.items())[:3] if str(value).strip())
        if name and required:
            examples.append(f"{name}：{required[:80]}")
        if len(examples) >= limit:
            break
    return examples


def _deviation_examples(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    examples: list[str] = []
    for row in rows:
        name = str(row.get("parameter_name") or "").strip()
        status = str(row.get("deviation_status") or "").strip()
        action = str(row.get("suggested_action") or "").strip()
        if name and status:
            examples.append(f"{name}：{status}，{action[:60]}")
        if len(examples) >= limit:
            break
    return examples


def _taichang_parameter_examples(rows: list[dict[str, Any]]) -> list[str]:
    wanted = ("环刚度", "平均内径", "壁厚")
    examples: list[str] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        name = str(row.get("parameter_name") or "").strip()
        if not any(term in name for term in wanted):
            continue
        key = (str(row.get("product_family") or ""), name)
        if key in seen:
            continue
        seen.add(key)
        result = str(row.get("inspection_result") or "").strip()
        report = str(row.get("report_no") or "").strip()
        if name and result:
            examples.append(f"{row.get('product_family') or '-'} {name}={result}（报告{report}）")
        if len(examples) >= 4:
            break
    return examples


def _match_assets(assets: list[dict[str, Any]], keywords: list[str], *, limit: int) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for asset in assets:
        text = _asset_search_text(asset)
        if any(keyword in text for keyword in keywords):
            matched.append(asset)
        if len(matched) >= limit:
            break
    return matched


def _asset_search_text(asset: dict[str, Any]) -> str:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    specs = asset.get("specs") if isinstance(asset.get("specs"), dict) else {}
    tags = asset.get("tags") if isinstance(asset.get("tags"), list) else []
    return " ".join(str(part or "") for part in [
        asset.get("title"),
        asset.get("description"),
        asset.get("category"),
        asset.get("asset_type"),
        " ".join(map(str, tags)),
        " ".join(f"{k}:{v}" for k, v in metadata.items()),
        " ".join(f"{k}:{v}" for k, v in specs.items()),
    ])


def _asset_label(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": asset.get("id"),
        "title": asset.get("title") or asset.get("file_name") or "未命名资产",
        "category": asset.get("category"),
        "assetType": asset.get("asset_type"),
    }


def _asset_evidence(assets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sourceType": "enterprise_library",
        "sourceLabel": "企业知识库/资信库/产品库资产",
        "assetCount": len(assets),
        "assets": [_asset_label(asset) for asset in assets[:5]],
    }


def _extract_asset_text_field(key: str, assets: list[dict[str, Any]]) -> tuple[Any, dict[str, Any], float]:
    if not assets:
        return None, {}, 0
    text = "\n".join(_asset_search_text(asset) for asset in assets)
    patterns = {
        "unified_social_credit_code": [r"(?:统一社会信用代码|社会信用代码)[:：\s]*([0-9A-Z]{15,20})"],
        "legal_representative": [r"(?:法定代表人|法人)[:：\s]*([\u4e00-\u9fa5]{2,8})"],
        "company_address": [r"(?:住所|地址)[:：\s]*([^\n；;。]{4,80})"],
    }
    value, evidence, confidence = _regex_value(text, patterns.get(key, []), "enterprise_library")
    if value:
        evidence = {**evidence, **_asset_evidence(assets)}
    return value, evidence, confidence


def _product_models_from_assets(assets: list[dict[str, Any]]) -> list[str]:
    models: list[str] = []
    for asset in assets:
        text = _asset_search_text(asset)
        for model in re.findall(r"\b(?:CPVC|MPP)[A-Za-z0-9\-φΦ×*./ ]{0,24}", text, flags=re.IGNORECASE):
            clean = re.sub(r"\s+", " ", model).strip(" -_，,。；;")
            if clean and clean.upper() not in {item.upper() for item in models}:
                models.append(clean)
    return models[:8]


def _evidence(source_type: str, *, snippet: str | None = None) -> dict[str, Any]:
    labels = {
        "project_or_tender_extract": "项目/招标文件结构化字段",
        "tender_text_regex": "招标文件文本规则识别",
        "tender_text_keyword": "招标文件关键词识别",
        "tender_goods_list_summary": "货物清单摘要规则识别",
        "enterprise_library": "企业资料资产识别",
        "taichang_verified_fact_pack": "泰昌核验事实包",
    }
    evidence: dict[str, Any] = {
        "sourceType": source_type,
        "sourceLabel": labels.get(source_type, source_type),
    }
    if snippet:
        evidence["snippet"] = snippet
    return evidence


def _group_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for field in fields:
        groups.setdefault(field["group"], []).append(field)
    return [{"name": name, "fields": values} for name, values in groups.items()]


def _build_section_candidates(fields: list[dict[str, Any]], sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for field in fields:
        for target in _field_section_targets(field):
            section = _match_section(target, sections)
            key = str(section.get("id") or section.get("title") or target)
            if key not in targets:
                targets[key] = {
                    "sectionId": section.get("id"),
                    "sectionTitle": section.get("title") or target,
                    "orderIndex": section.get("order_index"),
                    "virtual": not bool(section.get("id")),
                    "fields": [],
                }
            targets[key]["fields"].append(_section_candidate_field(field))

    candidates = []
    for item in targets.values():
        candidate_fields = _dedupe_section_candidate_fields(item["fields"])
        status_counts = Counter(str(field.get("status")) for field in candidate_fields)
        source_domains = sorted({
            str(field.get("sourceDomain") or "")
            for field in candidate_fields
            if str(field.get("sourceDomain") or "").strip()
        })
        gap_fields = [
            field for field in candidate_fields
            if field.get("status") in {"customer_required", "manual_confirm"} or field.get("riskLevel") == "critical"
        ]
        candidates.append({
            **item,
            "fields": candidate_fields,
            "fieldCount": len(candidate_fields),
            "gapCount": len(gap_fields),
            "statusCounts": dict(status_counts),
            "sourceDomains": source_domains,
            "boundaryWarnings": _section_boundary_warnings(candidate_fields),
        })
    candidates.sort(key=lambda item: (
        item.get("orderIndex") is None,
        item.get("orderIndex") if item.get("orderIndex") is not None else 999999,
        str(item.get("sectionTitle") or ""),
    ))
    return candidates


def _field_section_targets(field: dict[str, Any]) -> list[str]:
    key = str(field.get("key") or "")
    maps_to = [str(item) for item in field.get("mapsTo") or [] if str(item).strip()]
    explicit: dict[str, list[str]] = {
        "package_no": ["封面", "货物清单", "技术响应"],
        "package_name": ["封面", "货物清单", "技术响应"],
        "material_category": ["货物清单", "技术响应"],
        "goods_list_summary": ["报价文件及货物清单", "货物清单", "技术响应"],
        "technical_parameter_summary": ["技术特性参数表", "技术响应文件", "技术响应"],
        "technical_deviation_candidates": ["技术偏差表", "技术响应文件", "技术响应"],
        "taichang_parameter_match_summary": ["产品制造与质量控制", "技术响应文件", "检验报告", "技术响应"],
        "inspection_reports": ["检验报告", "附件清单", "技术响应"],
        "product_models": ["技术特性参数表", "产品制造与质量控制", "技术响应"],
        "product_image_assets": ["产品制造与质量控制", "供货组织与交付保障", "技术响应"],
        "qualification_assets": ["资格证明文件", "附件清单"],
        "project_performance_cases": ["业绩文件", "技术评分支撑材料"],
    }
    return list(dict.fromkeys([*(explicit.get(key) or []), *maps_to]))


def _match_section(target: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
    clean_target = _normalize_section_text(target)
    if not sections:
        return {"title": target}
    scored: list[tuple[int, dict[str, Any]]] = []
    for section in sections:
        title = str(section.get("title") or "")
        clean_title = _normalize_section_text(title)
        score = 0
        if clean_target and clean_target in clean_title:
            score += 10 + len(clean_target)
        if clean_title and clean_title in clean_target:
            score += 6 + len(clean_title)
        for keyword in _section_match_keywords(target):
            if keyword and keyword in clean_title:
                score += 5
        if score:
            scored.append((score, section))
    if not scored:
        return {"title": target}
    scored.sort(key=lambda item: (
        item[0],
        -int(item[1].get("level") or 99),
        -int(item[1].get("order_index") or 999999),
    ), reverse=True)
    return scored[0][1]


def _normalize_section_text(value: str) -> str:
    return re.sub(r"[\s　：:、.．·\-—_（）()【】\\[\\]]+", "", str(value or ""))


def _section_match_keywords(target: str) -> list[str]:
    target_text = str(target or "")
    keywords = []
    for keyword in ["货物清单", "技术响应", "技术特性", "技术参数", "技术偏差", "报价", "附件", "检验报告", "资格", "业绩", "产品制造", "质量控制"]:
        if keyword in target_text:
            keywords.append(keyword)
    return keywords


def _section_candidate_field(field: dict[str, Any]) -> dict[str, Any]:
    evidence = field.get("evidence") if isinstance(field.get("evidence"), dict) else {}
    return {
        "key": field.get("key"),
        "label": field.get("label"),
        "group": field.get("group"),
        "status": field.get("status"),
        "statusLabel": field.get("statusLabel"),
        "requiredLevel": field.get("requiredLevel"),
        "riskLevel": field.get("riskLevel"),
        "valuePreview": _preview_value(field.get("value")),
        "sourceLabel": evidence.get("sourceLabel"),
        "sourceType": evidence.get("sourceType"),
        "sourceDomain": evidence.get("sourceDomain"),
        "factSourceAllowedForEnterprise": evidence.get("factSourceAllowedForEnterprise"),
    }


def _dedupe_section_candidate_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field in fields:
        key = str(field.get("key") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(field)
    return deduped


def _preview_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        text = "；".join(
            str(item.get("title") if isinstance(item, dict) else item)
            for item in value
            if str(item.get("title") if isinstance(item, dict) else item).strip()
        )
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:180] + ("..." if len(text) > 180 else "")


def _section_boundary_warnings(fields: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    if any(field.get("sourceDomain") == "tender_requirement" for field in fields):
        warnings.append("含招标要求候选，需客户确认后才能写入本次投标响应。")
    if any(field.get("factSourceAllowedForEnterprise") is False for field in fields):
        warnings.append("存在不可作为泰昌企业事实的来源，禁止当作企业资质或能力证明。")
    if any(field.get("key") == "technical_deviation_candidates" for field in fields):
        warnings.append("偏差表候选不自动生成无偏差结论。")
    return warnings


def _status_label(status: Status) -> str:
    return {
        "system_recognized": "系统已识别",
        "enterprise_library": "企业库带出",
        "customer_required": "客户需填写",
        "manual_confirm": "待人工确认",
    }.get(status, "待人工确认")


def _maps_to(key: str) -> list[str]:
    mapping = {
        "project_name": ["封面", "投标函", "目录", "正文页眉"],
        "tender_no": ["封面", "投标函", "授权委托书"],
        "package_no": ["封面", "货物清单", "商务响应", "技术响应"],
        "goods_list_summary": ["货物清单", "技术响应", "报价文件"],
        "total_bid_price": ["投标函", "报价文件"],
        "bid_bond_amount": ["投标保证金", "商务偏差表"],
        "authorized_representative": ["授权委托书", "签章页"],
        "qualification_assets": ["资格文件", "附件清单"],
        "inspection_reports": ["技术响应", "附件清单"],
        "project_performance_cases": ["业绩章节", "附件清单"],
        "technical_parameter_summary": ["技术响应", "技术特性参数表", "技术偏差表"],
        "technical_deviation_candidates": ["技术偏差表", "技术响应", "附件清单"],
        "taichang_parameter_match_summary": ["技术响应", "检验报告", "产品参数"],
        "product_image_assets": ["技术响应", "企业能力展示"],
    }
    return mapping.get(key, [])


def _field_aliases() -> dict[str, list[str]]:
    return {
        "project_name": ["项目名称", "本项目名称"],
        "tender_no": ["招标编号", "项目编号"],
        "tender_unit": ["招标人", "招标单位"],
        "agency": ["招标代理机构", "代理机构"],
        "package_no": ["包号", "包件号", "包编号", "包件编号"],
        "package_name": ["包名称", "包件名称"],
        "material_category": ["物料类别", "物资类别"],
        "goods_list_summary": ["货物清单", "供货清单"],
        "delivery_place": ["交货地点", "交货地"],
        "bidder_name": ["投标人名称", "投标人", "公司全称", "企业全称"],
        "unified_social_credit_code": ["统一社会信用代码", "社会信用代码"],
        "legal_representative": ["法定代表人", "法人"],
        "company_address": ["企业地址", "注册地址", "住所"],
        "total_bid_price": ["投标总价", "投标报价", "报价总额"],
        "total_bid_price_upper": ["投标总价大写", "大写金额"],
        "tax_rate": ["税率"],
        "bid_bond_amount": ["投标保证金金额", "保证金金额"],
        "bid_bond_form": ["投标保证金形式", "保证金形式"],
        "basic_account": ["基本账户信息", "基本账户"],
        "delivery_period": ["交货期承诺", "交货期", "供货周期"],
        "warranty_period": ["质保期承诺", "质保期", "质量保证期"],
        "bid_validity_days": ["投标有效期"],
        "after_sales_response_time": ["售后响应时间", "响应时间"],
        "authorized_representative": ["授权代表", "授权代理人", "委托代理人"],
        "authorized_representative_id": ["授权代表身份证号", "授权代理人身份证号"],
        "authorized_representative_phone": ["授权代表联系方式", "授权代理人联系方式"],
        "signature_date": ["签署日期", "投标日期", "日期"],
        "product_models": ["产品规格型号", "规格型号"],
        "technical_parameter_summary": ["技术参数表候选摘要", "技术参数表", "技术特性参数表", "项目需求值"],
        "technical_deviation_candidates": ["技术偏差表候选", "技术偏差表", "偏差表", "偏差说明"],
        "taichang_parameter_match_summary": ["泰昌参数佐证摘要", "泰昌参数", "检验报告参数", "产品参数佐证"],
    }

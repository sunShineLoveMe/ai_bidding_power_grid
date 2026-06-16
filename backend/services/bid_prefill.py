from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.db.supabase_repo import get_project_interpretation, list_knowledge_assets
from backend.export.md_to_word import DOCX_BIDDER_FULL_NAME


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
    PrefillFieldSpec("product_image_assets", "产品及生产能力图片", "企业产品", "asset_list", "recommended", "medium", "产品库图片资产带出，用户确认是否插图"),
)


def build_bid_prefill_report(project_id: str) -> dict[str, Any]:
    interpretation = get_project_interpretation(project_id)
    assets = _safe_list_knowledge_assets()
    fields = [_build_field(spec, interpretation, assets) for spec in PREFILL_FIELD_SPECS]
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
            "affectsSectionsSnapshotExport": False,
        },
        "groups": _group_fields(fields),
        "fields": fields,
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
            "本报告为旁路只读确认，不写入 bid_sections，不影响 sectionsSnapshot DOCX 导出契约。",
        ],
    }


def _build_field(spec: PrefillFieldSpec, interpretation: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, Any]:
    value, evidence, confidence = _candidate_value(spec.key, interpretation, assets)
    if spec.customer_decision and not value:
        status: Status = "customer_required"
    elif spec.key in {"package_no", "package_name", "goods_list_summary", "delivery_period", "warranty_period"} and value:
        status = "manual_confirm"
    elif spec.key in {"qualification_assets", "inspection_reports", "project_performance_cases", "product_image_assets"}:
        status = "enterprise_library" if value else "manual_confirm"
    elif value and evidence.get("sourceType") == "enterprise_library":
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
        "confidence": confidence,
        "evidence": evidence,
        "mapsTo": _maps_to(spec.key),
    }


def _candidate_value(key: str, interpretation: dict[str, Any], assets: list[dict[str, Any]]) -> tuple[Any, dict[str, Any], float]:
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
        return _first_value(direct_map[key], "project_or_tender_extract")

    chunks = interpretation.get("documentChunks") or []
    requirements = interpretation.get("requirements") or []
    risks = interpretation.get("risks") or []
    all_text = "\n".join(
        str(item.get("content") or item.get("source_text") or "")
        for item in [*chunks, *requirements, *risks]
        if isinstance(item, dict)
    )

    if key == "package_no":
        return _regex_value(all_text, [r"(?:包号|包件号|包件编号)[:：\s]*([A-Za-z0-9一二三四五六七八九十\-#号]+)"], "tender_text_regex")
    if key == "package_name":
        return _regex_value(all_text, [r"(?:包名称|包件名称)[:：\s]*([^\n；;，,。]{2,40})"], "tender_text_regex")
    if key == "material_category":
        return _keyword_value(all_text, ["CPVC电缆保护管", "MPP电缆保护管", "电缆保护管", "铁构件", "接地铁"], "tender_text_keyword")
    if key == "goods_list_summary":
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
        "product_image_assets": ["技术响应", "企业能力展示"],
    }
    return mapping.get(key, [])

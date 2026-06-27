from __future__ import annotations

import json
import re
from typing import Any


TAICHANG_SUPPORTED_PRODUCT_FAMILIES = (
    "CPVC电缆保护管",
    "MPP电缆保护管",
    "电缆保护管",
)

SUPPORTED_TERMS = (
    "CPVC",
    "MPP",
    "电缆保护管",
    "电力电缆保护管",
    "保护管",
    "导管",
)

UNSUPPORTED_TENDER_MATERIALS = (
    "架空绝缘导线",
    "绝缘导线",
    "布电线",
    "控制电缆",
    "低压电力电缆",
    "中压电力电缆",
    "高压电力电缆",
    "电力电缆",
    "钢芯铝绞线",
    "铝绞线",
)

MATERIAL_KEY_ALIASES = (
    "material_category",
    "package_name",
    "包名称",
    "包件名称",
    "物资名称",
    "物料类别",
    "分标名称",
    "项目名称",
)


def build_bid_product_compatibility_report(interpretation: dict[str, Any] | None) -> dict[str, Any]:
    text = _compatibility_source_text(interpretation or {})
    detected_supported = _matched_terms(text, SUPPORTED_TERMS)
    detected_unsupported = _matched_terms(text, UNSUPPORTED_TENDER_MATERIALS)

    if detected_unsupported and not detected_supported:
        status = "mismatch"
        blocking = True
        message = (
            "当前招标包物料疑似为"
            f"{'、'.join(detected_unsupported[:4])}，泰昌现有已核验产品资料主要覆盖"
            f"{'、'.join(TAICHANG_SUPPORTED_PRODUCT_FAMILIES[:2])}；不得直接生成无偏差技术响应。"
        )
    elif detected_supported:
        status = "matched"
        blocking = False
        message = "当前招标物料与泰昌已核验产品资料存在可比对产品族，可继续生成候选并由客户确认。"
    else:
        status = "unknown"
        blocking = False
        message = "暂未从招标资料中稳定识别物料类别，技术响应需保留人工确认口径。"

    return {
        "status": status,
        "blocking": blocking,
        "detectedTenderMaterials": detected_unsupported + [term for term in detected_supported if term not in detected_unsupported],
        "unsupportedTenderMaterials": detected_unsupported,
        "matchedSupportedTerms": detected_supported,
        "supportedProductFamilies": list(TAICHANG_SUPPORTED_PRODUCT_FAMILIES),
        "message": message,
    }


def is_product_compatibility_blocking(report: dict[str, Any] | None) -> bool:
    return bool((report or {}).get("blocking") or (report or {}).get("status") == "mismatch")


def product_compatibility_warning(report: dict[str, Any] | None) -> str:
    report = report or {}
    if not report:
        return "暂未形成产品适配性预检结果。"
    return str(report.get("message") or "当前产品适配性需要人工复核。")


def _compatibility_source_text(interpretation: dict[str, Any]) -> str:
    project = interpretation.get("project") if isinstance(interpretation.get("project"), dict) else {}
    analysis = interpretation.get("analysis") if isinstance(interpretation.get("analysis"), dict) else {}
    project_meta = analysis.get("project_meta") if isinstance(analysis.get("project_meta"), dict) else {}
    cover_fields = project_meta.get("cover_fields") if isinstance(project_meta.get("cover_fields"), dict) else {}

    focused_values: list[Any] = [
        project.get("project_name"),
        project.get("project_no"),
        analysis.get("summary"),
        project_meta.get("project_name"),
        project_meta.get("tender_no"),
    ]
    for key, value in cover_fields.items():
        key_text = str(key)
        if key_text in MATERIAL_KEY_ALIASES or any(alias in key_text for alias in MATERIAL_KEY_ALIASES):
            focused_values.append(value)

    for bucket in ("requirements", "risks", "documentChunks"):
        for item in interpretation.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            focused_values.append(item.get("title"))
            focused_values.append(item.get("content") or item.get("source_text"))

    return "\n".join(_stringify(value) for value in focused_values if _stringify(value).strip())[:12000]


def _matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    normalized = re.sub(r"\s+", "", text or "").upper()
    found: list[str] = []
    for term in terms:
        if re.sub(r"\s+", "", term).upper() in normalized:
            found.append(term)
    return list(dict.fromkeys(found))


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)

from __future__ import annotations

import json
import re
from typing import Any


DOCUMENT_EVIDENCE_TYPES = {
    "business_license",
    "certification",
    "finance",
    "inspection_report",
    "project_performance",
    "authorization",
    "personnel_certificate",
    "social_security",
    "audit_report",
    "contract",
    "bid_award_notice",
}

PHOTO_EVIDENCE_LABELS = {
    "production_capacity": "生产制造能力资料",
    "testing_capacity": "试验检测能力资料",
    "green_low_carbon": "绿色低碳资料",
    "product": "产品实物资料",
    "product_image": "产品实物资料",
    "inspection_equipment": "试验检测设备资料",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _dict_value(asset: dict[str, Any], key: str) -> str:
    for container_name in ("metadata", "specs"):
        container = asset.get(container_name)
        if isinstance(container, dict):
            value = container.get(key)
            if value not in (None, ""):
                return str(value).strip()
    value = asset.get(key)
    return str(value).strip() if value not in (None, "") else ""


def _looks_like_person_identity(value: str) -> bool:
    if re.search(r"身份证|法定代表人身份证明|授权委托|委托代理人", value):
        return True
    if "脱敏" not in value:
        return False
    non_identity_terms = (
        "证书",
        "认证",
        "营业执照",
        "检验报告",
        "检测报告",
        "审计报告",
        "生产线",
        "试验设备",
        "检测设备",
        "产品",
    )
    return not any(term in value for term in non_identity_terms)


def clean_formal_asset_title(value: Any, fallback: str = "企业资料") -> str:
    title = _text(value).strip()
    if not title:
        return fallback

    title = re.sub(r"\*\*(.*?)\*\*", r"\1", title)
    title = re.sub(r"^(?:图示|图片|资料|图\s*\d+(?:[.\-—]\d+)*)\s*[：:、.\s]*", "", title)
    title = title.replace("河北泰昌电力器材科技有限公司", "").strip()
    title = re.sub(r"^(?:河北)?泰昌(?:电力器材科技有限公司)?", "", title).strip()
    title = re.sub(r"^\d{1,3}(?:\.\d{1,3})*[、.．_\-\s]+", "", title)
    title = re.sub(r"[（(]\s*脱敏示意图\s*[）)]", "", title)
    title = re.sub(r"\b[a-f0-9]{8}-[a-f0-9-]{27,}\b", "", title, flags=re.I)
    title = re.sub(r"\b[a-f0-9]{24,}\b", "", title, flags=re.I)
    title = re.sub(r"(?:^|[-_])20\d{6,14}(?:$|[-_])", "", title)
    title = re.sub(r"(?:页面|页码|page)[_\-\s]*\d+", "", title, flags=re.I)
    title = re.sub(r"_?第\s*\d+\s*页", "", title)
    title = re.sub(r"第\s*\d+\s*页", "", title)
    title = re.sub(r"_?第\s*0+\d+\s*页", "", title)
    title = re.sub(r"内径\s*[：:]?\s*[φΦ]?\s*\d+(?:\.\d+)?", "", title)
    title = re.sub(r"(?:外径|壁厚|环刚度|管径)\s*[：:]?\s*[φΦ]?\s*\d+(?:\.\d+)?(?:\s*(?:mm|毫米|MPa|kN/m2|kN/m²))?", "", title)
    title = title.replace("原图", "")
    title = title.replace("模拟产品图片", "产品实物资料")
    title = re.sub(r"(资料){2,}$", "资料", title)
    title = re.sub(r"(证书){2,}$", "证书", title)
    title = re.sub(r"(报告){2,}$", "报告", title)
    title = re.sub(r"\bcodex[-_\w]*\b", "", title, flags=re.I)
    title = re.sub(r"\b(?:taichang|power_grid|production_capacity|green_low_carbon|business_license|certification)\b", "", title, flags=re.I)
    title = title.replace("_", "")
    title = re.sub(r"[，,。；;：:\-_\s]+$", "", title)
    title = re.sub(r"^[，,。；;：:\-_\s]+", "", title)
    title = re.sub(r"\s+", "", title)
    if not re.search(r"[\u4e00-\u9fff]", title):
        return fallback
    return title or fallback


def formalize_legacy_image_caption(text: str) -> str | None:
    value = _text(text).strip()
    if not re.match(r"^(?:图示|图片|资料|图\s*\d+(?:[.\-—]\d+)*)\s*[：:、.\s]*", value):
        return None

    raw = re.sub(r"^(?:图示|图片|资料|图\s*\d+(?:[.\-—]\d+)*)\s*[：:、.\s]*", "", value).strip()
    if _looks_like_person_identity(raw):
        return "资料：身份证明文件"

    if "生产线" in raw:
        cleaned = clean_formal_asset_title(raw, "生产制造能力资料")
    elif any(keyword in raw for keyword in ("试验设备", "检测设备", "电子天平", "万能试验机", "维卡")):
        cleaned = clean_formal_asset_title(raw, "试验检测设备资料")
    elif "营业执照" in raw:
        cleaned = "营业执照"
    elif "审计报告" in raw or "财务" in raw:
        cleaned = clean_formal_asset_title(raw, "财务审计资料")
    elif "检验报告" in raw or "检测报告" in raw or "型式试验" in raw:
        cleaned = clean_formal_asset_title(raw, "检验检测报告")
    elif "认证证书" in raw or "体系认证" in raw or "证书" in raw:
        cleaned = clean_formal_asset_title(raw, "资质证书")
    else:
        cleaned = clean_formal_asset_title(raw, "企业资料")

    if not cleaned:
        return None
    return f"资料：{cleaned}"


def formal_asset_title(asset: dict[str, Any], fallback: str = "企业资料") -> str:
    explicit = _dict_value(asset, "formal_display_title") or _dict_value(asset, "formal_title")
    if explicit:
        return clean_formal_asset_title(explicit, fallback)

    candidates = [
        _dict_value(asset, "title"),
        _dict_value(asset, "source_display_name"),
        _dict_value(asset, "category_label"),
        _dict_value(asset, "evidence_type_label"),
    ]
    for candidate in candidates:
        title = clean_formal_asset_title(candidate, "")
        if title:
            return title

    evidence_type = _dict_value(asset, "evidence_type")
    return PHOTO_EVIDENCE_LABELS.get(evidence_type, fallback)


def formal_asset_caption(asset: dict[str, Any]) -> str | None:
    explicit = _dict_value(asset, "formal_caption")
    if explicit:
        return formalize_legacy_image_caption(explicit) or f"资料：{clean_formal_asset_title(explicit)}"

    evidence_type = _dict_value(asset, "evidence_type")
    visual_type = _dict_value(asset, "asset_visual_type")
    source_type = _dict_value(asset, "source_type")
    title_blob = " ".join([
        _dict_value(asset, "title"),
        _dict_value(asset, "source_display_name"),
        _dict_value(asset, "category"),
        _dict_value(asset, "description"),
    ])

    is_full_page_document = (
        evidence_type in DOCUMENT_EVIDENCE_TYPES
        or "full_page" in visual_type
        or source_type == "customer_pdf_full_page_render"
    )
    if is_full_page_document and not any(keyword in title_blob for keyword in ("生产线", "试验设备", "检测设备", "产品实物")):
        return None

    if _looks_like_person_identity(title_blob):
        return "资料：身份证明文件"

    title = formal_asset_title(asset, PHOTO_EVIDENCE_LABELS.get(evidence_type, "企业资料"))
    if not title:
        return None
    return f"资料：{title}"


def caption_policy(asset: dict[str, Any]) -> str:
    return "suppressed_document_page_caption" if formal_asset_caption(asset) is None else "formal_material_caption"

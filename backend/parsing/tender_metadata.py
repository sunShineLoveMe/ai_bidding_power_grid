from __future__ import annotations

import re
from typing import Any


COVER_FIELD_LABELS = (
    "项目名称",
    "文件类型",
    "招标编号",
    "分标编号",
    "分标名称",
    "包号",
    "包名称",
    "招标人",
    "招标代理机构",
)

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "项目名称": ("项目名称", "招标项目名称", "采购项目名称", "工程名称"),
    "文件类型": ("文件类型", "投标文件类型"),
    "招标编号": ("招标编号", "采购编号", "项目编号"),
    "分标编号": ("分标编号", "标段编号", "标包编号"),
    "分标名称": ("分标名称", "标段名称", "标包名称"),
    "包号": ("包号", "包件号", "包编号", "包件编号"),
    "包名称": ("包名称", "包件名称"),
    "招标人": ("招标人", "采购人", "项目单位"),
    "招标代理机构": ("招标代理机构", "招标代理", "代理机构", "采购代理机构"),
}

BLANK_VALUES = {"", "无", "暂无", "待补充", "【待补充】", "/", "-", "—"}
ALL_FIELD_ALIASES = tuple(alias for aliases in FIELD_ALIASES.values() for alias in aliases)


def clean_metadata_value(value: Any, *, max_chars: int = 120) -> str:
    text = str(value or "")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"^[#：:|*、.\s]+", "", text)
    text = re.split(r"\n|\s{3,}|\s*\|\s*", text.strip())[0].strip()
    text = re.sub(r"[；;。]+$", "", text).strip()
    if text in BLANK_VALUES:
        return ""
    return text[:max_chars]


def _looks_like_field_label(value: str) -> bool:
    compact = _compact_text(value).rstrip(":：")
    if not compact:
        return True
    if compact in ALL_FIELD_ALIASES or any(compact == alias for alias in ALL_FIELD_ALIASES):
        return True
    return bool(re.search(r"(?:招标编号|采购编号|项目编号|分标编号|分标名称|包名称|包号|招标人|采购人|招标代理机构|代理机构)\s*[:：]", value))


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _source_page_by_snippet(content_list: list[dict[str, Any]], snippet: str) -> int | None:
    if not snippet:
        return None
    needle = _compact_text(snippet[:40])
    if not needle:
        return None
    for item in content_list:
        text = _compact_text(str(item.get("text") or ""))
        if needle in text:
            page_idx = item.get("page_idx")
            return int(page_idx) + 1 if isinstance(page_idx, int) else None
    return None


def _field_patterns(alias: str) -> list[str]:
    escaped = re.escape(alias)
    return [
        rf"(?:^|\n)[ \t\u3000]*(?:[-*+][ \t\u3000]*)?(?:\*\*)?{escaped}(?:\*\*)?[ \t\u3000]*[:：][ \t\u3000]*([^\n|]+?)(?:\n|$)",
        rf"(?:^|\n)\s*\|\s*(?:\*\*)?{escaped}(?:\*\*)?\s*\|\s*(.+?)\s*\|",
    ]


def _extract_direct_field(markdown: str, canonical_label: str, content_list: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    aliases = FIELD_ALIASES.get(canonical_label, (canonical_label,))
    for alias in aliases:
        for pattern in _field_patterns(alias):
            match = re.search(pattern, markdown)
            if not match:
                continue
            raw_value = match.group(1)
            value = clean_metadata_value(raw_value)
            if not value or _looks_like_field_label(value):
                continue
            snippet = match.group(0)
            return value, {
                "source": "tender_file_structured_extract",
                "matched_label": alias,
                "source_page": _source_page_by_snippet(content_list, snippet),
                "snippet": clean_metadata_value(snippet, max_chars=180),
            }
    return "", None


def _infer_project_name(markdown: str, content_list: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    candidates = [
        r"#\s*(.+?（项目名称）.+?)(?:\n|$)",
        r"^\s*(.+?招标采购(?:项目)?)(?:招标文件|采购文件)?\s*$",
        r"^\s*(.+?)(?:招标文件|采购文件)\s*$",
    ]
    for pattern in candidates:
        match = re.search(pattern, markdown, flags=re.MULTILINE)
        if not match:
            continue
        value = clean_metadata_value(match.group(1))
        value = value.replace("（项目名称）", "").strip()
        value = re.sub(r"(招标文件|采购文件)$", "", value).strip()
        if value and not _looks_like_field_label(value):
            return value, {
                "source": "tender_file_title_extract",
                "matched_label": "标题",
                "source_page": _source_page_by_snippet(content_list, match.group(0)),
                "snippet": clean_metadata_value(match.group(0), max_chars=180),
            }
    return "", None


def _infer_file_type(markdown: str) -> str:
    for candidate in ("商务投标文件", "技术投标文件", "资格投标文件", "价格投标文件", "投标文件"):
        if candidate in markdown[:2000]:
            return candidate
    return "投标文件"


def extract_tender_project_metadata(markdown: str, content_list: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Extract cover-ready project fields from an uploaded tender document.

    The result is intentionally auditable: every extracted field has a source
    record so export metadata can explain whether the cover used structured
    tender data or a fallback value.
    """
    content_items = content_list if isinstance(content_list, list) else []
    cover_fields: dict[str, str] = {}
    field_sources: dict[str, dict[str, Any]] = {}

    for label in COVER_FIELD_LABELS:
        value, source = _extract_direct_field(markdown, label, content_items)
        if value:
            cover_fields[label] = value
            if source:
                field_sources[label] = source

    if not cover_fields.get("项目名称"):
        value, source = _infer_project_name(markdown, content_items)
        if value:
            cover_fields["项目名称"] = value
            if source:
                field_sources["项目名称"] = source

    if not cover_fields.get("文件类型"):
        cover_fields["文件类型"] = _infer_file_type(markdown)
        field_sources["文件类型"] = {"source": "default_bid_document_type", "matched_label": "默认投标文件"}

    missing = [label for label in COVER_FIELD_LABELS if label not in cover_fields and label not in {"招标人", "招标代理机构"}]
    project_name = cover_fields.get("项目名称")
    return {
        "project_name": project_name,
        "tender_no": cover_fields.get("招标编号"),
        "project_no": cover_fields.get("招标编号"),
        "tender_unit": cover_fields.get("招标人"),
        "agency": cover_fields.get("招标代理机构"),
        "document_type": "招标文件",
        "parser": "mineru",
        "cover_fields": cover_fields,
        "cover_field_sources": field_sources,
        "cover_field_missing": missing,
        "cover_field_source_priority": [
            "uploaded_tender_structured_extract",
            "markdown_fallback",
            "manual_review",
        ],
    }

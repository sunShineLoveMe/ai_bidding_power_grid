#!/usr/bin/env python3
"""只读盘点泰昌两份历史 Word，生成候选清单、历史参考骨架和来源对照。

本脚本直接读取 DOCX XML、样式、关系、表格和媒体，不调用 MinerU/OCR，
不解包客户图片到正式资产目录，也不写数据库。所有抽取结果均为候选或
版式线索，默认 ``review_only`` 且 ``allowed_for_bid=false``。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import posixpath
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

from lxml import etree
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = PROJECT_ROOT / "assets" / "template_words"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs" / "development" / "taichang-bid-v1-data"
DEFAULT_TECHNICAL_DOCX = TEMPLATE_ROOT / "技术补充文件.docx"
DEFAULT_BUSINESS_DOCX = TEMPLATE_ROOT / "商务补充文件.docx"
DEFAULT_TENDER_DOCX = (
    TEMPLATE_ROOT
    / "包1_完整招标文件_92475576192439826"
    / "SL2655招标文件-预审.docx"
)
DEFAULT_BASELINE = DEFAULT_OUTPUT_DIR / "current_asset_baseline.json"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W_NS, "r": R_NS, "a": A_NS, "wp": WP_NS}

ORIGIN_TYPES = {
    "tender_mandated",
    "tender_conditional",
    "tender_scoring_derived",
    "taichang_habitual_addition",
    "reference_layout_only",
    "uncertain",
}

CSV_FIELDS = [
    "candidate_id",
    "bid_volume",
    "record_type",
    "chapter_id",
    "chapter_level",
    "chapter_number",
    "title",
    "form_name",
    "source_file",
    "source_section",
    "source_page",
    "source_page_end",
    "origin_type",
    "source_tender_file",
    "source_clause",
    "match_method",
    "confidence",
    "review_status",
    "content_role",
    "fact_kind",
    "evidence_strength",
    "parameter_value_type",
    "applicable_product",
    "applicable_material",
    "report_or_certificate_no",
    "validity_status",
    "reuse_decision",
    "quality_tier",
    "allowed_for_bid",
    "table_index",
    "table_rows",
    "table_columns",
    "media_relationship_id",
    "media_target",
    "media_sha256",
    "media_width",
    "media_height",
    "content_sha256",
    "notes",
]

PRODUCT_TERMS = (
    "CPVC",
    "PVC-C",
    "MPP",
    "N-HAP",
    "UPVC",
    "PVC复合材料管",
    "PVC复合",
    "PE电缆保护管",
    "架空绝缘导线",
    "电缆保护管",
)
CONDITIONAL_MARKERS = (
    "如有",
    "本批次不适用",
    "不适用",
    "接受补充",
    "更新或补充",
    "过期",
    "根据本单位",
)
EVIDENCE_LAYOUT_MARKERS = (
    "证书",
    "报告",
    "截图",
    "通知书",
    "凭证",
    "营业执照",
    "许可证",
    "证明材料",
    "附件",
)
HABITUAL_MARKERS = (
    "方案",
    "措施",
    "流程",
    "保障",
    "承诺",
    "服务",
    "培训",
    "指导",
    "响应",
    "管控",
    "环境",
    "备品备件",
)
PARAMETER_MARKERS = (
    "内径",
    "外径",
    "壁厚",
    "环刚度",
    "密度",
    "断裂伸长率",
    "维卡",
    "熔体",
    "落锤",
    "公称",
    "弯曲",
    "拉伸",
    "冲击",
    "保证值",
    "标准参数值",
    "项目需求值",
)
EQUIPMENT_TERMS = (
    "电子拉力试验机",
    "微机控制电子万能试验机",
    "熔体流动速率仪",
    "热变型、维卡软化点温度测定仪",
    "热变型维卡软化点温度测定仪",
    "锤击试验装置",
    "电子天平",
)


def _qname(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _content_sha256(*values: Any) -> str:
    payload = "|".join(_text(value) for value in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def _paragraph_text(paragraph: etree._Element) -> str:
    return _text("".join(paragraph.xpath(".//w:t/text()", namespaces=NS)))


def _element_text(element: etree._Element) -> str:
    return _text(" ".join(element.xpath(".//w:t/text()", namespaces=NS)))


def _style_level(style_name: str, style_id: str) -> int | None:
    normalized = style_name.lower().strip()
    if "toc" in normalized or "目录" in normalized:
        return None
    match = re.search(r"heading\s*([1-9])", normalized)
    if match:
        return int(match.group(1))
    if style_id in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
        return int(style_id)
    return None


def _strip_toc_page(text: str) -> str:
    return re.sub(r"(?<=[\u4e00-\u9fffA-Za-z）)])\s*\d{1,4}$", "", _text(text))


def _chapter_number(title: str) -> str:
    text = _strip_toc_page(title)
    patterns = [
        r"^(第[一二三四五六七八九十百]+章)",
        r"^([一二三四五六七八九十]+、)",
        r"^([（(][一二三四五六七八九十0-9]+[）)])",
        r"^(\d+(?:\.\d+)*[.、]?)",
        r"^(附表\s*\d+)",
        r"^(附[:：]?)",
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            return match.group(1)
    return ""


def normalize_heading(title: str) -> str:
    """将目录页码、编号、上传路径和条件注释移除后用于保守匹配。"""

    text = _strip_toc_page(title)
    text = re.sub(r"（(?:上传)?投标工具路径[^）]*）", "", text)
    text = re.sub(r"\((?:上传)?投标工具路径[^)]*\)", "", text, flags=re.I)
    text = re.sub(r"（根据本单位信息系统情况编制）", "", text)
    text = re.sub(r"（本批次不适用[^）]*）", "", text)
    text = re.sub(r"（如有[^）]*）", "", text)
    text = re.sub(r"^(?:第[一二三四五六七八九十百]+章\s*)", "", text)
    text = re.sub(r"^(?:[一二三四五六七八九十]+、)", "", text)
    text = re.sub(r"^(?:[（(][一二三四五六七八九十0-9]+[）)])", "", text)
    text = re.sub(r"^(?:\d+(?:\.\d+)*[.、]?\s*)", "", text)
    text = re.sub(r"^(?:附表\s*\d+\s*)", "", text)
    return re.sub(r"[\s\u3000，,。；;：:（）()“”‘’/\-—_]+", "", text).lower()


def _detect_products(text: str) -> list[str]:
    upper = text.upper()
    found: list[str] = []
    for term in PRODUCT_TERMS:
        if term.upper() in upper and term not in found:
            found.append(term)
    return found


def _detect_materials(text: str) -> list[str]:
    products = _detect_products(text)
    if products:
        return products
    return ["物资类通用"]


def _is_form_name(title: str) -> bool:
    return any(marker in title for marker in ("表", "函", "书", "说明", "保险", "授权", "承诺"))


def _content_role(title: str, bid_volume: str) -> str:
    if any(marker in title for marker in ("偏差", "承诺", "投标保证", "响应")):
        return "项目专属响应/承诺/偏差"
    if any(marker in title for marker in ("参数", "组件材料", "产品", "工艺", "生产", "检测", "试验")):
        return "产品事实与结构化参数"
    if any(marker in title for marker in EVIDENCE_LAYOUT_MARKERS):
        return "正式证据包候选"
    if any(marker in title for marker in ("评分", "评审", "招标文件", "资格要求")):
        return "招标原文/评分项引用"
    if any(marker in title for marker in ("身份证", "公章", "签名", "财务", "审计")):
        return "敏感/限制/待复核内容"
    if bid_volume == "business":
        return "泰昌可复用企业事实"
    return "泰昌历史编制内容候选"


@dataclass
class TenderMatch:
    origin_type: str
    source_clause: str = ""
    match_method: str = "none"
    confidence: float = 0.45
    review_status: str = "needs_manual_review"


class TenderMatcher:
    def __init__(self, tender_path: Path):
        self.tender_path = tender_path
        self.source_file = _rel(tender_path)
        # P0-03 只对单个 SL2655 样本做来源对照。这里按语义标题定位样本的
        # 格式/组成内容，不把样本实际出现的“第六章”固化成通用章节规则。
        self.clauses = self._load_sample_format_clauses(tender_path)

    @staticmethod
    def _load_sample_format_clauses(path: Path) -> list[dict[str, str]]:
        with ZipFile(path) as archive:
            root = etree.fromstring(archive.read("word/document.xml"))
        paragraphs = root.findall(".//w:p", NS)
        texts = [_paragraph_text(paragraph) for paragraph in paragraphs]
        semantic_titles = {
            "投标文件格式",
            "投标文件组成",
            "投标文件组成及格式",
            "投标文件编制要求",
        }
        starts = [
            index
            for index, text in enumerate(texts)
            if normalize_heading(text) in semantic_titles
        ]
        start = starts[-1] if starts else 0
        clauses: list[dict[str, str]] = []
        for index, raw in enumerate(texts[start:], start=start):
            if not raw or len(raw) > 500:
                continue
            normalized = normalize_heading(raw)
            if len(normalized) < 2:
                continue
            clauses.append({"paragraph_index": str(index), "text": raw, "normalized": normalized})
        return clauses

    def classify(self, title: str, heading_path: Iterable[str]) -> TenderMatch:
        normalized = normalize_heading(title)
        if not normalized:
            return TenderMatch(origin_type="uncertain", confidence=0.2)

        exact = [clause for clause in self.clauses if clause["normalized"] == normalized]
        if exact:
            clause = min(exact, key=lambda item: len(item["text"]))
            conditional = any(marker in clause["text"] or marker in title for marker in CONDITIONAL_MARKERS)
            return TenderMatch(
                origin_type="tender_conditional" if conditional else "tender_mandated",
                source_clause=clause["text"],
                match_method="normalized_exact",
                confidence=0.98,
                review_status="source_matched",
            )

        fuzzy: list[tuple[float, dict[str, str]]] = []
        for clause in self.clauses:
            candidate = clause["normalized"]
            shorter, longer = sorted((normalized, candidate), key=len)
            if len(shorter) < 4 or shorter not in longer:
                continue
            ratio = len(shorter) / max(len(longer), 1)
            if ratio >= 0.62:
                fuzzy.append((ratio, clause))
        if fuzzy:
            score, clause = max(fuzzy, key=lambda item: item[0])
            conditional = any(marker in clause["text"] or marker in title for marker in CONDITIONAL_MARKERS)
            return TenderMatch(
                origin_type="tender_conditional" if conditional else "tender_mandated",
                source_clause=clause["text"],
                match_method="normalized_contains",
                confidence=round(min(0.94, 0.72 + score * 0.2), 3),
                review_status="source_matched",
            )

        path_text = " / ".join(heading_path)
        if "评审要素" in path_text:
            return TenderMatch(
                origin_type="tender_scoring_derived",
                source_clause="5.针对评审要素，需要补充的其他文件",
                match_method="parent_scoring_section",
                confidence=0.78,
                review_status="needs_manual_review",
            )
        if any(marker in title for marker in EVIDENCE_LAYOUT_MARKERS):
            return TenderMatch(
                origin_type="reference_layout_only",
                match_method="evidence_layout_heuristic",
                confidence=0.68,
                review_status="needs_manual_review",
            )
        if any(marker in title for marker in HABITUAL_MARKERS):
            return TenderMatch(
                origin_type="taichang_habitual_addition",
                match_method="historical_writing_heuristic",
                confidence=0.66,
                review_status="needs_manual_review",
            )
        return TenderMatch(origin_type="uncertain", confidence=0.35)


@dataclass
class Chapter:
    chapter_id: str
    bid_volume: str
    level: int
    number: str
    title: str
    source_section: str
    page_start: int
    page_end: int
    rendered_page_start: int
    toc_page_matched: bool
    paragraph_index: int
    path: list[str]
    origin: TenderMatch
    table_ids: list[str] = field(default_factory=list)
    media_ids: list[str] = field(default_factory=list)
    fact_ids: list[str] = field(default_factory=list)


class DocxInventory:
    def __init__(
        self,
        path: Path,
        bid_volume: str,
        matcher: TenderMatcher,
        known_reports: set[str],
    ):
        self.path = path
        self.bid_volume = bid_volume
        self.matcher = matcher
        self.known_reports = known_reports
        self.source_file = _rel(path)
        self.source_sha256 = _sha256_file(path)
        self.rows: list[dict[str, Any]] = []
        self.chapters: list[Chapter] = []
        self.warnings: list[str] = []
        self.stats: dict[str, Any] = {}

    def run(self) -> tuple[list[dict[str, Any]], list[Chapter], dict[str, Any]]:
        with ZipFile(self.path) as archive:
            root = etree.fromstring(archive.read("word/document.xml"))
            styles = self._load_styles(archive)
            toc_entries = self._load_toc_entries(root, styles)
            toc_pages = self._toc_page_queues(toc_entries)
            relationships = self._load_relationships(archive)
            app_props = self._load_app_properties(archive)
            media_info = self._load_media_info(archive)
            header_footer_stats = self._header_footer_stats(archive)

            body = root.find("w:body", NS)
            if body is None:
                raise RuntimeError(f"DOCX 缺少 w:body: {self.path}")

            rendered_break_total = len(root.findall(".//w:lastRenderedPageBreak", NS))
            manual_break_total = len(root.xpath('.//w:br[@w:type="page"]', namespaces=NS))
            page_count = int(app_props.get("Pages") or 0)
            current_page = 1
            current_chapter: Chapter | None = None
            heading_stack: list[Chapter] = []
            paragraph_index = 0
            table_index = 0
            media_occurrence = 0
            nonempty_paragraphs = 0
            text_chars = 0
            broken_relationships: list[str] = []
            seen_fact_keys: set[tuple[Any, ...]] = set()

            for element in body:
                page_start = current_page
                element_rendered_breaks = len(element.findall(".//w:lastRenderedPageBreak", NS))
                if element.tag == _qname(W_NS, "p"):
                    paragraph_index += 1
                    text = _paragraph_text(element)
                    if text:
                        nonempty_paragraphs += 1
                        text_chars += len(text)
                    style_id, style_name = self._paragraph_style(element, styles)
                    level = _style_level(style_name, style_id)
                    if text and level is not None:
                        while heading_stack and heading_stack[-1].level >= level:
                            heading_stack.pop()
                        heading_path = [chapter.title for chapter in heading_stack] + [text]
                        origin = self.matcher.classify(text, heading_path)
                        toc_page = self._take_toc_page(toc_pages, level, text)
                        chapter_page = toc_page or page_start
                        chapter_id = f"{self.bid_volume}-chapter-{len(self.chapters) + 1:03d}"
                        current_chapter = Chapter(
                            chapter_id=chapter_id,
                            bid_volume=self.bid_volume,
                            level=level,
                            number=_chapter_number(text),
                            title=text,
                            source_section=" / ".join(heading_path),
                            page_start=chapter_page,
                            page_end=chapter_page,
                            rendered_page_start=page_start,
                            toc_page_matched=toc_page is not None,
                            paragraph_index=paragraph_index,
                            path=heading_path,
                            origin=origin,
                        )
                        self.chapters.append(current_chapter)
                        heading_stack.append(current_chapter)
                        self.rows.append(self._chapter_row(current_chapter))
                    if text and not self._is_toc_style(style_name):
                        self._extract_fact_candidates(
                            text,
                            current_chapter,
                            self._map_page(page_start, current_chapter, page_count),
                            seen_fact_keys,
                        )
                elif element.tag == _qname(W_NS, "tbl"):
                    table_index += 1
                    table_id = f"{self.bid_volume}-table-{table_index:03d}"
                    table_rows = self._table_rows(element)
                    table_title = current_chapter.title if current_chapter else f"表格{table_index}"
                    table_row = self._base_row(
                        candidate_id=table_id,
                        record_type="table",
                        chapter=current_chapter,
                        title=table_title,
                        source_page=self._map_page(page_start, current_chapter, page_count),
                    )
                    table_row.update(
                        {
                            "form_name": table_title if _is_form_name(table_title) else "",
                            "table_index": table_index,
                            "table_rows": len(table_rows),
                            "table_columns": max((len(row) for row in table_rows), default=0),
                            "content_sha256": _content_sha256(table_rows),
                            "reuse_decision": "preserve_structure_review_before_reuse",
                            "notes": self._table_note(table_rows),
                        }
                    )
                    self.rows.append(table_row)
                    if current_chapter:
                        current_chapter.table_ids.append(table_id)
                    for cell_text in (cell for row in table_rows for cell in row if cell):
                        self._extract_fact_candidates(
                            cell_text,
                            current_chapter,
                            self._map_page(page_start, current_chapter, page_count),
                            seen_fact_keys,
                        )

                for drawing in element.findall(".//w:drawing", NS):
                    media_occurrence += 1
                    media_id = f"{self.bid_volume}-media-{media_occurrence:04d}"
                    blip = drawing.find(".//a:blip", NS)
                    rel_id = blip.get(_qname(R_NS, "embed")) if blip is not None else ""
                    target = relationships.get(rel_id or "", "")
                    normalized_target = self._normalize_word_target(target)
                    info = media_info.get(normalized_target, {})
                    if rel_id and not info:
                        broken_relationships.append(rel_id)
                    media_row = self._base_row(
                        candidate_id=media_id,
                        record_type="media",
                        chapter=current_chapter,
                        title=(current_chapter.title if current_chapter else "历史标书内嵌媒体"),
                        source_page=self._map_page(page_start, current_chapter, page_count),
                    )
                    media_row.update(
                        {
                            "media_relationship_id": rel_id,
                            "media_target": normalized_target,
                            "media_sha256": info.get("sha256", ""),
                            "media_width": info.get("width", ""),
                            "media_height": info.get("height", ""),
                            "content_sha256": info.get("sha256", ""),
                            "reuse_decision": "inventory_only_needs_original_evidence_or_manual_promotion",
                            "notes": "Word内嵌媒体未导出；不得直接提升为正式图片资产",
                        }
                    )
                    self.rows.append(media_row)
                    if current_chapter:
                        current_chapter.media_ids.append(media_id)

                current_page += element_rendered_breaks

            effective_pages = page_count or max(1, current_page)
            for index, chapter in enumerate(self.chapters):
                next_page = self.chapters[index + 1].page_start if index + 1 < len(self.chapters) else effective_pages + 1
                chapter.page_end = max(chapter.page_start, min(effective_pages, next_page - 1))
                row = next(item for item in self.rows if item["candidate_id"] == chapter.chapter_id)
                row["source_page_end"] = chapter.page_end

            media_occurrence_hashes = [row["media_sha256"] for row in self.rows if row["record_type"] == "media" and row["media_sha256"]]
            self.stats = {
                "source_file": self.source_file,
                "source_sha256": self.source_sha256,
                "file_size": self.path.stat().st_size,
                "parser": "native_docx_xml",
                "mineru_invoked": False,
                "app_properties": app_props,
                "pages_declared": page_count,
                "pages_from_rendered_breaks": rendered_break_total + 1,
                "page_sequence_coverage": round((rendered_break_total + 1) / page_count, 4) if page_count else None,
                "page_sequence_method": "toc_page_number_with_rendered_break_fallback",
                "toc_entries": len(toc_entries),
                "headings_with_toc_page": sum(
                    1 for chapter in self.chapters if chapter.toc_page_matched
                ),
                "manual_page_breaks": manual_break_total,
                "paragraphs_total": len(root.findall(".//w:p", NS)),
                "paragraphs_nonempty_body": nonempty_paragraphs,
                "text_characters_body": text_chars,
                "headings": len(self.chapters),
                "heading_levels": dict(sorted(Counter(chapter.level for chapter in self.chapters).items())),
                "tables": table_index,
                "media_files": len(media_info),
                "media_occurrences": media_occurrence,
                "unique_media_sha256": len(set(media_occurrence_hashes)),
                "duplicate_media_occurrences": max(0, len(media_occurrence_hashes) - len(set(media_occurrence_hashes))),
                "broken_media_relationships": sorted(set(broken_relationships)),
                "headers_footers": header_footer_stats,
                "sections": len(root.findall(".//w:sectPr", NS)),
                "candidate_rows": len(self.rows),
                "candidate_rows_by_type": dict(sorted(Counter(row["record_type"] for row in self.rows).items())),
                "origin_types": dict(sorted(Counter(chapter.origin.origin_type for chapter in self.chapters).items())),
                "review_statuses": dict(sorted(Counter(chapter.origin.review_status for chapter in self.chapters).items())),
                "warnings": self._quality_warnings(page_count, rendered_break_total, broken_relationships),
            }
        return self.rows, self.chapters, self.stats

    @staticmethod
    def _load_styles(archive: ZipFile) -> dict[str, str]:
        root = etree.fromstring(archive.read("word/styles.xml"))
        styles: dict[str, str] = {}
        for style in root.findall("w:style", NS):
            style_id = style.get(_qname(W_NS, "styleId"), "")
            name = style.find("w:name", NS)
            styles[style_id] = name.get(_qname(W_NS, "val"), "") if name is not None else ""
        return styles

    @classmethod
    def _load_toc_entries(
        cls,
        root: etree._Element,
        styles: dict[str, str],
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for paragraph in root.findall(".//w:p", NS):
            text = _paragraph_text(paragraph)
            if not text:
                continue
            style_id, style_name = cls._paragraph_style(paragraph, styles)
            normalized_style = style_name.lower()
            if "toc" not in normalized_style and "目录" not in normalized_style:
                continue
            level_match = re.search(r"(?:toc|目录)\s*([1-9])", normalized_style)
            if not level_match:
                level_match = re.search(r"([1-9])0$", style_id)
            page_match = re.search(r"(\d{1,4})\s*$", text)
            if not level_match or not page_match:
                continue
            title = re.sub(r"\s*\d{1,4}\s*$", "", text)
            entries.append(
                {
                    "level": int(level_match.group(1)),
                    "title": title,
                    "normalized": normalize_heading(title),
                    "page": int(page_match.group(1)),
                }
            )
        return entries

    @staticmethod
    def _toc_page_queues(entries: list[dict[str, Any]]) -> dict[tuple[int, str], list[int]]:
        queues: dict[tuple[int, str], list[int]] = {}
        for entry in entries:
            queues.setdefault((entry["level"], entry["normalized"]), []).append(entry["page"])
        return queues

    @staticmethod
    def _take_toc_page(queues: dict[tuple[int, str], list[int]], level: int, title: str) -> int | None:
        queue = queues.get((level, normalize_heading(title)))
        if not queue:
            return None
        return queue.pop(0)

    @staticmethod
    def _map_page(rendered_page: int, chapter: Chapter | None, page_count: int) -> int:
        if chapter is None:
            return rendered_page
        mapped = chapter.page_start + max(0, rendered_page - chapter.rendered_page_start)
        return min(page_count, mapped) if page_count else mapped

    @staticmethod
    def _load_relationships(archive: ZipFile) -> dict[str, str]:
        name = "word/_rels/document.xml.rels"
        if name not in archive.namelist():
            return {}
        root = etree.fromstring(archive.read(name))
        return {
            relation.get("Id", ""): relation.get("Target", "")
            for relation in root.findall(f"{{{PKG_REL_NS}}}Relationship")
        }

    @staticmethod
    def _load_app_properties(archive: ZipFile) -> dict[str, Any]:
        if "docProps/app.xml" not in archive.namelist():
            return {}
        root = etree.fromstring(archive.read("docProps/app.xml"))
        wanted = {"Pages", "Words", "Characters", "Lines", "Paragraphs", "Application", "AppVersion"}
        return {etree.QName(element).localname: element.text for element in root if etree.QName(element).localname in wanted}

    @staticmethod
    def _load_media_info(archive: ZipFile) -> dict[str, dict[str, Any]]:
        info: dict[str, dict[str, Any]] = {}
        for name in sorted(item for item in archive.namelist() if item.startswith("word/media/")):
            data = archive.read(name)
            width: int | str = ""
            height: int | str = ""
            try:
                with Image.open(io.BytesIO(data)) as image:
                    width, height = image.size
            except Exception:
                pass
            info[name] = {
                "sha256": _sha256_bytes(data),
                "width": width,
                "height": height,
                "size": len(data),
            }
        return info

    @staticmethod
    def _header_footer_stats(archive: ZipFile) -> dict[str, Any]:
        names = sorted(
            name
            for name in archive.namelist()
            if re.match(r"word/(?:header|footer)\d+\.xml$", name)
        )
        return {
            "parts": len(names),
            "files": names,
            "nonempty_parts": sum(1 for name in names if _element_text(etree.fromstring(archive.read(name)))),
        }

    @staticmethod
    def _paragraph_style(paragraph: etree._Element, styles: dict[str, str]) -> tuple[str, str]:
        node = paragraph.find("./w:pPr/w:pStyle", NS)
        style_id = node.get(_qname(W_NS, "val"), "") if node is not None else ""
        return style_id, styles.get(style_id, "")

    @staticmethod
    def _is_toc_style(style_name: str) -> bool:
        normalized = style_name.lower()
        return "toc" in normalized or "目录" in normalized

    @staticmethod
    def _table_rows(table: etree._Element) -> list[list[str]]:
        rows: list[list[str]] = []
        for row in table.findall("./w:tr", NS):
            cells = [_element_text(cell) for cell in row.findall("./w:tc", NS)]
            if any(cells):
                rows.append(cells)
        return rows

    @staticmethod
    def _table_note(rows: list[list[str]]) -> str:
        if not rows:
            return "空表或未提取到可见单元格文字，需人工复核"
        first = " | ".join(rows[0])[:240]
        return f"首行：{first}" if first else "表格首行无可见文字，需人工复核"

    @staticmethod
    def _normalize_word_target(target: str) -> str:
        if not target:
            return ""
        return posixpath.normpath(posixpath.join("word", target.lstrip("/")))

    def _chapter_row(self, chapter: Chapter) -> dict[str, Any]:
        row = self._base_row(
            candidate_id=chapter.chapter_id,
            record_type="chapter",
            chapter=chapter,
            title=chapter.title,
            source_page=chapter.page_start,
        )
        row.update(
            {
                "form_name": chapter.title if _is_form_name(chapter.title) else "",
                "content_sha256": _content_sha256(chapter.title, chapter.source_section),
                "reuse_decision": (
                    "historical_reference_skeleton_candidate"
                    if chapter.origin.origin_type in {"tender_mandated", "tender_conditional"}
                    else "manual_review_before_skeleton_reuse"
                ),
            }
        )
        return row

    def _base_row(
        self,
        *,
        candidate_id: str,
        record_type: str,
        chapter: Chapter | None,
        title: str,
        source_page: int,
    ) -> dict[str, Any]:
        origin = chapter.origin if chapter else TenderMatch(origin_type="uncertain", confidence=0.2)
        row = {field: "" for field in CSV_FIELDS}
        row.update(
            {
                "candidate_id": candidate_id,
                "bid_volume": self.bid_volume,
                "record_type": record_type,
                "chapter_id": chapter.chapter_id if chapter else "",
                "chapter_level": chapter.level if chapter else "",
                "chapter_number": chapter.number if chapter else "",
                "title": title,
                "source_file": self.source_file,
                "source_section": chapter.source_section if chapter else "未归入章节",
                "source_page": source_page,
                "source_page_end": source_page,
                "origin_type": origin.origin_type,
                "source_tender_file": self.matcher.source_file,
                "source_clause": origin.source_clause,
                "match_method": origin.match_method,
                "confidence": origin.confidence,
                "review_status": origin.review_status,
                "content_role": _content_role(title, self.bid_volume),
                "applicable_material": _detect_materials(title),
                "quality_tier": "review_only",
                "allowed_for_bid": False,
                "validity_status": "needs_review",
            }
        )
        return row

    def _add_fact(
        self,
        *,
        chapter: Chapter | None,
        page: int,
        fact_kind: str,
        title: str,
        evidence_strength: str,
        parameter_value_type: str,
        applicable_product: list[str],
        identifier: str,
        validity_status: str,
        reuse_decision: str,
        notes: str,
        seen: set[tuple[Any, ...]],
    ) -> None:
        key = (chapter.chapter_id if chapter else "", fact_kind, identifier or title)
        if key in seen:
            return
        seen.add(key)
        fact_id = f"{self.bid_volume}-fact-{sum(row['record_type'] == 'fact_candidate' for row in self.rows) + 1:04d}"
        row = self._base_row(
            candidate_id=fact_id,
            record_type="fact_candidate",
            chapter=chapter,
            title=title[:260],
            source_page=page,
        )
        row.update(
            {
                "fact_kind": fact_kind,
                "evidence_strength": evidence_strength,
                "parameter_value_type": parameter_value_type,
                "applicable_product": applicable_product,
                "applicable_material": applicable_product or _detect_materials(title),
                "report_or_certificate_no": identifier,
                "validity_status": validity_status,
                "reuse_decision": reuse_decision,
                "content_sha256": _content_sha256(fact_kind, identifier, title),
                "notes": notes,
            }
        )
        self.rows.append(row)
        if chapter:
            chapter.fact_ids.append(fact_id)

    def _extract_fact_candidates(
        self,
        text: str,
        chapter: Chapter | None,
        page: int,
        seen: set[tuple[Any, ...]],
    ) -> None:
        clean = _text(text)
        if not clean:
            return
        products = _detect_products(clean)

        for report_no in sorted(set(re.findall(r"(?<!\d)(20\d{17})(?!\d)", clean))):
            exists = report_no in self.known_reports
            self._add_fact(
                chapter=chapter,
                page=page,
                fact_kind="report_identifier",
                title=f"检验/检测报告编号 {report_no}",
                evidence_strength="existing_structured_evidence" if exists else "historical_index_only",
                parameter_value_type="measured_report_value_reference" if exists else "not_a_parameter_value",
                applicable_product=products,
                identifier=report_no,
                validity_status="existing_evidence_matched" if exists else "needs_original_evidence",
                reuse_decision="duplicate_existing_asset_reference_only" if exists else "needs_original_evidence",
                notes="历史标书中的报告索引；不得仅凭 Word 内截图建立正式报告事实",
                seen=seen,
            )

        for bid_no in sorted(set(re.findall(r"(?<![A-Za-z0-9])(SL\d{3,6}[A-Z]?)(?![A-Za-z0-9])", clean, flags=re.I))):
            self._add_fact(
                chapter=chapter,
                page=page,
                fact_kind="project_identifier",
                title=f"历史项目招标编号 {bid_no.upper()}",
                evidence_strength="historical_document_text",
                parameter_value_type="not_a_parameter_value",
                applicable_product=products,
                identifier=bid_no.upper(),
                validity_status="project_conflict_check_required",
                reuse_decision="project_specific_do_not_reuse",
                notes="项目专属字段；生成新标书时必须由本次招标文件覆盖",
                seen=seen,
            )

        fixed_ids = set(re.findall(r"(?<![A-Za-z0-9])(?:G\d{3}|\d{4})-\d{9}-\d{5}(?!\d)", clean, flags=re.I))
        for fixed_id in sorted(fixed_ids):
            self._add_fact(
                chapter=chapter,
                page=page,
                fact_kind="fixed_parameter_id",
                title=f"固化ID {fixed_id}",
                evidence_strength="historical_document_text",
                parameter_value_type="identifier_only",
                applicable_product=products,
                identifier=fixed_id,
                validity_status="applicability_needs_tender_confirmation",
                reuse_decision="match_current_tender_before_use",
                notes="固化ID不得跨物料、跨批次直接复用",
                seen=seen,
            )

        if re.search(r"完全响应|符合招标文件要求", clean) and len(clean) <= 300:
            self._add_fact(
                chapter=chapter,
                page=page,
                fact_kind="generic_response",
                title=clean,
                evidence_strength="generic_statement_only",
                parameter_value_type="generic_response_not_value",
                applicable_product=products,
                identifier="",
                validity_status="not_parameter_evidence",
                reuse_decision="do_not_write_to_parameter_layer",
                notes="笼统响应不构成投标保证值或检验报告实测值",
                seen=seen,
            )

        if products and any(marker in clean for marker in PARAMETER_MARKERS) and re.search(r"\d", clean):
            self._add_fact(
                chapter=chapter,
                page=page,
                fact_kind="technical_parameter_candidate",
                title=clean[:260],
                evidence_strength="historical_bid_text_unverified",
                parameter_value_type="historical_numeric_text",
                applicable_product=products,
                identifier="",
                validity_status="needs_original_parameter_evidence",
                reuse_decision="compare_structured_parameter_layer_before_use",
                notes="精确数值缺少原始报告/招标条款绑定时不得进入正式参数层",
                seen=seen,
            )

        spec_tokens = sorted(
            set(
                token.replace(" ", "")
                for token in re.findall(
                    r"(?:φ|Φ|DN)?\s*(?:50|100|150|175|200|250)(?:\s*[×xX*]\s*\d+(?:\.\d+)?)?",
                    clean,
                    flags=re.I,
                )
                if token.strip()
            )
        )
        if products and spec_tokens and len(clean) <= 500:
            for token in spec_tokens:
                self._add_fact(
                    chapter=chapter,
                    page=page,
                    fact_kind="candidate_product_spec",
                    title=f"候选产品规格 {token}",
                    evidence_strength="historical_product_list_only",
                    parameter_value_type="product_list_specification",
                    applicable_product=products,
                    identifier=token,
                    validity_status="coverage_unconfirmed",
                    reuse_decision="verify_report_and_current_goods_list_coverage",
                    notes="产品清单规格不等于该规格已有检验报告支持",
                    seen=seen,
                )

        for equipment in EQUIPMENT_TERMS:
            if equipment not in clean:
                continue
            self._add_fact(
                chapter=chapter,
                page=page,
                fact_kind="testing_equipment_candidate",
                title=equipment,
                evidence_strength="historical_bid_evidence_index",
                parameter_value_type="not_a_parameter_value",
                applicable_product=products,
                identifier=equipment,
                validity_status="needs_current_asset_match",
                reuse_decision="deduplicate_by_equipment_model_and_management_no",
                notes="需与现有设备资产按设备型号、管理编号和有效证据归并",
                seen=seen,
            )

    @staticmethod
    def _quality_warnings(page_count: int, rendered_break_total: int, broken_relationships: list[str]) -> list[str]:
        warnings = [
            "图片型证据页未执行 OCR；图片内部文字、印章、签字和表格数值不进入事实候选",
            "页码来自 Word 保存的 lastRenderedPageBreak，章节页序可追溯但不替代最终 Word/PDF 视觉复核",
        ]
        if page_count and rendered_break_total + 1 != page_count:
            warnings.append(
                f"Word声明页数为{page_count}，渲染分页标记可覆盖{rendered_break_total + 1}页，差异需人工复核"
            )
        if broken_relationships:
            warnings.append(f"存在{len(set(broken_relationships))}个无法解析的媒体关系")
        return warnings


def _load_known_reports(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    reports: set[str] = set()
    for record in payload.get("records", []):
        value = _text(record.get("report_or_certificate_no"))
        reports.update(re.findall(r"20\d{17}", value))
    return reports


def _serialize_csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return str(value).lower()
    return value


def _write_inventory(rows: list[dict[str, Any]], output_json: Path, output_csv: Path, metadata: dict[str, Any]) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": metadata, "records": rows}
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in CSV_FIELDS})


def _chapter_payload(chapter: Chapter) -> dict[str, Any]:
    return {
        "node_id": chapter.chapter_id,
        "bid_volume": chapter.bid_volume,
        "level": chapter.level,
        "chapter_number": chapter.number,
        "title": chapter.title,
        "path": chapter.path,
        "source_file": (
            "assets/template_words/技术补充文件.docx"
            if chapter.bid_volume == "technical"
            else "assets/template_words/商务补充文件.docx"
        ),
        "source_section": chapter.source_section,
        "source_page_start": chapter.page_start,
        "source_page_end": chapter.page_end,
        "toc_page_matched": chapter.toc_page_matched,
        "origin_type": chapter.origin.origin_type,
        "source_clause": chapter.origin.source_clause,
        "match_method": chapter.origin.match_method,
        "confidence": chapter.origin.confidence,
        "review_status": chapter.origin.review_status,
        "applicable_material": _detect_materials(" / ".join(chapter.path)),
        "content_role": _content_role(chapter.title, chapter.bid_volume),
        "table_ids": chapter.table_ids,
        "media_ids": chapter.media_ids,
        "fact_candidate_ids": chapter.fact_ids,
        "quality_tier": "review_only",
        "allowed_for_bid": False,
        "reuse_decision": (
            "historical_reference_skeleton_candidate"
            if chapter.origin.origin_type in {"tender_mandated", "tender_conditional"}
            else "manual_review_before_skeleton_reuse"
        ),
    }


def _write_skeleton(
    path: Path,
    *,
    technical: list[Chapter],
    business: list[Chapter],
    technical_stats: dict[str, Any],
    business_stats: dict[str, Any],
    tender_path: Path,
) -> None:
    payload = {
        "schema_version": "taichang_historical_reference_skeleton_v1",
        "artifact_role": "historical_reference_skeleton",
        "not_final_project_skeleton": True,
        "current_tender_semantic_detection_required": True,
        "chapter_number_locator_allowed": False,
        "project_output_contract": "project_bid_skeleton.json",
        "generated_at": datetime.now().astimezone().isoformat(),
        "enterprise": "河北泰昌电力器材科技有限公司",
        "pilot_scope": "泰昌物资类历史标书复用V1",
        "source_domain": "mixed_historical_bid",
        "fact_source_allowed_for_enterprise": False,
        "quality_tier": "review_only",
        "allowed_for_bid": False,
        "parser": "native_docx_xml",
        "mineru_invoked": False,
        "tender_reference": _rel(tender_path),
        "origin_type_enum": sorted(ORIGIN_TYPES),
        "documents": {
            "technical": {"stats": technical_stats, "chapters": [_chapter_payload(item) for item in technical]},
            "business": {"stats": business_stats, "chapters": [_chapter_payload(item) for item in business]},
        },
        "promotion_policy": "本产物只用于历史差异对照；任何章节、表单、事实、参数和媒体均须经当次招标文件包全文语义定位、现有资产去重和人工审核后方可使用",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_crosswalk(path: Path, skeleton_path: Path, tender_path: Path, chapters: list[Chapter]) -> None:
    origin_counts = Counter(chapter.origin.origin_type for chapter in chapters)
    lines = [
        "# 泰昌历史参考骨架—招标条款来源对照表",
        "",
        "> 试点企业：河北泰昌电力器材科技有限公司",
        "> 对照招标文件：`%s`" % _rel(tender_path),
        "> 数据文件：`%s`" % _rel(skeleton_path),
        "> 结论边界：来源匹配只证明章节来源关系，不证明历史正文、参数或证据仍适用于当前项目。",
        "",
        "## 来源类型统计",
        "",
        "| origin_type | 数量 |",
        "| --- | ---: |",
    ]
    for origin_type in sorted(ORIGIN_TYPES):
        lines.append(f"| `{origin_type}` | {origin_counts.get(origin_type, 0)} |")
    lines.extend(
        [
            "",
            "## 章节逐项对照",
            "",
            "| 分册 | 页序 | 层级 | 历史章节 | 来源属性 | 招标文件匹配条款 | 置信度 | 审核状态 |",
            "| --- | ---: | ---: | --- | --- | --- | ---: | --- |",
        ]
    )
    for chapter in chapters:
        clause = chapter.origin.source_clause.replace("|", "\\|")[:180] or "未直接匹配"
        title = chapter.title.replace("|", "\\|")
        lines.append(
            f"| {'技术标' if chapter.bid_volume == 'technical' else '商务标'} | "
            f"{chapter.page_start}-{chapter.page_end} | {chapter.level} | {title} | "
            f"`{chapter.origin.origin_type}` | {clause} | {chapter.origin.confidence:.2f} | "
            f"`{chapter.origin.review_status}` |"
        )
    lines.extend(
        [
            "",
            "## 审核规则",
            "",
            "- `tender_mandated` 与 `tender_conditional` 仅表示在本次 SL2655 样本中找到对应条目；该样本实际来源位于第六章，但不代表其他项目固定为第六章。",
            "- 生成其他项目时必须扫描当次招标文件全套内容、附件和独立格式文件，按语义定位真实来源并生成 `project_bid_skeleton.json`；本历史参考骨架不得直接作为最终目录。",
            "- `tender_scoring_derived`、`taichang_habitual_addition`、`reference_layout_only`、`uncertain` 均不得自动视为招标强制目录。",
            "- 招标文件原样表格优先于历史 Word 表格；历史正文中的项目名称、招标编号、分标、包号、固化 ID、产品规格必须重新绑定当前项目。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_quality_report(
    path: Path,
    *,
    technical_stats: dict[str, Any],
    business_stats: dict[str, Any],
    technical_rows: list[dict[str, Any]],
    business_rows: list[dict[str, Any]],
    known_reports: set[str],
) -> None:
    all_rows = technical_rows + business_rows
    reports = sorted(
        {
            row["report_or_certificate_no"]
            for row in all_rows
            if row["fact_kind"] == "report_identifier" and row["report_or_certificate_no"]
        }
    )
    known = [report for report in reports if report in known_reports]
    missing = [report for report in reports if report not in known_reports]
    lines = [
        "# 两份泰昌历史标书解析质量报告",
        "",
        "> 解析方式：原生 DOCX XML/样式/关系/表格读取",
        "> MinerU/OCR：未调用",
        "> 数据处理：只读；未写数据库、未入库、未提升正式资产",
        "",
        "## 总体统计",
        "",
        "| 指标 | 技术补充文件 | 商务补充文件 |",
        "| --- | ---: | ---: |",
    ]
    metrics = [
        ("Word 声明页数", "pages_declared"),
        ("渲染分页可覆盖页数", "pages_from_rendered_breaks"),
        ("正文段落", "paragraphs_total"),
        ("标题章节", "headings"),
        ("表格", "tables"),
        ("媒体文件", "media_files"),
        ("媒体出现次数", "media_occurrences"),
        ("候选记录", "candidate_rows"),
    ]
    for label, key in metrics:
        lines.append(f"| {label} | {technical_stats.get(key, 0)} | {business_stats.get(key, 0)} |")
    lines.extend(
        [
            "",
            "## 候选记录分布",
            "",
            "| 分册 | chapter | table | media | fact_candidate |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for label, stats in (("技术标", technical_stats), ("商务标", business_stats)):
        counts = stats.get("candidate_rows_by_type", {})
        lines.append(
            f"| {label} | {counts.get('chapter', 0)} | {counts.get('table', 0)} | "
            f"{counts.get('media', 0)} | {counts.get('fact_candidate', 0)} |"
        )
    lines.extend(
        [
            "",
            "## 报告编号交叉核验",
            "",
            f"- 历史 Word 中识别报告编号：{', '.join(reports) if reports else '未识别'}。",
            f"- 已与现有结构化基线匹配：{', '.join(known) if known else '无'}。",
            f"- 仅有历史索引、需原始完整报告：{', '.join(missing) if missing else '无'}。",
            "- 已匹配只表示系统存在同编号证据，不在 P0-03 重复建立资产；未匹配编号不得仅凭 Word 截图正式入库。",
            "",
            "## 内容一致性风险",
            "",
            "- 历史 Word 同时出现 SL265/SL2655、架空绝缘导线、电缆保护管及多个产品族线索，不能整份视为同一项目、同一产品或同一事实域。",
            "- `完全响应/符合招标文件要求` 已作为 `generic_response` 单独标记，不进入正式参数层。",
            "- 产品清单中的 φ50、φ100、φ150、φ175、φ200 等规格只能作为候选范围，不证明每个规格均有检测报告覆盖。",
            "- Word 内图片未做 OCR；证书有效期、报告主体、签章、个人信息和图片内部表格值必须回到客户原始证据核验。",
            "",
            "## 解析缺口与人工复核",
            "",
        ]
    )
    for label, stats in (("技术标", technical_stats), ("商务标", business_stats)):
        for warning in stats.get("warnings", []):
            lines.append(f"- {label}：{warning}。" if not warning.endswith("。") else f"- {label}：{warning}")
    lines.extend(
        [
            "- DOCX 中的 `lastRenderedPageBreak` 可恢复主要页序，但最终页码仍受 Word 字段刷新、字体和打印机版式影响；正式模板复用前需以 Word/PDF 视觉结果复核。",
            "- 本轮没有把媒体文件解包为正式图片资产，也没有对任何候选赋予 `formal_bid_ready`。",
            "",
            "## 结论",
            "",
            "两份 Word 的章节、表格、媒体关系和主要页序已可追溯；历史参考骨架可作为泰昌 V1 差异对照底稿，但不得直接作为新项目最终目录。每次生成必须先对当次招标文件包全文语义定位，以实际识别到的格式、组成、编制要求及澄清补遗为最高优先级。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _validate_outputs(
    technical_rows: list[dict[str, Any]],
    business_rows: list[dict[str, Any]],
    chapters: list[Chapter],
) -> list[str]:
    failures: list[str] = []
    for label, rows in (("technical", technical_rows), ("business", business_rows)):
        if not rows:
            failures.append(f"{label}: inventory empty")
        if any(row.get("quality_tier") != "review_only" for row in rows):
            failures.append(f"{label}: non-review-only candidate found")
        if any(row.get("allowed_for_bid") is not False for row in rows):
            failures.append(f"{label}: allowed_for_bid candidate found")
        if any(not row.get("candidate_id") for row in rows):
            failures.append(f"{label}: candidate without id")
        for row in rows:
            if row.get("record_type") == "fact_candidate":
                required = (
                    "fact_kind",
                    "evidence_strength",
                    "parameter_value_type",
                    "validity_status",
                    "reuse_decision",
                )
                if any(not row.get(field) for field in required):
                    failures.append(f"{label}: incomplete fact candidate {row.get('candidate_id')}")
    for chapter in chapters:
        if chapter.origin.origin_type not in ORIGIN_TYPES:
            failures.append(f"invalid origin type: {chapter.origin.origin_type}")
        if not chapter.source_section or not chapter.origin.review_status:
            failures.append(f"incomplete chapter provenance: {chapter.chapter_id}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="生成泰昌历史技术标/商务标只读 inventory 与历史参考骨架")
    parser.add_argument("--technical", type=Path, default=DEFAULT_TECHNICAL_DOCX)
    parser.add_argument("--business", type=Path, default=DEFAULT_BUSINESS_DOCX)
    parser.add_argument("--tender", type=Path, default=DEFAULT_TENDER_DOCX)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    for path in (args.technical, args.business, args.tender):
        if not path.exists():
            raise FileNotFoundError(path)

    matcher = TenderMatcher(args.tender)
    known_reports = _load_known_reports(args.baseline)
    technical_inventory = DocxInventory(args.technical, "technical", matcher, known_reports)
    business_inventory = DocxInventory(args.business, "business", matcher, known_reports)
    technical_rows, technical_chapters, technical_stats = technical_inventory.run()
    business_rows, business_chapters, business_stats = business_inventory.run()
    all_chapters = technical_chapters + business_chapters

    failures = _validate_outputs(technical_rows, business_rows, all_chapters)
    if failures:
        raise RuntimeError("; ".join(failures))

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone().isoformat()
    common_metadata = {
        "schema_version": "taichang_historical_bid_candidate_inventory_v1",
        "generated_at": generated_at,
        "enterprise": "河北泰昌电力器材科技有限公司",
        "source_domain": "mixed_historical_bid",
        "quality_tier": "review_only",
        "allowed_for_bid": False,
        "database_written": False,
        "mineru_invoked": False,
        "tender_reference": _rel(args.tender),
    }
    technical_json = output_dir / "taichang_technical_bid_candidate_inventory.json"
    technical_csv = output_dir / "taichang_technical_bid_candidate_inventory.csv"
    business_json = output_dir / "taichang_business_bid_candidate_inventory.json"
    business_csv = output_dir / "taichang_business_bid_candidate_inventory.csv"
    skeleton_path = output_dir / "taichang_historical_reference_skeleton.json"
    crosswalk_path = PROJECT_ROOT / "docs" / "development" / "taichang-historical-skeleton-tender-crosswalk-20260713.md"
    quality_path = PROJECT_ROOT / "docs" / "development" / "taichang-historical-bid-parse-quality-report-20260713.md"

    _write_inventory(
        technical_rows,
        technical_json,
        technical_csv,
        {**common_metadata, "bid_volume": "technical", "stats": technical_stats},
    )
    _write_inventory(
        business_rows,
        business_json,
        business_csv,
        {**common_metadata, "bid_volume": "business", "stats": business_stats},
    )
    _write_skeleton(
        skeleton_path,
        technical=technical_chapters,
        business=business_chapters,
        technical_stats=technical_stats,
        business_stats=business_stats,
        tender_path=args.tender,
    )
    _write_crosswalk(crosswalk_path, skeleton_path, args.tender, all_chapters)
    _write_quality_report(
        quality_path,
        technical_stats=technical_stats,
        business_stats=business_stats,
        technical_rows=technical_rows,
        business_rows=business_rows,
        known_reports=known_reports,
    )

    result = {
        "generated_at": generated_at,
        "technical_inventory": _rel(technical_json),
        "business_inventory": _rel(business_json),
        "historical_reference_skeleton": _rel(skeleton_path),
        "crosswalk": _rel(crosswalk_path),
        "quality_report": _rel(quality_path),
        "technical_stats": technical_stats,
        "business_stats": business_stats,
        "mineru_invoked": False,
        "database_written": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

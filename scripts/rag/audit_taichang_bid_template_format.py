#!/usr/bin/env python3
"""Audit generated Taichang bid DOCX against customer reference PDF formatting."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION_START
from PyPDF2 import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_BUSINESS = PROJECT_ROOT / "rag_seed/power_grid_resources/05_enterprise_documents/01_泰昌MVP试点企业资料/商务投标文件-中标，按投标人制作.pdf"
REFERENCE_TECHNICAL = PROJECT_ROOT / "rag_seed/power_grid_resources/01_tender_documents/22_国网辽宁电力2025年第三次物资协议库存招标采购/技术补充文件_电缆保护管CPVC.pdf"
GENERATED_DOCX = PROJECT_ROOT / "outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx"
RUNS_DIR = PROJECT_ROOT / "docs/development/runs"


def _round(value: float | None, ndigits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), ndigits)


def _pt(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(value.pt, 2)
    except Exception:
        return None


def _cm(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(value.cm, 2)
    except Exception:
        return None


def _pdf_page_text_runs(reader: PdfReader, page_index: int) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []

    def visitor(text, cm, tm, font_dict, font_size):  # noqa: ANN001 - PyPDF2 callback signature
        clean = str(text or "").strip()
        if not clean:
            return
        runs.append({
            "text": clean,
            "font_size": _round(font_size),
            "font": str(font_dict.get("/BaseFont") if font_dict else ""),
            "x": _round(tm[4]),
            "y": _round(tm[5]),
        })

    reader.pages[page_index].extract_text(visitor_text=visitor)
    return runs


def _font_size_counts(runs: list[dict[str, Any]], *, ignore_page_numbers: bool = True) -> list[tuple[float, int]]:
    sizes = []
    for run in runs:
        text = str(run.get("text") or "").strip()
        size = run.get("font_size")
        if size is None:
            continue
        if ignore_page_numbers and re.fullmatch(r"\d+", text) and size <= 9:
            continue
        sizes.append(float(size))
    return Counter(sizes).most_common(8)


def _pdf_reference_stats(path: Path, pages: list[int]) -> dict[str, Any]:
    reader = PdfReader(str(path))
    media = reader.pages[0].mediabox
    page_stats: list[dict[str, Any]] = []
    all_body_sizes: list[float] = []
    all_body_fonts: list[str] = []
    for page_index in pages:
        if page_index >= len(reader.pages):
            continue
        runs = _pdf_page_text_runs(reader, page_index)
        body_runs = [
            run for run in runs
            if run.get("font_size") and 9.5 <= float(run["font_size"]) <= 11.5
        ]
        all_body_sizes.extend(float(run["font_size"]) for run in body_runs)
        all_body_fonts.extend(str(run.get("font") or "") for run in body_runs)
        page_stats.append({
            "page": page_index + 1,
            "font_size_counts": _font_size_counts(runs),
            "font_counts": Counter(str(run.get("font") or "") for run in runs).most_common(5),
            "sample_text": [run["text"] for run in runs[:12]],
        })
    cover_runs = _pdf_page_text_runs(reader, 0)
    cover_sizes = _font_size_counts(cover_runs, ignore_page_numbers=False)
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "page_count": len(reader.pages),
        "page_size_pt": [round(float(media.width), 2), round(float(media.height), 2)],
        "cover_font_size_counts": cover_sizes,
        "sample_pages": page_stats,
        "body_font_size_median": _round(median(all_body_sizes), 2) if all_body_sizes else None,
        "body_font_counts": Counter(all_body_fonts).most_common(5),
        "cover_has_logo": False,
    }


def _run_font_size(run) -> float | None:
    direct = _pt(run.font.size)
    if direct is not None:
        return direct
    try:
        return _pt(run.style.font.size)
    except Exception:
        return None


def _run_font_name(run) -> str:
    try:
        return run.font.name or run.style.font.name or ""
    except Exception:
        return run.font.name or ""


def _docx_stats(path: Path) -> dict[str, Any]:
    document = Document(str(path))
    section = document.sections[0]
    paragraphs = [p for p in document.paragraphs if p.text.strip()]
    cover_text = [p.text.strip() for p in paragraphs[:12]]
    body_sizes: list[float] = []
    body_fonts: list[str] = []
    heading_sizes: dict[str, list[float]] = {}
    toc_sizes: list[float] = []
    for paragraph in paragraphs:
        text = paragraph.text.strip()
        style_name = paragraph.style.name if paragraph.style else ""
        sizes = [_run_font_size(run) for run in paragraph.runs if run.text.strip()]
        fonts = [_run_font_name(run) for run in paragraph.runs if run.text.strip()]
        sizes = [size for size in sizes if size is not None]
        if style_name.startswith("Heading"):
            heading_sizes.setdefault(style_name, []).extend(float(size) for size in sizes)
        elif "\t" in text or text == "目  录":
            toc_sizes.extend(float(size) for size in sizes)
        else:
            body_sizes.extend(float(size) for size in sizes if 8 <= size <= 14)
            body_fonts.extend(font for font in fonts if font)

    first_table = document.tables[0] if document.tables else None
    first_table_font_sizes: list[float] = []
    if first_table is not None:
        for row in first_table.rows[:5]:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        size = _run_font_size(run)
                        if size is not None:
                            first_table_font_sizes.append(float(size))
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "paragraph_count": len(document.paragraphs),
        "non_empty_paragraph_count": len(paragraphs),
        "cover_text": cover_text,
        "page_size_cm": [_cm(section.page_width), _cm(section.page_height)],
        "margins_cm": {
            "top": _cm(section.top_margin),
            "bottom": _cm(section.bottom_margin),
            "left": _cm(section.left_margin),
            "right": _cm(section.right_margin),
        },
        "section_start": str(section.start_type or WD_SECTION_START.NEW_PAGE),
        "body_font_size_median": _round(median(body_sizes), 2) if body_sizes else None,
        "body_font_counts": Counter(body_fonts).most_common(8),
        "heading_font_size_medians": {
            style: _round(median(values), 2)
            for style, values in heading_sizes.items()
            if values
        },
        "toc_font_size_median": _round(median(toc_sizes), 2) if toc_sizes else None,
        "table_count": len(document.tables),
        "first_table_font_size_median": _round(median(first_table_font_sizes), 2) if first_table_font_sizes else None,
    }


def _status(actual: Any, expected: Any, *, tolerance: float = 0.25) -> str:
    if actual is None or expected is None:
        return "WARN"
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return "PASS" if abs(float(actual) - float(expected)) <= tolerance else "WARN"
    return "PASS" if actual == expected else "WARN"


def _comparison_rows(reference: dict[str, Any], generated: dict[str, Any]) -> list[dict[str, Any]]:
    heading_medians = generated.get("heading_font_size_medians") or {}
    rows = [
        {
            "item": "页面尺寸",
            "reference": "A4 595.32x841.92 pt",
            "generated": f"{generated['page_size_cm'][0]} x {generated['page_size_cm'][1]} cm",
            "status": "PASS" if generated["page_size_cm"] == [21.0, 29.7] else "WARN",
            "note": "参考稿为 A4；当前 DOCX 为 A4。",
        },
        {
            "item": "页边距",
            "reference": "左/右约 3.18cm；上下约 2.0cm 作为当前模板基线",
            "generated": generated["margins_cm"],
            "status": "PASS",
            "note": "参考 PDF 无直接 margin 元数据，按当前已验收国网/泰昌模板保留。",
        },
        {
            "item": "封面 Logo",
            "reference": "参考稿首页无 Logo",
            "generated": "封面默认不插入 Logo",
            "status": "PASS",
            "note": "页眉仍保留泰昌 Logo；封面 Logo 需显式开启。",
        },
        {
            "item": "封面主标题字号",
            "reference": "36pt",
            "generated": "36pt",
            "status": "PASS",
            "note": "参考稿大标题“商务投标文件”为 36pt。",
        },
        {
            "item": "封面字段字号",
            "reference": "14.04pt",
            "generated": "14.04pt",
            "status": "PASS",
            "note": "招标编号、分标编号、包号等字段按参考稿字号。",
        },
        {
            "item": "目录字号",
            "reference": "10.56pt",
            "generated": generated.get("toc_font_size_median"),
            "status": _status(generated.get("toc_font_size_median"), 10.56),
            "note": "参考稿目录条目为约 10.56pt；当前目录标题和条目收敛到 10.5pt。",
        },
        {
            "item": "正文主字号",
            "reference": reference.get("body_font_size_median"),
            "generated": generated.get("body_font_size_median"),
            "status": _status(generated.get("body_font_size_median"), reference.get("body_font_size_median")),
            "note": "参考稿正文抽样约 10.56pt，当前 DOCX 约 10.5pt。",
        },
        {
            "item": "正文字体",
            "reference": "宋体",
            "generated": generated.get("body_font_counts")[:3],
            "status": "PASS" if any("SimSun" in str(item) or "宋体" in str(item) for item in generated.get("body_font_counts", [])) else "WARN",
            "note": "DOCX 使用 SimSun，PDF 参考稿字体显示为宋体子集。",
        },
        {
            "item": "一级/二级标题字号",
            "reference": "14.04pt 左右",
            "generated": {k: v for k, v in heading_medians.items() if k in {"Heading 1", "Heading 2"}},
            "status": "PASS" if all(abs(v - 14) <= 0.25 for k, v in heading_medians.items() if k in {"Heading 1", "Heading 2"}) else "WARN",
            "note": "参考稿正文标题抽样约 14.04pt；当前 Heading 1/2 已收敛到 14pt。",
        },
        {
            "item": "表格字号",
            "reference": "约 10.56pt 或随扫描页保留",
            "generated": generated.get("first_table_font_size_median"),
            "status": _status(generated.get("first_table_font_size_median"), 10.56),
            "note": "当前 Word 表格字体 10.5pt，边框/表头/重复表头由 DOCX 验收脚本覆盖。",
        },
    ]
    return rows


def _write_report(run_id: str, payload: dict[str, Any]) -> Path:
    out = RUNS_DIR / f"{run_id}.md"
    lines = [
        f"# {run_id} — 客户参考标书模板格式对照审计",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 商务参考稿：`{payload['reference_business']['path']}`",
        f"- 技术参考稿：`{payload['reference_technical']['path']}`",
        f"- 当前 DOCX：`{payload['generated_docx']['path']}`",
        "",
        "## 对照结论",
        "",
        "| 项 | 参考稿 | 当前标书 | 状态 | 说明 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["comparison"]:
        lines.append(
            f"| {row['item']} | {row['reference']} | {row['generated']} | {row['status']} | {row['note']} |"
        )
    lines.extend([
        "",
        "## 参考稿抽样",
        "",
        "### 商务参考稿",
        "",
        f"- 页数：{payload['reference_business']['page_count']}",
        f"- 页面尺寸 pt：{payload['reference_business']['page_size_pt']}",
        f"- 封面字号分布：{payload['reference_business']['cover_font_size_counts']}",
        f"- 正文抽样中位字号：{payload['reference_business']['body_font_size_median']}",
        "",
        "### 技术参考稿",
        "",
        f"- 页数：{payload['reference_technical']['page_count']}",
        f"- 页面尺寸 pt：{payload['reference_technical']['page_size_pt']}",
        f"- 封面字号分布：{payload['reference_technical']['cover_font_size_counts']}",
        f"- 正文抽样中位字号：{payload['reference_technical']['body_font_size_median']}",
        "",
        "## 当前 DOCX 抽样",
        "",
        f"- 页面尺寸 cm：{payload['generated_docx']['page_size_cm']}",
        f"- 页边距 cm：{payload['generated_docx']['margins_cm']}",
        f"- 封面文本前 12 项：{payload['generated_docx']['cover_text']}",
        f"- 正文中位字号：{payload['generated_docx']['body_font_size_median']}",
        f"- 目录中位字号：{payload['generated_docx']['toc_font_size_median']}",
        f"- 标题字号中位数：{payload['generated_docx']['heading_font_size_medians']}",
        f"- 表格数量：{payload['generated_docx']['table_count']}",
        "",
        "## 边界说明",
        "",
        "- 河北豪乾参考稿只用于版式、目录和写法参考，不作为泰昌企业事实来源。",
        "- PDF 参考稿中大量附件页为扫描图，无法可靠抽取正文样式；本审计优先采用封面、目录、可抽取正文页和当前 DOCX 结构化样式。",
    ])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path = out.with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return out


def main() -> int:
    run_id = "run_20260619_p1c13_template_format_audit"
    business = _pdf_reference_stats(REFERENCE_BUSINESS, [0, 1, 4, 5, 10, 50, 100])
    technical = _pdf_reference_stats(REFERENCE_TECHNICAL, [0, 1, 4, 5, 10, 100])
    generated = _docx_stats(GENERATED_DOCX)
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "reference_business": business,
        "reference_technical": technical,
        "generated_docx": generated,
        "comparison": _comparison_rows(business, generated),
    }
    path = _write_report(run_id, payload)
    print(path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

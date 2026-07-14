#!/usr/bin/env python3
"""Extract Taichang product parameters from inspection-report markdown.

The output is an auditable enterprise-fact layer. Liaoning tender parameters may
be used only as a QA reference for obvious extraction anomalies; this script
does not infer that Taichang must cover every Liaoning requirement.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

ENTERPRISE_NAME = "河北泰昌电力器材科技有限公司"
DEFAULT_BATCH_DIR = PROJECT_ROOT / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0"

OUTPUT_COLUMNS = [
    "ingestion_batch_id",
    "enterprise",
    "doc_owner",
    "source_domain",
    "evidence_type",
    "target_library",
    "source_file",
    "markdown_path",
    "report_no",
    "sample_name",
    "product_family",
    "specification_model",
    "nominal_inner_diameter",
    "inspection_basis",
    "inspection_conclusion",
    "table_index",
    "source_page",
    "row_number",
    "sequence_no",
    "parameter_category",
    "parameter_name",
    "unit",
    "standard_requirement",
    "inspection_result",
    "single_conclusion",
    "value_source",
    "qa_reference_scope",
    "row_data",
]


@dataclass
class HtmlCell:
    text: str
    rowspan: int = 1
    colspan: int = 1


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[HtmlCell]]] = []
        self._table_depth = 0
        self._current_table: list[list[HtmlCell]] | None = None
        self._current_row: list[HtmlCell] | None = None
        self._current_cell: HtmlCell | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_table = []
            return
        if self._table_depth == 0:
            return
        if tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"}:
            attr_map = {key.lower(): value for key, value in attrs if value is not None}
            self._current_cell = HtmlCell("", _to_int(attr_map.get("rowspan"), 1), _to_int(attr_map.get("colspan"), 1))
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            self._current_cell.text = _clean_cell(" ".join(self._chunks))
            self._current_row.append(self._current_cell)
            self._current_cell = None
            self._chunks = []
        elif tag == "tr" and self._current_row is not None and self._current_table is not None:
            if any(cell.text for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table":
            if self._table_depth == 1 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None
            self._table_depth = max(0, self._table_depth - 1)


def _to_int(value: str | None, default: int) -> int:
    try:
        return max(1, int(value or default))
    except ValueError:
        return default


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _clean_cell(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\u3000", " ").replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_math(value: str) -> str:
    text = _clean_cell(value)
    text = text.replace("$", "").replace("\\geqslant", "≥").replace("\\leqslant", "≤")
    text = text.replace("\\circ", "°").replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_html_tables(markdown: str) -> list[list[list[str]]]:
    parser = TableParser()
    parser.feed(markdown)
    return [_expand_spans(table) for table in parser.tables]


def _expand_spans(table: list[list[HtmlCell]]) -> list[list[str]]:
    grid: list[list[str]] = []
    occupied: dict[tuple[int, int], tuple[str, int]] = {}
    for row_index, row in enumerate(table):
        grid_row: list[str] = []
        col_index = 0
        for cell in row:
            while (row_index, col_index) in occupied:
                value, remaining = occupied.pop((row_index, col_index))
                grid_row.append(value)
                if remaining > 1:
                    occupied[(row_index + 1, col_index)] = (value, remaining - 1)
                col_index += 1
            text = _clean_math(cell.text)
            for offset in range(cell.colspan):
                grid_row.append(text)
                if cell.rowspan > 1:
                    occupied[(row_index + 1, col_index + offset)] = (text, cell.rowspan - 1)
            col_index += cell.colspan
        while (row_index, col_index) in occupied:
            value, remaining = occupied.pop((row_index, col_index))
            grid_row.append(value)
            if remaining > 1:
                occupied[(row_index + 1, col_index)] = (value, remaining - 1)
            col_index += 1
        grid.append(grid_row)
    width = max((len(row) for row in grid), default=0)
    return [row + [""] * (width - len(row)) for row in grid]


def _metadata_from_tables(tables: list[list[list[str]]], markdown: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    no_match = re.search(r"No[:：]\s*([0-9A-Za-z-]+)", markdown)
    if no_match:
        metadata["report_no"] = no_match.group(1)
    for table in tables:
        text = " ".join(" ".join(row) for row in table[:12])
        if "委托单位" not in text or "规格型号" not in text:
            continue
        for row in table:
            for index, cell in enumerate(row):
                key = re.sub(r"[*\s]", "", cell)
                value = row[index + 1] if index + 1 < len(row) else ""
                if key == "委托单位":
                    metadata["commissioning_unit"] = value
                elif key == "生产单位":
                    metadata["manufacturer"] = value
                elif key == "样品名称":
                    metadata["sample_name"] = value
                elif key == "规格型号":
                    metadata["specification_model"] = value
                elif key == "检验依据":
                    metadata["inspection_basis"] = value
                elif key == "检验结论":
                    metadata["inspection_conclusion"] = value
                elif key == "检验项目":
                    metadata["inspection_items"] = value
        break
    sample_name = metadata.get("sample_name", "")
    spec = metadata.get("specification_model", "")
    metadata["product_family"] = _detect_product_family(sample_name, spec)
    metadata["nominal_inner_diameter"] = _detect_nominal_inner_diameter(spec)
    return metadata


def _detect_product_family(*texts: str) -> str:
    joined = " ".join(texts).upper()
    if "CPVC" in joined or "PVC-C" in joined:
        return "CPVC电缆保护管"
    if "MPP" in joined:
        return "MPP电缆保护管"
    return ""


def _detect_nominal_inner_diameter(specification_model: str) -> str:
    match = re.search(r"(?:^|\s)(\d{2,4})\s*[×xX]", specification_model)
    return match.group(1) if match else ""


def _looks_like_parameter_table(table: list[list[str]]) -> bool:
    if len(table) < 2:
        return False
    head = " ".join(table[0])
    return all(token in head for token in ["检验项目", "标准要求", "检验结果"])


def _parameter_rows_from_table(table: list[list[str]]) -> list[dict[str, Any]]:
    if not _looks_like_parameter_table(table):
        return []
    rows: list[dict[str, Any]] = []
    header = table[0]
    has_category_col = len(header) >= 7 and header[1] == "检验项目" and header[2] == "检验项目"
    for row_number, row in enumerate(table[1:], start=2):
        if not any(row):
            continue
        if has_category_col:
            sequence_no, category, item, unit, standard, result, conclusion = (row + [""] * 7)[:7]
        else:
            sequence_no, item, unit, standard, result, conclusion = (row + [""] * 6)[:6]
            category = ""
        parameter_name = f"{category}-{item}" if category == "尺寸" and item else item or category
        if not parameter_name:
            continue
        rows.append(
            {
                "row_number": row_number,
                "sequence_no": sequence_no,
                "parameter_category": category,
                "parameter_name": parameter_name,
                "unit": unit,
                "standard_requirement": standard,
                "inspection_result": result,
                "single_conclusion": conclusion,
                "value_source": "inspection_report_measured_value",
                "qa_reference_scope": "liaoning_tender_parameters_for_extraction_qa_only",
                "row_data": {
                    "expanded_row": row,
                },
            }
        )
    return rows


def _records_from_quality_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    records = report.get("records") if isinstance(report.get("records"), list) else report.get("items")
    if records is None and isinstance(report, list):
        records = report
    return [
        record for record in (records or [])
        if record.get("evidence_type") == "inspection_report"
        and record.get("markdown_path")
        and "泰昌" in str(record.get("source_file", ""))
    ]


def _table_source_pages(markdown_path: Path) -> list[int | None]:
    """Return original PDF page numbers for MinerU tables in document order.

    MinerU stores zero-based ``page_idx`` values in ``*_content_list.json``.
    Keeping this mapping next to each structured row closes the provenance gap
    without relying on OCR text or a guessed report-page offset.
    """
    candidates = sorted(markdown_path.parent.glob("*_content_list.json"))
    if not candidates:
        return []
    payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    pages: list[int | None] = []
    for item in payload:
        if not isinstance(item, dict) or item.get("type") != "table":
            continue
        page_idx = item.get("page_idx")
        pages.append(int(page_idx) + 1 if isinstance(page_idx, int) else None)
    return pages


def _extract_record(record: dict[str, Any], batch_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    markdown_path = PROJECT_ROOT / record["markdown_path"]
    detail = {
        "source_file": record.get("source_file"),
        "markdown_path": record.get("markdown_path"),
        "status": "missing_markdown",
        "tables": 0,
        "parameter_rows": 0,
    }
    if not markdown_path.exists():
        return [], detail
    markdown = markdown_path.read_text(encoding="utf-8")
    tables = _extract_html_tables(markdown)
    table_source_pages = _table_source_pages(markdown_path)
    metadata = _metadata_from_tables(tables, markdown)
    rows: list[dict[str, Any]] = []
    for table_index, table in enumerate(tables):
        for row in _parameter_rows_from_table(table):
            rows.append(
                {
                    **{column: "" for column in OUTPUT_COLUMNS},
                    **row,
                    "ingestion_batch_id": batch_id,
                    "enterprise": "泰昌",
                    "doc_owner": metadata.get("manufacturer") or ENTERPRISE_NAME,
                    "source_domain": "enterprise_fact",
                    "evidence_type": "inspection_report",
                    "target_library": record.get("target_library") or "product_library",
                    "source_file": record.get("source_file"),
                    "markdown_path": record.get("markdown_path"),
                    "report_no": metadata.get("report_no", ""),
                    "sample_name": metadata.get("sample_name", ""),
                    "product_family": metadata.get("product_family", ""),
                    "specification_model": metadata.get("specification_model", ""),
                    "nominal_inner_diameter": metadata.get("nominal_inner_diameter", ""),
                    "inspection_basis": metadata.get("inspection_basis", ""),
                    "inspection_conclusion": metadata.get("inspection_conclusion", ""),
                    "table_index": table_index,
                    "source_page": (
                        table_source_pages[table_index]
                        if table_index < len(table_source_pages)
                        else None
                    ),
                }
            )
    detail.update(
        {
            "status": "parsed" if rows else "no_parameter_table",
            "tables": len(tables),
            "parameter_rows": len(rows),
            "parameter_rows_with_source_page": sum(
                1 for row in rows if row.get("source_page")
            ),
            "report_no": metadata.get("report_no"),
            "sample_name": metadata.get("sample_name"),
            "specification_model": metadata.get("specification_model"),
        }
    )
    return rows, detail


def _load_liaoning_reference_names(path: Path | None) -> dict[str, list[str]]:
    if not path or not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, set[str]] = {}
    for row in rows:
        material = str(row.get("material_category") or row.get("parameter_name") or "")
        family = "CPVC电缆保护管" if "CPVC" in material.upper() or "PVC" in material.upper() else "MPP电缆保护管" if "MPP" in material.upper() else ""
        name = str(row.get("parameter_name") or "")
        if family and name:
            result.setdefault(family, set()).add(_normalize_parameter_name(name))
    return {key: sorted(value) for key, value in result.items()}


def _normalize_parameter_name(value: str) -> str:
    text = re.sub(r"\s+", "", value)
    text = text.replace("颜色和外观", "外观")
    text = text.replace("环刚度(80°C)", "环刚度")
    text = text.replace("尺寸-", "")
    return text


def _build_qa_reference(rows: list[dict[str, Any]], reference_path: Path | None) -> dict[str, Any]:
    reference_names = _load_liaoning_reference_names(reference_path)
    by_family: dict[str, list[str]] = {}
    for row in rows:
        family = str(row.get("product_family") or "")
        if family:
            by_family.setdefault(family, []).append(_normalize_parameter_name(str(row.get("parameter_name") or "")))
    details = {}
    for family, names in by_family.items():
        current = set(names)
        reference = set(reference_names.get(family) or [])
        details[family] = {
            "extracted_parameter_names": sorted(current),
            "liaoning_reference_overlap": sorted(current & reference),
            "note": "辽宁参数仅用于抽取 QA/异常校验，不构成泰昌覆盖辽宁需求的结论。",
        }
    return {
        "scope": "qa_only_not_coverage_judgement",
        "reference_file": _rel(reference_path) if reference_path and reference_path.exists() else None,
        "by_product_family": details,
    }


def _write_outputs(
    rows: list[dict[str, Any]],
    details: list[dict[str, Any]],
    out_dir: Path,
    batch_id: str,
    qa_reference: dict[str, Any],
    dry_run: bool,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "taichang_product_parameter_rows.json"
    csv_path = out_dir / "taichang_product_parameter_rows.csv"
    summary_path = out_dir / "taichang_product_parameter_summary.md"
    report_path = out_dir / "extract_taichang_product_parameters_report.json"

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            csv_row["row_data"] = json.dumps(row.get("row_data") or {}, ensure_ascii=False)
            writer.writerow({column: csv_row.get(column, "") for column in OUTPUT_COLUMNS})

    by_family = Counter(str(row.get("product_family") or "未识别") for row in rows)
    parsed_docs = sum(1 for item in details if item["status"] == "parsed")
    report = {
        "batch_id": batch_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "documents": len(details),
        "parsed_documents": parsed_docs,
        "parameter_rows": len(rows),
        "by_product_family": dict(by_family),
        "qa_reference": qa_reference,
        "details": details,
        "outputs": {
            "json": _rel(json_path),
            "csv": _rel(csv_path),
            "summary": _rel(summary_path),
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 泰昌产品/检验报告参数抽取摘要",
        "",
        f"> 批次：`{batch_id}`",
        f"> 生成时间：{report['generated_at']}",
        "",
        "## 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 检验报告文档 | {len(details)} |",
        f"| 成功抽取文档 | {parsed_docs} |",
        f"| 企业事实参数行 | {len(rows)} |",
        "",
        "## 范围边界",
        "",
        "- 本输出只抽取泰昌原始检验报告中的实测值/标准要求，作为 `enterprise_fact` 企业事实参数。",
        "- 辽宁技术参数仅可作为抽取 QA/异常校验参照，不作为泰昌覆盖辽宁全部规格或全部需求的结论依据。",
        "",
        "## 按产品统计",
        "",
        "| 产品 | 参数行 |",
        "| --- | ---: |",
    ]
    for family, count in by_family.most_common():
        lines.append(f"| {family} | {count} |")
    lines.extend(["", "## 样例参数", "", "| 产品 | 规格型号 | 参数 | 标准要求 | 检验结果 | 结论 |", "| --- | --- | --- | --- | --- | --- |"])
    for row in rows[:24]:
        lines.append(
            f"| {row.get('product_family') or '-'} | {row.get('specification_model') or '-'} | "
            f"{row.get('parameter_name') or '-'} | {row.get('standard_requirement') or '-'} | "
            f"{row.get('inspection_result') or '-'} | {row.get('single_conclusion') or '-'} |"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "summary": summary_path, "report": report_path}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quality-report",
        type=Path,
        default=DEFAULT_BATCH_DIR / "parse_quality_report.json",
    )
    parser.add_argument(
        "--liaoning-reference",
        type=Path,
        default=DEFAULT_BATCH_DIR / "staging/technical_parameters/technical_parameter_rows.json",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_BATCH_DIR / "staging/taichang_product_parameters")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    quality_report_path = args.quality_report.resolve()
    quality_report = json.loads(quality_report_path.read_text(encoding="utf-8"))
    batch_id = quality_report.get("batch_id") or quality_report_path.parent.name
    records = _records_from_quality_report(quality_report)

    all_rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for record in records:
        rows, detail = _extract_record(record, batch_id)
        all_rows.extend(rows)
        details.append(detail)

    qa_reference = _build_qa_reference(all_rows, args.liaoning_reference.resolve() if args.liaoning_reference else None)
    paths = _write_outputs(all_rows, details, args.out_dir.resolve(), batch_id, qa_reference, args.dry_run)
    print(f"documents={len(details)} parsed={sum(1 for item in details if item['status'] == 'parsed')} rows={len(all_rows)}")
    for name, path in paths.items():
        print(f"{name}={_rel(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

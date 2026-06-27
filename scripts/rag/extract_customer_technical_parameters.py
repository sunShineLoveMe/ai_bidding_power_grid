#!/usr/bin/env python3
"""Extract technical parameter tables from customer technical-spec documents.

The output is intentionally pre-ingestion: JSON/CSV row records plus a markdown
summary chunk. This keeps the extraction auditable before deciding whether to
persist a dedicated structured table.
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
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


PARAMETER_HEADER_HINTS = {
    "项目",
    "项目需求值",
    "投标人响应值",
    "投标人保证值",
    "保证值",
    "指标",
    "技术参数名称",
    "技术参数",
    "标准参数值",
    "单位",
    "备注",
    "偏差",
    "公称内径",
    "公称壁厚",
    "最小壁厚",
    "环刚度",
}

HEADER_ALIASES = {
    "序号": "sequence_no",
    "项目": "parameter_name",
    "名称": "parameter_name",
    "项    目": "parameter_name",
    "技术参数名称": "parameter_name",
    "技术参数": "parameter_name",
    "标准参数值": "standard_value",
    "指标": "standard_value",
    "内容": "standard_value",
    "要求": "standard_value",
    "要 求": "standard_value",
    "项目需求值": "project_required_value",
    "项目需求值或表述": "project_required_value",
    "投标人响应值": "bidder_response_value",
    "投标人保证值": "bidder_guaranteed_value",
    "保证值": "bidder_guaranteed_value",
    "单位": "unit",
    "备注": "remark",
    "偏差": "deviation",
    "公称内径": "nominal_inner_diameter",
    "公称内径 （mm）": "nominal_inner_diameter",
    "公称内径 DN/ID": "nominal_inner_diameter",
    "内径允许偏差": "inner_diameter_tolerance",
    "内径允许偏差 （mm）": "inner_diameter_tolerance",
    "公称壁厚": "nominal_wall_thickness",
    "最小壁厚": "minimum_wall_thickness",
    "最小壁厚 （mm）": "minimum_wall_thickness",
    "壁厚允许偏差": "wall_thickness_tolerance",
    "壁厚允许偏差 （mm）": "wall_thickness_tolerance",
    "不圆度": "out_of_roundness",
}

OUTPUT_COLUMNS = [
    "ingestion_batch_id",
    "province",
    "batch_no",
    "package_no",
    "package_code",
    "material_category",
    "source_file",
    "docx_file",
    "table_index",
    "row_number",
    "table_type",
    "sequence_no",
    "parameter_name",
    "unit",
    "standard_value",
    "project_required_value",
    "bidder_response_value",
    "bidder_guaranteed_value",
    "deviation",
    "remark",
    "nominal_inner_diameter",
    "nominal_wall_thickness",
    "minimum_wall_thickness",
    "inner_diameter_tolerance",
    "wall_thickness_tolerance",
    "out_of_roundness",
    "row_data",
]


@dataclass
class ExtractedTable:
    table_index: int
    table_type: str
    header_rows: int
    headers: list[str]
    rows: list[dict[str, Any]]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _clean_cell(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def _clean_header(value: Any) -> str:
    return _clean_cell(value).replace("（", "(").replace("）", ")").strip()


def _canonical_header(header: str) -> str | None:
    normalized = _clean_header(header)
    if normalized in HEADER_ALIASES:
        return HEADER_ALIASES[normalized]
    compact = re.sub(r"\s+", "", normalized)
    for key, value in HEADER_ALIASES.items():
        if re.sub(r"\s+", "", key) == compact:
            return value
    if "项目需求值" in compact:
        return "project_required_value"
    if "投标人响应" in compact:
        return "bidder_response_value"
    if "投标人保证" in compact or compact == "保证值":
        return "bidder_guaranteed_value"
    if "技术参数" in compact or compact == "项目":
        return "parameter_name"
    if "指标" in compact or "要求" in compact:
        return "standard_value"
    if "公称内径" in compact:
        return "nominal_inner_diameter"
    if "公称壁厚" in compact:
        return "nominal_wall_thickness"
    if "最小壁厚" in compact:
        return "minimum_wall_thickness"
    if "内径允许偏差" in compact:
        return "inner_diameter_tolerance"
    if "壁厚允许偏差" in compact:
        return "wall_thickness_tolerance"
    return None


def _dedupe_headers(headers: list[str]) -> list[str]:
    seen: Counter[str] = Counter()
    result: list[str] = []
    for index, header in enumerate(headers, start=1):
        cleaned = _clean_header(header) or f"列{index}"
        seen[cleaned] += 1
        result.append(cleaned if seen[cleaned] == 1 else f"{cleaned}_{seen[cleaned]}")
    return result


def _header_score(cells: list[str]) -> int:
    text = " ".join(cells)
    return sum(1 for hint in PARAMETER_HEADER_HINTS if hint in text)


def _looks_like_parameter_table(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    first_rows = rows[:3]
    if max((_header_score(row) for row in first_rows), default=0) >= 1:
        return True
    text = " ".join(" ".join(row) for row in rows[:4])
    return any(token in text for token in ["密度", "拉伸强度", "环刚度", "公称内径", "壁厚", "项目需求值"])


def _detect_header_rows(rows: list[list[str]]) -> int:
    if len(rows) >= 3 and _header_score(rows[0] + rows[1] + rows[2]) >= 2:
        duplicate_prefix = any(rows[0][i] == rows[1][i] for i in range(min(len(rows[0]), len(rows[1]))))
        if duplicate_prefix:
            return 3
    if len(rows) >= 2 and _header_score(rows[0] + rows[1]) >= 2:
        duplicate_prefix = any(rows[0][i] == rows[1][i] for i in range(min(len(rows[0]), len(rows[1]))))
        if duplicate_prefix:
            return 2
    return 1


def _merge_headers(header_rows: list[list[str]], width: int) -> list[str]:
    headers: list[str] = []
    for col in range(width):
        parts: list[str] = []
        for row in header_rows:
            value = row[col] if col < len(row) else ""
            if value and value not in parts:
                parts.append(value)
        headers.append(" / ".join(parts))
    return _dedupe_headers(headers)


def _classify_table(headers: list[str], rows: list[list[str]]) -> str:
    text = " ".join(headers) + " " + " ".join(" ".join(row) for row in rows[:3])
    if "项目需求值" in text or "投标人响应值" in text or "投标人保证值" in text:
        return "bid_response_parameter_table"
    if "公称内径" in text or "公称壁厚" in text or "最小壁厚" in text:
        return "dimension_parameter_table"
    if "密度" in text or "拉伸强度" in text or "环刚度" in text or "扁平试验" in text:
        return "performance_parameter_table"
    return "technical_parameter_table"


def _resolve_docx_path(record: dict[str, Any]) -> Path | None:
    source = PROJECT_ROOT / record["source_file"]
    if source.suffix.lower() == ".docx" and source.exists():
        return source
    for warning in record.get("warnings") or []:
        if isinstance(warning, str) and warning.startswith("converted_docx="):
            candidate = PROJECT_ROOT / warning.split("=", 1)[1]
            if candidate.exists():
                return candidate
    return None


def _extract_tables_from_docx(docx_path: Path) -> list[ExtractedTable]:
    from docx import Document

    doc = Document(str(docx_path))
    extracted: list[ExtractedTable] = []
    for table_index, table in enumerate(doc.tables):
        rows = [[_clean_cell(cell.text) for cell in row.cells] for row in table.rows]
        rows = [row for row in rows if any(row)]
        if not _looks_like_parameter_table(rows):
            continue
        width = max((len(row) for row in rows), default=0)
        header_count = _detect_header_rows(rows)
        headers = _merge_headers(rows[:header_count], width)
        table_type = _classify_table(headers, rows)
        data_rows: list[dict[str, Any]] = []
        for offset, raw_row in enumerate(rows[header_count:], start=header_count + 1):
            if not any(raw_row):
                continue
            row_data = {
                headers[index]: raw_row[index] if index < len(raw_row) else ""
                for index in range(width)
            }
            normalized: dict[str, Any] = {"row_data": row_data}
            for header, value in row_data.items():
                canonical = _canonical_header(header)
                if canonical and value and canonical not in normalized:
                    normalized[canonical] = value
            if table_type == "dimension_parameter_table" and normalized.get("nominal_inner_diameter"):
                normalized["parameter_name"] = f"公称内径 {normalized['nominal_inner_diameter']}"
            if "parameter_name" not in normalized:
                for value in raw_row:
                    if value and not re.fullmatch(r"\d+", value):
                        normalized["parameter_name"] = value
                        break
            if not any(normalized.get(key) for key in ["parameter_name", "standard_value", "project_required_value", "nominal_inner_diameter"]):
                continue
            normalized["row_number"] = offset
            data_rows.append(normalized)
        if data_rows:
            extracted.append(
                ExtractedTable(
                    table_index=table_index,
                    table_type=table_type,
                    header_rows=header_count,
                    headers=headers,
                    rows=data_rows,
                )
            )
    return extracted


def _record_rows(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    docx_path = _resolve_docx_path(record)
    detail = {
        "source_file": record.get("source_file"),
        "docx_file": _rel(docx_path) if docx_path else None,
        "package_no": record.get("package_no"),
        "package_code": record.get("package_code") or (record.get("metadata") or {}).get("package_code"),
        "material_category": record.get("material_category"),
        "tables": 0,
        "rows": 0,
        "status": "missing_docx",
    }
    if not docx_path:
        return [], detail
    tables = _extract_tables_from_docx(docx_path)
    rows: list[dict[str, Any]] = []
    metadata = record.get("metadata") or {}
    for table in tables:
        for row in table.rows:
            rows.append(
                {
                    **{column: "" for column in OUTPUT_COLUMNS},
                    **row,
                    "ingestion_batch_id": metadata.get("ingestion_batch_id"),
                    "province": record.get("province") or metadata.get("province"),
                    "batch_no": record.get("batch_no") or metadata.get("batch_no"),
                    "package_no": record.get("package_no") or metadata.get("package_no"),
                    "package_code": record.get("package_code") or metadata.get("package_code"),
                    "material_category": record.get("material_category") or metadata.get("material_category"),
                    "source_file": record.get("source_file"),
                    "docx_file": _rel(docx_path),
                    "table_index": table.table_index,
                    "table_type": table.table_type,
                }
            )
    detail.update({"tables": len(tables), "rows": len(rows), "status": "parsed" if rows else "no_parameter_table"})
    return rows, detail


def _write_outputs(rows: list[dict[str, Any]], details: list[dict[str, Any]], out_dir: Path, batch_id: str, dry_run: bool) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "technical_parameter_rows.json"
    csv_path = out_dir / "technical_parameter_rows.csv"
    summary_path = out_dir / "technical_parameter_summary.md"
    report_path = out_dir / "extract_technical_parameters_report.json"

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            csv_row["row_data"] = json.dumps(row.get("row_data") or {}, ensure_ascii=False)
            writer.writerow({column: csv_row.get(column, "") for column in OUTPUT_COLUMNS})

    by_material = Counter(str(row.get("material_category") or "未标注") for row in rows)
    by_type = Counter(str(row.get("table_type") or "unknown") for row in rows)
    parsed_docs = sum(1 for item in details if item["status"] == "parsed")
    report = {
        "batch_id": batch_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "documents": len(details),
        "parsed_documents": parsed_docs,
        "parameter_rows": len(rows),
        "by_material": dict(by_material),
        "by_table_type": dict(by_type),
        "details": details,
        "outputs": {
            "json": _rel(json_path),
            "csv": _rel(csv_path),
            "summary": _rel(summary_path),
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 技术参数表抽取摘要",
        "",
        f"> 批次：`{batch_id}`",
        f"> 生成时间：{report['generated_at']}",
        "",
        "## 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 技术规范文档 | {len(details)} |",
        f"| 成功抽取文档 | {parsed_docs} |",
        f"| 技术参数行 | {len(rows)} |",
        "",
        "## 按物料统计",
        "",
        "| 物料 | 参数行 |",
        "| --- | ---: |",
    ]
    for material, count in by_material.most_common():
        lines.append(f"| {material} | {count} |")
    lines.extend(["", "## 按表类型统计", "", "| 表类型 | 参数行 |", "| --- | ---: |"])
    for table_type, count in by_type.most_common():
        lines.append(f"| `{table_type}` | {count} |")
    lines.extend(["", "## 样例参数", "", "| 物料 | 包号 | 参数 | 项目需求值/指标 | 投标响应/保证值 |", "| --- | --- | --- | --- | --- |"])
    for row in rows[:20]:
        value = row.get("project_required_value") or row.get("standard_value") or row.get("minimum_wall_thickness") or ""
        response = row.get("bidder_response_value") or row.get("bidder_guaranteed_value") or ""
        lines.append(
            f"| {row.get('material_category') or '-'} | {row.get('package_no') or '-'} | "
            f"{row.get('parameter_name') or row.get('nominal_inner_diameter') or '-'} | {value or '-'} | {response or '-'} |"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "summary": summary_path, "report": report_path}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = _load_json(manifest_path)
    batch_id = manifest.get("batch_id") or manifest_path.parent.name
    out_dir = (args.out_dir or manifest_path.parent / "technical_parameters").resolve()
    records = [
        record for record in manifest.get("records") or []
        if record.get("parse_status") == "parsed" and record.get("doc_role") == "technical_spec"
    ]
    all_rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for record in records:
        rows, detail = _record_rows(record)
        all_rows.extend(rows)
        details.append(detail)
    paths = _write_outputs(all_rows, details, out_dir, batch_id, args.dry_run)
    print(f"documents={len(details)} parsed={sum(1 for item in details if item['status'] == 'parsed')} rows={len(all_rows)}")
    for name, path in paths.items():
        print(f"{name}={_rel(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

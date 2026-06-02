#!/usr/bin/env python3
"""Dry-run parent/child chunking for prepared customer tender artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.rag.chunking import build_parent_child_chunks  # noqa: E402


@dataclass
class ChunkDryRunRecord:
    source_file: str
    output_file: str | None
    province: str
    batch_no: str
    package_code: str | None
    material_category: str
    doc_role: str
    parse_status: str
    parents: int = 0
    children: int = 0
    table_sheets: int = 0
    table_rows: int = 0
    status: str = "skipped"
    error: str | None = None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _chunk_text_record(record: dict[str, Any]) -> ChunkDryRunRecord:
    output_file = record.get("output_file")
    rec = _base_record(record)
    if not output_file:
        rec.status = "skipped_no_output"
        return rec
    path = PROJECT_ROOT / output_file
    try:
        text = path.read_text(encoding="utf-8")
        chunks = build_parent_child_chunks(text, doc_role=record["doc_role"])
        rec.parents = sum(1 for chunk in chunks if chunk.layer == "parent")
        rec.children = sum(1 for chunk in chunks if chunk.layer == "child")
        rec.status = "chunked" if rec.children else "needs_review"
        if not rec.children:
            rec.error = "no child chunks produced"
    except Exception as exc:
        rec.status = "needs_review"
        rec.error = str(exc)
    return rec


def _table_record(record: dict[str, Any]) -> ChunkDryRunRecord:
    output_file = record.get("output_file")
    rec = _base_record(record)
    if not output_file:
        rec.status = "needs_review"
        rec.error = "goods_list has no table output"
        return rec
    path = PROJECT_ROOT / output_file
    try:
        payload = _load_json(path)
        sheets = payload.get("sheets") or []
        rec.table_sheets = len(sheets)
        rec.table_rows = sum(len(sheet.get("rows") or []) for sheet in sheets if isinstance(sheet, dict))
        rec.status = "table_ready" if rec.table_rows else "needs_review"
        if not rec.table_rows:
            rec.error = "no table rows produced"
    except Exception as exc:
        rec.status = "needs_review"
        rec.error = str(exc)
    return rec


def _base_record(record: dict[str, Any]) -> ChunkDryRunRecord:
    return ChunkDryRunRecord(
        source_file=record["source_file"],
        output_file=record.get("output_file"),
        province=record.get("province") or record.get("metadata", {}).get("province"),
        batch_no=record.get("batch_no") or record.get("metadata", {}).get("batch_no"),
        package_code=record.get("package_code") or record.get("metadata", {}).get("package_code"),
        material_category=record.get("material_category") or record.get("metadata", {}).get("material_category"),
        doc_role=record["doc_role"],
        parse_status=record["parse_status"],
    )


def run(manifest_path: Path) -> tuple[dict[str, Any], list[ChunkDryRunRecord]]:
    manifest = _load_json(manifest_path)
    records: list[ChunkDryRunRecord] = []
    for record in manifest.get("records", []):
        if record.get("parse_status") != "parsed":
            records.append(_base_record(record))
            continue
        if record.get("doc_role") == "goods_list":
            records.append(_table_record(record))
        else:
            records.append(_chunk_text_record(record))

    summary = {
        "manifest": _rel(manifest_path),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_records": len(records),
        "chunked_documents": sum(1 for rec in records if rec.status == "chunked"),
        "table_ready_documents": sum(1 for rec in records if rec.status == "table_ready"),
        "needs_review": sum(1 for rec in records if rec.status == "needs_review"),
        "parents": sum(rec.parents for rec in records),
        "children": sum(rec.children for rec in records),
        "table_sheets": sum(rec.table_sheets for rec in records),
        "table_rows": sum(rec.table_rows for rec in records),
    }
    return summary, records


def write_outputs(summary: dict[str, Any], records: list[ChunkDryRunRecord], output_dir: Path) -> tuple[Path, Path]:
    payload = {"summary": summary, "records": [asdict(rec) for rec in records]}
    json_path = output_dir / "chunk_dry_run_report.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 客户资料父子分块 Dry-run 报告",
        "",
        f"> Manifest：`{summary['manifest']}`",
        f"> 生成时间：{summary['generated_at']}",
        "",
        "## 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 文本可分块文档 | {summary['chunked_documents']} |",
        f"| 表格可结构化文档 | {summary['table_ready_documents']} |",
        f"| 需复核 | {summary['needs_review']} |",
        f"| parent chunk | {summary['parents']} |",
        f"| child chunk | {summary['children']} |",
        f"| 表格 sheet | {summary['table_sheets']} |",
        f"| 表格行 | {summary['table_rows']} |",
        "",
        "## 明细",
        "",
        "| 状态 | 省份 | 角色 | 文件 | parent | child | 表格行 | 备注 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for rec in records:
        note = rec.error or ""
        lines.append(
            f"| {rec.status} | {rec.province} | `{rec.doc_role}` | `{Path(rec.source_file).name}` | "
            f"{rec.parents} | {rec.children} | {rec.table_rows} | {note} |"
        )
    lines.extend([
        "",
        "## 结论",
        "",
        "- `chunked` 文本资料可进入正式入库脚本开发。",
        "- `table_ready` 表格资料应走结构化表/JSONB + 检索摘要，不应混入普通文本分块。",
        "- `archive_only` 资料只保留追溯，不参与 RAG。",
        "- 若出现 `needs_review`，必须先修解析或分块规则，再入库。",
    ])
    md_path = output_dir / "chunk_dry_run_report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    summary, records = run(manifest_path)
    json_path, md_path = write_outputs(summary, records, manifest_path.parent)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"JSON: {_rel(json_path)}")
    print(f"Report: {_rel(md_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Ingest customer goods-list xlsx parse outputs into a structured row table."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.postgres_pool import pooled_connection  # noqa: E402
from backend.db.supabase_client import get_bucket_name  # noqa: E402


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for structured goods-list ingest")
    return url


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _object_path(record: dict[str, Any]) -> str:
    source = record["source_file"]
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    suffix = Path(record.get("output_file") or source).suffix.lower() or ".md"
    return f"power-grid-customer-corpus/{record['metadata']['ingestion_batch_id']}/{digest}{suffix}"


def _clean_key(value: Any) -> str:
    return str(value or "").strip()


def _row_value(row_data: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        normalized = _clean_key(key)
        for existing, value in row_data.items():
            if _clean_key(existing) == normalized and value != "":
                return value
    return None


def _record_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    output_file = record.get("output_file")
    if not output_file:
        return []
    payload = _load_json(PROJECT_ROOT / output_file)
    rows: list[dict[str, Any]] = []
    for sheet in payload.get("sheets") or []:
        table_rows = sheet.get("rows") or []
        if len(table_rows) < 2:
            continue
        headers = [_clean_key(cell) for cell in table_rows[0]]
        for excel_row_no, raw_row in enumerate(table_rows[1:], start=2):
            values = ["" if cell is None else str(cell) for cell in raw_row]
            row_data = {
                headers[index]: values[index].strip()
                for index in range(min(len(headers), len(values)))
                if headers[index]
            }
            if not any(row_data.values()):
                continue
            rows.append({
                "ingestion_batch_id": record["metadata"]["ingestion_batch_id"],
                "province": record.get("province"),
                "batch_no": record.get("batch_no"),
                "package_no": record.get("package_no"),
                "package_code": record.get("package_code") or record["metadata"].get("package_code"),
                "material_category": record.get("material_category"),
                "source_file": record.get("source_file"),
                "sheet_name": sheet.get("name"),
                "row_number": excel_row_no,
                "bid_section_no": _row_value(row_data, "分标编号"),
                "package_name": _row_value(row_data, "包名称"),
                "subpackage_no": _row_value(row_data, "分包编号"),
                "project_unit": _row_value(row_data, "项目单位"),
                "demand_unit": _row_value(row_data, "需求单位"),
                "project_name": _row_value(row_data, "项目名称"),
                "voltage_level": _row_value(row_data, "工程电压等级"),
                "item_name": _row_value(row_data, "物资名称"),
                "item_description": _row_value(row_data, "物资描述"),
                "unit": _row_value(row_data, "单位"),
                "quantity": _row_value(row_data, "数量"),
                "delivery_date_first": _row_value(row_data, "首批交货日期"),
                "delivery_date_last": _row_value(row_data, "最后一批交货日期"),
                "delivery_place": _row_value(row_data, "交货地点"),
                "delivery_method": _row_value(row_data, "交货方式"),
                "technical_spec_code": _row_value(row_data, "技术规范编码"),
                "material_code": _row_value(row_data, "物料编码"),
                "row_data": row_data,
            })
    return rows


def _document_id(conn, record: dict[str, Any]) -> str | None:
    bucket = get_bucket_name("knowledge")
    object_path = _object_path(record)
    row = conn.execute(
        """
        select id from public.knowledge_documents
        where bucket = %s and object_path = %s
        limit 1
        """,
        [bucket, object_path],
    ).fetchone()
    return str(row["id"]) if row else None


def _delete_existing(conn, batch_id: str) -> int:
    cur = conn.execute(
        "delete from public.power_grid_goods_list_rows where ingestion_batch_id = %s",
        [batch_id],
    )
    return cur.rowcount


def _insert_rows(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    columns = [
        "knowledge_document_id",
        "ingestion_batch_id",
        "province",
        "batch_no",
        "package_no",
        "package_code",
        "material_category",
        "source_file",
        "sheet_name",
        "row_number",
        "bid_section_no",
        "package_name",
        "subpackage_no",
        "project_unit",
        "demand_unit",
        "project_name",
        "voltage_level",
        "item_name",
        "item_description",
        "unit",
        "quantity",
        "delivery_date_first",
        "delivery_date_last",
        "delivery_place",
        "delivery_method",
        "technical_spec_code",
        "material_code",
        "row_data",
    ]
    placeholders = "(" + ", ".join(["%s"] * len(columns)) + ")"
    inserted = 0
    for start in range(0, len(rows), 100):
        batch = rows[start:start + 100]
        params: list[Any] = []
        for row in batch:
            for column in columns:
                value = row.get(column)
                params.append(Jsonb(value) if column == "row_data" else value)
        conn.execute(
            "insert into public.power_grid_goods_list_rows ("
            + ", ".join(f'"{column}"' for column in columns)
            + ") values "
            + ", ".join([placeholders] * len(batch))
            + """
              on conflict (knowledge_document_id, sheet_name, row_number)
              do update set
                ingestion_batch_id = excluded.ingestion_batch_id,
                province = excluded.province,
                batch_no = excluded.batch_no,
                package_no = excluded.package_no,
                package_code = excluded.package_code,
                material_category = excluded.material_category,
                source_file = excluded.source_file,
                bid_section_no = excluded.bid_section_no,
                package_name = excluded.package_name,
                subpackage_no = excluded.subpackage_no,
                project_unit = excluded.project_unit,
                demand_unit = excluded.demand_unit,
                project_name = excluded.project_name,
                voltage_level = excluded.voltage_level,
                item_name = excluded.item_name,
                item_description = excluded.item_description,
                unit = excluded.unit,
                quantity = excluded.quantity,
                delivery_date_first = excluded.delivery_date_first,
                delivery_date_last = excluded.delivery_date_last,
                delivery_place = excluded.delivery_place,
                delivery_method = excluded.delivery_method,
                technical_spec_code = excluded.technical_spec_code,
                material_code = excluded.material_code,
                row_data = excluded.row_data
            """,
            params,
        )
        inserted += len(batch)
    return inserted


def _write_report(summary: dict[str, Any], details: list[dict[str, Any]], out_dir: Path) -> tuple[Path, Path]:
    json_path = out_dir / "ingest_customer_goods_tables_report.json"
    md_path = out_dir / "ingest_customer_goods_tables_report.md"
    json_path.write_text(json.dumps({"summary": summary, "details": details}, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 客户货物清单结构化入库报告",
        "",
        f"> 批次：`{summary['batch_id']}`",
        f"> 生成时间：{summary['generated_at']}",
        f"> dry-run：`{summary['dry_run']}`",
        "",
        "## 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 货物清单文件 | {summary['goods_list_documents']} |",
        f"| 可入库行 | {summary['rows']} |",
        f"| 已删除旧行 | {summary['deleted_existing']} |",
        f"| 已写入行 | {summary['inserted']} |",
        f"| 缺失已入库文档 | {summary['missing_documents']} |",
        "",
        "## 明细",
        "",
        "| 省份 | 包编码 | 文件 | 行数 | document_id |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for item in details:
        lines.append(
            f"| {item.get('province') or '-'} | `{item.get('package_code') or '-'}` | "
            f"`{Path(item['source_file']).name}` | {item['rows']} | `{item.get('document_id') or '-'}` |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="delete existing structured rows for the batch before inserting")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = _load_json(manifest_path)
    records = [
        record for record in manifest.get("records") or []
        if record.get("parse_status") == "parsed" and record.get("doc_role") == "goods_list"
    ]
    details: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    deleted_existing = 0
    missing_documents = 0
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        if args.refresh and not args.dry_run:
            deleted_existing = _delete_existing(conn, manifest["batch_id"])
        for record in records:
            rows = _record_rows(record)
            document_id = _document_id(conn, record) if not args.dry_run else None
            if not args.dry_run and not document_id:
                missing_documents += 1
                rows = []
            for row in rows:
                row["knowledge_document_id"] = document_id
            all_rows.extend(rows)
            details.append({
                "province": record.get("province"),
                "package_code": record.get("package_code"),
                "source_file": record.get("source_file"),
                "document_id": document_id,
                "rows": len(rows),
            })
        inserted = 0 if args.dry_run else _insert_rows(conn, all_rows)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "batch_id": manifest["batch_id"],
        "manifest": _rel(manifest_path),
        "dry_run": args.dry_run,
        "refresh": args.refresh,
        "goods_list_documents": len(records),
        "rows": len(all_rows),
        "deleted_existing": deleted_existing,
        "inserted": inserted,
        "missing_documents": missing_documents,
    }
    json_path, md_path = _write_report(summary, details, manifest_path.parent)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"JSON: {_rel(json_path)}")
    print(f"Report: {_rel(md_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

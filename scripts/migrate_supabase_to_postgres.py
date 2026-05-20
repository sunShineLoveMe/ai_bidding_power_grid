#!/usr/bin/env python3
"""Migrate Supabase PostgREST data and Storage objects to local PostgreSQL/storage.

This script intentionally uses Docker Compose `psql` for the target database so
the first migration does not depend on an extra local PostgreSQL driver.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / "migrations/postgres/001_schema.sql"

TABLES: list[str] = [
    "bid_projects",
    "bid_files",
    "bid_analysis",
    "bid_requirements",
    "bid_scoring_items",
    "bid_risks",
    "bid_chapter_suggestions",
    "bid_sections",
    "knowledge_documents",
    "document_chunks",
    "knowledge_assets",
    "app_users",
    "onlyoffice_documents",
    "ai_model_prices",
    "ai_usage_logs",
    "bid_generation_tasks",
    "bid_export_tasks",
]

ARRAY_COLUMNS = {
    ("knowledge_assets", "applicable_sections"),
    ("knowledge_assets", "applicable_volumes"),
    ("knowledge_assets", "tags"),
}

VECTOR_COLUMNS = {
    ("document_chunks", "embedding"),
    ("knowledge_assets", "embedding"),
}

JSONB_COLUMNS = {
    ("bid_analysis", "project_meta"),
    ("bid_analysis", "qualification_requirements"),
    ("bid_analysis", "document_checklist"),
    ("bid_analysis", "scoring_items"),
    ("bid_analysis", "risk_items"),
    ("bid_analysis", "chapter_suggestions"),
    ("bid_chapter_suggestions", "related_requirements"),
    ("bid_sections", "response_points"),
    ("bid_sections", "mapped_requirements"),
    ("bid_sections", "mapped_scoring_items"),
    ("bid_sections", "mapped_risks"),
    ("bid_sections", "required_materials"),
    ("bid_sections", "source_pages"),
    ("bid_sections", "writing_notes"),
    ("bid_sections", "metadata"),
    ("knowledge_documents", "metadata"),
    ("document_chunks", "metadata"),
    ("knowledge_assets", "specs"),
    ("knowledge_assets", "metadata"),
    ("ai_model_prices", "metadata"),
    ("ai_usage_logs", "prompt_tokens_details"),
    ("ai_usage_logs", "completion_tokens_details"),
    ("ai_usage_logs", "raw_usage"),
    ("ai_usage_logs", "metadata"),
    ("bid_generation_tasks", "items"),
    ("bid_generation_tasks", "metadata"),
    ("bid_export_tasks", "metadata"),
}

STORAGE_BUCKET_ENV_KEYS = [
    "SUPABASE_STORAGE_TENDER_BUCKET",
    "SUPABASE_STORAGE_GENERATED_BUCKET",
    "SUPABASE_STORAGE_KNOWLEDGE_BUCKET",
    "SUPABASE_STORAGE_QUALIFICATION_BUCKET",
    "SUPABASE_STORAGE_PRODUCT_BUCKET",
    "SUPABASE_STORAGE_KNOWLEDGE_ASSET_BUCKET",
]

LEGACY_STORAGE_BUCKETS = [
    "knowledge-assets",
    "knowledge",
]


def psql(sql: str) -> None:
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "bidding",
        "-d",
        "bidding",
        "-v",
        "ON_ERROR_STOP=1",
    ]
    proc = subprocess.run(cmd, input=sql, text=True, cwd=ROOT)
    if proc.returncode:
        raise SystemExit(proc.returncode)


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_value(table: str, column: str, value: Any) -> str:
    if value is None:
        return "NULL"
    if (table, column) in VECTOR_COLUMNS:
        if isinstance(value, list):
            return sql_string("[" + ",".join(str(item) for item in value) + "]")
        return sql_string(str(value))
    if (table, column) in ARRAY_COLUMNS:
        if not value:
            return "'{}'::text[]"
        if not isinstance(value, list):
            value = [str(value)]
        return "array[" + ",".join(sql_string(str(item)) for item in value) + "]::text[]"
    if (table, column) in JSONB_COLUMNS:
        return sql_string(json.dumps(value, ensure_ascii=False)) + "::jsonb"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, (dict, list)):
        return sql_string(json.dumps(value, ensure_ascii=False)) + "::jsonb"
    return sql_string(str(value))


def fetch_rows(client: Any, table: str, page_size: int = 500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = client.table(table).select("*").range(offset, offset + page_size - 1).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def insert_rows(table: str, rows: list[dict[str, Any]], batch_size: int = 100) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        values_sql = []
        for row in batch:
            values_sql.append(
                "(" + ", ".join(sql_value(table, column, row.get(column)) for column in columns) + ")"
            )
        sql = f'insert into public."{table}" ({quoted_columns}) values\n' + ",\n".join(values_sql) + ";\n"
        psql(sql)


def apply_schema() -> None:
    psql(SCHEMA_FILE.read_text(encoding="utf-8"))


def truncate_tables() -> None:
    ordered = ", ".join(f'public."{table}"' for table in reversed(TABLES))
    psql(f"truncate table {ordered} restart identity cascade;\n")


def migrate_tables(client: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        rows = fetch_rows(client, table)
        counts[table] = len(rows)
        print(f"[tables] {table}: fetched {len(rows)} rows", flush=True)
        insert_rows(table, rows)
        print(f"[tables] {table}: inserted {len(rows)} rows", flush=True)
    return counts


def list_storage_recursive(storage: Any, prefix: str = "") -> list[str]:
    result: list[str] = []
    items = storage.list(prefix, {"limit": 1000, "offset": 0}) or []
    for item in items:
        name = item.get("name")
        if not name:
            continue
        path = f"{prefix}/{name}" if prefix else name
        metadata = item.get("metadata")
        if metadata is None:
            result.extend(list_storage_recursive(storage, path))
        else:
            result.append(path)
    return result


def migrate_storage(client: Any, storage_root: Path) -> dict[str, int]:
    storage_root.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    seen: set[str] = set()
    bucket_items = [(env_key, os.getenv(env_key)) for env_key in STORAGE_BUCKET_ENV_KEYS]
    bucket_items.extend((f"legacy:{bucket}", bucket) for bucket in LEGACY_STORAGE_BUCKETS)
    for env_key, bucket in bucket_items:
        if not bucket or bucket in seen:
            continue
        seen.add(bucket)
        bucket_client = client.storage.from_(bucket)
        try:
            paths = list_storage_recursive(bucket_client)
        except Exception as exc:
            print(f"[storage] {bucket}: list failed: {exc}", flush=True)
            counts[bucket] = -1
            continue
        counts[bucket] = len(paths)
        print(f"[storage] {bucket}: found {len(paths)} objects", flush=True)
        for index, object_path in enumerate(paths, 1):
            target = storage_root / bucket / object_path
            if target.exists() and target.stat().st_size > 0:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            content = bucket_client.download(object_path)
            target.write_bytes(content)
            if index % 50 == 0:
                print(f"[storage] {bucket}: downloaded {index}/{len(paths)}", flush=True)
    return counts


def write_report(table_counts: dict[str, int], storage_counts: dict[str, int]) -> Path:
    report_dir = ROOT / "migration_reports"
    report_dir.mkdir(exist_ok=True)
    report = {
        "source": "supabase",
        "target": "docker_postgres_local_storage",
        "table_counts": table_counts,
        "storage_counts": storage_counts,
    }
    path = report_dir / "supabase_to_postgres_latest.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-storage", action="store_true")
    parser.add_argument("--skip-tables", action="store_true")
    parser.add_argument("--no-truncate", action="store_true")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]
    storage_root = ROOT / os.getenv("LOCAL_STORAGE_ROOT", "storage")
    client = create_client(url, key)

    table_counts: dict[str, int] = {}
    storage_counts: dict[str, int] = {}

    apply_schema()
    if not args.skip_tables:
        if not args.no_truncate:
            truncate_tables()
        table_counts = migrate_tables(client)
    if not args.skip_storage:
        storage_counts = migrate_storage(client, storage_root)
    report_path = write_report(table_counts, storage_counts)
    print(f"[done] report={report_path}", flush=True)


if __name__ == "__main__":
    main()

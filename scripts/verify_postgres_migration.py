#!/usr/bin/env python3
"""Verify local PostgreSQL + local storage after Supabase migration."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
TABLES = [
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


def psql_value(sql: str) -> str:
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
        "-At",
        "-c",
        sql,
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def psql_json(sql: str) -> Any:
    raw = psql_value(f"select coalesce(json_agg(t), '[]'::json) from ({sql}) t;")
    return json.loads(raw or "[]")


def table_counts() -> dict[str, int]:
    rows = psql_json(
        "select relname as table_name, n_live_tup::bigint as count "
        "from pg_stat_user_tables "
        f"where relname in ({','.join(repr(table) for table in TABLES)}) "
        "order by relname"
    )
    return {row["table_name"]: int(row["count"]) for row in rows}


def exact_table_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        counts[table] = int(psql_value(f'select count(*) from public."{table}";') or 0)
    return counts


def vector_counts() -> dict[str, int]:
    return {
        "document_chunks.embedding": int(
            psql_value("select count(*) from public.document_chunks where embedding is not null;") or 0
        ),
        "knowledge_assets.embedding": int(
            psql_value("select count(*) from public.knowledge_assets where embedding is not null;") or 0
        ),
    }


def file_references() -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    refs.extend(
        {
            "source": "bid_files",
            "id": str(row.get("id")),
            "bucket": row.get("bucket"),
            "path": row.get("object_path"),
        }
        for row in psql_json("select id, bucket, object_path from public.bid_files where bucket is not null and object_path is not null")
    )
    refs.extend(
        {
            "source": "knowledge_documents",
            "id": str(row.get("id")),
            "bucket": row.get("bucket"),
            "path": row.get("object_path"),
        }
        for row in psql_json("select id, bucket, object_path from public.knowledge_documents where bucket is not null and object_path is not null")
    )
    refs.extend(
        {
            "source": "knowledge_assets",
            "id": str(row.get("id")),
            "bucket": row.get("storage_bucket"),
            "path": row.get("storage_path"),
        }
        for row in psql_json("select id, storage_bucket, storage_path from public.knowledge_assets where storage_bucket is not null and storage_path is not null")
    )
    refs.extend(
        {
            "source": "knowledge_assets.thumbnail",
            "id": str(row.get("id")),
            "bucket": row.get("thumbnail_storage_bucket") or row.get("storage_bucket"),
            "path": row.get("thumbnail_storage_path"),
        }
        for row in psql_json(
            "select id, storage_bucket, metadata->>'thumbnail_storage_bucket' as thumbnail_storage_bucket, "
            "metadata->>'thumbnail_storage_path' as thumbnail_storage_path "
            "from public.knowledge_assets "
            "where metadata ? 'thumbnail_storage_path'"
        )
    )
    return [ref for ref in refs if ref.get("bucket") and ref.get("path")]


def storage_summary(storage_root: Path) -> dict[str, Any]:
    refs = file_references()
    missing = []
    existing = 0
    for ref in refs:
        path = storage_root / ref["bucket"] / ref["path"]
        if path.exists() and path.stat().st_size >= 0:
            existing += 1
        else:
            missing.append(ref)
    return {
        "referenced_files": len(refs),
        "existing_files": existing,
        "missing_files": missing[:100],
        "missing_count": len(missing),
    }


def main() -> None:
    load_dotenv(ROOT / ".env")
    storage_root = ROOT / os.getenv("LOCAL_STORAGE_ROOT", "storage")
    report = {
        "exact_table_counts": exact_table_counts(),
        "estimated_table_counts": table_counts(),
        "vector_counts": vector_counts(),
        "storage": storage_summary(storage_root),
    }
    report_dir = ROOT / "migration_reports"
    report_dir.mkdir(exist_ok=True)
    path = report_dir / "postgres_migration_verify_latest.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[done] report={path}")


if __name__ == "__main__":
    main()


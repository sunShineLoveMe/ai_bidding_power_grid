#!/usr/bin/env python3
"""Dry-run or delete one customer RAG ingestion batch.

The default mode is dry-run. Add `--execute` to delete matching
knowledge_documents, document_chunks, and structured goods-list rows.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.postgres_pool import pooled_connection  # noqa: E402


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for batch rollback")
    return url


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        """
        select exists (
          select 1 from information_schema.tables
          where table_schema = 'public' and table_name = %s
        ) as exists
        """,
        [table],
    ).fetchone()
    return bool(row and row["exists"])


def _counts(conn, batch_id: str) -> dict[str, int]:
    goods_rows = 0
    if _table_exists(conn, "power_grid_goods_list_rows"):
        goods_rows = conn.execute(
            "select count(*) as count from public.power_grid_goods_list_rows where ingestion_batch_id = %s",
            [batch_id],
        ).fetchone()["count"]
    return {
        "knowledge_documents": conn.execute(
            "select count(*) as count from public.knowledge_documents where metadata->>'ingestion_batch_id' = %s",
            [batch_id],
        ).fetchone()["count"],
        "document_chunks": conn.execute(
            "select count(*) as count from public.document_chunks where metadata->>'ingestion_batch_id' = %s",
            [batch_id],
        ).fetchone()["count"],
        "goods_list_rows": goods_rows,
    }


def _role_counts(conn, batch_id: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            """
            select metadata->>'doc_role' as doc_role, count(*) as count
            from public.document_chunks
            where metadata->>'ingestion_batch_id' = %s
            group by metadata->>'doc_role'
            order by count desc
            """,
            [batch_id],
        ).fetchall()
    ]


def _sample_documents(conn, batch_id: str) -> list[dict[str, Any]]:
    return [
        {key: str(value) if key == "id" and value is not None else value for key, value in dict(row).items()}
        for row in conn.execute(
            """
            select id, title, metadata->>'province' as province, metadata->>'package_code' as package_code,
                   metadata->>'doc_role' as doc_role
            from public.knowledge_documents
            where metadata->>'ingestion_batch_id' = %s
            order by title
            limit 10
            """,
            [batch_id],
        ).fetchall()
    ]


def _execute_delete(conn, batch_id: str) -> dict[str, int]:
    deleted: dict[str, int] = {}
    if _table_exists(conn, "power_grid_goods_list_rows"):
        cur = conn.execute(
            "delete from public.power_grid_goods_list_rows where ingestion_batch_id = %s",
            [batch_id],
        )
        deleted["goods_list_rows"] = cur.rowcount
    else:
        deleted["goods_list_rows"] = 0
    cur = conn.execute(
        "delete from public.document_chunks where metadata->>'ingestion_batch_id' = %s",
        [batch_id],
    )
    deleted["document_chunks"] = cur.rowcount
    cur = conn.execute(
        "delete from public.knowledge_documents where metadata->>'ingestion_batch_id' = %s",
        [batch_id],
    )
    deleted["knowledge_documents"] = cur.rowcount
    return deleted


def _write_report(report: dict[str, Any], save_dir: Path) -> tuple[Path, Path]:
    save_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "executed" if report["execute"] else "dry_run"
    json_path = save_dir / f"rollback_{report['batch_id']}_{suffix}_{stamp}.json"
    md_path = save_dir / f"rollback_{report['batch_id']}_{suffix}_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 客户 RAG 批次回滚报告",
        "",
        f"> 批次：`{report['batch_id']}`",
        f"> 模式：`{'execute' if report['execute'] else 'dry-run'}`",
        f"> 生成时间：{report['generated_at']}",
        "",
        "## 影响范围",
        "",
        "| 表 | 数量 |",
        "| --- | ---: |",
    ]
    for key, value in report["before_counts"].items():
        lines.append(f"| `{key}` | {value} |")
    if report.get("deleted_counts") is not None:
        lines.extend(["", "## 已删除", "", "| 表 | 数量 |", "| --- | ---: |"])
        for key, value in report["deleted_counts"].items():
            lines.append(f"| `{key}` | {value} |")
    lines.extend(["", "## chunk 角色分布", "", "| doc_role | chunk 数 |", "| --- | ---: |"])
    for row in report["role_counts"]:
        lines.append(f"| `{row.get('doc_role') or '-'}` | {row['count']} |")
    lines.extend(["", "## 文档样例", "", "| 省份 | 包编码 | doc_role | title |", "| --- | --- | --- | --- |"])
    for row in report["sample_documents"]:
        lines.append(
            f"| {row.get('province') or '-'} | `{row.get('package_code') or '-'}` | "
            f"`{row.get('doc_role') or '-'}` | `{row.get('title') or '-'}` |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--execute", action="store_true", help="actually delete the batch")
    parser.add_argument("--save-dir", type=Path, default=PROJECT_ROOT / "docs/rag/runs")
    args = parser.parse_args()

    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        before_counts = _counts(conn, args.batch_id)
        role_counts = _role_counts(conn, args.batch_id)
        sample_documents = _sample_documents(conn, args.batch_id)
        deleted_counts = _execute_delete(conn, args.batch_id) if args.execute else None
        report = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "batch_id": args.batch_id,
            "execute": args.execute,
            "before_counts": before_counts,
            "deleted_counts": deleted_counts,
            "role_counts": role_counts,
            "sample_documents": sample_documents,
        }
    json_path, md_path = _write_report(report, args.save_dir.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"JSON: {_rel(json_path)}")
    print(f"Report: {_rel(md_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

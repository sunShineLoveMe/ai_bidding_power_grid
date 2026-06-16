#!/usr/bin/env python3
"""Backfill missing embeddings for knowledge_assets.

This script is intentionally update-only: it does not rebuild, delete, or
re-upload asset files. It uses the same embedding client/configuration as the
runtime RAG path, so local Ollama and DashScope behave consistently.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.core.config import get_setting  # noqa: E402
from backend.db.postgres_pool import pooled_connection  # noqa: E402
from backend.rag.vector_store import get_embeddings, init_ali_client  # noqa: E402


DEFAULT_SOURCE_BATCH_ID = "customer_liaoning_taichang_20260606_p0_formal_full_page_assets_v1"


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required")
    return url


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _vector(value: list[float]) -> str:
    return "[" + ",".join(str(item) for item in value) + "]"


def _asset_text(asset: dict[str, Any]) -> str:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    parts: list[str] = [
        str(asset.get("searchable_text") or ""),
        str(asset.get("title") or ""),
        str(asset.get("description") or ""),
        str(asset.get("category") or ""),
        str(metadata.get("source_display_name") or ""),
        str(metadata.get("source_file_name") or ""),
        str(metadata.get("evidence_type_label") or ""),
        str(metadata.get("target_library_label") or ""),
        str(metadata.get("enterprise") or ""),
        str(metadata.get("doc_owner") or ""),
    ]
    tags = asset.get("tags")
    if isinstance(tags, list):
        parts.append(" ".join(str(item) for item in tags))
    text = "\n".join(part.strip() for part in parts if part and part.strip())
    return text.strip()


def _count_by_batch(source_batch_id: str) -> dict[str, Any]:
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        row = conn.execute(
            """
            select count(*)::int as total,
                   count(embedding)::int as with_embedding,
                   (count(*) - count(embedding))::int as missing
            from public.knowledge_assets
            where metadata->>'source_batch_id' = %s
            """,
            [source_batch_id],
        ).fetchone()
        return dict(row or {})


def _load_missing(source_batch_id: str, limit: int | None) -> list[dict[str, Any]]:
    limit_sql = "" if not limit else " limit %s"
    params: list[Any] = [source_batch_id]
    if limit:
        params.append(limit)
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        return [
            dict(row)
            for row in conn.execute(
                f"""
                select id, title, description, category, asset_type, tags, searchable_text, metadata
                from public.knowledge_assets
                where embedding is null
                  and metadata->>'source_batch_id' = %s
                order by created_at asc, id asc
                {limit_sql}
                """,
                params,
            ).fetchall()
        ]


def _update_asset_embedding(asset_id: str, embedding: list[float], metadata_patch: dict[str, Any]) -> None:
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        conn.execute(
            """
            update public.knowledge_assets
            set embedding = %s::vector,
                metadata = coalesce(metadata, '{}'::jsonb) || %s::jsonb,
                updated_at = now()
            where id = %s::uuid
            """,
            [_vector(embedding), Jsonb(metadata_patch), asset_id],
        )


def _write_reports(report_path: Path, report: dict[str, Any]) -> Path:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = report_path.with_suffix(".md")
    lines = [
        f"# 知识资产 embedding backfill 记录 - {report['run_id']}",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- source_batch_id：`{report['source_batch_id']}`",
        f"- dry-run：`{report['dry_run']}`",
        f"- embedding_base_url：`{report['embedding_base_url']}`",
        f"- embedding_model：`{report['embedding_model']}`",
        f"- embedding_dimensions：`{report['embedding_dimensions']}`",
        "",
        "## 统计",
        "",
        "| 阶段 | total | with_embedding | missing |",
        "| --- | ---: | ---: | ---: |",
        f"| before | {report['before']['total']} | {report['before']['with_embedding']} | {report['before']['missing']} |",
        f"| after | {report['after']['total']} | {report['after']['with_embedding']} | {report['after']['missing']} |",
        "",
        "## 执行结果",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| selected | {report['selected']} |",
        f"| updated | {report['updated']} |",
        f"| skipped_empty_text | {report['skipped_empty_text']} |",
        f"| failed | {report['failed']} |",
        "",
        "## 失败项",
        "",
    ]
    failures = [item for item in report["items"] if item["status"] == "failed"]
    if failures:
        for item in failures[:50]:
            lines.append(f"- `{item['id']}` {item.get('title') or ''}: {item.get('error')}")
    else:
        lines.append("- 无")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-batch-id", default=DEFAULT_SOURCE_BATCH_ID)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="JSON report path. Defaults to docs/rag/runs/<run_id>_asset_embedding_backfill.json",
    )
    args = parser.parse_args()

    report_path = args.report or PROJECT_ROOT / "docs" / "rag" / "runs" / f"{args.run_id}_asset_embedding_backfill.json"
    before = _count_by_batch(args.source_batch_id)
    assets = _load_missing(args.source_batch_id, args.limit or None)
    client = init_ali_client()
    items: list[dict[str, Any]] = []
    updated = 0
    skipped_empty = 0
    failed = 0

    for start in range(0, len(assets), max(1, args.batch_size)):
        batch_assets = assets[start : start + max(1, args.batch_size)]
        text_pairs = [(asset, _asset_text(asset)) for asset in batch_assets]
        valid_pairs = [(asset, text) for asset, text in text_pairs if text]
        for asset, text in text_pairs:
            if not text:
                skipped_empty += 1
                items.append({"id": str(asset["id"]), "title": asset.get("title"), "status": "skipped_empty_text"})
        if args.dry_run or not valid_pairs:
            if args.dry_run:
                for asset, text in valid_pairs:
                    items.append({
                        "id": str(asset["id"]),
                        "title": asset.get("title"),
                        "status": "dry_run",
                        "text_chars": len(text),
                    })
            continue
        texts = [text for _, text in valid_pairs]
        try:
            embeddings = get_embeddings(
                client,
                texts,
                batch_size=max(1, args.batch_size),
                usage_context={
                    "stage": "knowledge_asset_embedding_backfill",
                    "metadata": {
                        "run_id": args.run_id,
                        "source_batch_id": args.source_batch_id,
                        "asset_count": len(valid_pairs),
                    },
                },
            )
        except Exception as exc:
            failed += len(valid_pairs)
            for asset, text in valid_pairs:
                items.append({
                    "id": str(asset["id"]),
                    "title": asset.get("title"),
                    "status": "failed",
                    "text_chars": len(text),
                    "error": str(exc),
                })
            continue
        for (asset, text), embedding in zip(valid_pairs, embeddings):
            try:
                metadata_patch = {
                    "embedding_backfill_run_id": args.run_id,
                    "embedding_backfilled_at": _now_iso(),
                    "embedding_model": str(get_setting("embedding_model", "text-embedding-v4")),
                    "embedding_dimensions": len(embedding),
                    "embedding_source": "knowledge_asset_embedding_backfill",
                }
                _update_asset_embedding(str(asset["id"]), embedding, metadata_patch)
                updated += 1
                items.append({
                    "id": str(asset["id"]),
                    "title": asset.get("title"),
                    "status": "updated",
                    "text_chars": len(text),
                    "embedding_dimensions": len(embedding),
                })
            except Exception as exc:
                failed += 1
                items.append({
                    "id": str(asset["id"]),
                    "title": asset.get("title"),
                    "status": "failed",
                    "text_chars": len(text),
                    "error": str(exc),
                })

    after = _count_by_batch(args.source_batch_id)
    report = {
        "run_id": args.run_id,
        "generated_at": _now_iso(),
        "source_batch_id": args.source_batch_id,
        "dry_run": bool(args.dry_run),
        "limit": args.limit or None,
        "batch_size": args.batch_size,
        "embedding_base_url": str(get_setting("embedding_base_url", "")),
        "embedding_model": str(get_setting("embedding_model", "text-embedding-v4")),
        "embedding_dimensions": int(get_setting("embedding_dimensions", 1024) or 1024),
        "before": before,
        "after": after,
        "selected": len(assets),
        "updated": updated,
        "skipped_empty_text": skipped_empty,
        "failed": failed,
        "items": items,
    }
    md_path = _write_reports(report_path.resolve(), report)
    print(json.dumps({k: report[k] for k in ["run_id", "source_batch_id", "dry_run", "selected", "updated", "skipped_empty_text", "failed", "before", "after"]}, ensure_ascii=False, indent=2))
    print(f"JSON: {report_path}")
    print(f"Report: {md_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

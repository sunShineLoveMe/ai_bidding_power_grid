#!/usr/bin/env python3
"""Repair user-facing Chinese display metadata for RAG sources.

This keeps source files and content unchanged. It only updates titles/category
labels/display-name metadata that can appear in the knowledge assistant.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.postgres_compat import _database_url  # noqa: E402
from backend.db.postgres_pool import pooled_connection  # noqa: E402
from backend.rag.display_names import (  # noqa: E402
    INTERNAL_NAME_LABELS,
    category_display_name,
    sanitize_source_metadata,
    source_display_name,
)


INTERNAL_PATTERNS = [
    "%taichang_%",
    "%power_grid_%",
    "%production_capacity%",
    "%green_low_carbon%",
    "%business_license%",
    "%certification%",
    "%product_library%",
    "%qualification_library%",
    "%_private.md%",
]

ASSET_CATALOG_FILENAME_RENAMES = {
    "taichang_business_license_taichang_internal_private.md": "泰昌基础证照内部专用图片资产目录.md",
    "taichang_certification_private.md": "泰昌资质证书图片资产目录.md",
    "taichang_finance_taichang_internal_private.md": "泰昌财务资料内部专用图片资产目录.md",
    "taichang_green_low_carbon_private.md": "泰昌绿色低碳资料图片资产目录.md",
    "taichang_inspection_report_private.md": "泰昌检验报告图片资产目录.md",
    "taichang_production_capacity_private.md": "泰昌生产制造能力图片资产目录.md",
    "taichang_production_capacity_taichang_internal_private.md": "泰昌生产制造能力内部专用图片资产目录.md",
    "taichang_testing_capacity_private.md": "泰昌试验检测能力图片资产目录.md",
    "taichang_testing_capacity_taichang_internal_private.md": "泰昌试验检测能力内部专用图片资产目录.md",
}


def _needs_repair_text(value: Any) -> bool:
    text = str(value or "")
    lowered = text.lower()
    return any(token.strip("%").lower() in lowered for token in INTERNAL_PATTERNS)


def _display_title(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    title = str(row.get("title") or "")
    display = source_display_name(metadata, fallback_title=title)
    if display != "企业知识库资料":
        return display
    lowered = title.lower()
    return INTERNAL_NAME_LABELS.get(lowered, title)


def _repair_source_file(metadata: dict[str, Any]) -> dict[str, Any]:
    source_file = str(metadata.get("source_file") or "")
    if not source_file:
        return metadata
    for old_name, new_name in ASSET_CATALOG_FILENAME_RENAMES.items():
        if old_name in source_file:
            metadata = dict(metadata)
            metadata["source_file"] = source_file.replace(old_name, new_name)
            if not metadata.get("source_display_name"):
                metadata["source_display_name"] = new_name.removesuffix(".md")
            break
    return metadata


def _repair_document(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    metadata = sanitize_source_metadata(row.get("metadata") if isinstance(row.get("metadata"), dict) else {}, fallback_title=row.get("title"))
    metadata = _repair_source_file(metadata)
    title = _display_title({**row, "metadata": metadata})
    return title, metadata


def repair(dry_run: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "documents_scanned": 0,
        "documents_updated": 0,
        "chunks_scanned": 0,
        "chunks_updated": 0,
        "assets_scanned": 0,
        "assets_updated": 0,
        "document_updates": [],
        "chunk_updates": [],
        "asset_updates": [],
    }
    database_url = _database_url()
    with pooled_connection(database_url) as conn:
        docs = conn.execute(
            """
            select id, title, category, metadata
            from public.knowledge_documents
            where title ilike any(%s) or category ilike any(%s) or metadata::text ilike any(%s)
            """,
            (INTERNAL_PATTERNS, INTERNAL_PATTERNS, INTERNAL_PATTERNS),
        ).fetchall()
        report["documents_scanned"] = len(docs)
        for row in docs:
            item = dict(row)
            new_title, new_metadata = _repair_document(item)
            new_category = category_display_name(item.get("category"))
            changed = (
                new_title != item.get("title")
                or new_category != item.get("category")
                or new_metadata != item.get("metadata")
            )
            if not changed:
                continue
            report["documents_updated"] += 1
            report["document_updates"].append({
                "id": str(item["id"]),
                "old_title": item.get("title"),
                "new_title": new_title,
                "old_category": item.get("category"),
                "new_category": new_category,
            })
            if not dry_run:
                conn.execute(
                    "update public.knowledge_documents set title = %s, category = %s, metadata = %s::jsonb where id = %s",
                    (new_title, new_category, json.dumps(new_metadata, ensure_ascii=False), item["id"]),
                )

        chunks = conn.execute(
            """
            select id, metadata
            from public.document_chunks
            where metadata::text ilike any(%s)
            """,
            (INTERNAL_PATTERNS,),
        ).fetchall()
        report["chunks_scanned"] = len(chunks)
        for row in chunks:
            item = dict(row)
            old_metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            new_metadata = sanitize_source_metadata(old_metadata)
            new_metadata = _repair_source_file(new_metadata)
            if new_metadata == old_metadata:
                continue
            report["chunks_updated"] += 1
            report["chunk_updates"].append({"id": str(item["id"]), "source_display_name": new_metadata.get("source_display_name")})
            if not dry_run:
                conn.execute(
                    "update public.document_chunks set metadata = %s::jsonb where id = %s",
                    (json.dumps(new_metadata, ensure_ascii=False), item["id"]),
                )

        assets = conn.execute(
            """
            select id, title, category, metadata, specs
            from public.knowledge_assets
            where title ilike any(%s) or category ilike any(%s) or metadata::text ilike any(%s) or specs::text ilike any(%s)
            """,
            (INTERNAL_PATTERNS, INTERNAL_PATTERNS, INTERNAL_PATTERNS, INTERNAL_PATTERNS),
        ).fetchall()
        report["assets_scanned"] = len(assets)
        for row in assets:
            item = dict(row)
            old_metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            new_metadata = sanitize_source_metadata(old_metadata, fallback_title=item.get("title"))
            new_metadata = _repair_source_file(new_metadata)
            new_category = category_display_name(item.get("category"))
            new_title = item.get("title")
            if _needs_repair_text(new_title):
                new_title = source_display_name(new_metadata, fallback_title=new_title)
            changed = new_metadata != old_metadata or new_category != item.get("category") or new_title != item.get("title")
            if not changed:
                continue
            report["assets_updated"] += 1
            report["asset_updates"].append({"id": str(item["id"]), "old_title": item.get("title"), "new_title": new_title})
            if not dry_run:
                conn.execute(
                    "update public.knowledge_assets set title = %s, category = %s, metadata = %s::jsonb where id = %s",
                    (new_title, new_category, json.dumps(new_metadata, ensure_ascii=False), item["id"]),
                )

        if not dry_run:
            conn.commit()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()

    report = repair(dry_run=not args.execute)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "dry_run": report["dry_run"],
        "documents_updated": report["documents_updated"],
        "chunks_updated": report["chunks_updated"],
        "assets_updated": report["assets_updated"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

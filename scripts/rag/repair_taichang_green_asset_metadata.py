#!/usr/bin/env python3
"""Repair Taichang green/low-carbon metadata that was classified as certification.

The script is deliberately metadata-only:
- it does not delete rows;
- it does not move files or storage objects;
- it does not rewrite embeddings.

The retrieval layer now protects customer-facing answers, but correcting the
metadata keeps enterprise asset pages, keyword fallback, and future exports from
presenting ESG/green development/carbon-footprint documents as formal
qualification certificates.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.postgres_compat import _database_url  # noqa: E402
from backend.db.postgres_pool import pooled_connection  # noqa: E402


GREEN_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("ESG环境社会公司治理报告", re.compile(r"ESG|环境社会公司治理", re.I)),
    ("绿色发展规划报告", re.compile(r"绿色发展")),
    ("绿色供应链认证证书", re.compile(r"绿色供应链")),
    ("碳足迹报告", re.compile(r"碳足迹")),
    ("废水废气废固检测报告", re.compile(r"废水废气废固|废水废气")),
]


def _json_text(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def classify_green_document(row: dict[str, Any]) -> str | None:
    blob = "\n".join(
        str(part or "")
        for part in [
            row.get("title"),
            row.get("category"),
            row.get("description"),
            row.get("searchable_text"),
            row.get("content"),
            _json_text(row.get("metadata")),
            _json_text(row.get("specs")),
        ]
    )
    for label, pattern in GREEN_RULES:
        if pattern.search(blob):
            return label
    return None


def _is_taichang_row(row: dict[str, Any]) -> bool:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    blob = "\n".join(
        str(part or "")
        for part in [
            row.get("title"),
            row.get("description"),
            row.get("searchable_text"),
            row.get("content"),
            metadata.get("enterprise"),
            metadata.get("doc_owner"),
            metadata.get("source_file"),
            metadata.get("source_display_name"),
        ]
    )
    return "泰昌" in blob or "河北泰昌电力器材科技有限公司" in blob


def _repair_asset(row: dict[str, Any], green_label: str) -> dict[str, Any]:
    metadata = dict(row.get("metadata") or {})
    specs = dict(row.get("specs") or {})
    metadata.update(
        {
            "enterprise": metadata.get("enterprise") or "泰昌",
            "source_domain": "enterprise_fact",
            "fact_source_allowed_for_enterprise": True,
            "reference_only": False,
            "target_library": "product_library",
            "target_library_label": "产品库资料",
            "evidence_type": "green_low_carbon",
            "evidence_type_label": "绿色低碳资料",
            "category_label": "绿色低碳资料",
            "source_display_name": metadata.get("source_display_name") or row.get("title") or green_label,
            "green_metadata_repaired": True,
        }
    )
    specs.update(
        {
            "target_library": "product_library",
            "evidence_type": "green_low_carbon",
            "green_document_type": green_label,
        }
    )
    category = "绿色低碳资料"
    title = str(row.get("title") or metadata["source_display_name"] or green_label)
    searchable_parts = [
        title,
        row.get("description"),
        category,
        "泰昌 泰昌企业事实 绿色低碳资料",
        green_label,
        _json_text(row.get("tags")),
    ]
    return {
        "title": title,
        "category": category,
        "asset_type": "product_image",
        "applicable_volumes": ["technical", "business"],
        "metadata": metadata,
        "specs": specs,
        "searchable_text": "\n".join(str(part).strip() for part in searchable_parts if str(part or "").strip()),
    }


def _repair_chunk(row: dict[str, Any], green_label: str) -> dict[str, Any]:
    metadata = dict(row.get("metadata") or {})
    source_display_name = metadata.get("source_display_name")
    if not source_display_name or source_display_name in {"泰昌资质证书资料", "泰昌绿色低碳资料"}:
        source_display_name = green_label
    metadata.update(
        {
            "enterprise": metadata.get("enterprise") or "泰昌",
            "source_domain": "enterprise_fact",
            "fact_source_allowed_for_enterprise": True,
            "reference_only": False,
            "target_library": "product_library",
            "target_library_label": "产品库资料",
            "evidence_type": "green_low_carbon",
            "evidence_type_label": "绿色低碳资料",
            "category_label": "绿色低碳资料",
            "source_display_name": source_display_name,
            "green_document_type": green_label,
            "green_metadata_repaired": True,
        }
    )
    return {"metadata": metadata}


def repair(dry_run: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "assets_scanned": 0,
        "assets_updated": 0,
        "chunks_scanned": 0,
        "chunks_updated": 0,
        "asset_updates": [],
        "chunk_updates": [],
    }
    with pooled_connection(_database_url()) as conn:
        asset_rows = conn.execute(
            """
            select id, title, description, category, asset_type, applicable_volumes,
                   tags, metadata, specs, searchable_text
            from public.knowledge_assets
            where status = 'indexed'
              and (
                    title ilike any(array['%ESG%', '%绿色发展%', '%绿色供应链%', '%碳足迹%', '%废水废气%'])
                 or description ilike any(array['%ESG%', '%绿色发展%', '%绿色供应链%', '%碳足迹%', '%废水废气%'])
                 or searchable_text ilike any(array['%ESG%', '%绿色发展%', '%绿色供应链%', '%碳足迹%', '%废水废气%'])
                 or metadata::text ilike any(array['%ESG%', '%绿色发展%', '%绿色供应链%', '%碳足迹%', '%废水废气%'])
              )
            """
        ).fetchall()
        report["assets_scanned"] = len(asset_rows)
        for raw in asset_rows:
            row = dict(raw)
            green_label = classify_green_document(row)
            if not green_label or not _is_taichang_row(row):
                continue
            old_metadata = row.get("metadata") or {}
            old_target = old_metadata.get("target_library")
            old_evidence = old_metadata.get("evidence_type")
            old_category = row.get("category")
            updates = _repair_asset(row, green_label)
            changed = (
                row.get("category") != updates["category"]
                or row.get("asset_type") != updates["asset_type"]
                or row.get("applicable_volumes") != updates["applicable_volumes"]
                or row.get("metadata") != updates["metadata"]
                or row.get("specs") != updates["specs"]
                or row.get("searchable_text") != updates["searchable_text"]
            )
            if not changed:
                continue
            report["assets_updated"] += 1
            report["asset_updates"].append(
                {
                    "id": str(row["id"]),
                    "title": row.get("title"),
                    "green_document_type": green_label,
                    "old_category": old_category,
                    "new_category": updates["category"],
                    "old_evidence_type": old_evidence,
                    "new_evidence_type": updates["metadata"]["evidence_type"],
                    "old_target_library": old_target,
                    "new_target_library": updates["metadata"]["target_library"],
                }
            )
            if not dry_run:
                conn.execute(
                    """
                    update public.knowledge_assets
                    set category = %s,
                        asset_type = %s,
                        applicable_volumes = %s,
                        metadata = %s::jsonb,
                        specs = %s::jsonb,
                        searchable_text = %s
                    where id = %s
                    """,
                    (
                        updates["category"],
                        updates["asset_type"],
                        updates["applicable_volumes"],
                        json.dumps(updates["metadata"], ensure_ascii=False),
                        json.dumps(updates["specs"], ensure_ascii=False),
                        updates["searchable_text"],
                        row["id"],
                    ),
                )

        chunk_rows = conn.execute(
            """
            select id, content, metadata
            from public.document_chunks
            where (
                    content ilike any(array['%ESG%', '%绿色发展%', '%绿色供应链%', '%碳足迹%', '%废水废气%'])
                 or metadata::text ilike any(array['%ESG%', '%绿色发展%', '%绿色供应链%', '%碳足迹%', '%废水废气%'])
              )
              and (
                    content ilike '%泰昌%'
                 or metadata::text ilike '%泰昌%'
                 or metadata::text ilike '%河北泰昌电力器材科技有限公司%'
              )
            """
        ).fetchall()
        report["chunks_scanned"] = len(chunk_rows)
        for raw in chunk_rows:
            row = dict(raw)
            green_label = classify_green_document(row)
            if not green_label or not _is_taichang_row(row):
                continue
            old_metadata = row.get("metadata") or {}
            updates = _repair_chunk(row, green_label)
            if old_metadata == updates["metadata"]:
                continue
            report["chunks_updated"] += 1
            report["chunk_updates"].append(
                {
                    "id": str(row["id"]),
                    "green_document_type": green_label,
                    "old_source_display_name": old_metadata.get("source_display_name"),
                    "new_source_display_name": updates["metadata"].get("source_display_name"),
                    "old_evidence_type": old_metadata.get("evidence_type"),
                    "new_evidence_type": updates["metadata"].get("evidence_type"),
                }
            )
            if not dry_run:
                conn.execute(
                    """
                    update public.document_chunks
                    set metadata = %s::jsonb
                    where id = %s
                    """,
                    (json.dumps(updates["metadata"], ensure_ascii=False), row["id"]),
                )
        if not dry_run:
            conn.commit()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="apply changes; default is dry-run")
    parser.add_argument("--save", type=Path, help="write full JSON report")
    args = parser.parse_args()

    report = repair(dry_run=not args.execute)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "dry_run": report["dry_run"],
                "assets_scanned": report["assets_scanned"],
                "assets_updated": report["assets_updated"],
                "chunks_scanned": report["chunks_scanned"],
                "chunks_updated": report["chunks_updated"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    raise SystemExit(main())

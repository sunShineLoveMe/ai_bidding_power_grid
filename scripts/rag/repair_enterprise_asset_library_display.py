#!/usr/bin/env python3
"""Repair enterprise asset library ownership and user-facing display names.

This script is intentionally metadata-focused: it does not move or rewrite
stored files. Existing asset ids and storage paths stay stable, so knowledge
chat image URLs and DOCX image references continue to work.
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
from backend.rag.display_names import category_display_name  # noqa: E402


PERSONNEL_RE = re.compile(r"人员证书|人员花名册|劳动合同|社保|参保证明")


def _json_text(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _asset_text(row: dict[str, Any]) -> str:
    return "\n".join(
        str(part or "")
        for part in [
            row.get("title"),
            row.get("category"),
            row.get("description"),
            row.get("searchable_text"),
            _json_text(row.get("tags")),
            _json_text(row.get("metadata")),
            _json_text(row.get("specs")),
        ]
    )


def _is_personnel_asset(row: dict[str, Any]) -> bool:
    return bool(PERSONNEL_RE.search(_asset_text(row)))


def _friendly_title(row: dict[str, Any], category: str) -> str:
    title = str(row.get("title") or "").strip()
    if not title:
        return "泰昌企业资料"
    title = re.sub(r"^河北泰昌电力器材科技有限公司\s*", "", title)
    title = re.sub(r"^泰昌泰昌", "泰昌", title)
    title = re.sub(r"^泰昌\s*[0-9]+[._、-]?", "", title)
    title = re.sub(r"\s+", "", title)
    title = title.replace("Logo", " Logo")
    title = re.sub(r"第([0-9一二三四五六七八九十百]+)页$", r"（第\1页）", title)
    if category == "人员证书" and not re.search(r"人员证书|人员花名册|劳动合同|社保|参保证明", title):
        title = re.sub(r"（第([0-9一二三四五六七八九十百]+)页）$", r"人员证书（第\1页）", title)
    return title or str(row.get("title") or "泰昌企业资料")


def _target_category(row: dict[str, Any]) -> str:
    if _is_personnel_asset(row):
        return "人员证书"
    if row.get("category"):
        return category_display_name(row.get("category"))
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    for key in ("evidence_type_label", "category_label", "evidence_type"):
        value = metadata.get(key)
        if value:
            return category_display_name(value)
    return category_display_name(row.get("category")) or str(row.get("category") or "企业资料")


def _repair_asset(row: dict[str, Any], include_title_cleanup: bool = True) -> dict[str, Any]:
    metadata = dict(row.get("metadata") or {})
    specs = dict(row.get("specs") or {})
    category = _target_category(row)
    title = _friendly_title(row, category) if include_title_cleanup or category == "人员证书" else str(row.get("title") or "").strip()
    title_changed = title != row.get("title")

    updates: dict[str, Any] = {
        "title": title,
        "category": category,
        "metadata": metadata,
        "specs": specs,
    }

    if category == "人员证书":
        updates["asset_type"] = "qualification_image"
        updates["applicable_volumes"] = ["qualification", "business", "attachment"]
        metadata.update(
            {
                "library_type": "qualification",
                "target_library": "qualification_library",
                "target_library_label": "资信库资料",
                "evidence_type": "personnel_certificate",
                "evidence_type_label": "人员证书",
                "category_label": "人员证书",
                "source_display_name": title,
            }
        )
        specs.update(
            {
                "library_type": "qualification",
                "applicable_volumes": ["qualification", "business", "attachment"],
            }
        )
    else:
        if title_changed and (metadata.get("source_display_name") == row.get("title") or not metadata.get("source_display_name")):
            metadata["source_display_name"] = title
        if title_changed and not metadata.get("category_label"):
            metadata["category_label"] = category

    if title_changed or category == "人员证书":
        searchable_parts = [
            title,
            row.get("description"),
            category,
            updates.get("asset_type") or row.get("asset_type"),
            _json_text(row.get("tags")),
            _json_text(specs),
        ]
        updates["searchable_text"] = "\n".join(str(part).strip() for part in searchable_parts if str(part or "").strip())
    return updates


def repair(dry_run: bool, include_title_cleanup: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "assets_scanned": 0,
        "assets_updated": 0,
        "personnel_assets_moved": 0,
        "updates": [],
    }
    with pooled_connection(_database_url()) as conn:
        rows = conn.execute(
            """
            select id, title, description, category, asset_type, applicable_volumes,
                   tags, metadata, specs, searchable_text
            from public.knowledge_assets
            where title ilike '%泰昌%'
               or category in ('人员证书', '资质证书', '基础证照', '绿色低碳资料', '生产制造能力', '试验检测设备', '检验报告')
               or metadata::text ilike '%人员证书%'
               or specs::text ilike '%人员证书%'
            """
        ).fetchall()
        report["assets_scanned"] = len(rows)
        for row in rows:
            item = dict(row)
            updates = _repair_asset(item, include_title_cleanup=include_title_cleanup)
            changed = any(updates.get(key) != item.get(key) for key in updates)
            if not changed:
                continue
            if _is_personnel_asset(item) and item.get("asset_type") != "qualification_image":
                report["personnel_assets_moved"] += 1
            report["assets_updated"] += 1
            report["updates"].append(
                {
                    "id": str(item["id"]),
                    "old_title": item.get("title"),
                    "new_title": updates["title"],
                    "old_category": item.get("category"),
                    "new_category": updates["category"],
                    "old_asset_type": item.get("asset_type"),
                    "new_asset_type": updates.get("asset_type") or item.get("asset_type"),
                }
            )
            if not dry_run:
                conn.execute(
                    """
                    update public.knowledge_assets
                    set title = %s,
                        category = %s,
                        asset_type = %s,
                        applicable_volumes = %s,
                        metadata = %s::jsonb,
                        specs = %s::jsonb,
                        searchable_text = %s
                    where id = %s
                    """,
                    (
                        updates["title"],
                        updates["category"],
                        updates.get("asset_type") or item.get("asset_type"),
                        updates.get("applicable_volumes") or item.get("applicable_volumes") or [],
                        json.dumps(updates["metadata"], ensure_ascii=False),
                        json.dumps(updates["specs"], ensure_ascii=False),
                        updates.get("searchable_text") or item.get("searchable_text") or "",
                        item["id"],
                    ),
                )
        if not dry_run:
            conn.commit()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="apply changes; default is dry-run")
    parser.add_argument("--include-title-cleanup", action="store_true", help="also rewrite non-personnel page-style asset titles")
    parser.add_argument("--save", type=Path, help="write full JSON report")
    args = parser.parse_args()

    report = repair(dry_run=not args.execute, include_title_cleanup=args.include_title_cleanup)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "dry_run": report["dry_run"],
                "assets_scanned": report["assets_scanned"],
                "assets_updated": report["assets_updated"],
                "personnel_assets_moved": report["personnel_assets_moved"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    raise SystemExit(main())

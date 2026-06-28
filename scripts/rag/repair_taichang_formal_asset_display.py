#!/usr/bin/env python3
"""Backfill formal Chinese display metadata for Taichang image assets.

The script keeps original files, storage paths and asset ids unchanged. It only
updates user-facing titles/labels and formal-bid eligibility metadata so local
and Aliyun deployments use the same deterministic rules.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.postgres_compat import _database_url  # noqa: E402
from backend.db.postgres_pool import pooled_connection  # noqa: E402
from backend.rag.display_names import category_display_name  # noqa: E402
from backend.services.formal_asset_naming import (  # noqa: E402
    caption_policy,
    formal_asset_caption,
    formal_asset_title,
)


RUNS_DIR = PROJECT_ROOT / "docs" / "development" / "runs"

EVIDENCE_LABELS = {
    "business_license": "基础证照",
    "certification": "资质证书",
    "finance": "财务资料",
    "audit_report": "财务资料",
    "production_capacity": "生产制造能力",
    "testing_capacity": "试验检测能力",
    "green_low_carbon": "绿色低碳资料",
    "inspection_report": "检验报告",
    "project_performance": "项目业绩",
    "personnel_certificate": "人员证书",
    "authorization": "授权文件",
    "product": "产品实物图片",
    "product_image": "产品实物图片",
}

LIBRARY_LABELS = {
    "product_library": "产品库资料",
    "qualification_library": "资信库资料",
    "knowledge_library": "知识库资料",
}


def _category_fallback_title(category: str) -> str:
    return category if category.endswith(("资料", "证书", "报告", "文件", "图片")) else f"{category}资料"


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _text_blob(row: dict[str, Any]) -> str:
    return "\n".join(
        str(part or "")
        for part in [
            row.get("title"),
            row.get("description"),
            row.get("category"),
            row.get("file_name"),
            row.get("local_path"),
            row.get("storage_path"),
            row.get("source_type"),
            _json(row.get("tags")),
            _json(row.get("metadata")),
            _json(row.get("specs")),
        ]
    )


def _meta(row: dict[str, Any], key: str) -> Any:
    for container_name in ("metadata", "specs"):
        container = row.get(container_name)
        if isinstance(container, dict) and key in container:
            return container.get(key)
    return row.get(key)


def _is_full_page(row: dict[str, Any]) -> bool:
    visual_type = str(_meta(row, "asset_visual_type") or "")
    source_type = str(row.get("source_type") or "")
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return bool(
        metadata.get("full_page") is True
        or "full_page" in visual_type
        or source_type == "customer_pdf_full_page_render"
    )


def _should_exclude_from_formal_bid(row: dict[str, Any]) -> tuple[bool, str]:
    blob = _text_blob(row).lower()
    if any(token in blob for token in ("模拟产品图片", "codex-taichang", "mock", "sample_generated")):
        return True, "模拟或测试图片资产，不进入正式标书候选。"
    if "taichang_mvp_mineru_asset" in blob and not _is_full_page(row):
        return True, "MinerU 局部切图只作为解析复核线索，不进入正式标书候选。"
    if "extract/images" in blob and not _is_full_page(row):
        return True, "解析局部图片只作为复核线索，不进入正式标书候选。"
    if re.search(r"二维码|qr\s*code|签名|印章|页脚|页眉|装饰", blob, flags=re.I) and not _is_full_page(row):
        return True, "二维码、签章、页眉页脚或装饰性局部图片不进入正式标书候选。"
    return False, ""


def _formal_category(row: dict[str, Any]) -> str:
    evidence_type = str(_meta(row, "evidence_type") or "")
    if evidence_type in EVIDENCE_LABELS:
        return EVIDENCE_LABELS[evidence_type]
    category = category_display_name(row.get("category"))
    return category or "企业资料"


def _formal_description(row: dict[str, Any], formal_title: str, category: str) -> str:
    source_name = ""
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    source_file_name = str(metadata.get("source_file_name") or "")
    if source_file_name:
        source_name = Path(source_file_name).stem
    if not source_name:
        source_file = str(metadata.get("source_file") or row.get("local_path") or row.get("storage_path") or "")
        if source_file:
            source_name = Path(source_file).stem
    source_name = re.sub(r"_?第\s*\d+\s*页", "", source_name)
    source_name = re.sub(r"_?第\s*0+\d+\s*页", "", source_name)
    source_name = re.sub(r"[_\-]?(?:页面|页码|page)[_\-\s]*\d+", "", source_name, flags=re.I)
    if not re.search(r"[\u4e00-\u9fff]", source_name):
        source_name = ""
    source_name = source_name or formal_title
    if _is_full_page(row):
        return f"河北泰昌电力器材科技有限公司{category}，来源于客户已提供文件《{source_name}》。该图片为客户原始资料整页渲染件。"
    return f"河北泰昌电力器材科技有限公司{category}，用于正式投标文件中的企业资料展示。"


def _repair_row(row: dict[str, Any], rewrite_title: bool) -> dict[str, Any]:
    metadata = dict(row.get("metadata") or {})
    specs = dict(row.get("specs") or {})
    evidence_type = str(metadata.get("evidence_type") or specs.get("evidence_type") or "")
    target_library = str(metadata.get("target_library") or specs.get("target_library") or "")
    excluded, exclusion_reason = _should_exclude_from_formal_bid(row)
    category = _formal_category(row)
    fallback_title = _category_fallback_title(category)
    clean_metadata = dict(metadata)
    clean_specs = dict(specs)
    clean_metadata.pop("formal_display_title", None)
    clean_metadata.pop("formal_caption", None)
    clean_specs.pop("formal_display_title", None)
    clean_specs.pop("formal_caption", None)
    formal_title = formal_asset_title({**row, "metadata": clean_metadata, "specs": clean_specs}, fallback_title)
    if formal_title == "企业资料" and category != "企业资料":
        formal_title = fallback_title
    formal_asset = {**row, "title": formal_title, "metadata": clean_metadata, "specs": clean_specs}
    formal_caption = formal_asset_caption(formal_asset) or ""
    policy = caption_policy(formal_asset)

    metadata.update(
        {
            "enterprise": metadata.get("enterprise") or "泰昌",
            "doc_owner": metadata.get("doc_owner") or "河北泰昌电力器材科技有限公司",
            "source_domain": metadata.get("source_domain") or "enterprise_fact",
            "reference_only": False,
            "fact_source_allowed_for_enterprise": True,
            "tenant_visibility": metadata.get("tenant_visibility") or "taichang_only",
            "access_scope": metadata.get("access_scope") or "taichang_tenant_internal",
            "formal_display_title": formal_title,
            "formal_caption": formal_caption,
            "formal_caption_policy": policy,
            "category_label": category,
            "source_display_name": formal_title,
        }
    )
    if evidence_type:
        metadata["evidence_type_label"] = EVIDENCE_LABELS.get(evidence_type, category)
    if target_library:
        metadata["target_library_label"] = LIBRARY_LABELS.get(target_library, "企业资料库")

    specs["formal_display_title"] = formal_title
    specs["display_name"] = formal_title
    specs["formal_caption"] = formal_caption
    specs["formal_caption_policy"] = policy
    specs["category_label"] = category

    if excluded:
        metadata["allowed_for_bid"] = False
        metadata["formal_bid_excluded"] = True
        metadata["formal_bid_exclusion_reason"] = exclusion_reason
        specs["allowed_for_bid"] = False
        specs["formal_bid_excluded"] = True
    else:
        metadata.setdefault("allowed_for_bid", True)
        specs.setdefault("allowed_for_bid", True)

    title = formal_title if rewrite_title else str(row.get("title") or "")
    description = _formal_description(row, formal_title, category)
    searchable_parts = [
        title,
        formal_title,
        formal_caption,
        category,
        description,
        row.get("asset_type"),
        _json(row.get("tags")),
        _json(specs),
    ]
    return {
        "title": title,
        "description": description,
        "category": category,
        "metadata": metadata,
        "specs": specs,
        "searchable_text": "\n".join(str(part).strip() for part in searchable_parts if str(part or "").strip()),
        "excluded": excluded,
        "exclusion_reason": exclusion_reason,
        "formal_title": formal_title,
        "formal_caption": formal_caption,
        "caption_policy": policy,
    }


def repair(run_id: str, dry_run: bool, rewrite_title: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "run_id": run_id,
        "dry_run": dry_run,
        "rewrite_title": rewrite_title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assets_scanned": 0,
        "assets_changed": 0,
        "titles_rewritten": 0,
        "formal_bid_excluded": 0,
        "caption_suppressed": 0,
        "samples": [],
    }
    with pooled_connection(_database_url()) as conn:
        rows = conn.execute(
            """
            select id, title, description, category, asset_type, file_name, local_path,
                   storage_path, source_type, applicable_sections, applicable_volumes,
                   tags, metadata, specs, searchable_text
            from public.knowledge_assets
            where title ilike '%%泰昌%%'
               or description ilike '%%泰昌%%'
               or metadata::text ilike '%%泰昌%%'
               or specs::text ilike '%%泰昌%%'
               or local_path ilike '%%泰昌%%'
               or storage_path ilike '%%泰昌%%'
            order by created_at asc nulls last
            """
        ).fetchall()
        report["assets_scanned"] = len(rows)
        for row in rows:
            item = dict(row)
            updates = _repair_row(item, rewrite_title=rewrite_title)
            changed = (
                updates["title"] != item.get("title")
                or updates["category"] != item.get("category")
                or updates["description"] != (item.get("description") or "")
                or updates["metadata"] != (item.get("metadata") or {})
                or updates["specs"] != (item.get("specs") or {})
                or updates["searchable_text"] != (item.get("searchable_text") or "")
            )
            if not changed:
                continue
            report["assets_changed"] += 1
            if updates["title"] != item.get("title"):
                report["titles_rewritten"] += 1
            if updates["excluded"]:
                report["formal_bid_excluded"] += 1
            if updates["caption_policy"] == "suppressed_document_page_caption":
                report["caption_suppressed"] += 1
            if len(report["samples"]) < 30:
                report["samples"].append(
                    {
                        "id": str(item["id"]),
                        "old_title": item.get("title"),
                        "new_title": updates["title"],
                        "formal_caption": updates["formal_caption"],
                        "caption_policy": updates["caption_policy"],
                        "category": updates["category"],
                        "excluded": updates["excluded"],
                        "exclusion_reason": updates["exclusion_reason"],
                    }
                )
            if not dry_run:
                conn.execute(
                    """
                    update public.knowledge_assets
                    set title = %s,
                        category = %s,
                        description = %s,
                        metadata = %s::jsonb,
                        specs = %s::jsonb,
                        searchable_text = %s,
                        updated_at = now()
                    where id = %s
                    """,
                    (
                        updates["title"],
                        updates["category"],
                        updates["description"],
                        json.dumps(updates["metadata"], ensure_ascii=False),
                        json.dumps(updates["specs"], ensure_ascii=False),
                        updates["searchable_text"],
                        item["id"],
                    ),
                )
        if not dry_run:
            conn.commit()
    return report


def write_report(report: dict[str, Any]) -> tuple[Path, Path]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RUNS_DIR / f"{report['run_id']}.json"
    md_path = RUNS_DIR / f"{report['run_id']}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 泰昌正式图片资产展示字段回填",
        "",
        f"> Run：`{report['run_id']}`",
        f"> dry_run：`{report['dry_run']}`",
        "",
        "## 摘要",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 扫描资产 | {report['assets_scanned']} |",
        f"| 更新资产 | {report['assets_changed']} |",
        f"| 重写标题 | {report['titles_rewritten']} |",
        f"| 剔除正式标书候选 | {report['formal_bid_excluded']} |",
        f"| 抑制整页资料题注 | {report['caption_suppressed']} |",
        "",
        "## 样例",
        "",
    ]
    for sample in report["samples"]:
        lines.append(
            f"- `{sample['id']}` {sample['old_title']} -> {sample['new_title']}；"
            f"题注策略：{sample['caption_policy']}；正式题注：{sample['formal_caption'] or '无'}"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_taichang_formal_asset_repair")
    parser.add_argument("--execute", action="store_true", help="apply changes; default is dry-run")
    parser.add_argument("--rewrite-title", action="store_true", help="rewrite knowledge_assets.title to formal Chinese title")
    args = parser.parse_args()

    report = repair(args.run_id, dry_run=not args.execute, rewrite_title=args.rewrite_title)
    json_path, md_path = write_report(report)
    print(
        json.dumps(
            {
                "run_id": report["run_id"],
                "dry_run": report["dry_run"],
                "json": str(json_path.relative_to(PROJECT_ROOT)),
                "markdown": str(md_path.relative_to(PROJECT_ROOT)),
                "summary": {
                    "assets_scanned": report["assets_scanned"],
                    "assets_changed": report["assets_changed"],
                    "titles_rewritten": report["titles_rewritten"],
                    "formal_bid_excluded": report["formal_bid_excluded"],
                    "caption_suppressed": report["caption_suppressed"],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    raise SystemExit(main())

#!/usr/bin/env python3
"""Repair Hebei Haoqian reference-template metadata.

河北豪乾资料只能作为格式、目录和写法参考，不得作为泰昌企业事实。
本脚本修复历史入库/后续修复中被误置为 fact source 的 reference metadata。
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

from backend.db.postgres_pool import pooled_connection  # noqa: E402

RUNS_DIR = PROJECT_ROOT / "docs" / "rag" / "runs"
HAOQIAN_OWNER = "河北豪乾电气设备科技有限公司"


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return dict(value) if isinstance(value, dict) else {}


def _repair_reference_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    repaired = dict(metadata)
    repaired.update(
        {
            "source_domain": "reference_template",
            "doc_owner": HAOQIAN_OWNER,
            "reference_only": True,
            "fact_source_allowed_for_enterprise": False,
            "citation_policy": "reference_style_only",
            "authority_level": "reference_template",
            "privacy_level": "reference_only",
            "target_library": "reference_template_library",
            "target_library_label": "参考模板资料",
            "category_label": "参考模板资料",
            "do_not_mix_with": ["泰昌企业事实"],
        }
    )
    return repaired


def run(run_id: str, *, execute: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "run_id": run_id,
        "dry_run": not execute,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents_scanned": 0,
        "documents_updated": 0,
        "chunks_scanned": 0,
        "chunks_updated": 0,
        "samples": [],
    }
    with pooled_connection(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        documents = conn.execute(
            """
            select id, title, category, metadata
            from public.knowledge_documents
            where metadata->>'source_domain' = 'reference_template'
               or metadata->>'doc_owner' = %s
               or title ilike '%%河北豪乾%%'
            """,
            (HAOQIAN_OWNER,),
        ).fetchall()
        report["documents_scanned"] = len(documents)
        for row in documents:
            item = dict(row)
            old_meta = _metadata(item)
            new_meta = _repair_reference_metadata(old_meta)
            new_category = "参考模板资料"
            changed = new_meta != old_meta or item.get("category") != new_category
            if not changed:
                continue
            report["documents_updated"] += 1
            if len(report["samples"]) < 20:
                report["samples"].append(
                    {
                        "type": "document",
                        "id": str(item["id"]),
                        "title": item.get("title"),
                        "old_reference_only": old_meta.get("reference_only"),
                        "old_fact_source_allowed_for_enterprise": old_meta.get("fact_source_allowed_for_enterprise"),
                    }
                )
            if execute:
                conn.execute(
                    "update public.knowledge_documents set category=%s, metadata=%s where id=%s",
                    (new_category, Jsonb(new_meta), item["id"]),
                )

        chunks = conn.execute(
            """
            select id, document_id, left(content, 180) as content_sample, metadata
            from public.document_chunks
            where metadata->>'source_domain' = 'reference_template'
               or metadata->>'doc_owner' = %s
            """,
            (HAOQIAN_OWNER,),
        ).fetchall()
        report["chunks_scanned"] = len(chunks)
        for row in chunks:
            item = dict(row)
            old_meta = _metadata(item)
            new_meta = _repair_reference_metadata(old_meta)
            changed = new_meta != old_meta
            if not changed:
                continue
            report["chunks_updated"] += 1
            if len(report["samples"]) < 40:
                report["samples"].append(
                    {
                        "type": "chunk",
                        "id": str(item["id"]),
                        "old_reference_only": old_meta.get("reference_only"),
                        "old_fact_source_allowed_for_enterprise": old_meta.get("fact_source_allowed_for_enterprise"),
                        "content_sample": item.get("content_sample"),
                    }
                )
            if execute:
                conn.execute(
                    "update public.document_chunks set metadata=%s where id=%s",
                    (Jsonb(new_meta), item["id"]),
                )
        if execute:
            conn.commit()
    return report


def write_report(report: dict[str, Any]) -> tuple[Path, Path]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RUNS_DIR / f"{report['run_id']}.json"
    md_path = RUNS_DIR / f"{report['run_id']}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# {report['run_id']} — 河北豪乾参考稿 metadata 修复",
                "",
                f"- 生成时间：{report['generated_at']}",
                f"- dry_run：{report['dry_run']}",
                f"- documents_scanned：{report['documents_scanned']}",
                f"- documents_updated：{report['documents_updated']}",
                f"- chunks_scanned：{report['chunks_scanned']}",
                f"- chunks_updated：{report['chunks_updated']}",
                "",
                "## 结论",
                "",
                "- 河北豪乾参考稿统一标记为 `source_domain=reference_template`、`reference_only=true`、`fact_source_allowed_for_enterprise=false`、`citation_policy=reference_style_only`。",
                "- 该资料只允许作为格式、目录和写法参考，不得作为泰昌企业事实来源。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")
    report = run(args.run_id, execute=args.execute)
    json_path, md_path = write_report(report)
    print(json.dumps({"run_id": args.run_id, "dry_run": not args.execute, "json": str(json_path.relative_to(PROJECT_ROOT)), "markdown": str(md_path.relative_to(PROJECT_ROOT)), "summary": {k: report[k] for k in ("documents_scanned", "documents_updated", "chunks_scanned", "chunks_updated")}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Repair Taichang RAG source display metadata and isolate internal asset-index chunks."""

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
from backend.services.formal_asset_naming import clean_formal_asset_title  # noqa: E402


RUNS_DIR = PROJECT_ROOT / "docs" / "development" / "runs"
INTERNAL_CHUNK_RE = re.compile(
    r"asset_path\s*:|parsed_outputs/|extract/images/|\btaichang_[a-z0-9_]+|"
    r"^\s*[-*]?\s*(?:evidence_type|target_library|caption|ocr_context)\s*:",
    re.I | re.M,
)
PAGE_MARKER_RE = re.compile(r"[_\-]?(?:页面|页码|page)[_\-\s]*\d+|第\s*\d+\s*页", re.I)


def _clean_source_name(value: Any, fallback: str = "泰昌企业资料") -> str:
    text = clean_formal_asset_title(value, fallback)
    text = PAGE_MARKER_RE.sub("", text)
    text = re.sub(r"^\d{1,3}(?:\.\d{1,3})*[、.．_\-\s]+", "", text).strip()
    text = re.sub(r"_+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[，,。；;：:\-_\s]+$", "", text)
    return text or fallback


def _doc_category(metadata: dict[str, Any], current: Any, title: Any = "") -> str:
    title_text = str(title or "")
    if re.search(r"人员|花名册|社保|参保|劳动合同|陈仙瑞|晁坤琳", title_text):
        return "人员证书"
    for key in ("category_label", "evidence_type_label", "evidence_type", "target_library_label", "target_library"):
        value = metadata.get(key)
        if value:
            label = category_display_name(value)
            if label and label != "电网招投标资料":
                return label
    label = category_display_name(current)
    return "泰昌企业资料" if label == "电网招投标资料" else (label or "泰昌企业资料")


def _source_name_from_metadata(metadata: dict[str, Any]) -> str:
    for key in ("source_file_name", "source_file", "source_document_name"):
        value = str(metadata.get(key) or "").strip()
        if not value:
            continue
        name = Path(value).stem
        cleaned = _clean_source_name(name, "")
        if cleaned:
            return cleaned
    return ""


def _fallback_doc_title(raw_title: str, metadata: dict[str, Any], category: str) -> str:
    generic_titles = {"报告", "投标", "年审计报告", "泰昌企业资料", "企业资料"}
    if raw_title not in generic_titles and len(raw_title) >= 4:
        return raw_title
    source_name = _source_name_from_metadata(metadata)
    if source_name and source_name not in generic_titles:
        return source_name
    return category if category.endswith(("资料", "证书", "报告", "文件")) else f"{category}资料"


def _repair_metadata(metadata: dict[str, Any], *, title: str, category: str) -> dict[str, Any]:
    meta = dict(metadata or {})
    source_name = _clean_source_name(meta.get("source_display_name") or title, title or "泰昌企业资料")
    source_name = _fallback_doc_title(source_name, meta, category)
    meta.update(
        {
            "enterprise": meta.get("enterprise") or "泰昌",
            "doc_owner": meta.get("doc_owner") or "河北泰昌电力器材科技有限公司",
            "source_domain": meta.get("source_domain") or "enterprise_fact",
            "reference_only": False,
            "fact_source_allowed_for_enterprise": True,
            "tenant_visibility": meta.get("tenant_visibility") or "taichang_only",
            "access_scope": meta.get("access_scope") or "taichang_tenant_internal",
            "source_display_name": source_name,
            "source_document_name": source_name,
            "category_label": category,
        }
    )
    if meta.get("evidence_type"):
        meta["evidence_type_label"] = category_display_name(meta.get("evidence_type"))
    if meta.get("target_library"):
        meta["target_library_label"] = category_display_name(meta.get("target_library"))
    return meta


def repair(run_id: str, dry_run: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "run_id": run_id,
        "dry_run": dry_run,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents_scanned": 0,
        "documents_updated": 0,
        "chunks_scanned": 0,
        "chunks_updated": 0,
        "chunks_isolated": 0,
        "samples": [],
    }
    with pooled_connection(_database_url()) as conn:
        docs = conn.execute(
            """
            select id, title, category, metadata
            from public.knowledge_documents
            where coalesce(metadata->>'enterprise', '') = '泰昌'
               or coalesce(metadata->>'doc_owner', '') in ('泰昌', '河北泰昌电力器材科技有限公司')
               or title ilike '%%泰昌%%'
               or metadata::text ilike '%%泰昌%%'
            """
        ).fetchall()
        report["documents_scanned"] = len(docs)
        doc_updates: dict[str, tuple[str, str, dict[str, Any]]] = {}
        for row in docs:
            item = dict(row)
            old_meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            category = _doc_category(old_meta, item.get("category"), item.get("title"))
            title = _clean_source_name(item.get("title"), old_meta.get("source_display_name") or "泰昌企业资料")
            title = _fallback_doc_title(title, old_meta, category)
            new_meta = _repair_metadata(old_meta, title=title, category=category)
            changed = title != item.get("title") or category != item.get("category") or new_meta != old_meta
            if not changed:
                continue
            report["documents_updated"] += 1
            doc_updates[str(item["id"])] = (title, category, new_meta)
            if len(report["samples"]) < 20:
                report["samples"].append({"type": "document", "id": str(item["id"]), "old_title": item.get("title"), "new_title": title, "category": category})
            if not dry_run:
                conn.execute(
                    "update public.knowledge_documents set title=%s, category=%s, metadata=%s::jsonb where id=%s",
                    (title, category, json.dumps(new_meta, ensure_ascii=False), item["id"]),
                )

        chunks = conn.execute(
            """
            select id, document_id, left(content, 800) as content_sample, metadata
            from public.document_chunks
            where coalesce(metadata->>'enterprise', '') = '泰昌'
               or coalesce(metadata->>'doc_owner', '') in ('泰昌', '河北泰昌电力器材科技有限公司')
               or metadata::text ilike '%%泰昌%%'
            """
        ).fetchall()
        report["chunks_scanned"] = len(chunks)
        for row in chunks:
            item = dict(row)
            old_meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            doc_patch = doc_updates.get(str(item.get("document_id")))
            source_title = doc_patch[0] if doc_patch else old_meta.get("source_display_name") or "泰昌企业资料"
            category = doc_patch[1] if doc_patch else _doc_category(old_meta, old_meta.get("category_label"), source_title)
            new_meta = _repair_metadata(old_meta, title=source_title, category=category)
            content_sample = str(item.get("content_sample") or "")
            if INTERNAL_CHUNK_RE.search(content_sample):
                new_meta.update(
                    {
                        "exclude_from_rag": True,
                        "rag_visibility": "internal_only",
                        "status": "superseded",
                        "reference_only": True,
                        "fact_source_allowed_for_enterprise": False,
                        "citation_policy": "metadata_only_not_citable",
                        "source_display_name": "泰昌图片资产解析索引（内部）",
                        "source_document_name": "泰昌图片资产解析索引（内部）",
                        "category_label": "内部解析索引",
                    }
                )
            changed = new_meta != old_meta
            if not changed:
                continue
            report["chunks_updated"] += 1
            if new_meta.get("exclude_from_rag") is True:
                report["chunks_isolated"] += 1
            if len(report["samples"]) < 40:
                report["samples"].append(
                    {
                        "type": "chunk",
                        "id": str(item["id"]),
                        "source_display_name": new_meta.get("source_display_name"),
                        "isolated": bool(new_meta.get("exclude_from_rag")),
                    }
                )
            if not dry_run:
                conn.execute(
                    "update public.document_chunks set metadata=%s::jsonb where id=%s",
                    (json.dumps(new_meta, ensure_ascii=False), item["id"]),
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
        "# 泰昌 RAG 来源展示与内部分块隔离",
        "",
        f"> Run：`{report['run_id']}`",
        f"> dry_run：`{report['dry_run']}`",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 扫描文档 | {report['documents_scanned']} |",
        f"| 更新文档 | {report['documents_updated']} |",
        f"| 扫描分块 | {report['chunks_scanned']} |",
        f"| 更新分块 | {report['chunks_updated']} |",
        f"| 隔离内部分块 | {report['chunks_isolated']} |",
        "",
        "## 样例",
        "",
    ]
    for sample in report["samples"]:
        lines.append(f"- {sample}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_taichang_rag_source_repair")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    report = repair(args.run_id, dry_run=not args.execute)
    json_path, md_path = write_report(report)
    print(json.dumps({
        "run_id": report["run_id"],
        "dry_run": report["dry_run"],
        "json": str(json_path.relative_to(PROJECT_ROOT)),
        "markdown": str(md_path.relative_to(PROJECT_ROOT)),
        "summary": {
            "documents_scanned": report["documents_scanned"],
            "documents_updated": report["documents_updated"],
            "chunks_scanned": report["chunks_scanned"],
            "chunks_updated": report["chunks_updated"],
            "chunks_isolated": report["chunks_isolated"],
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    raise SystemExit(main())

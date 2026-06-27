#!/usr/bin/env python3
"""Audit Taichang formal asset display quality for bid delivery.

This script is read-only. It scans the real PostgreSQL RAG/asset tables and
local Taichang staging payloads, then writes JSON + Markdown reports used by
the formal asset cleanup P0 task.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.postgres_compat import _database_url  # noqa: E402
from backend.db.postgres_pool import pooled_connection  # noqa: E402


RUNS_DIR = PROJECT_ROOT / "docs" / "development" / "runs"
STAGING_ROOT = PROJECT_ROOT / "parsed_outputs" / "power_grid_customer_corpus"

INTERNAL_TOKEN_RE = re.compile(
    r"taichang_|power_grid_|production_capacity|testing_capacity|green_low_carbon|"
    r"business_license|certification|product_library|qualification_library|"
    r"source_display_name|asset_id|target_library|source_domain",
    re.I,
)
CONTENT_INTERNAL_TOKEN_RE = re.compile(
    r"taichang_|power_grid_|production_capacity|testing_capacity|green_low_carbon|"
    r"business_license|product_library|qualification_library|source_display_name|"
    r"asset_id|target_library|source_domain|evidence_type\s*:",
    re.I,
)
TRACE_MARKER_RE = re.compile(
    r"原图|页面[_-]?\d+|第\s*\d+\s*页|第[一二三四五六七八九十百]+页|"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)
API_PATH_RE = re.compile(r"/api/(?:bidding/)?knowledge/assets|parsed_outputs/|rag_seed/", re.I)
TRACE_PATH_RE = re.compile(r"parsed_outputs/|rag_seed/|extract/images|/api/(?:bidding/)?knowledge/assets", re.I)
FORMAL_CAPTION_BLOCK_RE = re.compile(
    r"^图示：|^图片：|^资料：.*(?:原图|页面[_-]?\d+|检验报告.*第\s*\d+\s*页)",
)
BAD_LOCAL_CUT_RE = re.compile(r"二维码|条码|印章|签名|页脚|页眉|局部|切图|表格单元格|装饰")
ENGLISH_OR_PINYIN_FILE_RE = re.compile(r"[A-Za-z_]{3,}")

FORMAL_UNSAFE_EVIDENCE_TYPES = {
    "restricted_signature_seal",
    "signature",
    "seal",
}


def _json_text(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, default=str)


def _text(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return _json_text(value)
    return str(value or "")


def _compact(text: str, limit: int = 180) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    return value[:limit]


def _has_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def _asset_blob(row: dict[str, Any]) -> str:
    return "\n".join(
        _text(row.get(key))
        for key in [
            "title",
            "description",
            "category",
            "asset_type",
            "source_type",
            "file_name",
            "local_path",
            "tags",
            "applicable_sections",
            "applicable_volumes",
            "metadata",
            "specs",
            "ai_caption",
            "searchable_text",
        ]
    )


def _is_full_page_asset(row: dict[str, Any]) -> bool:
    metadata = _metadata(row)
    specs = _specs(row)
    asset_visual_type = _text(metadata.get("asset_visual_type") or specs.get("asset_visual_type") or row.get("source_type"))
    return bool(
        metadata.get("full_page") is True
        or specs.get("full_page") is True
        or "full_page" in asset_visual_type
        or row.get("source_type") == "customer_pdf_full_page_render"
    )


def _display_blob(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    specs = row.get("specs") if isinstance(row.get("specs"), dict) else {}
    return "\n".join(
        _text(value)
        for value in [
            row.get("title"),
            row.get("description"),
            row.get("category"),
            row.get("tags"),
            row.get("applicable_sections"),
            metadata.get("formal_display_title"),
            metadata.get("formal_caption"),
            metadata.get("source_display_name"),
            metadata.get("category_label"),
            metadata.get("evidence_type_label"),
            metadata.get("target_library_label"),
            specs.get("formal_display_title"),
            specs.get("formal_caption"),
            specs.get("display_name"),
        ]
    )


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("metadata") if isinstance(row.get("metadata"), dict) else {}


def _specs(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("specs") if isinstance(row.get("specs"), dict) else {}


def _is_allowed_for_bid(row: dict[str, Any]) -> bool:
    metadata = _metadata(row)
    specs = _specs(row)
    if metadata.get("allowed_for_bid") is False or specs.get("allowed_for_bid") is False:
        return False
    return True


def _asset_issues(row: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    display = _display_blob(row)
    blob = _asset_blob(row)
    metadata = _metadata(row)
    specs = _specs(row)
    trace_blob = "\n".join(_text(value) for value in [row.get("file_name"), row.get("local_path"), metadata.get("source_file"), metadata.get("page_no"), specs.get("page_no")])

    if INTERNAL_TOKEN_RE.search(display):
        issues.append({"code": "display_internal_token", "severity": "blocker", "evidence": _compact(display)})
    if TRACE_MARKER_RE.search(display):
        issues.append({"code": "display_trace_marker", "severity": "blocker", "evidence": _compact(display)})
    if API_PATH_RE.search(display):
        issues.append({"code": "display_path_or_api", "severity": "blocker", "evidence": _compact(display)})
    if not _has_chinese(_text(row.get("title"))):
        issues.append({"code": "title_without_chinese", "severity": "high", "evidence": _compact(_text(row.get("title")))})
    if FORMAL_CAPTION_BLOCK_RE.search(_text(row.get("ai_caption"))) or FORMAL_CAPTION_BLOCK_RE.search(_text(row.get("description"))):
        issues.append({"code": "caption_formal_unsafe", "severity": "blocker", "evidence": _compact(_text(row.get("ai_caption")) or _text(row.get("description")))})
    if BAD_LOCAL_CUT_RE.search(blob) and not _is_full_page_asset(row):
        issues.append({"code": "suspected_local_cut_or_noise", "severity": "high", "evidence": _compact(blob)})
    if TRACE_PATH_RE.search(trace_blob):
        issues.append({"code": "trace_field_contains_path", "severity": "info", "evidence": _compact(trace_blob)})
    if (
        ENGLISH_OR_PINYIN_FILE_RE.search(_text(row.get("file_name")))
        and not _has_chinese(_text(row.get("file_name")))
        and not _has_chinese(display)
    ):
        issues.append({"code": "file_name_non_chinese_without_display_name", "severity": "medium", "evidence": _compact(_text(row.get("file_name")))})

    evidence_type = _text(metadata.get("evidence_type") or specs.get("evidence_type"))
    if evidence_type in FORMAL_UNSAFE_EVIDENCE_TYPES and _is_allowed_for_bid(row):
        issues.append({"code": "restricted_asset_allowed_for_bid", "severity": "blocker", "evidence": evidence_type})

    asset_visual_type = _text(metadata.get("asset_visual_type") or specs.get("asset_visual_type") or row.get("source_type"))
    full_page = metadata.get("full_page")
    if _is_allowed_for_bid(row) and asset_visual_type and "mineru" in asset_visual_type.lower() and full_page is not True:
        issues.append({"code": "mineru_partial_allowed_for_bid", "severity": "blocker", "evidence": asset_visual_type})

    if _is_allowed_for_bid(row) and TRACE_MARKER_RE.search(_text(row.get("title"))):
        issues.append({"code": "bid_allowed_title_trace_marker", "severity": "blocker", "evidence": _compact(_text(row.get("title")))})
    return issues


def _source_issues(row: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    display = "\n".join(
        _text(value)
        for value in [
            row.get("title"),
            row.get("category"),
            meta.get("source_display_name"),
            meta.get("category_label"),
            meta.get("evidence_type_label"),
            meta.get("target_library_label"),
        ]
    )
    if INTERNAL_TOKEN_RE.search(display):
        issues.append({"code": "source_display_internal_token", "severity": "blocker", "evidence": _compact(display)})
    if TRACE_MARKER_RE.search(display):
        issues.append({"code": "source_display_trace_marker", "severity": "high", "evidence": _compact(display)})
    if API_PATH_RE.search(display):
        issues.append({"code": "source_display_path_or_api", "severity": "blocker", "evidence": _compact(display)})
    return issues


def _load_staging_payloads() -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if not STAGING_ROOT.exists():
        return payloads
    for path in sorted(STAGING_ROOT.glob("customer*taichang*/**/asset_staging_payloads.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            payloads.append({"path": str(path.relative_to(PROJECT_ROOT)), "error": str(exc), "payload": None})
            continue
        for item in data.get("assets") or []:
            payloads.append({"path": str(path.relative_to(PROJECT_ROOT)), "payload": item})
    return payloads


def _staging_issues(item: dict[str, Any]) -> list[dict[str, str]]:
    payload = item.get("payload")
    if not isinstance(payload, dict):
        return [{"code": "staging_payload_read_error", "severity": "high", "evidence": _text(item.get("error"))}]
    row = {
        "title": payload.get("title"),
        "description": payload.get("description"),
        "category": payload.get("category"),
        "asset_type": payload.get("asset_type"),
        "source_type": payload.get("source_type"),
        "file_name": payload.get("file_name"),
        "local_path": payload.get("local_path"),
        "tags": payload.get("tags"),
        "applicable_sections": payload.get("applicable_sections"),
        "applicable_volumes": payload.get("applicable_volumes"),
        "metadata": payload.get("metadata"),
        "specs": payload.get("specs"),
        "ai_caption": payload.get("ai_caption"),
        "searchable_text": payload.get("searchable_text"),
    }
    return _asset_issues(row)


def _fetch_assets() -> list[dict[str, Any]]:
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        return conn.execute(
            """
            select id, title, description, category, asset_type, file_name, local_path,
                   source_type, tags, applicable_sections, applicable_volumes,
                   metadata, specs, ai_caption, searchable_text, status, created_at, updated_at
            from public.knowledge_assets
            where coalesce(metadata->>'enterprise', '') = %s
               or coalesce(metadata->>'doc_owner', '') in (%s, %s)
               or title ilike %s
               or metadata::text ilike %s
            order by created_at nulls last, title
            """,
            ["泰昌", "泰昌", "河北泰昌电力器材科技有限公司", "%泰昌%", "%泰昌%"],
        ).fetchall()


def _fetch_documents() -> list[dict[str, Any]]:
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        return conn.execute(
            """
            select id, title, category, metadata, status, created_at
            from public.knowledge_documents
            where coalesce(metadata->>'enterprise', '') = %s
               or coalesce(metadata->>'doc_owner', '') in (%s, %s)
               or title ilike %s
               or metadata::text ilike %s
            order by created_at nulls last, title
            """,
            ["泰昌", "泰昌", "河北泰昌电力器材科技有限公司", "%泰昌%", "%泰昌%"],
        ).fetchall()


def _fetch_chunks(limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        select id, document_id, left(content, 500) as content_sample, metadata
        from public.document_chunks
        where coalesce(metadata->>'enterprise', '') = %s
           or coalesce(metadata->>'doc_owner', '') in (%s, %s)
           or metadata::text ilike %s
        order by id
    """
    params: list[Any] = ["泰昌", "泰昌", "河北泰昌电力器材科技有限公司", "%泰昌%"]
    if limit:
        sql += " limit %s"
        params.append(limit)
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def _summarize_issues(records: list[dict[str, Any]], issue_key: str = "issues") -> dict[str, Any]:
    by_code: Counter[str] = Counter()
    by_severity: Counter[str] = Counter()
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        for issue in record.get(issue_key) or []:
            code = issue["code"]
            by_code[code] += 1
            by_severity[issue.get("severity") or "unknown"] += 1
            if len(samples[code]) < 8:
                samples[code].append(
                    {
                        "id": record.get("id"),
                        "title": record.get("title"),
                        "source": record.get("source"),
                        "evidence": issue.get("evidence"),
                    }
                )
    return {
        "by_code": dict(by_code),
        "by_severity": dict(by_severity),
        "samples": samples,
    }


def _non_info_issues(record: dict[str, Any]) -> list[dict[str, str]]:
    return [issue for issue in record.get("issues") or [] if issue.get("severity") != "info"]


def _info_issues(record: dict[str, Any]) -> list[dict[str, str]]:
    return [issue for issue in record.get("issues") or [] if issue.get("severity") == "info"]


def _chunk_excluded_from_rag(metadata: dict[str, Any]) -> bool:
    return bool(
        metadata.get("exclude_from_rag") is True
        or str(metadata.get("rag_visibility") or "").lower() == "internal_only"
        or str(metadata.get("status") or "").lower() in {"superseded", "disabled", "archived"}
    )


def build_report(run_id: str, *, chunk_limit: int | None = None) -> dict[str, Any]:
    assets = [dict(row) for row in _fetch_assets()]
    documents = [dict(row) for row in _fetch_documents()]
    chunks = [dict(row) for row in _fetch_chunks(limit=chunk_limit)]
    staging_items = _load_staging_payloads()

    asset_records: list[dict[str, Any]] = []
    for row in assets:
        issues = _asset_issues(row)
        asset_records.append(
            {
                "id": str(row.get("id")),
                "title": row.get("title"),
                "category": row.get("category"),
                "asset_type": row.get("asset_type"),
                "source_type": row.get("source_type"),
                "allowed_for_bid": _is_allowed_for_bid(row),
                "evidence_type": _metadata(row).get("evidence_type") or _specs(row).get("evidence_type"),
                "target_library": _metadata(row).get("target_library") or _specs(row).get("target_library"),
                "asset_visual_type": _metadata(row).get("asset_visual_type") or _specs(row).get("asset_visual_type"),
                "source_display_name": _metadata(row).get("source_display_name"),
                "source_file": _metadata(row).get("source_file"),
                "issues": issues,
            }
        )

    document_records: list[dict[str, Any]] = []
    for row in documents:
        issues = _source_issues(row)
        document_records.append(
            {
                "id": str(row.get("id")),
                "title": row.get("title"),
                "category": row.get("category"),
                "source_display_name": (row.get("metadata") or {}).get("source_display_name") if isinstance(row.get("metadata"), dict) else None,
                "issues": issues,
            }
        )

    chunk_records: list[dict[str, Any]] = []
    for row in chunks:
        issues = _source_issues({"title": "", "category": "", "metadata": row.get("metadata")})
        content = _text(row.get("content_sample"))
        chunk_metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if _chunk_excluded_from_rag(chunk_metadata):
            if INTERNAL_TOKEN_RE.search(content) or API_PATH_RE.search(content):
                issues.append({"code": "isolated_internal_chunk", "severity": "info", "evidence": _compact(content)})
        else:
            if CONTENT_INTERNAL_TOKEN_RE.search(content):
                issues.append({"code": "chunk_content_internal_token", "severity": "high", "evidence": _compact(content)})
            if API_PATH_RE.search(content):
                issues.append({"code": "chunk_content_path_or_api", "severity": "blocker", "evidence": _compact(content)})
        chunk_records.append(
            {
                "id": str(row.get("id")),
                "document_id": str(row.get("document_id")),
                "source_display_name": (row.get("metadata") or {}).get("source_display_name") if isinstance(row.get("metadata"), dict) else None,
                "issues": issues,
            }
        )

    staging_records: list[dict[str, Any]] = []
    for item in staging_items:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        issues = _staging_issues(item)
        staging_records.append(
            {
                "source": item.get("path"),
                "title": payload.get("title"),
                "category": payload.get("category"),
                "source_display_name": (payload.get("metadata") or {}).get("source_display_name") if isinstance(payload.get("metadata"), dict) else None,
                "issues": issues,
            }
        )

    problem_assets = [{**item, "issues": _non_info_issues(item)} for item in asset_records if _non_info_issues(item)]
    trace_assets = [{**item, "issues": _info_issues(item)} for item in asset_records if _info_issues(item)]
    problem_documents = [item for item in document_records if item["issues"]]
    problem_chunks = [{**item, "issues": _non_info_issues(item)} for item in chunk_records if _non_info_issues(item)]
    trace_chunks = [{**item, "issues": _info_issues(item)} for item in chunk_records if _info_issues(item)]
    problem_staging = [item for item in staging_records if item["issues"]]

    return {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "taichang_formal_asset_cleanup_audit",
        "chunk_limit": chunk_limit,
        "summary": {
            "assets_scanned": len(asset_records),
            "assets_with_issues": len(problem_assets),
            "documents_scanned": len(document_records),
            "documents_with_issues": len(problem_documents),
            "chunks_scanned": len(chunk_records),
            "chunks_with_issues": len(problem_chunks),
            "staging_payloads_scanned": len(staging_records),
            "staging_payloads_with_issues": len(problem_staging),
        },
        "asset_issue_summary": _summarize_issues(problem_assets),
        "asset_trace_summary": _summarize_issues(trace_assets),
        "document_issue_summary": _summarize_issues(problem_documents),
        "chunk_issue_summary": _summarize_issues(problem_chunks),
        "chunk_trace_summary": _summarize_issues(trace_chunks),
        "staging_issue_summary": _summarize_issues(problem_staging),
        "problem_assets": problem_assets,
        "trace_assets": trace_assets[:500],
        "problem_documents": problem_documents[:500],
        "problem_chunks": problem_chunks[:500],
        "trace_chunks": trace_chunks[:500],
        "problem_staging_payloads": problem_staging[:500],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    lines = [
        "# 泰昌正式资料资产中文化与配图质量审计",
        "",
        f"> Run：`{report['run_id']}`",
        f"> 生成时间：{report['generated_at']}",
        "",
        "## 结论",
        "",
        "| 范围 | 扫描数 | 问题数 |",
        "| --- | ---: | ---: |",
        f"| 真实图片资产 | {summary['assets_scanned']} | {summary['assets_with_issues']} |",
        f"| 知识文档 | {summary['documents_scanned']} | {summary['documents_with_issues']} |",
        f"| 文档分块 | {summary['chunks_scanned']} | {summary['chunks_with_issues']} |",
        f"| staging 图片 payload | {summary['staging_payloads_scanned']} | {summary['staging_payloads_with_issues']} |",
        "",
        "## 图片资产问题分布",
        "",
        "| 问题代码 | 数量 |",
        "| --- | ---: |",
    ]
    for code, count in sorted(report["asset_issue_summary"]["by_code"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{code}` | {count} |")
    lines.extend(["", "## 典型样例", ""])
    for code, samples in report["asset_issue_summary"]["samples"].items():
        lines.append(f"### {code}")
        lines.append("")
        for sample in samples[:5]:
            lines.append(f"- `{sample.get('id') or '-'}` {sample.get('title') or sample.get('source') or '-'}：{sample.get('evidence') or ''}")
        lines.append("")

    lines.extend(
        [
            "## 后续处理要求",
            "",
            "1. 先修复正式展示字段、RAG 选图 caption 和正式导出门禁，再批量回填数据。",
            "2. 对 `bid_allowed_title_trace_marker`、`display_trace_marker`、`display_internal_token` 命中的资产优先处理。",
            "3. 对疑似局部切图、二维码、印章、签名、页脚等资产设置 `allowed_for_bid=false` 或迁移为复核线索。",
            "4. 修复后必须重跑 Base + 泰昌专项增量门禁、真实 `/api/knowledge/search/stream`、技术标/商务标真实 DOCX 导出和阿里云线上复验。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_taichang_formal_asset_audit")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--chunk-limit", type=int, default=None, help="limit chunk scan for debugging; default scans all matching chunks")
    args = parser.parse_args()

    report = build_report(args.run_id, chunk_limit=args.chunk_limit)
    json_out = args.json_out or RUNS_DIR / f"{args.run_id}.json"
    md_out = args.md_out or RUNS_DIR / f"{args.run_id}.md"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_markdown(report, md_out)
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "json": str(json_out.relative_to(PROJECT_ROOT)),
                "markdown": str(md_out.relative_to(PROJECT_ROOT)),
                "summary": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    raise SystemExit(main())

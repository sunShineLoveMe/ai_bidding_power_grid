#!/usr/bin/env python3
"""Run MinerU OCR for Taichang supplemental scanned PDFs and refresh manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.parsing.mineru_client import (  # noqa: E402
    create_local_file_batch_task,
    download_and_extract_zip,
    has_mineru_token,
    wait_for_batch_file_result,
)
from scripts.rag.stage_taichang_supplement_20260611 import (  # noqa: E402
    BATCH_ID,
    ENTERPRISE_SHORT,
    ENTERPRISE_FULL,
    OUT_ROOT,
    _category_label,
    _is_sensitive,
    _rel,
    _safe_stem,
)

MIN_TEXT_CHARS = 1000
OCR_BATCH_DIR = OUT_ROOT / "mineru_batch_p1b_ocr"
REPORT_JSON = OUT_ROOT / "p1b_mineru_ocr_report.json"
REPORT_MD = OUT_ROOT / "p1b_mineru_ocr_report.md"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _candidate_reason(record: dict[str, Any], min_text_chars: int) -> str | None:
    if record.get("suffix") != ".pdf":
        return None
    if str(record.get("auto_usage_policy") or "").startswith("restricted"):
        return None
    text_chars = int(record.get("text_chars") or 0)
    if text_chars == 0:
        return "no_extractable_text"
    if text_chars < min_text_chars:
        return f"low_extractable_text<{min_text_chars}"
    if record.get("output_file"):
        return None
    return "missing_text_manifest"


def _select_candidates(inventory: dict[str, Any], *, min_text_chars: int, limit: int | None) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in inventory.get("records") or []:
        reason = _candidate_reason(record, min_text_chars)
        if not reason:
            continue
        item = dict(record)
        item["ocr_reason"] = reason
        candidates.append(item)
    candidates.sort(key=lambda r: (int(r.get("pdf_pages") or 0), r.get("source_file") or ""))
    return candidates[:limit] if limit else candidates


def _metadata_for_record(record: dict[str, Any], *, parser: str) -> dict[str, Any]:
    evidence_type = record["evidence_type"]
    return {
        "seed_corpus": "power_grid_customer_corpus",
        "source_domain": "enterprise_fact",
        "province": "河北",
        "batch_no": "taichang_supplement_20260611",
        "package_no": "",
        "package_code": "2225AC",
        "material_category": "电缆保护管CPVC/MPP",
        "doc_role": "enterprise_evidence",
        "source_file": record["source_file"],
        "source_display_name": Path(record["source_file"]).stem,
        "source_category": "05_enterprise_documents",
        "category_label": _category_label(evidence_type),
        "chunker": "parent_child_v2",
        "ingestion_batch_id": BATCH_ID,
        "doc_version": 2 if parser == "mineru_ocr" else 1,
        "status": "parsed_pending_ingestion",
        "doc_owner": ENTERPRISE_SHORT,
        "enterprise": ENTERPRISE_SHORT,
        "source_type": "pdf_ocr",
        "parser": parser,
        "evidence_type": evidence_type,
        "evidence_type_label": _category_label(evidence_type),
        "target_library": record["target_library"],
        "target_library_label": record["target_library_label"],
        "privacy_level": "taichang_internal_private" if _is_sensitive(evidence_type, record["source_file"]) else "private",
        "reference_only": False,
        "fact_source_allowed_for_enterprise": True,
        "access_scope": "taichang_tenant_internal",
        "tenant_visibility": "taichang_only",
        "sensitive_handling": "taichang_internal_use_no_redaction_required",
        "do_not_mix_with": ["河北豪乾参考稿", "辽宁招标资料"],
        "ocr_enhanced": True,
        "ocr_engine": "MinerU",
    }


def _manifest_record(record: dict[str, Any], markdown_path: Path, markdown_text: str) -> dict[str, Any]:
    return {
        "source_file": record["source_file"],
        "output_file": _rel(markdown_path),
        "province": "河北",
        "batch_no": "taichang_supplement_20260611",
        "package_no": "",
        "package_code": "2225AC",
        "material_category": "电缆保护管CPVC/MPP",
        "doc_role": "enterprise_evidence",
        "qualification_mode": None,
        "source_type": "pdf",
        "parser": "mineru_ocr",
        "parse_status": "parsed",
        "sha256": _sha256_text(markdown_text),
        "file_size": (PROJECT_ROOT / record["source_file"]).stat().st_size,
        "text_chars": len(markdown_text.strip()),
        "metadata": _metadata_for_record(record, parser="mineru_ocr"),
    }


def _run_one(record: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    source_path = PROJECT_ROOT / record["source_file"]
    output_dir = OCR_BATCH_DIR / _safe_stem(record["source_file"])
    if dry_run:
        return {
            "source_file": record["source_file"],
            "status": "dry_run",
            "ocr_reason": record["ocr_reason"],
            "pdf_pages": record.get("pdf_pages"),
            "text_chars_before": record.get("text_chars"),
            "output_dir": _rel(output_dir),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    data_id = f"{BATCH_ID}_p1b_ocr_{hashlib.sha1(record['source_file'].encode('utf-8')).hexdigest()[:12]}"
    task = create_local_file_batch_task(
        local_file_path=source_path,
        file_name=source_path.name,
        data_id=data_id,
        is_ocr=True,
    )
    result = wait_for_batch_file_result(batch_id=task.batch_id, data_id=data_id)
    full_zip_url = result.get("full_zip_url")
    if not full_zip_url:
        raise RuntimeError(f"MinerU finished without full_zip_url: {result}")
    artifacts = download_and_extract_zip(full_zip_url, output_dir)
    markdown_path = Path(artifacts.get("markdown_path") or "")
    markdown_text = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    status = {
        "source_file": record["source_file"],
        "status": "mineru_done",
        "ocr_reason": record["ocr_reason"],
        "pdf_pages": record.get("pdf_pages"),
        "text_chars_before": record.get("text_chars"),
        "text_chars_after": len(markdown_text.strip()),
        "batch_id": task.batch_id,
        "data_id": data_id,
        "output_dir": _rel(output_dir),
        "artifacts": {key: _rel(Path(value)) if isinstance(value, str) and Path(value).is_absolute() else value for key, value in artifacts.items()},
    }
    _write_json(output_dir / "status.json", status)
    return status


def _update_manifest(manifest: dict[str, Any], candidates_by_source: dict[str, dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    records = list(manifest.get("records") or [])
    by_source = {record.get("source_file"): index for index, record in enumerate(records)}
    updated_sources: list[str] = []
    for result in results:
        if result.get("status") != "mineru_done":
            continue
        artifacts = result.get("artifacts") or {}
        markdown_path = PROJECT_ROOT / artifacts.get("markdown_path") if artifacts.get("markdown_path") else None
        if not markdown_path or not markdown_path.exists():
            continue
        markdown_text = markdown_path.read_text(encoding="utf-8")
        source_file = result["source_file"]
        next_record = _manifest_record(candidates_by_source[source_file], markdown_path, markdown_text)
        if source_file in by_source:
            records[by_source[source_file]] = next_record
        else:
            records.append(next_record)
        updated_sources.append(source_file)
    manifest["records"] = records
    manifest["updated_at"] = _now()
    manifest["last_ocr_refresh"] = {
        "engine": "MinerU",
        "batch_dir": _rel(OCR_BATCH_DIR),
        "updated_sources": updated_sources,
    }
    return manifest


def _write_report(report: dict[str, Any]) -> None:
    _write_json(REPORT_JSON, report)
    lines = [
        "# 泰昌补充包扫描 PDF MinerU OCR 增强报告",
        "",
        f"> 批次：`{report['batch_id']}`",
        f"> 生成时间：{report['generated_at']}",
        f"> dry-run：`{report['dry_run']}`",
        "",
        "## 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 候选 PDF | {report['summary']['candidates']} |",
        f"| MinerU 完成 | {report['summary']['mineru_done']} |",
        f"| 失败 | {report['summary']['failed']} |",
        f"| Manifest 更新 | {report['summary']['manifest_updated']} |",
        "",
        "## 明细",
        "",
        "| 状态 | 页数 | 原文本量 | OCR 文本量 | 文件 | 原因 |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for item in report["results"]:
        lines.append(
            f"| `{item.get('status')}` | {item.get('pdf_pages') or 0} | {item.get('text_chars_before') or 0} | "
            f"{item.get('text_chars_after') or 0} | `{Path(item.get('source_file') or '').name}` | {item.get('ocr_reason') or '-'} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--min-text-chars", type=int, default=MIN_TEXT_CHARS)
    args = parser.parse_args()

    if not args.dry_run and not has_mineru_token():
        raise RuntimeError("MINERU_API_TOKEN or MINERU_TOKEN is required")

    inventory_path = OUT_ROOT / "inventory.json"
    manifest_path = OUT_ROOT / "manifest.json"
    inventory = _load_json(inventory_path)
    manifest = _load_json(manifest_path)
    candidates = _select_candidates(inventory, min_text_chars=args.min_text_chars, limit=args.limit)
    candidates_by_source = {item["source_file"]: item for item in candidates}

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            results.append(_run_one(candidate, dry_run=args.dry_run))
        except Exception as exc:
            results.append({
                "source_file": candidate["source_file"],
                "status": "failed",
                "ocr_reason": candidate["ocr_reason"],
                "pdf_pages": candidate.get("pdf_pages"),
                "text_chars_before": candidate.get("text_chars"),
                "error": str(exc),
            })

    manifest_updated = 0
    if not args.dry_run:
        before = json.dumps(manifest.get("records") or [], ensure_ascii=False, sort_keys=True)
        manifest = _update_manifest(manifest, candidates_by_source, results)
        after = json.dumps(manifest.get("records") or [], ensure_ascii=False, sort_keys=True)
        manifest_updated = len((manifest.get("last_ocr_refresh") or {}).get("updated_sources") or [])
        if before != after:
            _write_json(manifest_path, manifest)

    report = {
        "batch_id": BATCH_ID,
        "generated_at": _now(),
        "dry_run": args.dry_run,
        "inventory": _rel(inventory_path),
        "manifest": _rel(manifest_path),
        "ocr_batch_dir": _rel(OCR_BATCH_DIR),
        "summary": {
            "candidates": len(candidates),
            "mineru_done": sum(1 for result in results if result.get("status") == "mineru_done"),
            "failed": sum(1 for result in results if result.get("status") == "failed"),
            "manifest_updated": manifest_updated,
        },
        "results": results,
    }
    _write_report(report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Report: {_rel(REPORT_MD)}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

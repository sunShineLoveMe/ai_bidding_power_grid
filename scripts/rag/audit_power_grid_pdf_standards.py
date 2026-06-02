#!/usr/bin/env python3
"""Audit downloaded power-grid PDF standard seed files before ingestion.

The power-grid seed index intentionally skipped PDFs in the first ingestion pass.
Before enabling PDF ingestion, verify that each downloaded PDF actually matches
the title recorded in index.csv. A few source URLs can point to unrelated public
attachments, and blindly indexing them would pollute the technical-standard RAG
corpus.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_ROOT = PROJECT_ROOT / "rag_seed" / "power_grid_resources"
DEFAULT_MD_OUT = PROJECT_ROOT / "docs" / "rag" / "runs" / "run_20260602_pdf_standard_audit.md"
DEFAULT_JSON_OUT = PROJECT_ROOT / "docs" / "rag" / "runs" / "run_20260602_pdf_standard_audit.json"


@dataclass
class AuditResult:
    title: str
    file_path: str
    source_url: str
    doc_type: str
    pages: int | None
    extracted_chars: int
    matched_terms: list[str]
    missing_terms: list[str]
    status: str
    preview: str
    error: str | None = None


def _normalize(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text or "", flags=re.UNICODE).lower()


def _title_terms(title: str) -> list[str]:
    terms: list[str] = []
    code_match = re.match(r"^([A-Z]+(?:/[A-Z]+)?(?:\s*/\s*[A-Z]+)?\s*\d+(?:[-—]\d+)?)", title, flags=re.I)
    if code_match:
        code = code_match.group(1)
        terms.append(code)
        terms.append(re.sub(r"\s+", "", code))
    cleaned = re.sub(r"^[A-Z]+(?:/[A-Z]+)?(?:\s*/\s*[A-Z]+)?\s*\d+(?:[-—]\d+)?\s*", "", title, flags=re.I)
    cleaned = re.sub(r"[-—]\d{4}\s*", "", cleaned)
    for piece in re.split(r"[，,、（）() ]+", cleaned):
        piece = piece.strip()
        if len(piece) >= 4:
            terms.append(piece)
    # Keep order while removing duplicates.
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = _normalize(term)
        if key and key not in seen:
            deduped.append(term)
            seen.add(key)
    return deduped[:8]


def _extract_pdf_text(path: Path, max_pages: int) -> tuple[int, str]:
    import PyPDF2

    text_parts: list[str] = []
    with path.open("rb") as f:
        reader = PyPDF2.PdfReader(f)
        pages = len(reader.pages)
        for page in reader.pages[:max_pages]:
            text_parts.append(page.extract_text() or "")
    return pages, "\n".join(text_parts)


def _audit_row(row: dict[str, str], max_pages: int) -> AuditResult:
    rel_path = row["file_path"]
    path = SEED_ROOT / rel_path
    if not path.exists():
        return AuditResult(
            title=row["title"],
            file_path=rel_path,
            source_url=row.get("source_url", ""),
            doc_type=row.get("doc_type", ""),
            pages=None,
            extracted_chars=0,
            matched_terms=[],
            missing_terms=_title_terms(row["title"]),
            status="missing_file",
            preview="",
            error="file does not exist",
        )
    try:
        pages, text = _extract_pdf_text(path, max_pages)
    except Exception as exc:  # noqa: BLE001 - audit should keep scanning all files.
        return AuditResult(
            title=row["title"],
            file_path=rel_path,
            source_url=row.get("source_url", ""),
            doc_type=row.get("doc_type", ""),
            pages=None,
            extracted_chars=0,
            matched_terms=[],
            missing_terms=_title_terms(row["title"]),
            status="extract_failed",
            preview="",
            error=str(exc),
        )

    normalized_text = _normalize(text)
    terms = _title_terms(row["title"])
    matched = [term for term in terms if _normalize(term) in normalized_text]
    missing = [term for term in terms if term not in matched]
    code_terms = [term for term in terms if re.search(r"\d", term) and re.search(r"[A-Za-z]", term)]
    code_matched = any(term in matched for term in code_terms)
    expected_is_standard = row.get("doc_type", "").endswith("PDF") and row.get("category") == "03_standards_specs"
    unrelated_standard_marker = bool(
        code_terms
        and
        re.search(r"\bHJ\s*/?\s*T?\s*\d+|\bHJ\d+|\bNB\s*/\s*T\s*\d+", text, flags=re.I)
        and not code_matched
    )

    if not text.strip():
        status = "empty_text"
    elif expected_is_standard and ((code_terms and not code_matched) or unrelated_standard_marker):
        status = "mismatch"
    elif len(matched) >= 2 or (matched and len(terms) <= 2):
        status = "match"
    elif matched:
        status = "weak_match"
    else:
        status = "mismatch"
    preview = re.sub(r"\s+", " ", text).strip()[:240]
    return AuditResult(
        title=row["title"],
        file_path=rel_path,
        source_url=row.get("source_url", ""),
        doc_type=row.get("doc_type", ""),
        pages=pages,
        extracted_chars=len(text),
        matched_terms=matched,
        missing_terms=missing,
        status=status,
        preview=preview,
    )


def load_pdf_standard_rows() -> list[dict[str, str]]:
    rows = list(csv.DictReader((SEED_ROOT / "index.csv").open(encoding="utf-8-sig")))
    return [
        row
        for row in rows
        if row.get("category") == "03_standards_specs"
        and Path(row.get("file_path", "")).suffix.lower() == ".pdf"
        and row.get("status") == "downloaded"
    ]


def _write_json(results: list[AuditResult], output: Path, max_pages: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "max_pages": max_pages,
        "summary": _summary(results),
        "results": [asdict(result) for result in results],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _summary(results: list[AuditResult]) -> dict[str, int]:
    statuses = sorted({result.status for result in results})
    summary = {status: sum(1 for result in results if result.status == status) for status in statuses}
    summary["total"] = len(results)
    return summary


def _write_markdown(results: list[AuditResult], output: Path, max_pages: int, json_output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = _summary(results)
    lines = [
        "# PDF 标准源文件审计",
        "",
        f"> 生成时间：{datetime.now(timezone.utc).isoformat()}",
        f"> 扫描页数：前 {max_pages} 页",
        f"> JSON 结果：`{json_output.relative_to(PROJECT_ROOT)}`",
        "",
        "## 结论",
        "",
        "- `match` 可进入后续解析/分块样板。",
        "- `weak_match` 需要人工抽查后再入库。",
        "- `mismatch` / `empty_text` / `extract_failed` 不得直接入库，需重新采集或走 MinerU/OCR 后复核。",
        "",
        "## 统计",
        "",
        "| 状态 | 数量 |",
        "| --- | ---: |",
    ]
    for status, count in summary.items():
        if status != "total":
            lines.append(f"| `{status}` | {count} |")
    lines.extend([
        f"| **合计** | **{summary['total']}** |",
        "",
        "## 明细",
        "",
        "| 状态 | 标题 | 页数 | 抽取字符 | 命中项 | 缺失项 | 内容预览 |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ])
    for result in results:
        matched = "、".join(f"`{item}`" for item in result.matched_terms) or "-"
        missing = "、".join(f"`{item}`" for item in result.missing_terms) or "-"
        preview = result.preview.replace("|", "\\|") or (result.error or "")
        lines.append(
            f"| `{result.status}` | {result.title} | {result.pages or '-'} | "
            f"{result.extracted_chars} | {matched} | {missing} | {preview} |"
        )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    results = [_audit_row(row, args.max_pages) for row in load_pdf_standard_rows()]
    _write_json(results, args.json_output, args.max_pages)
    _write_markdown(results, args.md_output, args.max_pages, args.json_output)
    summary = _summary(results)
    print("PDF standard audit:", summary)
    print("Markdown:", args.md_output)
    print("JSON:", args.json_output)
    return 1 if any(result.status in {"mismatch", "empty_text", "extract_failed"} for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

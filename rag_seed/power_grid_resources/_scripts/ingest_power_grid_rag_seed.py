#!/usr/bin/env python3
"""Ingest the power-grid RAG seed corpus into the project knowledge base.

The script is safe to re-run: existing indexed documents are skipped by default,
and ``--refresh`` rewrites the document metadata and chunks for the same storage
object path.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from backend.db.supabase_client import get_bucket_name, get_supabase_client, upload_file_to_storage  # noqa: E402
from backend.rag.vector_store import get_embeddings, init_ali_client, read_file_content  # noqa: E402


CATEGORY_MAP = {
    "01_tender_documents": "power_grid_tender_documents",
    "02_policy_regulations": "power_grid_policy_regulations",
    "03_standards_specs": "power_grid_standards_specs",
    "04_standard_phrases": "power_grid_standard_phrases",
}

DEFAULT_STATUSES = {"downloaded", "generated"}


def stable_object_path(title: str, source_path: str) -> str:
    digest = hashlib.sha1(f"{title}|{source_path}".encode("utf-8")).hexdigest()[:12]
    suffix = Path(source_path).suffix.lower() or ".md"
    return f"power-grid-rag-seed/{digest}{suffix}"


def load_seed_rows(statuses: set[str], categories: set[str] | None) -> list[dict[str, str]]:
    index_path = ROOT / "index.csv"
    rows = list(csv.DictReader(index_path.open(encoding="utf-8-sig")))
    filtered = [row for row in rows if row.get("status") in statuses]
    if categories:
        filtered = [row for row in filtered if row.get("category") in categories]
    priority = {
        "04_standard_phrases": 0,
        "02_policy_regulations": 1,
        "01_tender_documents": 2,
        "03_standards_specs": 3,
    }
    return sorted(filtered, key=lambda row: (priority.get(row.get("category"), 99), row.get("file_path") or ""))


def split_for_rag(text: str, max_chars: int = 1800, overlap: int = 180) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(paragraph):
                end = start + max_chars
                piece = paragraph[start:end].strip()
                if piece:
                    chunks.append(piece)
                start = max(end - overlap, end)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current.strip():
                chunks.append(current.strip())
            current = paragraph

    if current.strip():
        chunks.append(current.strip())

    overlapped: list[str] = []
    for index, chunk in enumerate(chunks):
        if index == 0:
            overlapped.append(chunk)
            continue
        previous_tail = chunks[index - 1][-overlap:].strip()
        overlapped.append(f"{previous_tail}\n\n{chunk}" if previous_tail else chunk)
    return [chunk for chunk in overlapped if chunk.strip()]


def find_existing_document(bucket: str, object_path: str) -> dict[str, Any] | None:
    response = (
        get_supabase_client()
        .table("knowledge_documents")
        .select("id,title,status")
        .eq("bucket", bucket)
        .eq("object_path", object_path)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def upsert_document(row: dict[str, str], bucket: str, object_path: str, existing: dict[str, Any] | None) -> str:
    client = get_supabase_client()
    payload = {
        "title": row["title"],
        "category": CATEGORY_MAP.get(row["category"], row["category"]),
        "bucket": bucket,
        "object_path": object_path,
        "source_type": Path(row["file_path"]).suffix.lstrip(".") or row["doc_type"],
        "status": "processing",
        "metadata": {
            "seed_corpus": "power_grid_resources",
            "source_category": row["category"],
            "doc_type": row["doc_type"],
            "source_org": row["source_org"],
            "source_url": row["source_url"],
            "tags": row["tags"],
            "source_file": row["file_path"],
            "sha256": row["sha256"],
        },
    }
    if existing:
        client.table("knowledge_documents").update(payload).eq("id", existing["id"]).execute()
        return str(existing["id"])
    response = client.table("knowledge_documents").insert(payload).execute()
    if not response.data:
        raise RuntimeError(f"创建知识文档失败: {row['title']}")
    return response.data[0]["id"]


def update_document(document_id: str, status: str) -> None:
    get_supabase_client().table("knowledge_documents").update({"status": status}).eq("id", document_id).execute()


def insert_chunks(document_id: str, row: dict[str, str], chunks: list[str]) -> int:
    client = get_supabase_client()
    ali_client = init_ali_client()
    embeddings = get_embeddings(
        ali_client,
        chunks,
        batch_size=10,
        usage_context={
            "stage": "power_grid_rag_seed_ingestion",
            "metadata": {"seed_corpus": "power_grid_resources", "source_file": row["file_path"]},
        },
    )

    rows: list[dict[str, Any]] = []
    for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
        rows.append(
            {
                "document_id": document_id,
                "chunk_index": index,
                "content": content,
                "embedding": embedding,
                "metadata": {
                    "type": "text",
                    "seed_corpus": "power_grid_resources",
                    "category": row["category"],
                    "category_label": CATEGORY_MAP.get(row["category"], row["category"]),
                    "doc_type": row["doc_type"],
                    "source_org": row["source_org"],
                    "source_url": row["source_url"],
                    "tags": row["tags"],
                    "source_file": row["file_path"],
                    "sha256": row["sha256"],
                },
            }
        )

    client.table("document_chunks").delete().eq("document_id", document_id).execute()
    inserted = 0
    for start in range(0, len(rows), 50):
        batch = rows[start : start + 50]
        response = client.table("document_chunks").insert(batch).execute()
        inserted += len(response.data or batch)
        time.sleep(0.2)
    return inserted


def ingest_one(row: dict[str, str], *, include_pdf: bool, refresh: bool, dry_run: bool) -> dict[str, Any]:
    source_path = ROOT / row["file_path"]
    if not source_path.exists():
        return {"title": row["title"], "status": "missing_file", "chunks": 0, "error": str(source_path)}
    if source_path.suffix.lower() == ".pdf" and not include_pdf:
        return {"title": row["title"], "status": "skipped_pdf", "chunks": 0, "error": "PDF 需显式 --include-pdf 后入库"}

    bucket = get_bucket_name("knowledge")
    object_path = stable_object_path(row["title"], row["file_path"])
    existing = find_existing_document(bucket, object_path)
    if existing and existing.get("status") == "indexed" and not refresh:
        return {"title": row["title"], "status": "skipped_existing", "chunks": 0, "error": ""}

    text = read_file_content(source_path)
    chunks = split_for_rag(text)
    if not chunks:
        return {"title": row["title"], "status": "empty_content", "chunks": 0, "error": "文件未提取到可入库文本"}
    if dry_run:
        return {"title": row["title"], "status": "dry_run", "chunks": len(chunks), "error": ""}

    content_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
    upload_file_to_storage(bucket, object_path, source_path, content_type)
    document_id = upsert_document(row, bucket, object_path, existing)

    try:
        inserted = insert_chunks(document_id, row, chunks)
        update_document(document_id, "indexed")
        return {"title": row["title"], "status": "indexed", "chunks": inserted, "error": ""}
    except Exception as exc:
        update_document(document_id, "failed")
        return {"title": row["title"], "status": "failed", "chunks": 0, "error": f"{type(exc).__name__}: {exc}"}


def write_report(results: list[dict[str, Any]], args: argparse.Namespace) -> None:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "include_pdf": args.include_pdf,
        "refresh": args.refresh,
        "dry_run": args.dry_run,
        "total": len(results),
        "indexed": sum(1 for item in results if item["status"] == "indexed"),
        "dry_run_items": sum(1 for item in results if item["status"] == "dry_run"),
        "skipped_existing": sum(1 for item in results if item["status"] == "skipped_existing"),
        "skipped_pdf": sum(1 for item in results if item["status"] == "skipped_pdf"),
        "failed": [item for item in results if item["status"] not in {"indexed", "dry_run", "skipped_existing", "skipped_pdf"}],
        "total_chunks": sum(int(item.get("chunks", 0)) for item in results),
        "results": results,
    }
    (ROOT / "ingestion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 电网 RAG 种子库入库报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 待处理资料：{report['total']}",
        f"- 新入库资料：{report['indexed']}",
        f"- Dry run 资料：{report['dry_run_items']}",
        f"- 已存在跳过：{report['skipped_existing']}",
        f"- PDF 跳过：{report['skipped_pdf']}",
        f"- 新增/预计分片：{report['total_chunks']}",
        "",
        "## 明细",
        "",
    ]
    for item in results:
        lines.append(f"- `{item['status']}` | chunks={item.get('chunks', 0)} | {item['title']}")
        if item.get("error"):
            lines.append(f"  - error: {item['error']}")
    (ROOT / "ingestion_report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest power-grid RAG seed documents.")
    parser.add_argument("--include-pdf", action="store_true", help="Include PDF files. Default skips PDFs to avoid noisy extraction.")
    parser.add_argument("--refresh", action="store_true", help="Refresh existing indexed documents and rewrite chunks.")
    parser.add_argument("--dry-run", action="store_true", help="Only parse and split documents; do not upload or write embeddings.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of rows after filtering.")
    parser.add_argument(
        "--category",
        action="append",
        choices=sorted(CATEGORY_MAP),
        help="Limit to one category. Can be provided multiple times.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run and not os.getenv("DASHSCOPE_API_KEY"):
        raise EnvironmentError("DASHSCOPE_API_KEY is required for embedding")

    rows = load_seed_rows(DEFAULT_STATUSES, set(args.category or []))
    if args.limit:
        rows = rows[: args.limit]

    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        print(f"[{index}/{len(rows)}] {row['title']}")
        result = ingest_one(row, include_pdf=args.include_pdf, refresh=args.refresh, dry_run=args.dry_run)
        print(f"  -> {result['status']} chunks={result.get('chunks', 0)}")
        if result.get("error"):
            print(f"     {result['error']}", file=sys.stderr)
        results.append(result)

    write_report(results, args)
    print(f"Done. report={ROOT / 'ingestion_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

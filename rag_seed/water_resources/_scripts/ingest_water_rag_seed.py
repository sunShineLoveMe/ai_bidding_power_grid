#!/usr/bin/env python3
"""Ingest the water-resources RAG seed corpus into the existing knowledge base.

Target storage:
- Supabase Storage bucket configured by SUPABASE_STORAGE_KNOWLEDGE_BUCKET
- knowledge_documents
- document_chunks with pgvector embeddings
"""

from __future__ import annotations

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

from backend.rag.vector_store import get_embeddings, init_ali_client, read_file_content  # noqa: E402
from backend.db.supabase_client import get_bucket_name, get_supabase_client, upload_file_to_storage  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")


CATEGORY_MAP = {
    "01_tender_documents": "water_tender_documents",
    "02_policy_regulations": "water_policy_regulations",
    "03_standards_specs": "water_standards_specs",
    "04_standard_phrases": "water_standard_phrases",
}


def stable_ascii_name(title: str, source_path: str) -> str:
    digest = hashlib.sha1(f"{title}|{source_path}".encode("utf-8")).hexdigest()[:12]
    suffix = Path(source_path).suffix.lower() or ".md"
    return f"water-rag-seed/{digest}{suffix}"


def load_seed_rows() -> list[dict[str, str]]:
    index_path = ROOT / "index.csv"
    rows = list(csv.DictReader(index_path.open(encoding="utf-8-sig")))
    return [row for row in rows if row.get("status") in {"downloaded", "generated"}]


def existing_document_titles() -> set[str]:
    client = get_supabase_client()
    response = client.table("knowledge_documents").select("title").execute()
    return {row["title"] for row in response.data or [] if row.get("title")}


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

    # Add light overlap between neighboring chunks for better recall.
    overlapped: list[str] = []
    for index, chunk in enumerate(chunks):
        if index == 0:
            overlapped.append(chunk)
            continue
        previous_tail = chunks[index - 1][-overlap:].strip()
        overlapped.append(f"{previous_tail}\n\n{chunk}" if previous_tail else chunk)
    return [chunk for chunk in overlapped if chunk.strip()]


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return read_file_content(path)
    return read_file_content(path)


def create_document(row: dict[str, str], bucket: str, object_path: str) -> str:
    client = get_supabase_client()
    payload = {
        "title": row["title"],
        "category": CATEGORY_MAP.get(row["category"], row["category"]),
        "bucket": bucket,
        "object_path": object_path,
        "source_type": Path(row["file_path"]).suffix.lstrip(".") or row["doc_type"],
        "status": "processing",
    }
    response = client.table("knowledge_documents").insert(payload).execute()
    if not response.data:
        raise RuntimeError(f"创建知识文档失败: {row['title']}")
    return response.data[0]["id"]


def update_document(document_id: str, status: str) -> None:
    get_supabase_client().table("knowledge_documents").update({"status": status}).eq("id", document_id).execute()


def insert_chunks(document_id: str, row: dict[str, str], chunks: list[str]) -> int:
    client = get_supabase_client()
    ali_client = init_ali_client()
    embeddings = get_embeddings(ali_client, chunks, batch_size=10)

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
                    "seed_corpus": "water_resources",
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

    inserted = 0
    for start in range(0, len(rows), 50):
        batch = rows[start : start + 50]
        response = client.table("document_chunks").insert(batch).execute()
        inserted += len(response.data or batch)
        time.sleep(0.2)
    return inserted


def ingest_one(row: dict[str, str], known_titles: set[str]) -> dict[str, Any]:
    source_path = ROOT / row["file_path"]
    if not source_path.exists():
        return {"title": row["title"], "status": "missing_file", "chunks": 0, "error": str(source_path)}

    if row["title"] in known_titles:
        return {"title": row["title"], "status": "skipped_existing", "chunks": 0, "error": ""}

    bucket = get_bucket_name("knowledge")
    object_path = stable_ascii_name(row["title"], row["file_path"])
    content_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"

    upload_file_to_storage(bucket, object_path, source_path, content_type)
    document_id = create_document(row, bucket, object_path)

    try:
        text = read_text(source_path)
        chunks = split_for_rag(text)
        if not chunks:
            update_document(document_id, "failed")
            return {"title": row["title"], "status": "empty_content", "chunks": 0, "error": "文件未提取到可入库文本"}

        inserted = insert_chunks(document_id, row, chunks)
        update_document(document_id, "indexed")
        known_titles.add(row["title"])
        return {"title": row["title"], "status": "indexed", "chunks": inserted, "error": ""}
    except Exception as exc:
        update_document(document_id, "failed")
        return {"title": row["title"], "status": "failed", "chunks": 0, "error": f"{type(exc).__name__}: {exc}"}


def write_report(results: list[dict[str, Any]]) -> None:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "indexed": sum(1 for item in results if item["status"] == "indexed"),
        "skipped_existing": sum(1 for item in results if item["status"] == "skipped_existing"),
        "failed": [item for item in results if item["status"] not in {"indexed", "skipped_existing"}],
        "total_chunks": sum(int(item.get("chunks", 0)) for item in results),
        "results": results,
    }
    (ROOT / "ingestion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 水利 RAG 种子库入库报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 待处理资料：{report['total']}",
        f"- 新入库资料：{report['indexed']}",
        f"- 已存在跳过：{report['skipped_existing']}",
        f"- 新增分片：{report['total_chunks']}",
        "",
        "## 明细",
        "",
    ]
    for item in results:
        lines.append(f"- `{item['status']}` | chunks={item.get('chunks', 0)} | {item['title']}")
        if item.get("error"):
            lines.append(f"  - error: {item['error']}")
    (ROOT / "ingestion_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not os.getenv("DASHSCOPE_API_KEY"):
        raise EnvironmentError("DASHSCOPE_API_KEY is required for embedding")
    rows = load_seed_rows()
    known_titles = existing_document_titles()
    results = []
    for index, row in enumerate(rows, 1):
        print(f"[{index}/{len(rows)}] {row['title']}")
        result = ingest_one(row, known_titles)
        print(f"  -> {result['status']} chunks={result.get('chunks', 0)}")
        if result.get("error"):
            print(f"     {result['error']}", file=sys.stderr)
        results.append(result)
    write_report(results)
    print(f"Done. report={ROOT / 'ingestion_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Ingest anonymized water-industry enterprise mock data into the knowledge base."""

from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.rag.vector_store import get_embeddings, init_ali_client, read_file_content, split_text  # noqa: E402
from backend.db.supabase_client import get_bucket_name, get_supabase_client, upload_file_to_storage  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

CATEGORY_MAP = {
    "company_profile": "water_company_profiles",
    "qualification": "water_qualification_library",
    "product": "water_product_library",
    "capability": "water_capability_library",
    "workflow": "water_upload_workflow",
}


def object_path_for(row: dict[str, str]) -> str:
    digest = hashlib.sha1(f"{row['title']}|{row['path']}".encode("utf-8")).hexdigest()[:12]
    suffix = Path(row["path"]).suffix.lower() or ".md"
    return f"water-enterprise-mock/{digest}{suffix}"


def existing_titles() -> set[str]:
    client = get_supabase_client()
    response = client.table("knowledge_documents").select("title").execute()
    return {item["title"] for item in response.data or [] if item.get("title")}


def create_document(row: dict[str, str], bucket: str, object_path: str) -> str:
    response = get_supabase_client().table("knowledge_documents").insert({
        "title": row["title"],
        "category": CATEGORY_MAP.get(row["category"], row["category"]),
        "bucket": bucket,
        "object_path": object_path,
        "source_type": Path(row["path"]).suffix.lstrip(".") or row["doc_type"],
        "status": "processing",
    }).execute()
    if not response.data:
        raise RuntimeError(f"创建知识文档失败: {row['title']}")
    return response.data[0]["id"]


def update_document(document_id: str, status: str) -> None:
    get_supabase_client().table("knowledge_documents").update({"status": status}).eq("id", document_id).execute()


def insert_chunks(document_id: str, row: dict[str, str], chunks: list[str]) -> int:
    client = get_supabase_client()
    embeddings = get_embeddings(init_ali_client(), chunks, batch_size=10)
    rows: list[dict[str, Any]] = []
    for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        rows.append({
            "document_id": document_id,
            "chunk_index": index,
            "content": chunk,
            "embedding": embedding,
            "metadata": {
                "type": "text",
                "seed_corpus": "water_enterprise_mock",
                "category": row["category"],
                "category_label": CATEGORY_MAP.get(row["category"], row["category"]),
                "doc_type": row["doc_type"],
                "source_org": "脱敏模拟企业资料包",
                "source_file": row["path"],
                "tags": row["tags"],
            },
        })

    inserted = 0
    for start in range(0, len(rows), 50):
        batch = rows[start:start + 50]
        response = client.table("document_chunks").insert(batch).execute()
        inserted += len(response.data or batch)
        time.sleep(0.2)
    return inserted


def main() -> int:
    bucket = get_bucket_name("knowledge")
    known = existing_titles()
    rows = list(csv.DictReader((ROOT / "index.csv").open(encoding="utf-8")))
    results = []

    for index, row in enumerate(rows, 1):
        print(f"[{index}/{len(rows)}] {row['title']}")
        path = ROOT / row["path"]
        if row["title"] in known:
            results.append({"title": row["title"], "status": "skipped_existing", "chunks": 0})
            print("  -> skipped_existing")
            continue

        object_path = object_path_for(row)
        upload_file_to_storage(bucket, object_path, path, mimetypes.guess_type(path.name)[0] or "text/markdown")
        document_id = create_document(row, bucket, object_path)
        try:
            content = read_file_content(path)
            chunks = split_text(content, max_length=1800)
            if not chunks:
                update_document(document_id, "failed")
                results.append({"title": row["title"], "status": "empty", "chunks": 0})
                continue
            inserted = insert_chunks(document_id, row, chunks)
            update_document(document_id, "indexed")
            known.add(row["title"])
            results.append({"title": row["title"], "status": "indexed", "chunks": inserted})
            print(f"  -> indexed chunks={inserted}")
        except Exception as exc:
            update_document(document_id, "failed")
            results.append({"title": row["title"], "status": "failed", "chunks": 0, "error": f"{type(exc).__name__}: {exc}"})
            print(f"  -> failed {exc}", file=sys.stderr)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "indexed": sum(1 for item in results if item["status"] == "indexed"),
        "skipped_existing": sum(1 for item in results if item["status"] == "skipped_existing"),
        "total_chunks": sum(item.get("chunks", 0) for item in results),
        "results": results,
    }
    (ROOT / "ingestion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 水利行业脱敏模拟企业资料入库报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 待处理资料：{report['total']}",
        f"- 新入库资料：{report['indexed']}",
        f"- 已存在跳过：{report['skipped_existing']}",
        f"- 新增分片：{report['total_chunks']}",
        "",
    ]
    lines.extend(f"- `{item['status']}` | chunks={item.get('chunks', 0)} | {item['title']}" for item in results)
    (ROOT / "ingestion_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Done. report={ROOT / 'ingestion_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

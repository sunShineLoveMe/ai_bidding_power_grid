#!/usr/bin/env python3
"""Ingest prepared Jiangxi/Shanxi customer tender corpus into pgvector.

Input is the manifest produced by `prepare_customer_corpus.py`. This script
keeps customer data isolated with seed_corpus + ingestion_batch_id metadata and
supports dry-run/refresh so each batch is auditable and repeatable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.supabase_client import get_bucket_name, get_supabase_client, upload_file_to_storage  # noqa: E402
from backend.rag.chunking import Chunk, build_parent_child_chunks  # noqa: E402
from backend.rag.vector_store import get_embeddings, init_ali_client  # noqa: E402
from scripts.rag.customer_metadata_policy import (  # noqa: E402
    normalize_customer_record_metadata,
    should_supersede,
)

CATEGORY = "power_grid_tender_documents"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _object_path(record: dict[str, Any]) -> str:
    source = record["source_file"]
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    suffix = Path(record.get("output_file") or source).suffix.lower() or ".md"
    return f"power-grid-customer-corpus/{record['metadata']['ingestion_batch_id']}/{digest}{suffix}"


def _upsert_document(record: dict[str, Any], bucket: str, object_path: str) -> str:
    client = get_supabase_client()
    existing = (
        client.table("knowledge_documents")
        .select("id")
        .eq("bucket", bucket)
        .eq("object_path", object_path)
        .limit(1)
        .execute()
    ).data
    metadata = dict(record.get("metadata") or {})
    metadata.update({
        "parser": record.get("parser"),
        "source_file": record.get("source_file"),
        "output_file": record.get("output_file"),
        "parse_status": record.get("parse_status"),
        "sha256": record.get("sha256"),
    })
    payload = {
        "title": Path(record["source_file"]).stem,
        "category": CATEGORY,
        "bucket": bucket,
        "object_path": object_path,
        "source_type": record.get("source_type"),
        "status": "processing",
        "metadata": metadata,
    }
    if existing:
        client.table("knowledge_documents").update(payload).eq("id", existing[0]["id"]).execute()
        return str(existing[0]["id"])
    resp = client.table("knowledge_documents").insert(payload).execute()
    return str(resp.data[0]["id"])


def _supersede_previous_versions(document_id: str, metadata: dict[str, Any]) -> int:
    client = get_supabase_client()
    rows = (
        client.table("knowledge_documents")
        .select("id,metadata,status")
        .eq("category", CATEGORY)
        .limit(1000)
        .execute()
    ).data or []
    superseded = 0
    for row in rows:
        existing_id = str(row.get("id") or "")
        if existing_id == document_id:
            continue
        existing_meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if not should_supersede(existing_meta, metadata):
            continue
        next_meta = dict(existing_meta)
        next_meta.update({
            "status": "superseded",
            "superseded_by": document_id,
        })
        client.table("knowledge_documents").update({
            "status": "superseded",
            "metadata": next_meta,
        }).eq("id", existing_id).execute()
        superseded += 1
    return superseded


def _base_chunk_meta(record: dict[str, Any], chunk: Chunk | None = None) -> dict[str, Any]:
    metadata = dict(record.get("metadata") or {})
    metadata.update({
        "type": "text",
        "category_label": CATEGORY,
        "source_file": record.get("source_file"),
        "output_file": record.get("output_file"),
        "parser": record.get("parser"),
        "parse_status": record.get("parse_status"),
        "status": "staging_indexed",
    })
    if chunk is not None:
        metadata.update({
            "chunk_layer": chunk.layer,
            "parent_index": chunk.parent_index,
            "block_type": chunk.block_type,
            "content_sha256": _sha256_text(chunk.content),
        })
    return metadata


def _table_chunks(record: dict[str, Any]) -> list[dict[str, Any]]:
    output_file = record.get("output_file")
    if not output_file:
        return []
    payload = _load_json(PROJECT_ROOT / output_file)
    chunks: list[dict[str, Any]] = []
    idx = 0
    for sheet in payload.get("sheets") or []:
        rows = sheet.get("rows") or []
        if not rows:
            continue
        summary = sheet.get("retrieval_summary") or f"{Path(record['source_file']).name} {sheet.get('name')}"
        parent_index = idx
        parent_meta = _base_chunk_meta(record)
        parent_meta.update({
            "type": "table",
            "chunk_layer": "parent",
            "parent_index": None,
            "block_type": "table",
            "table_id": f"{record['metadata']['package_code']}_{sheet.get('name')}",
            "table_name": sheet.get("name"),
            "content_sha256": _sha256_text(summary),
        })
        chunks.append({
            "chunk_index": idx,
            "content": summary,
            "source_section": sheet.get("name"),
            "metadata": parent_meta,
            "embedding": None,
        })
        idx += 1

        summary_meta = _base_chunk_meta(record)
        summary_meta.update({
            "type": "table",
            "chunk_layer": "child",
            "parent_index": parent_index,
            "block_type": "table_summary",
            "table_name": sheet.get("name"),
            "content_sha256": _sha256_text(summary),
        })
        chunks.append({
            "chunk_index": idx,
            "content": summary,
            "source_section": sheet.get("name"),
            "metadata": summary_meta,
            "embedding": "__PENDING__",
        })
        idx += 1

        headers = [str(cell or "") for cell in rows[0]]
        for row_no, row in enumerate(rows[1:], 1):
            values = [str(cell or "") for cell in row]
            pairs = [f"{headers[i]}={values[i]}" for i in range(min(len(headers), len(values))) if values[i]]
            content = (
                f"{record['province']} {record['batch_no']} {record.get('package_code') or record['metadata'].get('package_code')} "
                f"{record['material_category']} 货物清单 第{row_no}行："
                + "；".join(pairs)
            )
            meta = _base_chunk_meta(record)
            meta.update({
                "type": "table",
                "chunk_layer": "child",
                "parent_index": parent_index,
                "block_type": "table_row",
                "table_name": sheet.get("name"),
                "row_number": row_no,
                "row": {headers[i]: values[i] for i in range(min(len(headers), len(values)))},
                "content_sha256": _sha256_text(content),
            })
            chunks.append({
                "chunk_index": idx,
                "content": content,
                "source_section": sheet.get("name"),
                "metadata": meta,
                "embedding": "__PENDING__",
            })
            idx += 1
    return chunks


def _text_chunks(record: dict[str, Any]) -> list[dict[str, Any]]:
    output_file = record.get("output_file")
    if not output_file:
        return []
    text = (PROJECT_ROOT / output_file).read_text(encoding="utf-8")
    chunks = build_parent_child_chunks(text, doc_role=record["doc_role"])
    rows = []
    for chunk in chunks:
        rows.append({
            "chunk_index": chunk.index,
            "content": chunk.content,
            "source_section": chunk.section,
            "metadata": _base_chunk_meta(record, chunk),
            "embedding": "__PENDING__" if chunk.layer == "child" else None,
        })
    return rows


def _build_chunks(record: dict[str, Any]) -> list[dict[str, Any]]:
    if record.get("doc_role") == "goods_list":
        return _table_chunks(record)
    return _text_chunks(record)


def _ingest_record(record: dict[str, Any], *, dry_run: bool, refresh: bool) -> dict[str, Any]:
    if record.get("parse_status") != "parsed":
        return {"source_file": record.get("source_file"), "status": "skipped", "parents": 0, "children": 0}
    normalized_metadata, metadata_warnings, metadata_errors = normalize_customer_record_metadata(record)
    if metadata_errors:
        return {
            "source_file": record.get("source_file"),
            "status": "blocked_metadata",
            "doc_role": record.get("doc_role"),
            "parents": 0,
            "children": 0,
            "embedding_count": 0,
            "metadata_warnings": metadata_warnings,
            "metadata_errors": metadata_errors,
        }
    record = {**record, "metadata": normalized_metadata}
    chunks = _build_chunks(record)
    parents = sum(1 for row in chunks if row["metadata"].get("chunk_layer") == "parent")
    children = sum(1 for row in chunks if row["metadata"].get("chunk_layer") == "child")
    pending = [row for row in chunks if row["embedding"] == "__PENDING__"]
    if dry_run:
        return {
            "source_file": record.get("source_file"),
            "status": "dry_run",
            "doc_role": record.get("doc_role"),
            "parents": parents,
            "children": children,
            "embedding_count": len(pending),
            "metadata_warnings": metadata_warnings,
        }

    bucket = get_bucket_name("knowledge")
    object_path = _object_path(record)
    output_file = record.get("output_file")
    if output_file:
        upload_file_to_storage(bucket, object_path, PROJECT_ROOT / output_file)
    document_id = _upsert_document(record, bucket, object_path)
    superseded_documents = _supersede_previous_versions(document_id, normalized_metadata)

    client = get_supabase_client()
    if refresh:
        client.table("document_chunks").delete().eq("document_id", document_id).execute()

    if pending:
        ali = init_ali_client()
        embeddings = get_embeddings(
            ali,
            [row["content"] for row in pending],
            batch_size=10,
            usage_context={
                "stage": "power_grid_customer_corpus",
                "metadata": {
                    "source_file": record.get("source_file"),
                    "ingestion_batch_id": record["metadata"].get("ingestion_batch_id"),
                },
            },
        )
        for row, embedding in zip(pending, embeddings):
            row["embedding"] = embedding
    for row in chunks:
        if row["embedding"] == "__PENDING__":
            row["embedding"] = None
        row["document_id"] = document_id

    inserted = 0
    for start in range(0, len(chunks), 50):
        batch = chunks[start:start + 50]
        resp = client.table("document_chunks").insert(batch).execute()
        inserted += len(resp.data or batch)
        time.sleep(0.05)
    client.table("knowledge_documents").update({"status": "indexed"}).eq("id", document_id).execute()
    return {
        "source_file": record.get("source_file"),
        "status": "indexed",
        "document_id": document_id,
        "doc_role": record.get("doc_role"),
        "parents": parents,
        "children": children,
        "embedding_count": len(pending),
        "inserted_chunks": inserted,
        "superseded_documents": superseded_documents,
        "metadata_warnings": metadata_warnings,
    }


def _write_report(results: list[dict[str, Any]], summary: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    json_path = out_dir / "ingest_customer_corpus_report.json"
    json_path.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 客户资料 staging 入库报告",
        "",
        f"> 批次：`{summary['batch_id']}`",
        f"> 生成时间：{summary['generated_at']}",
        "",
        "## 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 文档数 | {summary['documents']} |",
        f"| indexed | {summary['indexed']} |",
        f"| skipped | {summary['skipped']} |",
        f"| blocked_metadata | {summary['blocked_metadata']} |",
        f"| superseded_documents | {summary['superseded_documents']} |",
        f"| parent | {summary['parents']} |",
        f"| child/table 检索块 | {summary['children']} |",
        f"| embedding | {summary['embedding_count']} |",
        "",
        "## 明细",
        "",
        "| 状态 | 角色 | 文件 | parent | child | embedding | metadata |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for result in results:
        metadata_note = ""
        if result.get("metadata_errors"):
            metadata_note = "errors: " + "；".join(result.get("metadata_errors") or [])
        elif result.get("metadata_warnings"):
            metadata_note = "warnings: " + "；".join(result.get("metadata_warnings") or [])
        lines.append(
            f"| {result['status']} | `{result.get('doc_role') or '-'}` | `{Path(result['source_file']).name}` | "
            f"{result.get('parents', 0)} | {result.get('children', 0)} | {result.get('embedding_count', 0)} | {metadata_note or '-'} |"
        )
    md_path = out_dir / "ingest_customer_corpus_report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="delete existing chunks for matching documents before inserting")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = _load_json(manifest_path)
    records = manifest.get("records") or []
    results = [_ingest_record(record, dry_run=args.dry_run, refresh=args.refresh) for record in records]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "manifest": _rel(manifest_path),
        "batch_id": manifest.get("batch_id"),
        "dry_run": args.dry_run,
        "refresh": args.refresh,
        "documents": len(results),
        "indexed": sum(1 for r in results if r["status"] == "indexed"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "blocked_metadata": sum(1 for r in results if r["status"] == "blocked_metadata"),
        "superseded_documents": sum(r.get("superseded_documents", 0) for r in results),
        "parents": sum(r.get("parents", 0) for r in results),
        "children": sum(r.get("children", 0) for r in results),
        "embedding_count": sum(r.get("embedding_count", 0) for r in results),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    json_path, md_path = _write_report(results, summary, manifest_path.parent)
    print(f"JSON: {_rel(json_path)}")
    print(f"Report: {_rel(md_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

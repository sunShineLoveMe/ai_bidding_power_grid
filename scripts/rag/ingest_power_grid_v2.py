#!/usr/bin/env python3
"""国网种子库 v2 入库：父子双层分块 + 丰富 metadata（P0 实现）。

相对旧版 `rag_seed/.../ingest_power_grid_rag_seed.py` 的改进：
- 用 `backend.rag.chunking.build_parent_child_chunks` 做按 doc_role 的父子分块，
  替代统一 1800 字盲切。
- 写入丰富 metadata：chunk_layer / parent_index / doc_role / authority_level /
  citation_policy / source_category / block_type / content_sha256 等（评审稿 §7）。
- 只对 child 层做 embedding（召回目标）；parent 层写入但 embedding 置空（写作回溯用），
  因此不会污染向量召回（match RPC 过滤 embedding is not null）。

用法：
    python scripts/rag/ingest_power_grid_v2.py --dry-run     # 只分块统计
    python scripts/rag/ingest_power_grid_v2.py               # 实际入库（Markdown 类）
    python scripts/rag/ingest_power_grid_v2.py --category 02_policy_regulations
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_ROOT = PROJECT_ROOT / "rag_seed" / "power_grid_resources"
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.supabase_client import get_bucket_name, get_supabase_client, upload_file_to_storage  # noqa: E402
from backend.rag.vector_store import get_embeddings, init_ali_client, read_file_content  # noqa: E402
from backend.rag.chunking import build_parent_child_chunks  # noqa: E402

CATEGORY_MAP = {
    "01_tender_documents": "power_grid_tender_documents",
    "02_policy_regulations": "power_grid_policy_regulations",
    "03_standards_specs": "power_grid_standards_specs",
    "04_standard_phrases": "power_grid_standard_phrases",
}

# 权威性序：law > regulation > national_standard > industry_standard > sgcc_rule > tender_file > template
AUTHORITY_BY_DOC_TYPE = {
    "法律": "law",
    "法律PDF": "law",
    "行政法规": "regulation",
    "行政法规PDF": "regulation",
    "部门规章PDF": "regulation",
    "规范性文件": "regulation",
    "国家标准": "national_standard",
    "国家标准PDF": "national_standard",
    "国家标准网页": "national_standard",
    "行业标准PDF": "industry_standard",
    "行业标准网页": "industry_standard",
    "国网标准网页": "sgcc_rule",
    "国网规章网页": "sgcc_rule",
    "国网采购公告": "tender_file",
    "自建话术模板": "template",
}

CITATION_BY_AUTHORITY = {
    "law": "summary_only",
    "regulation": "summary_only",
    "national_standard": "summary_only",
    "industry_standard": "summary_only",
    "sgcc_rule": "summary_only",
    "tender_file": "internal_reference_only",
    "template": "direct_quote_allowed",
}


def classify_doc_role(row: dict[str, str]) -> str:
    cat = row.get("category", "")
    doc_type = row.get("doc_type", "")
    title = row.get("title", "")
    if cat == "04_standard_phrases":
        return "self_phrase"
    if cat == "03_standards_specs":
        return "standard_spec"
    if cat == "01_tender_documents":
        if "公告" in title or "谈判" in title:
            return "tender_notice"
        return "main_tender_file"
    # 02_policy_regulations
    if "国家电网" in title or "国网" in doc_type:
        return "sgcc_rule"
    return "policy_regulation"


def stable_object_path(title: str, source_path: str) -> str:
    digest = hashlib.sha1(f"{title}|{source_path}".encode("utf-8")).hexdigest()[:12]
    suffix = Path(source_path).suffix.lower() or ".md"
    return f"power-grid-rag-seed-v2/{digest}{suffix}"


def load_rows(categories: set[str] | None) -> list[dict[str, str]]:
    rows = list(csv.DictReader((SEED_ROOT / "index.csv").open(encoding="utf-8-sig")))
    rows = [r for r in rows if r.get("status") in {"downloaded", "generated"}]
    rows = [r for r in rows if Path(r["file_path"]).suffix.lower() != ".pdf"]
    if categories:
        rows = [r for r in rows if r.get("category") in categories]
    return rows


def upsert_document(row: dict[str, str], bucket: str, object_path: str, doc_role: str) -> str:
    client = get_supabase_client()
    existing = (
        client.table("knowledge_documents").select("id")
        .eq("bucket", bucket).eq("object_path", object_path).limit(1).execute()
    ).data
    payload = {
        "title": row["title"],
        "category": CATEGORY_MAP.get(row["category"], row["category"]),
        "bucket": bucket,
        "object_path": object_path,
        "source_type": Path(row["file_path"]).suffix.lstrip(".") or row["doc_type"],
        "status": "processing",
        "metadata": {
            "seed_corpus": "power_grid_resources",
            "chunker": "parent_child_v2",
            "source_category": row["category"],
            "doc_role": doc_role,
            "doc_type": row["doc_type"],
            "source_org": row["source_org"],
            "source_url": row["source_url"],
            "tags": row["tags"],
            "source_file": row["file_path"],
            "sha256": row["sha256"],
        },
    }
    if existing:
        client.table("knowledge_documents").update(payload).eq("id", existing[0]["id"]).execute()
        return str(existing[0]["id"])
    resp = client.table("knowledge_documents").insert(payload).execute()
    return resp.data[0]["id"]


def ingest_one(row: dict[str, str], *, dry_run: bool) -> dict[str, Any]:
    source_path = SEED_ROOT / row["file_path"]
    if not source_path.exists():
        return {"title": row["title"], "status": "missing_file", "parents": 0, "children": 0}

    doc_role = classify_doc_role(row)
    authority = AUTHORITY_BY_DOC_TYPE.get(row.get("doc_type", ""), "template")
    citation = CITATION_BY_AUTHORITY.get(authority, "summary_only")

    text = read_file_content(source_path)
    chunks = build_parent_child_chunks(text, doc_role=doc_role)
    parents = [c for c in chunks if c.layer == "parent"]
    children = [c for c in chunks if c.layer == "child"]
    if not children:
        return {"title": row["title"], "status": "empty", "parents": 0, "children": 0, "doc_role": doc_role}
    if dry_run:
        return {"title": row["title"], "status": "dry_run", "parents": len(parents),
                "children": len(children), "doc_role": doc_role}

    bucket = get_bucket_name("knowledge")
    object_path = stable_object_path(row["title"], row["file_path"])
    upload_file_to_storage(bucket, object_path, source_path, "text/markdown")
    document_id = upsert_document(row, bucket, object_path, doc_role)

    client = get_supabase_client()
    client.table("document_chunks").delete().eq("document_id", document_id).execute()

    # 只对 child embedding
    child_texts = [c.content for c in children]
    ali = init_ali_client()
    embeddings = get_embeddings(ali, child_texts, batch_size=10,
                                usage_context={"stage": "power_grid_rag_seed_v2",
                                               "metadata": {"source_file": row["file_path"]}})
    emb_by_index = {children[i].index: embeddings[i] for i in range(len(children))}

    def base_meta(c) -> dict[str, Any]:
        return {
            "type": "text",
            "seed_corpus": "power_grid_resources",
            "chunker": "parent_child_v2",
            "chunk_layer": c.layer,
            "parent_index": c.parent_index,
            "block_type": c.block_type,
            "doc_role": doc_role,
            "authority_level": authority,
            "citation_policy": citation,
            "source_category": row["category"],
            "category_label": CATEGORY_MAP.get(row["category"], row["category"]),
            "doc_type": row["doc_type"],
            "source_org": row["source_org"],
            "source_file": row["file_path"],
            "tags": row["tags"],
            "content_sha256": hashlib.sha256(c.content.encode("utf-8")).hexdigest(),
        }

    db_rows: list[dict[str, Any]] = []
    for c in chunks:
        db_rows.append({
            "document_id": document_id,
            "chunk_index": c.index,
            "content": c.content,
            "source_section": c.section,
            "embedding": emb_by_index.get(c.index),  # parent -> None
            "metadata": base_meta(c),
        })

    inserted = 0
    for start in range(0, len(db_rows), 50):
        batch = db_rows[start:start + 50]
        resp = client.table("document_chunks").insert(batch).execute()
        inserted += len(resp.data or batch)
        time.sleep(0.1)
    client.table("knowledge_documents").update({"status": "indexed"}).eq("id", document_id).execute()
    return {"title": row["title"], "status": "indexed", "parents": len(parents),
            "children": len(children), "doc_role": doc_role}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--category", action="append", choices=sorted(CATEGORY_MAP))
    args = parser.parse_args()

    rows = load_rows(set(args.category or []))
    results = []
    for i, row in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {row['title']}")
        r = ingest_one(row, dry_run=args.dry_run)
        print(f"  -> {r['status']} role={r.get('doc_role')} parents={r['parents']} children={r['children']}")
        results.append(r)

    total_p = sum(r["parents"] for r in results)
    total_c = sum(r["children"] for r in results)
    print(f"\nDone. docs={len(results)} parents={total_p} children={total_c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

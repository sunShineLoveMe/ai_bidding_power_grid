#!/usr/bin/env python3
"""Import Taichang MVP image asset payloads into knowledge_assets."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.postgres_pool import pooled_connection  # noqa: E402
from backend.db.supabase_repo import create_knowledge_asset, upload_knowledge_asset_file  # noqa: E402
from backend.rag.vector_store import get_embeddings, init_ali_client  # noqa: E402


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for asset refresh")
    return url


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _load_payloads(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["batch_id"], payload.get("assets") or []


def _delete_existing(batch_id: str) -> int:
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        cur = conn.execute(
            "delete from public.knowledge_assets where metadata->>'source_batch_id' = %s",
            [batch_id],
        )
        return cur.rowcount


def _image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def _library_type(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata") or {}
    return "qualification" if metadata.get("target_library") == "qualification_library" else "product"


def _build_import_payload(payload: dict[str, Any], embedding: list[float] | None) -> dict[str, Any]:
    local_path = PROJECT_ROOT / payload["local_path"]
    width, height = _image_size(local_path)
    return {
        "title": payload["title"],
        "description": payload.get("description"),
        "category": payload.get("category"),
        "asset_type": payload.get("asset_type") or "image",
        "file_name": local_path.name,
        "file_ext": local_path.suffix.lower().lstrip("."),
        "mime_type": payload.get("mime_type"),
        "file_size": local_path.stat().st_size,
        "local_path": payload.get("local_path"),
        "width": width,
        "height": height,
        "source_type": payload.get("source_type"),
        "license": payload.get("license"),
        "attribution": payload.get("attribution"),
        "is_synthetic": bool(payload.get("is_synthetic")),
        "is_sensitive": bool(payload.get("is_sensitive")),
        "anonymized": bool(payload.get("anonymized")),
        "industry": payload.get("industry") or "电力行业",
        "applicable_sections": payload.get("applicable_sections") or [],
        "applicable_volumes": payload.get("applicable_volumes") or [],
        "tags": payload.get("tags") or [],
        "specs": payload.get("specs") or {},
        "ocr_text": payload.get("ocr_text"),
        "ai_caption": payload.get("ai_caption"),
        "searchable_text": payload.get("searchable_text"),
        "embedding": embedding,
        "status": payload.get("status") or "indexed",
        "metadata": payload.get("metadata") or {},
    }


def _write_report(out_path: Path, report: dict[str, Any]) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = out_path.with_suffix(".md")
    lines = [
        "# 泰昌 MVP 图片资产入库报告",
        "",
        f"> 批次：`{report['batch_id']}`",
        f"> 生成时间：{report['generated_at']}",
        f"> dry-run：`{report['dry_run']}`",
        "",
        "## 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| payload assets | {report['total']} |",
        f"| imported | {report['imported']} |",
        f"| skipped | {report['skipped']} |",
        f"| failed | {report['failed']} |",
        f"| deleted_existing | {report['deleted_existing']} |",
        "",
        "## 明细样例",
        "",
        "| 状态 | 类型 | 文件 | asset_id |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["items"][:40]:
        lines.append(
            f"| {item['status']} | `{item.get('asset_type') or '-'}` | "
            f"`{item.get('file_name') or '-'}` | `{item.get('asset_id') or '-'}` |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("payloads", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="delete existing assets for this source_batch_id before import")
    parser.add_argument("--no-embedding", action="store_true")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/ingest_taichang_assets_report.json")
    args = parser.parse_args()

    payload_path = args.payloads.resolve()
    batch_id, payloads = _load_payloads(payload_path)
    deleted_existing = 0
    if args.refresh and not args.dry_run:
        deleted_existing = _delete_existing(batch_id)

    embeddings: list[list[float] | None] = [None] * len(payloads)
    if not args.no_embedding and not args.dry_run and payloads:
        texts = [str(payload.get("searchable_text") or payload.get("description") or payload.get("title") or "") for payload in payloads]
        embeddings = get_embeddings(
            init_ali_client(),
            texts,
            batch_size=20,
            usage_context={
                "stage": "taichang_asset_ingestion",
                "metadata": {"source_batch_id": batch_id, "asset_count": len(payloads)},
            },
        )

    items: list[dict[str, Any]] = []
    for index, payload in enumerate(payloads):
        local_path = PROJECT_ROOT / payload["local_path"]
        asset_id = (payload.get("metadata") or {}).get("asset_id")
        if args.dry_run:
            status = "dry_run" if local_path.exists() else "missing_file"
            items.append({
                "status": status,
                "asset_id": asset_id,
                "asset_type": payload.get("asset_type"),
                "file_name": local_path.name,
            })
            continue
        if not local_path.exists():
            items.append({
                "status": "missing_file",
                "asset_id": asset_id,
                "asset_type": payload.get("asset_type"),
                "file_name": local_path.name,
            })
            continue
        try:
            import_payload = _build_import_payload(payload, embeddings[index] if embeddings else None)
            storage_info = upload_knowledge_asset_file(
                local_file_path=local_path,
                original_filename=local_path.name,
                library_type=_library_type(payload),
            )
            import_payload.update({
                "file_ext": storage_info.get("file_ext"),
                "mime_type": storage_info.get("mime_type"),
                "file_size": storage_info.get("file_size"),
                "storage_bucket": storage_info.get("bucket"),
                "storage_path": storage_info.get("object_path"),
                "public_url": storage_info.get("public_url"),
                "metadata": {
                    **(import_payload.get("metadata") or {}),
                    "thumbnail_storage_bucket": storage_info.get("thumbnail_bucket"),
                    "thumbnail_storage_path": storage_info.get("thumbnail_path"),
                    "thumbnail_mime_type": storage_info.get("thumbnail_mime_type"),
                    "thumbnail_size": storage_info.get("thumbnail_size"),
                },
            })
            created = create_knowledge_asset(import_payload)
            items.append({
                "status": "imported",
                "id": str(created.get("id")),
                "asset_id": asset_id,
                "asset_type": import_payload.get("asset_type"),
                "file_name": local_path.name,
            })
            time.sleep(0.02)
        except Exception as exc:
            items.append({
                "status": "failed",
                "asset_id": asset_id,
                "asset_type": payload.get("asset_type"),
                "file_name": local_path.name,
                "error": str(exc),
            })

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "payloads": _rel(payload_path),
        "batch_id": batch_id,
        "dry_run": args.dry_run,
        "refresh": args.refresh,
        "embedding": not args.no_embedding and not args.dry_run,
        "total": len(payloads),
        "imported": sum(1 for item in items if item["status"] == "imported"),
        "skipped": sum(1 for item in items if item["status"] in {"dry_run", "missing_file"}),
        "failed": sum(1 for item in items if item["status"] == "failed"),
        "deleted_existing": deleted_existing,
        "items": items,
    }
    md_path = _write_report(args.report.resolve(), report)
    print(json.dumps({key: report[key] for key in ["batch_id", "dry_run", "total", "imported", "skipped", "failed", "deleted_existing"]}, ensure_ascii=False, indent=2))
    print(f"JSON: {_rel(args.report.resolve())}")
    print(f"Report: {_rel(md_path)}")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

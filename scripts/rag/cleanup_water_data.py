#!/usr/bin/env python3
"""清理水利（water_*）历史知识数据，使知识库回归为国网电力场景纯净集。

设计原则（安全可回滚）：
- 删除前先把将被删除的行导出为 JSON 备份（含 document_chunks / knowledge_documents /
  knowledge_assets），写入 backups/water_cleanup_<时间戳>/。
- 默认 dry-run：只统计与备份，不删除。加 --apply 才真正删除。
- 范围严格限定：
    * knowledge_documents.category LIKE 'water%'
    * 上述文档关联的 document_chunks（按 document_id 外键，ON DELETE CASCADE 也会删，
      这里显式统计/备份以便审计）
    * document_chunks.metadata->>'seed_corpus' IN ('water_resources','water_enterprise_mock')
    * knowledge_assets.industry = '水利行业'
- 不触碰：embedding 为空的招标解析 chunk（属于 bid_projects，有 project_id、无 document_id 关联到 water 文档）。

用法：
    python scripts/rag/cleanup_water_data.py            # dry-run，仅统计+备份
    python scripts/rag/cleanup_water_data.py --apply    # 实际删除
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

WATER_DOC_CATEGORY_PREFIX = "water"
WATER_SEED_CORPORA = ("water_resources", "water_enterprise_mock")
WATER_ASSET_INDUSTRY = "水利行业"


def _fetch_all(cur, sql: str, params: tuple = ()) -> list[dict]:
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _json_default(value):
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="清理水利历史知识数据")
    parser.add_argument("--apply", action="store_true", help="实际执行删除（默认仅 dry-run + 备份）")
    args = parser.parse_args()

    if not DATABASE_URL:
        print("缺少 DATABASE_URL", file=sys.stderr)
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = PROJECT_ROOT / "backups" / f"water_cleanup_{ts}"

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            water_docs = _fetch_all(
                cur,
                "select * from knowledge_documents where category like %s",
                (f"{WATER_DOC_CATEGORY_PREFIX}%",),
            )
            water_doc_ids = [d["id"] for d in water_docs]

            water_chunks = _fetch_all(
                cur,
                """
                select * from document_chunks
                where (document_id = any(%s))
                   or (metadata->>'seed_corpus' = any(%s))
                """,
                (water_doc_ids, list(WATER_SEED_CORPORA)),
            )
            water_assets = _fetch_all(
                cur,
                "select * from knowledge_assets where industry = %s",
                (WATER_ASSET_INDUSTRY,),
            )

            print("将清理的水利数据范围：")
            print(f"  knowledge_documents : {len(water_docs)}")
            print(f"  document_chunks     : {len(water_chunks)}")
            print(f"  knowledge_assets    : {len(water_assets)}")

            # 备份（无论 dry-run 还是 apply 都先备份）
            backup_dir.mkdir(parents=True, exist_ok=True)
            for name, rows in (
                ("knowledge_documents", water_docs),
                ("document_chunks", water_chunks),
                ("knowledge_assets", water_assets),
            ):
                # embedding 字段较大，备份保留以便完整恢复
                (backup_dir / f"{name}.json").write_text(
                    json.dumps(rows, ensure_ascii=False, indent=2, default=_json_default),
                    encoding="utf-8",
                )
            print(f"已备份到：{backup_dir}")

            if not args.apply:
                print("dry-run 完成，未删除任何数据。加 --apply 执行删除。")
                return 0

            # 实际删除：先删 assets 与 chunks（chunks 也会被文档级联删，这里显式删 seed 命中的），再删文档
            cur.execute(
                "delete from knowledge_assets where industry = %s",
                (WATER_ASSET_INDUSTRY,),
            )
            deleted_assets = cur.rowcount
            cur.execute(
                "delete from document_chunks where metadata->>'seed_corpus' = any(%s)",
                (list(WATER_SEED_CORPORA),),
            )
            deleted_chunks_seed = cur.rowcount
            cur.execute(
                "delete from knowledge_documents where category like %s",
                (f"{WATER_DOC_CATEGORY_PREFIX}%",),
            )
            deleted_docs = cur.rowcount
            conn.commit()

            print("删除完成：")
            print(f"  knowledge_assets    deleted = {deleted_assets}")
            print(f"  document_chunks(seed) deleted = {deleted_chunks_seed}")
            print(f"  knowledge_documents deleted = {deleted_docs}（关联 chunk 级联删除）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Query structured customer goods-list rows for validation and operations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.postgres_pool import pooled_connection  # noqa: E402


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for structured goods-list query")
    return url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id")
    parser.add_argument("--province")
    parser.add_argument("--package-code")
    parser.add_argument("--keyword")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    clauses: list[str] = []
    params: list[object] = []
    if args.batch_id:
        clauses.append("ingestion_batch_id = %s")
        params.append(args.batch_id)
    if args.province:
        clauses.append("province = %s")
        params.append(args.province)
    if args.package_code:
        clauses.append("package_code = %s")
        params.append(args.package_code)
    if args.keyword:
        clauses.append(
            "(item_name ilike %s or item_description ilike %s or material_code ilike %s "
            "or technical_spec_code ilike %s or row_data::text ilike %s)"
        )
        like = f"%{args.keyword}%"
        params.extend([like, like, like, like, like])
    where_sql = " where " + " and ".join(clauses) if clauses else ""
    params.append(args.limit)
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            select province, batch_no, package_code, package_name, subpackage_no,
                   item_name, item_description, unit, quantity,
                   technical_spec_code, material_code, delivery_place, row_number
            from public.power_grid_goods_list_rows
            """
            + where_sql
            + " order by province, package_code, row_number limit %s",
            params,
        ).fetchall()
    print(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify Taichang supplement P1B quality with real DB and stream route."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs" / "rag" / "runs"
BATCH_ID = "customer_taichang_supplement_20260611"

sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.postgres_pool import pooled_connection  # noqa: E402


QUERIES = {
    "compound_contract_award": "泰昌补充资料里有没有同类产品供货合同或中标通知书？请说明资料来源。",
    "logo_assets": "泰昌有没有官方Logo和生产线、产品实物图片可以用于标书配图？请列出可用资产类型。",
    "report_params": "泰昌CPVC和MPP内径250检验报告的报告编号、平均内径或环刚度是多少？请说明来源。",
}


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required")
    return url


def _fetch_db_audit() -> dict[str, Any]:
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        document_count = conn.execute(
            """
            select count(*) as count
            from public.knowledge_documents
            where metadata->>'ingestion_batch_id' = %s
               or metadata->>'source_batch_id' = %s
            """,
            [BATCH_ID, BATCH_ID],
        ).fetchone()["count"]
        chunk_count = conn.execute(
            """
            select count(*) as count
            from public.document_chunks
            where metadata->>'ingestion_batch_id' = %s
               or metadata->>'source_batch_id' = %s
            """,
            [BATCH_ID, BATCH_ID],
        ).fetchone()["count"]
        asset_count = conn.execute(
            """
            select count(*) as count
            from public.knowledge_assets
            where metadata->>'source_batch_id' = %s
               or metadata->>'ingestion_batch_id' = %s
            """,
            [BATCH_ID, BATCH_ID],
        ).fetchone()["count"]
        bad_asset_count = conn.execute(
            """
            select count(*) as count
            from public.knowledge_assets
            where (metadata->>'source_batch_id' = %s or metadata->>'ingestion_batch_id' = %s)
              and (
                metadata->>'source_domain' is distinct from 'enterprise_fact'
                or metadata->>'enterprise' is distinct from '泰昌'
                or coalesce(metadata->>'reference_only', 'false') not in ('false', 'False')
              )
            """,
            [BATCH_ID, BATCH_ID],
        ).fetchone()["count"]
        asset_evidence_counts = conn.execute(
            """
            select metadata->>'evidence_type' as evidence_type, count(*) as count
            from public.knowledge_assets
            where metadata->>'source_batch_id' = %s
               or metadata->>'ingestion_batch_id' = %s
            group by metadata->>'evidence_type'
            order by count desc, evidence_type
            """,
            [BATCH_ID, BATCH_ID],
        ).fetchall()
        samples = conn.execute(
            """
            select id, title, category, asset_type, file_name,
                   metadata->>'evidence_type' as evidence_type,
                   metadata->>'source_file' as source_file
            from public.knowledge_assets
            where metadata->>'source_batch_id' = %s
               or metadata->>'ingestion_batch_id' = %s
            order by
              case
                when title like '%%Logo%%' then 0
                when title like '%%中标通知书%%' then 1
                when title like '%%合同%%' then 2
                when title like '%%生产线%%' then 3
                when title like '%%检验报告%%' then 4
                else 9
              end,
              title
            limit 20
            """,
            [BATCH_ID, BATCH_ID],
        ).fetchall()
    return {
        "document_count": int(document_count),
        "chunk_count": int(chunk_count),
        "asset_count": int(asset_count),
        "bad_asset_metadata_count": int(bad_asset_count),
        "asset_evidence_counts": [dict(row) for row in asset_evidence_counts],
        "asset_samples": [dict(row) for row in samples],
    }


def _decode_stream_response(response) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    answer = ""
    retrieved: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = []
    current: list[str] = []

    def handle(payload: str) -> None:
        nonlocal answer, retrieved
        if not payload.startswith("data:"):
            return
        try:
            data = json.loads(payload[5:].strip())
        except Exception as exc:
            errors.append({"parse_error": str(exc), "payload": payload[:200]})
            return
        events.append(data)
        if data.get("type") == "chunk":
            answer += data.get("content") or ""
        elif data.get("type") == "retrieved":
            retrieved = data
        elif data.get("type") == "error":
            errors.append(data)

    for raw in response.response:
        chunk = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        for line in chunk.splitlines():
            line = line.strip("\n")
            if not line:
                if current:
                    handle("\n".join(current))
                    current = []
                continue
            current.append(line)
    if current:
        handle("\n".join(current))

    return {
        "status_code": response.status_code,
        "has_error": bool(errors),
        "errors": errors,
        "event_types": [event.get("type") for event in events],
        "status_messages": [event.get("message") for event in events if event.get("type") == "status"],
        "retrieved": {
            "contexts_count": (retrieved or {}).get("contexts_count"),
            "assets_count": (retrieved or {}).get("assets_count"),
        },
        "answer_preview": answer[:3000],
        "answer": answer,
    }


def _run_stream_checks() -> dict[str, Any]:
    os.environ["APP_AUTH_ENABLED"] = "false"
    os.environ["APP_LOGIN_ENABLED"] = "false"
    os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
    os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
    os.environ["APP_ENV"] = "testing"

    import main  # noqa: WPS433

    app = main.app
    app.config.update(TESTING=True)
    client = app.test_client()

    results: dict[str, Any] = {}
    for key, query in QUERIES.items():
        response = client.post(
            "/api/bidding/knowledge/search/stream",
            json={"query": query},
            buffered=True,
        )
        decoded = _decode_stream_response(response)
        decoded["query"] = query
        results[key] = decoded
    return results


def _validate(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    db = report["database"]
    if db["document_count"] < 13:
        failures.append(f"expected at least 13 supplement documents, got {db['document_count']}")
    if db["chunk_count"] < 300:
        failures.append(f"expected at least 300 supplement chunks, got {db['chunk_count']}")
    if db["asset_count"] < 297:
        failures.append(f"expected at least 297 supplement assets, got {db['asset_count']}")
    if db["bad_asset_metadata_count"] != 0:
        failures.append(f"found bad supplement asset metadata rows: {db['bad_asset_metadata_count']}")

    streams = report["streams"]
    for key, result in streams.items():
        if result["status_code"] != 200 or result["has_error"]:
            failures.append(f"{key} stream failed: status={result['status_code']} errors={result['errors']}")
    compound_answer = streams["compound_contract_award"]["answer"]
    if "合同" not in compound_answer:
        failures.append("compound answer missing contract")
    if "中标通知书" not in compound_answer:
        failures.append("compound answer missing award notice")
    if "0322AB" not in compound_answer:
        failures.append("compound answer missing award notice tender no 0322AB")
    logo_answer = streams["logo_assets"]["answer"]
    if "Logo" not in logo_answer and "logo" not in logo_answer:
        failures.append("logo answer missing Logo")
    if "生产线" not in logo_answer:
        failures.append("logo answer missing production line")
    params_answer = streams["report_params"]["answer"]
    for expected in ["2024100312005501712", "2024100312005501713", "66.40", "250.2"]:
        if expected not in params_answer:
            failures.append(f"parameter answer missing {expected}")
    return failures


def _write_report(report: dict[str, Any]) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = report["run_id"]
    json_path = RUNS_DIR / f"{run_id}.json"
    md_path = RUNS_DIR / f"{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    status = "PASS" if not report["failures"] else "FAIL"
    lines = [
        f"# {run_id} — 泰昌补充资料 P1B 真实链路验证",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 批次：`{BATCH_ID}`",
        f"- 状态：{status}",
        "",
        "## 数据库质量复核",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 文档 | {report['database']['document_count']} |",
        f"| chunks | {report['database']['chunk_count']} |",
        f"| 图片资产 | {report['database']['asset_count']} |",
        f"| 异常资产 metadata | {report['database']['bad_asset_metadata_count']} |",
        "",
        "## 真实 stream 验证",
        "",
        "| 用例 | HTTP | 错误 | 资料/资产召回 | 结论 |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for key, result in report["streams"].items():
        retrieved = result.get("retrieved") or {}
        conclusion = "通过" if result["status_code"] == 200 and not result["has_error"] else "失败"
        lines.append(
            f"| `{key}` | {result['status_code']} | {result['has_error']} | "
            f"{retrieved.get('contexts_count')}/{retrieved.get('assets_count')} | {conclusion} |"
        )
    lines.extend(["", "## 结论", ""])
    if report["failures"]:
        lines.extend(f"- {failure}" for failure in report["failures"])
    else:
        lines.append("- P1B-1 数据库质量复核通过，P1B-3 复合问答漏答回归通过。")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def main_cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="run_20260611_taichang_supplement_p1b_quality")
    args = parser.parse_args()

    report = {
        "run_id": args.run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "batch_id": BATCH_ID,
        "database": _fetch_db_audit(),
        "streams": _run_stream_checks(),
    }
    report["failures"] = _validate(report)
    md_path = _write_report(report)
    print(json.dumps({"report": str(md_path.relative_to(PROJECT_ROOT)), "failures": report["failures"]}, ensure_ascii=False, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main_cli())

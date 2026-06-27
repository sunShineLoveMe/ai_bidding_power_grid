#!/usr/bin/env python3
"""Refresh Taichang product parameters and run the required regression checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs" / "rag" / "runs"
DEFAULT_RUN_ID = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_taichang_product_parameter_refresh"
DEFAULT_AUTH_FILE = Path("/tmp/taichang_auth.json")

MIN_PARSED_DOCUMENTS = 2
MIN_PARAMETER_ROWS = 30

STREAM_QUERIES = {
    "mpp_ring_stiffness": "泰昌MPP电缆保护管内径250的环刚度检验结果是多少？请说明报告编号和资料来源。",
    "cpvc_diameter_wall": "泰昌CPVC电缆保护管内径250的平均内径和壁厚检验结果是多少？请说明报告编号和资料来源。",
}


def _run(command: list[str], *, label: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    print(f"\n>>> {label}")
    print(" ".join(command))
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}")
    return completed


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_extraction_report(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if int(report.get("parsed_documents") or 0) < MIN_PARSED_DOCUMENTS:
        failures.append(f"parsed_documents below {MIN_PARSED_DOCUMENTS}: {report.get('parsed_documents')}")
    if int(report.get("parameter_rows") or 0) < MIN_PARAMETER_ROWS:
        failures.append(f"parameter_rows below {MIN_PARAMETER_ROWS}: {report.get('parameter_rows')}")
    if (report.get("qa_reference") or {}).get("scope") != "qa_only_not_coverage_judgement":
        failures.append("qa_reference scope is not qa_only_not_coverage_judgement")
    families = report.get("by_product_family") or {}
    if not any("CPVC" in str(name) for name in families):
        failures.append("CPVC product family missing")
    if not any("MPP" in str(name) for name in families):
        failures.append("MPP product family missing")
    return failures


def _stream_query(query: str, *, auth_file: Path, base_url: str) -> dict[str, Any]:
    auth = _load_json(auth_file)
    token = auth.get("token")
    if not token:
        raise RuntimeError(f"auth token missing in {auth_file}")
    response = requests.post(
        f"{base_url.rstrip('/')}/api/knowledge/search/stream",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=240,
        stream=True,
    )
    response.raise_for_status()
    events: list[dict[str, Any]] = []
    answer = ""
    retrieved: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = []
    current: list[str] = []

    def handle(payload: str) -> None:
        nonlocal answer, retrieved
        try:
            data = json.loads(payload[5:].strip())
        except Exception as exc:  # pragma: no cover - only for malformed SSE payloads.
            errors.append({"parse_error": str(exc), "payload": payload[:200]})
            return
        events.append(data)
        if data.get("type") == "chunk":
            answer += data.get("content") or ""
        elif data.get("type") == "retrieved":
            retrieved = data
        elif data.get("type") == "error":
            errors.append(data)

    for raw in response.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        line = raw.strip("\n")
        if not line:
            if current:
                handle("\n".join(current))
                current = []
            continue
        if line.startswith("data:"):
            current.append(line)
    if current:
        handle("\n".join(current))

    contexts = (retrieved or {}).get("raw_contexts") or []
    return {
        "query": query,
        "done": any(event.get("type") == "done" for event in events),
        "errors": errors,
        "event_count": len(events),
        "context_count": len(contexts),
        "answer": answer,
        "answer_preview": answer[:1800],
    }


def _validate_stream_results(results: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    mpp = results.get("mpp_ring_stiffness") or {}
    cpvc = results.get("cpvc_diameter_wall") or {}
    if not mpp.get("done") or mpp.get("errors"):
        failures.append("MPP stream did not complete cleanly")
    if "66.40" not in str(mpp.get("answer") or ""):
        failures.append("MPP stream answer missing 66.40")
    if not cpvc.get("done") or cpvc.get("errors"):
        failures.append("CPVC stream did not complete cleanly")
    cpvc_answer = str(cpvc.get("answer") or "")
    if "250.2" not in cpvc_answer or "250.4" not in cpvc_answer:
        failures.append("CPVC stream answer missing average inner diameter range")
    if "15.2" not in cpvc_answer or "15.3" not in cpvc_answer:
        failures.append("CPVC stream answer missing wall thickness range")
    return failures


def _write_summary(
    *,
    run_id: str,
    extraction_report: dict[str, Any],
    gate_summary_path: Path,
    stream_path: Path | None,
    failures: list[str],
) -> Path:
    out = RUNS_DIR / f"{run_id}_summary.md"
    status = "PASS" if not failures else "FAIL"
    lines = [
        f"# {run_id} — 泰昌产品参数重抽取与真实链路回归",
        "",
        f"- 生成时间：{datetime.now(timezone.utc).isoformat()}",
        f"- 状态：{status}",
        "",
        "## 抽取结果",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 检验报告文档 | {extraction_report.get('documents')} |",
        f"| 成功抽取文档 | {extraction_report.get('parsed_documents')} |",
        f"| 产品参数行 | {extraction_report.get('parameter_rows')} |",
        "",
        "## 回归结果",
        "",
        f"- 增量回归门禁：`{gate_summary_path.relative_to(PROJECT_ROOT)}`",
    ]
    if stream_path:
        lines.append(f"- 页面同源 stream 抽样：`{stream_path.relative_to(PROJECT_ROOT)}`")
    lines.extend(["", "## 结论", ""])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- 重抽取、结构化参数查询、真实 stream 抽样和增量回归门禁均通过。")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)
    parser.add_argument("--stream-base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--skip-stream", action="store_true", help="Skip real same-origin stream checks.")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id
    failures: list[str] = []

    _run([sys.executable, "scripts/rag/extract_taichang_product_parameters.py"], label="Extract Taichang product parameters")
    extraction_report_path = (
        PROJECT_ROOT
        / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0"
        / "staging/taichang_product_parameters/extract_taichang_product_parameters_report.json"
    )
    extraction_report = _load_json(extraction_report_path)
    failures.extend(_validate_extraction_report(extraction_report))

    _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_taichang_product_parameter_extraction.py",
            "tests/test_taichang_product_parameter_query.py",
            "-q",
        ],
        label="Product parameter unit/query regression",
    )

    gate_id = f"{run_id}_gate"
    _run(
        [sys.executable, "scripts/rag/run_incremental_regression_gate.py", "--run-id", gate_id],
        label="Incremental regression gate",
        timeout=180,
    )
    gate_summary_path = RUNS_DIR / f"{gate_id}_summary.md"

    stream_path: Path | None = None
    if not args.skip_stream:
        if not args.auth_file.exists():
            failures.append(f"stream auth file missing: {args.auth_file}")
        else:
            stream_results = {
                key: _stream_query(query, auth_file=args.auth_file, base_url=args.stream_base_url)
                for key, query in STREAM_QUERIES.items()
            }
            failures.extend(_validate_stream_results(stream_results))
            stream_path = RUNS_DIR / f"{run_id}_real_stream.json"
            stream_path.write_text(json.dumps(stream_results, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = _write_summary(
        run_id=run_id,
        extraction_report=extraction_report,
        gate_summary_path=gate_summary_path,
        stream_path=stream_path,
        failures=failures,
    )
    print(f"\nSummary: {summary}")
    print("Refresh:", "PASS" if not failures else "FAIL")
    if failures:
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

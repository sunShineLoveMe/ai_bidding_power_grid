#!/usr/bin/env python3
"""Run the local RAG quality gate with real services."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs" / "rag" / "runs"
DEFAULT_BASE_URL = "http://127.0.0.1:3012"
DEFAULT_USERNAME = "codex_regression_20260616"
DEFAULT_PASSWORD = "CodexRegression20260616!"
DEFAULT_STREAM_QUERY = "泰昌MPP生产线有哪些图片资料？"


@dataclass
class StepResult:
    name: str
    status: str
    duration_ms: int
    detail: str = ""
    artifact: str | None = None


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _artifact(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _run_command(name: str, command: list[str], *, artifact: Path | None = None) -> StepResult:
    started = _now_ms()
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    duration = _now_ms() - started
    if artifact:
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(completed.stdout, encoding="utf-8")
    detail = f"exit_code={completed.returncode}"
    if completed.returncode != 0:
        detail = f"{detail}; output_tail={completed.stdout[-1200:]}"
    return StepResult(
        name=name,
        status="pass" if completed.returncode == 0 else "fail",
        duration_ms=duration,
        detail=detail,
        artifact=_artifact(artifact) if artifact else None,
    )


def check_ready(base_url: str, timeout: int) -> tuple[StepResult, dict[str, Any]]:
    started = _now_ms()
    response = requests.get(f"{base_url.rstrip('/')}/api/ready", timeout=timeout)
    duration = _now_ms() - started
    payload = response.json()
    failed_checks = [
        name
        for name, check in (payload.get("checks") or {}).items()
        if isinstance(check, dict) and check.get("status") in {"fail", "error", "not_ready"}
    ]
    ok = response.status_code == 200 and payload.get("status") == "ok" and not failed_checks
    detail = f"http={response.status_code}; status={payload.get('status')}; failed_checks={failed_checks or []}"
    return StepResult("api_ready", "pass" if ok else "fail", duration, detail), payload


def login(base_url: str, username: str, password: str, timeout: int) -> str:
    response = requests.post(
        f"{base_url.rstrip('/')}/api/users/login",
        json={"username": username, "password": password},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("token") or payload.get("access_token") or (payload.get("data") or {}).get("token")
    if not token:
        raise RuntimeError("login response did not include token")
    return str(token)


def parse_sse_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        raw = line.removeprefix("data:").strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def summarize_stream_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    retrieved = next((event for event in events if event.get("type") == "retrieved"), {})
    return {
        "done": any(event.get("type") == "done" for event in events),
        "error": next((event.get("error") for event in events if event.get("type") == "error"), None),
        "contexts_count": retrieved.get("contexts_count", 0),
        "assets_count": retrieved.get("assets_count", 0),
        "images_count": len(retrieved.get("images") or []),
        "chunks": sum(1 for event in events if event.get("type") == "chunk"),
    }


def run_stream_sample(
    *,
    base_url: str,
    token: str,
    query: str,
    timeout: int,
    output: Path,
) -> tuple[StepResult, dict[str, Any]]:
    started = _now_ms()
    lines: list[str] = []
    response = requests.post(
        f"{base_url.rstrip('/')}/api/knowledge/search/stream",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query},
        stream=True,
        timeout=timeout,
    )
    response.raise_for_status()
    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line:
            lines.append(raw_line)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    events = parse_sse_events("\n".join(lines))
    summary = summarize_stream_events(events)
    ok = bool(summary["done"]) and not summary["error"] and (
        int(summary["contexts_count"] or 0) > 0 or int(summary["assets_count"] or 0) > 0
    )
    detail = (
        f"done={summary['done']}; contexts={summary['contexts_count']}; "
        f"assets={summary['assets_count']}; images={summary['images_count']}; error={summary['error']}"
    )
    return StepResult("stream_sample", "pass" if ok else "fail", _now_ms() - started, detail, _artifact(output)), summary


def write_summary(
    *,
    run_id: str,
    status: str,
    steps: list[StepResult],
    ready_payload: dict[str, Any] | None,
    stream_summary: dict[str, Any] | None,
    gate_summary_path: Path | None,
    json_path: Path,
    md_path: Path,
) -> None:
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "steps": [asdict(step) for step in steps],
        "ready": ready_payload,
        "stream_summary": stream_summary,
        "gate_summary_path": _artifact(gate_summary_path) if gate_summary_path else None,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {run_id} - RAG 本地门禁自动化入口",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 门禁状态：{status.upper()}",
        "",
        "## 步骤结果",
        "",
        "| 步骤 | 状态 | 耗时 | 详情 | 产物 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for step in steps:
        lines.append(
            f"| {step.name} | {step.status.upper()} | {step.duration_ms} ms | {step.detail} | {step.artifact or '-'} |"
        )
    lines.extend(["", "## 关键产物", ""])
    if gate_summary_path:
        lines.append(f"- 增量回归门禁：`{_artifact(gate_summary_path)}`")
    if stream_summary:
        lines.append(
            "- 真实 stream 抽样："
            f"contexts={stream_summary.get('contexts_count')}，"
            f"assets={stream_summary.get('assets_count')}，"
            f"done={stream_summary.get('done')}"
        )
    lines.extend(["", "## 结论", ""])
    if status == "pass":
        lines.append("- 本地 RAG 门禁通过。")
    else:
        lines.append("- 本地 RAG 门禁失败，请优先查看状态为 FAIL 的步骤和对应产物。")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_local_rag_gate")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--stream-query", default=DEFAULT_STREAM_QUERY)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--skip-unit-tests", action="store_true")
    parser.add_argument("--skip-incremental-gate", action="store_true")
    parser.add_argument("--skip-stream", action="store_true")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    run_id = args.run_id
    steps: list[StepResult] = []
    ready_payload: dict[str, Any] | None = None
    stream_summary: dict[str, Any] | None = None
    gate_summary_path: Path | None = None

    try:
        ready_step, ready_payload = check_ready(args.base_url, args.timeout)
        steps.append(ready_step)
    except Exception as exc:
        steps.append(StepResult("api_ready", "fail", 0, str(exc)))

    if not args.skip_unit_tests:
        steps.append(
            _run_command(
                "rag_unit_tests",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/test_incremental_regression_gate.py",
                    "tests/test_rag_retrieval.py",
                    "-q",
                ],
                artifact=RUNS_DIR / f"{run_id}_pytest.log",
            )
        )

    if not args.skip_incremental_gate:
        gate_run_id = f"{run_id}_incremental"
        steps.append(
            _run_command(
                "incremental_regression_gate",
                [sys.executable, "scripts/rag/run_incremental_regression_gate.py", "--run-id", gate_run_id],
                artifact=RUNS_DIR / f"{run_id}_incremental_gate.log",
            )
        )
        gate_summary_path = RUNS_DIR / f"{gate_run_id}_summary.md"

    if not args.skip_stream:
        try:
            token = login(args.base_url, args.username, args.password, args.timeout)
            stream_step, stream_summary = run_stream_sample(
                base_url=args.base_url,
                token=token,
                query=args.stream_query,
                timeout=args.timeout,
                output=RUNS_DIR / f"{run_id}_stream.jsonl",
            )
            steps.append(stream_step)
        except Exception as exc:
            steps.append(StepResult("stream_sample", "fail", 0, str(exc)))

    status = "pass" if steps and all(step.status == "pass" for step in steps) else "fail"
    json_path = RUNS_DIR / f"{run_id}_summary.json"
    md_path = RUNS_DIR / f"{run_id}_summary.md"
    write_summary(
        run_id=run_id,
        status=status,
        steps=steps,
        ready_payload=ready_payload,
        stream_summary=stream_summary,
        gate_summary_path=gate_summary_path,
        json_path=json_path,
        md_path=md_path,
    )
    print(f"Summary JSON: {_artifact(json_path)}")
    print(f"Summary MD: {_artifact(md_path)}")
    print(f"Gate: {status.upper()}")
    for step in steps:
        print(f"- {step.name}: {step.status.upper()} ({step.detail})")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

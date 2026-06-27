#!/usr/bin/env python3
"""Run the standard RAG incremental regression gate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs" / "rag" / "runs"
CUSTOMER_TESTSET = "tests/rag/customer_liaoning_taichang_testset.jsonl"

DEFAULT_THRESHOLDS = {
    "base_recall_min": 0.9667,
    "base_top1_min": 1.0,
    "base_cross_max": 0.0,
    "customer_qwen3_recall_min": 1.0,
    "customer_qwen3_top1_min": 1.0,
    "customer_qwen3_forbidden_max": 0.0,
    "customer_qwen3_cross_max": 0.0,
}


def _run_eval(label: str, args: list[str], output: Path) -> dict[str, Any]:
    command = [sys.executable, "scripts/rag/eval_recall.py", *args, "--save", str(output.relative_to(PROJECT_ROOT))]
    print(f"\n>>> {label}")
    print(" ".join(command))
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}")
    return json.loads(output.read_text(encoding="utf-8"))


def _metric(row: dict[str, Any], key: str) -> float:
    value = row.get(key)
    return float(value or 0)


def _check_gate(results: dict[str, dict[str, Any]], thresholds: dict[str, float]) -> list[str]:
    failures: list[str] = []
    base_qwen3 = results["base_qwen3"]
    customer_qwen3 = results["customer_qwen3"]

    if _metric(base_qwen3, "recall_at_5") < thresholds["base_recall_min"]:
        failures.append(f"Base qwen3 Recall@5 below threshold: {base_qwen3.get('recall_at_5')}")
    if _metric(base_qwen3, "role_accuracy_top1") < thresholds["base_top1_min"]:
        failures.append(f"Base qwen3 top1 accuracy below threshold: {base_qwen3.get('role_accuracy_top1')}")
    if _metric(base_qwen3, "avg_cross_role_ratio") > thresholds["base_cross_max"]:
        failures.append(f"Base qwen3 cross-role ratio above threshold: {base_qwen3.get('avg_cross_role_ratio')}")

    if _metric(customer_qwen3, "recall_at_5") < thresholds["customer_qwen3_recall_min"]:
        failures.append(f"Customer qwen3 Recall@5 below threshold: {customer_qwen3.get('recall_at_5')}")
    if _metric(customer_qwen3, "role_accuracy_top1") < thresholds["customer_qwen3_top1_min"]:
        failures.append(f"Customer qwen3 top1 accuracy below threshold: {customer_qwen3.get('role_accuracy_top1')}")
    if _metric(customer_qwen3, "forbidden_hit_rate") > thresholds["customer_qwen3_forbidden_max"]:
        failures.append(f"Customer qwen3 forbidden hit rate above threshold: {customer_qwen3.get('forbidden_hit_rate')}")
    if _metric(customer_qwen3, "avg_cross_role_ratio") > thresholds["customer_qwen3_cross_max"]:
        failures.append(f"Customer qwen3 cross-role ratio above threshold: {customer_qwen3.get('avg_cross_role_ratio')}")
    if int(customer_qwen3.get("rerank_scored_cases") or 0) <= 0:
        failures.append("Customer qwen3 did not record rerank scores; online rerank may not have run.")
    return failures


def _fmt_pct(value: Any) -> str:
    return f"{float(value or 0) * 100:.1f}%"


def _write_summary(run_id: str, results: dict[str, dict[str, Any]], failures: list[str], thresholds: dict[str, float]) -> Path:
    out = RUNS_DIR / f"{run_id}_summary.md"
    status = "PASS" if not failures else "FAIL"
    lines = [
        f"# {run_id} — RAG 增量回归门禁",
        "",
        f"- 生成时间：{datetime.now(timezone.utc).isoformat()}",
        f"- 门禁状态：{status}",
        f"- 测试集：Base 30 + 泰昌专项 30",
        "",
        "## 结果",
        "",
        "| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in [
        ("base_off", "Base / off"),
        ("base_qwen3", "Base / qwen3-rerank"),
        ("customer_off", "泰昌专项 / off"),
        ("customer_qwen3", "泰昌专项 / qwen3-rerank"),
    ]:
        row = results[key]
        lines.append(
            "| {label} | {mode} | {recall} | {top1} | {mrr:.3f} | {forbidden} | {cross} | {latency:.0f} ms | {scored} |".format(
                label=label.rsplit(" / ", 1)[0],
                mode=label.rsplit(" / ", 1)[1],
                recall=_fmt_pct(row.get("recall_at_5")),
                top1=_fmt_pct(row.get("role_accuracy_top1")),
                mrr=float(row.get("mrr") or 0),
                forbidden=_fmt_pct(row.get("forbidden_hit_rate")),
                cross=_fmt_pct(row.get("avg_cross_role_ratio")),
                latency=float(row.get("avg_latency_ms") or 0),
                scored=row.get("rerank_scored_cases"),
            )
        )
    lines.extend([
        "",
        "## 阈值",
        "",
        "```json",
        json.dumps(thresholds, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 结论",
        "",
    ])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- 门禁通过，无召回、来源排序、禁用关键词或跨资料域串扰退化。")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_incremental_regression_gate")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id

    outputs = {
        "base_off": RUNS_DIR / f"{run_id}_base_off.json",
        "base_qwen3": RUNS_DIR / f"{run_id}_base_qwen3.json",
        "customer_off": RUNS_DIR / f"{run_id}_customer_off.json",
        "customer_qwen3": RUNS_DIR / f"{run_id}_customer_qwen3.json",
    }
    results = {
        "base_off": _run_eval("Base rerank off", ["--k", str(args.k), "--rerank", "off"], outputs["base_off"]),
        "base_qwen3": _run_eval(
            "Base qwen3-rerank",
            ["--k", str(args.k), "--rerank", "on", "--rerank-model", "qwen3-rerank"],
            outputs["base_qwen3"],
        ),
        "customer_off": _run_eval(
            "Customer rerank off",
            ["--k", str(args.k), "--testset", CUSTOMER_TESTSET, "--rerank", "off"],
            outputs["customer_off"],
        ),
        "customer_qwen3": _run_eval(
            "Customer qwen3-rerank",
            ["--k", str(args.k), "--testset", CUSTOMER_TESTSET, "--rerank", "on", "--rerank-model", "qwen3-rerank"],
            outputs["customer_qwen3"],
        ),
    }
    failures = _check_gate(results, DEFAULT_THRESHOLDS)
    summary = _write_summary(run_id, results, failures, DEFAULT_THRESHOLDS)
    print(f"\nSummary: {summary}")
    print("Gate:", "PASS" if not failures else "FAIL")
    if failures:
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

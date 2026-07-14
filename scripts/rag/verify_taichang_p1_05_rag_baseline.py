#!/usr/bin/env python3
"""通过真实 stream 验证 P1-05 产品预过滤、结构化参数与范围守卫。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.rag.verify_taichang_p1_03_business_ledgers import _combined, _stream  # noqa: E402

RUNS_DIR = PROJECT_ROOT / "docs/rag/runs"
DEFAULT_AUTH_FILE = Path("/tmp/p1_03_login.json")
QUERIES = {
    "cross_product_guard": "泰昌架空绝缘导线有哪些检验报告和结构化参数？不得引用其他产品事实。",
    "mpp_parameter": "泰昌MPP电缆保护管内径250的环刚度检验结果是多少？请说明报告编号、来源和页码。",
    "cpvc_parameter": "泰昌CPVC电缆保护管内径250的平均内径和壁厚是多少？请说明报告编号、来源和页码。",
}


def _validate(results: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for key, result in results.items():
        if not result.get("done") or result.get("errors"):
            failures.append(f"{key}: stream 未正常完成")
    guard = _combined(results["cross_product_guard"])
    for expected in ("未发现", "不得跨产品引用", "补充"):
        if expected not in guard:
            failures.append(f"cross_product_guard: 缺少范围守卫表达 {expected}")
    for forbidden in ("CPVC", "MPP", "N-HAP", "UPVC", "2024100312005501712", "2024100312005501713"):
        if forbidden in guard:
            failures.append(f"cross_product_guard: 串入其他产品事实 {forbidden}")
    mpp = _combined(results["mpp_parameter"])
    for expected in ("66.40", "2024100312005501712", "第3页"):
        if expected not in mpp:
            failures.append(f"mpp_parameter: 缺少 {expected}")
    if "2024100312005501713" in mpp:
        failures.append("mpp_parameter: 串入 CPVC 报告")
    cpvc = _combined(results["cpvc_parameter"])
    for expected in ("250.2", "250.4", "15.2", "15.3", "2024100312005501713", "第3页"):
        if expected not in cpvc:
            failures.append(f"cpvc_parameter: 缺少 {expected}")
    if "2024100312005501712" in cpvc or "280.5" in cpvc:
        failures.append("cpvc_parameter: 串入 MPP 报告或承口尺寸")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:3012")
    parser.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)
    parser.add_argument("--run-id", default="20260714_taichang_p1_05_structured_rag_stream")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    auth = json.loads(args.auth_file.read_text(encoding="utf-8"))
    token = str(auth.get("token") or "")
    if not token:
        raise RuntimeError(f"auth token missing in {args.auth_file}")
    ready = requests.get(f"{args.base_url.rstrip('/')}/api/ready", timeout=30)
    ready.raise_for_status()
    results = {key: _stream(args.base_url, token, query, args.timeout) for key, query in QUERIES.items()}
    failures = _validate(results)
    payload = {
        "run_id": args.run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not failures else "fail",
        "real_api": True,
        "mock_used": False,
        "base_url": args.base_url,
        "ready": ready.json(),
        "failures": failures,
        "results": results,
    }
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RUNS_DIR / f"{args.run_id}.json"
    summary_path = RUNS_DIR / f"{args.run_id}_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 泰昌 P1-05 结构化事实基线真实流式验证", "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 状态：{'PASS' if not failures else 'FAIL'}",
        "- 链路：真实 `/api/knowledge/search/stream`，真实 LLM，未使用 mock", "",
        "## 结果", "", "| 用例 | 完成 | 上下文 | 资产 |", "| --- | --- | ---: | ---: |",
    ]
    for key, result in results.items():
        lines.append(f"| {key} | {result['done']} | {result['contexts_count']} | {result['assets_count']} |")
    lines.extend(["", "## 结论", ""])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend([
            "- 架空绝缘导线问题仅命中范围守卫，未召回其他产品事实。",
            "- MPP 环刚度和 CPVC 平均内径/壁厚均返回准确数值、报告编号和来源页。",
            "- 结构化直查与父子分块向量召回可并行使用，未使用 mock。",
        ])
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "failures": failures, "json": str(json_path), "summary": str(summary_path)}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

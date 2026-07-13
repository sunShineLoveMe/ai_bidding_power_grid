#!/usr/bin/env python3
"""通过真实知识库流式 API 验证 P1-01 入库及技术参数精确性。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs/rag/runs"
DEFAULT_RUN_ID = "20260713_taichang_historical_bid_p1_01_stream"
QUERIES = {
    "mpp_ring_stiffness": "泰昌MPP电缆保护管内径250的环刚度检验结果是多少？请说明报告编号和资料来源。",
    "cpvc_diameter_wall": "泰昌CPVC电缆保护管内径250的平均内径和壁厚检验结果是多少？请说明报告编号和资料来源。",
    "historical_asset": "泰昌历史技术标中的现状环境影响评估报告有哪些知识资料？",
}


def _stream(base_url: str, query: str, timeout: int) -> dict[str, Any]:
    response = requests.post(
        f"{base_url.rstrip('/')}/api/knowledge/search/stream",
        json={"query": query},
        stream=True,
        timeout=timeout,
    )
    response.raise_for_status()
    events: list[dict[str, Any]] = []
    answer = ""
    retrieved: dict[str, Any] = {}
    for raw in response.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data:"):
            continue
        try:
            event = json.loads(raw[5:].strip())
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        if event.get("type") == "chunk":
            answer += str(event.get("content") or "")
        elif event.get("type") == "retrieved":
            retrieved = event
    return {
        "query": query,
        "http_status": response.status_code,
        "done": any(event.get("type") == "done" for event in events),
        "errors": [event for event in events if event.get("type") == "error"],
        "event_count": len(events),
        "contexts_count": retrieved.get("contexts_count", 0),
        "assets_count": retrieved.get("assets_count", 0),
        "raw_contexts": retrieved.get("raw_contexts") or [],
        "assets": retrieved.get("assets") or [],
        "answer": answer,
    }


def _validate(results: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for key, result in results.items():
        if not result["done"] or result["errors"]:
            failures.append(f"{key}: stream 未正常完成")

    mpp = results["mpp_ring_stiffness"]
    mpp_answer = mpp["answer"]
    for value in ("66.40", "2024100312005501712"):
        if value not in mpp_answer:
            failures.append(f"MPP 回答缺少 {value}")
    if "2024100312005501713" in mpp_answer:
        failures.append("MPP 回答串入 CPVC 报告编号")

    cpvc = results["cpvc_diameter_wall"]
    cpvc_answer = cpvc["answer"]
    for value in ("250.2", "250.4", "15.2", "15.3", "2024100312005501713"):
        if value not in cpvc_answer:
            failures.append(f"CPVC 回答缺少 {value}")
    for forbidden in ("280.5", "2024100312005501712"):
        if forbidden in cpvc_answer:
            failures.append(f"CPVC 回答错误包含 {forbidden}")
    context_text = "\n".join(str(row.get("content") or "") for row in cpvc["raw_contexts"])
    for value in ("尺寸-平均内径", "250.2~250.4", "尺寸-壁厚", "15.2~15.3"):
        if value not in context_text:
            failures.append(f"CPVC 原始召回上下文缺少 {value}")
    if "承口平均内径" in context_text or "280.5" in context_text:
        failures.append("CPVC 原始召回上下文把承口平均内径误作管体平均内径")

    asset = results["historical_asset"]
    asset_titles = [str(row.get("title") or "") for row in asset["assets"]]
    if not any("现状环境影响评估报告" in title for title in asset_titles):
        failures.append("历史标书知识资产未从真实 stream 召回")
    if "历史标书内嵌" not in asset["answer"]:
        failures.append("历史资产回答缺少历史 Word 内嵌来源边界")
    has_formal_boundary = any(term in asset["answer"] for term in ("正式投标附件", "正式法定文件", "正式法定效力"))
    has_negative_boundary = any(term in asset["answer"] for term in ("不得", "不能", "不可", "不具备", "并非"))
    if not (has_formal_boundary and has_negative_boundary):
        failures.append("历史资产回答缺少禁止直接用于正式投标的边界")
    asset_context_text = "\n".join(str(row.get("content") or "") for row in asset["raw_contexts"])
    for boundary in ("不得直接作为精确参数", "正式投标附件"):
        if boundary not in asset_context_text:
            failures.append(f"历史资产原始召回上下文缺少确定性边界：{boundary}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    ready = requests.get(f"{args.base_url.rstrip('/')}/api/ready", timeout=30)
    ready.raise_for_status()
    ready_payload = ready.json()
    results = {key: _stream(args.base_url, query, args.timeout) for key, query in QUERIES.items()}
    failures = _validate(results)
    payload = {
        "run_id": args.run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not failures else "fail",
        "real_api": True,
        "mock_used": False,
        "base_url": args.base_url,
        "ready": ready_payload,
        "failures": failures,
        "results": results,
    }
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RUNS_DIR / f"{args.run_id}.json"
    md_path = RUNS_DIR / f"{args.run_id}_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 泰昌历史标书 P1-01 真实流式链路验证",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 状态：{'PASS' if not failures else 'FAIL'}",
        "- 链路：真实 `/api/knowledge/search/stream`，未使用 mock",
        "",
        "## 验证结果",
        "",
        "| 用例 | 完成 | 资料上下文 | 图片资产 | 关键结论 |",
        "| --- | --- | ---: | ---: | --- |",
        f"| MPP 环刚度 | {results['mpp_ring_stiffness']['done']} | {results['mpp_ring_stiffness']['contexts_count']} | {results['mpp_ring_stiffness']['assets_count']} | 66.40 kN/m²，报告 2024100312005501712 |",
        f"| CPVC 平均内径和壁厚 | {results['cpvc_diameter_wall']['done']} | {results['cpvc_diameter_wall']['contexts_count']} | {results['cpvc_diameter_wall']['assets_count']} | 250.2～250.4 mm、15.2～15.3 mm，报告 2024100312005501713 |",
        f"| 历史标书知识资产 | {results['historical_asset']['done']} | {results['historical_asset']['contexts_count']} | {results['historical_asset']['assets_count']} | 成功召回且明确仅作内部知识资料 |",
        "",
        "## 精度门禁",
        "",
        "- CPVC 普通平均内径问题不得召回或回答承口平均内径 280.5 mm。",
        "- CPVC 与 MPP 报告编号不得串用。",
        "- 历史 Word 内嵌图片不得作为精确参数或正式附件来源。",
        "",
        "## 失败项",
        "",
        *(f"- {item}" for item in failures),
    ]
    if not failures:
        lines.append("- 无。")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "failures": failures, "json": str(json_path), "summary": str(md_path)}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

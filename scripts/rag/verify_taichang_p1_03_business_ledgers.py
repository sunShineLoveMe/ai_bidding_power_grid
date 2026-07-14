#!/usr/bin/env python3
"""通过真实知识库流式 API 验证泰昌 P1-03 结构化参数和业务台账。"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs/rag/runs"
DEFAULT_RUN_ID = "20260714_taichang_p1_03_business_ledgers_stream"
DEFAULT_AUTH_FILE = Path("/tmp/p1_03_login.json")
QUERIES = {
    "equipment": "泰昌微机控制电子万能试验机的型号、管理编号、校准证书编号、校准日期和复校日期是什么？请给出资料来源和页码。",
    "expired_certificate": "泰昌职业健康安全管理体系认证证书是否仍在有效期？请给出证书编号、有效期和资料来源。",
    "missing_reports": "泰昌N-HAP和UPVC检验报告是否有原始报告，能否生成正式参数？请分别说明报告编号和证据边界。",
    "audit": "泰昌2023、2024、2025年审计报告编号、会计师事务所和文件完整性如何？",
    "personnel": "泰昌人员花名册和试验检测人员证书有多少条？普通问答能否展示个人证件号？",
    "mpp_ring_stiffness": "泰昌MPP电缆保护管内径250的环刚度检验结果是多少？请说明报告编号、资料来源和页码。",
    "cpvc_diameter_wall": "泰昌CPVC电缆保护管内径250的平均内径和壁厚检验结果是多少？请说明报告编号、资料来源和页码。",
}


def _stream(base_url: str, token: str, query: str, timeout: int) -> dict[str, Any]:
    response = requests.post(
        f"{base_url.rstrip('/')}/api/knowledge/search/stream",
        headers={"Authorization": f"Bearer {token}"},
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
        "answer": answer,
    }


def _combined(result: dict[str, Any]) -> str:
    contexts = "\n".join(str(row.get("content") or "") for row in result.get("raw_contexts") or [])
    return f"{result.get('answer') or ''}\n{contexts}"


def _validate(results: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for key, result in results.items():
        if not result.get("done") or result.get("errors"):
            failures.append(f"{key}: stream 未正常完成")

    expected = {
        "equipment": ["WDW-1", "TC-8", "GL2605LX02282", "2026-05-26", "2027-05-25", "第6页"],
        "expired_certificate": ["626023S10219R0", "2026-06-18", "过期"],
        "missing_reports": ["2024400312005505333", "2025200312005503479", "不得生成正式参数"],
        "audit": ["世仁审字〔2024〕第VE-73号", "世仁审字〔2026〕第St-050号", "2024", "待人工复核"],
        "personnel": ["65", "2", "受限"],
        "mpp_ring_stiffness": ["66.40", "2024100312005501712", "第3页"],
        "cpvc_diameter_wall": ["250.2", "250.4", "15.2", "15.3", "2024100312005501713", "第3页"],
    }
    for key, values in expected.items():
        text = _combined(results[key])
        for value in values:
            if value not in text:
                failures.append(f"{key}: 回答与上下文缺少 {value}")

    missing_text = _combined(results["missing_reports"])
    for forbidden in ("2024100312005501713", "250.2~250.4", "15.2~15.3"):
        if forbidden in missing_text:
            failures.append(f"missing_reports: 错误串入 CPVC 正式参数 {forbidden}")
    personnel_text = _combined(results["personnel"])
    if re.search(r"\bT[0-9X]{16,20}\b", personnel_text):
        failures.append("personnel: 普通问答泄露完整个人证件号")
    cpvc_text = _combined(results["cpvc_diameter_wall"])
    if "280.5" in cpvc_text or "2024100312005501712" in cpvc_text:
        failures.append("cpvc_diameter_wall: 串入承口内径或MPP报告编号")
    mpp_text = _combined(results["mpp_ring_stiffness"])
    if "2024100312005501713" in mpp_text:
        failures.append("mpp_ring_stiffness: 串入CPVC报告编号")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:3012")
    parser.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
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
    labels = {
        "equipment": "设备校准台账",
        "expired_certificate": "体系证书有效期",
        "missing_reports": "N-HAP/UPVC补证边界",
        "audit": "审计报告台账",
        "personnel": "人员资料脱敏",
        "mpp_ring_stiffness": "MPP环刚度",
        "cpvc_diameter_wall": "CPVC平均内径和壁厚",
    }
    lines = [
        "# 泰昌 P1-03 结构化参数和业务台账真实流式验证",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 状态：{'PASS' if not failures else 'FAIL'}",
        "- 链路：真实 `/api/knowledge/search/stream`，真实 LLM，未使用 mock",
        "",
        "## 验证结果",
        "",
        "| 用例 | 完成 | 上下文 | 资产 |",
        "| --- | --- | ---: | ---: |",
    ]
    for key, result in results.items():
        lines.append(f"| {labels[key]} | {result['done']} | {result['contexts_count']} | {result['assets_count']} |")
    lines.extend(["", "## 失败项", ""])
    lines.extend(f"- {item}" for item in failures)
    if not failures:
        lines.append("- 无。")
    lines.extend([
        "",
        "## 边界结论",
        "",
        "- N-HAP、UPVC 仅保留历史报告编号，缺少原始报告，不能生成正式参数。",
        "- 2024 年审计报告编号保持为空并标记人工复核，不跨年度推断。",
        "- 人员明细保持 `restricted/internal_only`，真实普通问答不展示完整证件号。",
        "- 本轮不写数据库、不提升正式资产等级。",
    ])
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "failures": failures, "json": str(json_path), "summary": str(summary_path)}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

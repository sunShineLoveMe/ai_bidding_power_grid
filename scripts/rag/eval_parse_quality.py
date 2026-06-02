#!/usr/bin/env python3
"""Evaluate whether prepared customer parsing artifacts contain key evidence."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = PROJECT_ROOT / "tests" / "rag" / "customer_parse_qa_cases.jsonl"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _matches(record: dict[str, Any], selector: dict[str, Any]) -> bool:
    metadata = record.get("metadata") or {}
    for key, expected in selector.items():
        actual = record.get(key, metadata.get(key))
        if expected is not None and actual != expected:
            return False
    return True


def _record_text(record: dict[str, Any]) -> str:
    output_file = record.get("output_file")
    if not output_file:
        return ""
    path = PROJECT_ROOT / output_file
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _evaluate_case(case: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        record for record in records
        if record.get("parse_status") == "parsed" and _matches(record, case.get("selector") or {})
    ]
    keywords = case.get("must_include_keywords") or []
    candidate_results = []
    for record in candidates:
        text = _record_text(record)
        found = [kw for kw in keywords if kw in text]
        candidate_results.append({
            "source_file": record.get("source_file"),
            "output_file": record.get("output_file"),
            "found_keywords": found,
            "missing_keywords": [kw for kw in keywords if kw not in found],
            "hit": len(found) == len(keywords),
        })
    hit = any(item["hit"] for item in candidate_results)
    best = max(candidate_results, key=lambda item: len(item["found_keywords"]), default=None)
    return {
        "id": case["id"],
        "metric": case.get("metric"),
        "description": case.get("description"),
        "selector": case.get("selector"),
        "must_include_keywords": keywords,
        "candidate_count": len(candidates),
        "hit": hit,
        "best": best,
    }


def _write_markdown(summary: dict[str, Any], results: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# 客户资料解析 QA 评测报告",
        "",
        f"> Manifest：`{summary['manifest']}`",
        f"> 测试集：`{summary['testset']}`",
        f"> 生成时间：{summary['generated_at']}",
        "",
        "## 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 用例数 | {summary['cases']} |",
        f"| 命中数 | {summary['hits']} |",
        f"| 命中率 | {summary['hit_rate']:.1%} |",
        f"| 无候选用例 | {summary['no_candidate_cases']} |",
        "",
        "## 明细",
        "",
        "| 用例 | 结果 | 候选数 | 最佳文件 | 缺失关键词 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for result in results:
        best = result.get("best") or {}
        missing = "、".join(best.get("missing_keywords") or result.get("must_include_keywords") or [])
        source = Path(best.get("source_file") or "-").name
        lines.append(
            f"| `{result['id']}` | {'PASS' if result['hit'] else 'FAIL'} | "
            f"{result['candidate_count']} | `{source}` | {missing or '-'} |"
        )
    lines.extend([
        "",
        "## 结论",
        "",
        "- PASS 表示解析产物中存在满足该用例全部关键词的文件。",
        "- FAIL 需要先检查解析产物是否丢内容，再决定是否改用 MinerU/人工复核。",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--testset", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--save", type=Path, default=None)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    testset_path = args.testset.resolve()
    manifest = _load_json(manifest_path)
    cases = _load_cases(testset_path)
    records = manifest.get("records") or []
    results = [_evaluate_case(case, records) for case in cases]

    hits = sum(1 for result in results if result["hit"])
    no_candidate = sum(1 for result in results if result["candidate_count"] == 0)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "manifest": _rel(manifest_path),
        "testset": _rel(testset_path),
        "cases": len(results),
        "hits": hits,
        "hit_rate": hits / len(results) if results else 0,
        "no_candidate_cases": no_candidate,
    }
    payload = {"summary": summary, "results": results}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    failures = [result for result in results if not result["hit"]]
    if failures:
        print("\n未通过用例：")
        for result in failures:
            print(f"  {result['id']} candidates={result['candidate_count']} best={result.get('best')}")

    if args.save:
        save_path = args.save
        if not save_path.is_absolute():
            save_path = PROJECT_ROOT / save_path
    else:
        save_path = manifest_path.parent / "parse_qa_report.json"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = save_path.with_suffix(".md")
    _write_markdown(summary, results, md_path)
    print(f"JSON: {_rel(save_path)}")
    print(f"Report: {_rel(md_path)}")
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())

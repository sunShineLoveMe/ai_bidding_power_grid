#!/usr/bin/env python3
"""Base 测试集召回评测（P0）。

对 `tests/rag/base_testset.jsonl` 的每条用例：
1. 用当前 embedding 后端向量化 question；
2. 调用 metadata 过滤召回 RPC（match_knowledge_chunks_filtered），取 top-k child；
3. 计算指标：
   - Recall@k：top-k 中是否命中“正确 doc_role 且含关键词”的片段；
   - 来源类别准确率：top-1 的 doc_role 是否等于期望 doc_role；
   - 关键词命中率：top-k 文本是否包含 must_include_keywords（任一即算命中）；
   - 串扰：top-k 是否混入非期望 doc_role（统计比例）。

支持 --no-filter 关闭 metadata 过滤做 A/B 对比（验证过滤的价值）。

用法：
    python scripts/rag/eval_recall.py
    python scripts/rag/eval_recall.py --no-filter        # 关闭 metadata 过滤对比
    python scripts/rag/eval_recall.py --k 5 --save docs/rag/_run.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.supabase_client import get_supabase_client  # noqa: E402
from backend.rag.vector_store import init_ali_client, get_embeddings  # noqa: E402

DEFAULT_TESTSET = PROJECT_ROOT / "tests" / "rag" / "base_testset.jsonl"


def load_cases(testset: Path) -> list[dict]:
    cases = []
    for line in testset.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def _role_of(row: dict) -> str | None:
    return (row.get("metadata") or {}).get("doc_role")


def _parent_rows_for(client, rows: list[dict]) -> list[dict]:
    parents: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for row in rows:
        metadata = row.get("metadata") or {}
        document_id = row.get("document_id")
        parent_index = metadata.get("parent_index")
        if not document_id or not isinstance(parent_index, int):
            continue
        key = (str(document_id), parent_index)
        if key in seen:
            continue
        seen.add(key)
        resp = client.rpc(
            "get_parent_chunk",
            {"p_document_id": document_id, "p_parent_index": parent_index},
        ).execute()
        for parent in resp.data or []:
            parent_meta = parent.get("metadata") or {}
            parents.append({
                **parent,
                "similarity": row.get("similarity"),
                "metadata": {
                    **parent_meta,
                    "retrieved_by_child": {
                        "id": row.get("id"),
                        "metadata": metadata,
                        "source_section": row.get("source_section"),
                    },
                },
            })
    return parents


def recall_for_case(client, ali, case: dict, k: int, use_filter: bool) -> dict:
    q_emb = get_embeddings(ali, [case["question"]])[0]
    filter_md = case.get("metadata_filter", {}) if use_filter else {}
    resp = client.rpc(
        "match_knowledge_chunks_filtered",
        {
            "query_embedding": q_emb,
            "match_threshold": 0.2,
            "match_count": k,
            "filter_metadata": filter_md,
        },
    ).execute()
    rows = resp.data or []
    evaluated_rows = _parent_rows_for(client, rows) if case.get("return_parent") else rows

    expected_role = case.get("expected_doc_role")
    keywords = case.get("must_include_keywords", [])
    forbidden_keywords = case.get("must_not_include_keywords", [])

    def has_kw(r):
        text = r.get("content") or ""
        return any(kw in text for kw in keywords) if keywords else True

    def has_forbidden_kw(r):
        text = r.get("content") or ""
        return any(kw in text for kw in forbidden_keywords) if forbidden_keywords else False

    # Recall@k：存在一条 doc_role 正确且含关键词的片段
    forbidden_hit = any(has_forbidden_kw(r) for r in evaluated_rows)
    hit = any((_role_of(r) == expected_role) and has_kw(r) for r in evaluated_rows) and not forbidden_hit
    # 来源类别准确率：top-1 role 正确
    top1_role_ok = bool(evaluated_rows) and _role_of(evaluated_rows[0]) == expected_role
    # 关键词命中率：top-k 任一含关键词
    kw_hit = any(has_kw(r) for r in evaluated_rows) if keywords else None
    # 串扰：非期望 role 的比例
    off = sum(1 for r in evaluated_rows if _role_of(r) != expected_role)
    cross = (off / len(evaluated_rows)) if evaluated_rows else 0.0

    return {
        "id": case["id"],
        "scenario": case.get("scenario"),
        "metric": case.get("metric") or case.get("scenario"),
        "returned": len(rows),
        "evaluated_returned": len(evaluated_rows),
        "return_parent": bool(case.get("return_parent")),
        "recall_hit": hit,
        "top1_role_ok": top1_role_ok,
        "kw_hit": kw_hit,
        "forbidden_hit": forbidden_hit,
        "cross_role_ratio": round(cross, 3),
        "top1_role": _role_of(evaluated_rows[0]) if evaluated_rows else None,
        "top1_preview": (evaluated_rows[0].get("content") or "")[:60] if evaluated_rows else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--no-filter", action="store_true", help="关闭 metadata 过滤做对比")
    parser.add_argument("--save", type=str, default="", help="保存 JSON 结果到指定路径")
    parser.add_argument("--testset", type=str, default=str(DEFAULT_TESTSET), help="JSONL 测试集路径")
    args = parser.parse_args()

    testset_path = Path(args.testset)
    if not testset_path.is_absolute():
        testset_path = PROJECT_ROOT / testset_path
    cases = load_cases(testset_path)
    client = get_supabase_client()
    ali = init_ali_client()
    use_filter = not args.no_filter

    results = [recall_for_case(client, ali, c, args.k, use_filter) for c in cases]

    n = len(results)
    recall = sum(1 for r in results if r["recall_hit"]) / n
    role_acc = sum(1 for r in results if r["top1_role_ok"]) / n
    kw_cases = [r for r in results if r["kw_hit"] is not None]
    kw_rate = (sum(1 for r in kw_cases if r["kw_hit"]) / len(kw_cases)) if kw_cases else None
    avg_cross = sum(r["cross_role_ratio"] for r in results) / n
    forbidden_cases = [r for r in results if "forbidden_hit" in r]
    forbidden_rate = sum(1 for r in forbidden_cases if r["forbidden_hit"]) / len(forbidden_cases) if forbidden_cases else 0.0

    print(f"\n=== Base 召回评测  (k={args.k}, filter={'ON' if use_filter else 'OFF'}, cases={n}) ===")
    print(f"Recall@{args.k}          : {recall:.1%}")
    print(f"来源类别准确率(top1)    : {role_acc:.1%}")
    if kw_rate is not None:
        print(f"关键词命中率            : {kw_rate:.1%}")
    print(f"跨 doc_role 串扰均值    : {avg_cross:.1%}")
    if any(c.get("must_not_include_keywords") for c in cases):
        print(f"禁用关键词命中率        : {forbidden_rate:.1%}")

    # 按场景拆分
    print("\n按场景：")
    for sc in sorted({r["scenario"] for r in results}):
        sub = [r for r in results if r["scenario"] == sc]
        sr = sum(1 for r in sub if r["recall_hit"]) / len(sub)
        print(f"  {sc:11s} cases={len(sub):2d}  Recall@{args.k}={sr:.0%}")

    print("\n按指标：")
    for metric in sorted({r["metric"] for r in results}):
        sub = [r for r in results if r["metric"] == metric]
        sr = sum(1 for r in sub if r["recall_hit"]) / len(sub)
        print(f"  {metric:24s} cases={len(sub):2d}  Recall@{args.k}={sr:.0%}")

    # 失败用例
    fails = [r for r in results if not r["recall_hit"]]
    if fails:
        print("\n未命中用例：")
        for r in fails:
            print(f"  {r['id']} [{r['scenario']}] top1_role={r['top1_role']} preview={r['top1_preview']!r}")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "k": args.k,
        "filter": use_filter,
        "testset": str(testset_path.relative_to(PROJECT_ROOT)),
        "cases": n,
        f"recall_at_{args.k}": round(recall, 4),
        "role_accuracy_top1": round(role_acc, 4),
        "keyword_hit_rate": round(kw_rate, 4) if kw_rate is not None else None,
        "avg_cross_role_ratio": round(avg_cross, 4),
        "forbidden_hit_rate": round(forbidden_rate, 4),
        "results": results,
    }
    if args.save:
        out = PROJECT_ROOT / args.save
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已保存：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

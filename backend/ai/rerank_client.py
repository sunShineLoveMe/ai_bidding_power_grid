import logging
import os
import time
from typing import Any

import requests

from backend.core.config import get_setting
from backend.db.supabase_repo import record_ai_usage_log


RERANK_TEXT_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
RERANK_COMPAT_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"


def _build_rerank_request(model: str, query: str, documents: list[str], top_n: int) -> tuple[str, dict[str, Any]]:
    if model == "qwen3-rerank":
        return RERANK_COMPAT_ENDPOINT, {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": min(top_n, len(documents)),
            "return_documents": False,
        }
    return RERANK_TEXT_ENDPOINT, {
        "model": model,
        "input": {
            "query": query,
            "documents": documents,
        },
        "parameters": {
            "top_n": min(top_n, len(documents)),
            "return_documents": False,
        },
    }


def _payload_top_n(payload: dict[str, Any]) -> int:
    if "top_n" in payload:
        return int(payload["top_n"])
    return int((payload.get("parameters") or {}).get("top_n") or 0)


def rerank_documents(
    query: str,
    rows: list[dict[str, Any]],
    *,
    text_key: str,
    top_n: int | None = None,
    usage_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rerank retrieved rows with Alibaba Cloud Model Studio / DashScope.

    The function is deliberately fail-open: if the rerank service is not
    configured or returns an unexpected shape, vector recall results are kept.
    """
    if not get_setting("rerank_enabled", True) or not rows:
        return rows

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return rows

    documents = [str(row.get(text_key) or row.get("content") or row.get("searchable_text") or "").strip() for row in rows]
    indexed_documents = [(index, doc) for index, doc in enumerate(documents) if doc]
    if not indexed_documents:
        return rows

    # DashScope Rerank 要求至少 2 条文档，否则返回 400
    if len(indexed_documents) < 2:
        return rows[:top_n]

    top_n = int(top_n or get_setting("rerank_top_n", 6) or 6)
    model = get_setting("rerank_model", "qwen3-rerank")
    documents_for_rerank = [doc for _, doc in indexed_documents]
    endpoint, payload = _build_rerank_request(model, query, documents_for_rerank, top_n)
    context = usage_context or {}
    started_at = time.time()

    try:
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=int(get_setting("request_timeout_seconds", 120) or 120),
        )
        response.raise_for_status()
        data = response.json()
        record_ai_usage_log(
            provider="dashscope",
            region="cn-beijing",
            api_protocol="dashscope",
            endpoint=endpoint,
            model=model,
            operation_type="rerank",
            stage=context.get("stage") or "rerank",
            project_id=context.get("project_id"),
            file_id=context.get("file_id"),
            section_id=context.get("section_id"),
            batch_id=context.get("batch_id"),
            request_id=data.get("request_id"),
            status_code=response.status_code,
            latency_ms=int((time.time() - started_at) * 1000),
            raw_usage=data.get("usage") or {},
            input_text=f"{query}\n" + "\n".join(documents_for_rerank),
            document_count=len(documents_for_rerank),
            character_count=len(query) + sum(len(item) for item in documents_for_rerank),
            metadata={"top_n": _payload_top_n(payload), "return_documents": False, **(context.get("metadata") or {})},
        )
        results = data.get("output", {}).get("results") or data.get("results") or []
        reranked: list[dict[str, Any]] = []
        for result in results:
            local_index = result.get("index")
            if local_index is None:
                continue
            original_index = indexed_documents[int(local_index)][0]
            row = dict(rows[original_index])
            row["rerank_score"] = result.get("relevance_score") or result.get("score")
            reranked.append(row)
        return reranked or rows[:top_n]
    except Exception:
        logging.exception("DashScope rerank failed; fallback to vector recall")
        record_ai_usage_log(
            provider="dashscope",
            region="cn-beijing",
            api_protocol="dashscope",
            endpoint=endpoint,
            model=model,
            operation_type="rerank",
            stage=context.get("stage") or "rerank",
            project_id=context.get("project_id"),
            file_id=context.get("file_id"),
            section_id=context.get("section_id"),
            batch_id=context.get("batch_id"),
            latency_ms=int((time.time() - started_at) * 1000),
            input_text=f"{query}\n" + "\n".join(documents_for_rerank),
            document_count=len(documents_for_rerank),
            character_count=len(query) + sum(len(item) for item in documents_for_rerank),
            success=False,
            error_message="DashScope rerank failed; fallback to vector recall",
            metadata={"top_n": _payload_top_n(payload), **(context.get("metadata") or {})},
        )
        return rows

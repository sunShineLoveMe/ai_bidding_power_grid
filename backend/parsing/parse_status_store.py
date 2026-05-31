"""招标文件解析状态存储（P1-1 第二批）。

提供 `write_parse_status` / `read_parse_status` 两个函数，语义与原先写本地
`parsed_outputs/{parse_id}/mineru_status.json` 完全一致（浅合并 + 自动 updated_at），
但支持两种后端：

- `file`：原本的本地 JSON 文件实现。保留用于本地单机调试与现有文件型测试。
- `db`  ：写 PostgreSQL 表 `bid_parse_tasks`，保证 web 进程与 Celery worker 跨进程可见。

通过环境变量 `PARSE_STATUS_BACKEND` 选择，默认 `db`。这样：
- 迁移到 Celery 后，状态默认进 DB，解决跨进程不可见问题；
- 现有依赖本地文件的测试可显式 `PARSE_STATUS_BACKEND=file` 保持原行为。

设计要点：
- DB 后端用 JSONB `||` 原子浅合并 + upsert，等价于原 read-modify-write，但无并发覆盖问题。
- key 列为 text：拆分大 PDF 时分片任务键形如 "{uuid}_part001"，不是合法 uuid。
- 不改变调用方签名，避免在 ~20 个调用点散弹式改动。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PARSED_OUTPUT_ROOT = Path("parsed_outputs")


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _backend() -> str:
    return (os.getenv("PARSE_STATUS_BACKEND") or "db").strip().lower()


# ---------------------------------------------------------------------------
# 文件后端（原实现，保持不变）
# ---------------------------------------------------------------------------

def _status_file(parse_id: str) -> Path:
    return PARSED_OUTPUT_ROOT / parse_id / "mineru_status.json"


def _file_write(parse_id: str, payload: dict[str, Any]) -> None:
    status_path = _status_file(parse_id)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if status_path.exists():
        try:
            existing = json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    existing.update(payload)
    existing["updated_at"] = _now_iso()
    status_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def _file_read(parse_id: str) -> dict[str, Any] | None:
    status_path = _status_file(parse_id)
    if not status_path.exists():
        return None
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# DB 后端（bid_parse_tasks）
# ---------------------------------------------------------------------------

def _db_write(parse_id: str, payload: dict[str, Any]) -> None:
    import psycopg
    from psycopg.types.json import Jsonb

    merged = dict(payload)
    merged["updated_at"] = _now_iso()
    url = os.environ["DATABASE_URL"]
    # JSONB `||` 浅合并：等价于原文件实现的 existing.update(payload)，但是原子 upsert。
    with psycopg.connect(url) as conn:
        conn.execute(
            """
            insert into public.bid_parse_tasks (parse_id, status_payload)
            values (%s, %s)
            on conflict (parse_id)
            do update set status_payload = public.bid_parse_tasks.status_payload || excluded.status_payload
            """,
            (parse_id, Jsonb(merged)),
        )


def _db_read(parse_id: str) -> dict[str, Any] | None:
    import psycopg
    from psycopg.rows import dict_row

    url = os.environ["DATABASE_URL"]
    with psycopg.connect(url, row_factory=dict_row) as conn:
        row = conn.execute(
            "select status_payload from public.bid_parse_tasks where parse_id = %s",
            (parse_id,),
        ).fetchone()
    if not row:
        return None
    payload = row["status_payload"]
    return payload if isinstance(payload, dict) else None


def find_parse_status_by_supabase_file(supabase_file_id: str) -> dict[str, Any] | None:
    """按 supabase_file_id 找最近一次解析状态（DB 后端，供历史列表/重试使用）。

    返回值附带 `_parse_id`，与文件后端 glob 实现保持一致的字段约定。
    """
    if not supabase_file_id:
        return None
    if _backend() != "db":
        return _file_find_by_supabase_file(supabase_file_id)
    import psycopg
    from psycopg.rows import dict_row

    url = os.environ["DATABASE_URL"]
    with psycopg.connect(url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            select parse_id, status_payload
            from public.bid_parse_tasks
            where status_payload->>'supabase_file_id' = %s
            order by updated_at desc
            limit 1
            """,
            (supabase_file_id,),
        ).fetchone()
    if not row:
        return None
    payload = row["status_payload"] if isinstance(row["status_payload"], dict) else {}
    payload = dict(payload)
    payload["_parse_id"] = row["parse_id"]
    return payload


def _file_find_by_supabase_file(supabase_file_id: str) -> dict[str, Any] | None:
    if not PARSED_OUTPUT_ROOT.exists():
        return None
    latest_status = None
    latest_mtime = 0.0
    for status_path in PARSED_OUTPUT_ROOT.glob("*/mineru_status.json"):
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("supabase_file_id") != supabase_file_id:
            continue
        mtime = status_path.stat().st_mtime
        if mtime >= latest_mtime:
            latest_mtime = mtime
            payload["_parse_id"] = status_path.parent.name
            latest_status = payload
    return latest_status


# ---------------------------------------------------------------------------
# 对外统一入口（签名与原 document_parser 中的函数一致）
# ---------------------------------------------------------------------------

def write_parse_status(parse_id: str, payload: dict[str, Any]) -> None:
    if _backend() == "db":
        try:
            _db_write(parse_id, payload)
            return
        except Exception:
            # DB 不可用时退回文件，避免解析链路整体中断；记录日志便于排查。
            logger.exception("写解析状态到 DB 失败，回退本地文件: parse_id=%s", parse_id)
    _file_write(parse_id, payload)


def read_parse_status(parse_id: str) -> dict[str, Any] | None:
    if _backend() == "db":
        try:
            return _db_read(parse_id)
        except Exception:
            logger.exception("读解析状态(DB)失败，回退本地文件: parse_id=%s", parse_id)
    return _file_read(parse_id)

"""Scheduling policy for batch bid section generation."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any


POLICY_NAME = "adaptive_v1"
ACTIVE_STATUSES = {"leased", "running", "generating", "saving"}
TERMINAL_STATUSES = {"done", "failed", "stopped", "cancelled", "expired", "partial_generated"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _is_slow_or_timeout(item: dict[str, Any]) -> bool:
    metadata = _metadata(item)
    timeout_code = str(metadata.get("timeout_code") or "")
    status = str(item.get("status") or "")
    return (
        bool(metadata.get("slow_stream"))
        or timeout_code in {"MODEL_STREAM_SLOW_TIMEOUT", "MODEL_STREAM_WALL_TIMEOUT", "MODEL_STREAM_IDLE_TIMEOUT"}
        or (status == "partial_generated" and timeout_code.startswith("MODEL_STREAM_"))
    )


def _is_normal_done(item: dict[str, Any]) -> bool:
    if str(item.get("status") or "") != "done":
        return False
    metadata = _metadata(item)
    if metadata.get("slow_stream"):
        return False
    if str(metadata.get("timeout_code") or "").startswith("MODEL_STREAM_"):
        return False
    return True


def _sort_time_key(item: dict[str, Any]) -> tuple[str, int]:
    return (
        str(
            item.get("finished_at")
            or item.get("final_saved_at")
            or item.get("draft_saved_at")
            or item.get("last_token_at")
            or item.get("started_at")
            or ""
        ),
        _safe_int(item.get("order_index")),
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _seconds_since(value: Any) -> float | None:
    parsed = _parse_datetime(value)
    if not parsed:
        return None
    return (datetime.now(timezone.utc) - parsed).total_seconds()


def _task_policy_config(task: dict[str, Any], max_concurrency: int) -> dict[str, Any]:
    task_metadata = _metadata(task)
    raw_policy = task_metadata.get("scheduler_policy")
    enabled = _env_bool("BID_SECTION_ADAPTIVE_CONCURRENCY_ENABLED", True)
    if str(raw_policy or "").lower() in {"fixed", "disabled", "off"}:
        enabled = False
    if task_metadata.get("adaptive_concurrency_enabled") is False:
        enabled = False
    initial = _safe_int(
        task_metadata.get("initial_concurrency"),
        _env_int("BID_SECTION_ADAPTIVE_INITIAL_CONCURRENCY", 2),
    )
    window = _safe_int(
        task_metadata.get("adaptive_window_size"),
        _env_int("BID_SECTION_ADAPTIVE_WINDOW_SIZE", 5),
    )
    slow_threshold = _safe_int(
        task_metadata.get("adaptive_slow_threshold"),
        _env_int("BID_SECTION_ADAPTIVE_SLOW_THRESHOLD", 2),
    )
    success_threshold = _safe_int(
        task_metadata.get("adaptive_success_threshold"),
        _env_int("BID_SECTION_ADAPTIVE_SUCCESS_THRESHOLD", 5),
    )
    increase_hold_seconds = _safe_int(
        task_metadata.get("adaptive_increase_hold_seconds"),
        _env_int("BID_SECTION_ADAPTIVE_INCREASE_HOLD_SECONDS", 60),
    )
    return {
        "enabled": enabled,
        "initial_concurrency": max(1, min(initial, max_concurrency)),
        "window_size": max(2, min(window, 20)),
        "slow_threshold": max(1, slow_threshold),
        "success_threshold": max(1, min(success_threshold, max(2, min(window, 20)))),
        "increase_hold_seconds": max(0, increase_hold_seconds),
    }


def resolve_section_generation_concurrency(task: dict[str, Any], *, max_concurrency: int) -> dict[str, Any]:
    """Return the adaptive scheduling decision for one generation task.

    The returned dict is intentionally JSON-serializable so it can be merged
    into bid_generation_tasks.metadata and shown by the frontend without any
    extra schema changes.
    """
    max_concurrency = max(1, int(max_concurrency or 1))
    items = list(task.get("items") or [])
    task_metadata = _metadata(task)
    config = _task_policy_config(task, max_concurrency)
    now_iso = datetime.now(timezone.utc).isoformat()

    active_items = [item for item in items if str(item.get("status") or "") in ACTIVE_STATUSES]
    active_slow = [item for item in active_items if _is_slow_or_timeout(item)]
    terminal_items = [item for item in items if str(item.get("status") or "") in TERMINAL_STATUSES]
    recent_items = sorted(terminal_items, key=_sort_time_key, reverse=True)[: config["window_size"]]
    recent_slow = [item for item in recent_items if _is_slow_or_timeout(item)]
    recent_normal = [item for item in recent_items if _is_normal_done(item)]
    total_slow = sum(1 for item in items if _is_slow_or_timeout(item))
    timeout_count = sum(1 for item in items if str(_metadata(item).get("timeout_code") or "").startswith("MODEL_STREAM_"))
    previous = _safe_int(task_metadata.get("current_concurrency"), config["initial_concurrency"])

    if not config["enabled"]:
        current = max_concurrency
        action = "fixed_concurrency"
        message = f"已按固定并发 {current} 路调度"
    elif active_slow:
        current = 1
        action = "reduce_concurrency"
        message = "检测到运行中章节输出变慢，已暂停新增并发并降为单路补位"
    elif len(recent_slow) >= config["slow_threshold"]:
        current = 1
        action = "reduce_concurrency"
        message = "最近章节多次慢流或超时，已自动降为单路续写"
    elif len(recent_normal) >= config["success_threshold"]:
        current = max_concurrency
        action = "increase_concurrency" if previous < max_concurrency else "keep_concurrency"
        message = f"最近章节输出稳定，已恢复到 {current} 路并发" if previous < max_concurrency else f"最近章节输出稳定，保持 {current} 路并发"
    else:
        current = min(config["initial_concurrency"], max_concurrency)
        action = "initial_concurrency" if not recent_items else "keep_concurrency"
        message = f"采用 {current} 路自适应初始并发，持续观察模型吞吐"

    current = max(1, min(int(current), max_concurrency))

    last_change_at = task_metadata.get("last_policy_change_at")
    if (
        config["enabled"]
        and current > previous
        and config["increase_hold_seconds"] > 0
        and (elapsed := _seconds_since(last_change_at)) is not None
        and elapsed < config["increase_hold_seconds"]
    ):
        current = max(1, min(previous, max_concurrency))
        action = "hold_concurrency"
        message = f"模型刚发生调度变化，暂时保持 {current} 路并发避免抖动"

    changed = current != previous or action in {"reduce_concurrency", "increase_concurrency", "fixed_concurrency"}
    metadata_patch = {
        "scheduler_policy": POLICY_NAME if config["enabled"] else "fixed",
        "current_concurrency": current,
        "max_concurrency": max_concurrency,
        "initial_concurrency": config["initial_concurrency"],
        "adaptive_window_size": config["window_size"],
        "slow_stream_count": total_slow,
        "timeout_count": timeout_count,
        "active_slow_count": len(active_slow),
        "recent_slow_count": len(recent_slow),
        "recent_success_count": len(recent_normal),
        "recent_terminal_count": len(recent_items),
        "last_policy_change": action,
        "last_policy_change_at": now_iso if changed else task_metadata.get("last_policy_change_at"),
        "policy_message": message,
        "policy_evaluated_at": now_iso,
    }
    return {
        "current_concurrency": current,
        "max_concurrency": max_concurrency,
        "slots_policy": action,
        "policy_message": message,
        "metadata": metadata_patch,
    }

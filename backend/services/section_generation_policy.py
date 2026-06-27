"""Scheduling policy for batch bid section generation."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any


POLICY_NAME = "adaptive_v1"
PARTIAL_RESUME_POLICY_NAME = "partial_resume_v1"
ACTIVE_STATUSES = {"leased", "running", "generating", "saving"}
TERMINAL_STATUSES = {"done", "failed", "stopped", "cancelled", "expired", "partial_generated"}
MANUAL_ONLY_PROFILES = {"price_sensitive", "attachment_index"}


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


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _text_units(value: Any) -> int:
    text = str(value or "")
    return len("".join(text.split()))


def partial_auto_resume_enabled(task: dict[str, Any]) -> bool:
    metadata = _metadata(task)
    raw = metadata.get("autoResumePartial", metadata.get("auto_resume_partial", True))
    if isinstance(raw, str):
        return raw.strip().lower() not in {"0", "false", "no", "off"}
    return bool(raw)


def max_partial_auto_resume_attempts(task: dict[str, Any]) -> int:
    metadata = _metadata(task)
    raw = metadata.get(
        "maxAutoResumeAttempts",
        metadata.get("max_auto_resume_attempts", os.getenv("BID_SECTION_MAX_AUTO_RESUME_ATTEMPTS", "2")),
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 2
    return max(1, min(value, 6))


def _partial_policy_config(task: dict[str, Any]) -> dict[str, Any]:
    metadata = _metadata(task)
    min_ratio = _safe_float(
        metadata.get("partialAutoResumeMinDraftRatio"),
        _env_float("BID_SECTION_AUTO_RESUME_MIN_DRAFT_RATIO", 0.30),
    )
    review_ratio = _safe_float(
        metadata.get("partialReviewDraftRatio"),
        _env_float("BID_SECTION_PARTIAL_REVIEW_DRAFT_RATIO", 0.70),
    )
    max_slow_attempts = _safe_int(
        metadata.get("partialMaxSlowAttempts"),
        _env_int("BID_SECTION_AUTO_RESUME_MAX_SLOW_ATTEMPTS", 2),
    )
    return {
        "enabled": partial_auto_resume_enabled(task),
        "max_attempts": max_partial_auto_resume_attempts(task),
        "min_draft_ratio": min(max(min_ratio, 0.05), 0.95),
        "review_draft_ratio": min(max(review_ratio, 0.10), 0.98),
        "max_slow_attempts": max(1, min(max_slow_attempts, 6)),
    }


def _target_units(item: dict[str, Any]) -> int:
    metadata = _metadata(item)
    plan = metadata.get("writing_plan") if isinstance(metadata.get("writing_plan"), dict) else {}
    raw = item.get("target_words") or metadata.get("target_words") or plan.get("target_words")
    return max(0, _safe_int(raw, 0))


def _partial_units(item: dict[str, Any]) -> int:
    metadata = _metadata(item)
    candidates = [
        metadata.get("partial_words"),
        metadata.get("draft_words"),
        metadata.get("partial_chars"),
        item.get("chars"),
        _text_units(item.get("draft_content") or item.get("generated_content") or ""),
    ]
    return max(_safe_int(value, 0) for value in candidates)


def _profile_name(item: dict[str, Any]) -> str:
    metadata = _metadata(item)
    profile = metadata.get("prompt_profile")
    if isinstance(profile, dict):
        profile = profile.get("name")
    return str(profile or metadata.get("profile") or "").strip()


def _is_manual_only_partial(item: dict[str, Any]) -> bool:
    profile = _profile_name(item)
    if profile in MANUAL_ONLY_PROFILES:
        return True
    title = str(item.get("title") or "")
    return any(keyword in title for keyword in ("报价", "单价", "保证金", "附件索引", "证明材料索引"))


def resolve_partial_resume_policy(task: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """Decide whether a saved partial draft should auto-resume or wait for review.

    The policy is intentionally metadata-first. We keep the database item status
    as ``partial_generated`` for compatibility, and expose the review/next action
    state through item metadata and frontend copy.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    config = _partial_policy_config(task)
    metadata = _metadata(item)
    attempt = _safe_int(item.get("attempt"), _safe_int(metadata.get("attempt"), 0))
    target_units = _target_units(item)
    partial_units = _partial_units(item)
    draft_ratio = (partial_units / target_units) if target_units > 0 else 0.0
    slow_partial = _is_slow_or_timeout(item)
    profile = _profile_name(item)

    action = "manual_resume"
    reason = "draft_requires_manual_decision"
    message = "草稿已保存，可人工复核后继续续写。"
    next_action = "manual_review_or_single_section_retry"
    auto_resume_allowed = False
    review_required = False

    if not config["enabled"]:
        reason = "auto_resume_disabled"
        message = "自动续写已关闭，草稿已保存，等待人工续写。"
    elif _is_manual_only_partial(item):
        action = "needs_review"
        reason = "manual_only_profile"
        message = "报价、保证金或附件索引类章节不自动长篇续写，请人工复核后处理。"
        review_required = True
    elif target_units and draft_ratio >= config["review_draft_ratio"]:
        action = "needs_review"
        reason = "draft_near_target"
        message = "草稿已接近目标篇幅，系统停止自动续写，请人工复核质量后决定是否继续。"
        review_required = True
    elif slow_partial and attempt >= config["max_slow_attempts"]:
        action = "needs_review"
        reason = "slow_partial_limit_reached"
        message = "同一章节已连续慢流，系统停止自动续写，请人工复核或手动续写。"
        review_required = True
    elif attempt >= config["max_attempts"]:
        action = "needs_review"
        reason = "auto_resume_attempt_limit_reached"
        message = "已达到自动续写上限，草稿已保存，请人工复核或手动续写。"
        review_required = True
    elif target_units and draft_ratio < config["min_draft_ratio"]:
        action = "auto_resume"
        reason = "draft_too_short"
        message = "草稿较短，系统将使用轻量续写 prompt 自动续写一次。"
        next_action = "auto_resume_with_slim_prompt"
        auto_resume_allowed = True
    elif not target_units and attempt == 0:
        action = "auto_resume"
        reason = "missing_target_first_partial"
        message = "草稿已保存，系统将使用轻量续写 prompt 自动续写一次。"
        next_action = "auto_resume_with_slim_prompt"
        auto_resume_allowed = True

    exhausted = action != "auto_resume" and review_required
    metadata_patch = {
        "partial_resume_policy": PARTIAL_RESUME_POLICY_NAME,
        "partial_resume_action": action,
        "partial_resume_reason": reason,
        "partial_auto_resume_allowed": auto_resume_allowed,
        "partial_review_required": review_required,
        "partial_review_reason": reason if review_required else None,
        "partial_policy_evaluated_at": now_iso,
        "partial_draft_units": partial_units,
        "partial_target_units": target_units,
        "partial_draft_ratio": round(draft_ratio, 4) if target_units else None,
        "partial_prompt_profile": profile or None,
        "next_action": next_action,
        "retry_policy": {
            "attempt": attempt,
            "max_attempts": config["max_attempts"],
            "max_slow_attempts": config["max_slow_attempts"],
            "min_draft_ratio": config["min_draft_ratio"],
            "review_draft_ratio": config["review_draft_ratio"],
            "next_profile": "continuation_slim",
            "exhausted": exhausted,
            "reason": reason,
        },
    }
    return {
        "action": action,
        "reason": reason,
        "message": message,
        "next_action": next_action,
        "metadata": metadata_patch,
        "auto_resume_allowed": auto_resume_allowed,
        "review_required": review_required,
        "draft_ratio": draft_ratio,
        "draft_units": partial_units,
        "target_units": target_units,
        "attempt": attempt,
        "requeue_reason": "auto_resume_partial",
    }


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

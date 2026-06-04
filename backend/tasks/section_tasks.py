"""Bid section generation Celery tasks.

Moves section body writing out of the HTTP/SSE request lifecycle. The frontend
creates a bid_generation_tasks row, then polls task state while these workers
generate and save section content in the background.

并发模型（对应"恢复 3 路并行编写"需求）：
- 协调任务 `run_bid_section_generation` 不再逐章串行，而是把每个章节派成独立子任务
  `generate_one_section`，用 Celery `group` 并发执行。
- 真实并行度由 Celery worker 并发度（`CELERY_WORKER_CONCURRENCY`，默认 4）与本文件的
  `SECTION_GEN_CONCURRENCY`（默认 3，对齐历史"3 路 DeepSeek 并行"）共同决定。
- 子任务各自独立：可独立重试、独立失败、独立取消，互不阻塞。
- eager 模式（测试）下 group 同步顺序执行，行为可预测。
"""

from __future__ import annotations

import logging
import os
import socket
import time
from datetime import datetime, timezone
from typing import Any

from celery import group

from backend.core.logging_config import log_context
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

ACTIVE_ITEM_STATUSES = {"leased", "running", "generating", "saving"}
TERMINAL_ITEM_STATUSES = {"done", "failed", "stopped", "cancelled", "expired", "partial_generated"}


class SectionGenerationSuperseded(Exception):
    """Raised when another worker/manual recovery already finished this item."""


def _section_gen_concurrency() -> int:
    """单个批量任务期望的并行编写章节数。默认 3，对齐历史 3 路 DeepSeek 并行。"""
    try:
        value = int(os.getenv("SECTION_GEN_CONCURRENCY", "3"))
    except (TypeError, ValueError):
        value = 3
    return max(1, value)


def _section_lease_seconds() -> int:
    try:
        value = int(os.getenv("BID_SECTION_LEASE_SECONDS", "900"))
    except (TypeError, ValueError):
        value = 900
    return max(30, value)


def _section_heartbeat_interval() -> float:
    try:
        value = float(os.getenv("BID_SECTION_HEARTBEAT_INTERVAL_SECONDS", "10"))
    except (TypeError, ValueError):
        value = 10.0
    return max(2.0, value)


def _section_progress_flush_interval() -> float:
    try:
        value = float(os.getenv("BID_SECTION_PROGRESS_FLUSH_INTERVAL_SECONDS", "1.0"))
    except (TypeError, ValueError):
        value = 1.0
    return max(0.25, value)


def _section_progress_flush_min_chars() -> int:
    try:
        value = int(float(os.getenv("BID_SECTION_PROGRESS_FLUSH_MIN_CHARS", "160")))
    except (TypeError, ValueError):
        value = 160
    return max(40, value)


def _section_chunk_event_limit() -> int:
    try:
        value = int(float(os.getenv("BID_SECTION_CHUNK_EVENT_LIMIT", "200")))
    except (TypeError, ValueError):
        value = 200
    return max(20, value)


def _auto_resume_partial_enabled(task: dict[str, Any]) -> bool:
    metadata = _task_metadata(task)
    raw = metadata.get("autoResumePartial", metadata.get("auto_resume_partial", True))
    if isinstance(raw, str):
        return raw.lower() not in {"0", "false", "no", "off"}
    return bool(raw)


def _max_auto_resume_attempts(task: dict[str, Any]) -> int:
    metadata = _task_metadata(task)
    raw = metadata.get("maxAutoResumeAttempts", metadata.get("max_auto_resume_attempts", os.getenv("BID_SECTION_MAX_AUTO_RESUME_ATTEMPTS", "3")))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 3
    return max(1, min(value, 6))


def _worker_id() -> str:
    return f"celery:{socket.gethostname()}:{os.getpid()}"


def _section_by_id(sections: list[dict], section_id: str) -> dict | None:
    for section in sections:
        if str(section.get("id")) == str(section_id):
            return section
    return None


def _as_order(value) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _section_for_task_item(sections: list[dict], item: dict) -> dict | None:
    section_id = str(item.get("section_id") or "")
    found = _section_by_id(sections, section_id)
    if found:
        return found

    title = str(item.get("title") or "").strip()
    order_index = _as_order(item.get("order_index"))
    if title and order_index:
        for section in sections:
            if str(section.get("title") or "").strip() == title and _as_order(section.get("order_index") or section.get("order")) == order_index:
                return section
    if order_index:
        for section in sections:
            if _as_order(section.get("order_index") or section.get("order")) == order_index:
                return section
    if title:
        for section in sections:
            if str(section.get("title") or "").strip() == title:
                return section
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_metadata(task: dict[str, Any]) -> dict[str, Any]:
    metadata = task.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _dispatch_next_sections(project_id: str, task_id: str) -> dict:
    """Top up a section-generation task to the configured concurrency window."""
    from backend.db.supabase_repo import (
        expire_bid_generation_task_items,
        get_bid_generation_task,
        lease_bid_generation_task_items,
        requeue_bid_generation_task_item,
    )

    task = get_bid_generation_task(project_id, task_id)
    if not task:
        raise RuntimeError("章节生成任务不存在")
    if task.get("status") == "cancelled":
        return {"task_id": task_id, "dispatched": 0, "reason": "cancelled"}

    expired = expire_bid_generation_task_items(project_id, task_id, requeue=True)
    if expired:
        task = get_bid_generation_task(project_id, task_id) or task

    items = list(task.get("items") or [])
    running_count = sum(1 for item in items if item.get("status") in ACTIVE_ITEM_STATUSES)
    queued_count = sum(1 for item in items if item.get("status") == "queued")

    if (
        queued_count == 0
        and running_count == 0
        and _auto_resume_partial_enabled(task)
    ):
        max_attempts = _max_auto_resume_attempts(task)
        resumable = [
            item
            for item in items
            if item.get("status") == "partial_generated"
            and int(item.get("attempt") or 0) < max_attempts
        ]
        if resumable:
            for item in resumable:
                section_id = str(item.get("section_id") or "")
                if not section_id:
                    continue
                requeue_bid_generation_task_item(
                    project_id,
                    task_id,
                    section_id,
                    reason="auto_resume_partial",
                    preserve_draft=True,
                )
            task = get_bid_generation_task(project_id, task_id) or task
            items = list(task.get("items") or [])
            queued_count = sum(1 for item in items if item.get("status") == "queued")

    slots = max(0, _section_gen_concurrency() - running_count)
    if slots <= 0:
        return {"task_id": task_id, "dispatched": 0, "running": running_count}

    leased_items = lease_bid_generation_task_items(
        project_id,
        task_id,
        limit=slots,
        worker_id=_worker_id(),
        lease_seconds=_section_lease_seconds(),
    )
    if not leased_items:
        return {"task_id": task_id, "dispatched": 0, "running": running_count}

    job = group(
        generate_one_section.s(
            project_id,
            task_id,
            str(item.get("section_id")),
            str(item.get("attempt_id") or ""),
            str(item.get("worker_id") or ""),
        )
        for item in leased_items
        if item.get("section_id")
    )
    job.apply_async()
    logger.info(
        "section_generation_dispatched",
        extra={
            "task_id": task_id,
            "dispatched": len(leased_items),
            "running_before": running_count,
            "concurrency": _section_gen_concurrency(),
        },
    )
    return {"task_id": task_id, "dispatched": len(leased_items), "running": running_count + len(leased_items)}


@celery_app.task(name="bid.sections.generate_one", bind=True, max_retries=0)
def generate_one_section(
    self,
    project_id: str,
    task_id: str,
    task_section_id: str,
    attempt_id: str | None = None,
    worker_id: str | None = None,
) -> dict:
    """生成单个章节正文。被协调任务以 group 形式并发派发。

    自身完整处理：重绑定章节、流式进度落库、保存、失败/取消状态。
    与其它章节子任务互不阻塞，真实并行度由 worker 并发度决定。
    """
    from backend.db.supabase_repo import (
        get_bid_generation_task,
        generation_task_item_owner_matches,
        heartbeat_bid_generation_task_item,
        list_bid_sections,
        update_bid_generation_task_item,
    )
    from backend.services.section_generation import SectionGenerationCancelled, SectionGenerationTimeout, generate_and_save_bid_section

    with log_context(project_id=project_id, task_id=task_id):
        task = get_bid_generation_task(project_id, task_id)
        if not task:
            raise RuntimeError("章节生成任务不存在")
        if task.get("status") == "cancelled":
            return {"section_id": task_section_id, "status": "cancelled"}

        with_images = bool(task.get("with_images"))
        task_metadata = _task_metadata(task)
        items = list(task.get("items") or [])
        item = next((it for it in items if str(it.get("section_id")) == str(task_section_id)), None)
        if item is None:
            return {"section_id": task_section_id, "status": "skipped"}
        if item.get("status") in TERMINAL_ITEM_STATUSES:
            return {"section_id": task_section_id, "status": item.get("status")}
        attempt_id = attempt_id or item.get("attempt_id")
        worker_id = worker_id or item.get("worker_id")
        if attempt_id or worker_id:
            if not generation_task_item_owner_matches(
                project_id,
                task_id,
                task_section_id,
                attempt_id=str(attempt_id or ""),
                worker_id=str(worker_id or ""),
            ):
                return {"section_id": task_section_id, "status": "superseded"}

        sections = list_bid_sections(project_id)
        chapter = _section_for_task_item(sections, item)
        if not chapter:
            update_bid_generation_task_item(project_id, task_id, task_section_id, {
                "status": "failed",
                "percent": 100,
                "message": "章节目录已变化，请重置生成状态后重新编写。",
                "error": f"章节不存在或无法重绑定: {task_section_id}",
            })
            return {"section_id": task_section_id, "status": "failed"}

        section_id = str(chapter.get("id"))
        if section_id != task_section_id:
            logger.warning(
                "章节任务 ID 已重绑定: task_id=%s old=%s new=%s title=%s",
                task_id, task_section_id, section_id, chapter.get("title"),
            )
            update_bid_generation_task_item(project_id, task_id, task_section_id, {
                "section_id": section_id,
                "message": "章节目录已同步，继续生成",
            })

        update_bid_generation_task_item(project_id, task_id, section_id, {
            "status": "generating",
            "percent": 2,
            "chars": 0,
            "message": "Celery worker 正在编写章节正文",
            "generated_content": "",
            "chunk_seq": 0,
            "chunk_events": [],
            "attempt_id": attempt_id,
            "worker_id": worker_id,
        })

        chapter_metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
        chapter = {
            **chapter,
            "withImages": with_images,
            "metadata": {
                **chapter_metadata,
                "generation_options": {
                    **task_metadata,
                    "continuationDraft": item.get("draft_content") or item.get("generated_content") or "",
                    "continuationAttempt": item.get("attempt") or 0,
                },
            },
        }
        generated_content = str(item.get("draft_content") or item.get("generated_content") or "").strip()
        if not generated_content:
            generated_content = f"## {chapter.get('title') or '未命名章节'}\n\n"
        pending_chunk = ""
        chunk_seq = 0
        chunk_events: list[dict] = []
        last_flush_at = 0.0
        last_heartbeat_at = 0.0
        first_token_at: str | None = None

        def assert_owner() -> None:
            if not attempt_id or not worker_id:
                return
            if not generation_task_item_owner_matches(
                project_id,
                task_id,
                section_id,
                attempt_id=str(attempt_id),
                worker_id=str(worker_id),
            ):
                raise SectionGenerationSuperseded("章节任务 lease owner 已变化")

        def heartbeat(*, force: bool = False) -> None:
            nonlocal last_heartbeat_at
            if not attempt_id or not worker_id:
                return
            now = time.monotonic()
            if not force and now - last_heartbeat_at < _section_heartbeat_interval():
                return
            row = heartbeat_bid_generation_task_item(
                project_id,
                task_id,
                section_id,
                attempt_id=str(attempt_id),
                worker_id=str(worker_id),
                lease_seconds=_section_lease_seconds(),
            )
            if not row:
                raise SectionGenerationSuperseded("章节任务 lease 已失效")
            last_heartbeat_at = now

        def flush_progress(*, force: bool = False, message: str = "正在编写") -> None:
            nonlocal pending_chunk, last_flush_at
            heartbeat()
            if not force and not pending_chunk:
                return
            now = time.monotonic()
            if (
                not force
                and len(pending_chunk) < _section_progress_flush_min_chars()
                and now - last_flush_at < _section_progress_flush_interval()
            ):
                return
            latest_task = get_bid_generation_task(project_id, task_id)
            if latest_task and latest_task.get("status") == "cancelled":
                raise SectionGenerationCancelled("章节正文生成已取消")
            latest_items = list((latest_task or {}).get("items") or [])
            latest_item = next((it for it in latest_items if str(it.get("section_id")) == str(section_id)), None)
            if latest_item and latest_item.get("status") in TERMINAL_ITEM_STATUSES:
                raise SectionGenerationSuperseded(f"章节任务已终态: {latest_item.get('status')}")
            assert_owner()
            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "saving" if "保存" in message else "generating",
                "percent": min(98, max(3, int((len(generated_content.replace("\n", "")) / max(int(item.get("target_words") or 800), 1)) * 100))),
                "chars": len(generated_content.replace("\n", "")),
                "message": message,
                "generated_content": generated_content,
                "chunk_seq": chunk_seq,
                "last_chunk": pending_chunk,
                "chunk_events": chunk_events,
                "first_token_at": first_token_at,
                "last_token_at": _now_iso(),
                "attempt_id": attempt_id,
                "worker_id": worker_id,
            })
            pending_chunk = ""
            last_flush_at = now

        def on_event(event: dict) -> None:
            nonlocal generated_content, pending_chunk, chunk_seq, first_token_at
            if event.get("type") != "chunk":
                return
            content = str(event.get("content") or "")
            if not content:
                return
            if not first_token_at:
                first_token_at = _now_iso()
            generated_content += content
            pending_chunk += content
            chunk_seq += 1
            chunk_events.append({"seq": chunk_seq, "content": content, "created_at": _now_iso()})
            if len(chunk_events) > _section_chunk_event_limit():
                del chunk_events[: len(chunk_events) - _section_chunk_event_limit()]
            flush_progress()

        try:
            heartbeat(force=True)
            result = generate_and_save_bid_section(project_id, chapter, with_images=with_images, on_event=on_event)
            assert_owner()
            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "saving",
                "percent": 99,
                "message": "正在保存章节正文",
                "generated_content": generated_content,
                "chunk_seq": chunk_seq,
                "chunk_events": chunk_events,
                "attempt_id": attempt_id,
                "worker_id": worker_id,
            })
            flush_progress(force=True, message="正在保存")
            assert_owner()
            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "done",
                "percent": 100,
                "chars": result.get("words") or result.get("chars") or 0,
                "message": "已完成",
                "saved_section_id": result.get("section_id"),
                "generated_content": generated_content,
                "chunk_seq": chunk_seq,
                "chunk_events": chunk_events,
                "first_token_at": first_token_at,
                "last_token_at": _now_iso(),
                "final_saved_at": _now_iso(),
                "attempt_id": attempt_id,
                "worker_id": worker_id,
            })
            _dispatch_next_sections(project_id, task_id)
            return {"section_id": section_id, "status": "done"}
        except SectionGenerationCancelled:
            logger.info("章节正文后台生成已取消", extra={"section_id": section_id})
            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "stopped",
                "percent": 100,
                "message": "已停止",
                "task_status": "cancelled",
            })
            _dispatch_next_sections(project_id, task_id)
            return {"section_id": section_id, "status": "stopped"}
        except SectionGenerationSuperseded:
            logger.info("章节正文后台生成已由其它任务完成，当前 worker 退出", extra={"section_id": section_id})
            _dispatch_next_sections(project_id, task_id)
            return {"section_id": section_id, "status": "superseded"}
        except SectionGenerationTimeout as exc:
            logger.warning("章节正文模型流超时，已保留草稿", extra={"section_id": section_id, "error_code": exc.code})
            if attempt_id and worker_id and not generation_task_item_owner_matches(
                project_id,
                task_id,
                section_id,
                attempt_id=str(attempt_id),
                worker_id=str(worker_id),
            ):
                logger.info("章节生成超时回写被跳过：lease owner 已变化", extra={"section_id": section_id})
                _dispatch_next_sections(project_id, task_id)
                return {"section_id": section_id, "status": "superseded"}
            partial_content = exc.partial_content or generated_content
            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "partial_generated",
                "percent": 100,
                "chars": len(partial_content.replace("\n", "")),
                "message": "模型输出超时，已保存草稿，待续写或人工复核。",
                "error": f"{exc.code}: {str(exc)}",
                "generated_content": partial_content,
                "draft_content": partial_content,
                "chunk_seq": chunk_seq,
                "chunk_events": chunk_events,
                "first_token_at": first_token_at,
                "last_token_at": _now_iso(),
                "draft_saved_at": _now_iso(),
                "attempt_id": attempt_id,
                "worker_id": worker_id,
            })
            _dispatch_next_sections(project_id, task_id)
            return {"section_id": section_id, "status": "partial_generated", "error_code": exc.code}
        except Exception as exc:
            logger.exception("章节正文后台生成失败", extra={"section_id": section_id})
            if attempt_id and worker_id and not generation_task_item_owner_matches(
                project_id,
                task_id,
                section_id,
                attempt_id=str(attempt_id),
                worker_id=str(worker_id),
            ):
                logger.info("章节生成失败回写被跳过：lease owner 已变化", extra={"section_id": section_id})
                _dispatch_next_sections(project_id, task_id)
                return {"section_id": section_id, "status": "superseded"}
            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "failed",
                "percent": 100,
                "message": "章节正文后台生成失败，已保留原正文。",
                "error": str(exc)[:1000],
                "attempt_id": attempt_id,
                "worker_id": worker_id,
            })
            _dispatch_next_sections(project_id, task_id)
            return {"section_id": section_id, "status": "failed"}


@celery_app.task(name="bid.sections.generate_task", bind=True, max_retries=0)
def run_bid_section_generation(self, project_id: str, task_id: str) -> dict:
    """协调任务：把待生成章节派成并发子任务（Celery group）。

    并行度由 worker 并发度与 SECTION_GEN_CONCURRENCY 共同决定，
    恢复历史"多路 DeepSeek 同时编写"的速度。
    """
    from backend.db.supabase_repo import get_bid_generation_task

    with log_context(project_id=project_id, task_id=task_id):
        task = get_bid_generation_task(project_id, task_id)
        if not task:
            raise RuntimeError("章节生成任务不存在")

        items = list(task.get("items") or [])
        queued_count = sum(1 for item in items if item.get("status") == "queued")
        running_count = sum(1 for item in items if item.get("status") in ACTIVE_ITEM_STATUSES)
        pending_ids = [
            str(item.get("section_id"))
            for item in items
            if str(item.get("section_id") or "")
            and item.get("status") == "queued"
        ]
        logger.info(
            "section_generation_task_started",
            extra={
                "task_id": task_id,
                "item_count": len(items),
                "queued": queued_count,
                "running": running_count,
                "concurrency": _section_gen_concurrency(),
            },
        )
        if not pending_ids:
            return {"task_id": task_id, "dispatched": 0}

        return _dispatch_next_sections(project_id, task_id)

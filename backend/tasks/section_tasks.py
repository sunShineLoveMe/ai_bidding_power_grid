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
import time
from datetime import datetime
from typing import Any

from celery import group

from backend.core.logging_config import log_context
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

ACTIVE_ITEM_STATUSES = {"leased", "running", "generating", "saving"}
TERMINAL_ITEM_STATUSES = {"done", "failed", "stopped", "cancelled", "expired"}


class SectionGenerationSuperseded(Exception):
    """Raised when another worker/manual recovery already finished this item."""


def _section_gen_concurrency() -> int:
    """单个批量任务期望的并行编写章节数。默认 3，对齐历史 3 路 DeepSeek 并行。"""
    try:
        value = int(os.getenv("SECTION_GEN_CONCURRENCY", "3"))
    except (TypeError, ValueError):
        value = 3
    return max(1, value)


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
    return datetime.utcnow().isoformat()


def _task_metadata(task: dict[str, Any]) -> dict[str, Any]:
    metadata = task.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _dispatch_next_sections(project_id: str, task_id: str) -> dict:
    """Top up a section-generation task to the configured concurrency window."""
    from backend.db.supabase_repo import get_bid_generation_task, update_bid_generation_task_item

    task = get_bid_generation_task(project_id, task_id)
    if not task:
        raise RuntimeError("章节生成任务不存在")
    if task.get("status") == "cancelled":
        return {"task_id": task_id, "dispatched": 0, "reason": "cancelled"}

    items = list(task.get("items") or [])
    running_count = sum(1 for item in items if item.get("status") in ACTIVE_ITEM_STATUSES)
    slots = max(0, _section_gen_concurrency() - running_count)
    if slots <= 0:
        return {"task_id": task_id, "dispatched": 0, "running": running_count}

    queued_ids = [
        str(item.get("section_id"))
        for item in items
        if str(item.get("section_id") or "") and item.get("status") == "queued"
    ][:slots]
    if not queued_ids:
        return {"task_id": task_id, "dispatched": 0, "running": running_count}

    for section_id in queued_ids:
        update_bid_generation_task_item(project_id, task_id, section_id, {
            "status": "leased",
            "percent": 1,
            "message": "已派发，等待 worker 开始编写",
        })

    job = group(
        generate_one_section.s(project_id, task_id, section_id)
        for section_id in queued_ids
    )
    job.apply_async()
    logger.info(
        "section_generation_dispatched",
        extra={
            "task_id": task_id,
            "dispatched": len(queued_ids),
            "running_before": running_count,
            "concurrency": _section_gen_concurrency(),
        },
    )
    return {"task_id": task_id, "dispatched": len(queued_ids), "running": running_count + len(queued_ids)}


@celery_app.task(name="bid.sections.generate_one", bind=True, max_retries=0)
def generate_one_section(self, project_id: str, task_id: str, task_section_id: str) -> dict:
    """生成单个章节正文。被协调任务以 group 形式并发派发。

    自身完整处理：重绑定章节、流式进度落库、保存、失败/取消状态。
    与其它章节子任务互不阻塞，真实并行度由 worker 并发度决定。
    """
    from backend.db.supabase_repo import (
        get_bid_generation_task,
        list_bid_sections,
        update_bid_generation_task_item,
    )
    from backend.services.section_generation import SectionGenerationCancelled, generate_and_save_bid_section

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
        })

        chapter_metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
        chapter = {
            **chapter,
            "withImages": with_images,
            "metadata": {
                **chapter_metadata,
                "generation_options": task_metadata,
            },
        }
        generated_content = f"## {chapter.get('title') or '未命名章节'}\n\n"
        pending_chunk = ""
        chunk_seq = 0
        chunk_events: list[dict] = []
        last_flush_at = 0.0

        def flush_progress(*, force: bool = False, message: str = "正在编写") -> None:
            nonlocal pending_chunk, last_flush_at
            if not force and not pending_chunk:
                return
            now = time.monotonic()
            # 更低的节流阈值，让前端轮询能看到更接近"打字机"的增量更新。
            if not force and len(pending_chunk) < 40 and now - last_flush_at < 0.15:
                return
            latest_task = get_bid_generation_task(project_id, task_id)
            if latest_task and latest_task.get("status") == "cancelled":
                raise SectionGenerationCancelled("章节正文生成已取消")
            latest_items = list((latest_task or {}).get("items") or [])
            latest_item = next((it for it in latest_items if str(it.get("section_id")) == str(section_id)), None)
            if latest_item and latest_item.get("status") in TERMINAL_ITEM_STATUSES:
                raise SectionGenerationSuperseded(f"章节任务已终态: {latest_item.get('status')}")
            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "saving" if "保存" in message else "generating",
                "percent": min(98, max(3, int((len(generated_content.replace("\n", "")) / max(int(item.get("target_words") or 800), 1)) * 100))),
                "chars": len(generated_content.replace("\n", "")),
                "message": message,
                "generated_content": generated_content,
                "chunk_seq": chunk_seq,
                "last_chunk": pending_chunk,
                "chunk_events": chunk_events,
            })
            pending_chunk = ""
            last_flush_at = now

        def on_event(event: dict) -> None:
            nonlocal generated_content, pending_chunk, chunk_seq
            latest_task = get_bid_generation_task(project_id, task_id)
            if latest_task and latest_task.get("status") == "cancelled":
                raise SectionGenerationCancelled("章节正文生成已取消")
            latest_items = list((latest_task or {}).get("items") or [])
            latest_item = next((it for it in latest_items if str(it.get("section_id")) == str(section_id)), None)
            if latest_item and latest_item.get("status") in TERMINAL_ITEM_STATUSES:
                raise SectionGenerationSuperseded(f"章节任务已终态: {latest_item.get('status')}")
            if event.get("type") != "chunk":
                return
            content = str(event.get("content") or "")
            if not content:
                return
            generated_content += content
            pending_chunk += content
            chunk_seq += 1
            chunk_events.append({"seq": chunk_seq, "content": content, "created_at": _now_iso()})
            flush_progress()

        try:
            result = generate_and_save_bid_section(project_id, chapter, with_images=with_images, on_event=on_event)
            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "saving",
                "percent": 99,
                "message": "正在保存章节正文",
                "generated_content": generated_content,
                "chunk_seq": chunk_seq,
                "chunk_events": chunk_events,
            })
            flush_progress(force=True, message="正在保存")
            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "done",
                "percent": 100,
                "chars": result.get("words") or result.get("chars") or 0,
                "message": "已完成",
                "saved_section_id": result.get("section_id"),
                "generated_content": generated_content,
                "chunk_seq": chunk_seq,
                "chunk_events": chunk_events,
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
        except Exception as exc:
            logger.exception("章节正文后台生成失败", extra={"section_id": section_id})
            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "failed",
                "percent": 100,
                "message": "章节正文后台生成失败，已保留原正文。",
                "error": str(exc)[:1000],
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

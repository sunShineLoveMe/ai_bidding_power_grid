"""Bid section generation Celery tasks.

Moves section body writing out of the HTTP/SSE request lifecycle. The frontend
creates a bid_generation_tasks row, then polls task state while this worker
generates and saves section content in the background.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from backend.core.logging_config import log_context
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


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


@celery_app.task(name="bid.sections.generate_task", bind=True, max_retries=0)
def run_bid_section_generation(self, project_id: str, task_id: str) -> dict:
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

        with_images = bool(task.get("with_images"))
        items = list(task.get("items") or [])
        logger.info("section_generation_task_started", extra={"task_id": task_id, "item_count": len(items)})

        completed = 0
        failed = 0
        for item in items:
            task = get_bid_generation_task(project_id, task_id) or task
            if task.get("status") == "cancelled":
                break
            task_section_id = str(item.get("section_id") or "")
            if not task_section_id:
                continue
            if item.get("status") in {"done", "failed", "stopped"}:
                continue

            sections = list_bid_sections(project_id)
            chapter = _section_for_task_item(sections, item)
            if not chapter:
                update_bid_generation_task_item(project_id, task_id, task_section_id, {
                    "status": "failed",
                    "percent": 100,
                    "message": "章节目录已变化，请重置生成状态后重新编写。",
                    "error": f"章节不存在或无法重绑定: {task_section_id}",
                })
                failed += 1
                continue

            section_id = str(chapter.get("id"))
            if section_id != task_section_id:
                logger.warning(
                    "章节任务 ID 已重绑定: task_id=%s old_section_id=%s new_section_id=%s title=%s",
                    task_id,
                    task_section_id,
                    section_id,
                    chapter.get("title"),
                )
                update_bid_generation_task_item(project_id, task_id, task_section_id, {
                    "section_id": section_id,
                    "message": "章节目录已同步，继续生成",
                })

            update_bid_generation_task_item(project_id, task_id, section_id, {
                "status": "running",
                "percent": 2,
                "chars": 0,
                "message": "Celery worker 正在编写章节正文",
                "generated_content": "",
                "chunk_seq": 0,
                "chunk_events": [],
            })
            try:
                chapter = {
                    **chapter,
                    "withImages": with_images,
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
                    if not force and len(pending_chunk) < 120 and now - last_flush_at < 0.4:
                        return
                    latest_task = get_bid_generation_task(project_id, task_id)
                    if latest_task and latest_task.get("status") == "cancelled":
                        raise SectionGenerationCancelled("章节正文生成已取消")
                    update_bid_generation_task_item(project_id, task_id, section_id, {
                        "status": "running",
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
                    if event.get("type") != "chunk":
                        return
                    content = str(event.get("content") or "")
                    if not content:
                        return
                    generated_content += content
                    pending_chunk += content
                    chunk_seq += 1
                    chunk_events.append({
                        "seq": chunk_seq,
                        "content": content,
                        "created_at": _now_iso(),
                    })
                    flush_progress()

                update_bid_generation_task_item(project_id, task_id, section_id, {
                    "status": "running",
                    "percent": 2,
                    "chars": len(generated_content.replace("\n", "")),
                    "message": "正在编写",
                    "generated_content": generated_content,
                    "chunk_seq": chunk_seq,
                    "chunk_events": chunk_events,
                })
                result = generate_and_save_bid_section(project_id, chapter, with_images=with_images, on_event=on_event)
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
                completed += 1
            except SectionGenerationCancelled:
                logger.info("章节正文后台生成已取消", extra={"section_id": section_id})
                update_bid_generation_task_item(project_id, task_id, section_id, {
                    "status": "stopped",
                    "percent": 100,
                    "message": "已停止",
                    "task_status": "cancelled",
                })
            except Exception as exc:
                logger.exception("章节正文后台生成失败", extra={"section_id": section_id})
                update_bid_generation_task_item(project_id, task_id, section_id, {
                    "status": "failed",
                    "percent": 100,
                    "message": "章节正文后台生成失败，已保留原正文。",
                    "error": str(exc)[:1000],
                })
                failed += 1

        logger.info(
            "section_generation_task_completed",
            extra={"task_id": task_id, "completed": completed, "failed": failed},
        )
        return {"task_id": task_id, "completed": completed, "failed": failed}

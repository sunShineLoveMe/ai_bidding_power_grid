"""Shared bid section generation helpers.

Both the legacy SSE endpoint and the Celery worker use this module so content
assembly, image append, word stats, and failure preservation stay consistent.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any

from backend.ai.section_writer import estimate_bid_content_words, stream_bid_section
from backend.db.supabase_repo import (
    list_knowledge_assets,
    update_bid_section_content,
)
from backend.api.routes import (
    _asset_allowed_for_bid,
    _asset_image_ref,
    _build_section_image_markdown,
)

ProgressCallback = Callable[[dict[str, Any]], None]


class SectionGenerationCancelled(Exception):
    """Raised when a persisted generation task is cancelled by the user."""


def append_section_images(full_content: str, chapter: dict[str, Any], *, with_images: bool) -> str:
    if not with_images:
        return ""
    try:
        image_assets = [
            asset for asset in list_knowledge_assets()
            if _asset_image_ref(asset)
            and _asset_allowed_for_bid(asset)
            and str(asset.get("asset_type") or "").lower() not in {"document", "markdown", "text"}
        ]
        return _build_section_image_markdown(
            {**chapter, "content": full_content},
            image_assets,
            set(),
        )
    except Exception:
        logging.exception("章节图文配图失败，继续保存纯文本章节: %s", chapter.get("id"))
        return ""


def save_generated_section(project_id: str, chapter: dict[str, Any], full_content: str) -> dict[str, Any]:
    actual_words = estimate_bid_content_words(full_content)
    target_words = None
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    writing_plan = metadata.get("writing_plan") if isinstance(metadata.get("writing_plan"), dict) else {}
    try:
        target_words = int(float(writing_plan.get("target_words") or 0)) or None
    except (TypeError, ValueError):
        target_words = None
    return update_bid_section_content(
        project_id,
        chapter["id"],
        full_content,
        "generated",
        chapter,
        metadata_patch={
            "generation_status": "generated",
            "writing_status": "generated",
            "actual_words": actual_words,
            "target_words": target_words,
            "length_completion_ratio": round(actual_words / target_words, 3) if target_words else None,
        },
    )


def mark_section_generation_failed(project_id: str, chapter: dict[str, Any], message: str) -> None:
    if not chapter.get("id"):
        return
    try:
        update_bid_section_content(
            project_id,
            chapter["id"],
            "",
            "failed",
            chapter,
            preserve_existing_content=True,
            metadata_patch={
                "generation_status": "failed",
                "writing_status": "failed",
                "writing_error": message,
            },
        )
    except Exception:
        logging.exception("写入章节失败状态失败: %s", chapter.get("id"))


def generate_and_save_bid_section(
    project_id: str,
    chapter: dict[str, Any],
    *,
    with_images: bool = False,
    on_event: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Generate one bid section with real LLM calls and persist it.

    Returns a small summary used by Celery task status updates.
    """
    full_content = f"## {chapter.get('title') or '未命名章节'}\n\n"
    chunk_count = 0
    saved_section: dict[str, Any] | None = None
    try:
        for event in stream_bid_section(project_id, chapter):
            event_type = event.get("type", "message")
            if event_type == "chunk":
                content = event.get("content", "")
                full_content += content
                if content:
                    chunk_count += 1
            if event_type == "done" and chapter.get("id"):
                image_markdown = append_section_images(full_content, chapter, with_images=with_images)
                if image_markdown:
                    full_content += image_markdown
                    chunk_count += 1
                    if on_event:
                        on_event({"type": "chunk", "content": image_markdown})
                saved_section = save_generated_section(project_id, chapter, full_content)
            if on_event:
                on_event(event)
    except SectionGenerationCancelled:
        raise
    except Exception:
        mark_section_generation_failed(project_id, chapter, "章节正文后台生成失败，已保留原正文。")
        raise

    return {
        "section_id": (saved_section or {}).get("id") or chapter.get("id"),
        "old_section_id": chapter.get("id"),
        "chars": len(full_content.replace("\n", "")),
        "words": estimate_bid_content_words(full_content),
        "chunks": chunk_count,
        "content_length": len(full_content),
    }


def stream_generate_bid_section_events(
    project_id: str,
    chapter: dict[str, Any],
    *,
    with_images: bool = False,
) -> Iterable[dict[str, Any]]:
    """Legacy SSE adapter around the shared generation implementation."""
    buffered: list[dict[str, Any]] = []

    def collect(event: dict[str, Any]) -> None:
        buffered.append(dict(event))

    generate_and_save_bid_section(project_id, chapter, with_images=with_images, on_event=collect)
    yield from buffered

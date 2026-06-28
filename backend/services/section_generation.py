"""Shared bid section generation helpers.

Both the legacy SSE endpoint and the Celery worker use this module so content
assembly, image append, word stats, and failure preservation stay consistent.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any

from backend.ai.qwen_client import LLMStreamTimeoutError
from backend.ai.section_writer import (
    compact_formal_placeholders,
    estimate_bid_content_words,
    rewrite_generated_section_for_formal_quality,
    strip_generated_section_heading_noise,
    stream_bid_section,
)
from backend.db.supabase_repo import (
    list_knowledge_assets,
    update_bid_section_content,
)

ProgressCallback = Callable[[dict[str, Any]], None]


class SectionGenerationCancelled(Exception):
    """Raised when a persisted generation task is cancelled by the user."""


class SectionGenerationTimeout(Exception):
    """Raised when a section stream exceeds wall-clock or idle-token budget."""

    def __init__(self, *, code: str, message: str, partial_content: str, metadata: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.partial_content = partial_content
        self.metadata = metadata if isinstance(metadata, dict) else {}


def append_section_images(full_content: str, chapter: dict[str, Any], *, with_images: bool) -> str:
    if not with_images:
        return ""
    try:
        from backend.api.routes import _asset_allowed_for_bid, _asset_image_ref, _build_section_image_markdown

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


def save_generated_section(
    project_id: str,
    chapter: dict[str, Any],
    full_content: str,
    quality_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    full_content, heading_cleanup = strip_generated_section_heading_noise(full_content, chapter)
    full_content, compaction_report = compact_formal_placeholders(chapter, full_content)
    quality = {**(quality_report or {})}
    if heading_cleanup.get("heading_noise_removed") or heading_cleanup.get("heading_brackets_normalized"):
        quality["heading_cleanup"] = heading_cleanup
    if compaction_report.get("compacted"):
        quality["placeholder_compaction"] = compaction_report
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
            "writing_error": None,
            "actual_words": actual_words,
            "target_words": target_words,
            "length_completion_ratio": round(actual_words / target_words, 3) if target_words else None,
            "formal_quality": quality,
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


def mark_section_generation_partial(
    project_id: str,
    chapter: dict[str, Any],
    *,
    message: str,
    code: str,
    partial_content: str,
) -> None:
    if not chapter.get("id"):
        return
    try:
        update_bid_section_content(
            project_id,
            chapter["id"],
            "",
            "partial_generated",
            chapter,
            preserve_existing_content=True,
            metadata_patch={
                "generation_status": "partial_generated",
                "writing_status": "partial_generated",
                "writing_error": message,
                "writing_error_code": code,
                "draft_words": estimate_bid_content_words(partial_content),
                "draft_chars": len(partial_content.replace("\n", "")),
            },
        )
    except Exception:
        logging.exception("写入章节部分生成状态失败: %s", chapter.get("id"))


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
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    options = metadata.get("generation_options") if isinstance(metadata.get("generation_options"), dict) else {}
    continuation_draft = str(options.get("continuationDraft") or options.get("continuation_draft") or "").strip()
    full_content = continuation_draft or f"## {chapter.get('title') or '未命名章节'}\n\n"
    chunk_count = 0
    saved_section: dict[str, Any] | None = None
    quality_report: dict[str, Any] = {}
    prompt_metadata: dict[str, Any] = {}
    try:
        for event in stream_bid_section(project_id, chapter):
            event_type = event.get("type", "message")
            if event_type == "start":
                prompt_metadata = {
                    key: event.get(key)
                    for key in [
                        "prompt_profile",
                        "prompt_profile_label",
                        "prompt_chars",
                        "max_prompt_chars",
                        "rag_limit",
                        "asset_limit",
                        "fact_pack_mode",
                    ]
                    if event.get(key) is not None
                }
            if event_type == "stream_metric":
                prompt_metadata.update({
                    key: event.get(key)
                    for key in [
                        "first_token_latency_ms",
                        "first_token_slow",
                        "chars_at_60s",
                        "chars_at_90s",
                        "chars_per_minute",
                        "stream_elapsed_ms",
                        "stream_chars",
                        "slow_check_seconds",
                        "min_chars_at_slow_check",
                        "slow_stream",
                        "slow_stream_reason",
                        "timeout_code",
                    ]
                    if event.get(key) is not None
                })
            if event_type == "chunk":
                content = event.get("content", "")
                full_content += content
                if content:
                    chunk_count += 1
            if event_type == "done" and chapter.get("id"):
                full_content, quality_report = rewrite_generated_section_for_formal_quality(project_id, chapter, full_content)
                if quality_report.get("rewritten") and on_event:
                    on_event({"type": "quality_rewrite", "report": quality_report})
                image_markdown = append_section_images(full_content, chapter, with_images=with_images)
                if image_markdown:
                    full_content += image_markdown
                    chunk_count += 1
                    if on_event:
                        on_event({"type": "chunk", "content": image_markdown})
                saved_section = save_generated_section(project_id, chapter, full_content, quality_report)
            if on_event:
                on_event(event)
        if chapter.get("id") and saved_section is None:
            full_content, quality_report = rewrite_generated_section_for_formal_quality(project_id, chapter, full_content)
            saved_section = save_generated_section(project_id, chapter, full_content, quality_report)
    except SectionGenerationCancelled:
        raise
    except LLMStreamTimeoutError as exc:
        code = str(getattr(exc, "code", None) or "MODEL_STREAM_TIMEOUT")
        message = str(exc)
        timeout_metadata = getattr(exc, "metadata", {}) if isinstance(getattr(exc, "metadata", {}), dict) else {}
        timeout_metadata = {
            **prompt_metadata,
            **timeout_metadata,
            "timeout_code": code,
            "timeout_message": message,
        }
        if on_event:
            on_event({
                "type": "timeout",
                "code": code,
                "message": message,
                "partial_content": full_content,
                "chars": len(full_content.replace("\n", "")),
                "words": estimate_bid_content_words(full_content),
                "metadata": timeout_metadata,
            })
        mark_section_generation_partial(
            project_id,
            chapter,
            message=message,
            code=code,
            partial_content=full_content,
        )
        raise SectionGenerationTimeout(code=code, message=message, partial_content=full_content, metadata=timeout_metadata) from exc
    except Exception:
        if saved_section is None:
            mark_section_generation_failed(project_id, chapter, "章节正文后台生成失败，已保留原正文。")
        raise

    return {
        "section_id": (saved_section or {}).get("id") or chapter.get("id"),
        "old_section_id": chapter.get("id"),
        "chars": len(full_content.replace("\n", "")),
        "words": estimate_bid_content_words(full_content),
        "chunks": chunk_count,
        "content_length": len(full_content),
        "generated_content": full_content,
        **prompt_metadata,
    }


def stream_generate_bid_section_events(
    project_id: str,
    chapter: dict[str, Any],
    *,
    with_images: bool = False,
) -> Iterable[dict[str, Any]]:
    """SSE adapter that yields events in real time (true streaming).

    生成在后台线程跑，事件经线程安全队列实时转交给 SSE 生成器，实现"打字机"逐字输出，
    而不是先把所有 chunk 攒完再一次性吐出。
    """
    import queue
    import threading

    event_queue: "queue.Queue[dict[str, Any] | object]" = queue.Queue()
    _DONE = object()
    error_holder: dict[str, BaseException] = {}

    def on_event(event: dict[str, Any]) -> None:
        event_queue.put(dict(event))

    def worker() -> None:
        try:
            generate_and_save_bid_section(project_id, chapter, with_images=with_images, on_event=on_event)
        except BaseException as exc:  # noqa: BLE001 - 转交给主线程统一处理
            error_holder["error"] = exc
        finally:
            event_queue.put(_DONE)

    thread = threading.Thread(target=worker, name="section-stream", daemon=True)
    thread.start()

    while True:
        item = event_queue.get()
        if item is _DONE:
            break
        yield item  # type: ignore[misc]

    thread.join()
    if "error" in error_holder:
        raise error_holder["error"]

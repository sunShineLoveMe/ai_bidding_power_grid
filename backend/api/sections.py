"""
标书章节管理路由模块。

负责：
  - POST   /api/bidding/interpretations/<project_id>/sections/stream                                          流式生成章节正文
  - GET    /api/bidding/interpretations/<project_id>/sections                                                 查询章节列表
  - POST   /api/bidding/interpretations/<project_id>/sections                                                 新增/更新章节
  - POST   /api/bidding/interpretations/<project_id>/sections/reorder                                        批量排序章节
  - POST   /api/bidding/interpretations/<project_id>/sections/reset-generation                               重置章节生成状态
  - GET    /api/bidding/interpretations/<project_id>/section-generation-tasks/latest                         查询最新批量生成任务
  - POST   /api/bidding/interpretations/<project_id>/section-generation-tasks                                创建批量生成任务
  - PATCH  /api/bidding/interpretations/<project_id>/section-generation-tasks/<task_id>/items/<section_id>   更新任务单章状态
  - POST   /api/bidding/interpretations/<project_id>/section-generation-tasks/<task_id>/cancel               取消批量生成任务
  - DELETE /api/bidding/interpretations/<project_id>/sections/<section_id>                                   删除章节

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import json
import logging
import uuid

from flask import Response, jsonify, request, stream_with_context

from backend.api._shared import bp
from backend.ai.section_writer import estimate_bid_content_words, stream_bid_section
from backend.db.supabase_repo import (
    cancel_bid_generation_task,
    create_bid_generation_task,
    delete_bid_section,
    get_latest_bid_generation_task,
    list_bid_sections,
    list_knowledge_assets,
    reorder_bid_sections,
    reset_bid_sections_generation,
    update_bid_generation_task_item,
    update_bid_section_content,
    upsert_bid_section,
)
from backend.api.routes import (
    _asset_allowed_for_bid,
    _asset_image_ref,
    _build_section_image_markdown,
)


@bp.route('/interpretations/<project_id>/sections/stream', methods=['POST'])
def stream_interpretation_bid_section(project_id):
    """以 SSE 方式生成单个标书章节正文。"""
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400

    chapter = request.get_json(silent=True) or {}
    if not chapter.get("title"):
        return jsonify({'error': '缺少章节标题。'}), 400

    def event_stream():
        full_content = f"## {chapter.get('title') or '未命名章节'}\n\n"
        with_images = bool(chapter.get("withImages"))
        try:
            for event in stream_bid_section(project_id, chapter):
                event_type = event.pop("type", "message")
                if event_type == "chunk":
                    full_content += event.get("content", "")
                if event_type == "done" and chapter.get("id"):
                    if with_images:
                        try:
                            image_assets = [
                                asset for asset in list_knowledge_assets()
                                if _asset_image_ref(asset)
                                and _asset_allowed_for_bid(asset)
                                and str(asset.get("asset_type") or "").lower() not in {"document", "markdown", "text"}
                            ]
                            image_markdown = _build_section_image_markdown(
                                {**chapter, "content": full_content},
                                image_assets,
                                set(),
                            )
                            if image_markdown:
                                full_content += image_markdown
                                yield "event: chunk\n"
                                yield f"data: {json.dumps({'content': image_markdown}, ensure_ascii=False)}\n\n"
                        except Exception:
                            logging.exception("章节图文配图失败，继续保存纯文本章节: %s", chapter.get("id"))
                    actual_words = estimate_bid_content_words(full_content)
                    target_words = None
                    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
                    writing_plan = metadata.get("writing_plan") if isinstance(metadata.get("writing_plan"), dict) else {}
                    try:
                        target_words = int(float(writing_plan.get("target_words") or 0)) or None
                    except (TypeError, ValueError):
                        target_words = None
                    saved_section = update_bid_section_content(
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
                    if saved_section.get("id") != chapter.get("id"):
                        yield "event: saved\n"
                        yield f"data: {json.dumps({'id': saved_section.get('id'), 'oldId': chapter.get('id')}, ensure_ascii=False)}\n\n"
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logging.exception("流式生成章节正文失败: %s", project_id)
            if chapter.get("id"):
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
                            "writing_error": "流式生成章节正文失败，已保留原正文。",
                        },
                    )
                except Exception:
                    logging.exception("写入章节失败状态失败: %s", chapter.get("id"))
            yield "event: error\n"
            yield f"data: {json.dumps({'error': '流式生成章节正文失败，已保留原正文，请查看后端日志。'}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


@bp.route('/interpretations/<project_id>/sections', methods=['GET'])
def get_bid_sections(project_id):
    """查询项目标书章节。"""
    try:
        uuid.UUID(project_id)
        return jsonify({"sections": list_bid_sections(project_id)})
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("查询标书章节失败: %s", project_id)
        return jsonify({'error': f'查询标书章节失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/sections', methods=['POST'])
def save_bid_section_api(project_id):
    """新增或更新单个标书章节。"""
    try:
        uuid.UUID(project_id)
        section = request.get_json(force=True)
        saved = upsert_bid_section(project_id, section)
        return jsonify({"section": saved})
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("保存标书章节失败: %s", project_id)
        return jsonify({'error': f'保存标书章节失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/sections/reorder', methods=['POST'])
def reorder_bid_sections_api(project_id):
    """批量保存章节顺序和父子关系。"""
    try:
        uuid.UUID(project_id)
        payload = request.get_json(force=True) or {}
        sections = payload.get("sections") or []
        saved = reorder_bid_sections(project_id, sections)
        return jsonify({"sections": saved})
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("批量排序标书章节失败: %s", project_id)
        return jsonify({'error': f'批量排序标书章节失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/sections/reset-generation', methods=['POST'])
def reset_bid_sections_generation_api(project_id):
    """重置标书章节生成状态，可选清空正文内容。"""
    try:
        uuid.UUID(project_id)
        payload = request.get_json(silent=True) or {}
        clear_content = bool(payload.get("clearContent"))
        sections = reset_bid_sections_generation(project_id, clear_content=clear_content)
        return jsonify({
            "message": "章节生成状态已重置。",
            "clearContent": clear_content,
            "sections": sections,
        })
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("重置标书章节生成状态失败: %s", project_id)
        return jsonify({'error': f'重置标书章节生成状态失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/section-generation-tasks/latest', methods=['GET'])
def get_latest_section_generation_task_api(project_id):
    """查询最近一次批量章节生成任务。"""
    try:
        uuid.UUID(project_id)
        task = get_latest_bid_generation_task(project_id)
        return jsonify({"task": task})
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("查询批量章节生成任务失败: %s", project_id)
        return jsonify({'error': f'查询批量章节生成任务失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/section-generation-tasks', methods=['POST'])
def create_section_generation_task_api(project_id):
    """创建批量章节生成任务记录。"""
    try:
        uuid.UUID(project_id)
        payload = request.get_json(force=True) or {}
        items = payload.get("items") or []
        if not isinstance(items, list) or not items:
            return jsonify({'error': '缺少待生成章节列表。'}), 400
        task = create_bid_generation_task(
            project_id,
            items,
            volume_type=payload.get("volumeType") or "all",
            with_images=bool(payload.get("withImages")),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        return jsonify({"task": task}), 201
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("创建批量章节生成任务失败: %s", project_id)
        return jsonify({'error': f'创建批量章节生成任务失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/section-generation-tasks/<task_id>/items/<section_id>', methods=['PATCH'])
def update_section_generation_task_item_api(project_id, task_id, section_id):
    """更新批量章节生成任务中的单章状态。"""
    try:
        uuid.UUID(project_id)
        uuid.UUID(task_id)
    except ValueError:
        return jsonify({'error': 'project_id 或 task_id 不是合法 UUID。'}), 400

    try:
        payload = request.get_json(force=True) or {}
        task = update_bid_generation_task_item(project_id, task_id, section_id, payload)
        return jsonify({"task": task})
    except Exception as e:
        logging.exception("更新批量章节生成任务失败: %s", project_id)
        return jsonify({'error': f'更新批量章节生成任务失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/section-generation-tasks/<task_id>/cancel', methods=['POST'])
def cancel_section_generation_task_api(project_id, task_id):
    """取消批量章节生成任务。"""
    try:
        uuid.UUID(project_id)
        uuid.UUID(task_id)
        task = cancel_bid_generation_task(project_id, task_id)
        return jsonify({"task": task})
    except ValueError:
        return jsonify({'error': 'project_id 或 task_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("取消批量章节生成任务失败: %s", project_id)
        return jsonify({'error': f'取消批量章节生成任务失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/sections/<section_id>', methods=['DELETE'])
def remove_bid_section(project_id, section_id):
    """删除单个标书章节。"""
    try:
        uuid.UUID(project_id)
        uuid.UUID(section_id)
        delete_bid_section(project_id, section_id)
        return jsonify({"message": "章节已删除。"})
    except ValueError:
        return jsonify({'error': 'project_id 或 section_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("删除标书章节失败: %s", project_id)
        return jsonify({'error': f'删除标书章节失败: {str(e)}'}), 500

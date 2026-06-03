"""
标书章节管理路由模块。

负责：
  - POST   /api/bidding/interpretations/<project_id>/sections/stream                                          流式生成章节正文
  - GET    /api/bidding/interpretations/<project_id>/sections                                                 查询章节列表
  - POST   /api/bidding/interpretations/<project_id>/sections                                                 新增/更新章节
  - POST   /api/bidding/interpretations/<project_id>/sections/reorder                                        批量排序章节
  - POST   /api/bidding/interpretations/<project_id>/sections/reset-generation                               重置章节生成状态
  - GET    /api/bidding/interpretations/<project_id>/section-generation-tasks/latest                         查询最新批量生成任务
  - GET    /api/bidding/interpretations/<project_id>/section-generation-tasks/<task_id>                      查询指定批量生成任务
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
from backend.db.supabase_repo import (
    cancel_bid_generation_task,
    create_bid_generation_task,
    delete_bid_section,
    get_bid_generation_task,
    get_latest_bid_generation_task,
    get_outline_lock,
    list_bid_sections,
    reorder_bid_sections,
    reset_bid_sections_generation,
    set_outline_lock,
    update_bid_generation_task_item,
    upsert_bid_section,
)
from backend.services.section_generation import stream_generate_bid_section_events


def dispatch_section_generation_task(project_id: str, task_id: str) -> None:
    from backend.tasks.section_tasks import run_bid_section_generation

    run_bid_section_generation.delay(project_id, task_id)


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
        with_images = bool(chapter.get("withImages"))
        try:
            for event in stream_generate_bid_section_events(project_id, chapter, with_images=with_images):
                event_type = event.pop("type", "message")
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logging.exception("流式生成章节正文失败: %s", project_id)
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


@bp.route('/interpretations/<project_id>/outline-lock', methods=['GET'])
def get_outline_lock_api(project_id):
    """查询项目大纲锁定状态。锁定后 AI 精修/重生成不会覆盖目录。"""
    try:
        uuid.UUID(project_id)
        return jsonify({"locked": get_outline_lock(project_id)})
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("查询大纲锁定状态失败: %s", project_id)
        return jsonify({'error': f'查询大纲锁定状态失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/outline-lock', methods=['POST'])
def set_outline_lock_api(project_id):
    """设置项目大纲锁定状态。body: {"locked": true|false}

    - locked=true：固定当前目录，禁止 AI 精修/重生成覆盖（用户确认大纲后调用）。
    - locked=false：解锁，允许重新生成或 AI 精修（用户主动想重做大纲时调用）。
    """
    try:
        uuid.UUID(project_id)
        payload = request.get_json(silent=True) or {}
        locked = bool(payload.get("locked", True))
        result = set_outline_lock(project_id, locked)
        return jsonify({"locked": result})
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("设置大纲锁定状态失败: %s", project_id)
        return jsonify({'error': f'设置大纲锁定状态失败: {str(e)}'}), 500


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


@bp.route('/interpretations/<project_id>/section-generation-tasks/<task_id>', methods=['GET'])
def get_section_generation_task_api(project_id, task_id):
    """查询指定批量章节生成任务。"""
    try:
        uuid.UUID(project_id)
        uuid.UUID(task_id)
        task = get_bid_generation_task(project_id, task_id)
        if not task:
            return jsonify({'error': '批量章节生成任务不存在。'}), 404
        return jsonify({"task": task})
    except ValueError:
        return jsonify({'error': 'project_id 或 task_id 不是合法 UUID。'}), 400
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
        # 进入全文编写即锁定大纲：之后任何 AI 精修/重生成都不得覆盖目录。
        try:
            set_outline_lock(project_id, True)
        except Exception:
            logging.exception("锁定项目大纲失败（不阻断生成）: %s", project_id)
        if payload.get("autoStart", True):
            dispatch_section_generation_task(project_id, task["id"])
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

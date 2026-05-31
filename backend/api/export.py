"""
DOCX 导出路由模块。

负责：
  - POST /api/bidding/interpretations/<project_id>/download-docx          创建 DOCX 导出任务
  - GET  /api/bidding/interpretations/<project_id>/export-tasks/<task_id> 查询导出任务状态

DOCX 导出任务已迁移到 Celery（P1-1 第一批）：路由只负责创建任务记录并把执行
投递给 Celery worker，实际导出逻辑在 backend/tasks/export_tasks.py。前端轮询
export-tasks 接口的契约保持不变。
"""

from __future__ import annotations

import logging
import uuid

from flask import jsonify, request

from backend.api._shared import bp
from backend.db.supabase_repo import create_bid_export_task, get_bid_export_task


@bp.route('/interpretations/<project_id>/download-docx', methods=['POST'])
def download_bid_docx(project_id):
    """创建 DOCX 导出任务，并在后台生成下载文件。"""
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400

    try:
        request_payload = request.get_json(silent=True) or {}
        section_id = request_payload.get("sectionId")
        with_images = bool(request_payload.get("withImages"))
        volume_type = request_payload.get("volumeType")
        sections_snapshot = request_payload.get("sectionsSnapshot")
        if not isinstance(sections_snapshot, list):
            sections_snapshot = None
        if volume_type not in {"technical", "business", "qualification", "price", "attachment", "other"}:
            volume_type = None
        if section_id:
            try:
                uuid.UUID(section_id)
            except ValueError:
                section_id = None
        task = create_bid_export_task(
            project_id,
            scope="section" if section_id else ("volume" if volume_type else "full"),
            section_id=section_id,
            volume_type=None if section_id else volume_type,
            with_images=with_images,
            metadata={"requested_from": "bid_editor"},
        )

        # 投递给 Celery worker 执行；进程重启后任务由 broker 重新投递，不再无痕丢失。
        from backend.tasks.export_tasks import run_bid_docx_export

        run_bid_docx_export.delay(
            project_id,
            task["id"],
            section_id,
            with_images,
            volume_type,
            sections_snapshot,
        )

        return jsonify({
            'message': 'DOCX 导出任务已创建。',
            'projectId': project_id,
            'task': task,
            'taskId': task["id"],
            'sectionId': section_id,
            'withImages': with_images,
            'volumeType': volume_type,
        }), 201
    except Exception as e:
        logging.exception("创建 DOCX 导出任务失败: %s", project_id)
        return jsonify({'error': f'创建 DOCX 导出任务失败: {str(e)}'}), 500


def _run_bid_docx_export_task(*args, **kwargs):
    """已迁移到 Celery：backend/tasks/export_tasks.py:run_bid_docx_export。

    保留此占位以兼容历史引用；不应再被调用。
    """
    raise RuntimeError(
        "_run_bid_docx_export_task 已迁移到 Celery 任务 run_bid_docx_export，请勿直接调用。"
    )


@bp.route('/interpretations/<project_id>/export-tasks/<task_id>', methods=['GET'])
def get_bid_export_task_api(project_id, task_id):
    """查询 DOCX 导出任务状态。"""
    try:
        uuid.UUID(project_id)
        uuid.UUID(task_id)
    except ValueError:
        return jsonify({'error': 'project_id 或 task_id 不是合法 UUID。'}), 400
    try:
        task = get_bid_export_task(project_id, task_id)
        if not task:
            return jsonify({'error': 'DOCX 导出任务不存在。'}), 404
        return jsonify({"task": task})
    except Exception as e:
        logging.exception("查询 DOCX 导出任务失败: %s", project_id)
        return jsonify({'error': f'查询 DOCX 导出任务失败: {str(e)}'}), 500

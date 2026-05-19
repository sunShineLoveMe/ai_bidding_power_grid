"""
DOCX 导出路由模块。

负责：
  - POST /api/bidding/interpretations/<project_id>/download-docx          创建 DOCX 导出任务
  - GET  /api/bidding/interpretations/<project_id>/export-tasks/<task_id> 查询导出任务状态

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import current_app, jsonify, request

from backend.api._shared import bp
from backend.db.supabase_repo import create_bid_export_task, get_bid_export_task, update_bid_export_task
from backend.export.md_to_word import convert_md_to_word, refresh_docx_fields_with_soffice
from backend.api.routes import build_project_bid_markdown, _output_url_for_path


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

        app = current_app._get_current_object()
        thread = threading.Thread(
            target=_run_bid_docx_export_task,
            args=(app, project_id, task["id"], section_id, with_images, volume_type, sections_snapshot),
            daemon=True,
        )
        thread.start()

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


def _run_bid_docx_export_task(
    app,
    project_id: str,
    task_id: str,
    section_id: str | None,
    with_images: bool,
    volume_type: str | None,
    sections_snapshot: list[dict] | None = None,
) -> None:
    with app.app_context():
        try:
            update_bid_export_task(project_id, task_id, {
                "status": "running",
                "progress": 10,
                "message": "正在整理标书 Markdown 内容。",
                "started_at": datetime.utcnow().isoformat(),
            })
            markdown_path, project_name, image_selection_report = build_project_bid_markdown(
                project_id,
                section_id,
                with_images=with_images,
                volume_type=None if section_id else volume_type,
                sections_snapshot=sections_snapshot,
            )
            update_bid_export_task(project_id, task_id, {
                "progress": 55,
                "message": "正在转换 Word 文档。",
                "project_name": project_name,
            })
            generated_docx_path, image_conversion_report = convert_md_to_word(markdown_path, return_report=True)
            if not generated_docx_path or not Path(generated_docx_path).exists():
                raise RuntimeError("DOCX 生成失败，未找到输出文件。")
            generated_docx_path = Path(generated_docx_path)
            update_bid_export_task(project_id, task_id, {
                "progress": 75,
                "message": "正在刷新 Word 目录页码和页脚页码。",
            })
            generated_docx_path, field_refresh_report = refresh_docx_fields_with_soffice(generated_docx_path)
            export_metadata = {
                "requested_from": "bid_editor",
                "with_images": bool(with_images),
                "used_editor_snapshot": bool(sections_snapshot),
                "snapshot_section_count": len(sections_snapshot or []),
                "image_selection": image_selection_report,
                "image_conversion": image_conversion_report,
                "field_refresh": field_refresh_report,
            }
            update_bid_export_task(project_id, task_id, {
                "status": "completed",
                "progress": 100,
                "message": "DOCX 已生成，目录页码已刷新。" if field_refresh_report.get("status") == "refreshed" else "DOCX 已生成，目录页码将在 Word 打开时刷新。",
                "project_name": project_name,
                "file_name": generated_docx_path.name,
                "file_path": str(generated_docx_path),
                "download_url": _output_url_for_path(generated_docx_path),
                "metadata": export_metadata,
                "finished_at": datetime.utcnow().isoformat(),
            })
        except Exception as exc:
            logging.exception("后台 DOCX 导出任务失败: project_id=%s task_id=%s", project_id, task_id)
            try:
                update_bid_export_task(project_id, task_id, {
                    "status": "failed",
                    "progress": 100,
                    "message": "DOCX 导出失败，请查看错误信息。",
                    "error_message": str(exc)[:1000],
                    "finished_at": datetime.utcnow().isoformat(),
                })
            except Exception:
                logging.exception("写入 DOCX 导出任务失败状态失败: %s", task_id)


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

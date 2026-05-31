"""DOCX 导出 Celery 任务（P1-1 第一批迁移）。

迁移前：`backend/api/export.py` 的 `_run_bid_docx_export_task` 跑在
`threading.Thread(daemon=True)` 上，进程重启即无痕丢失。
迁移后：任务体搬到本模块的 Celery 任务，状态仍写 PostgreSQL 表
`bid_export_tasks`，前端轮询契约完全不变。

任务通过 `backend.tasks.celery_app.FlaskTask` 基类自动推入 Flask 应用上下文，
因此可以直接使用 current_app 配置（GENERATED_FOLDER、下载 URL 拼接等）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="bid.export.docx",
    bind=True,
    max_retries=0,
)
def run_bid_docx_export(
    self,
    project_id: str,
    task_id: str,
    section_id: str | None,
    with_images: bool,
    volume_type: str | None,
    sections_snapshot: list[dict] | None = None,
) -> dict:
    """执行 DOCX 导出，全程把进度写回 bid_export_tasks。

    返回值仅用于日志/调试；前端通过轮询 export-tasks 接口读取状态，不依赖返回值。
    """
    # 延迟导入，避免在 worker 启动阶段过早加载重型导出依赖。
    from backend.api.routes import build_project_bid_markdown, _output_url_for_path
    from backend.db.supabase_repo import update_bid_export_task
    from backend.export.md_to_word import convert_md_to_word, refresh_docx_fields_with_soffice

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
            "message": field_refresh_report.get("user_message") or ("DOCX 已生成，目录页码已刷新。" if field_refresh_report.get("status") == "refreshed" else "DOCX 已生成，目录页码将在 Word 打开时刷新。"),
            "project_name": project_name,
            "file_name": generated_docx_path.name,
            "file_path": str(generated_docx_path),
            "download_url": _output_url_for_path(generated_docx_path),
            "metadata": export_metadata,
            "finished_at": datetime.utcnow().isoformat(),
        })
        return {"status": "completed", "task_id": task_id}
    except Exception as exc:
        logger.exception("后台 DOCX 导出任务失败: project_id=%s task_id=%s", project_id, task_id)
        try:
            update_bid_export_task(project_id, task_id, {
                "status": "failed",
                "progress": 100,
                "message": "DOCX 导出失败，请查看错误信息。",
                "error_message": str(exc)[:1000],
                "finished_at": datetime.utcnow().isoformat(),
            })
        except Exception:
            logger.exception("写入 DOCX 导出任务失败状态失败: %s", task_id)
        return {"status": "failed", "task_id": task_id, "error": str(exc)[:200]}

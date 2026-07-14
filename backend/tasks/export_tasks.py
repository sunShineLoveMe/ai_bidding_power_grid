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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.tasks.celery_app import celery_app
from backend.core.logging_config import log_context

logger = logging.getLogger(__name__)


BEIJING_TZ = timezone(timedelta(hours=8))


def _now_api_iso() -> str:
    """Return the same +08:00 display contract as Postgres-created timestamps."""
    return datetime.now(BEIJING_TZ).isoformat(timespec="microseconds")


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
    initial_metadata: dict | None = None,
) -> dict:
    """执行 DOCX 导出，全程把进度写回 bid_export_tasks。

    返回值仅用于日志/调试；前端通过轮询 export-tasks 接口读取状态，不依赖返回值。
    """
    # 延迟导入，避免在 worker 启动阶段过早加载重型导出依赖。
    from backend.api.routes import build_project_bid_markdown, _output_url_for_path
    from backend.db.supabase_repo import update_bid_export_task
    from backend.export.md_to_word import convert_md_to_word, refresh_docx_fields_with_soffice
    from backend.services.formal_export_delivery_gate import build_formal_export_delivery_gate
    from backend.services.taichang_fixed_forms import (
        audit_fixed_form_docx,
        audit_full_document_fixed_forms,
        export_fixed_form_manifest_to_docx,
        replace_fixed_form_tables_in_docx,
    )

    with log_context(project_id=project_id, task_id=task_id):
        try:
            return _run_bid_docx_export(
                project_id,
                task_id,
                section_id,
                with_images,
                volume_type,
                sections_snapshot,
                initial_metadata,
                build_project_bid_markdown,
                _output_url_for_path,
                update_bid_export_task,
                convert_md_to_word,
                refresh_docx_fields_with_soffice,
                export_fixed_form_manifest_to_docx,
                audit_fixed_form_docx,
                replace_fixed_form_tables_in_docx,
                audit_full_document_fixed_forms,
                build_formal_export_delivery_gate,
            )
        except Exception as exc:
            logger.exception("后台 DOCX 导出任务失败")
            try:
                update_bid_export_task(project_id, task_id, {
                    "status": "failed",
                    "progress": 100,
                    "message": "DOCX 导出失败，请查看错误信息。",
                    "error_message": str(exc)[:1000],
                    "finished_at": _now_api_iso(),
                })
            except Exception:
                logger.exception("写入 DOCX 导出任务失败状态失败")
            return {"status": "failed", "task_id": task_id, "error": str(exc)[:200]}


def _run_bid_docx_export(
    project_id: str,
    task_id: str,
    section_id: str | None,
    with_images: bool,
    volume_type: str | None,
    sections_snapshot: list[dict] | None,
    initial_metadata: dict | None,
    build_project_bid_markdown,
    _output_url_for_path,
    update_bid_export_task,
    convert_md_to_word,
    refresh_docx_fields_with_soffice,
    export_fixed_form_manifest_to_docx,
    audit_fixed_form_docx,
    replace_fixed_form_tables_in_docx,
    audit_full_document_fixed_forms,
    build_formal_export_delivery_gate,
) -> dict:
    try:
        update_bid_export_task(project_id, task_id, {
            "status": "running",
            "progress": 10,
            "message": "正在整理标书 Markdown 内容。",
            "started_at": _now_api_iso(),
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
        fixed_form_manifest = (image_selection_report or {}).get("fixed_form_manifest")
        fixed_form_manifests = (image_selection_report or {}).get("fixed_form_manifests") or []
        if section_id and isinstance(fixed_form_manifest, dict):
            generated_docx_path, fixed_form_report = export_fixed_form_manifest_to_docx(
                fixed_form_manifest,
                Path(markdown_path).with_suffix(".docx"),
                document_title=project_name,
            )
            image_conversion_report = {
                "template": fixed_form_report.get("template") or {},
                "fixed_form_ooxml": fixed_form_report,
                "inserted": 0,
                "failed": 0,
                "warnings": [],
            }
        else:
            generated_docx_path, image_conversion_report = convert_md_to_word(
                markdown_path,
                return_report=True,
                cover_fields=(image_selection_report or {}).get("cover_fields") or None,
            )
            if fixed_form_manifests:
                generated_docx_path, replacement_report = replace_fixed_form_tables_in_docx(
                    generated_docx_path,
                    fixed_form_manifests,
                )
                image_conversion_report["fixed_form_ooxml"] = replacement_report
        if not generated_docx_path or not Path(generated_docx_path).exists():
            raise RuntimeError("DOCX 生成失败，未找到输出文件。")
        generated_docx_path = Path(generated_docx_path)
        update_bid_export_task(project_id, task_id, {
            "progress": 75,
            "message": "正在刷新 Word 目录页码和页脚页码。",
        })
        generated_docx_path, field_refresh_report = refresh_docx_fields_with_soffice(generated_docx_path)
        if section_id and isinstance(fixed_form_manifest, dict):
            post_refresh_audit = audit_fixed_form_docx(fixed_form_manifest, generated_docx_path)
            image_conversion_report["fixed_form_ooxml"]["post_refresh_audit"] = post_refresh_audit
            if not post_refresh_audit.get("passed"):
                raise RuntimeError("固定表单在 Word 字段刷新后发生结构漂移，已阻止交付。")
        elif fixed_form_manifests:
            post_refresh_audit = audit_full_document_fixed_forms(generated_docx_path, fixed_form_manifests)
            image_conversion_report["fixed_form_ooxml"]["post_refresh_audit"] = post_refresh_audit
            if not post_refresh_audit.get("passed"):
                raise RuntimeError("完整投标文件固定表单在 Word 字段刷新后发生结构漂移，已阻止交付。")
        base_metadata = initial_metadata if isinstance(initial_metadata, dict) else {}
        scope = "section" if section_id else ("volume" if volume_type else "full")
        delivery_gate = build_formal_export_delivery_gate(
            output_path=generated_docx_path,
            scope=scope,
            pre_export_gate=base_metadata.get("formal_export_gate"),
            image_selection=image_selection_report,
            image_conversion=image_conversion_report,
            field_refresh=field_refresh_report,
        )
        pre_gate = base_metadata.get("formal_export_gate") if isinstance(base_metadata.get("formal_export_gate"), dict) else {}
        effective_gate = {
            **pre_gate,
            "pre_export_mode": pre_gate.get("export_mode"),
            "post_export_checked": bool(delivery_gate.get("checked")),
            "artifact_ready": bool(delivery_gate.get("artifact_ready")),
            "can_formal_export": bool(delivery_gate.get("can_formal_deliver")),
            "export_mode": delivery_gate.get("export_mode") or pre_gate.get("export_mode") or "draft",
            "formal_export_label": "允许正式版交付" if delivery_gate.get("can_formal_deliver") else "仅允许草稿版导出",
        }
        export_metadata = {
            **base_metadata,
            "formal_export_gate": effective_gate,
            "formal_delivery_gate": delivery_gate,
            "requested_from": base_metadata.get("requested_from") or "bid_editor",
            "with_images": bool(with_images),
            "used_editor_snapshot": bool(sections_snapshot),
            "snapshot_section_count": len(sections_snapshot or []),
            "image_selection": image_selection_report,
            "image_conversion": image_conversion_report,
            "docx_template": (image_conversion_report or {}).get("template") or {},
            "field_refresh": field_refresh_report,
        }
        display_file_name = (
            (image_selection_report or {}).get("download_file_name")
            or generated_docx_path.name
        )
        update_bid_export_task(project_id, task_id, {
            "status": "completed",
            "progress": 100,
            "message": field_refresh_report.get("user_message") or ("DOCX 已生成，目录页码已刷新。" if field_refresh_report.get("status") == "refreshed" else "DOCX 已生成，目录页码将在 Word 打开时刷新。"),
            "project_name": project_name,
            "file_name": display_file_name,
            "file_path": str(generated_docx_path),
            "download_url": _output_url_for_path(generated_docx_path),
            "metadata": export_metadata,
            "finished_at": _now_api_iso(),
        })
        return {"status": "completed", "task_id": task_id}
    except Exception:
        raise

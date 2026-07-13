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
from typing import Any

from flask import jsonify, request

from backend.api._shared import bp
from backend.db.supabase_repo import create_bid_export_task, get_bid_export_task
from backend.services.formal_bid_check import build_formal_bid_check_report
from backend.services.project_mode_context import build_project_task_metadata


FORMAL_GATE_TOP_BLOCKER_LIMIT = 8


def _formal_gate_item_summary(item: dict[str, Any]) -> dict[str, Any]:
    """保留导出任务需要展示的轻量问题摘要，避免把完整检查报告塞进任务表。"""
    return {
        "id": item.get("id"),
        "category": item.get("category"),
        "severity": item.get("severity"),
        "title": item.get("title"),
        "status": item.get("status"),
        "evidence": item.get("evidence"),
        "suggestion": item.get("suggestion"),
        "target": item.get("target"),
    }


def _build_formal_export_gate(project_id: str, *, scope: str) -> dict[str, Any]:
    """生成导出前正式检查门禁 metadata。

    全文/分册导出会执行正式检查；存在阻断项时不拒绝创建任务，但任务被明确
    标记为 draft，防止草稿 DOCX 被误认为正式投标文件。
    """
    if scope == "section":
        return {
            "checked": False,
            "scope": scope,
            "export_mode": "section",
            "can_formal_export": False,
            "draft_export_allowed": True,
            "reason": "section_export_not_full_formal_gate",
            "formal_export_label": "章节导出不作为正式版全文门禁判断",
            "blocked_count": 0,
            "top_blockers": [],
        }

    try:
        report = build_formal_bid_check_report(project_id)
    except Exception as exc:
        logging.exception("DOCX 导出前正式检查失败，导出任务降级为草稿版: %s", project_id)
        return {
            "checked": False,
            "scope": scope,
            "export_mode": "draft",
            "can_formal_export": False,
            "draft_export_allowed": True,
            "reason": "formal_check_failed",
            "error": str(exc)[:500],
            "formal_export_label": "正式检查失败，仅允许草稿版导出",
            "blocked_count": 1,
            "top_blockers": [
                {
                    "id": "formal_check_failed",
                    "category": "导出门禁",
                    "severity": "blocker",
                    "title": "导出前正式检查未完成",
                    "status": "blocked",
                    "evidence": str(exc)[:500],
                    "suggestion": "请先修复正式检查服务或重试检查，再生成正式版投标文件。",
                }
            ],
        }

    summary = report.get("summary") or {}
    can_formal_export = bool(summary.get("canFormalExport"))
    blockers = [
        item for item in report.get("items") or []
        if item.get("blocksFormalExport")
    ]
    return {
        "checked": True,
        "scope": scope,
        "export_mode": "formal" if can_formal_export else "draft",
        "can_formal_export": can_formal_export,
        "draft_export_allowed": bool(summary.get("draftExportAllowed", True)),
        "formal_export_label": summary.get("formalExportLabel") or ("允许正式版导出" if can_formal_export else "仅允许草稿版导出"),
        "blocked_count": int(summary.get("blocked") or len(blockers) or 0),
        "warning_count": int(summary.get("warnings") or 0),
        "manual_confirm_count": int(summary.get("manualConfirm") or 0),
        "formal_required_gaps": int(summary.get("formalRequiredGaps") or 0),
        "unresolved_placeholder_count": int(summary.get("unresolvedPlaceholderCount") or 0),
        "compliance_percent": summary.get("compliancePercent") or 0,
        "high_risk_missing": int(summary.get("highRiskMissing") or 0),
        "rule_set_version": report.get("ruleSetVersion"),
        "checked_at": report.get("generatedAt"),
        "top_blockers": [
            _formal_gate_item_summary(item)
            for item in blockers[:FORMAL_GATE_TOP_BLOCKER_LIMIT]
        ],
    }


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
        # 泰昌 MVP 交付件默认必须图文并茂；前端未传值时不能降级成无图 DOCX。
        with_images = bool(request_payload.get("withImages", True))
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
        scope = "section" if section_id else ("volume" if volume_type else "full")
        formal_export_gate = _build_formal_export_gate(project_id, scope=scope)
        task_metadata = build_project_task_metadata(project_id, {
            "requested_from": "bid_editor",
            "formal_export_gate": formal_export_gate,
        })
        task = create_bid_export_task(
            project_id,
            scope=scope,
            section_id=section_id,
            volume_type=None if section_id else volume_type,
            with_images=with_images,
            metadata=task_metadata,
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
            task_metadata,
        )

        export_mode = formal_export_gate.get("export_mode")
        return jsonify({
            'message': 'DOCX 草稿版导出任务已创建。' if export_mode == "draft" else 'DOCX 导出任务已创建。',
            'projectId': project_id,
            'task': task,
            'taskId': task["id"],
            'sectionId': section_id,
            'withImages': with_images,
            'volumeType': volume_type,
            'exportMode': export_mode,
            'formalExportGate': formal_export_gate,
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

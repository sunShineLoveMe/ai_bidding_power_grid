"""
招标解读路由模块。

负责：
  - GET  /api/bidding/interpretations/<project_id>            获取招标解读结果
  - POST /api/bidding/interpretations/<project_id>/ai-report  生成 AI 深度解读报告

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import logging
import uuid

from flask import jsonify

from backend.api._shared import bp
from backend.ai.interpreter import generate_ai_interpretation_report
from backend.db.supabase_repo import (
    create_bid_interpretation_task,
    get_bid_interpretation_task,
    get_project_interpretation,
)
from backend.services.project_mode_context import build_project_task_metadata_from_project


@bp.route('/interpretations/<project_id>', methods=['GET'])
def get_interpretation(project_id):
    """按项目获取招标文件结构化解读结果。"""
    try:
        uuid.UUID(project_id)
        return jsonify(get_project_interpretation(project_id))
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("查询招标解读失败: %s", project_id)
        return jsonify({'error': f'查询招标解读失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/ai-report', methods=['POST'])
def generate_interpretation_ai_report(project_id):
    """生成并保存大模型深度招标解读报告。"""
    try:
        uuid.UUID(project_id)
        report = generate_ai_interpretation_report(project_id)
        return jsonify({
            'message': 'AI 深度解读报告已生成。',
            'projectId': project_id,
            'aiReport': report,
        })
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("生成 AI 深度解读报告失败: %s", project_id)
        return jsonify({'error': f'生成 AI 深度解读报告失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/ai-report-tasks', methods=['POST'])
def create_interpretation_ai_report_task(project_id):
    """创建 AI 深度解读后台任务。"""
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400

    try:
        payload = get_project_interpretation(project_id)
        analysis = payload.get("analysis")
        if not analysis:
            return jsonify({'error': '当前项目尚无结构化解读数据，请先完成招标文件解析和落库。'}), 400

        project_meta = analysis.get("project_meta") or {}
        project = payload.get("project")
        existing_report = project_meta.get("ai_report")
        if isinstance(existing_report, dict) and existing_report:
            task = create_bid_interpretation_task(
                project_id,
                status="completed",
                progress=100,
                message="AI 深度解读报告已存在，直接使用缓存结果。",
                metadata=build_project_task_metadata_from_project(
                    project,
                    {"cached": True, "report_keys": sorted(existing_report.keys())},
                ),
            )
            return jsonify({
                'message': 'AI 深度解读报告已存在。',
                'projectId': project_id,
                'task': task,
                'taskId': task["id"],
                'cached': True,
            }), 200

        task = create_bid_interpretation_task(
            project_id,
            metadata=build_project_task_metadata_from_project(
                project,
                {"requested_from": "interpretation_page", "cached": False},
            ),
        )

        from backend.tasks.interpretation_tasks import run_ai_interpretation_report

        run_ai_interpretation_report.delay(project_id, task["id"])

        return jsonify({
            'message': 'AI 深度解读任务已创建。',
            'projectId': project_id,
            'task': task,
            'taskId': task["id"],
            'cached': False,
        }), 201
    except Exception as e:
        logging.exception("创建 AI 深度解读任务失败: %s", project_id)
        return jsonify({'error': f'创建 AI 深度解读任务失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/ai-report-tasks/<task_id>', methods=['GET'])
def get_interpretation_ai_report_task(project_id, task_id):
    """查询 AI 深度解读任务状态。"""
    try:
        uuid.UUID(project_id)
        uuid.UUID(task_id)
    except ValueError:
        return jsonify({'error': 'project_id 或 task_id 不是合法 UUID。'}), 400

    try:
        task = get_bid_interpretation_task(project_id, task_id)
        if not task:
            return jsonify({'error': 'AI 深度解读任务不存在。'}), 404
        return jsonify({"task": task})
    except Exception as e:
        logging.exception("查询 AI 深度解读任务失败: %s", project_id)
        return jsonify({'error': f'查询 AI 深度解读任务失败: {str(e)}'}), 500

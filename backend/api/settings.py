"""
系统设置路由模块。

负责运行时配置的读取与保存（GET/POST /api/bidding/settings）。
视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import logging
import os
import uuid

from flask import jsonify, request

from backend.api._shared import bp
from backend.core.config import DEFAULT_SETTINGS, load_runtime_settings, save_runtime_settings
from backend.db.supabase_repo import get_ai_usage_overview


@bp.route('/settings', methods=['GET'])
def get_runtime_settings():
    settings = load_runtime_settings()
    return jsonify({
        "settings": settings,
        "defaults": DEFAULT_SETTINGS,
        "sensitive": {
            "dashscope_api_key_configured": bool(os.getenv("DASHSCOPE_API_KEY")),
            "deepseek_api_key_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
            "supabase_url_configured": bool(os.getenv("SUPABASE_URL")),
            "supabase_service_role_configured": bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
        }
    }), 200


@bp.route('/settings/ai-usage', methods=['GET'])
@bp.route('/ai-usage', methods=['GET'])
def get_ai_usage_settings_summary():
    try:
        project_id = request.args.get("projectId")
        days = int(request.args.get("days") or 30)
        if project_id:
            try:
                uuid.UUID(project_id)
            except ValueError:
                return jsonify({'error': 'projectId 不是合法 UUID。'}), 400
        return jsonify(get_ai_usage_overview(project_id=project_id, days=days)), 200
    except Exception as e:
        logging.exception("查询 AI 用量统计失败")
        return jsonify({'error': f'查询 AI 用量统计失败: {str(e)}'}), 500


@bp.route('/settings', methods=['POST'])
def update_runtime_settings():
    data = request.get_json() or {}
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else data
    saved = save_runtime_settings(settings)
    return jsonify({
        "settings": saved,
        "message": "系统设置已保存，新的模型配置会在下一次请求时生效。"
    }), 200

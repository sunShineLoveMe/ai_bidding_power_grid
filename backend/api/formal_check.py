from __future__ import annotations

import logging
import uuid

from flask import jsonify, request

from backend.api._shared import bp
from backend.services.formal_bid_check import build_formal_bid_check_report


@bp.route("/projects/<project_id>/formal-check", methods=["GET"])
def get_project_formal_check(project_id: str):
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({"error": "项目 ID 格式不正确"}), 400

    export_task_id = request.args.get("exportTaskId") or None
    try:
        return jsonify(build_formal_bid_check_report(project_id, export_task_id=export_task_id)), 200
    except Exception as exc:
        logging.exception("生成正式检查报告失败: %s", project_id)
        return jsonify({"error": f"生成正式检查报告失败: {exc}"}), 500


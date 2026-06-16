from __future__ import annotations

import logging
import uuid

from flask import jsonify

from backend.api._shared import bp
from backend.services.bid_prefill import build_bid_prefill_report


@bp.route("/projects/<project_id>/prefill-report", methods=["GET"])
def get_project_prefill_report(project_id: str):
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({"error": "项目 ID 格式不正确"}), 400

    try:
        return jsonify(build_bid_prefill_report(project_id)), 200
    except Exception as exc:
        logging.exception("生成投标前导确认页预填缺口报告失败: %s", project_id)
        return jsonify({"error": f"生成投标确认报告失败: {exc}"}), 500

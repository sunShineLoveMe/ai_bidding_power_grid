from __future__ import annotations

import logging
import uuid

from flask import jsonify, request

from backend.api._shared import bp
from backend.services.bid_prefill import apply_bid_prefill_confirmation, build_bid_prefill_report


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


@bp.route("/projects/<project_id>/prefill-confirmation/apply", methods=["POST"])
def apply_project_prefill_confirmation(project_id: str):
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({"error": "项目 ID 格式不正确"}), 400

    payload = request.get_json(silent=True) or {}
    if payload.get("confirmed") is not True:
        return jsonify({"error": "必须由用户显式确认后才能应用投标变量"}), 400
    try:
        result = apply_bid_prefill_confirmation(project_id, payload.get("confirmedValues") or {})
        return jsonify({
            "message": "投标确认值已保存并应用到明确占位符。",
            "application": result,
        }), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logging.exception("应用投标确认值失败: %s", project_id)
        return jsonify({"error": f"应用投标确认值失败: {exc}"}), 500

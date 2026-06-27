"""AI assisted editing routes for bid section content."""

from __future__ import annotations

import logging
import uuid

from flask import jsonify, request

from backend.api._shared import bp
from backend.services.ai_editing import edit_bid_section_text


@bp.route('/interpretations/<project_id>/sections/ai-edit', methods=['POST'])
def ai_edit_bid_section(project_id: str):
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400

    payload = request.get_json(silent=True) or {}
    try:
        result = edit_bid_section_text(project_id, payload)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logging.exception("AI 辅助编辑失败: %s", project_id)
        return jsonify({'error': f'AI 辅助编辑失败：{str(exc)}'}), 500

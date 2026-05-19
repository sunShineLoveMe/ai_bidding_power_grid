"""
全文篇幅设置路由模块。

负责：
  - POST /api/bidding/interpretations/<project_id>/length-settings  保存全文篇幅设置

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import logging
import uuid

from flask import jsonify, request

from backend.api._shared import bp
from backend.ai.length_settings import (
    allocate_chapter_length_targets,
    apply_length_allocations_to_sections,
    evaluate_length_feasibility,
    normalize_length_settings,
)
from backend.db.supabase_repo import (
    get_project_interpretation,
    update_bid_analysis_project_meta,
    upsert_bid_section,
)


@bp.route('/interpretations/<project_id>/length-settings', methods=['POST'])
def save_interpretation_length_settings(project_id):
    """保存全文篇幅设置，并按技术标/商务标目标刷新章节写作计划。"""
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400

    try:
        payload = request.get_json(force=True) or {}
        interpretation = get_project_interpretation(project_id)
        analysis = interpretation.get("analysis") or {}
        sections = interpretation.get("sections") or []
        if not analysis:
            return jsonify({'error': '当前项目尚无招标解读结果，无法保存全文设置。'}), 404
        if not sections:
            return jsonify({'error': '当前项目尚无标书章节，需先生成章节大纲。'}), 400

        settings = normalize_length_settings(payload)
        feasibility = evaluate_length_feasibility(settings, sections)
        allocations = allocate_chapter_length_targets(sections, settings)
        next_sections = apply_length_allocations_to_sections(sections, allocations, settings)
        saved_sections = [upsert_bid_section(project_id, section) for section in next_sections]

        project_meta = analysis.get("project_meta") if isinstance(analysis.get("project_meta"), dict) else {}
        next_project_meta = {
            **project_meta,
            "length_settings": settings,
            "length_feasibility": feasibility,
        }
        update_bid_analysis_project_meta(project_id, next_project_meta)

        return jsonify({
            "settings": settings,
            "feasibility": feasibility,
            "allocations": allocations,
            "sections": saved_sections,
        })
    except Exception as e:
        logging.exception("保存全文篇幅设置失败: %s", project_id)
        return jsonify({'error': f'保存全文篇幅设置失败: {str(e)}'}), 500

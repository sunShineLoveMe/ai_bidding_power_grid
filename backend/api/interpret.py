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
from backend.db.supabase_repo import get_project_interpretation


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

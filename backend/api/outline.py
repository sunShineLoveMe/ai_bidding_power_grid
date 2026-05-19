"""
标书章节大纲路由模块。

负责：
  - POST /api/bidding/interpretations/<project_id>/bid-outline        生成标书章节大纲
  - GET  /api/bidding/interpretations/<project_id>/bid-outline/stream 流式生成标书章节大纲

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import json
import logging
import uuid

from flask import Response, jsonify, stream_with_context

from backend.api._shared import bp
from backend.ai.chapter_planner import generate_bid_outline, stream_bid_outline


@bp.route('/interpretations/<project_id>/bid-outline', methods=['POST'])
def generate_interpretation_bid_outline(project_id):
    """生成并保存标书章节目录与章节大纲。"""
    try:
        uuid.UUID(project_id)
        outline = generate_bid_outline(project_id)
        return jsonify({
            'message': '标书章节大纲已生成。',
            'projectId': project_id,
            'bidOutline': outline,
        })
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("生成标书章节大纲失败: %s", project_id)
        return jsonify({'error': f'生成标书章节大纲失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/bid-outline/stream', methods=['GET'])
def stream_interpretation_bid_outline(project_id):
    """以 SSE 方式逐章生成并保存标书章节大纲。"""
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400

    def event_stream():
        try:
            for event in stream_bid_outline(project_id):
                event_type = event.pop("type", "message")
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logging.exception("流式生成标书章节大纲失败: %s", project_id)
            yield "event: error\n"
            yield f"data: {json.dumps({'error': f'流式生成标书章节大纲失败：{str(e)}'}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )

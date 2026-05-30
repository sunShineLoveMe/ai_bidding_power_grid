# 旧版标书链路（已停用）
"""
旧版标书生成链路路由模块（已停用）。

历史端点：
  - POST /api/bidding/pre-analysis_bid       预处理招标文件
  - POST /api/bidding/chapter-analysis_bid   招标文件章节分析
  - POST /api/bidding/chapter-design         投标文件章节设计
  - POST /api/bidding/generate-bid-document  生成完整投标书文件

这些端点基于早期 SQLite `bidding` 表实现，业务数据已统一迁移到 PostgreSQL，
前端也已改用新的 /api/bidding/upload → /api/bidding/interpretations/* 流程。
SQLite 数据通道下线后，这些路由不再可用，统一返回 HTTP 410 Gone，
保留注册仅为给仍可能存在的旧客户端一个明确的废弃提示，而不是静默 404 或后端崩溃。

如需彻底移除本模块，请同时删除 main.py 末尾的 `from backend.api import legacy` 注册。
"""

from __future__ import annotations

from flask import jsonify

from backend.api._shared import bp


_DEPRECATION_MESSAGE = (
    "该接口属于已停用的旧版标书链路，且依赖已下线的 SQLite 存储。"
    "请改用新的招标解读与投标生成流程：/api/bidding/upload → /api/bidding/interpretations/*。"
)


def _gone():
    return jsonify({"error": _DEPRECATION_MESSAGE, "deprecated": True}), 410


@bp.route('/pre-analysis_bid', methods=['POST'])
def pre_analysis_bid():
    """已停用：旧版招标文件预处理。"""
    return _gone()


@bp.route('/chapter-analysis_bid', methods=['POST'])
def chapter_analysis_bid():
    """已停用：旧版招标文件章节分析。"""
    return _gone()


@bp.route('/chapter-design', methods=['POST'])
def chapter_design():
    """已停用：旧版投标文件章节设计。"""
    return _gone()


@bp.route('/generate-bid-document', methods=['POST'])
def generate_bid_document():
    """已停用：旧版完整投标书生成。"""
    return _gone()

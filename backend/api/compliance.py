"""
合规检查路由模块。

负责：
  - GET  /api/bidding/interpretations/<project_id>/compliance-check           合规覆盖检查
  - POST /api/bidding/interpretations/<project_id>/semantic-compliance-check  LLM 语义合规复核
  - POST /api/bidding/interpretations/<project_id>/compliance-supplement       生成条款补强内容

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import logging
import uuid

from flask import jsonify, request

from backend.api._shared import bp
from backend.ai.compliance_checker import build_compliance_report
from backend.ai.qwen_client import call_dashscope_api
from backend.ai.semantic_compliance import build_semantic_compliance_report
from backend.core.bid_volumes import section_volume_type, volume_name
from backend.core.config import build_enterprise_context, get_stage_model
from backend.export.md_to_word import clean_formal_bid_text


@bp.route('/interpretations/<project_id>/compliance-check', methods=['GET'])
def get_interpretation_compliance_check(project_id):
    """基于结构化条款和标书章节输出合规覆盖检查。"""
    try:
        uuid.UUID(project_id)
        volume_type = request.args.get("volumeType")
        if volume_type not in {"technical", "business"}:
            volume_type = None
        return jsonify(build_compliance_report(project_id, volume_type=volume_type))
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("生成合规覆盖检查失败: %s", project_id)
        return jsonify({'error': f'生成合规覆盖检查失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/semantic-compliance-check', methods=['POST'])
def run_interpretation_semantic_compliance_check(project_id):
    """对高价值条款执行 LLM 语义合规复核。"""
    try:
        uuid.UUID(project_id)
        payload = request.get_json(silent=True) or {}
        volume_type = payload.get("volumeType")
        if volume_type not in {"technical", "business"}:
            volume_type = None
        limit = int(payload.get("limit") or 12)
        use_llm = bool(payload.get("useLlm", True))
        return jsonify(build_semantic_compliance_report(
            project_id,
            volume_type=volume_type,
            limit=limit,
            use_llm=use_llm,
        ))
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("生成语义合规复核失败: %s", project_id)
        return jsonify({'error': f'生成语义合规复核失败: {str(e)}'}), 500


@bp.route('/interpretations/<project_id>/compliance-supplement', methods=['POST'])
def generate_compliance_supplement(project_id):
    """Generate a focused supplement paragraph for an uncovered compliance row."""
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400

    payload = request.get_json(force=True) or {}
    row = payload.get("row") or {}
    section = payload.get("section") or {}
    if not row.get("content"):
        return jsonify({'error': '缺少待补强检查项内容。'}), 400
    if not section.get("title"):
        return jsonify({'error': '缺少建议补强章节。'}), 400

    prompt = f"""
你是资深投标文件审查与补强专家。请针对一个未响应或待补强的招标检查项，生成一段可直接追加到当前章节中的正式标书补强内容。

要求：
1. 只输出 Markdown 正文片段，不要解释生成过程。
2. 语言正式、稳健、可落地，符合国内水利施工投标文件表达习惯。
3. 不得编造证书编号、人员姓名、合同金额、具体日期、未提供的企业业绩；缺失事实用"【待补充：...】"占位。
4. 不使用 emoji、图标符号或装饰性提示符。
5. 内容应紧扣检查项，补充可执行措施、证明材料、页码索引或人工复核提示。
6. 篇幅控制在 300-600 字。

企业画像：
{build_enterprise_context()}

当前章节：
- 标题：{section.get("title")}
- 编写目标：{section.get("purpose") or "需结合章节正文补强"}
- 所属分册：{volume_name(section_volume_type(section))}

当前章节已有正文摘要：
{str(section.get("content") or "")[:1600]}

待补强检查项：
- 类别：{row.get("category") or "检查项"}
- 状态：{row.get("status") or "missing"}
- 重要性：{row.get("importance") or "medium"}
- 内容：{row.get("content")}
- 来源页码：{row.get("sourcePage") or "需复核"}
- 原文依据：{row.get("sourceText") or row.get("content")}
""".strip()

    try:
        response = call_dashscope_api(
            [{"role": "user", "content": prompt}],
            model=get_stage_model("compliance"),
            json_mode=False,
            usage_context={
                "project_id": project_id,
                "section_id": section.get("id"),
                "stage": "compliance_supplement",
                "metadata": {"row_id": row.get("id"), "row_status": row.get("status")},
            },
        )
        content = response["output"]["choices"][0]["message"]["content"].strip()
        content = clean_formal_bid_text(content)
        if not content:
            raise RuntimeError("模型未返回有效补强内容。")
        return jsonify({
            "projectId": project_id,
            "sectionId": section.get("id"),
            "rowId": row.get("id"),
            "content": content,
        })
    except Exception as e:
        logging.exception("生成条款补强内容失败: %s", project_id)
        return jsonify({'error': f'生成条款补强内容失败: {str(e)}'}), 500

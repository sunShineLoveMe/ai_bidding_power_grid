"""AI assisted editing for bid section text."""

from __future__ import annotations

import re
import uuid
from typing import Any

from backend.ai.qwen_client import call_dashscope_api
from backend.core.config import build_enterprise_context, get_stage_model
from backend.core.llm_json_utils import strip_llm_json
from backend.db.supabase_repo import get_project_interpretation


AI_EDIT_ACTIONS: dict[str, dict[str, str]] = {
    "expand": {
        "label": "扩写",
        "instruction": "在不编造项目事实、金额、日期、证书、业绩、参数的前提下，补充正式投标文件常用的承诺、措施、衔接语和执行细节。",
    },
    "shorten": {
        "label": "缩写",
        "instruction": "压缩重复表达，保留事实、承诺、数值、期限、主体和否决风险相关信息，输出更精炼的正式表述。",
    },
    "polish": {
        "label": "润色",
        "instruction": "提升语句通顺度、正式度和专业性，保留原意、事实、数值、结构和关键术语。",
    },
    "formalize": {
        "label": "正式化",
        "instruction": "改写为正式投标文件语气，使用严谨、承诺式、可交付的表达，避免口语化和草稿痕迹。",
    },
}

MAX_SELECTED_CHARS = 5000
MAX_CONTEXT_CHARS = 6000


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truncate(value: str, limit: int) -> str:
    value = _text(value)
    return value if len(value) <= limit else value[:limit]


def _uuid_or_none(value: Any) -> str | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        uuid.UUID(raw)
    except ValueError:
        return None
    return raw


def _response_content(payload: dict[str, Any]) -> str:
    return (
        payload.get("output", {})
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content")
        or ""
    )


def _parse_edit_response(payload: dict[str, Any]) -> dict[str, Any]:
    content = _response_content(payload)
    try:
        parsed = strip_llm_json(content)
    except Exception as exc:
        raise RuntimeError("AI 辅助编辑返回格式异常，请稍后重试。") from exc
    revised_text = _text(parsed.get("revised_text"))
    if not revised_text:
        raise RuntimeError("AI 辅助编辑未返回有效正文。")
    warnings = parsed.get("warnings") or []
    if not isinstance(warnings, list):
        warnings = [str(warnings)]
    return {
        "revisedText": revised_text,
        "summary": _text(parsed.get("summary")),
        "warnings": [str(item) for item in warnings if str(item).strip()][:5],
    }


def build_ai_edit_messages(
    *,
    project_payload: dict[str, Any],
    action: str,
    selected_text: str,
    section_title: str = "",
    section_context: str = "",
    full_content: str = "",
) -> list[dict[str, str]]:
    action_spec = AI_EDIT_ACTIONS[action]
    project = project_payload.get("project") or {}
    analysis = project_payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") if isinstance(analysis.get("project_meta"), dict) else {}
    enterprise_context = build_enterprise_context()
    selected_text = _truncate(selected_text, MAX_SELECTED_CHARS)
    full_content = _truncate(full_content, MAX_CONTEXT_CHARS)

    system = (
        "你是国家电网投标文件正文编辑助手，只负责对用户选中的章节文字做局部编辑。\n"
        "必须遵守：\n"
        "1. 不得编造企业资质、业绩、检测报告、产品参数、报价、金额、保证金、授权代表、身份证号、签署日期。\n"
        "2. 不得混用辽宁招标要求、河北豪乾参考稿和泰昌企业事实；缺失事实只能保留原文或提示人工确认。\n"
        "3. 不输出解释性前后缀，不输出 Markdown 代码块，不输出内部检索字段。\n"
        "4. 尽量保持原文 Markdown/列表/表格结构；只返回 JSON。"
    )
    user = f"""
编辑动作：{action_spec['label']}
动作要求：{action_spec['instruction']}

投标主体：
{enterprise_context}

项目上下文：
- 项目名称：{project_meta.get('project_name') or project.get('project_name') or '未确认'}
- 招标编号：{project_meta.get('tender_no') or project.get('project_no') or '未确认'}
- 章节标题：{section_title or '未命名章节'}
- 章节用途：{section_context or '未提供'}

当前章节全文片段：
{full_content or '未提供'}

用户选中文本：
{selected_text}

请仅返回 JSON：
{{
  "revised_text": "编辑后的文本",
  "summary": "一句话说明修改重点",
  "warnings": ["如存在事实缺口或人工确认项，在这里列出；没有则返回空数组"]
}}
""".strip()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def edit_bid_section_text(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    action = _text(payload.get("action"))
    if action not in AI_EDIT_ACTIONS:
        raise ValueError("不支持的 AI 编辑动作。")
    selected_text = _text(payload.get("selectedText") or payload.get("selected_text"))
    if not selected_text:
        raise ValueError("请先选中需要 AI 编辑的正文。")
    if len(selected_text) > MAX_SELECTED_CHARS:
        raise ValueError(f"选中文本过长，请控制在 {MAX_SELECTED_CHARS} 字以内。")
    if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", selected_text):
        raise ValueError("选中文本缺少有效内容。")

    project_payload = get_project_interpretation(project_id)
    messages = build_ai_edit_messages(
        project_payload=project_payload,
        action=action,
        selected_text=selected_text,
        section_title=_text(payload.get("sectionTitle") or payload.get("section_title")),
        section_context=_text(payload.get("sectionContext") or payload.get("section_context")),
        full_content=_text(payload.get("fullContent") or payload.get("full_content")),
    )
    response = call_dashscope_api(
        messages,
        model=get_stage_model("section_writing"),
        json_mode=True,
        usage_context={
            "operation_type": "text_generation",
            "stage": "bid_ai_edit",
            "project_id": project_id,
            "section_id": _uuid_or_none(payload.get("sectionId") or payload.get("section_id")),
            "metadata": {
                "action": action,
                "selected_chars": len(selected_text),
                "source_section_id": _text(payload.get("sectionId") or payload.get("section_id")) or None,
            },
        },
    )
    result = _parse_edit_response(response)
    return {
        "action": action,
        "actionLabel": AI_EDIT_ACTIONS[action]["label"],
        "originalText": selected_text,
        **result,
    }

import json
import re
from typing import Any

from backend.ai.compliance_checker import build_compliance_report
from backend.ai.qwen_client import call_dashscope_api
from backend.core.config import get_stage_model
from backend.core.llm_json_utils import strip_llm_json
from backend.core.bid_volumes import volume_name
from backend.db.supabase_repo import get_project_interpretation


def _clean_text(value: Any, limit: int = 1200) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _row_priority(row: dict[str, Any]) -> int:
    score = 0
    if row.get("category") == "风险项":
        score += 80
    if row.get("category") == "评分项":
        score += 60
    if row.get("status") == "missing":
        score += 45
    if row.get("status") == "partial":
        score += 30
    if str(row.get("importance") or "").lower() in {"high", "red", "否决", "废标"}:
        score += 40
    if "分" in str(row.get("importance") or ""):
        score += 20
    return score


def select_semantic_review_rows(rows: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    candidates = [
        row for row in rows
        if row.get("status") != "covered"
        or row.get("category") in {"风险项", "评分项"}
        or str(row.get("importance") or "").lower() in {"high", "red", "否决", "废标"}
    ]
    candidates.sort(key=_row_priority, reverse=True)
    return candidates[:max(1, min(limit, 30))]


def _section_by_id(sections: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(section.get("id")): section for section in sections if section.get("id")}


def _candidate_section(row: dict[str, Any], sections_by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for key in ("matchedChapterId", "suggestedChapterId"):
        section_id = row.get(key)
        if section_id and str(section_id) in sections_by_id:
            return sections_by_id[str(section_id)]
    return None


def _heuristic_review(row: dict[str, Any], section: dict[str, Any] | None, *, reason: str | None = None) -> dict[str, Any]:
    content = _clean_text(section.get("content") if section else "", 1600)
    evidence = ""
    confidence = 0.18
    status = row.get("status") or "missing"
    if section and content:
        terms = [term for term in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{3,}", str(row.get("content") or "")) if len(term) >= 3]
        matched = [term for term in terms[:20] if term in content]
        confidence = min(0.82, 0.35 + len(matched) * 0.04)
        if matched and status == "missing":
            status = "partial"
        evidence = content[:220]
    return {
        "rowId": row.get("id"),
        "category": row.get("category"),
        "importance": row.get("importance"),
        "status": status,
        "evidence": evidence or "未找到可直接引用的正文证据。",
        "confidence": round(confidence, 2),
        "weight": _semantic_weight(row),
        "suggestion": reason or _default_suggestion(row),
        "targetSectionId": row.get("suggestedChapterId") or row.get("matchedChapterId"),
        "targetSectionTitle": row.get("suggestedChapter") or row.get("matchedChapter"),
        "llmReviewed": False,
    }


def _semantic_weight(row: dict[str, Any]) -> str:
    if row.get("category") == "风险项":
        return "高风险" if str(row.get("importance") or "").lower() in {"high", "red", "否决", "废标"} else "风险项"
    if row.get("category") == "评分项":
        return str(row.get("importance") or "评分项")
    return str(row.get("importance") or "一般条款")


def _default_suggestion(row: dict[str, Any]) -> str:
    if row.get("category") == "风险项":
        return "建议补充明确承诺、控制措施、责任人/责任部门、检查记录和附件索引，避免形成否决或扣分风险。"
    if row.get("category") == "评分项":
        return "建议补充可量化承诺、实施措施、证明材料、页码索引和与评分点逐项对应的表述。"
    return "建议补充对招标要求的直接响应、证明材料索引和人工复核占位。"


def _build_prompt(row: dict[str, Any], section: dict[str, Any] | None) -> str:
    return f"""
你是资深投标文件合规评审专家。请判断当前标书正文是否实质响应检查项。

只输出 JSON，不要输出解释。JSON 字段：
- status: covered、partial、missing 三选一
- evidence: 从正文中摘录能证明响应的短句，最多 120 字；没有证据则为空字符串
- confidence: 0-1 的小数
- weight: 评分权重或风险等级
- suggestion: 简明补强建议，最多 120 字

判断要求：
1. 不能只看关键词重复，要判断是否有实质措施、承诺、证明材料或附件索引。
2. 若正文只是泛泛表态，没有具体措施或证据，应判为 partial。
3. 若正文没有相关内容，应判为 missing。
4. 不得编造正文中不存在的证据。

检查项：
- 类别：{row.get("category")}
- 重要性：{row.get("importance")}
- 内容：{row.get("content")}
- 来源原文：{row.get("sourceText") or row.get("content")}

候选章节：
- 标题：{section.get("title") if section else "未定位"}
- 正文摘录：{_clean_text(section.get("content") if section else "", 2600)}
""".strip()


def _call_llm_review(project_id: str, row: dict[str, Any], section: dict[str, Any] | None) -> dict[str, Any]:
    response = call_dashscope_api(
        [{"role": "user", "content": _build_prompt(row, section)}],
        model=get_stage_model("compliance"),
        json_mode=True,
        usage_context={
            "project_id": project_id,
            "section_id": section.get("id") if section else None,
            "stage": "semantic_compliance_review",
            "operation_type": "text_generation",
            "metadata": {"row_id": row.get("id"), "category": row.get("category")},
        },
    )
    content = response.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content") or "{}"
    parsed = strip_llm_json(content) if isinstance(content, str) else {}
    status = parsed.get("status") if parsed.get("status") in {"covered", "partial", "missing"} else row.get("status")
    try:
        confidence = max(0, min(float(parsed.get("confidence", 0)), 1))
    except (TypeError, ValueError):
        confidence = 0.5
    return {
        "rowId": row.get("id"),
        "category": row.get("category"),
        "importance": row.get("importance"),
        "status": status,
        "evidence": _clean_text(parsed.get("evidence"), 160),
        "confidence": round(confidence, 2),
        "weight": _clean_text(parsed.get("weight") or _semantic_weight(row), 60),
        "suggestion": _clean_text(parsed.get("suggestion") or _default_suggestion(row), 180),
        "targetSectionId": row.get("suggestedChapterId") or row.get("matchedChapterId"),
        "targetSectionTitle": row.get("suggestedChapter") or row.get("matchedChapter"),
        "llmReviewed": True,
    }


def build_semantic_compliance_report(
    project_id: str,
    *,
    volume_type: str | None = None,
    limit: int = 12,
    use_llm: bool = True,
) -> dict[str, Any]:
    base_report = build_compliance_report(project_id, volume_type=volume_type)
    payload = get_project_interpretation(project_id)
    sections = payload.get("sections") or []
    sections_by_id = _section_by_id(sections)
    selected_rows = select_semantic_review_rows(base_report.get("rows") or [], limit=limit)

    reviews: list[dict[str, Any]] = []
    for row in selected_rows:
        section = _candidate_section(row, sections_by_id)
        if not use_llm:
            reviews.append(_heuristic_review(row, section))
            continue
        try:
            reviews.append(_call_llm_review(project_id, row, section))
        except Exception as exc:
            reviews.append(_heuristic_review(row, section, reason=f"LLM 复核失败，已使用规则兜底：{str(exc)[:80]}"))

    total = len(reviews)
    covered = sum(1 for item in reviews if item["status"] == "covered")
    partial = sum(1 for item in reviews if item["status"] == "partial")
    missing = sum(1 for item in reviews if item["status"] == "missing")
    percent = round(((covered + partial * 0.5) / total) * 100) if total else 0

    return {
        "projectId": project_id,
        "volumeType": volume_type or "all",
        "volumeName": "完整投标文件" if not volume_type else ("商务标" if volume_type == "business" else volume_name(volume_type)),
        "baseSummary": base_report.get("summary") or {},
        "summary": {
            "total": total,
            "covered": covered,
            "partial": partial,
            "missing": missing,
            "percent": percent,
            "llmReviewed": sum(1 for item in reviews if item.get("llmReviewed")),
        },
        "reviews": reviews,
        "recommendations": [
            "语义复核优先检查高风险项、评分项、未覆盖和待补强项；结果用于下载前质量把关，不替代人工终审。",
            "置信度低或证据为空的检查项，应优先定位章节并生成补强内容。",
        ],
    }

import json
import logging
import math
from typing import Any

from backend.core.config import build_enterprise_context, get_setting, get_stage_model
from backend.db.supabase_repo import get_project_interpretation, get_supabase_client, list_project_document_chunks
from backend.core.llm_json_utils import strip_llm_json
from backend.ai.qwen_client import call_dashscope_api


def _compact_items(items: list[dict[str, Any]], fields: list[str], limit: int) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for item in items[:limit]:
        row: dict[str, Any] = {}
        for field in fields:
            value = item.get(field)
            if value is not None:
                row[field] = value
        compacted.append(row)
    return compacted


def _build_prompt(payload: dict[str, Any]) -> str:
    project = payload.get("project") or {}
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") or {}

    context = {
        "project": {
            "id": project.get("id"),
            "project_name": project_meta.get("project_name") or project.get("project_name"),
            "tender_no": project_meta.get("tender_no") or project.get("project_no"),
            "project_type": project.get("project_type"),
            "summary": analysis.get("summary"),
        },
        "requirements": _compact_items(
            payload.get("requirements") or [],
            ["requirement_type", "priority", "content", "source_section", "source_page", "source_text"],
            70,
        ),
        "risks": _compact_items(
            payload.get("risks") or [],
            ["risk_level", "risk_type", "content", "action", "source_section", "source_page", "source_text"],
            50,
        ),
        "scoring_items": _compact_items(
            payload.get("scoringItems") or [],
            ["category", "item", "score", "requirement", "response_suggestion", "source_page", "source_text"],
            40,
        ),
        "chapter_suggestions": _compact_items(
            payload.get("chapterSuggestions") or [],
            ["chapter_title", "priority", "reason"],
            30,
        ),
    }

    enterprise_context = build_enterprise_context()

    return f"""
你是资深水利工程招投标顾问，熟悉国内水利工程招投标、资质审查、技术响应、商务响应和评分规则。
企业画像：
{enterprise_context}

请基于下方已经结构化的招标文件信息，生成一份给非技术业务人员阅读的深度招标解读报告。
要求：
1. 不要复述系统处理过程，不要提 MinerU、OCR、分片。
2. 不要编造原文没有的信息；不确定的地方明确写“需人工复核”。
3. 每个重点建议尽量带来源页码，并在 evidence 字段引用压缩后的原文依据，不要只给结论。
4. 输出必须是严格 JSON，不要 Markdown，不要代码块。
5. JSON 字段必须与下面格式一致。

输出 JSON 格式：
{{
  "executive_summary": ["..."],
  "project_brief": {{
    "project_name": "...",
    "tender_no": "...",
    "procurement_scope": "...",
    "key_deadlines": ["..."],
    "core_conclusion": "..."
  }},
  "qualification_review": [
    {{"requirement": "...", "judgement": "需准备/需复核/风险较高", "evidence": "对应原文依据或来源章节", "source_page": 1, "action": "..."}}
  ],
  "scoring_strategy": [
    {{"scoring_point": "...", "score": null, "strategy": "...", "supporting_materials": ["..."], "source_page": 1, "evidence": "对应原文依据或来源章节"}}
  ],
  "risk_warnings": [
    {{"risk_level": "high/medium/low", "risk": "...", "impact": "...", "source_page": 1, "evidence": "对应原文依据或来源章节", "mitigation": "..."}}
  ],
  "document_plan": [
    {{"chapter": "...", "purpose": "...", "key_points": ["..."], "related_requirements": ["..."]}}
  ],
  "material_checklist": [
    {{"material": "...", "category": "资信/业绩/技术/商务/其他", "required": true, "owner": "企业/项目/人工复核", "note": "..."}}
  ],
  "next_actions": ["..."]
}}

结构化招标信息：
{json.dumps(context, ensure_ascii=False)}
""".strip()


def _normalize_list(value: Any, limit: int) -> list[Any]:
    return value[:limit] if isinstance(value, list) else []


def _empty_report() -> dict[str, Any]:
    return {
        "executive_summary": [],
        "project_brief": {
            "project_name": "",
            "tender_no": "",
            "procurement_scope": "",
            "key_deadlines": [],
            "core_conclusion": "",
        },
        "qualification_review": [],
        "scoring_strategy": [],
        "risk_warnings": [],
        "document_plan": [],
        "material_checklist": [],
        "next_actions": [],
    }


def _normalize_report(report: dict[str, Any]) -> dict[str, Any]:
    normalized = _empty_report()
    if not isinstance(report, dict):
        return normalized
    project_brief = report.get("project_brief") if isinstance(report.get("project_brief"), dict) else {}
    normalized["executive_summary"] = _normalize_list(report.get("executive_summary"), 12)
    normalized["project_brief"] = {
        **normalized["project_brief"],
        **{key: project_brief.get(key) for key in normalized["project_brief"].keys() if project_brief.get(key) is not None},
    }
    normalized["qualification_review"] = _normalize_list(report.get("qualification_review"), 80)
    normalized["scoring_strategy"] = _normalize_list(report.get("scoring_strategy"), 80)
    normalized["risk_warnings"] = _normalize_list(report.get("risk_warnings"), 80)
    normalized["document_plan"] = _normalize_list(report.get("document_plan"), 80)
    normalized["material_checklist"] = _normalize_list(report.get("material_checklist"), 120)
    normalized["next_actions"] = _normalize_list(report.get("next_actions"), 20)
    return normalized


def _chunk_source_text(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    page = chunk.get("source_page") or metadata.get("page") or metadata.get("source_page") or "未知"
    section = chunk.get("source_section") or metadata.get("heading") or metadata.get("source_section") or "未知章节"
    content = str(chunk.get("content") or "").strip()
    return f"【chunk {chunk.get('chunk_index')}｜页码 {page}｜章节 {section}】\n{content}"


def _segment_chunks(chunks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    max_chars = int(get_setting("interpretation_segment_max_chars", 24000) or 24000)
    max_groups = int(get_setting("interpretation_segment_max_groups", 24) or 24)
    raw_groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for chunk in chunks:
        text_len = len(str(chunk.get("content") or ""))
        if current and current_chars + text_len > max_chars:
            raw_groups.append(current)
            current = []
            current_chars = 0
        current.append(chunk)
        current_chars += text_len
    if current:
        raw_groups.append(current)
    if len(raw_groups) <= max_groups:
        return raw_groups

    logging.warning(
        "招标解读分段数量超过配置上限，将合并相邻分段以避免丢失正文: raw_groups=%s max_groups=%s",
        len(raw_groups),
        max_groups,
    )
    merged_groups: list[list[dict[str, Any]]] = []
    raw_groups_per_segment = max(1, math.ceil(len(raw_groups) / max_groups))
    for index in range(0, len(raw_groups), raw_groups_per_segment):
        merged: list[dict[str, Any]] = []
        for group in raw_groups[index : index + raw_groups_per_segment]:
            merged.extend(group)
        merged_groups.append(merged)
    return merged_groups[:max_groups]


def _build_segment_prompt(payload: dict[str, Any], group: list[dict[str, Any]], index: int, total: int) -> str:
    project = payload.get("project") or {}
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") or {}
    text = "\n\n---\n\n".join(_chunk_source_text(chunk) for chunk in group)
    return f"""
你是资深水利工程招投标顾问。请只基于当前文档分段抽取结构化招标解读信息。
这是第 {index}/{total} 段。不得编造当前分段没有的信息；必须保留页码、章节和原文证据。

企业画像：
{build_enterprise_context()}

项目基础信息：
{json.dumps({
    "project_name": project_meta.get("project_name") or project.get("project_name"),
    "tender_no": project_meta.get("tender_no") or project.get("project_no"),
    "summary": analysis.get("summary"),
}, ensure_ascii=False)}

输出必须是严格 JSON，字段如下：
{json.dumps(_empty_report(), ensure_ascii=False)}

当前分段原文：
{text}
""".strip()


def _build_merge_prompt(payload: dict[str, Any], segment_reports: list[dict[str, Any]]) -> str:
    base_context = {
        "project": (payload.get("project") or {}),
        "analysis_summary": (payload.get("analysis") or {}).get("summary"),
        "structured_requirements": _compact_items(
            payload.get("requirements") or [],
            ["requirement_type", "priority", "content", "source_section", "source_page", "source_text"],
            80,
        ),
        "structured_risks": _compact_items(
            payload.get("risks") or [],
            ["risk_level", "risk_type", "content", "action", "source_section", "source_page", "source_text"],
            60,
        ),
        "structured_scoring_items": _compact_items(
            payload.get("scoringItems") or [],
            ["category", "item", "score", "requirement", "response_suggestion", "source_page", "source_text"],
            60,
        ),
    }
    compact_segments = [
        {
            "segment_index": idx + 1,
            "executive_summary": report.get("executive_summary", [])[:6],
            "qualification_review": report.get("qualification_review", [])[:30],
            "scoring_strategy": report.get("scoring_strategy", [])[:30],
            "risk_warnings": report.get("risk_warnings", [])[:30],
            "document_plan": report.get("document_plan", [])[:24],
            "material_checklist": report.get("material_checklist", [])[:40],
            "next_actions": report.get("next_actions", [])[:8],
        }
        for idx, report in enumerate(segment_reports)
    ]
    return f"""
你是资深水利工程招投标顾问。请把多个分段解读结果融合为一份最终招标解读报告。
要求：
1. 去重合并同类资格项、评分项、风险项和材料清单。
2. 高风险、否决项、资格要求、评分项优先。
3. 结论必须带 evidence/source_page；不确定内容写“需人工复核”。
4. 不要提分段、chunk、MinerU、OCR 或系统处理过程。
5. 输出严格 JSON，字段必须与示例一致。

输出 JSON 示例：
{json.dumps(_empty_report(), ensure_ascii=False)}

结构化基础信息：
{json.dumps(base_context, ensure_ascii=False)}

分段解读结果：
{json.dumps(compact_segments, ensure_ascii=False)}
""".strip()


def _call_segment_interpretation(payload: dict[str, Any], group: list[dict[str, Any]], index: int, total: int) -> dict[str, Any]:
    response = call_dashscope_api(
        [{"role": "user", "content": _build_segment_prompt(payload, group, index, total)}],
        model=get_stage_model("interpretation_segment", get_stage_model("section_writing")),
        json_mode=True,
        usage_context={
            "project_id": (payload.get("project") or {}).get("id"),
            "stage": "ai_interpretation_segment",
            "metadata": {
                "segment_index": index,
                "segment_total": total,
                "chunk_start": group[0].get("chunk_index") if group else None,
                "chunk_end": group[-1].get("chunk_index") if group else None,
            },
        },
    )
    content = response["output"]["choices"][0]["message"]["content"]
    return _normalize_report(strip_llm_json(content))


def _merge_segment_reports(payload: dict[str, Any], segment_reports: list[dict[str, Any]]) -> tuple[dict[str, Any], str | None]:
    response = call_dashscope_api(
        [{"role": "user", "content": _build_merge_prompt(payload, segment_reports)}],
        model=get_stage_model("interpretation"),
        json_mode=True,
        usage_context={
            "project_id": (payload.get("project") or {}).get("id"),
            "stage": "ai_interpretation_merge",
            "metadata": {"segment_count": len(segment_reports)},
        },
    )
    content = response["output"]["choices"][0]["message"]["content"]
    return _normalize_report(strip_llm_json(content)), response.get("model")


def _generate_segmented_report(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    project_id = (payload.get("project") or {}).get("id")
    chunks = list_project_document_chunks(project_id, limit=1000) if project_id else []
    groups = _segment_chunks(chunks)
    if not groups:
        raise RuntimeError("未找到可用于分段解读的正文分片。")

    segment_reports: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        try:
            logging.info("招标解读分段开始: project_id=%s segment=%s/%s chunks=%s-%s", project_id, index, len(groups), group[0].get("chunk_index"), group[-1].get("chunk_index"))
            segment_reports.append(_call_segment_interpretation(payload, group, index, len(groups)))
        except Exception as exc:
            logging.exception("招标解读分段失败: project_id=%s segment=%s/%s", project_id, index, len(groups))
            failures.append({"segment": index, "error": str(exc)[:300]})

    if not segment_reports:
        raise RuntimeError("所有分段解读均失败，无法生成招标解读。")

    merged, model = _merge_segment_reports(payload, segment_reports)
    merged["_segmented_interpretation"] = {
        "enabled": True,
        "segment_count": len(groups),
        "success_count": len(segment_reports),
        "failure_count": len(failures),
        "failures": failures[:8],
    }
    return merged, {
        "model": model,
        "mode": "segmented",
        "segment_count": len(groups),
        "success_count": len(segment_reports),
        "failure_count": len(failures),
    }


def generate_ai_interpretation_report(project_id: str) -> dict[str, Any]:
    payload = get_project_interpretation(project_id)
    analysis = payload.get("analysis")
    if not analysis:
        raise RuntimeError("当前项目尚无结构化解读数据，请先完成 MinerU 解析和落库。")

    project_meta = analysis.get("project_meta") or {}
    existing_report = project_meta.get("ai_report")
    if isinstance(existing_report, dict) and existing_report:
        return existing_report

    chunks = list_project_document_chunks(project_id, limit=1000)
    use_segmented = len(chunks) >= 12 or sum(len(str(chunk.get("content") or "")) for chunk in chunks) > 80000
    model = None
    generation_mode = "segmented" if use_segmented else "single"
    generation_meta: dict[str, Any] = {}
    if use_segmented:
        try:
            ai_report, generation_meta = _generate_segmented_report(payload)
            model = generation_meta.get("model")
        except Exception:
            logging.exception("分段招标解读失败，尝试回退整体解读: %s", project_id)
            ai_report = {}
            generation_mode = "single_fallback"
    else:
        ai_report = {}

    if not ai_report:
        prompt = _build_prompt(payload)
        response = call_dashscope_api(
            [{"role": "user", "content": prompt}],
            model=get_stage_model("interpretation"),
            json_mode=True,
            usage_context={
                "project_id": project_id,
                "stage": "ai_interpretation_report",
            },
        )
        content = response["output"]["choices"][0]["message"]["content"]
        ai_report = _normalize_report(strip_llm_json(content))
        model = response.get("model") or "dashscope"
        generation_meta = {}

    project_meta["ai_report"] = ai_report
    project_meta["ai_report_model"] = model or get_stage_model("interpretation")
    project_meta["ai_report_generation"] = {
        "mode": generation_meta.get("mode") or generation_mode,
        "document_chunk_count": len(chunks),
        "segment_count": generation_meta.get("segment_count", 0),
        "segment_success_count": generation_meta.get("success_count", 0),
        "segment_failure_count": generation_meta.get("failure_count", 0),
    }

    updated = (
        get_supabase_client()
        .table("bid_analysis")
        .update({"project_meta": project_meta})
        .eq("id", analysis["id"])
        .execute()
    )
    if not updated.data:
        raise RuntimeError("AI 解读报告写回 Supabase 失败")

    return ai_report

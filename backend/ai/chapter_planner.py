import json
import logging
import re
import time
import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from backend.db.supabase_repo import get_project_interpretation, get_supabase_client, replace_bid_sections_from_outline
from backend.services.bid_material_scope import material_scope_from_context, prune_outline_by_material_scope
from backend.services.project_bid_skeleton import (
    build_project_bid_skeleton,
    has_current_tender_skeleton_inputs,
)
from backend.core.llm_json_utils import strip_llm_json
from backend.ai.qwen_client import call_dashscope_api
from backend.ai.bid_writing_plan import build_chapter_writing_plan
from backend.core.config import get_stage_model
from backend.core.bid_volumes import (
    VOLUME_ORDER,
    ensure_section_volume,
    infer_volume_type,
    normalize_volume_type,
    volume_description,
    volume_name,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HAOQIAN_REFERENCE_TEMPLATE_PATH = PROJECT_ROOT / (
    "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/"
    "reference_templates/haoqian_reference_templates.json"
)
REFERENCE_FACT_MARKERS = (
    "有限公司",
    "专利证书",
    "实用新型",
    "软件著作权",
    "认证证书",
    "校准证书",
    "资质文件",
)


def _compact_items(items: list[dict[str, Any]], fields: list[str], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items[:limit]:
        row: dict[str, Any] = {}
        for field in fields:
            value = item.get(field)
            if value not in (None, ""):
                row[field] = value
        rows.append(row)
    return rows


def _text(value: Any) -> str:
    return str(value) if value is not None else ""


def _contains_keyword(item: dict[str, Any], keyword: str, fields: list[str]) -> bool:
    return any(keyword in _text(item.get(field)) for field in fields)


def _dict_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _normalize_material_checklist(items: Any) -> list[dict[str, str]]:
    """AI 解读可能返回字符串或 dict，规则大纲必须容忍两种结构。"""
    if not isinstance(items, list):
        return []
    rows: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            material = _text(
                item.get("material")
                or item.get("name")
                or item.get("title")
                or item.get("content")
                or item.get("requirement")
            ).strip()
            category = _text(item.get("category") or item.get("type") or item.get("section")).strip()
        else:
            material = _text(item).strip()
            category = ""
        if material:
            rows.append({"material": material, "category": category})
    return rows


# ---------------------------------------------------------------------------
# 企业知识库上下文抽取
# ---------------------------------------------------------------------------

def _fetch_knowledge_context(payload: dict[str, Any]) -> dict[str, Any]:
    """
    从企业私有知识库（文档分片 + 资产库）中抽取与本次招标相关的上下文，
    用于指导 AI 生成更贴合企业实际能力的章节大纲。

    返回结构：
    {
        "rag_snippets": [{"title": ..., "content": ..., "category": ...}],  # 知识库文档片段
        "assets_summary": [{"title": ..., "category": ..., "asset_type": ..., "tags": [...]}],  # 资产摘要
        "has_qualification_assets": bool,   # 是否有资质/证书类资产
        "has_product_assets": bool,         # 是否有产品/设备类资产
        "has_case_assets": bool,            # 是否有业绩/案例类资产
        "qualification_titles": [...],      # 资质资产标题列表（用于章节命名）
        "product_titles": [...],            # 产品资产标题列表
    }
    """
    result: dict[str, Any] = {
        "rag_snippets": [],
        "assets_summary": [],
        "has_qualification_assets": False,
        "has_product_assets": False,
        "has_case_assets": False,
        "qualification_titles": [],
        "product_titles": [],
    }

    try:
        from backend.rag.retrieval import search_knowledge_base, search_knowledge_assets

        analysis = payload.get("analysis") or {}
        project_meta = analysis.get("project_meta") or {}
        summary = analysis.get("summary") or ""
        project_name = project_meta.get("project_name") or ""

        # 用项目摘要 + 关键词构造检索 query
        query = f"电网工程投标 {project_name} {summary}"[:300]

        # 1. 检索知识库文档片段（标准话术、施工方案、政策法规等）
        try:
            snippets = search_knowledge_base(
                query,
                match_threshold=0.3,
                match_count=12,
                scenario="writing",
                return_parent=True,
            )
            for snippet in snippets:
                meta = snippet.get("metadata") or {}
                result["rag_snippets"].append({
                    "title": meta.get("source_org") or meta.get("source_file") or "知识库资料",
                    "category": meta.get("category_label") or meta.get("category") or meta.get("doc_type") or "通用",
                    "content": str(snippet.get("content") or "")[:300],
                })
        except Exception:
            logging.warning("chapter_planner: 知识库文档片段检索失败，跳过")

        # 2. 检索企业资产库（资质证书、产品图、业绩证明等）
        try:
            assets = search_knowledge_assets(query, match_count=30)
            for asset in assets:
                asset_type = str(asset.get("asset_type") or "")
                category = str(asset.get("category") or "")
                title = str(asset.get("title") or "")
                tags = asset.get("tags") or []

                result["assets_summary"].append({
                    "title": title,
                    "category": category,
                    "asset_type": asset_type,
                    "tags": tags[:4],
                    "applicable_sections": (asset.get("applicable_sections") or [])[:3],
                })

                if asset_type == "qualification_image" or any(
                    kw in category + title for kw in ["资质", "证书", "营业执照", "许可", "安全生产", "人员", "社保", "业绩"]
                ):
                    result["has_qualification_assets"] = True
                    if title and title not in result["qualification_titles"]:
                        result["qualification_titles"].append(title)

                if asset_type == "product_image" or any(
                    kw in category + title for kw in ["产品", "设备", "材料", "水泵", "闸门", "水轮机", "叶片", "螺母"]
                ):
                    result["has_product_assets"] = True
                    if title and title not in result["product_titles"]:
                        result["product_titles"].append(title)

                if any(kw in category + title for kw in ["业绩", "案例", "合同", "中标", "验收", "类似项目"]):
                    result["has_case_assets"] = True

        except Exception:
            logging.warning("chapter_planner: 企业资产库检索失败，跳过")

    except Exception:
        logging.exception("chapter_planner: 知识库上下文抽取失败，将使用无知识库版本生成大纲")

    return result


def _normalize_outline_chapters(
    chapters: list[dict[str, Any]],
    *,
    volume_type: str | None = None,
    volume_name_override: str | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    order_index = 0
    normalized_volume_type = normalize_volume_type(volume_type) if volume_type else None
    normalized_volume_name = volume_name_override or (volume_name(normalized_volume_type) if normalized_volume_type else None)

    def visit(items: list[dict[str, Any]], level: int, prefix: str = "") -> None:
        nonlocal order_index
        for index, item in enumerate(items, start=1):
            order_index += 1
            children = item.get("children") or item.get("subsections") or []
            order = item.get("order") or (f"{prefix}.{index}" if prefix else index)
            row = {key: value for key, value in item.items() if key not in {"children", "subsections"}}
            row["order"] = order
            row["order_index"] = item.get("order_index") or order_index
            row["level"] = max(1, min(int(item.get("level") or level), 4))
            row["title"] = row.get("title") or "未命名章节"
            row["priority"] = row.get("priority") or "medium"
            row["response_points"] = row.get("response_points") or []
            row["mapped_requirements"] = row.get("mapped_requirements") or []
            row["mapped_scoring_items"] = row.get("mapped_scoring_items") or []
            row["mapped_risks"] = row.get("mapped_risks") or []
            row["source_pages"] = row.get("source_pages") or []
            row["required_materials"] = row.get("required_materials") or []
            row["writing_notes"] = row.get("writing_notes") or []
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            previous_volume_type = metadata.get("volume_type")
            if normalized_volume_type:
                metadata = {
                    **metadata,
                    "volume_type": normalized_volume_type,
                    "volume_name": normalized_volume_name or volume_name(normalized_volume_type),
                    "document_role": metadata.get("document_role") or "正文",
                    "export_group": metadata.get("export_group") or f"{normalized_volume_name or volume_name(normalized_volume_type)}文件",
                }
            row["metadata"] = metadata
            existing_writing_plan = metadata.get("writing_plan")
            should_rebuild_plan = bool(normalized_volume_type)
            row["metadata"] = {
                **metadata,
                "writing_plan": None if should_rebuild_plan else existing_writing_plan,
            }
            if not row["metadata"].get("writing_plan"):
                row["metadata"]["writing_plan"] = build_chapter_writing_plan(row)
            row = ensure_section_volume(row)
            normalized.append(row)
            if isinstance(children, list) and children:
                visit(children, min(level + 1, 4), str(order))

    visit(chapters, 1)
    return normalized


LEAF_SPLIT_TARGET_WORDS = 1200
LEAF_SPLIT_THRESHOLD_WORDS = 1800
LEAF_SPLIT_MAX_CHILDREN = 8
SUPPLY_ONLY_MAX_OUTLINE_NODES = 140
SUPPLY_ONLY_AI_REFINEMENT_MAX_GROWTH = 1.25
SUPPLY_ONLY_FORBIDDEN_OUTLINE_TERMS = (
    "施工组织设计",
    "施工部署",
    "施工方案",
    "工程概况",
    "总体部署",
    "建造师",
    "安全生产许可证",
    "BIM",
    "水利施工",
    "安装总承包",
)
REFERENCE_OUTLINE_RULES_PLANNER_MODE = "guarded_planner_hint"


def _writing_plan_target_words(chapter: dict[str, Any]) -> int:
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    plan = metadata.get("writing_plan") if isinstance(metadata.get("writing_plan"), dict) else {}
    try:
        return int(float(plan.get("target_words") or 0))
    except (TypeError, ValueError):
        return 0


def _chapter_has_child(chapters: list[dict[str, Any]], order: str) -> bool:
    prefix = f"{order}."
    return any(str(item.get("order") or "").startswith(prefix) for item in chapters if str(item.get("order") or "") != order)


def _leaf_split_topics(title: str, count: int) -> list[tuple[str, str]]:
    normalized_title = title or "章节内容"
    technical_bank = [
        ("编制依据", "列明本节引用的招标文件、技术标准、规范规程和响应边界。"),
        ("工程概况", "概述项目范围、建设条件、工作界面、关键约束和实施特点。"),
        ("总体部署", "说明总体组织思路、阶段安排、资源投入和协同机制。"),
        ("组织机构", "说明项目组织架构、岗位职责、沟通机制和管理闭环。"),
        ("实施方法", "围绕关键工序、技术路线、施工流程和质量控制展开响应。"),
        ("进度安排", "说明里程碑、工期控制、交叉作业协调和延误纠偏措施。"),
        ("质量控制", "说明材料、过程、验收、资料归档和质量追溯措施。"),
        ("安全环保", "说明安全生产、文明施工、环境保护、应急响应和风险管控。"),
    ]
    supply_technical_bank = [
        ("招标要求", "归纳本节对应的技术规范、货物清单、标准参数值和响应边界。"),
        ("泰昌响应", "使用泰昌检验报告、产品资料和结构化参数填写投标响应值。"),
        ("偏差核对", "逐项核对标准要求、投标保证值、偏差和人工复核事项。"),
        ("证明材料索引", "列出本节采用的泰昌检验报告、产品资料和附件页码。"),
    ]
    supply_delivery_bank = [
        ("备料与排产", "说明原材料准备、订单分解、生产排程和产能协调。"),
        ("检验与放行", "说明过程检验、出厂检验、不合格控制和放行要求。"),
        ("包装与运输", "说明包装标识、装卸防护、运输计划和到货交接。"),
        ("交付与应急保障", "说明交货计划、进度跟踪、异常订单和应急供货措施。"),
        ("质量追溯", "说明原料、生产批次、检验报告和交付记录的追溯关系。"),
    ]
    qualification_bank = [
        ("响应要求", "概述本项资质、证书、人员或材料对招标资格条件的响应关系。"),
        ("资料清单", "列出应提交的证明文件、复印件、签章和索引要求。"),
        ("有效性说明", "说明证书有效期、主体一致性、业务范围和人工复核要点。"),
        ("附件索引", "建立附件页码、文件名称、证明事项和待补充字段。"),
    ]
    commercial_bank = [
        ("条款响应", "逐项响应合同、付款、履约、服务和偏离要求。"),
        ("承诺事项", "整理工期、质量、服务、保密、廉政和合规承诺。"),
        ("偏离说明", "说明无偏离或偏离事项、风险边界和人工复核点。"),
        ("附件要求", "列明需配套提交的格式文件、签章文件和证明材料。"),
    ]
    title_text = normalized_title
    if any(keyword in title_text for keyword in ["技术偏差", "技术特性参数", "材料配置", "产品制造", "质量控制"]):
        bank = supply_technical_bank
    elif any(keyword in title_text for keyword in ["供货", "交付", "售后", "质量保证"]):
        bank = supply_delivery_bank
    elif any(keyword in title_text for keyword in ["资格", "资质", "证书", "人员", "业绩"]):
        bank = qualification_bank
    elif any(keyword in title_text for keyword in ["商务", "合同", "付款", "承诺", "偏离"]):
        bank = commercial_bank
    else:
        bank = technical_bank
    topics: list[tuple[str, str]] = []
    for index in range(count):
        if index < len(bank):
            topics.append(bank[index])
        else:
            topics.append((f"专项响应 {index + 1}", f"围绕「{normalized_title}」补充专项响应内容，避免大段一次性生成。"))
    return topics


def _reference_outline_rule_sets_for_supply_bid() -> list[dict[str, Any]]:
    """Load DOCX profile reference rules for guarded supply-bid outline planning."""
    try:
        from backend.export.md_to_word import docx_template_report
    except Exception:
        logging.warning("chapter_planner: DOCX reference outline rules unavailable")
        return []

    rule_sets: list[dict[str, Any]] = []
    for file_type in ("技术投标文件", "商务投标文件"):
        try:
            rules = (docx_template_report({"文件类型": file_type}).get("reference_outline_rules") or {})
        except Exception:
            logging.warning("chapter_planner: failed to load DOCX reference outline rules for %s", file_type)
            continue
        if not isinstance(rules, dict):
            continue
        if rules.get("planner_integration") != REFERENCE_OUTLINE_RULES_PLANNER_MODE:
            continue
        rule_sets.append(copy.deepcopy(rules))
    return rule_sets


def _reference_outline_rules_summary(rule_sets: list[dict[str, Any]]) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    for rules in rule_sets:
        for section in rules.get("sections") or []:
            if not isinstance(section, dict):
                continue
            sections.append({
                "id": section.get("id"),
                "title": section.get("title"),
                "volume_type": section.get("volume_type"),
                "section_type": section.get("section_type"),
                "generation_policy": section.get("generation_policy"),
                "requires_table": bool(section.get("requires_table")),
                "structured_data_required": bool(section.get("structured_data_required")),
            })
    return {
        "mode": REFERENCE_OUTLINE_RULES_PLANNER_MODE,
        "source": "DOCX_TEMPLATE_PROFILES.reference_outline_rules",
        "rule_set_count": len(rule_sets),
        "section_count": len(sections),
        "sections": sections,
        "priority": (
            "招标文件明确要求 > 客户确认章节 > 供货类大纲门禁和章节数上限 > "
            "客户范本/规则版回退 > reference_outline_rules 结构化提示 > AI自由生成"
        ),
    }


def _normalize_rule_match_text(value: Any) -> str:
    return re.sub(r"[\s：:、,，;；|（）()\\-_.]+", "", str(value or "")).lower()


def _match_reference_outline_rule(
    title: str,
    volume_type: str | None,
    rule_sets: list[dict[str, Any]],
) -> dict[str, Any] | None:
    normalized_title = _normalize_rule_match_text(title)
    normalized_volume = normalize_volume_type(volume_type) if volume_type else None
    for rules in rule_sets:
        for section in rules.get("sections") or []:
            if not isinstance(section, dict):
                continue
            section_volume = normalize_volume_type(section.get("volume_type"))
            if normalized_volume and section_volume != normalized_volume:
                continue
            tokens = [section.get("title"), *(section.get("aliases") or [])]
            for token in tokens:
                normalized_token = _normalize_rule_match_text(token)
                if normalized_token and (
                    normalized_token in normalized_title or normalized_title in normalized_token
                ):
                    return section
    return None


def _annotate_reference_outline_rule(
    node: dict[str, Any],
    rule_sets: list[dict[str, Any]],
) -> dict[str, Any]:
    if not rule_sets:
        return node
    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
    rule = _match_reference_outline_rule(str(node.get("title") or ""), metadata.get("volume_type"), rule_sets)
    if not rule:
        return node
    annotated_metadata = {
        **metadata,
        "reference_outline_rule_id": rule.get("id"),
        "reference_outline_section_type": rule.get("section_type"),
        "reference_outline_generation_policy": rule.get("generation_policy"),
        "reference_outline_requires_table": bool(rule.get("requires_table")),
        "reference_outline_structured_data_required": bool(rule.get("structured_data_required")),
        "reference_outline_preferred_asset_evidence_types": list(rule.get("preferred_asset_evidence_types") or []),
    }
    notes = list(node.get("writing_notes") or [])
    if rule.get("requires_table"):
        notes.append("本节命中结构化参考模板规则，优先按招标文件原表式或结构化表格输出；缺失数据不得编造。")
    if rule.get("structured_data_required"):
        notes.append("本节需要结构化参数或证据数据支撑，正文生成前必须核对泰昌真实资料来源。")
    return {
        **node,
        "metadata": annotated_metadata,
        "writing_notes": notes,
    }


def _sanitize_supply_reference_chapters(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []

    def sanitize(node: dict[str, Any]) -> dict[str, Any] | None:
        title = str(node.get("title") or "")
        if any(term in title for term in SUPPLY_ONLY_FORBIDDEN_OUTLINE_TERMS):
            return None
        clean_node = {key: copy.deepcopy(value) for key, value in node.items() if key != "children"}
        children = [
            child
            for child in (sanitize(child) for child in node.get("children") or [] if isinstance(child, dict))
            if child
        ]
        if children:
            clean_node["children"] = children
        return clean_node

    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        clean_chapter = sanitize(chapter)
        if clean_chapter:
            sanitized.append(clean_chapter)
    return sanitized


def _reference_outline_rules_prompt(rule_sets: list[dict[str, Any]]) -> str:
    if not rule_sets:
        return ""
    lines = [
        "结构化参考模板规则 reference_outline_rules（受控低优先级提示，不得覆盖招标文件、客户确认章节或供货类门禁）：",
        "- 只可用于章节类型、表单/附件属性、目录层级和证据准备提示；不得从参考稿生成企业事实。",
        "- 不得新增超出本项目要求的大量附件章节；不得绕过供货类章节上限和禁用工程施工类章节规则。",
    ]
    for rules in rule_sets:
        scope = rules.get("scope") or "unknown_scope"
        section_titles: list[str] = []
        for section in rules.get("sections") or []:
            if not isinstance(section, dict):
                continue
            flags = []
            if section.get("requires_table"):
                flags.append("表格")
            if section.get("structured_data_required"):
                flags.append("需结构化数据")
            suffix = f"（{'、'.join(flags)}）" if flags else ""
            section_titles.append(f"{section.get('title')}{suffix}")
        if section_titles:
            lines.append(f"- {scope}：{'；'.join(section_titles)}。")
    return "\n".join(lines)


def _mark_container_chapter(chapter: dict[str, Any], child_count: int) -> dict[str, Any]:
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    plan = metadata.get("writing_plan") if isinstance(metadata.get("writing_plan"), dict) else build_chapter_writing_plan(chapter)
    container_plan = {
        **plan,
        "target_words": 0,
        "min_words": 0,
        "max_words": 0,
        "suggested_pages": "结构汇总",
        "generation_mode": "container",
        "strategy": "本章节作为结构容器，不直接调用模型生成正文；正文由下级叶子小节分别生成后按目录合并导出。",
    }
    return {
        **chapter,
        "content": "",
        "metadata": {
            **metadata,
            "section_role": "container",
            "leaf_generation": False,
            "leaf_split_child_count": child_count,
            "writing_plan": container_plan,
        },
    }


def _build_split_child(parent: dict[str, Any], child_index: int, child_count: int, topic: tuple[str, str]) -> dict[str, Any]:
    title, purpose = topic
    parent_title = parent.get("title") or "章节"
    parent_order = str(parent.get("order") or "")
    metadata = parent.get("metadata") if isinstance(parent.get("metadata"), dict) else {}
    inherited_notes = list(parent.get("writing_notes") or [])
    target_words = max(700, min(1400, int(round((_writing_plan_target_words(parent) or LEAF_SPLIT_TARGET_WORDS) / child_count / 50) * 50)))
    child = {
        "title": title,
        "purpose": purpose,
        "priority": parent.get("priority") or "medium",
        "order": f"{parent_order}.{child_index}",
        "level": min(int(parent.get("level") or 1) + 1, 5),
        "response_points": list(parent.get("response_points") or []),
        "mapped_requirements": list(parent.get("mapped_requirements") or []),
        "mapped_scoring_items": list(parent.get("mapped_scoring_items") or []),
        "mapped_risks": list(parent.get("mapped_risks") or []),
        "required_materials": list(parent.get("required_materials") or []),
        "source_pages": list(parent.get("source_pages") or []),
        "writing_notes": [
            *inherited_notes[:3],
            f"本小节由「{parent_title}」拆分生成，正文目标控制在 {target_words} 字以内，避免大章节长流卡死。",
        ],
        "metadata": {
            **metadata,
            "section_role": "leaf",
            "leaf_generation": True,
            "split_from_parent_title": parent_title,
            "split_parent_order": parent_order,
            "writing_plan": {
                **(metadata.get("writing_plan") if isinstance(metadata.get("writing_plan"), dict) else {}),
                "importance": parent.get("priority") or "medium",
                "min_words": max(500, int(target_words * 0.7)),
                "max_words": int(target_words * 1.25),
                "target_words": target_words,
                "suggested_pages": "1-2",
                "generation_mode": "single_pass",
                "strategy": f"围绕「{parent_title}」下的「{title}」独立成节生成，短段落、表格或清单优先，缺失事实信息使用【待补充】。",
            },
        },
    }
    return ensure_section_volume(child)


def _expand_large_leaf_sections(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    order_set = {str(item.get("order") or "") for item in chapters}
    for chapter in chapters:
        order = str(chapter.get("order") or "")
        if not order or _chapter_has_child(chapters, order):
            expanded.append(chapter)
            continue
        target_words = _writing_plan_target_words(chapter)
        if target_words < LEAF_SPLIT_THRESHOLD_WORDS:
            metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
            expanded.append({
                **chapter,
                "metadata": {
                    **metadata,
                    "section_role": metadata.get("section_role") or "leaf",
                    "leaf_generation": metadata.get("leaf_generation", True),
                },
            })
            continue
        child_count = max(2, min(LEAF_SPLIT_MAX_CHILDREN, (target_words + LEAF_SPLIT_TARGET_WORDS - 1) // LEAF_SPLIT_TARGET_WORDS))
        expanded.append(_mark_container_chapter(chapter, child_count))
        for child_index, topic in enumerate(_leaf_split_topics(str(chapter.get("title") or ""), child_count), start=1):
            child_order = f"{order}.{child_index}"
            if child_order in order_set:
                continue
            expanded.append(_build_split_child(chapter, child_index, child_count, topic))

    for index, chapter in enumerate(expanded, start=1):
        chapter["order_index"] = index
    return expanded


def _build_volume(
    volume_type: str,
    *,
    required: bool = True,
    basis: str | None = None,
    chapters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_type = normalize_volume_type(volume_type)
    return {
        "type": normalized_type,
        "name": volume_name(normalized_type),
        "required": required,
        "basis": basis or volume_description(normalized_type),
        "chapters": chapters or [],
    }


def _outline_chapters_from_volumes(volumes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """扁平化 volumes → chapters 列表。

    关键约束：扁平化顺序必须是"按 volumes 依次、每个 volume 内按 order_index"
    —— 即资格文件全部章节在前，商务文件紧接其后，再是技术标……不能按每个 volume
    的局部 order_index 合并排序，否则会出现各 volume 第 1 章交叉排列的 bug。
    """
    chapters: list[dict[str, Any]] = []
    root_offset = 0
    global_order_index = 0
    for volume in volumes:
        volume_type = normalize_volume_type(volume.get("type"))
        volume_title = _text(volume.get("name")) or volume_name(volume_type)
        volume_chapters = volume.get("chapters") if isinstance(volume.get("chapters"), list) else []
        local_chapters = _normalize_outline_chapters(
            volume_chapters,
            volume_type=volume_type,
            volume_name_override=volume_title,
        )
        local_roots = [
            chapter for chapter in local_chapters
            if "." not in str(chapter.get("order") or "")
        ]
        root_map: dict[str, str] = {}
        for root_index, root in enumerate(local_roots, start=1):
            old_root = str(root.get("order") or root_index)
            root_map[old_root] = str(root_offset + root_index)

        # 保持 volume 内部 order_index 递增的原始顺序（一级章节后紧跟其子章节）
        for chapter in local_chapters:
            old_order = str(chapter.get("order") or "")
            old_root, _, suffix = old_order.partition(".")
            new_root = root_map.get(old_root, str(root_offset + len(root_map) + 1))
            chapter["order"] = f"{new_root}.{suffix}" if suffix else new_root
            # 重新分配全局唯一递增的 order_index
            global_order_index += 1
            chapter["order_index"] = global_order_index
            chapters.append(chapter)
        root_offset += len(local_roots)
    return chapters


def _normalize_outline_structure(outline: dict[str, Any]) -> dict[str, Any]:
    """Return an outline that always has both business volumes and flat chapters."""
    raw_volumes = outline.get("volumes") if isinstance(outline.get("volumes"), list) else []
    normalized_volumes: list[dict[str, Any]] = []

    for raw_volume in raw_volumes:
        if not isinstance(raw_volume, dict):
            continue
        raw_chapters = raw_volume.get("chapters") if isinstance(raw_volume.get("chapters"), list) else []
        volume_type = normalize_volume_type(raw_volume.get("type"))
        normalized_volumes.append({
            **raw_volume,
            "type": volume_type,
            "name": raw_volume.get("name") or volume_name(volume_type),
            "required": bool(raw_volume.get("required", True)),
            "basis": raw_volume.get("basis") or volume_description(volume_type),
            "chapters": _normalize_outline_chapters(
                raw_chapters,
                volume_type=volume_type,
                volume_name_override=raw_volume.get("name") or volume_name(volume_type),
            ),
        })

    if normalized_volumes:
        flat_chapters = _outline_chapters_from_volumes(normalized_volumes)
    else:
        flat_chapters = _normalize_outline_chapters(outline.get("chapters") or [])
        by_volume: dict[str, list[dict[str, Any]]] = {item: [] for item in VOLUME_ORDER}
        for chapter in flat_chapters:
            by_volume.setdefault(infer_volume_type(chapter), []).append(chapter)
        normalized_volumes = [
            _build_volume(
                volume_type,
                required=bool(by_volume.get(volume_type)),
                basis="由历史 chapters 结构按章节标题、响应点和资料需求兼容推断。",
                chapters=by_volume.get(volume_type) or [],
            )
            for volume_type in VOLUME_ORDER
            if by_volume.get(volume_type)
        ]
        normalized_volumes = [
            {
                **volume,
                "chapters": _normalize_outline_chapters(
                    volume.get("chapters") or [],
                    volume_type=volume.get("type"),
                    volume_name_override=volume.get("name"),
                ),
            }
            for volume in normalized_volumes
        ]
        flat_chapters = _outline_chapters_from_volumes(normalized_volumes)

    if not outline.get("preserve_reference_structure") and outline.get("artifact_role") != "current_tender_project_skeleton":
        flat_chapters = _expand_large_leaf_sections(flat_chapters)

    for index, chapter in enumerate(flat_chapters, start=1):
        chapter["order_index"] = index

    return {
        **outline,
        "version": outline.get("version") or "ai-volume-v1",
        "volumes": normalized_volumes,
        "chapters": flat_chapters,
    }


def _is_supply_only_bid(payload: dict[str, Any]) -> bool:
    project = payload.get("project") if isinstance(payload.get("project"), dict) else {}
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    project_meta = analysis.get("project_meta") if isinstance(analysis.get("project_meta"), dict) else {}
    high_confidence_text = " ".join(
        str(value or "")
        for value in (
            project.get("project_name"),
            project.get("project_type"),
            project.get("project_no"),
            project_meta.get("project_name"),
            project_meta.get("document_type"),
            project_meta.get("tender_no"),
            analysis.get("summary"),
        )
    )
    text = json.dumps(payload, ensure_ascii=False)
    supply_terms = (
        "电缆保护管",
        "CPVC",
        "MPP",
        "架空绝缘导线",
        "绝缘导线",
        "导线",
        "物资采购",
        "物资协议库存",
        "协议库存",
        "货物清单",
        "供货要求",
    )
    construction_terms = ("施工总承包", "安装工程", "土建工程", "工程施工招标")
    if any(term in high_confidence_text for term in supply_terms):
        return not any(term in high_confidence_text for term in construction_terms)
    return any(term in text for term in supply_terms) and not any(term in text for term in construction_terms)


def _taichang_reference_template_hint() -> str:
    return """客户提供的河北豪乾同类标书仅作目录、格式和写法参考，禁止引用其企业事实。参考结构如下：
- 技术文件：技术偏差表；专项投标文件；业绩文件；技术特性参数表；货物组件材料配置表；符合投标人资格要求的证明文件；技术评分支撑材料。
- 商务文件：商务偏差表；投标保证资料；投标人基本情况表；营业执照；资格证明文件；信用查询报告及截图；补充文件。
- 正式内容必须全部替换为河北泰昌电力器材科技有限公司的真实资料；专利、供应商、人员、业绩和证书不得从河北豪乾参考稿继承。
- 格式来源优先级：本次招标文件明确格式 > 客户参考稿结构 > 系统默认模板。"""


def _clean_reference_toc_line(line: str) -> str:
    text = re.sub(r"\s+", " ", str(line or "")).strip()
    text = re.sub(r"^[\-\u2022]\s*", "", text)
    text = re.sub(r"^(?:\d+\s+)?目录\s*$", "", text)
    text = re.sub(r"^\d+\s+(?=\d+(?:\.\d+)+\.?\s*)", "", text)
    text = re.sub(r"(?:\s*[\.\u2026·]{2,}|\s+\.{2,}|\s+…+|\s+·{2,}).*$", "", text).strip()
    text = re.sub(r"\s+\d{1,4}$", "", text).strip()
    return text.strip(" -_")


def _reference_toc_level_and_title(line: str) -> tuple[int, str] | None:
    text = _clean_reference_toc_line(line)
    if not text:
        return None
    chinese = re.match(r"^（[一二三四五六七八九十]+）\s*(.+)$", text)
    if chinese:
        return 1, chinese.group(1).strip()
    number = re.match(r"^(\d+(?:\.\d+)*)\.?\s*(.+)$", text)
    if number:
        level = min(number.group(1).count(".") + 1, 4)
        return level, number.group(2).strip()
    code_like = re.match(r"^（[A-Z0-9][A-Z0-9\s\-_]+）$", text, flags=re.I)
    if code_like:
        return 3, "技术特性参数明细（按物料编码）"
    if len(text) >= 3:
        return 2, text
    return None


def _sanitize_reference_template_title(title: str) -> str:
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    text = re.sub(r"\s*[-_]\s*", "-", text)
    lowered = text.lower()
    if text.startswith("一种"):
        return "专利证书"
    if "国网辽宁电力" in text and re.search(r"20\d{2}", text):
        return "同类项目业绩证明材料"
    if "有限公司" in text and "资质文件" in text:
        return "原材料供应商资质文件"
    if "有限公司" in text:
        return "供应商及外协证明材料"
    if "一种" in text and ("专利" in text or "保护管" in text):
        return "专利证书"
    if "电缆保护管生产" in text and ("系统" in text or "平台" in text or "软件" in text):
        return "软件著作权登记证书"
    if "软件" in text and ("系统" in text or "平台" in text or "评估" in text):
        return "软件著作权登记证书"
    if re.match(r"^20\d{2}\s*年?审计报告$", text):
        return "近三年审计报告"
    if re.search(r"\b[A-Z]\d{2,}-\d", text) or re.match(r"^（?[A-Z0-9][A-Z0-9\s\-_]{8,}）?$", text, flags=re.I):
        return "技术特性参数明细（按物料编码）"
    if "cpvc" in lowered:
        text = re.sub("cpvc", "CPVC", text, flags=re.I)
    if "mpp" in lowered:
        text = re.sub("mpp", "MPP", text, flags=re.I)
    return text[:80]


def _reference_root_title(record: dict[str, Any]) -> tuple[str, str]:
    role = str(record.get("doc_role") or "")
    file_name = str(record.get("file_name") or record.get("source_file") or "")
    if "technical" in role or "技术" in file_name:
        return "技术响应文件", "technical"
    if "business" in role or "商务" in file_name or "winning_bid" in role:
        return "商务响应文件", "business"
    return "参考模板响应文件", "business"


def _make_reference_node(title: str, volume_type: str, *, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    child_nodes = children or []
    writing_plan = {
        "target_words": 0 if child_nodes else 900,
        "min_words": 0 if child_nodes else 450,
        "max_words": 0 if child_nodes else 1200,
        "suggested_pages": "结构汇总" if child_nodes else "1-2",
        "generation_mode": "container" if child_nodes else "single_pass",
        "strategy": "本章节来自客户参考稿目录结构，只复用目录/表式/写法，正文必须使用泰昌事实和本次招标要求。",
    }
    return {
        "title": title,
        "purpose": "参考客户同类标书目录组织本节，内容以泰昌事实和本次招标要求重写。",
        "priority": "high",
        "children": child_nodes,
        "metadata": {
            "volume_type": volume_type,
            "section_role": "container" if child_nodes else "leaf",
            "leaf_generation": not bool(child_nodes),
            "reference_template_source": "haoqian_toc_structure_only",
            "writing_plan": writing_plan,
            "generation_options": {
                "required_scope": "河北泰昌电力器材科技有限公司国家电网物资供货投标，范围为生产、检验、包装、运输、交付和售后服务。",
                "forbidden_topics": ["施工组织", "建造师", "安全生产许可证", "BIM", "水利施工", "安装总承包"],
                "allowed_placeholders": ["本次包号及包名称", "最终报价及税率", "投标保证金", "授权代表及签署日期", "最终交货期及质保期"],
            },
        },
    }


def _parse_reference_toc_lines(record: dict[str, Any], *, max_nodes: int = 45) -> dict[str, Any] | None:
    root_title, volume_type = _reference_root_title(record)
    root = _make_reference_node(root_title, volume_type, children=[])
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]
    seen_by_parent: dict[int, set[str]] = {}
    added = 0
    for raw_line in record.get("toc_lines") or []:
        parsed = _reference_toc_level_and_title(str(raw_line))
        if not parsed:
            continue
        level, raw_title = parsed
        title = _sanitize_reference_template_title(raw_title)
        if not title or title in {"目录", root_title}:
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else root
        parent_key = id(parent)
        seen_by_parent.setdefault(parent_key, set())
        if title in seen_by_parent[parent_key]:
            continue
        seen_by_parent[parent_key].add(title)
        node = _make_reference_node(title, volume_type, children=[])
        parent.setdefault("children", []).append(node)
        stack.append((level, node))
        added += 1
        if added >= max_nodes:
            break
    if not root.get("children"):
        return None
    _refresh_reference_container_metadata(root)
    return root


def _refresh_reference_container_metadata(node: dict[str, Any]) -> None:
    children = node.get("children") or []
    metadata = node.setdefault("metadata", {})
    metadata["section_role"] = "container" if children else "leaf"
    metadata["leaf_generation"] = not bool(children)
    writing_plan = metadata.setdefault("writing_plan", {})
    if children:
        writing_plan.update({
            "target_words": 0,
            "min_words": 0,
            "max_words": 0,
            "suggested_pages": "结构汇总",
            "generation_mode": "container",
        })
    for child in children:
        _refresh_reference_container_metadata(child)


def _reference_template_chapters_from_files() -> list[dict[str, Any]]:
    if not HAOQIAN_REFERENCE_TEMPLATE_PATH.exists():
        return []
    try:
        payload = json.loads(HAOQIAN_REFERENCE_TEMPLATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    records = payload.get("records") if isinstance(payload, dict) else []
    roots: list[dict[str, Any]] = []
    for record in records or []:
        if not isinstance(record, dict) or not record.get("reference_only"):
            continue
        root = _parse_reference_toc_lines(record)
        if root:
            roots.append(root)
    if sum(_count_outline_nodes(root) for root in roots) < 40:
        return []
    _merge_required_supply_sections(roots)
    roots.append(_make_reference_node("报价文件及货物清单", "price"))
    roots.append(_make_reference_node("附件清单及页码索引", "attachment"))
    return roots


def _merge_required_supply_sections(roots: list[dict[str, Any]]) -> None:
    existing_titles: set[str] = set()

    def collect(node: dict[str, Any]) -> None:
        existing_titles.add(str(node.get("title") or ""))
        for child in node.get("children") or []:
            collect(child)

    for root in roots:
        collect(root)

    for required_root in _supply_reference_base_chapters():
        title = str(required_root.get("title") or "")
        if title in {"报价文件及货物清单", "附件清单及页码索引"}:
            continue
        if title not in existing_titles:
            roots.insert(0, required_root)
            collect(required_root)
            continue
        if "技术" not in title:
            continue
        technical_root = next((root for root in roots if "技术" in str(root.get("title") or "")), None)
        if not technical_root:
            continue
        for child in required_root.get("children") or []:
            child_title = str(child.get("title") or "")
            if child_title not in existing_titles:
                technical_root.setdefault("children", []).append(child)
                collect(child)
        _refresh_reference_container_metadata(technical_root)


def _count_outline_nodes(node: dict[str, Any]) -> int:
    return 1 + sum(_count_outline_nodes(child) for child in node.get("children") or [])


def _outline_total_nodes(outline: dict[str, Any]) -> int:
    chapters = outline.get("chapters") if isinstance(outline.get("chapters"), list) else []
    if chapters:
        return len(chapters)
    volumes = outline.get("volumes") if isinstance(outline.get("volumes"), list) else []
    return sum(
        _count_outline_nodes(chapter)
        for volume in volumes
        if isinstance(volume, dict)
        for chapter in (volume.get("chapters") or [])
        if isinstance(chapter, dict)
    )


def _outline_forbidden_terms(outline: dict[str, Any]) -> list[str]:
    titles = " ".join(str(chapter.get("title") or "") for chapter in outline.get("chapters") or [])
    return [term for term in SUPPLY_ONLY_FORBIDDEN_OUTLINE_TERMS if term in titles]


def _supply_outline_reject_reason(
    outline: dict[str, Any],
    *,
    quick_chapters_count: int | None = None,
) -> str | None:
    node_count = _outline_total_nodes(outline)
    forbidden_terms = _outline_forbidden_terms(outline)
    if forbidden_terms:
        return "供货类大纲包含工程施工类章节：" + "、".join(forbidden_terms)
    if node_count > SUPPLY_ONLY_MAX_OUTLINE_NODES:
        return f"供货类大纲章节数 {node_count} 超过上限 {SUPPLY_ONLY_MAX_OUTLINE_NODES}"
    if quick_chapters_count and node_count > max(
        quick_chapters_count + 12,
        int(quick_chapters_count * SUPPLY_ONLY_AI_REFINEMENT_MAX_GROWTH),
    ):
        return f"后台精修章节数 {node_count} 相比快速大纲 {quick_chapters_count} 膨胀过多"
    return None


def _use_supply_fallback_outline(
    fallback_outline: dict[str, Any],
    reason: str,
    *,
    source_version: str | None = None,
) -> dict[str, Any]:
    guarded = {
        **fallback_outline,
        "version": "rule-v1-supply-guardrail",
        "preserve_reference_structure": True,
        "fallback_reason": reason,
        "rejected_ai_outline_version": source_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _normalize_outline_structure(guarded)


def _supply_reference_base_chapters() -> list[dict[str, Any]]:
    chapters = [
        {
            "title": "投标函及法定格式文件",
            "purpose": "严格采用招标文件规定格式，填写投标主体、包件、报价、授权和签章信息。",
            "priority": "high",
            "children": [
                {"title": "投标函及投标函附录", "purpose": "按招标文件原表式填写投标承诺和报价信息。", "priority": "high"},
                {"title": "法定代表人身份证明及授权委托书", "purpose": "使用泰昌真实法定代表人与客户确认的授权信息。", "priority": "high"},
                {"title": "投标保证金及基本账户资料", "purpose": "放置本项目确认后的保证金凭证和基本账户证明。", "priority": "high"},
            ],
        },
        {
            "title": "商务响应文件",
            "purpose": "参照客户同类商务标结构并逐条响应本次招标商务要求。",
            "priority": "high",
            "children": [
                {"title": "商务偏差表", "purpose": "按招标文件原表式填写商务偏差。", "priority": "high"},
                {"title": "投标人基本情况表", "purpose": "使用泰昌营业执照和企业事实填写。", "priority": "high"},
                {"title": "资格证明文件", "purpose": "归集泰昌营业执照、体系认证、资信和适用资格证明。", "priority": "high"},
                {"title": "信用查询报告及截图", "purpose": "归集本次投标要求的泰昌信用查询材料。", "priority": "medium"},
                {"title": "商务承诺及补充文件", "purpose": "响应交货、质保、售后、廉洁和保密等商务条款。", "priority": "high"},
            ],
        },
        {
            "title": "技术响应文件",
            "purpose": "围绕电缆保护管产品参数、生产检验、供货交付和售后服务响应技术要求。",
            "priority": "high",
            "children": [
                {"title": "技术偏差表", "purpose": "按技术规范逐项填写标准值、保证值和偏差。", "priority": "high"},
                {"title": "技术特性参数表", "purpose": "优先使用泰昌检验报告结构化参数并匹配本次规格。", "priority": "high"},
                {"title": "货物组件材料配置表", "purpose": "按本次货物清单和技术规范填写产品组成及原材料。", "priority": "high"},
                {"title": "产品制造与质量控制", "purpose": "说明CPVC/MPP生产、过程检验、出厂检验和质量追溯。", "priority": "high"},
                {"title": "供货组织与交付保障", "purpose": "说明备料、排产、包装、运输、交货和应急供货安排。", "priority": "high"},
                {"title": "售后服务与质量保证", "purpose": "说明质保、响应、问题处理和技术支持。", "priority": "high"},
            ],
        },
        {
            "title": "业绩文件",
            "purpose": "仅使用泰昌真实合同、中标通知书及可追溯业绩证明。",
            "priority": "high",
            "children": [
                {"title": "业绩汇总表", "purpose": "列示经结构化核验的泰昌同类产品业绩。", "priority": "high"},
                {"title": "合同及中标通知书", "purpose": "附泰昌真实合同关键页和中标通知书。", "priority": "high"},
            ],
        },
        {
            "title": "技术评分支撑材料",
            "purpose": "按本次评分办法归集泰昌已有且适用的产品、生产、检测、绿色低碳和创新证明。",
            "priority": "high",
        },
        {
            "title": "报价文件及货物清单",
            "purpose": "按招标文件原表式填写价格清单、数量、税率和总价，不由模型推断。",
            "priority": "high",
        },
        {
            "title": "附件清单及页码索引",
            "purpose": "汇总本次实际采用的泰昌证明文件并在定稿后回填页码。",
            "priority": "medium",
        },
    ]
    volume_types = ["business", "business", "technical", "qualification", "technical", "price", "attachment"]
    for chapter, volume_type in zip(chapters, volume_types, strict=True):
        stack = [chapter]
        while stack:
            item = stack.pop()
            children = item.get("children") or []
            if children:
                writing_plan = {
                    "target_words": 0,
                    "min_words": 0,
                    "max_words": 0,
                    "suggested_pages": "结构汇总",
                    "generation_mode": "container",
                    "strategy": "本章节作为客户范本结构容器，正文由下级小节生成。",
                }
            else:
                writing_plan = {
                    "target_words": 1200,
                    "min_words": 600,
                    "max_words": 1500,
                    "suggested_pages": "1-2",
                    "generation_mode": "single_pass",
                    "strategy": "按招标文件原格式和泰昌真实资料形成可直接复核的正文或表格。",
                }
            item["metadata"] = {
                **(item.get("metadata") or {}),
                "volume_type": volume_type,
                "section_role": "container" if children else "leaf",
                "leaf_generation": not bool(children),
                "writing_plan": writing_plan,
                "generation_options": {
                    "required_scope": "河北泰昌电力器材科技有限公司国家电网物资供货投标，范围为生产、检验、包装、运输、交付和售后服务。",
                    "forbidden_topics": ["施工组织", "建造师", "安全生产许可证", "BIM", "水利施工", "安装总承包"],
                    "allowed_placeholders": ["本次包号及包名称", "最终报价及税率", "投标保证金", "授权代表及签署日期", "最终交货期及质保期"],
                },
            }
            stack.extend(children)
    return chapters


def _build_rule_outline(payload: dict[str, Any]) -> dict[str, Any]:
    project = payload.get("project") or {}
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") or {}
    ai_report = project_meta.get("ai_report") or {}
    supply_only = _is_supply_only_bid(payload)
    reference_rule_sets = _reference_outline_rule_sets_for_supply_bid() if supply_only else []

    # 供货类项目只要已经具备当次招标文件结构化内容，就必须由当前项目规则
    # 决定目录。历史参考稿不再作为快速骨架来源，也不能因章节更多而覆盖它。
    if supply_only and has_current_tender_skeleton_inputs(payload):
        return _normalize_outline_structure(build_project_bid_skeleton(payload))

    base_chapters = [
        {
            "title": "投标函及格式文件",
            "purpose": "响应招标文件投标函、报价、工期、质量等基础承诺。",
            "priority": "high",
            "children": [
                {"title": "投标函及投标函附录", "purpose": "按招标文件格式填写投标报价、工期、质量目标、项目经理等基础承诺。", "priority": "high"},
                {"title": "法定代表人身份证明及授权委托书", "purpose": "放置法定代表人身份证明、授权委托书、被授权人身份证明等签章文件。", "priority": "high"},
                {"title": "投标保证金", "purpose": "按要求提供投标保证金凭证、保函或缴纳证明，并核对有效期。", "priority": "high"},
                {"title": "联合体协议及分包说明", "purpose": "如适用，响应联合体协议、牵头人、职责分工、拟分包事项。", "priority": "medium"},
            ],
        },
        {
            "title": "资格审查资料",
            "purpose": "集中放置营业执照、资质证书、安全生产许可、信誉声明、人员证书、业绩证明等材料。",
            "priority": "high",
            "children": [
                {"title": "企业基本资格资料", "purpose": "整理营业执照、资质证书、安全生产许可证、基本账户等资格资料。", "priority": "high"},
                {"title": "信誉与合规承诺", "purpose": "响应信用中国、失信被执行人、行贿犯罪记录、禁止投标情形等要求。", "priority": "high"},
                {"title": "类似项目业绩", "purpose": "整理类似项目合同、中标通知书、验收证明、业主证明和联合体业绩说明。", "priority": "high"},
                {"title": "项目管理机构", "purpose": "展示项目经理、技术负责人、质量、安全、施工和资料管理人员配置及证书。", "priority": "high"},
            ],
        },
        {
            "title": "商务响应文件",
            "purpose": "响应付款、合同、服务、税费、廉政、保密、农民工工资等商务条款。",
            "priority": "medium",
            "children": [
                {"title": "商务条款响应", "purpose": "逐条响应合同、付款、履约担保、工期、质量和服务承诺。", "priority": "medium"},
                {"title": "偏离表及承诺函", "purpose": "明确商务和技术条款无偏离或偏离说明，避免实质性不响应。", "priority": "high"},
                {"title": "中小企业及政策性文件", "purpose": "按项目属性提供中小企业声明、政府采购政策响应等文件。", "priority": "medium"},
            ],
        },
        {
            "title": "技术响应文件",
            "purpose": "围绕发包人要求、技术标准、实施组织、质量安全和交付保障形成技术方案。",
            "priority": "high",
            "children": [
                {"title": "发包人要求响应", "purpose": "逐条响应发包人要求、技术标准、工程范围和关键技术参数。", "priority": "high"},
                {"title": "承包人建议书", "purpose": "围绕设计优化、设备配置、施工组织、资源保障提出可执行建议。", "priority": "high"},
                {
                    "title": "施工组织设计/实施方案",
                    "purpose": "围绕施工部署、进度、质量、安全、环保、资源配置和关键工序组织形成方案。",
                    "priority": "high",
                    "children": [
                        {"title": "施工部署与资源配置", "purpose": "描述总体施工部署、人员设备投入和关键资源配置。", "priority": "high"},
                        {"title": "进度计划与节点控制", "purpose": "围绕里程碑节点、工期控制和赶工预案形成进度方案。", "priority": "high"},
                        {
                            "title": "质量安全环保措施",
                            "purpose": "专项响应质量控制、安全管理、文明施工和环境保护要求。",
                            "priority": "high",
                            "children": [
                                {"title": "质量控制措施", "purpose": "聚焦工艺控制、材料检验、过程验收和质量追溯。", "priority": "high"},
                                {"title": "安全生产措施", "purpose": "聚焦现场安全组织、危险源控制、应急演练和责任落实。", "priority": "high"},
                                {"title": "环保与文明施工措施", "purpose": "响应扬尘、噪声、废料回收、现场围挡和文明施工。", "priority": "medium"},
                            ],
                        },
                    ],
                },
                {"title": "质量、安全、进度保障措施", "purpose": "对评分项和履约风险做专项响应，突出过程控制、验收、应急和交付保障。", "priority": "medium"},
            ],
        },
        {
            "title": "报价文件及工程量清单",
            "purpose": "按招标文件格式组织报价、清单、单价分析和相关说明。",
            "priority": "high",
            "children": [
                {"title": "价格清单", "purpose": "按招标文件格式填报价格清单、分项报价和汇总报价。", "priority": "high"},
                {"title": "报价说明及风险提示", "purpose": "说明报价口径、税费、暂估价、风险范围和需人工复核事项。", "priority": "medium"},
            ],
        },
        {
            "title": "其他响应资料",
            "purpose": "放置招标文件要求的补充资料、承诺、证明和投标人认为需提供的资料。",
            "priority": "low",
            "children": [
                {"title": "其他证明材料", "purpose": "归集招标文件要求但不属于前述章节的证明、声明和附件。", "priority": "low"},
                {"title": "页码索引及附件清单", "purpose": "建立材料索引，便于评审查找和后续 Word 导出。", "priority": "low"},
            ],
        },
    ]
    if supply_only:
        base_chapters = _sanitize_supply_reference_chapters(
            _reference_template_chapters_from_files() or _supply_reference_base_chapters()
        )

    requirements = _dict_items(payload.get("requirements") or [])
    scoring_items = _dict_items(payload.get("scoringItems") or [])
    risks = _dict_items(payload.get("risks") or [])
    materials = _normalize_material_checklist(ai_report.get("material_checklist") or [])

    def enrich_node(node: dict[str, Any], level: int) -> dict[str, Any]:
        title = node.get("title") or "未命名章节"
        keyword = title[:4]
        mapped_requirements = [
            item.get("content") for item in requirements
            if item.get("content") and _contains_keyword(item, keyword, ["content", "source_section"])
        ][:5]
        mapped_scoring = [
            item.get("item") for item in scoring_items
            if item.get("item") and _contains_keyword(item, keyword, ["item", "source_section"])
        ][:4]
        mapped_risks = [
            item.get("content") for item in risks
            if item.get("content") and _contains_keyword(item, keyword, ["content", "source_section"])
        ][:4]
        source_pages = sorted({
            item.get("source_page")
            for item in [*requirements, *scoring_items, *risks]
            if item.get("source_page") and _contains_keyword(item, keyword, ["content", "item", "source_section"])
        })
        writing_notes = [
            "正文生成前先核对招标文件格式要求、签章要求和附件清单。" if level == 1 else "正文生成前先核对本节是否为招标文件指定格式或评分点。",
            "章节内容应保留页码索引，便于后续评审响应和人工复核。" if level <= 2 else "如涉及证书、金额、人员、日期，应使用【待补充】占位，禁止编造。",
        ]
        enriched = {
            "title": title,
            "priority": node.get("priority") or "medium",
            "purpose": node.get("purpose"),
            "response_points": mapped_requirements[:3] or (["需结合招标文件条款逐项响应，避免遗漏实质性要求。"] if level == 1 else ["围绕本节目标补充对应招标响应内容。"]),
            "mapped_requirements": mapped_requirements,
            "mapped_scoring_items": mapped_scoring,
            "mapped_risks": mapped_risks,
            "source_pages": source_pages[:8],
            "required_materials": [
                item.get("material") for item in materials
                if item.get("material") and (keyword in _text(item.get("material")) or title[:2] in _text(item.get("category")))
            ][:5],
            "writing_notes": writing_notes,
            "metadata": dict(node.get("metadata") or {}),
            "children": [enrich_node(child, min(level + 1, 4)) for child in node.get("children") or []],
        }
        return _annotate_reference_outline_rule(enriched, reference_rule_sets)

    chapters = _normalize_outline_chapters([enrich_node(node, 1) for node in base_chapters])

    return _normalize_outline_structure({
        "version": "rule-volume-v1",
        "preserve_reference_structure": supply_only,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_name": project_meta.get("project_name") or project.get("project_name"),
        "tender_no": project_meta.get("tender_no") or project.get("project_no"),
        "summary": "基于招标解读结果生成的分册化投标文件章节大纲，可作为后续正文生成和 Word 排版输入。",
        "chapters": chapters,
        "reference_outline_rules_integration": _reference_outline_rules_summary(reference_rule_sets) if reference_rule_sets else None,
        "next_steps": [
            "先人工确认章节是否覆盖招标文件格式和实质性条款。",
            "补齐企业资信、人员证书、业绩和产品资料后，再进入单章节正文生成。",
            "优先生成资格审查、技术参数响应、商务偏差和报价等高风险章节。",
        ],
    })


def _build_prompt(payload: dict[str, Any]) -> str:
    project = payload.get("project") or {}
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") or {}
    ai_report = project_meta.get("ai_report") or {}
    supply_only = _is_supply_only_bid(payload)
    reference_rule_sets = _reference_outline_rule_sets_for_supply_bid() if supply_only else []

    requirements = payload.get("requirements") or []
    scoring_items = payload.get("scoringItems") or []
    risks = payload.get("risks") or []

    scoring_count = len(scoring_items)
    requirement_count = len(requirements)
    risk_count = len(risks)

    scoring_by_category: dict[str, list[str]] = {}
    for item in scoring_items:
        cat = str(item.get("category") or "其他")
        scoring_by_category.setdefault(cat, []).append(str(item.get("item") or "")[:60])

    high_risks = [
        item for item in risks
        if str(item.get("risk_level") or "").lower() in {"high", "critical", "废标", "否决", "高"}
    ]

    knowledge_ctx = _fetch_knowledge_context(payload)

    rag_summary_lines: list[str] = []
    if knowledge_ctx["rag_snippets"]:
        rag_summary_lines.append("【企业知识库文档片段（可作为章节内容依据）】")
        for snippet in knowledge_ctx["rag_snippets"][:8]:
            rag_summary_lines.append(
                f"- [{snippet['category']}] {snippet['title']}：{snippet['content'][:120]}..."
            )

    asset_summary_lines: list[str] = []
    if knowledge_ctx["assets_summary"]:
        asset_summary_lines.append("【企业资产库（资质/产品/业绩，可作为章节内容和附件依据）】")
        for asset in knowledge_ctx["assets_summary"][:20]:
            tags_str = "、".join(asset["tags"]) if asset["tags"] else "无"
            sections_str = "、".join(asset["applicable_sections"]) if asset["applicable_sections"] else "未指定"
            asset_summary_lines.append(
                f"- [{asset['asset_type']}] {asset['title']}（分类：{asset['category']}；标签：{tags_str}；适用章节：{sections_str}）"
            )

    asset_hints: list[str] = []
    if knowledge_ctx["has_qualification_assets"]:
        titles = "、".join(knowledge_ctx["qualification_titles"][:6])
        asset_hints.append(
            f"企业资信库中已有以下资质/证书资产，资格文件分册应为每类资产单独设置章节：{titles or '（见资产库）'}"
        )
    if knowledge_ctx["has_product_assets"]:
        titles = "、".join(knowledge_ctx["product_titles"][:6])
        asset_hints.append(
            f"企业产品库中已有以下产品/设备资产，技术标中应为主要产品/设备设置专项技术响应章节：{titles or '（见产品库）'}"
        )
    if knowledge_ctx["has_case_assets"]:
        asset_hints.append(
            "企业资产库中有业绩/案例材料，资格文件分册应设置类似项目业绩章节，技术标中应设置类似工程经验章节。"
        )

    if supply_only:
        min_chapters_hint = min(max(24, scoring_count, requirement_count // 8), 45)
    else:
        min_chapters_hint = max(25, scoring_count * 2, requirement_count // 3)
        min_chapters_hint = min(min_chapters_hint, 80)

    context = {
        "project": {
            "project_name": project_meta.get("project_name") or project.get("project_name"),
            "tender_no": project_meta.get("tender_no") or project.get("project_no"),
            "summary": analysis.get("summary"),
            "ai_core_conclusion": (ai_report.get("project_brief") or {}).get("core_conclusion"),
        },
        "requirements": _compact_items(requirements, ["requirement_type", "priority", "content", "source_section", "source_page", "source_text"], 70),
        "risks": _compact_items(risks, ["risk_level", "risk_type", "content", "action", "source_section", "source_page", "source_text"], 50),
        "scoring_items": _compact_items(scoring_items, ["category", "item", "score", "requirement", "response_suggestion", "source_page", "source_text"], 45),
        "chapter_suggestions": _compact_items(payload.get("chapterSuggestions") or [], ["chapter_title", "priority", "reason"], 30),
        "ai_document_plan": ai_report.get("document_plan") or [],
        "ai_material_checklist": ai_report.get("material_checklist") or [],
    }

    knowledge_section = ""
    if rag_summary_lines or asset_summary_lines or asset_hints:
        knowledge_section = (
            "\n".join(rag_summary_lines) + "\n\n" +
            "\n".join(asset_summary_lines) + "\n\n" +
            "基于企业知识库的章节扩展要求：\n" +
            ("\n".join(f"- {hint}" for hint in asset_hints) if asset_hints else "- 暂无特殊扩展要求，按招标文件结构生成。")
        )

    scoring_breakdown = ""
    if scoring_by_category:
        lines = ["评分项分类明细（每个评分项必须有对应章节响应）："]
        for cat, items in scoring_by_category.items():
            lines.append(f"  [{cat}]：" + "；".join(items[:5]))
        scoring_breakdown = "\n".join(lines)

    high_risk_section = ""
    if high_risks:
        high_risk_section = "高风险/废标项（必须有专项章节响应，不得遗漏）：\n" + "\n".join(
            f"- [{item.get('risk_level')}] {item.get('content') or ''}" for item in high_risks[:10]
        )

    prompt_parts = [
        "你是资深国家电网物资投标文件编制负责人。请基于招标文件结构化解读和企业私有知识库，生成\"真实投标分册组成 + 各分册章节大纲\"。",
        "",
        "核心要求：",
        "1. 面向后续自动生成标书正文，不要写完整正文。",
        "2. 先判断本项目实际需要提交哪些投标文件分册，再分别生成分册章节。",
        "3. 分册 type 只能使用：qualification、business、technical、price、attachment、other。",
        "4. 章节必须覆盖所有评分项、资格要求、商务要求、技术要求、报价要求、格式文件和高风险项。",
        "5. 每个章节必须说明编写目标、响应点、关联要求、关联评分项、风险提醒、需要准备的资料、来源页码和写作注意事项。",
        "",
        f"章节数量规则（严格执行）：",
        f"- 本次招标共有 {scoring_count} 个评分项、{requirement_count} 个要求条款、{risk_count} 个风险项。",
        (
            f"- 当前为物资供货类投标，章节总数建议控制在 {min_chapters_hint} 个左右；"
            f"如参考模板章节较多，总数也不得超过 {SUPPLY_ONLY_MAX_OUTLINE_NODES} 个（含各级子章节）。"
            if supply_only
            else f"- 建议生成章节总数不少于 {min_chapters_hint} 个（含各级子章节）。"
        ),
        "- 每个评分项必须有至少一个对应章节或子章节明确响应，不得合并到笼统章节里。",
        "- 每个高风险/废标项必须有专项章节或子章节响应。",
        ("- 当前为国家电网物资供货项目，禁止生成施工组织设计、建造师、安全生产许可证、BIM、水利施工等工程承包内容；技术部分应展开产品参数、生产检验、供货交付、质量保证和售后服务。" if supply_only else "- 技术标中施工组织设计必须展开到三级，至少包含：总体部署、进度计划、质量控制、安全管理、环保文明施工、资源配置、关键工序专项方案等子章节。"),
        ("- 资格/商务/技术资料应按正式物资投标文件表式归类，不得把每个附件、证明截图或材料清单项都扩张成独立正文章节。" if supply_only else "- 资格文件分册必须为每类资质/证书/人员/业绩单独设置章节，不得合并为一个资格材料章节。"),
        "- 如果企业知识库中有产品/设备资产，技术标中必须为主要产品/设备设置专项技术参数响应章节。",
        "- 目录层级灵活：简单章节保留一级，复杂章节展开到二级、三级，必要时四级。",
        "- 不要编造招标文件没有的信息；无法确认的写需人工复核。",
    ]

    if supply_only:
        prompt_parts += [
            "",
            "客户同类标书范本约束（只借目录/格式/写法，不借企业事实）：",
            _taichang_reference_template_hint(),
        ]
        rules_prompt = _reference_outline_rules_prompt(reference_rule_sets)
        if rules_prompt:
            prompt_parts += ["", rules_prompt]

    if knowledge_section:
        prompt_parts += ["", "企业私有知识库上下文（必须结合以下信息生成章节）：", knowledge_section]
    if scoring_breakdown:
        prompt_parts += ["", scoring_breakdown]
    if high_risk_section:
        prompt_parts += ["", high_risk_section]

    prompt_parts += [
        "",
        "输出必须是严格 JSON，不要 Markdown，不要代码块。",
        "",
        '输出 JSON 格式：',
        '{',
        '  "version": "ai-volume-v1",',
        '  "project_name": "...",',
        '  "tender_no": "...",',
        '  "summary": "...",',
        '  "volumes": [',
        '    {',
        '      "type": "technical",',
        '      "name": "技术标",',
        '      "required": true,',
        '      "basis": "招标文件要求提交物资供货技术响应文件",',
        '      "chapters": [',
        '        {',
        '          "title": "...",',
        '          "priority": "high/medium/low",',
        '          "purpose": "...",',
        '          "response_points": ["..."],',
        '          "mapped_requirements": ["..."],',
        '          "mapped_scoring_items": ["..."],',
        '          "mapped_risks": ["..."],',
        '          "source_pages": [1, 2],',
        '          "required_materials": ["..."],',
        '          "writing_notes": ["..."],',
        '          "children": [{"title": "...", "priority": "high", "purpose": "...", "response_points": [], "mapped_requirements": [], "mapped_scoring_items": [], "mapped_risks": [], "source_pages": [], "required_materials": [], "writing_notes": [], "children": []}]',
        '        }',
        '      ]',
        '    }',
        '  ],',
        '  "chapters": [],',
        '  "next_steps": ["..."]',
        '}',
        "",
        "结构化招标信息：",
        json.dumps(context, ensure_ascii=False),
    ]

    return "\n".join(prompt_parts)


def _generate_outline_from_ai_or_rule(payload: dict[str, Any]) -> dict[str, Any]:
    fallback_outline = _build_rule_outline(payload)
    supply_only = _is_supply_only_bid(payload)
    material_scope = material_scope_from_context((payload.get("analysis") or {}).get("project_meta") or {}, payload.get("project") or {})

    def finalize_outline(outline: dict[str, Any]) -> dict[str, Any]:
        outline = prune_outline_by_material_scope(outline, material_scope)
        if material_scope:
            outline["material_scope"] = sorted(material_scope)
        outline["generated_at"] = datetime.now(timezone.utc).isoformat()
        return outline

    # P2-01 项目动态骨架是招标规则产物。AI 精修只能服务后续正文写作，不能
    # 增删或改写分册、条件状态和提交范围，因此此处直接返回确定性骨架。
    if fallback_outline.get("artifact_role") == "current_tender_project_skeleton":
        fallback_outline["model"] = "deterministic-current-tender-rules"
        return finalize_outline(fallback_outline)

    try:
        prompt = _build_prompt(payload)
        project = payload.get("project") or {}
        response = call_dashscope_api(
            [{"role": "user", "content": prompt}],
            model=get_stage_model("outline"),
            json_mode=True,
            usage_context={
                "project_id": project.get("id"),
                "stage": "bid_outline_generation",
            },
        )
        content = response["output"]["choices"][0]["message"]["content"]
        ai_outline = strip_llm_json(content)
    except Exception as exc:
        ai_outline = fallback_outline
        ai_outline["version"] = "rule-v1-fallback"
        ai_outline["fallback_reason"] = f"AI 章节大纲生成失败，已使用规则版大纲: {exc}"
        return finalize_outline(ai_outline)

    has_volumes = isinstance(ai_outline.get("volumes"), list) and any(
        isinstance(volume, dict) and isinstance(volume.get("chapters"), list) and volume.get("chapters")
        for volume in ai_outline.get("volumes") or []
    )
    has_chapters = isinstance(ai_outline.get("chapters"), list) and bool(ai_outline.get("chapters"))
    if not has_volumes and not has_chapters:
        ai_outline = fallback_outline
        ai_outline["version"] = "rule-v1-fallback"
        ai_outline["fallback_reason"] = "AI 返回结果缺少 volumes[].chapters 或 chapters，已使用规则版分册大纲。"
        return finalize_outline(ai_outline)

    if supply_only:
        ai_outline["preserve_reference_structure"] = True
    ai_outline = _normalize_outline_structure(ai_outline)
    if supply_only:
        reject_reason = _supply_outline_reject_reason(ai_outline)
        if reject_reason:
            return finalize_outline(_use_supply_fallback_outline(
                fallback_outline,
                f"{reject_reason}，已保留客户范本/规则版供货类大纲。",
                source_version=str(ai_outline.get("version") or "ai-v1"),
            ))
    ai_outline["version"] = ai_outline.get("version") or "ai-v1"
    ai_outline = finalize_outline(ai_outline)
    if "model" not in ai_outline:
        ai_outline["model"] = locals().get("response", {}).get("model") or "dashscope"
    return ai_outline


def generate_bid_outline(project_id: str) -> dict[str, Any]:
    payload = get_project_interpretation(project_id)
    analysis = payload.get("analysis")
    if not analysis:
        raise RuntimeError("当前项目尚无结构化解读数据，请先完成招标文件解析和落库。")

    ai_outline = _generate_outline_from_ai_or_rule(payload)

    project_meta = _latest_project_meta(project_id, analysis)
    project_meta["outline_locked"] = False
    project_meta["bid_outline"] = ai_outline

    updated = (
        get_supabase_client()
        .table("bid_analysis")
        .update({"project_meta": project_meta})
        .eq("id", analysis["id"])
        .execute()
    )
    if not updated.data:
        raise RuntimeError("标书章节大纲写回 Supabase 失败")
    replace_bid_sections_from_outline(project_id, ai_outline)

    return ai_outline


def save_bid_outline(project_id: str, outline: dict[str, Any], analysis: dict[str, Any]) -> None:
    project_meta = _latest_project_meta(project_id, analysis)
    project_meta["bid_outline"] = outline

    updated = (
        get_supabase_client()
        .table("bid_analysis")
        .update({"project_meta": project_meta})
        .eq("id", analysis["id"])
        .execute()
    )
    if not updated.data:
        raise RuntimeError("标书章节大纲写回 Supabase 失败")


def _latest_project_meta(project_id: str, analysis: dict[str, Any]) -> dict[str, Any]:
    rows = (
        get_supabase_client()
        .table("bid_analysis")
        .select("project_meta")
        .eq("project_id", project_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if rows:
        return dict(rows[0].get("project_meta") or {})
    return dict(analysis.get("project_meta") or {})


def _stream_ordered_chapters(chapters: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    roots = [chapter for chapter in chapters if "." not in str(chapter.get("order") or "")]
    descendants_by_root: dict[str, list[dict[str, Any]]] = {}
    for chapter in chapters:
        order = str(chapter.get("order") or "")
        if "." not in order:
            continue
        root_key = order.split(".", 1)[0]
        descendants_by_root.setdefault(root_key, []).append(chapter)

    for chapter in roots:
        yield chapter

    for root in roots:
        root_key = str(root.get("order") or "")
        for child in descendants_by_root.get(root_key, []):
            yield child


def _refine_bid_outline_in_background(project_id: str, payload: dict[str, Any], analysis: dict[str, Any]) -> None:
    """
    后台任务：调用 AI 生成精细化大纲，完成后写回 Supabase/PostgreSQL。
    前端通过 reloadProject() 轮询最新章节来感知更新。
    """
    try:
        quick_chapters_count = len(
            (analysis.get("project_meta") or {}).get("bid_outline", {}).get("chapters") or []
        )
        ai_outline = _generate_outline_from_ai_or_rule(payload)
        ai_chapters = ai_outline.get("chapters") or []
        if _is_supply_only_bid(payload):
            reject_reason = _supply_outline_reject_reason(ai_outline, quick_chapters_count=quick_chapters_count)
            if reject_reason:
                logging.warning(
                    "后台 AI 供货类大纲被门禁拒绝，保留快速大纲: %s project=%s",
                    reject_reason, project_id,
                )
                return
        # 只有 AI 版章节数量不少于规则版时才替换，防止 AI 退化
        if len(ai_chapters) >= max(quick_chapters_count, 1):
            save_bid_outline(project_id, ai_outline, analysis)
            replace_bid_sections_from_outline(project_id, ai_outline)
            logging.info(
                "后台 AI 精细化大纲完成，章节数 %d（规则版 %d）: %s",
                len(ai_chapters), quick_chapters_count, project_id,
            )
        else:
            logging.warning(
                "后台 AI 大纲章节数（%d）少于规则版（%d），保留规则版: %s",
                len(ai_chapters), quick_chapters_count, project_id,
            )
    except Exception:
        logging.exception("后台 AI 复核标书章节大纲失败: %s", project_id)


def stream_bid_outline(project_id: str) -> Iterator[dict[str, Any]]:
    payload = get_project_interpretation(project_id)
    analysis = payload.get("analysis")
    if not analysis:
        raise RuntimeError("当前项目尚无结构化解读数据，请先完成招标文件解析和落库。")

    # 用户显式重新生成大纲是"重建目录"的主动操作：先解锁，允许本次覆盖与后台精修。
    try:
        from backend.db.supabase_repo import set_outline_lock
        set_outline_lock(project_id, False)
    except Exception:
        logging.exception("重置大纲锁定状态失败（不阻断生成）: %s", project_id)

    yield {
        "type": "start",
        "message": "正在依据当次招标文件核定分册、提交范围和章节状态。",
    }

    # ── 第一阶段：规则版快速骨架（秒级，立即展示）──────────────────────────
    quick_outline = _build_rule_outline(payload)
    quick_chapters = quick_outline.get("chapters") or []
    quick_root_count = sum(1 for chapter in quick_chapters if "." not in str(chapter.get("order") or ""))

    yield {
        "type": "meta",
        "outline": {key: value for key, value in quick_outline.items() if key != "chapters"},
        "total": len(quick_chapters),
        "rootTotal": quick_root_count,
        "phase": "quick",
    }

    yield {
        "type": "stage",
        "stage": "roots",
        "message": f"已生成当次招标项目目录，共 {quick_root_count} 个一级章节，正在逐章展开。",
    }

    yielded = 0
    quick_root_titles = {
        str(chapter.get("order") or ""): chapter.get("title")
        for chapter in quick_chapters
        if "." not in str(chapter.get("order") or "")
    }
    for chapter in _stream_ordered_chapters(quick_chapters):
        yielded += 1
        if (chapter.get("level") or 1) == 2:
            root_order = str(chapter.get("order") or "").split(".", 1)[0]
            yield {
                "type": "stage",
                "stage": "children",
                "message": f"正在补充「{quick_root_titles.get(root_order) or root_order}」下的子章节。",
                "chapter": {
                    "order": chapter.get("order"),
                    "title": chapter.get("title"),
                    "rootOrder": root_order,
                    "rootTitle": quick_root_titles.get(root_order),
                },
            }
        yield {
            "type": "chapter",
            "index": yielded,
            "total": len(quick_chapters),
            "phase": "quick",
            "chapter": chapter,
        }
        time.sleep(0.03 if (chapter.get("level") or 1) == 1 else 0.05)

    save_bid_outline(project_id, quick_outline, analysis)
    replace_bid_sections_from_outline(project_id, quick_outline)

    yield {
        "type": "stage",
        "stage": "done",
        "message": "快速章节大纲已生成，AI 将在后台结合招标评分项和企业知识库继续优化，完成后自动刷新。",
    }

    # ── 第二阶段：AI 精细化大纲（Celery 后台任务，不阻塞 SSE 连接）────────
    # 把规则版章节数写入 analysis 供后台任务判断是否需要替换
    analysis_with_quick = {
        **analysis,
        "project_meta": {
            **(analysis.get("project_meta") or {}),
            "bid_outline": quick_outline,
        },
    }
    from backend.tasks.outline_tasks import refine_bid_outline

    refine_bid_outline.delay(project_id, payload, analysis_with_quick)

    yield {
        "type": "done",
        "outline": quick_outline,
        "backgroundRefining": True,
    }

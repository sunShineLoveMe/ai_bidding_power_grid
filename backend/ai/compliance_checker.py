import re
from typing import Any

from backend.core.bid_volumes import VOLUME_ORDER, delivery_volume_type, normalize_volume_type, section_volume_type, volume_name
from backend.db.supabase_repo import get_project_interpretation

GENERIC_TERMS = {
    "招标文件",
    "投标文件",
    "投标人",
    "招标人",
    "本项目",
    "本工程",
    "工程项目",
    "施工工程",
    "相关要求",
    "符合要求",
    "满足要求",
    "按照要求",
    "进行响应",
}
TECHNICAL_HINTS = {
    "施工",
    "组织设计",
    "技术",
    "方案",
    "工艺",
    "质量",
    "安全",
    "环保",
    "进度",
    "资源",
    "设备",
    "材料",
    "人员配置",
    "临时工程",
    "测量",
    "试验",
    "验收",
    "防渗",
    "灌浆",
    "导流",
    "水土保持",
}
BUSINESS_HINTS = {
    "资格",
    "资质",
    "证书",
    "业绩",
    "财务",
    "信誉",
    "投标函",
    "授权",
    "商务",
    "合同",
    "偏离",
    "承诺",
    "报价",
    "保证金",
    "保函",
    "营业执照",
    "安全生产许可证",
    "项目经理",
    "附件",
    "签章",
    "盖章",
}


def _normalize(value: Any) -> str:
    return str(value or "").replace(" ", "").replace("\n", "").replace("\t", "").lower()


def _meaningful(value: str, length: int = 8) -> bool:
    return len(value) >= length


def _mapped_values(section: dict[str, Any], field: str) -> list[str]:
    values = section.get(field) or []
    if not isinstance(values, list):
        return []
    return [_normalize(value) for value in values if value]


def _keyword_terms(value: str) -> set[str]:
    text = str(value or "")
    terms: set[str] = set()
    for segment in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text):
        normalized = _normalize(segment)
        if len(normalized) < 3 or normalized in GENERIC_TERMS:
            continue
        if len(normalized) <= 8:
            terms.add(normalized)
            continue
        for size in (6, 5, 4, 3):
            for index in range(0, len(normalized) - size + 1):
                term = normalized[index:index + size]
                if term not in GENERIC_TERMS:
                    terms.add(term)
            if len(terms) >= 80:
                return terms
    return terms


def _section_text(section: dict[str, Any], mapped_field: str) -> str:
    mapped = " ".join(_mapped_values(section, mapped_field))
    return _normalize(
        " ".join([
            str(section.get("title") or ""),
            str(section.get("purpose") or ""),
            str(section.get("content") or ""),
            mapped,
        ])
    )


def _content_response_matched(target: str, section_text: str, check_type: str) -> bool:
    if not _meaningful(section_text, 80):
        return False
    terms = _keyword_terms(target)
    if len(terms) < 3:
        return False
    matched = [term for term in terms if term in section_text]
    ratio = len(matched) / len(terms)
    if check_type == "scoring":
        return len(matched) >= 3 or ratio >= 0.16
    if check_type == "risk":
        return len(matched) >= 4 and ratio >= 0.2
    return len(matched) >= 4 and ratio >= 0.18


def _section_keyword_score(content: str, section: dict[str, Any], mapped_field: str) -> float:
    section_text = _section_text(section, mapped_field)
    if not _meaningful(section_text, 20):
        return 0
    terms = _keyword_terms(content)
    if not terms:
        return 0
    matched = [term for term in terms if term in section_text]
    title = _normalize(section.get("title"))
    title_hits = sum(1 for term in terms if term in title)
    return len(matched) + title_hits * 1.5 + (len(matched) / len(terms))


def _suggest_section(content: str, sections: list[dict[str, Any]], check_type: str) -> dict[str, Any] | None:
    mapped_field = {
        "requirement": "mapped_requirements",
        "scoring": "mapped_scoring_items",
        "risk": "mapped_risks",
    }[check_type]
    best_section = None
    best_score = 0.0
    for section in sections:
        score = _section_keyword_score(content, section, mapped_field)
        if score > best_score:
            best_section = section
            best_score = score
    return best_section if best_score >= 2 else None


def _match_section(content: str, sections: list[dict[str, Any]], check_type: str) -> dict[str, Any] | None:
    target = _normalize(content)
    mapped_field = {
        "requirement": "mapped_requirements",
        "scoring": "mapped_scoring_items",
        "risk": "mapped_risks",
    }[check_type]

    for section in sections:
        mapped_matched = any(
            _meaningful(value) and (value in target or target[:60] in value)
            for value in _mapped_values(section, mapped_field)
        )
        title = _normalize(section.get("title"))
        title_matched = _meaningful(title) and (title in target or target[:16] in title)
        section_text = _section_text(section, mapped_field)
        exact_content_matched = _meaningful(target) and target[:40] in section_text
        semantic_content_matched = _content_response_matched(content, section_text, check_type)
        if mapped_matched or title_matched or exact_content_matched or semantic_content_matched:
            return section
    return None


def _infer_internal_volume_for_item(content: str, fallback: str = "business") -> str:
    normalized = _normalize(content)
    if any(term in normalized for term in {"报价", "清单", "单价", "工程量", "投标总价", "分项报价"}):
        return "price"
    if any(term in normalized for term in {"附件", "扫描件", "图纸", "附录", "图片", "证明材料"}):
        return "attachment"
    if any(term in normalized for term in {"资格", "资质", "证书", "营业执照", "安全生产许可证", "项目经理", "人员", "业绩", "信誉", "社保"}):
        return "qualification"
    technical_score = sum(1 for term in TECHNICAL_HINTS if term in normalized)
    business_score = sum(1 for term in BUSINESS_HINTS if term in normalized)
    if technical_score > business_score:
        return "technical"
    if business_score > technical_score:
        return "business"
    return fallback


def _row_matches_volume(row: dict[str, Any], volume_type: str | None) -> bool:
    if volume_type is None:
        return True
    if volume_type == "business":
        return row.get("deliveryVolumeType") == "business"
    return row.get("volumeType") == volume_type


def _summary_from_rows(rows: list[dict[str, Any]], *, volume_type: str | None = None, volume_name_value: str | None = None) -> dict[str, Any]:
    total = len(rows)
    covered = sum(1 for row in rows if row["status"] == "covered")
    partial = sum(1 for row in rows if row["status"] == "partial")
    missing = sum(1 for row in rows if row["status"] == "missing")
    percent = round(((covered + partial * 0.5) / total) * 100) if total else 0
    missing_rows = [row for row in rows if row["status"] == "missing"]
    high_risk_missing = [
        row for row in missing_rows
        if row["category"] == "风险项" or str(row.get("importance")).lower() in {"high", "red", "否决", "废标"}
    ]
    return {
        "volumeType": volume_type or "all",
        "volumeName": volume_name_value or (volume_name(volume_type) if volume_type else "完整投标文件"),
        "total": total,
        "covered": covered,
        "partial": partial,
        "missing": missing,
        "percent": percent,
        "highRiskMissing": len(high_risk_missing),
    }


def _row(
    *,
    row_id: str,
    category: str,
    importance: str,
    content: str,
    status: str,
    section: dict[str, Any] | None,
    source_page: int | None,
    source_text: str | None,
    volume_type: str,
    suggested_section: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": row_id,
        "category": category,
        "importance": importance,
        "content": content,
        "status": status,
        "matchedChapter": section.get("title") if section else None,
        "matchedChapterId": section.get("id") if section else None,
        "suggestedChapter": (suggested_section or section or {}).get("title"),
        "suggestedChapterId": (suggested_section or section or {}).get("id"),
        "sourcePage": source_page,
        "sourceText": source_text or content,
        "volumeType": volume_type,
        "volumeName": volume_name(volume_type),
        "deliveryVolumeType": "technical" if volume_type == "technical" else "business",
        "deliveryVolumeName": "技术标" if volume_type == "technical" else "商务标",
    }


def build_compliance_report(project_id: str, volume_type: str | None = None) -> dict[str, Any]:
    payload = get_project_interpretation(project_id)
    project = payload.get("project")
    sections = payload.get("sections") or []
    normalized_volume_type = normalize_volume_type(volume_type) if volume_type else None
    if normalized_volume_type == "other":
        normalized_volume_type = None

    def scoped_sections_for(item_volume_type: str | None = None) -> list[dict[str, Any]]:
        scope = normalized_volume_type or item_volume_type
        if not scope:
            return sections
        if scope == "business":
            return [section for section in sections if delivery_volume_type(section) == "business"]
        return [section for section in sections if section_volume_type(section) == scope]

    rows_all: list[dict[str, Any]] = []

    for item in payload.get("requirements") or []:
        content = item.get("content") or item.get("title") or ""
        if not content:
            continue
        inferred_volume_type = _infer_internal_volume_for_item(
            content,
            fallback="business" if item.get("requirement_type") in {"qualification", "business", "price"} else "technical",
        )
        scoped_sections = scoped_sections_for(inferred_volume_type)
        section = _match_section(content, scoped_sections, "requirement")
        suggested_section = section or _suggest_section(content, scoped_sections, "requirement")
        item_volume_type = section_volume_type(section) if section else inferred_volume_type
        row = _row(
            row_id=f"requirement-{item.get('id')}",
            category="要求条款",
            importance=item.get("priority") or item.get("requirement_type") or "medium",
            content=content,
            status="covered" if section else "missing",
            section=section,
            source_page=item.get("source_page"),
            source_text=item.get("source_text") or item.get("content"),
            volume_type=item_volume_type,
            suggested_section=suggested_section,
        )
        rows_all.append(row)

    for item in payload.get("scoringItems") or []:
        content = item.get("item") or item.get("requirement") or ""
        if not content:
            continue
        inferred_volume_type = _infer_internal_volume_for_item(
            f"{item.get('category') or ''} {content}",
            fallback="technical",
        )
        scoped_sections = scoped_sections_for(inferred_volume_type)
        section = _match_section(content, scoped_sections, "scoring")
        suggested_section = section or _suggest_section(content, scoped_sections, "scoring")
        item_volume_type = section_volume_type(section) if section else inferred_volume_type
        row = _row(
            row_id=f"scoring-{item.get('id')}",
            category="评分项",
            importance=f"{item.get('score')}分" if item.get("score") else item.get("category") or "medium",
            content=content,
            status="covered" if section else "partial",
            section=section,
            source_page=item.get("source_page"),
            source_text=item.get("source_text") or item.get("requirement") or item.get("item"),
            volume_type=item_volume_type,
            suggested_section=suggested_section,
        )
        rows_all.append(row)

    for item in payload.get("risks") or []:
        content = item.get("content") or ""
        if not content:
            continue
        inferred_volume_type = _infer_internal_volume_for_item(content, fallback="business")
        scoped_sections = scoped_sections_for(inferred_volume_type)
        section = _match_section(content, scoped_sections, "risk")
        suggested_section = section or _suggest_section(content, scoped_sections, "risk")
        item_volume_type = section_volume_type(section) if section else inferred_volume_type
        row = _row(
            row_id=f"risk-{item.get('id')}",
            category="风险项",
            importance=item.get("risk_level") or item.get("risk_type") or "medium",
            content=content,
            status="covered" if section else "missing",
            section=section,
            source_page=item.get("source_page"),
            source_text=item.get("source_text") or item.get("content"),
            volume_type=item_volume_type,
            suggested_section=suggested_section,
        )
        rows_all.append(row)

    rows = [row for row in rows_all if _row_matches_volume(row, normalized_volume_type)]
    display_volume_name = None
    if normalized_volume_type == "business":
        display_volume_name = "商务标"
    elif normalized_volume_type:
        display_volume_name = volume_name(normalized_volume_type)
    summary_base = _summary_from_rows(rows, volume_type=normalized_volume_type, volume_name_value=display_volume_name)

    volume_summaries = []
    for item in VOLUME_ORDER:
        scoped_rows = [row for row in rows_all if row.get("volumeType") == item]
        if scoped_rows or item in {"technical", "business", "qualification", "price", "attachment"}:
            volume_summaries.append(_summary_from_rows(scoped_rows, volume_type=item, volume_name_value=volume_name(item)))

    missing = summary_base["missing"]
    partial = summary_base["partial"]

    recommendations = []
    if missing:
        recommendations.append("该指标为条款响应追踪，不等同于最终 Word 合规结论；建议优先补齐未响应的资格要求、否决风险和强制性条款。")
    if partial:
        recommendations.append("评分项中“待补强”的内容建议补充证明材料、页码索引和可量化承诺。")
    if not scoped_sections_for():
        recommendations.append("当前尚未生成标书章节大纲，请先生成章节大纲后再执行覆盖检查。")
    if not recommendations:
        recommendations.append("当前章节已覆盖主要解析项，建议继续做正文质量、格式和附件完整性复核。")

    return {
        "projectId": project_id,
        "projectName": project.get("project_name") if project else None,
        "summary": {
            "metricName": "条款响应覆盖率",
            "scopeNote": f"当前按{display_volume_name or '完整投标文件'}统计；基于招标条款、评分项、风险项与当前章节映射/正文片段的响应追踪结果，不等同于最终 Word 标书合规结论。",
            **summary_base,
        },
        "volumeSummaries": volume_summaries,
        "rows": rows,
        "recommendations": recommendations,
    }

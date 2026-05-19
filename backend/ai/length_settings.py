from __future__ import annotations

from typing import Any

from backend.ai.bid_writing_plan import build_chapter_writing_plan
from backend.core.bid_volumes import delivery_volume_type, section_volume_type


WORDS_PER_PAGE = {
    "technical": 700,
    "business": 550,
}

DEFAULT_LENGTH_SETTINGS = {
    "mode": "pages",
    "technicalPages": 80,
    "businessPages": 40,
    "technicalWords": 56000,
    "businessWords": 22000,
    "allowAutoExpand": False,
}

BUSINESS_LIMITED_INTERNAL_VOLUMES = {"qualification", "price", "attachment"}
LIMITED_VOLUME_WORD_CAP = {
    "qualification": 1800,
    "price": 900,
    "attachment": 900,
}


def _as_positive_int(value: Any, fallback: int, *, minimum: int = 1, maximum: int = 500000) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(number, maximum))


def normalize_length_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    mode = str(payload.get("mode") or DEFAULT_LENGTH_SETTINGS["mode"]).strip()
    if mode not in {"pages", "words"}:
        mode = "pages"

    technical_pages = _as_positive_int(payload.get("technicalPages"), DEFAULT_LENGTH_SETTINGS["technicalPages"], maximum=600)
    business_pages = _as_positive_int(payload.get("businessPages"), DEFAULT_LENGTH_SETTINGS["businessPages"], maximum=600)
    technical_words = _as_positive_int(payload.get("technicalWords"), DEFAULT_LENGTH_SETTINGS["technicalWords"])
    business_words = _as_positive_int(payload.get("businessWords"), DEFAULT_LENGTH_SETTINGS["businessWords"])

    if mode == "pages":
        technical_words = technical_pages * WORDS_PER_PAGE["technical"]
        business_words = business_pages * WORDS_PER_PAGE["business"]
    else:
        technical_pages = max(1, round(technical_words / WORDS_PER_PAGE["technical"]))
        business_pages = max(1, round(business_words / WORDS_PER_PAGE["business"]))

    return {
        "mode": mode,
        "technicalPages": technical_pages,
        "businessPages": business_pages,
        "technicalWords": technical_words,
        "businessWords": business_words,
        "allowAutoExpand": bool(payload.get("allowAutoExpand", DEFAULT_LENGTH_SETTINGS["allowAutoExpand"])),
    }


def _chapter_weight(chapter: dict[str, Any]) -> float:
    plan = build_chapter_writing_plan(chapter)
    weight = 1.0
    if plan.get("importance") == "high":
        weight += 1.2
    elif plan.get("importance") == "medium":
        weight += 0.5
    weight += min(len(chapter.get("mapped_scoring_items") or []), 4) * 0.35
    weight += min(len(chapter.get("mapped_requirements") or []), 5) * 0.2
    weight += min(len(chapter.get("mapped_risks") or []), 3) * 0.25
    if (chapter.get("level") or 1) <= 2:
        weight += 0.35
    if section_volume_type(chapter) in BUSINESS_LIMITED_INTERNAL_VOLUMES:
        weight *= 0.55
    return max(weight, 0.5)


def evaluate_length_feasibility(settings: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
    technical_sections = [section for section in sections if delivery_volume_type(section) == "technical"]
    business_sections = [section for section in sections if delivery_volume_type(section) == "business"]

    recommended_technical_pages = max(20, min(180, len(technical_sections) * 7))
    recommended_business_pages = max(12, min(120, len(business_sections) * 3))
    warnings: list[str] = []

    if settings["technicalPages"] > max(120, recommended_technical_pages * 1.5):
        warnings.append(
            f"技术标目标 {settings['technicalPages']} 页已明显高于当前目录和资料支撑建议值 {recommended_technical_pages} 页左右，建议补充专项方案、设备参数、进度资源和质量安全证明材料后再扩写。"
        )
    if settings["businessPages"] > max(80, recommended_business_pages * 1.6):
        warnings.append(
            f"商务标目标 {settings['businessPages']} 页已明显高于当前商务/资格/报价材料建议值 {recommended_business_pages} 页左右，系统会限制资格、报价和附件类章节的空泛扩写。"
        )
    if settings["technicalPages"] + settings["businessPages"] >= 300:
        warnings.append("总目标页数达到 300 页以上，建议拆分为多轮生成和人工复核，避免一次性生成造成重复、泛化或证据不足。")

    return {
        "level": "warning" if warnings else "ok",
        "recommendedTechnicalPages": recommended_technical_pages,
        "recommendedBusinessPages": recommended_business_pages,
        "warnings": warnings,
    }


def allocate_chapter_length_targets(sections: list[dict[str, Any]], settings: dict[str, Any]) -> list[dict[str, Any]]:
    grouped = {
        "technical": [section for section in sections if delivery_volume_type(section) == "technical"],
        "business": [section for section in sections if delivery_volume_type(section) == "business"],
    }
    target_totals = {
        "technical": settings["technicalWords"],
        "business": settings["businessWords"],
    }
    allocations: dict[str, int] = {}

    for group, group_sections in grouped.items():
        if not group_sections:
            continue
        weights = {section["id"]: _chapter_weight(section) for section in group_sections if section.get("id")}
        total_weight = sum(weights.values()) or len(group_sections)
        for section in group_sections:
            section_id = section.get("id")
            if not section_id:
                continue
            target_words = int(round((target_totals[group] * (weights[section_id] / total_weight)) / 50) * 50)
            internal_volume = section_volume_type(section)
            if group == "business" and internal_volume in BUSINESS_LIMITED_INTERNAL_VOLUMES:
                target_words = min(target_words, LIMITED_VOLUME_WORD_CAP.get(internal_volume, 1200))
            allocations[section_id] = max(350, target_words)

    return [
        {
            "sectionId": section_id,
            "targetWords": target_words,
        }
        for section_id, target_words in allocations.items()
    ]


def apply_length_allocations_to_sections(
    sections: list[dict[str, Any]],
    allocations: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    by_id = {item["sectionId"]: int(item["targetWords"]) for item in allocations}
    next_sections: list[dict[str, Any]] = []
    for section in sections:
        section_id = section.get("id")
        target_words = by_id.get(section_id)
        if not target_words:
            next_sections.append(section)
            continue
        metadata = section.get("metadata") if isinstance(section.get("metadata"), dict) else {}
        plan = build_chapter_writing_plan(section)
        plan = {
            **plan,
            "target_words": target_words,
            "suggested_pages": str(max(1, round(target_words / WORDS_PER_PAGE[delivery_volume_type(section)]))),
            "length_settings_source": "project_length_settings",
            "allow_auto_expand": settings["allowAutoExpand"],
            "strategy": (
                f"{plan.get('strategy') or ''} 已按全文篇幅设置分配目标字数；"
                f"资料不足策略：{'允许围绕评分点和可验证措施扩写' if settings['allowAutoExpand'] else '稳健生成，缺失处使用待补充占位'}；"
                "不得通过重复、无关内容或虚构事实凑字数。"
            ).strip(),
        }
        next_sections.append({
            **section,
            "metadata": {
                **metadata,
                "writing_plan": plan,
                "length_settings": {
                    "mode": settings["mode"],
                    "delivery_volume_type": delivery_volume_type(section),
                    "allowAutoExpand": settings["allowAutoExpand"],
                },
            },
        })
    return next_sections

from typing import Any

from backend.core.bid_volumes import volume_generation_strategy


def _text(value: Any) -> str:
    return str(value) if value is not None else ""


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def build_chapter_writing_plan(chapter: dict[str, Any]) -> dict[str, Any]:
    """Build a pragmatic section writing plan without requiring a schema change.

    The plan is stored in bid_sections.metadata.writing_plan and used by the
    section writer to control target length and supporting materials.
    """

    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    volume_type = _text(metadata.get("volume_type")).strip().lower()
    has_explicit_volume = volume_type in {"qualification", "business", "technical", "price", "attachment"}
    title = _text(chapter.get("title"))
    purpose = _text(chapter.get("purpose"))
    combined = f"{title} {purpose}"
    level = int(chapter.get("level") or 1)
    priority = _text(chapter.get("priority") or "medium")
    scoring_count = len(chapter.get("mapped_scoring_items") or [])
    risk_count = len(chapter.get("mapped_risks") or [])
    requirement_count = len(chapter.get("mapped_requirements") or [])
    material_count = len(chapter.get("required_materials") or [])

    is_format = _contains_any(combined, ["投标函", "格式", "授权委托", "保证金", "声明", "承诺函", "偏离表"])
    is_qualification = volume_type == "qualification" or (not has_explicit_volume and _contains_any(combined, ["资格", "资质", "证书", "营业执照", "安全生产许可", "人员", "项目经理", "技术负责人"]))
    is_technical = volume_type == "technical" or (not has_explicit_volume and _contains_any(combined, ["技术", "施工组织", "实施方案", "施工方案", "质量", "安全", "环保", "进度", "资源配置", "发包人要求", "承包人建议"]))
    is_commercial = volume_type == "business" or (not has_explicit_volume and _contains_any(combined, ["商务", "合同", "付款", "履约", "服务", "税费", "廉政", "保密"]))
    is_price = volume_type == "price" or (not has_explicit_volume and _contains_any(combined, ["报价", "清单", "价格", "单价", "工程量"]))
    is_case = _contains_any(combined, ["业绩", "案例", "类似项目", "经验"])

    score = 0
    score += 3 if priority == "high" else 1 if priority == "medium" else 0
    score += min(scoring_count, 3)
    score += min(risk_count, 2)
    score += 1 if requirement_count >= 3 else 0
    score += 1 if material_count >= 2 else 0
    score += 2 if is_technical else 0
    score += 1 if is_qualification or is_price else 0

    if score >= 6:
        importance = "high"
    elif score >= 3:
        importance = "medium"
    else:
        importance = "low"

    if is_qualification:
        base_min, base_max = (1800, 4200) if level <= 2 else (900, 2200)
    elif is_price:
        base_min, base_max = (900, 2200)
    elif is_commercial:
        base_min, base_max = (1200, 3000)
    elif is_technical:
        base_min, base_max = (3500, 9000) if level <= 2 else (1800, 4500)
    elif is_case:
        base_min, base_max = (1500, 3600)
    elif is_format:
        base_min, base_max = (500, 1200)
    else:
        base_min, base_max = (800, 2200) if level <= 2 else (500, 1400)

    if importance == "high":
        base_min = int(base_min * 1.2)
        base_max = int(base_max * 1.25)
    elif importance == "low":
        base_min = int(base_min * 0.75)
        base_max = int(base_max * 0.8)

    target_words = int(round(((base_min + base_max) / 2) / 100) * 100)
    suggested_pages_min = max(1, round(base_min / 700))
    suggested_pages_max = max(suggested_pages_min, round(base_max / 700))

    needs_table = is_price or _contains_any(combined, ["人员", "业绩", "偏离", "进度", "计划", "清单", "参数", "评分"])
    needs_image = is_technical or _contains_any(combined, ["设备", "产品", "工艺", "流程", "布置", "现场"])
    needs_qualification = is_qualification
    needs_case = is_case or _contains_any(combined, ["施工组织", "技术", "质量", "安全"])
    generation_mode = "multi_pass" if target_words >= 3500 else "single_pass"

    if is_qualification:
        strategy = "以资质、人员、证书、业绩材料为主，正文应短而准，关键编号和日期使用占位符等待企业资料补齐。"
    elif is_price:
        strategy = "以报价口径、清单说明、风险边界和人工复核提示为主，表格信息必须保留可校验字段。"
    elif is_commercial:
        strategy = "按商务标口径响应投标函、合同条款、承诺、偏离和服务要求，金额、日期、签章和保证金信息必须使用占位符或人工复核提示。"
    elif is_technical:
        strategy = "按招标技术要求和评分点展开，优先覆盖施工部署、关键工序、质量安全、进度资源和风险控制，可分段续写。"
    elif is_format:
        strategy = "按招标文件格式响应，避免扩写过度，重点保留签章、日期、金额、附件页码等占位。"
    else:
        strategy = "围绕章节目标、招标要求、评分点和风险项形成正式响应，缺失事实信息使用占位符。"
    if has_explicit_volume:
        volume_strategy = volume_generation_strategy(volume_type)
        focus = "；".join(volume_strategy.get("focus") or [])
        constraints = "；".join(volume_strategy.get("constraints") or [])
        strategy = f"{strategy} 分册策略：{focus} 强制约束：{constraints}"

    return {
        "importance": importance,
        "min_words": base_min,
        "max_words": base_max,
        "target_words": target_words,
        "suggested_pages": f"{suggested_pages_min}-{suggested_pages_max}" if suggested_pages_min != suggested_pages_max else str(suggested_pages_min),
        "needs_table": needs_table,
        "needs_image": needs_image,
        "needs_qualification": needs_qualification,
        "needs_case": needs_case,
        "generation_mode": generation_mode,
        "strategy": strategy,
    }


def ensure_chapter_writing_plan(chapter: dict[str, Any]) -> dict[str, Any]:
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    existing = metadata.get("writing_plan") if isinstance(metadata.get("writing_plan"), dict) else None
    if existing:
        return existing
    return build_chapter_writing_plan(chapter)

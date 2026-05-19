import logging
import re
from typing import Any, Iterator

from backend.core.config import build_enterprise_context
from backend.core.bid_volumes import asset_applicable_volumes, asset_matches_volume, section_volume_type, volume_generation_strategy, volume_name
from backend.ai.bid_writing_plan import ensure_chapter_writing_plan
from backend.db.supabase_repo import get_project_interpretation, list_knowledge_assets
from backend.ai.qwen_client import call_dashscope_api, stream_dashscope_api
from backend.core.config import get_stage_model


def _text(value: Any) -> str:
    return str(value) if value is not None else ""


def _compact_list(items: list[str] | None, limit: int = 6) -> str:
    values = [item for item in (items or []) if item]
    return "\n".join(f"- {item}" for item in values[:limit]) or "- 需人工复核"


def _chunk_text(content: str, size: int = 90) -> Iterator[str]:
    parts = re.split(r"(\n+)", content)
    current = ""
    for part in parts:
        if len(current) + len(part) >= size:
            if current:
                yield current
            current = part
        else:
            current += part
    if current:
        yield current


def estimate_bid_content_words(content: str) -> int:
    """Estimate Chinese bid正文 length after stripping common Markdown syntax."""
    text = re.sub(r"```.*?```", "", content or "", flags=re.S)
    text = re.sub(r"!\[[^\]]*]\([^)]*\)", "", text)
    text = re.sub(r"\[[^\]]*]\([^)]*\)", "", text)
    text = re.sub(r"[#>*_`|:\-\s]+", "", text)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
    latin_words = re.findall(r"[A-Za-z0-9]+", re.sub(r"[\u4e00-\u9fff]", " ", text))
    return len(cjk_chars) + len(latin_words)


def _target_words(chapter: dict[str, Any]) -> int:
    plan = ensure_chapter_writing_plan(chapter)
    try:
        return max(0, int(float(plan.get("target_words") or 0)))
    except (TypeError, ValueError):
        return 0


def _allow_auto_expand(chapter: dict[str, Any]) -> bool:
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    length_settings = metadata.get("length_settings") if isinstance(metadata.get("length_settings"), dict) else {}
    plan = ensure_chapter_writing_plan(chapter)
    return bool(plan.get("allow_auto_expand") or length_settings.get("allowAutoExpand"))


def _needs_length_supplement(content: str, chapter: dict[str, Any], threshold: float = 0.75) -> bool:
    target_words = _target_words(chapter)
    if target_words < 800:
        return False
    return estimate_bid_content_words(content) < int(target_words * threshold)


def _asset_text(asset: dict[str, Any]) -> str:
    parts = [
        asset.get("title"),
        asset.get("description"),
        asset.get("category"),
        asset.get("asset_type"),
        asset.get("searchable_text"),
    ]
    parts.extend(asset.get("tags") or [])
    parts.extend(asset.get("applicable_sections") or [])
    parts.extend(asset_applicable_volumes(asset))
    specs = asset.get("specs") or {}
    if isinstance(specs, dict):
        parts.extend(str(value) for value in specs.values() if value)
    return " ".join(str(item) for item in parts if item).lower()


def _asset_library_type(asset: dict[str, Any]) -> str:
    metadata = asset.get("metadata") or {}
    specs = asset.get("specs") or {}
    if isinstance(metadata, dict) and metadata.get("library_type"):
        return str(metadata.get("library_type"))
    if isinstance(specs, dict) and specs.get("library_type"):
        return str(specs.get("library_type"))
    return ""


def _supporting_asset_score(asset: dict[str, Any], chapter: dict[str, Any], volume_type: str) -> int:
    asset_text = _asset_text(asset)
    chapter_text = " ".join(
        str(item)
        for item in [
            chapter.get("title"),
            chapter.get("purpose"),
            *(chapter.get("response_points") or []),
            *(chapter.get("required_materials") or []),
        ]
        if item
    ).lower()
    library_type = _asset_library_type(asset)
    score = 0
    if not asset_matches_volume(asset, volume_type, allow_unscoped=True):
        return -100
    if asset_matches_volume(asset, volume_type, allow_unscoped=False):
        score += 30
    if volume_type == "technical":
        if library_type == "product" or any(keyword in asset_text for keyword in ["产品", "设备", "参数", "工艺", "施工", "质量", "安全"]):
            score += 20
    elif volume_type == "qualification":
        if library_type == "qualification" or any(keyword in asset_text for keyword in ["资质", "证书", "营业执照", "人员", "业绩", "信誉"]):
            score += 24
    elif volume_type == "business":
        if any(keyword in asset_text for keyword in ["商务", "合同", "承诺", "偏离", "授权", "保证金", "服务"]):
            score += 18
    elif volume_type == "price":
        if any(keyword in asset_text for keyword in ["报价", "清单", "单价", "税费", "风险", "复核"]):
            score += 18
    elif volume_type == "attachment":
        score += 10

    for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", chapter_text):
        if token in asset_text:
            score += 2 if len(token) >= 4 else 1
    return score


def _compact_supporting_assets(chapter: dict[str, Any], volume_type: str, limit: int = 6) -> str:
    try:
        assets = list_knowledge_assets()
    except Exception:
        return "- 企业资料候选读取失败，本节按招标解读和人工占位生成。"

    candidates: list[tuple[int, dict[str, Any]]] = []
    for asset in assets:
        score = _supporting_asset_score(asset, chapter, volume_type)
        if score > 0:
            candidates.append((score, asset))
    candidates.sort(key=lambda item: item[0], reverse=True)
    if not candidates:
        return "- 暂未命中高相关企业资料；缺失事实信息必须使用【待补充：...】。"

    rows: list[str] = []
    for _, asset in candidates[:limit]:
        tags = "、".join(str(item) for item in (asset.get("tags") or [])[:4])
        note = asset.get("description") or asset.get("searchable_text") or ""
        note = str(note).replace("\n", " ")[:120]
        rows.append(
            f"- {asset.get('title') or '未命名资料'}"
            f"（类型：{asset.get('asset_type') or '资料'}；分类：{asset.get('category') or '未分类'}；标签：{tags or '无'}；说明：{note or '无'}）"
        )
    return "\n".join(rows)


def build_section_supplement_prompt(project_id: str, chapter: dict[str, Any], current_content: str) -> str:
    payload = get_project_interpretation(project_id)
    project = payload.get("project") or {}
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") or {}

    title = _text(chapter.get("title")) or "未命名章节"
    purpose = _text(chapter.get("purpose"))
    writing_plan = ensure_chapter_writing_plan(chapter)
    volume_type = section_volume_type(chapter)
    volume_strategy = volume_generation_strategy(volume_type)
    target_words = _target_words(chapter)
    actual_words = estimate_bid_content_words(current_content)
    missing_words = max(0, target_words - actual_words)
    allow_auto_expand = _allow_auto_expand(chapter)
    supporting_assets = _compact_supporting_assets(chapter, volume_type)
    current_excerpt = (current_content or "").strip()
    if len(current_excerpt) > 4200:
        current_excerpt = current_excerpt[-4200:]

    expand_rule = (
        "允许围绕评分点、可验证实施措施、质量安全控制、进度资源配置和风险应对展开，但不得编造企业专属事实。"
        if allow_auto_expand
        else "仅补充有依据的内容；资料不足时输出【待补充：...】、复核清单或表格占位，不得空泛扩写。"
    )

    return f"""
你是资深投标文件撰写专家。当前章节已生成一版，但低于该章节写作计划目标。请只输出“可直接追加到本章节末尾”的补写内容，不要重复已有内容，不要输出解释。

补写目标：
- 章节标题：{title}
- 编写目标：{purpose or "需人工复核"}
- 所属分册：{volume_name(volume_type)}（{volume_type}）
- 章节目标字数：{target_words or "需人工复核"} 字
- 当前估算字数：{actual_words} 字
- 建议补写字数：约 {missing_words} 字，优先补足到目标字数的 75% 以上
- 资料不足策略：{expand_rule}

必须遵守：
1. 补写内容必须承接当前章节，不要重新生成标题，不要重写已出现段落。
2. 优先补充与评分项、响应要求、风险控制、实施措施、表格化承诺有关的内容。
3. 不得为了凑页数重复同义段落、塞入无关内容或虚构证书编号、人员姓名、合同金额、具体日期。
4. 缺少企业事实时使用“【待补充：...】”占位，并说明需要补充的材料。
5. 正式正文不得使用 emoji、图标符号或装饰性提示符。

项目信息：
- 项目名称：{project_meta.get("project_name") or project.get("project_name") or "需人工复核"}
- 招标编号：{project_meta.get("tender_no") or project.get("project_no") or "需人工复核"}
- 项目摘要：{analysis.get("summary") or "需人工复核"}

分册写作策略：
{_compact_list(volume_strategy.get("focus"), limit=8)}

当前命中的企业资料候选：
{supporting_assets}

响应要点：
{_compact_list(chapter.get("response_points") or [])}

关联要求：
{_compact_list(chapter.get("mapped_requirements") or [])}

关联评分项：
{_compact_list(chapter.get("mapped_scoring_items") or [])}

风险提醒：
{_compact_list(chapter.get("mapped_risks") or [])}

章节写作计划：
- 目标字数：{writing_plan.get("target_words") or "需人工复核"} 字
- 建议篇幅：{writing_plan.get("suggested_pages") or "需人工复核"} 页
- 生成方式：{writing_plan.get("generation_mode") or "single_pass"}
- 写作策略：{writing_plan.get("strategy") or "需人工复核"}

当前章节已有内容节选：
{current_excerpt or "暂无"}
""".strip()


def build_section_prompt(project_id: str, chapter: dict[str, Any]) -> str:
    payload = get_project_interpretation(project_id)
    project = payload.get("project") or {}
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") or {}

    title = _text(chapter.get("title")) or "未命名章节"
    purpose = _text(chapter.get("purpose"))
    writing_plan = ensure_chapter_writing_plan(chapter)
    volume_type = section_volume_type(chapter)
    volume_strategy = volume_generation_strategy(volume_type)
    context = {
        "project_name": project_meta.get("project_name") or project.get("project_name"),
        "tender_no": project_meta.get("tender_no") or project.get("project_no"),
        "summary": analysis.get("summary"),
        "chapter_title": title,
        "chapter_purpose": purpose,
        "response_points": chapter.get("response_points") or [],
        "mapped_requirements": chapter.get("mapped_requirements") or [],
        "mapped_scoring_items": chapter.get("mapped_scoring_items") or [],
        "mapped_risks": chapter.get("mapped_risks") or [],
        "required_materials": chapter.get("required_materials") or [],
        "source_pages": chapter.get("source_pages") or [],
        "writing_notes": chapter.get("writing_notes") or [],
        "writing_plan": writing_plan,
        "volume_type": volume_type,
        "volume_name": volume_name(volume_type),
        "volume_strategy": volume_strategy,
    }

    enterprise_context = build_enterprise_context()
    supporting_assets = _compact_supporting_assets(chapter, volume_type)

    return f"""
你是资深投标文件撰写专家，熟悉水利水电工程总承包、设备配套、质量管理和招投标文件格式要求。
企业画像：
{enterprise_context}

请为当前投标章节生成可直接放入标书的正文草稿。

写作要求：
1. 只输出章节正文，不要解释你如何生成。
2. 语言正式、稳健、可落地，符合国内投标文件表达习惯。
3. 不要编造企业没有提供的证书编号、人员姓名、合同金额、具体日期；遇到缺失信息，用“【待补充：...】”占位。
4. 必须回应章节目标、响应要点、评分项和风险点。
5. 如适合表格，用 Markdown 表格输出。
6. 正文字数按章节写作计划控制。本次生成尽量覆盖完整章节；若目标字数较长，可先输出结构完整的第一版，并保留可续写的小标题。
7. 必须遵守当前分册策略，尤其是金额、证书、人员、日期、签章、保证金和报价信息的禁编造约束。
8. 正式标书正文不得使用 emoji、图标符号或装饰性提示符；“关键提醒”“风险提示”等内容必须使用纯文字标题。
9. 不得为了凑页数重复同义段落、塞入无关内容或虚构资料；当证据不足以支撑目标篇幅时，用“【待补充：...】”标明所需材料和人工复核点。

项目信息：
- 项目名称：{context["project_name"] or "需人工复核"}
- 招标编号：{context["tender_no"] or "需人工复核"}
- 项目摘要：{context["summary"] or "需人工复核"}

当前章节：
- 所属分册：{context["volume_name"]}（{context["volume_type"]}）
- 标题：{title}
- 编写目标：{purpose or "需人工复核"}
- 来源页码：{context["source_pages"] or "需人工复核"}

分册写作策略：
{_compact_list(context["volume_strategy"].get("focus"), limit=8)}

分册强制约束：
{_compact_list(context["volume_strategy"].get("constraints"), limit=8)}

资料召回侧重点：
- {context["volume_strategy"].get("retrieval_hint") or "按章节标题和响应要点召回资料。"}

当前命中的企业资料候选：
{supporting_assets}

图片/附件策略：
- {context["volume_strategy"].get("image_policy") or "仅在章节明确需要时插入。"}

章节写作计划：
- 重要性：{writing_plan.get("importance") or "medium"}
- 目标字数：{writing_plan.get("target_words") or "需人工复核"} 字
- 建议篇幅：{writing_plan.get("suggested_pages") or "需人工复核"} 页
- 生成方式：{writing_plan.get("generation_mode") or "single_pass"}
- 资料不足策略：{"允许围绕评分点和可验证措施扩写" if _allow_auto_expand(chapter) else "稳健生成，缺失处使用待补充占位"}
- 是否需要表格：{"是" if writing_plan.get("needs_table") else "否"}
- 是否需要图片/流程图：{"是" if writing_plan.get("needs_image") else "否"}
- 是否需要资质材料：{"是" if writing_plan.get("needs_qualification") else "否"}
- 是否需要业绩支撑：{"是" if writing_plan.get("needs_case") else "否"}
- 写作策略：{writing_plan.get("strategy") or "需人工复核"}

响应要点：
{_compact_list(context["response_points"])}

关联要求：
{_compact_list(context["mapped_requirements"])}

关联评分项：
{_compact_list(context["mapped_scoring_items"])}

风险提醒：
{_compact_list(context["mapped_risks"])}

需要准备的资料：
{_compact_list(context["required_materials"])}

写作注意事项：
{_compact_list(context["writing_notes"])}
""".strip()


def stream_bid_section(project_id: str, chapter: dict[str, Any]) -> Iterator[dict[str, Any]]:
    prompt = build_section_prompt(project_id, chapter)
    yield {
        "type": "start",
        "title": chapter.get("title") or "未命名章节",
    }

    emitted = False
    generated_content = ""
    try:
        for chunk in stream_dashscope_api(
            [{"role": "user", "content": prompt}],
            model=get_stage_model("section_writing"),
            usage_context={
                "project_id": project_id,
                "section_id": chapter.get("id"),
                "stage": "bid_section_stream",
                "metadata": {
                    "chapter_title": chapter.get("title"),
                    "volume_type": section_volume_type(chapter),
                },
            },
        ):
            emitted = True
            generated_content += chunk
            yield {
                "type": "chunk",
                "content": chunk,
            }
    except Exception:
        response = call_dashscope_api(
            [{"role": "user", "content": prompt}],
            model=get_stage_model("section_writing"),
            json_mode=False,
            usage_context={
                "project_id": project_id,
                "section_id": chapter.get("id"),
                "stage": "bid_section_sync_fallback",
                "metadata": {
                    "chapter_title": chapter.get("title"),
                    "volume_type": section_volume_type(chapter),
                },
            },
        )
        content = response["output"]["choices"][0]["message"]["content"]
        for chunk in _chunk_text(content):
            emitted = True
            generated_content += chunk
            yield {
                "type": "chunk",
                "content": chunk,
            }

    if not emitted:
        yield {
            "type": "chunk",
            "content": "【待补充：当前章节正文生成失败，请稍后重新生成。】",
        }
        generated_content = "【待补充：当前章节正文生成失败，请稍后重新生成。】"

    if emitted and _needs_length_supplement(generated_content, chapter):
        supplement_prompt = build_section_supplement_prompt(project_id, chapter, generated_content)
        supplement_prefix = "\n\n"
        generated_content += supplement_prefix
        yield {
            "type": "chunk",
            "content": supplement_prefix,
        }
        try:
            for chunk in stream_dashscope_api(
                [{"role": "user", "content": supplement_prompt}],
                model=get_stage_model("section_supplement"),
                usage_context={
                    "project_id": project_id,
                    "section_id": chapter.get("id"),
                    "stage": "bid_section_length_supplement",
                    "metadata": {
                        "chapter_title": chapter.get("title"),
                        "volume_type": section_volume_type(chapter),
                        "target_words": _target_words(chapter),
                        "actual_words": estimate_bid_content_words(generated_content),
                        "allow_auto_expand": _allow_auto_expand(chapter),
                    },
                },
            ):
                generated_content += chunk
                yield {
                    "type": "chunk",
                    "content": chunk,
                }
        except Exception:
            try:
                response = call_dashscope_api(
                    [{"role": "user", "content": supplement_prompt}],
                    model=get_stage_model("section_supplement"),
                    json_mode=False,
                    usage_context={
                        "project_id": project_id,
                        "section_id": chapter.get("id"),
                        "stage": "bid_section_length_supplement_fallback",
                        "metadata": {
                            "chapter_title": chapter.get("title"),
                            "volume_type": section_volume_type(chapter),
                            "target_words": _target_words(chapter),
                            "actual_words": estimate_bid_content_words(generated_content),
                            "allow_auto_expand": _allow_auto_expand(chapter),
                        },
                    },
                )
                supplement = response["output"]["choices"][0]["message"]["content"]
                for chunk in _chunk_text(supplement):
                    generated_content += chunk
                    yield {
                        "type": "chunk",
                        "content": chunk,
                    }
            except Exception:
                logging.exception("章节篇幅补写失败，保留首轮生成内容: %s", chapter.get("id"))

    yield {
        "type": "done",
    }

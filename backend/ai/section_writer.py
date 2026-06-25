import logging
import os
import re
import time
from typing import Any, Iterator

from backend.core.config import build_enterprise_context
from backend.core.bid_volumes import asset_applicable_volumes, asset_matches_volume, section_volume_type, volume_generation_strategy, volume_name
from backend.ai.bid_writing_plan import ensure_chapter_writing_plan
from backend.ai.section_prompt_policy import (
    build_section_context_budget,
    classify_section_prompt_profile,
    enforce_prompt_budget,
)
from backend.db.supabase_repo import get_project_interpretation, list_knowledge_assets
from backend.ai.qwen_client import LLMStreamTimeoutError, call_dashscope_api, stream_dashscope_api
from backend.core.config import get_stage_model
from backend.services.bid_prefill import confirmed_prefill_context
from backend.services.taichang_bid_context import build_taichang_verified_fact_context, load_taichang_verified_fact_pack

FORMAL_PLACEHOLDER_RE = re.compile(r"【\s*待(?:补充|填写|确认|核对)[^】]*】|\{\{[^}]+}}|\$\{[^}]+}")
GENERIC_PLACEHOLDER_LABELS = {
    "",
    "人工复核",
    "人工复核后填写",
    "人工核实后填写",
    "同上",
    "当前章节正文生成失败，请稍后重新生成。",
}


def _text(value: Any) -> str:
    return str(value) if value is not None else ""


def _compact_list(items: list[str] | None, limit: int = 6) -> str:
    values = [item for item in (items or []) if item]
    return "\n".join(f"- {item}" for item in values[:limit]) or "- 需人工复核"


def _confirmed_prefill_text(project_meta: dict[str, Any]) -> str:
    values = confirmed_prefill_context(project_meta)
    if not values:
        return "- 暂无用户确认变量；缺失事实仍须明确标注人工确认。"
    return "\n".join(f"- {key}: {value}" for key, value in values.items())


def _taichang_fact_digest(mode: str) -> str:
    if mode == "full":
        return build_taichang_verified_fact_context()

    facts = load_taichang_verified_fact_pack()
    if not facts:
        return "- 泰昌核验事实包当前不可用；不得从参考稿或招标样本推断企业事实。"

    enterprise = facts.get("enterprise") if isinstance(facts.get("enterprise"), dict) else {}
    rows = [
        "- 投标人：河北泰昌电力器材科技有限公司。",
        f"- 统一社会信用代码：{enterprise.get('unified_social_credit_code') or '未核验'}；法定代表人：{enterprise.get('legal_representative') or '未核验'}。",
    ]

    if mode == "identity_only":
        rows.append("- 本节仅保留投标主体基础事实；证书编号、金额、日期等专属事实不得编造。")
        return "\n".join(rows)

    if mode == "minimal_constraints":
        rows.append("- 本 profile 不加载完整泰昌事实包；金额、报价、保证金、签章日期、人员、证书编号和业绩金额缺失时必须保留人工确认。")
        rows.append("- 辽宁资料仅为招标要求样本；河北豪乾资料仅可参考目录/表式，不得作为泰昌企业事实。")
        return "\n".join(rows)

    if mode in {"certifications", "performance"}:
        cert_rows = []
        for cert in facts.get("certifications") or []:
            if isinstance(cert, dict) and cert.get("name"):
                cert_rows.append(
                    f"- {cert.get('name')}：证书编号 {cert.get('certificate_no') or '未核验'}，有效期至 {cert.get('valid_until') or '未核验'}。"
                )
        rows.extend(cert_rows[:5] or ["- 暂未命中证书摘要；涉及资质证书编号和有效期时不得编造。"])

    if mode in {"product_parameters", "performance"}:
        product_rows = []
        for product, report in (facts.get("product_inspection") or {}).items():
            if not isinstance(report, dict):
                continue
            parameters = "；".join(
                f"{item.get('parameter')} {item.get('inspection_result')}{item.get('unit') or ''}"
                for item in (report.get("parameters") or [])[:5]
                if isinstance(item, dict) and item.get("parameter")
            )
            product_rows.append(
                f"- {product}检验报告：报告编号 {report.get('report_no') or '未核验'}，规格型号 {report.get('specification_model') or '未核验'}；{parameters or '关键参数见结构化参数表'}。"
            )
        rows.extend(product_rows[:4] or ["- 暂未命中检验报告摘要；技术参数和报告编号缺失时不得编造。"])

    if mode == "performance":
        performance = facts.get("project_performance") if isinstance(facts.get("project_performance"), dict) else {}
        if performance:
            rows.append(
                f"- 泰昌真实业绩：{performance.get('project_name')}，招标编号 {performance.get('tender_no')}，"
                f"{performance.get('package_no')}，产品 {performance.get('product_summary')}，数量 {performance.get('total_quantity')}，"
                f"含税金额 {performance.get('amount_tax_included')}；合同签署日期原件为空，不得推断。"
            )
    rows.append("- 河北豪乾资料只允许参考目录、表式和写法，严禁作为上述泰昌事实来源。")
    return "\n".join(rows)


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


def _is_stream_timeout_error(exc: Exception) -> bool:
    return (
        isinstance(exc, LLMStreamTimeoutError)
        or str(getattr(exc, "code", "")) in {"MODEL_STREAM_WALL_TIMEOUT", "MODEL_STREAM_IDLE_TIMEOUT", "MODEL_STREAM_SLOW_TIMEOUT"}
        or "MODEL_STREAM_" in str(exc)
    )


def _env_float_value(names: list[str], default: float | None = None) -> float | None:
    for name in names:
        raw = os.getenv(name)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            logging.warning("忽略无效的章节流配置 %s=%s", name, raw)
    return default


def _env_int_value(names: list[str], default: int | None = None) -> int | None:
    value = _env_float_value(names, None)
    if value is None:
        return default
    return int(value)


def _stream_slow_check_seconds(profile) -> float:
    value = _env_float_value(
        ["SECTION_STREAM_SLOW_CHECK_SECONDS", "BID_SECTION_STREAM_SLOW_CHECK_SECONDS"],
        90.0,
    )
    if value is None or value <= 0:
        return 0.0
    return max(0.1, value)


def _stream_first_token_slow_seconds() -> float:
    value = _env_float_value(
        ["SECTION_STREAM_FIRST_TOKEN_SLOW_SECONDS", "BID_SECTION_STREAM_FIRST_TOKEN_SLOW_SECONDS"],
        30.0,
    )
    if value is None or value <= 0:
        return 0.0
    return max(0.1, value)


def _stream_min_chars_at_slow_check(profile) -> int:
    configured = _env_int_value(
        ["SECTION_STREAM_MIN_CHARS_AT_SLOW_CHECK", "BID_SECTION_STREAM_MIN_CHARS_AT_SLOW_CHECK"],
        None,
    )
    if configured is not None:
        return max(1, configured)
    profile_defaults = {
        "continuation_slim": 120,
        "attachment_index": 120,
        "price_sensitive": 120,
        "structured_table": 160,
        "simple_plan": 180,
    }
    return profile_defaults.get(profile.name, 250)


class _SectionStreamMonitor:
    def __init__(self, profile) -> None:
        self.profile = profile
        self.started_at = time.monotonic()
        self.first_token_at: float | None = None
        self.stream_chars = 0
        self.metrics: dict[str, Any] = {
            "slow_check_seconds": _stream_slow_check_seconds(profile),
            "min_chars_at_slow_check": _stream_min_chars_at_slow_check(profile),
        }
        self._emitted_first_token = False
        self._emitted_milestones: set[int] = set()
        self._emitted_final = False
        self._slow_triggered = False

    def _base_metrics(self, now: float) -> dict[str, Any]:
        elapsed = max(0.001, now - self.started_at)
        metrics = {
            **self.metrics,
            "stream_elapsed_ms": int(elapsed * 1000),
            "stream_chars": self.stream_chars,
            "chars_per_minute": round(self.stream_chars * 60 / elapsed, 2),
        }
        if self.first_token_at is not None:
            latency_ms = int((self.first_token_at - self.started_at) * 1000)
            metrics["first_token_latency_ms"] = latency_ms
            first_token_slow_seconds = _stream_first_token_slow_seconds()
            if first_token_slow_seconds and latency_ms >= int(first_token_slow_seconds * 1000):
                metrics["first_token_slow"] = True
        return metrics

    def record_chunk(self, chunk: str) -> tuple[dict[str, Any] | None, LLMStreamTimeoutError | None]:
        now = time.monotonic()
        self.stream_chars += len((chunk or "").replace("\n", ""))
        first_token_event = False
        if self.first_token_at is None:
            self.first_token_at = now
            first_token_event = True

        elapsed = max(0.001, now - self.started_at)
        milestone_event = False
        if elapsed >= 60 and "chars_at_60s" not in self.metrics:
            self.metrics["chars_at_60s"] = self.stream_chars
            self._emitted_milestones.add(60)
            milestone_event = True
        if elapsed >= 90 and "chars_at_90s" not in self.metrics:
            self.metrics["chars_at_90s"] = self.stream_chars
            self._emitted_milestones.add(90)
            milestone_event = True

        metrics = self._base_metrics(now)

        slow_check_seconds = float(metrics.get("slow_check_seconds") or 0)
        min_chars = int(metrics.get("min_chars_at_slow_check") or 0)
        if slow_check_seconds and elapsed >= slow_check_seconds and self.stream_chars < min_chars:
            reason = f"elapsed_{int(elapsed)}s_chars_{self.stream_chars}_below_{min_chars}"
            slow_metrics = {
                **metrics,
                "slow_stream": True,
                "slow_stream_reason": reason,
                "timeout_code": "MODEL_STREAM_SLOW_TIMEOUT",
            }
            self.metrics.update(slow_metrics)
            self._slow_triggered = True
            message = (
                f"模型流式输出超过 {int(slow_check_seconds)} 秒但仅输出 {self.stream_chars} 字，"
                f"低于慢流阈值 {min_chars} 字，已提前保存草稿并释放生成槽。"
            )
            return slow_metrics, LLMStreamTimeoutError("MODEL_STREAM_SLOW_TIMEOUT", message, metadata=slow_metrics)

        if first_token_event and not self._emitted_first_token:
            self._emitted_first_token = True
            return metrics, None
        if milestone_event:
            return metrics, None
        return None, None

    def finish(self) -> dict[str, Any] | None:
        if self._emitted_final or self._slow_triggered:
            return None
        self._emitted_final = True
        now = time.monotonic()
        metrics = {
            **self._base_metrics(now),
            "slow_stream": False,
            "slow_stream_reason": None,
        }
        self.metrics.update(metrics)
        return metrics


def _target_words(chapter: dict[str, Any]) -> int:
    plan = ensure_chapter_writing_plan(chapter)
    try:
        return max(0, int(float(plan.get("target_words") or 0)))
    except (TypeError, ValueError):
        return 0


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default)) or default))
    except (TypeError, ValueError):
        return default


def _hard_length_cap_words(chapter: dict[str, Any]) -> int:
    raw = str(os.getenv("BID_SECTION_HARD_LENGTH_CAP_ENABLED", "true") or "true").lower()
    if raw in {"0", "false", "no", "off"}:
        return 0
    target_words = _target_words(chapter)
    if target_words <= 0:
        return 0
    ratio = max(1.0, _float_env("BID_SECTION_HARD_LENGTH_CAP_RATIO", 1.1))
    min_extra_words = max(0, _int_env("BID_SECTION_HARD_LENGTH_CAP_MIN_EXTRA_WORDS", 120))
    return max(int(target_words * ratio), target_words + min_extra_words)


def _length_cap_reached(content: str, chapter: dict[str, Any]) -> tuple[bool, int, int]:
    max_words = _hard_length_cap_words(chapter)
    if max_words <= 0:
        return False, 0, estimate_bid_content_words(content)
    actual_words = estimate_bid_content_words(content)
    return actual_words >= max_words, max_words, actual_words


def _allow_auto_expand(chapter: dict[str, Any]) -> bool:
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    length_settings = metadata.get("length_settings") if isinstance(metadata.get("length_settings"), dict) else {}
    plan = ensure_chapter_writing_plan(chapter)
    return bool(plan.get("allow_auto_expand") or length_settings.get("allowAutoExpand"))


def _length_supplement_enabled(chapter: dict[str, Any]) -> bool:
    raw = str(os.getenv("BID_SECTION_LENGTH_SUPPLEMENT_ENABLED", "true") or "true").lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    options = metadata.get("generation_options") if isinstance(metadata.get("generation_options"), dict) else {}
    return not bool(options.get("skipLengthSupplement") or options.get("skip_length_supplement"))


def _needs_length_supplement(content: str, chapter: dict[str, Any], threshold: float = 0.75) -> bool:
    if not _length_supplement_enabled(chapter):
        return False
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
    if limit <= 0:
        return "- 当前 prompt profile 不加载企业资料候选；如本节缺少企业事实，必须使用【待补充：...】并提示人工确认。"
    try:
        assets = list_knowledge_assets()
    except LLMStreamTimeoutError:
        raise
    except LLMStreamTimeoutError:
        raise
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


def _section_rag_query(project: dict[str, Any], analysis: dict[str, Any], chapter: dict[str, Any]) -> str:
    project_meta = analysis.get("project_meta") or {}
    parts: list[str] = [
        "电网投标章节写作",
        project_meta.get("project_name") or project.get("project_name") or "",
        project_meta.get("tender_no") or project.get("project_no") or "",
        analysis.get("summary") or "",
        _text(chapter.get("title")),
        _text(chapter.get("purpose")),
        " ".join(str(item) for item in (chapter.get("response_points") or [])[:6]),
        " ".join(str(item) for item in (chapter.get("mapped_requirements") or [])[:6]),
        " ".join(str(item) for item in (chapter.get("mapped_scoring_items") or [])[:6]),
        " ".join(str(item) for item in (chapter.get("mapped_risks") or [])[:4]),
    ]
    return " ".join(part.strip() for part in parts if str(part or "").strip())[:700]


def _compact_section_rag_context(project: dict[str, Any], analysis: dict[str, Any], chapter: dict[str, Any], limit: int = 5) -> str:
    if limit <= 0:
        return "- 当前 prompt profile 不加载章节级 RAG 写作依据；仅使用草稿、客户确认变量和最小事实边界续写。"
    query = _section_rag_query(project, analysis, chapter)
    if not query:
        return "- 未形成有效章节检索 query，本节按招标解读和人工占位生成。"
    try:
        from backend.rag.retrieval import search_knowledge_base

        contexts = search_knowledge_base(
            query,
            match_threshold=0.25,
            match_count=limit,
            scenario="writing",
            return_parent=True,
        )
    except Exception:
        logging.warning("section_writer: 章节级 RAG 检索失败，跳过", exc_info=True)
        return "- 章节级 RAG 检索失败，本节按招标解读和人工占位生成。"

    if not contexts:
        return "- 未召回高相关文本依据；缺失事实信息必须使用【待补充：...】。"

    rows: list[str] = []
    for index, ctx in enumerate(contexts[:limit], 1):
        meta = ctx.get("metadata") or {}
        retrieved_by_child = meta.get("retrieved_by_child") if isinstance(meta.get("retrieved_by_child"), dict) else {}
        child_meta = retrieved_by_child.get("metadata") if isinstance(retrieved_by_child.get("metadata"), dict) else {}
        source = (
            meta.get("source_org")
            or meta.get("source_file")
            or child_meta.get("source_org")
            or child_meta.get("source_file")
            or "知识库资料"
        )
        doc_role = meta.get("doc_role") or child_meta.get("doc_role") or "unknown"
        section = ctx.get("source_section") or retrieved_by_child.get("source_section") or "未标注章节"
        content = str(ctx.get("content") or "").replace("\n", " ").strip()
        if len(content) > 360:
            content = content[:360] + "..."
        rows.append(
            f"- 资料{index}（来源：{source}；角色：{doc_role}；章节：{section}）：{content}"
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
    profile = classify_section_prompt_profile(chapter)
    target_words = _target_words(chapter)
    actual_words = estimate_bid_content_words(current_content)
    missing_words = max(0, target_words - actual_words)
    allow_auto_expand = _allow_auto_expand(chapter)
    supporting_assets = _compact_supporting_assets(chapter, volume_type, limit=min(profile.asset_limit, 2))
    rag_context = _compact_section_rag_context(project, analysis, chapter, limit=min(profile.rag_limit, 2))
    grounding_instructions = _grounding_instructions(chapter)
    confirmed_variables = _confirmed_prefill_text(project_meta)
    taichang_facts = _taichang_fact_digest(profile.fact_pack_mode)
    current_excerpt = (current_content or "").strip()
    if len(current_excerpt) > 4200:
        current_excerpt = current_excerpt[-4200:]

    expand_rule = (
        "允许围绕评分点、可验证实施措施、质量安全控制、进度资源配置和风险应对展开，但不得编造企业专属事实。"
        if allow_auto_expand
        else "仅补充有依据的内容；资料不足时输出【待补充：...】、复核清单或表格占位，不得空泛扩写。"
    )

    prompt = f"""
你是资深投标文件撰写专家。当前章节已生成一版，但低于该章节写作计划目标。请只输出“可直接追加到本章节末尾”的补写内容，不要重复已有内容，不要输出解释。

补写目标：
- 章节标题：{title}
- 编写目标：{purpose or "需人工复核"}
- 所属分册：{volume_name(volume_type)}（{volume_type}）
- Prompt profile：{profile.label}（{profile.name}，RAG {min(profile.rag_limit, 2)} 条，企业资料 {min(profile.asset_limit, 2)} 条）
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
6. 下列用户确认变量必须直接使用，不得再次输出为【待补充】。

用户已确认投标变量：
{confirmed_variables}

泰昌已核验企业事实：
{taichang_facts}

项目信息：
- 项目名称：{project_meta.get("project_name") or project.get("project_name") or "需人工复核"}
- 招标编号：{project_meta.get("tender_no") or project.get("project_no") or "需人工复核"}
- 项目摘要：{analysis.get("summary") or "需人工复核"}

分册写作策略：
{_compact_list(volume_strategy.get("focus"), limit=8)}

当前命中的企业资料候选：
{supporting_assets}

本次专项事实与边界约束：
{grounding_instructions}

章节级 RAG 写作依据：
{rag_context}

响应要点：
{_compact_list(chapter.get("response_points") or [], limit=profile.requirement_limit)}

关联要求：
{_compact_list(chapter.get("mapped_requirements") or [], limit=profile.requirement_limit)}

关联评分项：
{_compact_list(chapter.get("mapped_scoring_items") or [], limit=profile.scoring_limit)}

风险提醒：
{_compact_list(chapter.get("mapped_risks") or [], limit=profile.risk_limit)}

章节写作计划：
- 目标字数：{writing_plan.get("target_words") or "需人工复核"} 字
- 建议篇幅：{writing_plan.get("suggested_pages") or "需人工复核"} 页
- 生成方式：{writing_plan.get("generation_mode") or "single_pass"}
- 写作策略：{writing_plan.get("strategy") or "需人工复核"}

当前章节已有内容节选：
{current_excerpt or "暂无"}
""".strip()
    prompt, _ = enforce_prompt_budget(prompt, profile)
    return prompt


def _generation_options(chapter: dict[str, Any]) -> dict[str, Any]:
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    options = metadata.get("generation_options") if isinstance(metadata.get("generation_options"), dict) else {}
    return options


def _grounding_instructions(chapter: dict[str, Any]) -> str:
    options = _generation_options(chapter)
    factual_context = str(options.get("factual_context") or options.get("grounding_context") or "").strip()
    required_scope = str(options.get("required_scope") or "").strip()
    forbidden_topics = options.get("forbidden_topics") or []
    allowed_placeholders = options.get("allowed_placeholders") or []
    if isinstance(forbidden_topics, str):
        forbidden_topics = [forbidden_topics]
    if isinstance(allowed_placeholders, str):
        allowed_placeholders = [allowed_placeholders]
    if not any([factual_context, required_scope, forbidden_topics, allowed_placeholders]):
        return "- 未配置额外事实约束，按章节 RAG 依据稳健生成。"
    rows = []
    if required_scope:
        rows.append(f"- 本节业务边界：{required_scope}")
    if factual_context:
        rows.extend(["- 已核验企业事实如下，涉及相同字段时必须直接使用，不得再次留空：", factual_context])
    if forbidden_topics:
        rows.append("- 禁止写入的主题或资质：" + "、".join(str(item) for item in forbidden_topics if item))
    if allowed_placeholders:
        rows.append("- 仅以下未确认事项允许保留【待补充】：" + "、".join(str(item) for item in allowed_placeholders if item))
    return "\n".join(rows)


def _continuation_draft(chapter: dict[str, Any]) -> str:
    options = _generation_options(chapter)
    draft = options.get("continuationDraft") or options.get("continuation_draft") or ""
    return str(draft or "").strip()


def build_section_continuation_prompt(project_id: str, chapter: dict[str, Any], draft_content: str) -> str:
    payload = get_project_interpretation(project_id)
    project = payload.get("project") or {}
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") or {}

    title = _text(chapter.get("title")) or "未命名章节"
    purpose = _text(chapter.get("purpose"))
    writing_plan = ensure_chapter_writing_plan(chapter)
    volume_type = section_volume_type(chapter)
    volume_strategy = volume_generation_strategy(volume_type)
    profile = classify_section_prompt_profile(chapter, continuation=True)
    target_words = _target_words(chapter)
    draft_words = estimate_bid_content_words(draft_content)
    supporting_assets = _compact_supporting_assets(chapter, volume_type, limit=profile.asset_limit)
    rag_context = _compact_section_rag_context(project, analysis, chapter, limit=profile.rag_limit)
    grounding_instructions = _grounding_instructions(chapter)
    confirmed_variables = _confirmed_prefill_text(project_meta)
    taichang_facts = _taichang_fact_digest(profile.fact_pack_mode)
    draft_excerpt = (draft_content or "").strip()
    if len(draft_excerpt) > 2600:
        draft_excerpt = draft_excerpt[-2600:]

    prompt = f"""
你是资深投标文件撰写专家。当前章节此前生成时模型超时，系统已保存草稿。请基于草稿继续补齐本章节，只输出“可直接追加到草稿末尾”的续写内容，不要重写标题，不要重复已有段落，不要解释。

续写目标：
- 章节标题：{title}
- 编写目标：{purpose or "需人工复核"}
- 所属分册：{volume_name(volume_type)}（{volume_type}）
- Prompt profile：{profile.label}（{profile.name}，只保留草稿末尾和最小事实边界）
- 目标字数：{target_words or "需人工复核"} 字
- 草稿估算字数：{draft_words} 字
- 续写原则：优先补齐未完成的承诺、措施、表格、复核清单或待补充项；如果草稿已经基本完整，只补一个简短收束段。

必须遵守：
1. 只输出续写内容，不要输出章节标题，不要重复草稿中已有内容。
2. 续写内容必须自然承接草稿末尾，避免“重新开始写本章节”的口吻。
3. 不得编造企业没有提供的证书编号、人员姓名、合同金额、具体日期。
4. 缺少企业事实时使用“【待补充：...】”占位，并说明需要补充的材料。
5. 正式正文不得使用 emoji、图标符号或装饰性提示符。
6. 如果草稿末尾是未完成句子，请先补全句子，再继续写后续段落。
7. 下列用户确认变量必须直接使用，不得再次输出为【待补充】。

用户已确认投标变量：
{confirmed_variables}

泰昌已核验企业事实：
{taichang_facts}

项目信息：
- 项目名称：{project_meta.get("project_name") or project.get("project_name") or "需人工复核"}
- 招标编号：{project_meta.get("tender_no") or project.get("project_no") or "需人工复核"}
- 项目摘要：{analysis.get("summary") or "需人工复核"}

分册写作策略：
{_compact_list(volume_strategy.get("focus"), limit=8)}

当前命中的企业资料候选：
{supporting_assets}

本次专项事实与边界约束：
{grounding_instructions}

章节级 RAG 写作依据：
{rag_context}

响应要点：
{_compact_list(chapter.get("response_points") or [], limit=profile.requirement_limit)}

关联要求：
{_compact_list(chapter.get("mapped_requirements") or [], limit=profile.requirement_limit)}

关联评分项：
{_compact_list(chapter.get("mapped_scoring_items") or [], limit=profile.scoring_limit)}

风险提醒：
{_compact_list(chapter.get("mapped_risks") or [], limit=profile.risk_limit)}

章节写作计划：
- 建议篇幅：{writing_plan.get("suggested_pages") or "需人工复核"} 页
- 是否需要表格：{"是" if writing_plan.get("needs_table") else "否"}
- 是否需要图片/流程图：{"是" if writing_plan.get("needs_image") else "否"}
- 是否需要资质材料：{"是" if writing_plan.get("needs_qualification") else "否"}
- 是否需要业绩支撑：{"是" if writing_plan.get("needs_case") else "否"}
- 写作策略：{writing_plan.get("strategy") or "需人工复核"}

当前草稿末尾节选：
{draft_excerpt or "暂无"}
""".strip()
    prompt, _ = enforce_prompt_budget(prompt, profile)
    return prompt


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
    profile = classify_section_prompt_profile(chapter)
    context_budget = build_section_context_budget(profile, chapter)
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

    enterprise_context = (
        build_enterprise_context()
        if profile.include_enterprise_profile
        else "- 当前 prompt profile 不加载完整企业画像；仅保留投标主体和事实边界约束。"
    )
    supporting_assets = _compact_supporting_assets(chapter, volume_type, limit=context_budget["asset_limit"])
    rag_context = _compact_section_rag_context(project, analysis, chapter, limit=context_budget["rag_limit"])
    grounding_instructions = _grounding_instructions(chapter)
    confirmed_variables = _confirmed_prefill_text(project_meta)
    taichang_facts = _taichang_fact_digest(profile.fact_pack_mode)

    prompt = f"""
你是资深投标文件撰写专家，熟悉电网/电力工程、设备供货、安装调试、试验检测、运维检修、质量安全管理和招投标文件格式要求。
企业画像：
{enterprise_context}

请为当前投标章节生成可直接放入标书的正文草稿。

写作要求：
1. 只输出章节正文，不要解释你如何生成。
2. 语言正式、稳健、可落地，符合国内投标文件表达习惯。
3. 不要编造企业没有提供的证书编号、人员姓名、合同金额、具体日期；已核验事实必须直接填写，不得再次留空。
4. 必须回应章节目标、响应要点、评分项和风险点。
5. {"如适合表格，用 Markdown 表格输出。" if profile.allow_table else "本章节以正文段落为主，除非招标文件强制要求，不主动铺开大表格。"}
6. 正文字数按章节写作计划控制。本次生成尽量覆盖完整章节；若目标字数较长，可先输出结构完整的第一版，并保留可续写的小标题。
7. 必须遵守当前分册策略，尤其是金额、证书、人员、日期、签章、保证金和报价信息的禁编造约束。
8. 正式标书正文不得使用 emoji、图标符号或装饰性提示符；“关键提醒”“风险提示”等内容必须使用纯文字标题。
9. 不得为了凑页数重复同义段落、塞入无关内容或虚构资料；未知客户决策不得展开成大面积空表，每章最多保留 3 个合并后的“【待补充：...】”，其余集中写入简短人工确认清单。
10. 必须优先依据“章节级 RAG 写作依据”和“关联要求/评分项/风险提醒”写作；RAG 未覆盖的企业事实不得编造。
11. 下列用户确认变量必须直接使用，不得再次输出为【待补充】；未确认字段不得推断。

用户已确认投标变量：
{confirmed_variables}

泰昌已核验企业事实（必须优先直接使用）：
{taichang_facts}

项目信息：
- 项目名称：{context["project_name"] or "需人工复核"}
- 招标编号：{context["tender_no"] or "需人工复核"}
- 项目摘要：{context["summary"] or "需人工复核"}

当前章节：
- 所属分册：{context["volume_name"]}（{context["volume_type"]}）
- 标题：{title}
- 编写目标：{purpose or "需人工复核"}
- 来源页码：{context["source_pages"] or "需人工复核"}
- Prompt profile：{profile.label}（{profile.name}）
- 输入预算：prompt≤{profile.max_prompt_chars} 字符；RAG {context_budget["rag_limit"]} 条；企业资料 {context_budget["asset_limit"]} 条；事实包模式 {profile.fact_pack_mode}

分册写作策略：
{_compact_list(context["volume_strategy"].get("focus"), limit=8)}

分册强制约束：
{_compact_list(context["volume_strategy"].get("constraints"), limit=8)}

资料召回侧重点：
- {context["volume_strategy"].get("retrieval_hint") or "按章节标题和响应要点召回资料。"}

当前命中的企业资料候选：
{supporting_assets}

本次专项事实与边界约束：
{grounding_instructions}

章节级 RAG 写作依据：
{rag_context}

图片/附件策略：
- {context["volume_strategy"].get("image_policy") or "仅在章节明确需要时插入。"}

章节写作计划：
- 重要性：{writing_plan.get("importance") or "medium"}
- 目标字数：{writing_plan.get("target_words") or "需人工复核"} 字
- 硬性篇幅上限：{_hard_length_cap_words(chapter) or "按目标字数合理控制"} 字，超过后系统会截流保存
- 建议篇幅：{writing_plan.get("suggested_pages") or "需人工复核"} 页
- 生成方式：{writing_plan.get("generation_mode") or "single_pass"}
- 资料不足策略：{"允许围绕评分点和可验证措施扩写" if _allow_auto_expand(chapter) else "稳健生成，缺失处使用待补充占位"}
- 是否需要表格：{"是" if writing_plan.get("needs_table") else "否"}
- 是否需要图片/流程图：{"是" if writing_plan.get("needs_image") else "否"}
- 是否需要资质材料：{"是" if writing_plan.get("needs_qualification") else "否"}
- 是否需要业绩支撑：{"是" if writing_plan.get("needs_case") else "否"}
- 写作策略：{writing_plan.get("strategy") or "需人工复核"}

响应要点：
{_compact_list(context["response_points"], limit=profile.requirement_limit)}

关联要求：
{_compact_list(context["mapped_requirements"], limit=profile.requirement_limit)}

关联评分项：
{_compact_list(context["mapped_scoring_items"], limit=profile.scoring_limit)}

风险提醒：
{_compact_list(context["mapped_risks"], limit=profile.risk_limit)}

需要准备的资料：
{_compact_list(context["required_materials"], limit=profile.material_limit)}

写作注意事项：
{_compact_list(context["writing_notes"], limit=profile.writing_note_limit)}
""".strip()
    prompt, _ = enforce_prompt_budget(prompt, profile)
    return prompt


def _placeholder_label(token: str) -> str:
    text = token.strip("【】{}$ ")
    text = re.sub(r"^待(?:补充|填写|确认|核对)\s*[:：]?", "", text).strip()
    return text


def _generic_placeholder_for_section(chapter: dict[str, Any]) -> str:
    title = str(chapter.get("title") or "")
    if "附件" in title or "页码" in title:
        return "【待补充：附件页码索引待最终目录页码生成后填写】"
    if "投标函" in title:
        return "【待补充：投标函关键字段由客户最终确认】"
    if "商务承诺" in title:
        return "【待补充：商务承诺签章日期及客户最终承诺口径】"
    if "产品制造" in title or "质量控制" in title:
        return "【待补充：响应时间及产能数据待客户最终确认】"
    return "【待补充：本节客户决策字段待最终确认】"


def compact_formal_placeholders(
    chapter: dict[str, Any],
    content: str,
    *,
    max_placeholders: int = 3,
) -> tuple[str, dict[str, Any]]:
    """Collapse repeated placeholders so the exported bid reads as a formal draft."""
    original = content or ""
    tokens = FORMAL_PLACEHOLDER_RE.findall(original)
    if len(tokens) <= max_placeholders:
        return original, {
            "compacted": False,
            "before_placeholders": len(tokens),
            "placeholders": len(tokens),
        }

    kept: list[str] = []
    has_generic = False
    for token in tokens:
        label = _placeholder_label(token)
        is_generic = label in GENERIC_PLACEHOLDER_LABELS
        if is_generic:
            has_generic = True
            continue
        if token not in kept and len(kept) < max_placeholders:
            kept.append(token)

    if has_generic and len(kept) < max_placeholders:
        kept.insert(0, _generic_placeholder_for_section(chapter))

    seen_keep: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        label = _placeholder_label(token)
        is_generic = label in GENERIC_PLACEHOLDER_LABELS
        if is_generic:
            generic = _generic_placeholder_for_section(chapter)
            if generic in kept and generic not in seen_keep:
                seen_keep.add(generic)
                return generic
            return "客户确认后填写"
        if token in kept and token not in seen_keep:
            seen_keep.add(token)
            return token
        return f"客户确认后填写（{label}）" if label else "客户确认后填写"

    compacted = FORMAL_PLACEHOLDER_RE.sub(replace, original)
    compacted = re.sub(r"(客户确认后填写)(?:[、，,；;]\s*\1)+", r"\1", compacted)
    after = len(FORMAL_PLACEHOLDER_RE.findall(compacted))
    return compacted, {
        "compacted": compacted != original,
        "before_placeholders": len(tokens),
        "placeholders": after,
        "placeholder_compaction_replacements": len(tokens) - after,
    }


def rewrite_generated_section_for_formal_quality(
    project_id: str,
    chapter: dict[str, Any],
    content: str,
) -> tuple[str, dict[str, Any]]:
    content, compaction_report = compact_formal_placeholders(chapter, content)
    placeholder_count = len(re.findall(r"【\s*待(?:补充|填写|确认|核对)", content or ""))
    forbidden_topics = ["施工组织", "建造师", "安全生产许可证", "BIM", "水利施工", "安装总承包"]
    forbidden_hits = [topic for topic in forbidden_topics if topic in (content or "")]
    if placeholder_count <= 3 and not forbidden_hits:
        return content, {"rewritten": False, "placeholders": placeholder_count, "forbidden_hits": [], **compaction_report}

    payload = get_project_interpretation(project_id)
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") or {}
    confirmed_variables = _confirmed_prefill_text(project_meta)
    taichang_facts = build_taichang_verified_fact_context()
    title = _text(chapter.get("title")) or "未命名章节"
    prompt = f"""
你是正式投标文件终审人员。请重写下面章节，使其可直接进入河北泰昌电力器材科技有限公司的电缆保护管物资投标文件。

硬性要求：
1. 保留章节核心响应内容和必要 Markdown 表格，但删除泛化、重复和与物资供货无关的内容。
2. 已核验事实必须直接填写；不得把已知企业名称、信用代码、法人、证书、报告编号、产品参数和真实业绩继续写成待补充。
3. 全章最多保留 3 个合并后的【待补充：...】，仅限本次包号/包名称、报价/税率、保证金、授权签章日期、最终交货期/质保期等客户决策。不得把整张表铺满占位符。
4. 删除施工组织、建造师、安全生产许可证、BIM、水利施工、安装总承包等与本次电缆保护管物资供货无关内容。
5. 河北豪乾资料只参考目录和表式，不得引用其企业事实、专利、供应商、人员、证书或业绩。
6. 只输出重写后的完整章节正文，不要解释。

章节标题：{title}

用户已确认变量：
{confirmed_variables}

泰昌已核验事实：
{taichang_facts}

待终审正文：
{content}
""".strip()
    response = call_dashscope_api(
        [{"role": "user", "content": prompt}],
        model=get_stage_model("section_writing"),
        json_mode=False,
        usage_context={
            "project_id": project_id,
            "section_id": chapter.get("id"),
            "stage": "bid_section_formal_quality_rewrite",
            "metadata": {"chapter_title": title, "before_placeholders": placeholder_count},
        },
    )
    rewritten = str(response["output"]["choices"][0]["message"]["content"] or "").strip()
    if not rewritten:
        return content, {"rewritten": False, "placeholders": placeholder_count, "forbidden_hits": forbidden_hits, **compaction_report}
    after_placeholders = len(re.findall(r"【\s*待(?:补充|填写|确认|核对)", rewritten))
    after_forbidden = [topic for topic in forbidden_topics if topic in rewritten]
    if after_placeholders > placeholder_count or len(after_forbidden) > len(forbidden_hits):
        return content, {"rewritten": False, "placeholders": placeholder_count, "forbidden_hits": forbidden_hits, **compaction_report}
    return rewritten, {
        "rewritten": True,
        "before_placeholders": placeholder_count,
        "placeholders": after_placeholders,
        "forbidden_hits": after_forbidden,
        "placeholder_compaction": compaction_report,
    }


def stream_bid_section(project_id: str, chapter: dict[str, Any]) -> Iterator[dict[str, Any]]:
    continuation_draft = _continuation_draft(chapter)
    profile = classify_section_prompt_profile(chapter, continuation=bool(continuation_draft))
    prompt = (
        build_section_continuation_prompt(project_id, chapter, continuation_draft)
        if continuation_draft
        else build_section_prompt(project_id, chapter)
    )
    yield {
        "type": "start",
        "title": chapter.get("title") or "未命名章节",
        "prompt_profile": profile.name,
        "prompt_profile_label": profile.label,
        "prompt_chars": len(prompt),
        "max_prompt_chars": profile.max_prompt_chars,
        "rag_limit": profile.rag_limit,
        "asset_limit": profile.asset_limit,
        "fact_pack_mode": profile.fact_pack_mode,
    }

    emitted = False
    generated_content = continuation_draft
    try:
        stream_monitor = _SectionStreamMonitor(profile)
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
                    "prompt_profile": profile.name,
                    "prompt_chars": len(prompt),
                    "max_prompt_chars": profile.max_prompt_chars,
                },
            },
        ):
            emitted = True
            generated_content += chunk
            yield {
                "type": "chunk",
                "content": chunk,
            }
            metric_event, slow_error = stream_monitor.record_chunk(chunk)
            if metric_event:
                yield {
                    "type": "stream_metric",
                    **metric_event,
                }
            if slow_error:
                raise slow_error
            cap_reached, max_words, actual_words = _length_cap_reached(generated_content, chapter)
            if cap_reached:
                yield {
                    "type": "length_cap_reached",
                    "target_words": _target_words(chapter),
                    "max_words": max_words,
                    "actual_words": actual_words,
                }
                break
        final_metric = stream_monitor.finish()
        if final_metric:
            yield {
                "type": "stream_metric",
                **final_metric,
            }
    except Exception as exc:
        if _is_stream_timeout_error(exc):
            raise
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
                    "prompt_profile": profile.name,
                    "prompt_chars": len(prompt),
                    "max_prompt_chars": profile.max_prompt_chars,
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
            cap_reached, max_words, actual_words = _length_cap_reached(generated_content, chapter)
            if cap_reached:
                yield {
                    "type": "length_cap_reached",
                    "target_words": _target_words(chapter),
                    "max_words": max_words,
                    "actual_words": actual_words,
                }
                break

    if not emitted:
        yield {
            "type": "chunk",
            "content": "【待补充：当前章节正文生成失败，请稍后重新生成。】",
        }
        generated_content = "【待补充：当前章节正文生成失败，请稍后重新生成。】"

    cap_reached, _, _ = _length_cap_reached(generated_content, chapter)
    if emitted and not cap_reached and _needs_length_supplement(generated_content, chapter):
        supplement_prompt = build_section_supplement_prompt(project_id, chapter, generated_content)
        supplement_profile = classify_section_prompt_profile(chapter)
        supplement_prefix = "\n\n"
        generated_content += supplement_prefix
        yield {
            "type": "chunk",
            "content": supplement_prefix,
        }
        try:
            supplement_monitor = _SectionStreamMonitor(supplement_profile)
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
                        "prompt_profile": supplement_profile.name,
                        "prompt_chars": len(supplement_prompt),
                        "max_prompt_chars": supplement_profile.max_prompt_chars,
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
                metric_event, slow_error = supplement_monitor.record_chunk(chunk)
                if metric_event:
                    yield {
                        "type": "stream_metric",
                        **metric_event,
                    }
                if slow_error:
                    raise slow_error
                cap_reached, max_words, actual_words = _length_cap_reached(generated_content, chapter)
                if cap_reached:
                    yield {
                        "type": "length_cap_reached",
                        "target_words": _target_words(chapter),
                        "max_words": max_words,
                        "actual_words": actual_words,
                    }
                    break
            final_metric = supplement_monitor.finish()
            if final_metric:
                yield {
                    "type": "stream_metric",
                    **final_metric,
                }
        except Exception as exc:
            if _is_stream_timeout_error(exc):
                raise
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
                            "prompt_profile": supplement_profile.name,
                            "prompt_chars": len(supplement_prompt),
                            "max_prompt_chars": supplement_profile.max_prompt_chars,
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
                    cap_reached, max_words, actual_words = _length_cap_reached(generated_content, chapter)
                    if cap_reached:
                        yield {
                            "type": "length_cap_reached",
                            "target_words": _target_words(chapter),
                            "max_words": max_words,
                            "actual_words": actual_words,
                        }
                        break
            except Exception:
                logging.exception("章节篇幅补写失败，保留首轮生成内容: %s", chapter.get("id"))

    yield {
        "type": "done",
    }

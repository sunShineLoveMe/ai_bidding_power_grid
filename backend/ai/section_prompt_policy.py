from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.bid_volumes import section_volume_type


@dataclass(frozen=True)
class SectionPromptProfile:
    name: str
    label: str
    context_level: str
    max_prompt_chars: int
    rag_limit: int
    asset_limit: int
    fact_pack_mode: str
    allow_table: bool
    requirement_limit: int = 6
    scoring_limit: int = 4
    risk_limit: int = 4
    material_limit: int = 5
    writing_note_limit: int = 4
    include_enterprise_profile: bool = True
    continuation_mode: bool = False

    def to_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "context_level": self.context_level,
            "max_prompt_chars": self.max_prompt_chars,
            "rag_limit": self.rag_limit,
            "asset_limit": self.asset_limit,
            "fact_pack_mode": self.fact_pack_mode,
            "allow_table": self.allow_table,
            "continuation_mode": self.continuation_mode,
        }


PROMPT_PROFILES: dict[str, SectionPromptProfile] = {
    "simple_plan": SectionPromptProfile(
        name="simple_plan",
        label="轻量方案",
        context_level="slim",
        max_prompt_chars=5000,
        rag_limit=1,
        asset_limit=1,
        fact_pack_mode="identity_only",
        allow_table=False,
        requirement_limit=4,
        scoring_limit=2,
        risk_limit=2,
        material_limit=3,
        writing_note_limit=3,
        include_enterprise_profile=True,
    ),
    "fact_grounded": SectionPromptProfile(
        name="fact_grounded",
        label="事实支撑",
        context_level="grounded",
        max_prompt_chars=9000,
        rag_limit=3,
        asset_limit=4,
        fact_pack_mode="certifications",
        allow_table=True,
        requirement_limit=6,
        scoring_limit=4,
        risk_limit=4,
        material_limit=5,
        writing_note_limit=4,
        include_enterprise_profile=True,
    ),
    "technical_parameter": SectionPromptProfile(
        name="technical_parameter",
        label="技术参数",
        context_level="technical",
        max_prompt_chars=11000,
        rag_limit=4,
        asset_limit=3,
        fact_pack_mode="product_parameters",
        allow_table=True,
        requirement_limit=7,
        scoring_limit=5,
        risk_limit=4,
        material_limit=5,
        writing_note_limit=4,
        include_enterprise_profile=True,
    ),
    "structured_table": SectionPromptProfile(
        name="structured_table",
        label="结构化表格",
        context_level="table",
        max_prompt_chars=7000,
        rag_limit=2,
        asset_limit=1,
        fact_pack_mode="product_parameters",
        allow_table=True,
        requirement_limit=5,
        scoring_limit=3,
        risk_limit=3,
        material_limit=4,
        writing_note_limit=4,
        include_enterprise_profile=False,
    ),
    "attachment_index": SectionPromptProfile(
        name="attachment_index",
        label="附件索引",
        context_level="minimal",
        max_prompt_chars=4000,
        rag_limit=1,
        asset_limit=1,
        fact_pack_mode="minimal_constraints",
        allow_table=True,
        requirement_limit=3,
        scoring_limit=1,
        risk_limit=2,
        material_limit=6,
        writing_note_limit=3,
        include_enterprise_profile=False,
    ),
    "price_sensitive": SectionPromptProfile(
        name="price_sensitive",
        label="报价敏感",
        context_level="minimal",
        max_prompt_chars=4000,
        rag_limit=1,
        asset_limit=0,
        fact_pack_mode="minimal_constraints",
        allow_table=True,
        requirement_limit=4,
        scoring_limit=2,
        risk_limit=3,
        material_limit=3,
        writing_note_limit=3,
        include_enterprise_profile=False,
    ),
    "continuation_slim": SectionPromptProfile(
        name="continuation_slim",
        label="草稿续写",
        context_level="continuation",
        max_prompt_chars=4500,
        rag_limit=0,
        asset_limit=0,
        fact_pack_mode="minimal_constraints",
        allow_table=True,
        requirement_limit=3,
        scoring_limit=2,
        risk_limit=2,
        material_limit=2,
        writing_note_limit=3,
        include_enterprise_profile=False,
        continuation_mode=True,
    ),
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    return str(value)


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _profile_hint(chapter: dict[str, Any]) -> str:
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    options = metadata.get("generation_options") if isinstance(metadata.get("generation_options"), dict) else {}
    writing_plan = metadata.get("writing_plan") if isinstance(metadata.get("writing_plan"), dict) else {}
    for source in (options, writing_plan, metadata, chapter):
        value = source.get("prompt_profile") or source.get("promptProfile") or source.get("profile_hint") or source.get("profileHint")
        if str(value or "") in PROMPT_PROFILES:
            return str(value)
    return ""


def classify_section_prompt_profile(
    chapter: dict[str, Any],
    *,
    continuation: bool = False,
) -> SectionPromptProfile:
    if continuation:
        return PROMPT_PROFILES["continuation_slim"]

    explicit = _profile_hint(chapter)
    if explicit and explicit != "continuation_slim":
        return PROMPT_PROFILES[explicit]

    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    writing_plan = metadata.get("writing_plan") if isinstance(metadata.get("writing_plan"), dict) else {}
    volume_type = section_volume_type(chapter)
    combined = " ".join(
        _text(value)
        for value in [
            chapter.get("title"),
            chapter.get("purpose"),
            chapter.get("response_points"),
            chapter.get("mapped_requirements"),
            chapter.get("mapped_scoring_items"),
            chapter.get("mapped_risks"),
            chapter.get("required_materials"),
            chapter.get("writing_notes"),
            writing_plan.get("strategy"),
        ]
    )

    if _contains_any(combined, ["附件索引", "附件清单", "证明材料索引", "页码索引", "目录索引", "材料索引"]):
        return PROMPT_PROFILES["attachment_index"]

    if volume_type == "price" or _contains_any(combined, ["报价", "单价", "总价", "税率", "保证金", "报价文件", "价格", "造价"]):
        return PROMPT_PROFILES["price_sensitive"]

    parameter_keywords = [
        "技术参数",
        "技术特性",
        "检验报告",
        "检测报告",
        "型式试验",
        "投标人保证值",
        "标准参数值",
        "项目需求值",
        "保证值",
        "CPVC",
        "MPP",
        "环刚度",
        "平均内径",
        "壁厚",
        "生产制造",
        "试验检测",
        "质量控制",
    ]
    if _contains_any(combined, parameter_keywords):
        return PROMPT_PROFILES["technical_parameter"]

    table_keywords = ["偏差表", "响应表", "一览表", "明细表", "清单", "表格", "配置表", "核对表"]
    if _contains_any(combined, table_keywords) or writing_plan.get("needs_table"):
        return PROMPT_PROFILES["structured_table"]

    fact_keywords = [
        "资格",
        "资信",
        "资质",
        "证书",
        "营业执照",
        "体系认证",
        "授权",
        "人员",
        "社保",
        "业绩",
        "合同",
        "中标通知",
        "财务",
        "信誉",
    ]
    if volume_type == "qualification" or _contains_any(combined, fact_keywords):
        return PROMPT_PROFILES["fact_grounded"]

    simple_keywords = [
        "编制依据",
        "工程概况",
        "项目概况",
        "总体部署",
        "组织机构",
        "实施方法",
        "进度安排",
        "总体说明",
        "服务方案",
        "工作流程",
        "工作计划",
    ]
    if _contains_any(combined, simple_keywords):
        return PROMPT_PROFILES["simple_plan"]

    return PROMPT_PROFILES["simple_plan"]


def build_section_context_budget(profile: SectionPromptProfile, chapter: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": profile.name,
        "max_prompt_chars": profile.max_prompt_chars,
        "rag_limit": max(0, int(profile.rag_limit)),
        "asset_limit": max(0, int(profile.asset_limit)),
        "fact_pack_mode": profile.fact_pack_mode,
        "allow_table": bool(profile.allow_table),
        "limits": {
            "requirements": profile.requirement_limit,
            "scoring_items": profile.scoring_limit,
            "risks": profile.risk_limit,
            "materials": profile.material_limit,
            "writing_notes": profile.writing_note_limit,
        },
    }


def enforce_prompt_budget(prompt: str, profile: SectionPromptProfile) -> tuple[str, dict[str, Any]]:
    text = prompt.strip()
    original_chars = len(text)
    max_chars = max(1200, int(profile.max_prompt_chars or 0))
    if original_chars <= max_chars:
        return text, {
            "profile": profile.name,
            "max_prompt_chars": max_chars,
            "prompt_chars": original_chars,
            "original_prompt_chars": original_chars,
            "truncated": False,
        }

    marker = (
        "\n\n[系统已按 Prompt Profile 输入预算裁剪部分低优先级上下文；"
        "生成时必须优先使用保留的客户确认变量、泰昌事实和章节约束。]\n\n"
    )
    head_chars = max(800, int(max_chars * 0.68))
    tail_chars = max(300, max_chars - head_chars - len(marker))
    clipped = (text[:head_chars].rstrip() + marker + text[-tail_chars:].lstrip()).strip()
    if len(clipped) > max_chars:
        clipped = clipped[:max_chars].rstrip()
    return clipped, {
        "profile": profile.name,
        "max_prompt_chars": max_chars,
        "prompt_chars": len(clipped),
        "original_prompt_chars": original_chars,
        "truncated": True,
        "truncated_chars": original_chars - len(clipped),
    }

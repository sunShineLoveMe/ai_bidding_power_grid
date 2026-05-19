from typing import Any


VOLUME_DEFINITIONS: dict[str, dict[str, str]] = {
    "all": {
        "name": "全部",
        "description": "完整投标文件",
    },
    "technical": {
        "name": "技术标",
        "description": "施工组织设计、技术响应、质量安全环保、进度资源和设备方案",
    },
    "business": {
        "name": "商务标",
        "description": "投标函、商务条款响应、偏离表、承诺函和合同响应",
    },
    "qualification": {
        "name": "资格文件",
        "description": "营业执照、资质证书、人员证书、业绩和信誉声明",
    },
    "price": {
        "name": "报价文件",
        "description": "工程量清单、投标报价、分项报价和单价分析",
    },
    "attachment": {
        "name": "附件材料",
        "description": "图纸、证照扫描件、产品图片、业绩证明和其他附件",
    },
    "other": {
        "name": "其他",
        "description": "未能自动归类的其他响应材料",
    },
}

VOLUME_ORDER = ["qualification", "business", "technical", "price", "attachment", "other"]

VOLUME_ALIASES: dict[str, str] = {
    "technical": "technical",
    "技术": "technical",
    "技术标": "technical",
    "技术文件": "technical",
    "技术响应": "technical",
    "技术响应文件": "technical",
    "施工组织设计": "technical",
    "business": "business",
    "商务": "business",
    "商务标": "business",
    "商务文件": "business",
    "商务响应": "business",
    "商务响应文件": "business",
    "qualification": "qualification",
    "资格": "qualification",
    "资信": "qualification",
    "资格文件": "qualification",
    "资格审查": "qualification",
    "资格审查资料": "qualification",
    "企业资信": "qualification",
    "企业资信库": "qualification",
    "price": "price",
    "报价": "price",
    "报价文件": "price",
    "工程量清单": "price",
    "投标报价": "price",
    "attachment": "attachment",
    "附件": "attachment",
    "附件材料": "attachment",
    "附件册": "attachment",
    "other": "other",
    "其他": "other",
}

VOLUME_GENERATION_STRATEGIES: dict[str, dict[str, Any]] = {
    "technical": {
        "focus": [
            "围绕施工组织、技术方案、关键工序、质量安全环保、进度资源、设备配置展开。",
            "优先回应技术标准、发包人要求、评分办法和实施风险。",
            "可以使用施工方案、标准话术、产品库、设备图片和工艺流程作为支撑。",
        ],
        "constraints": [
            "不得把商务承诺、投标函格式内容写成技术方案主体。",
            "涉及设备参数、工艺指标和施工资源时，缺失数据必须使用【待补充：...】。",
            "流程图、产品图、设备图只作为辅助说明，不能替代文字响应。",
        ],
        "retrieval_hint": "优先召回施工方案、技术标准话术、产品库、设备图片、工艺流程和质量安全环保资料。",
        "image_policy": "可以自动插入产品图、设备图、工艺图、施工现场示意图；图片应与章节技术内容直接相关。",
    },
    "business": {
        "focus": [
            "围绕投标函、合同条款响应、商务偏离表、承诺函、服务承诺和履约安排展开。",
            "表达应短而准，优先保证格式响应和实质性条款不遗漏。",
            "商务条款应逐项响应付款、履约、税费、廉政、保密、服务等要求。",
        ],
        "constraints": [
            "不得编造金额、日期、签章、保证金账号、保函编号、合同编号。",
            "金额、日期、签章、保证金等信息必须使用【待补充：人工复核】类占位符。",
            "不要插入与商务条款无关的产品图或施工图。",
        ],
        "retrieval_hint": "优先召回商务条款话术、合同响应模板、承诺函模板、偏离表和历史商务响应。",
        "image_policy": "默认谨慎插图；仅当章节明确为格式附件、证明材料或用户要求图文导出时才插入证明类图片。",
    },
    "qualification": {
        "focus": [
            "围绕营业执照、资质证书、安全生产许可证、人员证书、业绩证明和信誉声明展开。",
            "正文应说明资料组成、响应关系、有效性复核点和附件索引。",
            "优先引用企业资信库、证照图片、人员资料、业绩材料。",
        ],
        "constraints": [
            "不得编造证书编号、人员姓名、身份证号、注册编号、合同金额、业绩日期。",
            "缺失证照、人员、业绩信息必须使用【待补充：...】并提示人工替换。",
            "插入图片时必须标明样张、脱敏或需人工替换，不得表述为正式原件。",
        ],
        "retrieval_hint": "优先召回企业资信库、证照图片、人员证书、业绩证明、信誉声明和社保资料。",
        "image_policy": "可以插入证照、证书、业绩证明样张；必须提示脱敏样张/需替换，不替代正式法定文件。",
    },
    "price": {
        "focus": [
            "围绕报价口径、工程量清单、分项报价说明、税费口径、单价分析和风险边界展开。",
            "重点说明报价依据、人工复核点、暂估价/暂列金/清单差异风险。",
            "正文以说明和复核提示为主，不替代造价人员填报。",
        ],
        "constraints": [
            "禁止编造任何具体金额、单价、总价、税率、工程量和报价汇总。",
            "涉及金额或清单数据时必须使用【待补充：造价人员复核】。",
            "报价文件默认不自动插图，除非用户明确要求。",
        ],
        "retrieval_hint": "优先召回报价说明、工程量清单模板、报价风险提示、税费和单价分析口径。",
        "image_policy": "默认不插图；只在明确需要清单截图或格式附件时由用户人工确认。",
    },
    "attachment": {
        "focus": [
            "汇总需要提交的附件清单，说明附件来源、适用章节、是否缺失和替换要求。",
            "按资格、商务、技术、报价等分册建立索引，便于评审查找。",
            "对缺失附件给出人工补齐提示。",
        ],
        "constraints": [
            "不得把附件清单写成正式证照或业绩事实。",
            "所有缺失附件必须明确标记【待补充】。",
            "图片和附件应保留来源、用途和是否脱敏说明。",
        ],
        "retrieval_hint": "优先召回企业资信库、产品库、图纸、证照扫描件、业绩证明和其他附件资产。",
        "image_policy": "可以按附件清单插入相关图片或证明样张，并标明来源和替换要求。",
    },
    "other": {
        "focus": [
            "围绕章节目标和招标文件要求形成稳健响应。",
            "无法确认所属分册时，应提示人工复核章节归属。",
        ],
        "constraints": [
            "不得编造企业事实、金额、证书编号、人员姓名和具体日期。",
            "缺失信息统一使用【待补充：...】。",
        ],
        "retrieval_hint": "按章节标题和响应要点召回相关知识库资料。",
        "image_policy": "仅当章节明确需要图片或附件时插入。",
    },
}


def _text(value: Any) -> str:
    return str(value) if value is not None else ""


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def normalize_volume_type(value: Any) -> str:
    volume_type = _text(value).strip().lower()
    if volume_type in VOLUME_ALIASES:
        return VOLUME_ALIASES[volume_type]
    raw_text = _text(value).strip()
    if raw_text in VOLUME_ALIASES:
        return VOLUME_ALIASES[raw_text]
    return volume_type if volume_type in VOLUME_DEFINITIONS and volume_type != "all" else "other"


def normalize_volume_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = [item.strip() for item in values.replace("，", ",").split(",")]
    elif isinstance(values, (list, tuple, set)):
        raw_values = list(values)
    else:
        raw_values = [values]
    normalized: list[str] = []
    for value in raw_values:
        volume_type = normalize_volume_type(value)
        if volume_type != "other" and volume_type not in normalized:
            normalized.append(volume_type)
    return normalized


def asset_applicable_volumes(asset: dict[str, Any]) -> list[str]:
    values = asset.get("applicable_volumes")
    if not values:
        specs = asset.get("specs") if isinstance(asset.get("specs"), dict) else {}
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        values = specs.get("applicable_volumes") or metadata.get("applicable_volumes")
    return normalize_volume_list(values)


def asset_matches_volume(asset: dict[str, Any], volume_type: Any, *, allow_unscoped: bool = True) -> bool:
    target = normalize_volume_type(volume_type)
    if target == "other":
        return True
    volumes = asset_applicable_volumes(asset)
    if not volumes:
        return allow_unscoped
    if target in volumes:
        return True
    if target == "qualification" and "attachment" in volumes:
        return True
    if target == "business" and any(item in volumes for item in ["qualification", "attachment"]):
        return True
    return False


def volume_name(volume_type: Any) -> str:
    return VOLUME_DEFINITIONS.get(normalize_volume_type(volume_type), VOLUME_DEFINITIONS["other"])["name"]


def volume_description(volume_type: Any) -> str:
    return VOLUME_DEFINITIONS.get(normalize_volume_type(volume_type), VOLUME_DEFINITIONS["other"])["description"]


def volume_generation_strategy(volume_type: Any) -> dict[str, Any]:
    return VOLUME_GENERATION_STRATEGIES.get(
        normalize_volume_type(volume_type),
        VOLUME_GENERATION_STRATEGIES["other"],
    )


def infer_volume_type(section: dict[str, Any]) -> str:
    metadata = section.get("metadata") if isinstance(section.get("metadata"), dict) else {}
    existing = metadata.get("volume_type")
    if existing and _text(existing).strip().lower() in VOLUME_DEFINITIONS:
        return normalize_volume_type(existing)

    title = _text(section.get("title"))
    purpose = _text(section.get("purpose"))
    materials = " ".join(_text(item) for item in section.get("required_materials") or [])
    response_points = " ".join(_text(item) for item in section.get("response_points") or [])
    combined = f"{title} {purpose} {materials} {response_points}"

    if _contains_any(combined, ["资格", "资质", "证书", "营业执照", "安全生产许可", "人员", "项目经理", "技术负责人", "业绩", "信誉", "社保", "建造师"]):
        return "qualification"
    if _contains_any(combined, ["商务", "合同", "付款", "履约", "服务", "税费", "廉政", "保密", "偏离", "承诺", "投标函", "授权委托", "保证金"]):
        return "business"
    if _contains_any(combined, ["报价", "清单", "价格", "单价", "工程量", "投标总价", "分项报价"]):
        return "price"
    if _contains_any(combined, ["施工组织", "技术", "实施方案", "施工方案", "质量", "安全", "环保", "进度", "资源配置", "发包人要求", "承包人建议", "设备", "工艺", "调试"]):
        return "technical"
    if _contains_any(combined, ["附件", "图纸", "扫描件", "证明材料", "附录", "图片", "图册"]):
        return "attachment"
    return "other"


def ensure_section_volume(section: dict[str, Any]) -> dict[str, Any]:
    volume_type = infer_volume_type(section)
    metadata = section.get("metadata") if isinstance(section.get("metadata"), dict) else {}
    return {
        **section,
        "metadata": {
            **metadata,
            "volume_type": volume_type,
            "volume_name": metadata.get("volume_name") or volume_name(volume_type),
            "document_role": metadata.get("document_role") or "正文",
            "export_group": metadata.get("export_group") or f"{volume_name(volume_type)}文件",
        },
    }


def section_volume_type(section: dict[str, Any]) -> str:
    return infer_volume_type(section)


def delivery_volume_type(section: dict[str, Any]) -> str:
    """User-facing delivery package: technical vs business.

    Internally qualification, price, attachment and other remain useful for
    writing strategy and asset matching, but most tender documents present
    them under the business/commercial package.
    """
    return "technical" if section_volume_type(section) == "technical" else "business"

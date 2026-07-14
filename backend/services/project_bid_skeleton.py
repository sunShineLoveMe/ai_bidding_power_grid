"""当前招标文件驱动的项目级投标骨架。

历史标书只能参与差异对照，不能决定当前项目目录。该模块将招标文件格式表、
投标人须知和结构化解读结果归一为项目规则，再只把当前项目需要提交的章节
转换为写作大纲。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_SKELETON_PATH = PROJECT_ROOT / (
    "docs/development/taichang-bid-v1-data/taichang_historical_reference_skeleton.json"
)

RULE_STATUSES = {
    "required",
    "conditional",
    "inherited_from_prequalification",
    "supplement_allowed",
    "update_required",
    "not_applicable",
    "forbidden",
    "reference_only",
}
OUTLINE_STATUSES = {"required", "conditional", "update_required"}
VOLUME_LABELS = {"price": "价格文件", "business": "商务文件", "technical": "技术文件"}

_NUMBER_PREFIX = re.compile(
    r"^\s*(?:第[一二三四五六七八九十百]+[章节部分]|[一二三四五六七八九十]+[、.]|"
    r"[（(]?[一二三四五六七八九十0-9]+[）)、.]|\d+(?:\.\d+)*[、.]?)\s*"
)

_TITLE_CANONICAL_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("投标函及附件", ("投标函及附件", "投标函及投标函附录", "投标函")),
    ("货物清单报价汇总表", ("已标价货物清单行报价暨投标报价汇总表", "货物清单报价汇总表")),
    ("商务偏差表", ("商务偏差表",)),
    ("技术偏差表", ("技术偏差表",)),
    ("技术特性参数表", ("技术特性参数表", "技术参数表")),
    ("货物组件材料配置表", ("货物组件材料配置表", "组件材料配置表")),
    ("投标人基本情况表", ("投标人基本情况表", "企业基本情况表")),
    ("营业执照", ("企业法人营业执照", "营业执照", "事业单位法人证书")),
    ("资格证明文件", ("符合招标文件投标人资格要求的证明文件", "资格证明文件")),
    ("授权委托书", ("法定代表人授权委托书", "授权委托书", "法定代表人身份证明")),
    ("资格预审结果通知书", ("资格预审结果通知书",)),
    ("人员关系说明", ("投标人与国家电网公司系统人员关系说明", "人员关系说明")),
    ("生产装备", ("生产装备", "生产设备")),
    ("试验检测设备", ("调试试验场所、试验检测设备", "试验检测设备")),
    ("检测检验报告", ("检测检验报告", "型式试验报告", "检验报告")),
)


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _rule_inputs(payload: dict[str, Any]) -> dict[str, Any]:
    direct = payload.get("project_rule_inputs")
    if isinstance(direct, dict):
        return direct
    analysis = payload.get("analysis") or {}
    stored = (analysis.get("project_meta") or {}).get("project_rule_inputs")
    return stored if isinstance(stored, dict) else {}


def _normalize_title(value: Any) -> str:
    text = _NUMBER_PREFIX.sub("", _text(value))
    text = re.sub(r"[（(](?:格式|如有|若无不需提供|扫描件|适用于[^）)]*)[）)]", "", text)
    text = re.sub(r"[\s，,。；;：:、（）()《》\-_]", "", text)
    return text.lower()


def _canonical_title(value: Any) -> str:
    normalized = _normalize_title(value)
    for canonical, aliases in _TITLE_CANONICAL_GROUPS:
        if any(_normalize_title(alias) in normalized or normalized in _normalize_title(alias) for alias in aliases):
            return canonical
    return _NUMBER_PREFIX.sub("", _text(value))[:100]


def _project_source_file(payload: dict[str, Any]) -> str:
    rule_inputs = _rule_inputs(payload)
    if _text(rule_inputs.get("source_file")):
        return _text(rule_inputs.get("source_file"))
    files = payload.get("files") or []
    for row in files:
        if isinstance(row, dict) and _text(row.get("file_name")):
            return _text(row.get("file_name"))
    project = payload.get("project") or {}
    return f"{_text(project.get('project_name')) or '当前项目'}招标文件解析结果"


def _source(
    payload: dict[str, Any],
    *,
    section: str,
    page: int | None = None,
    document_role: str = "main_tender_file",
    detection_method: str = "semantic_clause_detection",
    confidence: float = 0.86,
    source_file: str | None = None,
    chapter_number: str | None = None,
) -> dict[str, Any]:
    return {
        "source_file": source_file or _project_source_file(payload),
        "source_section": section or "招标文件结构化解读",
        "source_page": page,
        "document_role": document_role,
        "detection_method": detection_method,
        "confidence": round(float(confidence), 2),
        "chapter_number": chapter_number,
    }


def _submission_scope(text: str, volume_type: str) -> str:
    if "按分标" in text or "按标段" in text:
        return "by_lot"
    if "按包" in text or "分包" in text:
        return "by_package"
    return "by_package" if volume_type == "price" else "by_lot"


def _rule_scope(submission_scope: str, text: str) -> str:
    if "按批次" in text:
        return "batch"
    return "package" if submission_scope == "by_package" else "lot"


def _row_status(row: dict[str, Any], full_text: str) -> tuple[str, str]:
    title = _text(row.get("title"))
    required_marker = _text(row.get("required_marker") or row.get("submit_marker"))
    direct_text = " ".join(_text(row.get(key)) for key in ("title", "condition"))
    title_window = _nearby_text(full_text, title, radius=240)
    if "投标保证金" in title and re.search(r"免收投标保证金|保证金.{0,12}(?:均)?不适用", full_text):
        return "not_applicable", "招标文件明确免收投标保证金或相关要求不适用"
    if re.search(r"不适用|无需提供|不需提供", direct_text):
        return "not_applicable", "招标文件明确本项目不适用或无需提供"
    if re.search(r"如有|若有|适用于|选择.*有偏差|有偏差.*上传", direct_text):
        return "conditional", "招标文件将本项列为条件适用"
    if required_marker in {"√", "是", "须", "必需", "需要"} or bool(row.get("required")):
        return "required", "招标文件格式清单标记为须提供"
    if row.get("strict_format_table"):
        return "not_applicable", "格式清单声明仅标记项须提供，本行未标记"
    if re.search(r"不适用|无需提供|不需提供", title_window):
        return "not_applicable", "招标文件明确本项目不适用或无需提供"
    if re.search(r"如有|若有|适用于|选择.*有偏差|有偏差.*上传", title_window):
        return "conditional", "招标文件将本项列为条件适用"
    return "reference_only", "仅发现格式或标题，尚无当前项目必交依据"


def _nearby_text(full_text: str, needle: str, *, radius: int = 320) -> str:
    if not needle:
        return ""
    position = full_text.find(needle)
    if position < 0:
        return ""
    return full_text[max(0, position - radius): position + len(needle) + radius]


def _payload_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for chunk in payload.get("documentChunks") or []:
        if isinstance(chunk, dict):
            parts.append(_text(chunk.get("content")))
    for key in ("requirements", "risks", "scoringItems"):
        for item in payload.get(key) or []:
            if isinstance(item, dict):
                parts.append(" ".join(_text(item.get(field)) for field in ("title", "content", "item", "requirement", "source_text")))
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") or {}
    ai_report = project_meta.get("ai_report") or {}
    for plan in ai_report.get("document_plan") or []:
        if isinstance(plan, dict):
            parts.append(" ".join(_text(plan.get(field)) for field in ("file_type", "description", "format")))
    rule_inputs = _rule_inputs(payload)
    parts.extend(_text(item) for item in rule_inputs.get("clauses") or [])
    return "\n".join(part for part in parts if part)


def _format_rows_from_ai_plan(payload: dict[str, Any]) -> list[dict[str, Any]]:
    analysis = payload.get("analysis") or {}
    ai_report = ((analysis.get("project_meta") or {}).get("ai_report") or {})
    rows: list[dict[str, Any]] = []
    for plan in ai_report.get("document_plan") or []:
        if not isinstance(plan, dict):
            continue
        file_type = _text(plan.get("file_type"))
        volume_type = "price" if "价格" in file_type else "technical" if "技术" in file_type else "business"
        description = _text(plan.get("description"))
        scope_text = f"{file_type} {description}"
        extracted_count = 0
        for title in re.split(r"[、，,；;]", description):
            title = _text(title)
            title = re.sub(r"^.*?(?:包括|包含|内含)[：:]?", "", title)
            title = title.split("。", 1)[0].strip()
            if title.count("（") != title.count("）") or title.count("(") != title.count(")"):
                continue
            if len(title) < 4 or len(title) > 80:
                continue
            if not any(token in title for token in ("表", "文件", "证明", "报告", "截图", "委托书", "承诺函", "说明", "投标函")):
                continue
            rows.append({
                "title": title,
                "volume_type": volume_type,
                "required": True,
                "required_marker": "√",
                "submission_scope": _submission_scope(scope_text, volume_type),
                "notes": description,
                "source_section": _text((plan.get("source") or {}).get("section")) or "投标文件组成",
                "detection_method": "structured_interpretation_document_plan_item",
                "confidence": 0.76,
            })
            extracted_count += 1
        if not extracted_count:
            rows.append({
                "title": f"招标文件要求的{VOLUME_LABELS[volume_type]}响应材料",
                "volume_type": volume_type,
                "required": True,
                "required_marker": "√",
                "submission_scope": _submission_scope(scope_text, volume_type),
                "notes": description,
                "source_section": _text((plan.get("source") or {}).get("section")) or "投标文件组成",
                "detection_method": "structured_interpretation_document_plan_fallback",
                "confidence": 0.72,
            })
    return rows


def _dedupe_rules(rules: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    status_rank = {
        "forbidden": 8,
        "not_applicable": 7,
        "update_required": 6,
        "required": 5,
        "inherited_from_prequalification": 4,
        "conditional": 3,
        "supplement_allowed": 2,
        "reference_only": 1,
    }
    for rule in rules:
        key = (str(rule.get("volume_type")), _canonical_title(rule.get("title")))
        existing = by_key.get(key)
        if not existing or status_rank.get(str(rule.get("status")), 0) > status_rank.get(str(existing.get("status")), 0):
            by_key[key] = rule
        elif existing:
            existing.setdefault("sources", []).extend(rule.get("sources") or [])
    return list(by_key.values())


def _make_rule(
    payload: dict[str, Any],
    *,
    rule_id: str,
    title: str,
    volume_type: str,
    status: str,
    reason: str,
    source: dict[str, Any],
    submission_scope: str,
    rule_scope: str | None = None,
    parent_key: str | None = None,
    sequence: str | None = None,
) -> dict[str, Any]:
    if status not in RULE_STATUSES:
        raise ValueError(f"不支持的项目规则状态: {status}")
    return {
        "rule_id": rule_id,
        "semantic_key": f"{volume_type}.{_canonical_title(title)}",
        "title": _NUMBER_PREFIX.sub("", _text(title)),
        "canonical_title": _canonical_title(title),
        "volume_type": volume_type,
        "status": status,
        "status_reason": reason,
        "rule_scope": rule_scope or _rule_scope(submission_scope, title),
        "submission_scope": submission_scope,
        "sequence": sequence,
        "parent_key": parent_key,
        "sources": [source],
        "confidence": source.get("confidence"),
    }


def build_project_rule_inventory(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从当前项目资料生成全量规则，含不适用与禁止项。"""
    full_text = _payload_text(payload)
    rule_inputs = _rule_inputs(payload)
    format_rows = [item for item in rule_inputs.get("format_rows") or [] if isinstance(item, dict)]
    if not format_rows:
        format_rows = _format_rows_from_ai_plan(payload)

    rules: list[dict[str, Any]] = []
    current_volume = "business"
    current_scope = "by_lot"
    for index, row in enumerate(format_rows, start=1):
        title = _text(row.get("title"))
        if not title:
            continue
        volume_type = _text(row.get("volume_type")) or current_volume
        if volume_type not in VOLUME_LABELS:
            volume_type = "technical" if "技术" in title else "price" if "价格" in title else "business"
        current_volume = volume_type
        scope_text = " ".join(_text(row.get(key)) for key in ("title", "notes", "submission_scope"))
        submission_scope = _text(row.get("submission_scope")) or _submission_scope(scope_text, volume_type)
        current_scope = submission_scope or current_scope
        status, reason = _row_status(row, full_text)
        src = _source(
            payload,
            section=_text(row.get("source_section")) or "投标文件格式/组成清单",
            page=row.get("source_page") if isinstance(row.get("source_page"), int) else None,
            document_role=_text(row.get("document_role")) or "main_tender_file",
            detection_method=_text(row.get("detection_method")) or "structured_format_table_marker",
            confidence=float(row.get("confidence") or (0.98 if row.get("strict_format_table") else 0.82)),
            source_file=_text(row.get("source_file")) or None,
            chapter_number=_text(row.get("sequence")) or None,
        )
        rules.append(_make_rule(
            payload,
            rule_id=f"FORMAT-{index:03d}",
            title=title,
            volume_type=volume_type,
            status=status,
            reason=reason,
            source=src,
            submission_scope=submission_scope or current_scope,
            rule_scope=_text(row.get("rule_scope")) or None,
            parent_key=_text(row.get("parent_key")) or None,
            sequence=_text(row.get("sequence")) or None,
        ))

    project_src = _source(payload, section="投标人须知/投标文件组成", confidence=0.96)
    if "资格预审" in full_text and re.search(r"资格预审申请文件.{0,40}(?:作为|构成)投标文件", full_text):
        rules.append(_make_rule(
            payload, rule_id="PREQUAL-INHERIT", title="资格预审申请文件", volume_type="business",
            status="inherited_from_prequalification", reason="资格预审申请文件由招标规则继承，不重复编制整套资料",
            source=project_src, submission_scope="by_lot",
        ))
    if re.search(r"(?:允许|可|接受).{0,20}(?:更新|补充)|新的有效的支持证明材料", full_text):
        rules.append(_make_rule(
            payload, rule_id="PREQUAL-SUPPLEMENT", title="资格预审支持证明补充材料", volume_type="business",
            status="supplement_allowed", reason="仅在招标文件明确范围内允许补充，不扩大为整套资格资料重报",
            source=project_src, submission_scope="by_lot",
        ))
    if re.search(r"资质证书、?试验报告.{0,50}(?:到期|失效).{0,50}(?:新的|更新|有效)", full_text):
        rules.append(_make_rule(
            payload, rule_id="PREQUAL-UPDATE", title="到期资质证书和试验报告更新材料", volume_type="business",
            status="update_required", reason="预审材料在投标截止前到期时必须提交新的有效材料",
            source=project_src, submission_scope="by_lot",
        ))
    if re.search(r"不接收纸质投标文件|纸质投标文件.{0,10}不适用", full_text):
        rules.append(_make_rule(
            payload, rule_id="FORBID-PAPER", title="纸质投标文件", volume_type="business",
            status="forbidden", reason="当前项目明确不接收纸质投标文件",
            source=project_src, submission_scope="by_lot",
        ))
    if re.search(r"免收投标保证金|保证金的相关要求均不适用", full_text):
        rules.append(_make_rule(
            payload, rule_id="GUARANTEE-NA", title="投标保证金", volume_type="business",
            status="not_applicable", reason="当前项目明确免收投标保证金",
            source=project_src, submission_scope="by_lot",
        ))
    if "人员关系说明" in full_text:
        rules.append(_make_rule(
            payload, rule_id="RELATION-STATEMENT", title="投标人与国家电网公司系统人员关系说明", volume_type="business",
            status="required" if re.search(r"人员关系说明.{0,40}(?:未提交|须提交|√)", full_text) else "conditional",
            reason="按当前招标文件人员关系披露规则编制",
            source=project_src, submission_scope="by_lot",
        ))

    rules = _dedupe_rules(rules)
    for index, rule in enumerate(rules, start=1):
        rule["order_index"] = index
    return rules


def _load_historical_chapters(path: Path = HISTORICAL_SKELETON_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for volume_type, document in (payload.get("documents") or {}).items():
        for index, chapter in enumerate(document.get("chapters") or [], start=1):
            if not isinstance(chapter, dict):
                continue
            rows.append({
                "historical_id": chapter.get("node_id"),
                "title": chapter.get("title"),
                "canonical_title": _canonical_title(chapter.get("title")),
                "normalized_title": _normalize_title(chapter.get("title")),
                "volume_type": volume_type,
                "order_index": index,
                "origin_type": chapter.get("origin_type"),
                "source_file": chapter.get("source_file"),
                "chapter_number": chapter.get("chapter_number"),
            })
    return rows


def compare_with_historical_skeleton(
    rules: list[dict[str, Any]],
    historical_path: Path = HISTORICAL_SKELETON_PATH,
) -> dict[str, Any]:
    """按规范化标题/确定性别名逐项对照，绝不使用模糊相似度。"""
    historical = _load_historical_chapters(historical_path)
    current = [rule for rule in rules if rule.get("status") in OUTLINE_STATUSES]
    used_history: set[str] = set()
    added: list[dict[str, Any]] = []
    name_changes: list[dict[str, Any]] = []
    order_changes: list[dict[str, Any]] = []
    condition_changes: list[dict[str, Any]] = []

    for current_index, rule in enumerate(current, start=1):
        match = next((item for item in historical if item["volume_type"] == rule["volume_type"] and item["normalized_title"] == _normalize_title(rule["title"])), None)
        match_method = "normalized_exact"
        if not match:
            match = next((item for item in historical if item["volume_type"] == rule["volume_type"] and item["canonical_title"] == rule["canonical_title"]), None)
            match_method = "deterministic_alias"
        if not match:
            added.append({"rule_id": rule["rule_id"], "title": rule["title"], "volume_type": rule["volume_type"], "status": rule["status"]})
            continue
        used_history.add(str(match["historical_id"]))
        if _normalize_title(match["title"]) != _normalize_title(rule["title"]):
            name_changes.append({
                "rule_id": rule["rule_id"], "historical_id": match["historical_id"],
                "historical_title": match["title"], "current_title": rule["title"], "match_method": match_method,
            })
        if match["order_index"] != current_index:
            order_changes.append({
                "rule_id": rule["rule_id"], "historical_id": match["historical_id"],
                "historical_order": match["order_index"], "current_order": current_index,
            })
        historical_status = "required" if match.get("origin_type") == "tender_mandated" else "conditional" if match.get("origin_type") == "tender_conditional" else "reference_only"
        if historical_status != rule["status"]:
            condition_changes.append({
                "rule_id": rule["rule_id"], "historical_id": match["historical_id"],
                "title": rule["title"], "historical_status": historical_status, "current_status": rule["status"],
            })

    deleted = [
        {"historical_id": item["historical_id"], "title": item["title"], "volume_type": item["volume_type"], "historical_origin_type": item["origin_type"]}
        for item in historical if str(item["historical_id"]) not in used_history
    ]
    return {
        "comparison_method": "normalized_exact_then_deterministic_alias_no_fuzzy_similarity",
        "historical_role": "reference_only",
        "current_tender_precedence": True,
        "summary": {
            "added": len(added), "deleted": len(deleted), "name_changed": len(name_changes),
            "order_changed": len(order_changes), "condition_changed": len(condition_changes),
        },
        "added": added,
        "deleted": deleted,
        "name_changes": name_changes,
        "order_changes": order_changes,
        "condition_changes": condition_changes,
    }


def _scope_matrix(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for volume_type in ("price", "business", "technical"):
        scoped = [rule for rule in rules if rule.get("volume_type") == volume_type]
        scopes = Counter(str(rule.get("submission_scope")) for rule in scoped if rule.get("submission_scope"))
        submission_scope = scopes.most_common(1)[0][0] if scopes else ("by_package" if volume_type == "price" else "by_lot")
        rows.append({
            "volume_type": volume_type,
            "volume_label": VOLUME_LABELS[volume_type],
            "rule_scope": "package" if submission_scope == "by_package" else "lot",
            "submission_scope": submission_scope,
            "included_rule_count": sum(1 for rule in scoped if rule.get("status") in OUTLINE_STATUSES),
            "excluded_rule_count": sum(1 for rule in scoped if rule.get("status") not in OUTLINE_STATUSES),
        })
    return rows


def _chapter_from_rule(rule: dict[str, Any]) -> dict[str, Any]:
    source = (rule.get("sources") or [{}])[0]
    status = str(rule.get("status"))
    return {
        "title": rule.get("title"),
        "purpose": f"按当前招标文件编制；当前状态：{status}。{rule.get('status_reason')}",
        "priority": "high" if status in {"required", "update_required"} else "medium",
        "response_points": [rule.get("status_reason")],
        "source_pages": [source["source_page"]] if source.get("source_page") else [],
        "writing_notes": [
            "以当前招标原表和条款为准，历史标书仅用于差异核对。",
            "固定表头、签章位和提交范围不得由模型改写。",
        ],
        "metadata": {
            "volume_type": rule.get("volume_type"),
            "section_role": "leaf",
            "leaf_generation": True,
            "project_rule_id": rule.get("rule_id"),
            "project_rule_status": status,
            "rule_scope": rule.get("rule_scope"),
            "submission_scope": rule.get("submission_scope"),
            "source_trace": source,
            "writing_plan": {
                "target_words": 800,
                "min_words": 300,
                "max_words": 1200,
                "suggested_pages": "按招标原表/材料实际页数",
                "generation_mode": "single_pass",
                "strategy": "招标原表优先；企业事实仅从已核验泰昌资料填充，缺失项保留待确认。",
            },
        },
    }


def build_project_bid_skeleton(payload: dict[str, Any]) -> dict[str, Any]:
    rules = build_project_rule_inventory(payload)
    difference = compare_with_historical_skeleton(rules)
    project = payload.get("project") or {}
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") or {}
    status_counts = Counter(str(rule.get("status")) for rule in rules)
    volumes: list[dict[str, Any]] = []
    for volume_type in ("price", "business", "technical"):
        chapters = [_chapter_from_rule(rule) for rule in rules if rule.get("volume_type") == volume_type and rule.get("status") in OUTLINE_STATUSES]
        if chapters:
            volumes.append({
                "type": volume_type,
                "name": VOLUME_LABELS[volume_type],
                "required": any((chapter.get("metadata") or {}).get("project_rule_status") == "required" for chapter in chapters),
                "basis": "由当次招标文件格式表、投标人须知和结构化解读确定；历史标书不参与目录决策。",
                "chapters": chapters,
            })
    return {
        "schema_version": "project_bid_skeleton.v1",
        "version": "project-bid-skeleton-v1",
        "artifact_role": "current_tender_project_skeleton",
        "current_tender_precedence": True,
        "historical_skeleton_role": "difference_reference_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_id": project.get("id"),
        "project_name": project_meta.get("project_name") or project.get("project_name"),
        "tender_no": project_meta.get("tender_no") or project.get("project_no"),
        "summary": "本目录由当次招标文件确定；未标记须提交、不适用或仅存在于历史标书的章节不会进入成稿目录。",
        "project_rule_summary": {
            "total": len(rules),
            "included": sum(status_counts.get(status, 0) for status in OUTLINE_STATUSES),
            "excluded": sum(count for status, count in status_counts.items() if status not in OUTLINE_STATUSES),
            "status_counts": dict(status_counts),
            "source_basis": "当次招标文件",
            "requires_manual_review": any(float(rule.get("confidence") or 0) < 0.8 for rule in rules if rule.get("status") in OUTLINE_STATUSES),
        },
        "rule_inventory": rules,
        "scope_matrix": _scope_matrix(rules),
        "historical_difference": difference,
        "volumes": volumes,
        "chapters": [],
        "next_steps": [
            "先确认条件适用项、分标和包范围，再生成正文。",
            "资格预审继承项不重复编制；到期材料按投标截止日更新。",
            "历史标书差异只供复核，不得覆盖当次招标规则。",
        ],
    }


def has_current_tender_skeleton_inputs(payload: dict[str, Any]) -> bool:
    rule_inputs = _rule_inputs(payload)
    if rule_inputs.get("format_rows"):
        return True
    full_text = _payload_text(payload)
    return bool(
        len(full_text) >= 300
        and any(token in full_text for token in ("投标文件格式", "投标文件组成", "价格文件", "商务文件", "技术文件"))
    )

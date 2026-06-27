from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.ai.compliance_checker import build_compliance_report
from backend.db.supabase_repo import get_bid_export_task, get_project_interpretation, list_knowledge_assets
from backend.services.bid_compatibility import (
    build_bid_product_compatibility_report,
    is_product_compatibility_blocking,
)
from backend.services.bid_prefill import PREFILL_FIELD_SPECS, build_bid_prefill_report, formal_confirmation_issue
from backend.services.formal_placeholders import collect_formal_placeholders

RULES_PATH = Path(__file__).resolve().parents[2] / "rules" / "power_grid" / "formal_bid_check_rules.v1.json"

STATUS_LABELS = {
    "passed": "已通过",
    "blocked": "阻断正式导出",
    "warning": "需关注",
    "manual_confirm": "需人工确认",
    "not_applicable": "不适用",
}

SEVERITY_ORDER = {"blocker": 0, "high": 1, "medium": 2, "low": 3}

PREFILL_FIELD_LABELS = {spec.key: spec.label for spec in PREFILL_FIELD_SPECS}


def _primary_action_for_rule(rule: dict[str, Any], target: str | None = None) -> dict[str, Any]:
    check_type = str(rule.get("check_type") or "")
    category = str(rule.get("category") or "")
    title = str(rule.get("title") or "")
    field_keys = [str(key) for key in rule.get("field_keys") or [] if key]
    keywords = [str(keyword) for keyword in rule.get("keywords") or [] if keyword]
    combined = " ".join([category, title, " ".join(keywords)])

    if check_type.startswith("prefill_"):
        return {
            "type": "prefill",
            "label": "去投标确认",
            "target": field_keys[0] if field_keys else None,
            "description": "补齐或确认该投标关键字段后，重新执行正式检查。",
        }

    if check_type.startswith("asset_") or check_type == "content_requires_asset_when_mentions":
        product_terms = ["产品", "检验报告", "技术", "CPVC", "MPP", "生产", "检测", "绿色", "参数"]
        is_product = any(term in combined for term in product_terms)
        return {
            "type": "product_library" if is_product else "qualification_library",
            "label": "去产品库" if is_product else "去资信库",
            "target": keywords[0] if keywords else None,
            "description": "补充、修正或确认企业资料资产后，重新执行正式检查。",
        }

    if check_type.startswith("export_"):
        return {
            "type": "bid_editor",
            "label": "去导出/编制",
            "target": target,
            "description": "完成 DOCX 导出或成品复验后，刷新正式检查。",
        }

    return {
        "type": "bid_editor",
        "label": "去章节编辑",
        "target": target,
        "description": "在正文编辑页补齐对应章节或修正正文后，重新执行正式检查。",
    }


@lru_cache(maxsize=1)
def load_formal_check_rules() -> dict[str, Any]:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value)).lower()


def _contains_any(haystack: str, keywords: list[str] | None) -> bool:
    normalized = _norm(haystack)
    return any(_norm(keyword) in normalized for keyword in keywords or [])


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "；".join(_format_value(item) for item in value if _format_value(item))
    if isinstance(value, dict):
        for key in ("title", "name", "value"):
            if value.get(key):
                return _format_value(value.get(key))
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _field_label(key: str, fields: dict[str, dict[str, Any]] | None = None) -> str:
    field = (fields or {}).get(key) or {}
    label = str(field.get("label") or "").strip()
    if label and label != key:
        return label
    return PREFILL_FIELD_LABELS.get(key, key)


def _field_labels(keys: list[str], fields: dict[str, dict[str, Any]] | None = None) -> list[str]:
    return [_field_label(str(key), fields) for key in keys if key]


def _localize_internal_tokens(value: str) -> str:
    text = _text(value)
    for key, label in sorted(PREFILL_FIELD_LABELS.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])", label, text)
    return text


def _section_volume(section: dict[str, Any]) -> str:
    metadata = section.get("metadata") or {}
    return str(metadata.get("volume_type") or section.get("volume_type") or "other")


def _leaf_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parent_ids = {str(section.get("parent_id")) for section in sections if section.get("parent_id")}
    return [section for section in sections if str(section.get("id")) not in parent_ids]


def _section_blob(sections: list[dict[str, Any]]) -> str:
    return "\n".join(
        " ".join([
            _text(section.get("title")),
            _text(section.get("purpose")),
            _text(section.get("content")),
            _text(section.get("mapped_requirements")),
            _text(section.get("mapped_risks")),
            _text(section.get("mapped_scoring_items")),
        ])
        for section in sections
    )


def _asset_blob(asset: dict[str, Any]) -> str:
    return " ".join([
        _text(asset.get("title")),
        _text(asset.get("category")),
        _text(asset.get("description")),
        _text(asset.get("tags")),
        _text(asset.get("applicable_sections")),
        _text(asset.get("metadata")),
        _text(asset.get("source_file")),
    ])


def _asset_forbidden_source_blob(asset: dict[str, Any]) -> str:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    specs = asset.get("specs") if isinstance(asset.get("specs"), dict) else {}
    source_fields = [
        asset.get("source_file"),
        asset.get("local_path"),
        asset.get("source_url"),
        asset.get("attribution"),
        metadata.get("source_file"),
        metadata.get("source_display_name"),
        metadata.get("doc_owner"),
        metadata.get("source_domain"),
        specs.get("source_file"),
        specs.get("source_display_name"),
        specs.get("doc_owner"),
        specs.get("source_domain"),
    ]
    return " ".join(_text(value) for value in source_fields)


def _asset_is_enterprise_fact(asset: dict[str, Any]) -> bool:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    specs = asset.get("specs") if isinstance(asset.get("specs"), dict) else {}
    source_domain = str(metadata.get("source_domain") or specs.get("source_domain") or "")
    reference_only = bool(metadata.get("reference_only") or specs.get("reference_only"))
    enterprise = str(metadata.get("enterprise") or specs.get("enterprise") or "")
    return source_domain == "enterprise_fact" and not reference_only and ("泰昌" in enterprise or not enterprise)


def _field_by_key(prefill_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(field.get("key")): field for field in prefill_report.get("fields") or [] if field.get("key")}


def _field_value(field: dict[str, Any] | None) -> str:
    if not field:
        return ""
    return _format_value(field.get("confirmedValue") if field.get("confirmedValue") not in (None, "") else field.get("value"))


def _field_confirmed(field: dict[str, Any] | None) -> bool:
    if not field:
        return False
    return formal_confirmation_issue(_field_value(field)) is None


def _candidate_present(field: dict[str, Any] | None) -> bool:
    return bool(_field_value(field).strip())


def _make_result(
    rule: dict[str, Any],
    *,
    status: str,
    evidence: str,
    suggestion: str | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    blocks = bool(rule.get("blocks_formal_export")) and status == "blocked"
    resolved_suggestion = suggestion or rule.get("remediation") or ""
    source_ref = rule.get("source_ref") or ""
    source_level = rule.get("source_level") or ""
    localized_evidence = _localize_internal_tokens(evidence)
    localized_suggestion = _localize_internal_tokens(resolved_suggestion)
    evidence_chain = [
        {"label": "规则依据", "value": " / ".join(part for part in [source_level, source_ref] if part) or "-"},
        {"label": "当前证据", "value": localized_evidence or "-"},
        {"label": "处理建议", "value": localized_suggestion or "-"},
    ]
    return {
        "id": rule["id"],
        "category": rule.get("category") or "未分类",
        "severity": rule.get("severity") or "medium",
        "title": rule.get("title") or rule["id"],
        "description": rule.get("description") or "",
        "status": status,
        "statusLabel": STATUS_LABELS.get(status, status),
        "blocksFormalExport": blocks,
        "draftExportAllowed": status in {"blocked", "warning", "manual_confirm"},
        "sourceLevel": source_level,
        "sourceRef": source_ref,
        "evidence": localized_evidence,
        "suggestion": localized_suggestion,
        "target": target,
        "checkType": rule.get("check_type") or "",
        "fieldKeys": [str(key) for key in rule.get("field_keys") or [] if key],
        "fieldLabels": _field_labels([str(key) for key in rule.get("field_keys") or [] if key]),
        "evidenceChain": evidence_chain,
        "action": _primary_action_for_rule(rule, target),
    }


def _evaluate_rule(
    rule: dict[str, Any],
    *,
    payload: dict[str, Any],
    prefill_report: dict[str, Any],
    compliance_report: dict[str, Any],
    assets: list[dict[str, Any]],
    export_task: dict[str, Any] | None,
) -> dict[str, Any]:
    check_type = rule.get("check_type")
    sections = payload.get("sections") or []
    fields = _field_by_key(prefill_report)
    content_blob = _section_blob(sections)
    asset_blobs = [_asset_blob(asset) for asset in assets]

    if check_type == "asset_present":
        for asset in assets:
            if _contains_any(_asset_blob(asset), rule.get("keywords")):
                return _make_result(rule, status="passed", evidence=f"命中资产：{asset.get('title') or asset.get('id')}")
        return _make_result(rule, status="blocked" if rule.get("blocks_formal_export") else "warning", evidence="未找到匹配资产。")

    if check_type == "asset_boundary_no_wrong_category":
        wrong = [
            asset for asset in assets
            if _contains_any(_asset_blob(asset), rule.get("keywords"))
            and _contains_any(_asset_blob(asset), rule.get("forbidden_keywords"))
        ]
        if wrong:
            return _make_result(rule, status="warning", evidence=f"发现疑似错误归类资产 {len(wrong)} 条：{wrong[0].get('title') or wrong[0].get('id')}")
        return _make_result(rule, status="passed", evidence="未发现人员/社保资料误归入生产或检测能力。")

    if check_type == "content_must_not_include":
        hits = [keyword for keyword in rule.get("keywords") or [] if _contains_any(content_blob, [keyword])]
        if hits:
            return _make_result(rule, status="blocked" if rule.get("blocks_formal_export") else "warning", evidence=f"正文命中禁用词：{'、'.join(hits[:5])}")
        return _make_result(rule, status="passed", evidence="正文未命中禁用词。")

    if check_type == "content_must_not_include_near":
        keywords = rule.get("keywords") or []
        hit = all(_contains_any(content_blob, [keyword]) for keyword in keywords)
        if hit:
            return _make_result(rule, status="warning", evidence=f"正文同时命中风险组合：{'、'.join(keywords)}")
        return _make_result(rule, status="passed", evidence="未发现该类混用风险组合。")

    if check_type == "content_requires_asset_when_mentions":
        mentions = [keyword for keyword in rule.get("keywords") or [] if _contains_any(content_blob, [keyword])]
        if not mentions:
            return _make_result(rule, status="not_applicable", evidence="正文未提及该类事项。")
        has_asset = any(_contains_any(blob, rule.get("asset_keywords")) for blob in asset_blobs)
        if has_asset:
            return _make_result(rule, status="passed", evidence=f"正文提及 {'、'.join(mentions)}，且存在对应企业资料资产。")
        return _make_result(rule, status="warning", evidence=f"正文提及 {'、'.join(mentions)}，但未找到对应企业资料资产。")

    if check_type == "section_present":
        for section in sections:
            if _contains_any(" ".join([_text(section.get("title")), _text(section.get("content"))]), rule.get("keywords")):
                return _make_result(rule, status="passed", evidence=f"命中章节：{section.get('title') or section.get('id')}", target=section.get("id"))
        return _make_result(rule, status="blocked" if rule.get("blocks_formal_export") else "warning", evidence="未找到匹配章节。")

    if check_type == "prefill_confirmed":
        invalid = {
            key: formal_confirmation_issue(_field_value(fields.get(key)))
            for key in rule.get("field_keys") or []
            if not _field_confirmed(fields.get(key))
        }
        if not invalid:
            values = [f"{_field_label(str(key), fields)}：{_field_value(fields.get(key))}" for key in rule.get("field_keys") or []]
            return _make_result(rule, status="passed", evidence="；".join(values))
        details = "；".join(f"{_field_label(str(key), fields)}：{reason}" for key, reason in invalid.items())
        return _make_result(rule, status="blocked", evidence=f"未形成正式客户确认：{details}")

    if check_type == "prefill_confirmed_any":
        invalid: dict[str, str] = {}
        for key in rule.get("field_keys") or []:
            if _field_confirmed(fields.get(key)):
                return _make_result(rule, status="passed", evidence=f"{_field_label(str(key), fields)}：{_field_value(fields.get(key))}")
            invalid[str(key)] = formal_confirmation_issue(_field_value(fields.get(key))) or "未填写"
        details = "；".join(f"{_field_label(key, fields)}：{reason}" for key, reason in invalid.items())
        return _make_result(
            rule,
            status="blocked" if rule.get("blocks_formal_export") else "manual_confirm",
            evidence=f"候选字段均未形成正式客户确认：{details}",
        )

    if check_type == "prefill_candidate_present":
        for key in rule.get("field_keys") or []:
            if _candidate_present(fields.get(key)):
                return _make_result(rule, status="passed", evidence=f"存在候选：{_field_label(str(key), fields)}")
        missing_labels = "、".join(_field_labels([str(key) for key in rule.get("field_keys") or []], fields))
        return _make_result(rule, status="blocked" if rule.get("blocks_formal_export") else "manual_confirm", evidence=f"未找到候选字段：{missing_labels}")

    if check_type == "sections_min_count":
        count = len(sections)
        min_count = int(rule.get("min_count") or 1)
        if count >= min_count:
            return _make_result(rule, status="passed", evidence=f"当前章节数 {count}。")
        return _make_result(rule, status="warning", evidence=f"当前章节数 {count}，少于 {min_count}。")

    if check_type == "no_empty_leaf_sections":
        leaves = _leaf_sections(sections)
        empty = [section for section in leaves if not _text(section.get("content")).strip()]
        if not empty:
            return _make_result(rule, status="passed", evidence=f"叶子章节 {len(leaves)} 个，未发现空正文。")
        return _make_result(rule, status="blocked", evidence=f"空叶子章节 {len(empty)} 个，示例：{empty[0].get('title') or empty[0].get('id')}")

    if check_type == "no_placeholders":
        placeholders = collect_formal_placeholders(content_blob)
        if not placeholders:
            return _make_result(rule, status="passed", evidence="正文未发现常见占位符。")
        return _make_result(rule, status="blocked", evidence=f"发现占位符 {len(placeholders)} 处，示例：{placeholders[0]}")

    if check_type == "section_no_placeholder":
        target_sections = [
            section for section in sections
            if _contains_any(" ".join([_text(section.get("title")), _text(section.get("content"))]), rule.get("keywords"))
        ]
        target_blob = _section_blob(target_sections)
        placeholders = collect_formal_placeholders(target_blob)
        if not target_sections:
            return _make_result(rule, status="warning", evidence="未找到目标章节。")
        if placeholders:
            return _make_result(rule, status="warning", evidence=f"目标章节发现占位符 {len(placeholders)} 处。")
        return _make_result(rule, status="passed", evidence=f"已检查目标章节 {len(target_sections)} 个。")

    if check_type == "asset_no_forbidden_owner":
        wrong = [
            asset for asset in assets
            if not _asset_is_enterprise_fact(asset)
            and _contains_any(_asset_forbidden_source_blob(asset), rule.get("keywords"))
        ]
        if wrong:
            return _make_result(rule, status="blocked", evidence=f"发现疑似禁用来源资产：{wrong[0].get('title') or wrong[0].get('id')}")
        return _make_result(rule, status="passed", evidence="未发现禁用来源图片资产。")

    if check_type == "asset_titles_chinese":
        bad = [
            asset for asset in assets
            if re.search(r"taichang_|power_grid_|production_capacity|green_low_carbon|business_license|certification", _asset_blob(asset), re.I)
        ]
        if bad:
            return _make_result(rule, status="warning", evidence=f"发现疑似内部命名资产 {len(bad)} 条：{bad[0].get('title') or bad[0].get('id')}")
        return _make_result(rule, status="passed", evidence="资产标题/分类未发现常见内部命名。")

    if check_type == "product_compatibility_precheck":
        report = build_bid_product_compatibility_report(payload)
        if is_product_compatibility_blocking(report):
            return _make_result(
                rule,
                status="blocked",
                evidence=report.get("message") or "招标物料与泰昌现有产品资料不匹配。",
            )
        return _make_result(
            rule,
            status="passed" if report.get("status") == "matched" else "manual_confirm",
            evidence=report.get("message") or "产品适配性需人工复核。",
        )

    if check_type == "export_metadata_present":
        if export_task:
            return _make_result(rule, status="passed", evidence=f"存在导出任务：{export_task.get('id')}")
        return _make_result(rule, status="manual_confirm", evidence="未传入最近一次导出任务，导出后成品项需在导出完成后复验。")

    if check_type == "export_images_ok":
        metadata = (export_task or {}).get("metadata") or {}
        image_conversion = metadata.get("image_conversion") or {}
        failed = int(image_conversion.get("failed") or 0)
        inserted = int(image_conversion.get("inserted") or 0)
        if not export_task:
            return _make_result(rule, status="manual_confirm", evidence="未传入导出任务，图片插入需导出后复验。")
        if failed == 0:
            return _make_result(rule, status="passed", evidence=f"图片插入 {inserted}，失败 {failed}。")
        return _make_result(rule, status="warning", evidence=f"图片插入失败 {failed}。")

    if check_type == "export_fields_refreshed":
        metadata = (export_task or {}).get("metadata") or {}
        field_refresh = metadata.get("field_refresh") or {}
        if not export_task:
            return _make_result(rule, status="manual_confirm", evidence="未传入导出任务，字段刷新需导出后复验。")
        if field_refresh.get("status") == "refreshed":
            return _make_result(rule, status="passed", evidence="LibreOffice 字段刷新成功。")
        return _make_result(rule, status="warning", evidence=f"字段刷新状态：{field_refresh.get('status') or '未知'}。")

    summary = compliance_report.get("summary") or {}
    return _make_result(rule, status="manual_confirm", evidence=f"暂未实现自动检查类型 {check_type}。条款覆盖率 {summary.get('percent', 0)}%。")


def build_formal_bid_check_report(project_id: str, *, export_task_id: str | None = None) -> dict[str, Any]:
    rule_set = load_formal_check_rules()
    payload = get_project_interpretation(project_id)
    prefill_report = build_bid_prefill_report(project_id)
    compliance_report = build_compliance_report(project_id)
    assets = list_knowledge_assets()
    export_task = get_bid_export_task(project_id, export_task_id) if export_task_id else None

    items = [
        _evaluate_rule(
            rule,
            payload=payload,
            prefill_report=prefill_report,
            compliance_report=compliance_report,
            assets=assets,
            export_task=export_task,
        )
        for rule in rule_set.get("rules") or []
    ]
    items.sort(key=lambda item: (SEVERITY_ORDER.get(item["severity"], 99), item["category"], item["id"]))

    status_counts = Counter(item["status"] for item in items)
    severity_counts = Counter(item["severity"] for item in items)
    category_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "blocked": 0, "warning": 0, "manual_confirm": 0, "passed": 0})
    for item in items:
        category_counts[item["category"]]["total"] += 1
        if item["status"] in category_counts[item["category"]]:
            category_counts[item["category"]][item["status"]] += 1

    blockers = [item for item in items if item.get("blocksFormalExport")]
    warnings = [item for item in items if item["status"] == "warning"]
    manual = [item for item in items if item["status"] == "manual_confirm"]
    can_formal_export = len(blockers) == 0

    compliance_summary = compliance_report.get("summary") or {}
    prefill_summary = prefill_report.get("summary") or {}
    return {
        "schemaVersion": "formal_bid_check_report.v1",
        "ruleSetVersion": rule_set.get("schema_version"),
        "ruleSetName": rule_set.get("rule_set_name"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "projectId": project_id,
        "project": payload.get("project") or prefill_report.get("project") or {},
        "summary": {
            "totalRules": len(items),
            "passed": status_counts.get("passed", 0),
            "blocked": len(blockers),
            "warnings": len(warnings),
            "manualConfirm": len(manual),
            "notApplicable": status_counts.get("not_applicable", 0),
            "canFormalExport": can_formal_export,
            "draftExportAllowed": True,
            "formalExportLabel": "允许正式版导出" if can_formal_export else "仅允许草稿版导出",
            "compliancePercent": compliance_summary.get("percent", 0),
            "complianceMissing": compliance_summary.get("missing", 0),
            "highRiskMissing": compliance_summary.get("highRiskMissing", 0),
            "formalRequiredGaps": prefill_summary.get("formalRequiredGaps", 0),
            "unresolvedPlaceholderCount": prefill_summary.get("unresolvedPlaceholderCount", 0),
        },
        "statusCounts": dict(status_counts),
        "severityCounts": dict(severity_counts),
        "categorySummaries": [
            {"category": category, **counts}
            for category, counts in sorted(category_counts.items())
        ],
        "items": items,
        "sourceNotes": rule_set.get("source_notes") or [],
        "recommendations": [
            "阻断项未清零前只能导出草稿版，不能作为正式投标文件使用。",
            "客户确认字段、报价金额、保证金、授权签署信息必须由客户确认，系统不得编造。",
            "导出后还需执行 DOCX 成品复验，检查目录、页码、图片、表格和内部字段泄露。",
        ],
    }

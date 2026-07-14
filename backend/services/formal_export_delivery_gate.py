"""DOCX 导出后的正式交付门禁。

导出前正式检查负责业务事实、客户确认和章节完整性；本模块只检查已经生成的
DOCX 成品是否满足交付条件。两层门禁必须同时通过，任务才可标记为正式版。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile


FORBIDDEN_DOCX_PATTERNS = {
    "内部解析路径": re.compile(r"parsed_outputs/|staging/|/api/(?:bidding/)?knowledge/assets/", re.I),
    "内部枚举": re.compile(r"taichang_|production_capacity|green_low_carbon|business_license|source_domain|target_library", re.I),
    "非正式题注": re.compile(r"图示\s*[：:]|页面[_\-\s]*\d+|原图", re.I),
    "参考企业事实": re.compile(r"河北豪乾(?:业绩|资质|财务|人员|设备|检验报告)", re.I),
}


def _item(item_id: str, title: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "title": title,
        "status": "passed" if passed else "blocked",
        "blocks_formal_delivery": not passed,
        "evidence": evidence,
    }


def audit_formal_docx_package(path: str | Path) -> dict[str, Any]:
    output = Path(path).resolve()
    try:
        with ZipFile(output) as package:
            xml_names = [
                name for name in package.namelist()
                if name.startswith("word/") and name.endswith(".xml")
            ]
            visible_xml = "\n".join(
                package.read(name).decode("utf-8", errors="ignore")
                for name in xml_names
                if name == "word/document.xml" or "/header" in name or "/footer" in name
            )
            media_count = sum(name.startswith("word/media/") for name in package.namelist())
    except (BadZipFile, FileNotFoundError, OSError) as exc:
        return {
            "status": "failed",
            "passed": False,
            "path": str(output),
            "media_count": 0,
            "forbidden_hits": [{"label": "DOCX 包不可审计", "sample": str(exc)[:200]}],
        }

    hits = []
    for label, pattern in FORBIDDEN_DOCX_PATTERNS.items():
        match = pattern.search(visible_xml)
        if match:
            hits.append({"label": label, "sample": match.group(0)[:120]})
    return {
        "status": "passed" if not hits else "failed",
        "passed": not hits,
        "path": str(output),
        "media_count": media_count,
        "forbidden_hits": hits,
    }


def _manifest_asset_policy_errors(manifest: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row in manifest:
        policy = row.get("asset_policy") if isinstance(row.get("asset_policy"), dict) else {}
        asset_id = str(row.get("asset_id") or "未知资产")
        enterprise_text = " ".join(str(policy.get(key) or "") for key in ("enterprise", "doc_owner"))
        quality_tier = str(policy.get("quality_tier") or "")
        formal_ready = (
            policy.get("formal_bid_ready") is True
            or quality_tier == "formal_bid_ready"
            or policy.get("bundle_allowed_for_bid") is True
        )
        if "泰昌" not in enterprise_text:
            errors.append(f"{asset_id}: 主体不是泰昌")
        if str(policy.get("source_domain") or "") != "enterprise_fact":
            errors.append(f"{asset_id}: 来源域不是企业事实")
        if not formal_ready:
            errors.append(f"{asset_id}: 未达到 formal_bid_ready")
        if policy.get("allowed_for_bid") is not True:
            errors.append(f"{asset_id}: 未明确允许用于标书")
        if policy.get("reference_only") is True or policy.get("exclude_from_docx") is True:
            errors.append(f"{asset_id}: 属于参考或排除资产")
        if policy.get("full_page") is not True:
            errors.append(f"{asset_id}: 不是完整页资产")
    return errors


def build_formal_export_delivery_gate(
    *,
    output_path: str | Path,
    scope: str,
    pre_export_gate: dict[str, Any] | None,
    image_selection: dict[str, Any] | None,
    image_conversion: dict[str, Any] | None,
    field_refresh: dict[str, Any] | None,
) -> dict[str, Any]:
    """合并导出前业务门禁与导出后成品审计，返回最终交付状态。"""
    pre_gate = pre_export_gate if isinstance(pre_export_gate, dict) else {}
    selection = image_selection if isinstance(image_selection, dict) else {}
    conversion = image_conversion if isinstance(image_conversion, dict) else {}
    refresh = field_refresh if isinstance(field_refresh, dict) else {}
    if scope == "section":
        return {
            "schema_version": "formal_export_delivery_gate.v1",
            "scope": scope,
            "checked": False,
            "artifact_ready": False,
            "can_formal_deliver": False,
            "export_mode": "section",
            "blocked_count": 0,
            "items": [],
        }

    items: list[dict[str, Any]] = []
    readiness = selection.get("formal_readiness") if isinstance(selection.get("formal_readiness"), dict) else {}
    readiness_ok = readiness.get("ready") is True
    items.append(_item(
        "POST-001",
        "导出内容正式就绪",
        readiness_ok,
        "正文、占位和正式必填字段均已就绪。" if readiness_ok else (
            f"空章节 {int(readiness.get('empty_section_count') or 0)}，占位 {int(readiness.get('placeholder_count') or 0)}，"
            f"正式必填缺口 {len(readiness.get('missing_formal_required_fields') or [])}。"
        ),
    ))

    bundle_plan = selection.get("evidence_bundle_selection") if isinstance(selection.get("evidence_bundle_selection"), dict) else {}
    manifest = selection.get("manifest") if isinstance(selection.get("manifest"), list) else []
    selected_count = int(selection.get("selected") or len(manifest))
    bundle_pages = int(bundle_plan.get("selected_page_count") or selected_count)
    skipped_bundles = int(bundle_plan.get("skipped_bundle_count") or 0)
    bundle_ok = skipped_bundles == 0 and bundle_pages == len(manifest) == selected_count
    items.append(_item(
        "POST-002",
        "证据包完整页序",
        bundle_ok,
        f"计划页 {bundle_pages}，manifest {len(manifest)}，选中 {selected_count}，整包跳过 {skipped_bundles}。",
    ))

    deterministic_asset_policy = selection.get("selection_policy") == "chapter_to_evidence_bundle_to_original_page_sequence"
    policy_errors = _manifest_asset_policy_errors(manifest) if deterministic_asset_policy else []
    items.append(_item(
        "POST-003",
        "正式资产来源与质量等级",
        not policy_errors,
        (
            "全部选中资产均为泰昌企业事实完整页。"
            if deterministic_asset_policy and not policy_errors
            else "当前导出未启用泰昌证据包策略，本项沿用通用资产选择门禁。"
            if not deterministic_asset_policy
            else "；".join(policy_errors[:5])
        ),
    ))

    inserted = int(conversion.get("inserted") or 0)
    failed = int(conversion.get("failed") or 0)
    image_ok = failed == 0 and inserted == selected_count
    items.append(_item(
        "POST-004",
        "图片全部插入",
        image_ok,
        f"选中 {selected_count}，插入 {inserted}，失败 {failed}。",
    ))

    fields_ok = refresh.get("status") == "refreshed" and not bool(refresh.get("manual_refresh_required"))
    items.append(_item(
        "POST-005",
        "目录与页码字段刷新",
        fields_ok,
        f"字段刷新状态：{refresh.get('status') or '未知'}。",
    ))

    fixed_report = conversion.get("fixed_form_ooxml") if isinstance(conversion.get("fixed_form_ooxml"), dict) else {}
    fixed_expected = bool(selection.get("fixed_form_manifests"))
    fixed_audit = fixed_report.get("post_refresh_audit") if isinstance(fixed_report.get("post_refresh_audit"), dict) else {}
    fixed_ok = not fixed_expected or fixed_audit.get("passed") is True
    items.append(_item(
        "POST-006",
        "固定表单刷新后保真",
        fixed_ok,
        "当前项目无固定表单。" if not fixed_expected else f"表单审计：{fixed_audit.get('status') or '缺失'}。",
    ))

    package_audit = audit_formal_docx_package(output_path)
    items.append(_item(
        "POST-007",
        "DOCX 可见内容无内部痕迹",
        package_audit.get("passed") is True,
        "未发现内部路径、枚举或非正式题注。" if package_audit.get("passed") else str(package_audit.get("forbidden_hits") or [])[:500],
    ))

    blockers = [row for row in items if row["status"] == "blocked"]
    artifact_ready = not blockers
    source_ready = bool(pre_gate.get("can_formal_export"))
    can_formal_deliver = source_ready and artifact_ready
    return {
        "schema_version": "formal_export_delivery_gate.v1",
        "scope": scope,
        "checked": True,
        "source_ready": source_ready,
        "artifact_ready": artifact_ready,
        "can_formal_deliver": can_formal_deliver,
        "export_mode": "formal" if can_formal_deliver else "draft",
        "blocked_count": len(blockers),
        "items": items,
        "package_audit": package_audit,
    }

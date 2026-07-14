"""泰昌 P1-03 业务台账的结构化查询入口。

该项目为客户确认的私有项目，完整人员花名册和人员证书可进入泰昌租户内查询；
所有结果仍须保留来源、有效期和项目适用性边界。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    PROJECT_ROOT
    / "docs/development/taichang-bid-v1-data/p1_03_business_ledgers/taichang_p1_03_manifest.json"
)

EQUIPMENT_TERMS = ["设备", "仪器", "校准", "检定", "复校", "万能试验机", "维卡", "电子天平", "锤击", "熔体流动", "拉力试验机"]
CERTIFICATE_TERMS = ["管理体系", "体系认证", "质量管理", "环境管理", "职业健康", "认证证书"]
AUDIT_TERMS = ["审计", "财务报告", "财务审计"]
PERSONNEL_TERMS = ["人员", "花名册", "员工", "姓名", "岗位", "社保", "劳动合同", "试验检测人员", "特种作业证", "人员证书", "证件号"]
REPORT_TERMS = ["检验报告", "检测报告", "型式试验报告", "N-HAP", "NHAP", "UPVC", "CPVC", "MPP"]
IP_TERMS = ["知识产权", "专利", "软件著作权", "软著"]


def _load_manifest(path_text: str = str(MANIFEST_PATH)) -> dict[str, Any]:
    """每次查询读取最新 staging 文件，避免客户补充资料后仍命中旧缓存。"""
    path = Path(path_text)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _contains_any(query: str, terms: list[str]) -> bool:
    lowered = query.lower()
    return any(term.lower() in lowered for term in terms)


def _source_line(row: dict[str, Any]) -> str:
    return f"资料来源：{row.get('source_display_name') or '-'}；来源页码：第{row.get('source_page') or '-'}页"


def _equipment_content(row: dict[str, Any]) -> str:
    return "\n".join([
        "【泰昌试验检测设备台账｜原始校准证书】",
        f"设备名称：{row.get('equipment_name') or '-'}",
        f"型号：{row.get('equipment_model') or '-'}；出厂编号：{row.get('serial_no') or '-'}；管理编号：{row.get('equipment_no') or '-'}",
        f"校准证书编号：{row.get('calibration_certificate_no') or '-'}",
        f"校准日期：{row.get('calibration_date') or '-'}；复校日期：{row.get('recalibration_due') or '-'}；当前状态：{row.get('validity_status') or '-'}",
        _source_line(row),
        "使用边界：当前为知识库结构化事实，投标项目使用前仍需按开标日期复核有效性；不得用历史Word中的旧日期覆盖原始校准证书。",
    ])


def _certificate_content(row: dict[str, Any]) -> str:
    status = "已过期，禁止作为当前有效资质使用" if row.get("validity_status") == "expired" else "当前有效，投标前仍需按开标日期复核"
    return "\n".join([
        "【泰昌管理体系认证台账｜原始证书】",
        f"证书名称：{row.get('certificate_name') or '-'}",
        f"证书编号：{row.get('certificate_no') or '-'}；认证机构：{row.get('issuer') or '-'}",
        f"有效期至：{row.get('valid_until') or '-'}；状态：{status}",
        f"认证范围：{row.get('certification_scope') or '-'}",
        _source_line(row),
    ])


def _audit_content(row: dict[str, Any]) -> str:
    report_no = row.get("report_no") or "原始PDF封面未显示，待人工复核，禁止推断"
    return "\n".join([
        "【泰昌审计报告台账｜原始报告】",
        f"年度：{row.get('audit_year') or '-'}；报告编号：{report_no}",
        f"会计师事务所：{row.get('audit_firm') or '-'}",
        f"文件页数：{row.get('file_page_count') or '-'}；完整性：{'完整' if row.get('file_complete') else '待复核'}",
        _source_line(row),
        "使用边界：审计报告是否满足投标要求需结合具体招标年度和财务条款判断。",
    ])


def _personnel_summary_content(row: dict[str, Any]) -> str:
    return "\n".join([
        "【泰昌人员资料摘要｜私有项目完整台账】",
        f"花名册记录：{row.get('personnel_count') or 0}条；特种作业证记录：{row.get('certificate_record_count') or 0}条",
        f"已填写职称记录：{row.get('professional_title_filled_count') or 0}条",
        _source_line(row),
        "使用边界：人员信息已获客户确认，可用于本私有项目；正式投标仍需按岗位要求、证书有效期和项目角色复核。",
    ])


def _personnel_roster_content(row: dict[str, Any]) -> str:
    return "\n".join([
        "【泰昌人员花名册｜私有项目企业事实】",
        f"姓名：{row.get('person_name') or '-'}；岗位：{row.get('project_role') or '-'}",
        f"学历：{row.get('education') or '-'}；职称：{row.get('professional_title') or '-'}；入职年份：{row.get('employment_start_year') or '-'}",
        f"社保记录：{'有' if row.get('social_insurance_recorded') else '未记录'}；劳动合同记录：{'有' if row.get('labor_contract_recorded') else '未记录'}",
        _source_line(row),
    ])


def _personnel_roster_overview_content(rows: list[dict[str, Any]]) -> str:
    lines = ["【泰昌人员花名册明细｜私有项目企业事实】", f"共 {len(rows)} 条："]
    for row in sorted(rows, key=lambda item: int(item.get("roster_row_no") or 0)):
        lines.append(
            f"{row.get('roster_row_no')}. {row.get('person_name') or '-'}｜{row.get('project_role') or '-'}｜"
            f"学历 {row.get('education') or '-'}｜职称 {row.get('professional_title') or '-'}｜"
            f"社保 {'有' if row.get('social_insurance_recorded') else '未记录'}｜"
            f"劳动合同 {'有' if row.get('labor_contract_recorded') else '未记录'}｜"
            f"入职 {row.get('employment_start_year') or '-'}"
        )
    if rows:
        lines.append(_source_line(rows[0]))
    return "\n".join(lines)


def _personnel_certificate_content(row: dict[str, Any]) -> str:
    status = "当前有效，正式投标前仍需按开标日期复核" if row.get("validity_status") == "valid" else str(row.get("validity_status") or "待复核")
    return "\n".join([
        "【泰昌人员证书｜私有项目企业事实】",
        f"姓名：{row.get('person_name') or '-'}；岗位：{row.get('project_role') or '-'}",
        f"证书编号：{row.get('certificate_no') or '-'}；作业类别：{row.get('operation_category') or '-'}；准操项目：{row.get('permitted_operation') or '-'}",
        f"初领日期：{row.get('initial_issue_date') or '-'}；复审日期：{row.get('review_date') or '-'}；有效期至：{row.get('valid_until') or '-'}；状态：{status}",
        _source_line(row),
    ])


def _inspection_content(row: dict[str, Any]) -> str:
    verified = row.get("fact_status") == "verified_existing_report"
    status = "已有原始报告，复用既有结构化参数，不重复写入" if verified else "仅有历史报告编号，缺少原始报告；不得生成正式参数"
    return "\n".join([
        "【泰昌检验报告登记台账】",
        f"产品：{row.get('product_name') or row.get('product_family') or '-'}；规格型号：{row.get('specification_model') or '-'}",
        f"报告编号：{row.get('report_no') or '-'}；证据状态：{status}",
        _source_line(row),
        "边界：辽宁招标资料仅作QA参照，不得据此生成泰昌产品参数或规格覆盖结论。",
    ])


def _gap_content(gap: dict[str, Any]) -> str:
    report_no = gap.get("historical_report_no")
    lines = [
        "【泰昌企业事实缺口｜禁止推断】",
        f"缺口：{gap.get('title') or '-'}；状态：{gap.get('status') or '-'}",
    ]
    if report_no:
        lines.append(f"历史登记报告编号：{report_no}；当前缺少原始报告，不得生成正式参数。")
    if gap.get("note"):
        lines.append(f"说明：{gap['note']}")
    return "\n".join(lines)


def _context(row: dict[str, Any], content: str, similarity: float) -> dict[str, Any]:
    source_file = str(row.get("source_file") or "")
    return {
        "id": f"taichang-business-ledger:{row.get('business_key')}",
        "content": content,
        "similarity": similarity,
        "retrieval_source": "structured_business_ledger_json",
        "metadata": {
            "enterprise": "泰昌",
            "doc_owner": row.get("doc_owner") or "河北泰昌电力器材科技有限公司",
            "source_domain": "enterprise_fact",
            "fact_source_allowed_for_enterprise": True,
            "reference_only": False,
            "doc_type": "泰昌结构化业务台账",
            "source_display_name": row.get("source_display_name") or "泰昌结构化业务台账",
            "category_label": row.get("evidence_type_label") or "企业事实",
            "source_file": source_file,
            "source_page": row.get("source_page"),
            "source_section": row.get("equipment_name") or row.get("certificate_name") or row.get("person_name") or row.get("audit_year") or row.get("product_name"),
            "evidence_type": row.get("evidence_type"),
            "target_library": row.get("target_library"),
            "quality_tier": row.get("quality_tier"),
            "validity_status": row.get("validity_status"),
            "citation_policy": "private_project_enterprise_fact_citable_with_validity_check",
            "source_category": "structured_business_ledger_json",
        },
    }


def _gap_context(gap: dict[str, Any]) -> dict[str, Any]:
    gap_id = str(gap.get("gap_id") or "")
    return {
        "id": f"taichang-business-gap:{gap_id}",
        "content": _gap_content(gap),
        "similarity": 0.99,
        "retrieval_source": "structured_business_ledger_json",
        "metadata": {
            "enterprise": "泰昌",
            "doc_owner": "河北泰昌电力器材科技有限公司",
            "source_domain": "enterprise_fact_gap",
            "fact_source_allowed_for_enterprise": False,
            "is_fact_gap": True,
            "reference_only": False,
            "doc_type": "泰昌企业事实缺口",
            "source_display_name": gap.get("title") or "泰昌企业事实缺口",
            "category_label": "待补证据",
            "evidence_type": "inspection_report" if "report" in gap_id else "enterprise_evidence",
            "quality_tier": "review_only",
            "citation_policy": "gap_only_no_fact_generation",
            "source_category": "structured_business_ledger_json",
        },
    }


def search_taichang_business_ledger_contexts(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """按台账类别返回结构化上下文，包含客户确认可用的私有项目人员明细。"""
    text = str(query or "").strip()
    if not text or "泰昌" not in text:
        return []
    payload = _load_manifest()
    rows = [row for row in payload.get("rows") or [] if isinstance(row, dict)]
    gaps = [gap for gap in payload.get("gaps") or [] if isinstance(gap, dict)]
    selected: list[tuple[float, dict[str, Any], str]] = []

    if _contains_any(text, EQUIPMENT_TERMS):
        for row in rows:
            if row.get("ledger_type") != "equipment_calibration":
                continue
            name = str(row.get("equipment_name") or "")
            score = 0.99 if name and name in text else 0.92
            selected.append((score, row, _equipment_content(row)))

    if _contains_any(text, CERTIFICATE_TERMS):
        for row in rows:
            if row.get("ledger_type") != "management_certificate":
                continue
            name = str(row.get("certificate_name") or "")
            score = 0.99 if any(term in text for term in name.replace("认证证书", "").split()) or name[:4] in text else 0.94
            selected.append((score, row, _certificate_content(row)))

    if _contains_any(text, AUDIT_TERMS):
        years = {year for year in ("2023", "2024", "2025") if year in text}
        for row in rows:
            if row.get("ledger_type") != "audit_report":
                continue
            if years and str(row.get("audit_year")) not in years:
                continue
            selected.append((0.99 if years else 0.94, row, _audit_content(row)))

    roster_rows = [row for row in rows if row.get("ledger_type") == "personnel_roster"]
    personnel_certificate_rows = [row for row in rows if row.get("ledger_type") == "personnel_certificate"]
    explicit_person_names = {
        str(row.get("person_name") or "")
        for row in [*roster_rows, *personnel_certificate_rows]
        if row.get("person_name") and str(row.get("person_name")) in text
    }
    if _contains_any(text, PERSONNEL_TERMS) or explicit_person_names:
        for row in rows:
            if row.get("ledger_type") == "personnel_summary":
                selected.append((0.94 if explicit_person_names else 0.98, row, _personnel_summary_content(row)))
        if explicit_person_names:
            for row in roster_rows:
                if row.get("person_name") in explicit_person_names:
                    selected.append((0.995, row, _personnel_roster_content(row)))
            for row in personnel_certificate_rows:
                if row.get("person_name") in explicit_person_names:
                    selected.append((1.0, row, _personnel_certificate_content(row)))
        else:
            if roster_rows and _contains_any(text, ["花名册", "名单", "姓名", "岗位", "明细", "全部"]):
                overview = dict(roster_rows[0])
                overview["business_key"] = "personnel-roster:all"
                overview["source_display_name"] = "泰昌公司人员花名册"
                selected.append((0.99, overview, _personnel_roster_overview_content(roster_rows)))
            if _contains_any(text, ["证书", "证件号", "特种作业", "试验检测人员"]):
                for row in personnel_certificate_rows:
                    selected.append((0.99, row, _personnel_certificate_content(row)))

    if _contains_any(text, REPORT_TERMS) and not _contains_any(text, ["架空绝缘导线", "绝缘导线"]):
        normalized = text.upper().replace("-", "")
        for row in rows:
            if row.get("ledger_type") != "inspection_report_registry":
                continue
            family = str(row.get("product_family") or "").upper().replace("-", "")
            if any(term in normalized for term in ("NHAP", "UPVC", "CPVC", "MPP")) and family not in normalized:
                continue
            selected.append((0.97, row, _inspection_content(row)))
        for gap in gaps:
            gap_id = str(gap.get("gap_id") or "")
            if ("NHAP" in normalized and "nhap" in gap_id) or ("UPVC" in normalized and "upvc" in gap_id):
                selected.append((0.995, {"business_key": gap_id, **gap}, _gap_content(gap)))

    if _contains_any(text, IP_TERMS):
        gap = next((item for item in gaps if item.get("gap_id") == "missing-intellectual-property-evidence"), None)
        if gap:
            return [_gap_context(gap)][:limit]

    selected.sort(key=lambda item: (item[0], str(item[1].get("business_key") or "")), reverse=True)
    contexts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for score, row, content in selected:
        key = str(row.get("business_key") or "")
        if key in seen:
            continue
        seen.add(key)
        contexts.append(_gap_context(row) if row.get("gap_id") else _context(row, content, score))
        if len(contexts) >= limit:
            break
    return contexts

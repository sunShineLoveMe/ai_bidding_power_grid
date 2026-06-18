from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FACT_PACK_PATH = PROJECT_ROOT / (
    "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/"
    "staging/taichang_bid_fact_pack/"
    "run_20260612_taichang_fact_grounded_full_rewrite_fact_pack.json"
)


def load_taichang_verified_fact_pack() -> dict[str, Any]:
    if not FACT_PACK_PATH.exists():
        return {}
    try:
        payload = json.loads(FACT_PACK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_taichang_prefill_values() -> dict[str, Any]:
    facts = load_taichang_verified_fact_pack()
    if not facts:
        return {}
    enterprise = facts.get("enterprise") if isinstance(facts.get("enterprise"), dict) else {}
    product_inspection = facts.get("product_inspection") if isinstance(facts.get("product_inspection"), dict) else {}
    values: dict[str, Any] = {
        "bidder_name": "河北泰昌电力器材科技有限公司",
        "unified_social_credit_code": enterprise.get("unified_social_credit_code"),
        "legal_representative": enterprise.get("legal_representative"),
        "company_address": enterprise.get("registered_address"),
    }
    if product_inspection:
        product_models: list[str] = []
        inspection_reports: list[str] = []
        for product, report in product_inspection.items():
            if not isinstance(report, dict):
                continue
            model = report.get("specification_model")
            if model:
                product_models.append(f"{product}：{model}")
            report_no = report.get("report_no")
            if report_no:
                inspection_reports.append(f"{product}检验报告（报告编号：{report_no}）")
        values["product_models"] = product_models
        values["inspection_reports"] = inspection_reports
    certifications = facts.get("certifications") if isinstance(facts.get("certifications"), list) else []
    qualification_assets = ["营业执照副本"]
    qualification_assets.extend(
        str(cert.get("name"))
        for cert in certifications
        if isinstance(cert, dict) and cert.get("name")
    )
    if qualification_assets:
        values["qualification_assets"] = list(dict.fromkeys(qualification_assets))
    return {key: value for key, value in values.items() if value}


def build_taichang_verified_fact_context() -> str:
    facts = load_taichang_verified_fact_pack()
    if not facts:
        return "- 泰昌核验事实包当前不可用；不得从参考稿或招标样本推断企业事实。"

    enterprise = facts.get("enterprise") if isinstance(facts.get("enterprise"), dict) else {}
    rows = [
        "- 投标人：河北泰昌电力器材科技有限公司。",
        f"- 统一社会信用代码：{enterprise.get('unified_social_credit_code') or '未核验'}；法定代表人：{enterprise.get('legal_representative') or '未核验'}。",
        f"- 注册资本：{enterprise.get('registered_capital') or '未核验'}；成立日期：{enterprise.get('established_date') or '未核验'}；注册地址：{enterprise.get('registered_address') or '未核验'}。",
    ]
    for cert in facts.get("certifications") or []:
        if not isinstance(cert, dict):
            continue
        rows.append(
            f"- {cert.get('name')}：证书编号 {cert.get('certificate_no')}，有效期至 {cert.get('valid_until')}，认证机构 {cert.get('issuer')}。"
        )
    for product, report in (facts.get("product_inspection") or {}).items():
        if not isinstance(report, dict):
            continue
        parameters = "；".join(
            f"{item.get('parameter')} {item.get('inspection_result')}{item.get('unit') or ''}"
            for item in report.get("parameters") or []
            if isinstance(item, dict)
        )
        rows.append(
            f"- {product}检验报告：报告编号 {report.get('report_no')}，规格型号 {report.get('specification_model')}；{parameters}。"
        )
    performance = facts.get("project_performance") if isinstance(facts.get("project_performance"), dict) else {}
    if performance:
        rows.append(
            f"- 泰昌真实业绩：{performance.get('project_name')}，招标编号 {performance.get('tender_no')}，{performance.get('package_no')}，"
            f"产品 {performance.get('product_summary')}，数量 {performance.get('total_quantity')}，含税金额 {performance.get('amount_tax_included')}；"
            f"合同签署日期原件为空，不得推断。"
        )
    rows.append("- 河北豪乾资料只允许参考目录、表式和写法，严禁作为上述泰昌事实来源。")
    return "\n".join(rows)

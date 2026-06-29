"""Structured enterprise-basic-info lookup for Taichang verified facts."""

from __future__ import annotations

from typing import Any

from backend.services.taichang_bid_context import load_taichang_verified_fact_pack


ENTERPRISE_BASIC_TERMS = [
    "法人",
    "法定代表人",
    "法人代表",
    "负责人",
    "统一社会信用代码",
    "信用代码",
    "注册资本",
    "成立日期",
    "注册地址",
    "公司地址",
    "营业执照",
    "工商",
    "企业基本信息",
    "企业基础信息",
]

FALLBACK_ENTERPRISE = {
    "full_name": "河北泰昌电力器材科技有限公司",
    "unified_social_credit_code": "91130607056539515C",
    "legal_representative": "晁坤琳",
    "registered_capital": "10000万元人民币",
    "established_date": "2012年11月14日",
    "registered_address": "河北省保定市满城区陉阳驿村",
    "evidence": "泰昌营业执照副本及企业信用报告",
}


def is_enterprise_basic_info_query(query: str) -> bool:
    text = query or ""
    return any(term in text for term in ENTERPRISE_BASIC_TERMS)


def _enterprise_facts() -> dict[str, Any]:
    fact_pack = load_taichang_verified_fact_pack()
    enterprise = fact_pack.get("enterprise") if isinstance(fact_pack.get("enterprise"), dict) else {}
    return {**FALLBACK_ENTERPRISE, **{key: value for key, value in enterprise.items() if value}}


def _content(facts: dict[str, Any]) -> str:
    return "\n".join(
        [
            "【泰昌企业工商基础信息｜优先依据】",
            f"企业名称：{facts.get('full_name') or FALLBACK_ENTERPRISE['full_name']}",
            f"统一社会信用代码：{facts.get('unified_social_credit_code') or '-'}",
            f"法定代表人：{facts.get('legal_representative') or '-'}",
            f"注册资本：{facts.get('registered_capital') or '-'}",
            f"成立日期：{facts.get('established_date') or '-'}",
            f"注册地址：{facts.get('registered_address') or '-'}",
            f"资料来源：{facts.get('evidence') or '泰昌营业执照副本及企业信用报告'}",
            "边界：工商基础信息以营业执照、企业信用报告等基础证照为准；宣传彩页、人员花名册、劳动合同或OCR中间片段不得覆盖。",
        ]
    )


def search_taichang_enterprise_fact_contexts(query: str, limit: int = 2) -> list[dict[str, Any]]:
    """Return verified enterprise-basic-info contexts for Taichang company facts."""
    if not is_enterprise_basic_info_query(query):
        return []
    facts = _enterprise_facts()
    return [
        {
            "id": "taichang-enterprise-basic-info:business-license",
            "content": _content(facts),
            "similarity": 0.995,
            "retrieval_source": "structured_enterprise_fact_pack",
            "metadata": {
                "enterprise": "泰昌",
                "doc_owner": facts.get("full_name") or FALLBACK_ENTERPRISE["full_name"],
                "source_domain": "enterprise_fact",
                "fact_source_allowed_for_enterprise": True,
                "reference_only": False,
                "doc_type": "泰昌企业工商基础信息",
                "source_display_name": "营业执照副本",
                "category_label": "基础证照",
                "source_file": "营业执照副本",
                "source_section": "企业工商基础信息",
                "evidence_type": "business_license",
                "target_library": "qualification_library",
                "citation_policy": "enterprise_fact_citable",
                "source_category": "structured_enterprise_fact_pack",
            },
        }
    ][:limit]

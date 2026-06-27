"""Structured project-performance lookup for Taichang enterprise evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROWS_PATH = PROJECT_ROOT / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/taichang_project_performance_rows.json"
QUERY_TERMS = ["业绩", "类似项目", "同类项目", "合同", "供货合同", "合同协议书", "中标", "中标通知书", "0322AB", "TJ20220002363"]


def _load_rows(path_text: str = str(ROWS_PATH)) -> list[dict[str, Any]]:
    path = Path(path_text)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [row for row in payload if isinstance(row, dict)]


def _content(row: dict[str, Any]) -> str:
    pages = json.dumps(row.get("source_pages") or {}, ensure_ascii=False)
    sign_date = row.get("contract_sign_date") or "原件字段为空，未推断"
    return "\n".join([
        "【泰昌项目业绩结构化记录｜优先依据】",
        f"项目名称：{row.get('project_name') or '-'}",
        f"招标编号：{row.get('tender_no') or '-'}",
        f"分标/标包：{row.get('section_name') or '-'}；{row.get('package_no') or '-'}",
        f"产品：{row.get('product_summary') or '-'}",
        f"数量：{float(row.get('total_quantity') or 0):.0f} {row.get('quantity_unit') or ''}",
        f"含税金额：{float(row.get('amount_tax_included_yuan') or 0):.2f} 元",
        f"买方/招标人：{row.get('buyer') or '-'}",
        f"卖方/中标人：{row.get('seller') or '-'}",
        f"中标日期：{row.get('award_date') or '-'}",
        f"合同签署日期：{sign_date}",
        f"买方合同编号：{row.get('contract_no_buyer') or '-'}",
        f"证据类型：{row.get('evidence_type_label') or row.get('evidence_type')}",
        f"资料来源：{row.get('source_file') or '-'}",
        f"来源页码：{pages}",
        "边界：仅作为泰昌企业项目业绩事实；合同签署日期空白时不得用中标日期或交货日期替代。",
    ])


def search_taichang_project_performance_contexts(query: str, limit: int = 3) -> list[dict[str, Any]]:
    text = str(query or "")
    if not text or not any(term.lower() in text.lower() for term in QUERY_TERMS):
        return []
    contexts: list[dict[str, Any]] = []
    for row in _load_rows():
        source_file = str(row.get("source_file") or "")
        evidence = str(row.get("evidence_type") or "")
        contexts.append({
            "id": f"taichang-project-performance:{row.get('performance_id')}:{evidence}",
            "content": _content(row),
            "similarity": 0.98 if "0322AB" in text or evidence.replace("supply_", "") in text else 0.94,
            "retrieval_source": "structured_project_performance_json",
            "metadata": {
                "enterprise": "泰昌", "doc_owner": row.get("doc_owner"),
                "source_domain": "enterprise_fact", "fact_source_allowed_for_enterprise": True,
                "reference_only": False, "doc_type": "泰昌项目业绩结构化记录",
                "source_display_name": Path(source_file).stem, "category_label": "项目业绩",
                "source_file": source_file, "source_section": row.get("project_name"),
                "evidence_type": "project_performance", "target_library": "qualification_library",
                "performance_id": row.get("performance_id"), "tender_no": row.get("tender_no"),
                "package_no": row.get("package_no"), "citation_policy": "enterprise_fact_citable",
                "source_category": "structured_project_performance_json",
            },
        })
    return contexts[:limit]

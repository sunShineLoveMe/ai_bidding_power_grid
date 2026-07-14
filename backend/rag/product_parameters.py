"""Structured product-parameter lookup for Taichang staging data."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TAICHANG_PARAMETER_ROWS_PATH = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0"
    / "staging/taichang_product_parameters/taichang_product_parameter_rows.json"
)

PRODUCT_TERMS = {
    "CPVC电缆保护管": ["cpvc", "pvc-c", "pvc", "CPVC", "PVC-C", "CPVC电缆保护管"],
    "MPP电缆保护管": ["mpp", "MPP", "MPP电缆保护管"],
}

PARAMETER_SYNONYMS = {
    "环刚度": ["环刚度", "SN"],
    "平均内径": ["平均内径", "内径"],
    "壁厚": ["壁厚", "管壁厚度"],
    "长度": ["长度"],
    "不圆度": ["不圆度"],
    "弯曲度": ["弯曲度"],
    "密度": ["密度"],
    "压扁试验": ["压扁", "压扁试验"],
    "拉伸强度": ["拉伸强度"],
    "焊接强度": ["焊接强度"],
    "断裂伸长率": ["断裂伸长率", "伸长率"],
    "落锤冲击": ["落锤", "冲击", "落锤冲击"],
    "静摩擦系数": ["静摩擦", "摩擦系数", "静摩擦系数"],
    "维卡软化温度": ["维卡", "软化温度", "维卡软化温度"],
    "纵向回缩率": ["纵向回缩", "回缩率", "纵向回缩率"],
    "散热性能": ["散热", "散热性能"],
    "接头密封性能": ["接头密封", "密封性能"],
    "外观": ["外观", "颜色和外观"],
    "颜色": ["颜色"],
    "承口平均内径": ["承口平均内径"],
    "承口壁厚": ["承口壁厚"],
    "承口最小深度": ["承口最小深度"],
}


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _load_parameter_rows(path_text: str = str(TAICHANG_PARAMETER_ROWS_PATH)) -> tuple[dict[str, Any], ...]:
    path = Path(path_text)
    if not path.exists():
        return ()
    rows = json.loads(path.read_text(encoding="utf-8"))
    return tuple(row for row in rows if isinstance(row, dict))


def _query_product_families(query: str) -> set[str]:
    normalized = _normalize(query)
    families: set[str] = set()
    for family, terms in PRODUCT_TERMS.items():
        # UPVC 是独立产品族，当前又只有历史报告编号、没有原始报告；不能因
        # “pvc”子串把 CPVC 的正式参数错误注入 UPVC 问答。
        if family == "CPVC电缆保护管" and "upvc" in normalized and not any(
            term in normalized for term in ("cpvc", "pvc-c")
        ):
            continue
        if any(_normalize(term) in normalized for term in terms):
            families.add(family)
    return families


def _query_nominal_inner_diameters(query: str) -> set[str]:
    values = set(re.findall(r"(?:内径|dn|id|φ|Φ)?\s*(\d{2,4})(?:\s*(?:mm|毫米|×|x|X)|\b)", query, flags=re.I))
    if "内径250" in query or "250" in query:
        values.add("250")
    return values


def _parameter_match_score(query: str, row: dict[str, Any]) -> int:
    normalized_query = _normalize(query)
    parameter_name = str(row.get("parameter_name") or "")
    normalized_name = _normalize(parameter_name)
    score = 0

    # “平均内径/壁厚”与“承口平均内径/承口壁厚”在同一报告中同时存在。
    # 用户未明确提到“承口”时，不能用承口尺寸替代管体尺寸。
    if "承口" in parameter_name and "承口" not in normalized_query and any(
        term in normalized_query for term in ("平均内径", "内径", "壁厚", "管壁厚度")
    ):
        return 0

    explicit_parameter_query = any(
        _normalize(synonym) in normalized_query
        for synonyms in PARAMETER_SYNONYMS.values()
        for synonym in synonyms
    )
    if normalized_name and normalized_name in normalized_query:
        score += 8
    for canonical, synonyms in PARAMETER_SYNONYMS.items():
        row_hits_canonical = canonical in parameter_name or canonical in str(row.get("parameter_category") or "")
        if not row_hits_canonical:
            continue
        for synonym in synonyms:
            if _normalize(synonym) in normalized_query:
                score += 6
                break
    if score == 0 and not explicit_parameter_query:
        # For broad product-parameter questions, allow core inspection rows but keep
        # them below explicitly requested parameter names.
        if any(term in normalized_query for term in ["参数", "检验结果", "检测结果", "标准要求"]):
            score += 1
    return score


def _has_explicit_parameter_request(query: str) -> bool:
    normalized_query = _normalize(query)
    return any(
        _normalize(synonym) in normalized_query
        for synonyms in PARAMETER_SYNONYMS.values()
        for synonym in synonyms
    )


def _row_match_score(query: str, row: dict[str, Any]) -> int:
    parameter_score = _parameter_match_score(query, row)
    score = parameter_score
    families = _query_product_families(query)
    diameters = _query_nominal_inner_diameters(query)
    if parameter_score <= 0 and _has_explicit_parameter_request(query):
        return 0
    if parameter_score <= 0 and not families and not diameters:
        return 0
    if families:
        if row.get("product_family") in families:
            score += 5
        else:
            # 产品族已明确时采用硬过滤，避免把 MPP 的同名参数混入 CPVC，反之亦然。
            return 0
    if diameters:
        if str(row.get("nominal_inner_diameter") or "") in diameters:
            score += 4
        else:
            score -= 4
    if "泰昌" in query:
        score += 2
    return score


def _content_for_row(row: dict[str, Any]) -> str:
    source_name = Path(str(row.get("source_file") or "")).stem or "泰昌产品检验报告"
    return "\n".join(
        [
            "【泰昌产品结构化参数｜优先依据】",
            f"企业：{row.get('doc_owner') or '河北泰昌电力器材科技有限公司'}",
            f"产品：{row.get('product_family') or row.get('sample_name') or '-'}",
            f"规格型号：{row.get('specification_model') or '-'}",
            f"公称内径：{row.get('nominal_inner_diameter') or '-'}",
            f"参数名称：{row.get('parameter_name') or '-'}",
            f"单位：{row.get('unit') or '-'}",
            f"标准要求：{row.get('standard_requirement') or '-'}",
            f"检验结果：{row.get('inspection_result') or '-'}",
            f"单项结论：{row.get('single_conclusion') or '-'}",
            f"报告编号：{row.get('report_no') or '-'}",
            f"资料来源：{source_name}",
            f"来源页码：第{row.get('source_page') or '-'}页",
            "边界：本参数来自泰昌原始检验报告，只能作为泰昌企业事实；辽宁资料仅可作QA/异常校验参照，不构成覆盖辽宁全部规格的结论。",
        ]
    )


def search_taichang_product_parameter_contexts(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return structured parameter rows as RAG contexts for Taichang questions."""
    if not query or "泰昌" not in query and not any(_normalize(term) in _normalize(query) for terms in PRODUCT_TERMS.values() for term in terms):
        return []
    normalized_query = _normalize(query)
    if any(term in normalized_query for term in ("upvc", "n-hap", "nhap")) and not any(
        term in normalized_query for term in ("cpvc", "pvc-c", "mpp")
    ):
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in _load_parameter_rows():
        score = _row_match_score(query, row)
        if score <= 0:
            continue
        scored.append((score, row))
    scored.sort(
        key=lambda item: (
            item[0],
            str(item[1].get("product_family") or ""),
            str(item[1].get("parameter_name") or ""),
        ),
        reverse=True,
    )
    contexts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for score, row in scored:
        key = (
            str(row.get("report_no") or ""),
            str(row.get("specification_model") or ""),
            str(row.get("parameter_name") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        parameter_name = str(row.get("parameter_name") or "")
        contexts.append(
            {
                "id": f"taichang-product-parameter:{row.get('report_no')}:{parameter_name}",
                "content": _content_for_row(row),
                "similarity": min(0.99, 0.72 + score / 40),
                "retrieval_source": "structured_product_parameter_json",
                "metadata": {
                    "enterprise": "泰昌",
                    "doc_owner": row.get("doc_owner") or "河北泰昌电力器材科技有限公司",
                    "source_domain": "enterprise_fact",
                    "fact_source_allowed_for_enterprise": True,
                    "reference_only": False,
                    "doc_type": "泰昌产品结构化参数",
                    "source_display_name": Path(str(row.get("source_file") or "")).stem or "泰昌产品检验报告",
                    "category_label": "泰昌产品结构化参数",
                    "source_file": row.get("source_file"),
                    "source_page": row.get("source_page"),
                    "source_section": parameter_name,
                    "evidence_type": row.get("evidence_type") or "inspection_report",
                    "target_library": row.get("target_library") or "product_library",
                    "report_no": row.get("report_no"),
                    "product_family": row.get("product_family"),
                    "specification_model": row.get("specification_model"),
                    "nominal_inner_diameter": row.get("nominal_inner_diameter"),
                    "parameter_name": parameter_name,
                    "qa_reference_scope": row.get("qa_reference_scope"),
                    "citation_policy": "enterprise_fact_citable",
                    "source_category": "structured_product_parameter_json",
                },
            }
        )
        if len(contexts) >= limit:
            break
    return contexts

"""泰昌企业知识库的产品范围与证据类型预过滤。"""

from __future__ import annotations

from typing import Any


PRODUCT_SCOPES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("CPVC电缆保护管", ("CPVC", "PVC-C"), "电缆保护管CPVC"),
    ("MPP电缆保护管", ("MPP",), "电缆保护管MPP"),
    ("N-HAP电缆保护管", ("N-HAP", "NHAP"), "电缆保护管N-HAP"),
    ("UPVC电缆保护管", ("UPVC",), "电缆保护管UPVC"),
    ("架空绝缘导线", ("架空绝缘导线", "绝缘导线"), "架空绝缘导线"),
)


def infer_taichang_product_scope(query: str) -> dict[str, str] | None:
    """从问题中识别唯一产品范围；多产品问题不追加产品硬过滤。"""
    text = str(query or "").upper().replace("—", "-")
    matches: list[dict[str, str]] = []
    for family, aliases, material_category in PRODUCT_SCOPES:
        if any(alias.upper() in text for alias in aliases):
            matches.append({"product_family": family, "material_category": material_category})
    unique = {(item["product_family"], item["material_category"]) for item in matches}
    if len(unique) != 1:
        return None
    return matches[0]


def infer_taichang_evidence_type(query: str, product_scope: dict[str, str] | None = None) -> str | None:
    """仅在意图唯一时追加 evidence_type 预过滤，避免泛问被过度收窄。"""
    text = str(query or "")
    if product_scope and product_scope.get("product_family") == "架空绝缘导线":
        return "scope_guard"
    rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("inspection_report", ("检验报告", "检测报告", "型式试验", "参数", "环刚度", "平均内径", "壁厚")),
        ("testing_capacity", ("检测设备", "试验设备", "校准", "检定", "复校")),
        ("project_performance", ("项目业绩", "类似业绩", "供货合同", "中标通知书")),
        ("personnel_certificate", ("人员证书", "特种作业证", "证件号")),
        ("personnel_roster", ("人员花名册", "人员名单", "员工名单")),
        ("finance", ("审计报告", "财务报告", "财务审计")),
    )
    matched = [evidence_type for evidence_type, terms in rules if any(term in text for term in terms)]
    return matched[0] if len(set(matched)) == 1 else None


def build_taichang_scope_filter(query: str, explicit_filter: dict[str, Any] | None = None) -> dict[str, Any]:
    """构建进入向量检索前的泰昌 metadata 过滤条件。"""
    result: dict[str, Any] = {
        "enterprise": "泰昌",
        "source_domain": "enterprise_fact",
        "fact_source_allowed_for_enterprise": True,
        "reference_only": False,
    }
    for key, value in (explicit_filter or {}).items():
        if value not in (None, "", "all"):
            result[key] = value
    product_scope = infer_taichang_product_scope(query)
    if product_scope:
        # document_chunks 使用数组保存一份事实可能覆盖的多个产品族；RPC 的
        # JSONB containment 可用单元素数组在召回前命中对应范围。
        result.setdefault("product_family", [product_scope["product_family"]])
        result.setdefault("material_category", [product_scope["material_category"]])
    evidence_type = infer_taichang_evidence_type(query, product_scope)
    if evidence_type:
        result.setdefault("evidence_type", evidence_type)
    return result

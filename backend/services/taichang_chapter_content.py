"""泰昌专版章节内容复用清单。

本模块只做确定性资料装配：当前章节先匹配 P1-04 语义映射，再按映射中明确的
结构化来源、知识资产和证据包取数。它不会对全库做相似度拼装，也不会把
``knowledge_only`` 图片提升为可插入 DOCX 的正式证据。
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = REPO_ROOT / "docs/development/taichang-bid-v1-data/p1_04_chapter_evidence_mapping/taichang_bid_evidence_mapping.json"
CHUNK_PATH = REPO_ROOT / "docs/development/taichang-bid-v1-data/p1_05_rag_baseline/taichang_structured_rag_chunks.json"
ASSET_PATH = REPO_ROOT / "docs/development/taichang-bid-v1-data/p1_01_ingestion/taichang_historical_bid_asset_ingestion.json"
BUNDLE_PATH = REPO_ROOT / "docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundles.json"

TAICHANG_CONTENT_PROFILE = {
    "profile_id": "taichang_bid_content_reuse_v1",
    "enterprise": "河北泰昌电力器材科技有限公司",
    "skeleton_policy": "current_tender_only",
    "historical_bid_policy": "content_clue_and_layout_reference_only",
    "structured_fact_policy": "precise_values_must_use_structured_rows_or_primary_evidence",
    "knowledge_asset_policy": "writing_context_only_exclude_from_docx",
    "formal_evidence_policy": "bundle_must_pass_current_project_validity_and_scope_checks",
}


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=16)
def _load_json(path_text: str) -> Any:
    return _read_json(Path(path_text))


def clear_taichang_chapter_content_cache() -> None:
    """供资料刷新脚本和测试显式失效缓存。"""
    _load_json.cache_clear()


def _normalize(value: Any) -> str:
    return re.sub(r"[\s（）()\[\]【】《》、，,。；;：:\-—_/]", "", str(value or "")).lower()


def _stable_id(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _mapping_matches_chapter(mapping: dict[str, Any], chapter: dict[str, Any]) -> bool:
    metadata = chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}
    explicit_key = str(metadata.get("semantic_key") or chapter.get("semantic_key") or "")
    if explicit_key and explicit_key == mapping.get("semantic_chapter_key"):
        return True

    title = _normalize(chapter.get("title"))
    if not title:
        return False
    chapter_match = mapping.get("chapter_match") if isinstance(mapping.get("chapter_match"), dict) else {}
    if any(_normalize(word) in title for word in chapter_match.get("exclude_keywords") or [] if word):
        return False
    # 招标原表常只写“技术特性参数表”，产品族来自技术规范或货物清单；
    # 只有产品族明确时才允许绑定对应泰昌参数，未知时宁可不命中。
    if _normalize(chapter.get("title")) == _normalize("技术特性参数表"):
        product_families = metadata.get("product_families") or []
        product_text = " ".join(str(item) for item in product_families)
        semantic_key = str(mapping.get("semantic_chapter_key") or "")
        return ("mpp" in semantic_key and "MPP" in product_text) or ("cpvc" in semantic_key and "CPVC" in product_text.upper())
    candidates = [mapping.get("chapter_display_name"), *(chapter_match.get("aliases") or [])]
    if any(
        normalized and (normalized in title or title in normalized)
        for candidate in candidates
        if (normalized := _normalize(candidate))
    ):
        return True
    if mapping.get("semantic_chapter_key") == "enterprise.basic_profile":
        return "投标人基本情况" in str(chapter.get("title") or "")
    return False


def _source_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("rows", "records", "items", "evidence"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _matches_selector(row: dict[str, Any], selector: dict[str, Any]) -> bool:
    for key, expected in selector.items():
        if key.endswith("s") and isinstance(expected, list):
            singular = key[:-1]
            actual = row.get(key, row.get(singular))
            actual_values = actual if isinstance(actual, list) else [actual]
            if not any(value in expected for value in actual_values):
                return False
            continue
        actual = row.get(key)
        if key == "project_id" and actual in (None, ""):
            actual = row.get("performance_id")
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif str(actual or "") != str(expected or ""):
            return False
    return True


def _row_identifier(row: dict[str, Any]) -> str:
    if row.get("performance_id"):
        return f"{row['performance_id']}:{row.get('evidence_type') or 'evidence'}"
    for key in ("row_id", "business_key", "performance_id", "project_id", "candidate_id", "evidence_id"):
        if row.get(key):
            return str(row[key])
    return _stable_id("row", {
        "ledger_type": row.get("ledger_type"),
        "report_no": row.get("report_no"),
        "parameter_name": row.get("parameter_name"),
        "source_file": row.get("source_file"),
        "source_page": row.get("source_page"),
        "row_number": row.get("row_number"),
    })


def _resolve_fact_rows(mapping: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    resolved: list[dict[str, Any]] = []
    errors: list[str] = []
    for ref in mapping.get("fact_refs") or []:
        source = str(ref.get("source") or "")
        path = REPO_ROOT / source
        selector = ref.get("selector") if isinstance(ref.get("selector"), dict) else {}
        if source == "backend/rag/enterprise_facts.py" and selector.get("profile") == "taichang_verified_enterprise_profile":
            from backend.services.taichang_bid_context import load_taichang_verified_fact_pack

            facts = load_taichang_verified_fact_pack()
            enterprise = facts.get("enterprise") if isinstance(facts.get("enterprise"), dict) else {}
            if enterprise:
                resolved.append({
                    "row_id": "taichang-verified-enterprise-profile",
                    "source": source,
                    "source_file": (facts.get("source_files") or [source])[0],
                    "source_page": 1,
                    "ledger_type": "enterprise_profile",
                    "business_key": "enterprise:91130607056539515C",
                    "product_family": None,
                    "report_no": None,
                    "parameter_name": None,
                    "inspection_result": None,
                    "unit": None,
                    "validity_status": "verified",
                    "usage": ref.get("usage"),
                    "raw": enterprise,
                })
            continue
        if not source or not path.exists():
            errors.append(f"结构化来源不可用：{source or '未配置'}")
            continue
        rows = [row for row in _source_rows(_load_json(str(path))) if _matches_selector(row, selector)]
        for row in rows:
            resolved.append({
                "row_id": _row_identifier(row),
                "source": source,
                "source_file": row.get("source_file") or source,
                "source_page": row.get("source_page"),
                "ledger_type": row.get("ledger_type"),
                "business_key": row.get("business_key"),
                "product_family": row.get("product_family"),
                "report_no": row.get("report_no"),
                "parameter_name": row.get("parameter_name"),
                "inspection_result": row.get("inspection_result"),
                "unit": row.get("unit"),
                "validity_status": row.get("validity_status"),
                "usage": ref.get("usage"),
                "raw": row,
            })
    unique = {item["row_id"]: item for item in resolved}
    return list(unique.values()), errors


def _resolve_assets(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    candidate_ids = set(mapping.get("resolved_knowledge_asset_candidate_ids") or [])
    if not candidate_ids:
        return []
    records = _source_rows(_load_json(str(ASSET_PATH)))
    return [
        {
            "knowledge_asset_id": row.get("candidate_id"),
            "title": row.get("title_after_ingestion") or row.get("reviewed_title") or row.get("title"),
            "source_file": row.get("source_file"),
            "source_page": row.get("source_page"),
            "source_section": row.get("source_section"),
            "evidence_type": row.get("evidence_type"),
            "quality_tier": row.get("quality_tier_after_review") or row.get("quality_tier"),
            "writing_context_allowed": bool(row.get("ready_for_database_ingestion")),
            "docx_allowed": False,
            "usage_restriction": row.get("usage_restriction"),
        }
        for row in records
        if row.get("candidate_id") in candidate_ids and row.get("ready_for_database_ingestion") is True
    ]


def _resolve_bundles(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    bundle_ids = set(mapping.get("evidence_bundle_ids") or [])
    bundles = (_load_json(str(BUNDLE_PATH)) or {}).get("bundles") or []
    return [
        {
            "evidence_bundle_id": row.get("evidence_bundle_id"),
            "bundle_title": row.get("bundle_title"),
            "bundle_kind": row.get("bundle_kind"),
            "evidence_type": row.get("evidence_type"),
            "page_count": row.get("page_count"),
            "allowed_for_bid": bool(row.get("allowed_for_bid")),
            "usage_status": row.get("usage_status"),
            "warnings": row.get("warnings") or [],
            "primary_sources": row.get("primary_sources") or [],
        }
        for row in bundles
        if row.get("evidence_bundle_id") in bundle_ids
    ]


def _resolve_chunks(mapping: dict[str, Any], fact_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = {str(item.get("source_file") or "") for item in fact_rows if item.get("source_file")}
    business_keys = {str(item.get("business_key") or "") for item in fact_rows if item.get("business_key")}
    business_keys.update(
        f"report:{item.get('report_no')}"
        for item in fact_rows
        if item.get("report_no")
    )
    chunks = _load_json(str(CHUNK_PATH))
    resolved: list[dict[str, Any]] = []
    for row in chunks if isinstance(chunks, list) else []:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if meta.get("chunk_layer") != "child":
            continue
        source_match = str(meta.get("source_file") or "") in sources
        key_match = str(meta.get("business_key") or "") in business_keys
        if not (source_match or key_match):
            continue
        resolved.append({
            "chunk_id": f"taichang-p1-05-{row.get('chunk_index')}",
            "chunk_index": row.get("chunk_index"),
            "content": row.get("content"),
            "source_file": meta.get("source_file"),
            "source_page": meta.get("source_page"),
            "business_key": meta.get("business_key"),
            "evidence_type": meta.get("evidence_type"),
        })
    return resolved


def build_chapter_content_manifest(chapter: dict[str, Any]) -> dict[str, Any] | None:
    """为一个动态章节生成确定性的正文资料使用清单。"""
    mappings = (_load_json(str(MAPPING_PATH)) or {}).get("mappings") or []
    matched = [mapping for mapping in mappings if _mapping_matches_chapter(mapping, chapter)]
    if not matched:
        return None

    mapping = matched[0]
    fact_rows, resolution_errors = _resolve_fact_rows(mapping)
    assets = _resolve_assets(mapping)
    bundles = _resolve_bundles(mapping)
    chunks = _resolve_chunks(mapping, fact_rows)
    source_files = sorted({
        str(item.get("source_file"))
        for item in [*fact_rows, *assets, *chunks]
        if item.get("source_file")
    })
    for bundle in bundles:
        source_files.extend(
            str(source.get("source_file"))
            for source in bundle.get("primary_sources") or []
            if source.get("source_file")
        )
    source_pages = sorted({
        int(page)
        for item in [*fact_rows, *assets, *chunks]
        if (page := item.get("source_page")) not in (None, "") and str(page).isdigit()
    })
    blockers = [*(mapping.get("blockers") or []), *resolution_errors]
    return {
        "manifest_version": "taichang_chapter_content_manifest.v1",
        "profile_id": TAICHANG_CONTENT_PROFILE["profile_id"],
        "section_id": chapter.get("id"),
        "section_title": chapter.get("title"),
        "volume_type": mapping.get("bid_volume"),
        "semantic_key": mapping.get("semantic_chapter_key"),
        "mapping_id": mapping.get("mapping_id"),
        "material_status": mapping.get("material_status"),
        "structured_row_ids": [item["row_id"] for item in fact_rows],
        "chunk_ids": [item["chunk_id"] for item in chunks],
        "knowledge_asset_ids": [item["knowledge_asset_id"] for item in assets],
        "evidence_bundle_ids": [item["evidence_bundle_id"] for item in bundles],
        "source_files": sorted(set(source_files)),
        "source_pages": source_pages,
        "confirmations": mapping.get("customer_confirmation_fields") or [],
        "blockers": blockers,
        "structured_rows": fact_rows,
        "rag_chunks": chunks,
        "knowledge_assets": assets,
        "evidence_bundles": bundles,
        "generation_policy": mapping.get("generation_policy"),
        "knowledge_only_docx_allowed": False,
        "precise_value_source_policy": "structured_row_or_primary_evidence_only",
    }


def chapter_content_prompt_context(manifest: dict[str, Any] | None, *, max_rows: int = 12, max_chunks: int = 8) -> str:
    if not manifest:
        return "- 当前章节未命中泰昌专版资料映射；不得从全库随机拼装企业事实。"
    rows = manifest.get("structured_rows") or []
    row_lines = []
    selected_rows = list(rows[:max_rows])
    certificate_rows = [item for item in rows if item.get("ledger_type") == "personnel_certificate"]
    if certificate_rows and not any(item.get("ledger_type") == "personnel_certificate" for item in selected_rows):
        selected_rows = [*selected_rows[: max(0, max_rows - len(certificate_rows[:2]))], *certificate_rows[:2]]
    for item in selected_rows:
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        visible = []
        for key in (
            "person_name", "project_role", "education", "professional_title", "certificate_name",
            "certificate_no", "valid_until", "audit_year", "report_no", "project_name", "tender_no",
            "package_no", "product_summary", "total_quantity", "quantity_unit", "amount_tax_included_yuan",
            "product_family", "specification_model", "parameter_name", "standard_requirement",
            "inspection_result", "unit", "validity_status",
        ):
            value = raw.get(key)
            if value not in (None, "", []):
                visible.append(f"{key}={value}")
        row_lines.append(f"- {item['row_id']}：{'；'.join(visible) or '详见结构化原始行'}；来源 {item.get('source_file')} 第{item.get('source_page') or '待核'}页")
    chunk_lines = [
        f"- {item.get('chunk_id')}：{str(item.get('content') or '')[:180]}"
        for item in (manifest.get("rag_chunks") or [])[:max_chunks]
    ]
    asset_lines = [
        f"- {item.get('knowledge_asset_id')}：{item.get('title')}（仅作写作线索，禁止作为 DOCX 正式图片）"
        for item in (manifest.get("knowledge_assets") or [])[:8]
    ]
    bundle_lines = [
        f"- {item.get('evidence_bundle_id')}：{item.get('bundle_title')}，{item.get('page_count')}页，状态 {item.get('usage_status')}"
        for item in (manifest.get("evidence_bundles") or [])[:8]
    ]
    return "\n".join([
        f"- 语义章节：{manifest.get('semantic_key')}；资料状态：{manifest.get('material_status')}",
        "- 精确数值只能来自下列结构化行或正式证据；知识资料不得用于推断数值。",
        "结构化事实：",
        *(row_lines or ["- 无；涉及精确事实时必须保留缺口。"]),
        "结构化 RAG 写作依据：",
        *(chunk_lines or ["- 无。"]),
        "历史知识资料：",
        *(asset_lines or ["- 无。"]),
        "正式证据包：",
        *(bundle_lines or ["- 无。"]),
        "必须确认：",
        *([f"- {item}" for item in manifest.get("confirmations") or []] or ["- 无新增确认项。"]),
        "阻断与限制：",
        *([f"- {item}" for item in manifest.get("blockers") or []] or ["- 无。"]),
    ])


def _md(value: Any) -> str:
    text = str(value if value not in (None, "", "****") else "—").replace("|", "｜").replace("\n", " ")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return {"valid": "有效", "expired": "已过期"}.get(text, text)


def render_grounded_chapter_draft(manifest: dict[str, Any]) -> str:
    """渲染高精度章节正式草稿；不让模型改写结构化事实。"""
    semantic_key = str(manifest.get("semantic_key") or "")
    rows = [item.get("raw") or {} for item in manifest.get("structured_rows") or []]

    if semantic_key == "manufacturing.quality_control":
        certificate_rows = [row for row in rows if row.get("ledger_type") == "management_certificate"]
        table = [
            "| 证书名称 | 证书编号 | 有效期至 | 当前状态 | 来源页 |",
            "| --- | --- | --- | --- | ---: |",
            *[
                f"| {_md(row.get('certificate_name'))} | {_md(row.get('certificate_no'))} | {_md(row.get('valid_until'))} | {_md(row.get('validity_status'))} | {_md(row.get('source_page'))} |"
                for row in certificate_rows
            ],
        ]
        return "\n".join([
            "### 产品制造质量控制",
            "",
            "河北泰昌电力器材科技有限公司现有两项与本章相关、仍在有效期内的管理体系认证事实如下。证书有效期和适用范围在正式投标前仍应按项目日期复核。",
            "",
            *table,
            "",
            f"现有历史资料中另有 {len(manifest.get('knowledge_asset_ids') or [])} 项工序控制类知识资料。这些资料的当前等级为知识资料，只能作为正文组织和人工复核线索；其图片不得直接插入正式 DOCX，其内容也不能单独证明本项目的质量目标、质量保证期、具体工艺参数或过程控制措施。",
            "",
            "本章当前可正式落笔的范围仅包括上述证书事实及资料边界。项目质量目标、质量保证期和适用标准必须以当次招标文件与客户确认结果为准，未确认前不形成承诺性结论。",
        ])

    if semantic_key == "manufacturing.process.mpp":
        parameter_rows = [row for row in rows if row.get("parameter_name")]
        first = parameter_rows[0] if parameter_rows else {}
        table = [
            "| 检验项目 | 标准要求 | 检验结果 | 单位 | 单项结论 | 来源页 |",
            "| --- | --- | --- | --- | --- | ---: |",
            *[
                f"| {_md(row.get('parameter_name'))} | {_md(row.get('standard_requirement'))} | {_md(row.get('inspection_result'))} | {_md(row.get('unit'))} | {_md(row.get('single_conclusion') or row.get('inspection_conclusion'))} | {_md(row.get('source_page'))} |"
                for row in parameter_rows
            ],
        ]
        return "\n".join([
            "### MPP生产工艺资料与检验事实",
            "",
            f"现有可核验事实来自泰昌 MPP 电缆保护管检验报告，报告编号为 {_md(first.get('report_no'))}，规格型号为 {_md(first.get('specification_model'))}。报告中的结构化检验结果如下：",
            "",
            *table,
            "",
            "上述检验结果只证明该报告对应规格送检样品的产品检验事实，不能替代 MPP 专属生产工艺文件，也不能推导其他规格或本项目需求规格已经覆盖。现有工序控制类历史资料仍为知识线索，正式成稿如需描述生产步骤、过程参数或质量控制点，必须取得并核验相应原始工艺文件。",
        ])

    if semantic_key == "qualification.personnel_roster_and_certificates":
        roster_rows = [row for row in rows if row.get("ledger_type") == "personnel_roster"]
        certificate_rows = [row for row in rows if row.get("ledger_type") == "personnel_certificate"]
        roster_table = [
            "| 序号 | 姓名 | 在册岗位 | 学历 | 社保记录 | 劳动合同记录 | 来源页 |",
            "| ---: | --- | --- | --- | --- | --- | ---: |",
            *[
                f"| {_md(row.get('roster_row_no'))} | {_md(row.get('person_name'))} | {_md(row.get('project_role'))} | {_md(row.get('education'))} | {'有' if row.get('social_insurance_recorded') else '—'} | {'有' if row.get('labor_contract_recorded') else '—'} | {_md(row.get('source_page'))} |"
                for row in roster_rows[:10]
            ],
        ]
        certificate_table = [
            "| 姓名 | 证书编号 | 准操项目 | 复审日期 | 有效期至 | 来源页 |",
            "| --- | --- | --- | --- | --- | ---: |",
            *[
                f"| {_md(row.get('person_name'))} | {_md(row.get('certificate_no'))} | {_md(row.get('permitted_operation'))} | {_md(row.get('review_date'))} | {_md(row.get('valid_until'))} | {_md(row.get('source_page'))} |"
                for row in certificate_rows
            ],
        ]
        return "\n".join([
            "### 人员组织与人员证书",
            "",
            f"泰昌现有人员花名册共 {len(roster_rows)} 行。以下列示前 10 行用于正文样式与事实引用验证，完整人员范围以原始花名册为准。",
            "",
            *roster_table,
            "",
            "现有两行人员证书结构化记录如下：",
            "",
            *certificate_table,
            "",
            "花名册中的在册岗位不等同于本项目岗位任命。正式投标时必须按当次招标岗位要求、实际分工和证书有效期选择人员，并以项目任命和原始证书复核结果为准。",
        ])

    if semantic_key == "performance.project_evidence":
        award = next((row for row in rows if row.get("evidence_type") == "award_notice"), rows[0] if rows else {})
        contract = next((row for row in rows if row.get("evidence_type") == "supply_contract"), {})
        return "\n".join([
            "### 项目业绩",
            "",
            "| 项目名称 | 招标编号 | 分标/包号 | 产品 | 数量 | 含税金额 | 买方 | 卖方 | 中标日期 | 合同签署日期 |",
            "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
            f"| {_md(award.get('project_name'))} | {_md(award.get('tender_no'))} | {_md(award.get('section_name'))} / {_md(award.get('package_no'))} | {_md(award.get('product_summary'))} | {_md(award.get('total_quantity'))} {_md(award.get('quantity_unit'))} | {_md(award.get('amount_tax_included_yuan'))} 元 | {_md(award.get('buyer'))} | {_md(award.get('seller'))} | {_md(award.get('award_date'))} | {_md(contract.get('contract_sign_date'))} |",
            "",
            "本项业绩由中标通知书和供货合同两类原始证据共同支持。合同签署日期在现有原件中为空，因此保持为空，不以中标日期、交货日期或其他日期推断。正文仅陈述证据已明确的项目、产品、数量、金额、双方和中标日期，不对履约验收或当前项目适配性作无依据结论。",
        ])

    raise ValueError(f"暂不支持的泰昌高精度章节：{semantic_key}")

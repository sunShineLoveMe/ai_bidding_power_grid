#!/usr/bin/env python3
"""生成泰昌历史标书候选的标签、分类、中文展示字段和人工审核队列。

本脚本属于 P0-05 只读数据治理：不连接数据库、不写 RAG、不修改正式资产。
只有通过可选批准清单且满足全部门禁的记录才会进入 asset_ingestion_candidates；
默认没有 P0-06 人工批准，因此正式入库候选清单为空。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "docs/development/taichang-bid-v1-data"
DEFAULT_DEDUP = DATA_DIR / "asset_dedup_matrix.json"
DEFAULT_TECHNICAL = DATA_DIR / "taichang_technical_bid_candidate_inventory.json"
DEFAULT_BUSINESS = DATA_DIR / "taichang_business_bid_candidate_inventory.json"
DEFAULT_DICTIONARY = DATA_DIR / "tag_dictionary.json"
DEFAULT_CLASSIFICATION_JSON = DATA_DIR / "asset_classification_matrix.json"
DEFAULT_CLASSIFICATION_CSV = DATA_DIR / "asset_classification_matrix.csv"
DEFAULT_REVIEW_JSON = DATA_DIR / "asset_review_queue.json"
DEFAULT_REVIEW_CSV = DATA_DIR / "asset_review_queue.csv"
DEFAULT_INGESTION_JSON = DATA_DIR / "asset_ingestion_candidates.json"
DEFAULT_INGESTION_CSV = DATA_DIR / "asset_ingestion_candidates.csv"
DEFAULT_REPORT = PROJECT_ROOT / "docs/development/taichang-v1-tag-classification-report-20260713.md"

ENTERPRISE = "河北泰昌电力器材科技有限公司"
VISIBLE_FIELDS = (
    "title",
    "source_display_name",
    "source_document_name",
    "category_label",
    "evidence_type_label",
    "target_library_label",
    "dedup_status_label",
    "description",
    "formal_caption",
)
FORBIDDEN_VISIBLE_PATTERNS = (
    "taichang_",
    "power_grid_",
    "production_capacity",
    "testing_capacity",
    "green_low_carbon",
    "business_license",
    "certification",
    "product_image",
    "technical",
    "页面_",
    "原图",
    "parsed_outputs",
    "rag_seed",
    "/api/",
)
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
HASH_RE = re.compile(r"\b[0-9a-f]{24,64}\b", re.I)

EVIDENCE_LABELS = {
    "historical_structure_reference": "历史目录结构参考",
    "historical_form_reference": "历史表单结构参考",
    "project_context": "历史项目上下文",
    "product_parameter_table": "产品参数表",
    "technical_response": "技术响应资料",
    "business_license": "基础证照",
    "certification": "资质证书",
    "finance": "财务资料",
    "personnel_certificate": "人员证书",
    "project_performance": "项目业绩",
    "authorization": "授权文件",
    "inspection_report": "检验报告",
    "production_capacity": "生产制造能力",
    "testing_capacity": "试验检测能力",
    "green_low_carbon": "绿色低碳资料",
    "product_image": "产品实物图片",
    "enterprise_evidence": "企业证明材料",
}

TARGET_LIBRARY_LABELS = {
    "knowledge_library": "知识库资料",
    "product_library": "产品库资料",
    "qualification_library": "资信库资料",
    "reference_template_library": "历史参考资料",
}

QUALITY_LABELS = {
    "formal_bid_ready": "正式标书可用",
    "knowledge_only": "仅用于知识检索",
    "review_only": "仅限人工复核",
    "restricted": "受限资料",
}

REVIEW_LABELS = {
    "not_asset_reference": "非资产结构参考",
    "rejected_duplicate": "精确重复，不新增",
    "rejected_conflict": "事实冲突，禁止复用",
    "needs_manual_review": "需要人工复核",
    "needs_customer_confirmation": "需要客户确认",
    "approved": "已批准",
    "rejected": "已驳回",
}

SENSITIVITY_LABELS = {
    "internal": "企业内部资料",
    "sensitive": "敏感资料",
    "restricted": "受限资料",
}

DEDUP_STATUS_LABELS = {
    "new": "未发现重复，仍需审核",
    "duplicate_exact": "精确重复，不新增",
    "possible_visual_duplicate": "视觉疑似重复",
    "possible_text_duplicate": "文本疑似重复",
    "same_evidence_new_rendition": "同一证据的不同载体",
    "fact_conflict": "事实冲突",
}

CSV_FIELDS = [
    "candidate_id",
    "bid_volume",
    "record_type",
    "source_page",
    "dedup_status",
    "dedup_status_label",
    "enterprise",
    "doc_owner",
    "source_domain",
    "target_library",
    "target_library_label",
    "evidence_type",
    "evidence_type_label",
    "product_families",
    "material_category",
    "applicable_volumes",
    "applicable_sections",
    "origin_type",
    "validity_status",
    "sensitivity",
    "sensitivity_label",
    "quality_tier",
    "quality_tier_label",
    "review_status",
    "review_status_label",
    "title",
    "source_display_name",
    "source_document_name",
    "category_label",
    "description",
    "tags",
    "caption_policy",
    "formal_caption",
    "evidence_bundle_id",
    "manual_review_required",
    "approved_candidate",
    "ingestion_eligible",
    "ingestion_action",
    "ingestion_block_reason",
    "classification_confidence",
    "source_file",
    "source_section",
    "content_sha256",
    "media_sha256",
]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_section(value: Any) -> str:
    text = _text(value)
    text = re.sub(r"（上传投标工具路径.*?）", "", text)
    text = re.sub(r"\(上传投标工具路径.*?\)", "", text)
    text = re.sub(r"\s+", "", text)
    return text or "未归入历史章节"


def _leaf_sections(source_section: Any) -> list[str]:
    parts = [_clean_section(item) for item in _text(source_section).split(" / ") if _text(item)]
    result: list[str] = []
    for part in parts[-2:]:
        cleaned = re.sub(r"^[（(]?[一二三四五六七八九十\d]+(?:[.、．][\d一二三四五六七八九十]+)*[)）.、．]?", "", part)
        cleaned = cleaned.strip("：:、.． ") or part
        if cleaned not in result:
            result.append(cleaned)
    return result or ["未归入历史章节"]


def _product_families(blob: str, evidence_type: str) -> list[str]:
    upper = blob.upper().replace(" ", "")
    families: list[str] = []
    if "CPVC" in upper or "PVC-C" in upper:
        families.append("CPVC电缆保护管")
    if "MPP" in upper:
        families.append("MPP电缆保护管")
    if "N-HAP" in upper or "NHAP" in upper:
        families.append("N-HAP电缆保护管")
    if "UPVC" in upper or "PVC-U" in upper or "硬聚氯乙烯" in blob:
        families.append("UPVC电缆保护管")
    if not families and "电缆保护管" in blob:
        families.append("电缆保护管（材质待确认）")
    if not families and evidence_type in {"production_capacity", "testing_capacity", "product_parameter_table"}:
        families.append("电缆保护管通用")
    return families


def _classify_evidence(original: dict[str, Any], bid_volume: str) -> tuple[str, str, float]:
    record_type = _text(original.get("record_type"))
    fact_kind = _text(original.get("fact_kind"))
    leaf_section = _text(original.get("source_section")).split(" / ")[-1]
    blob = " ".join(
        _text(original.get(key))
        for key in ("title", "form_name", "content_role", "fact_kind")
    )
    blob = f"{blob} {leaf_section}"
    if record_type == "chapter":
        return "historical_structure_reference", "reference_template_library", 1.0
    if record_type == "table":
        if any(token in blob for token in ("技术特性参数", "技术参数", "偏差表", "货物组件材料配置")):
            return "product_parameter_table", "product_library", 0.9
        return "historical_form_reference", "reference_template_library", 0.85
    if fact_kind in {"project_identifier", "fixed_parameter_id"}:
        return "project_context", "reference_template_library", 1.0
    if fact_kind in {"candidate_product_spec", "technical_parameter_candidate"}:
        return "product_parameter_table", "product_library", 0.85
    if fact_kind == "testing_equipment_candidate" or any(
        token in blob for token in ("校准证书", "检定报告", "试验检测设备", "电子天平", "万能试验机", "维卡", "锤击试验")
    ):
        return "testing_capacity", "product_library", 0.9
    if fact_kind == "report_identifier" or any(token in blob for token in ("检验报告", "检测报告", "型式试验")):
        return "inspection_report", "product_library", 0.95
    if any(token in blob for token in ("审计报告", "财务状况", "财务报告", "纳税")):
        return "finance", "qualification_library", 0.9
    if any(token in blob for token in ("认证证书", "管理体系认证", "资质证书")):
        return "certification", "qualification_library", 0.9
    if any(token in blob for token in ("人员证书", "技术人员", "项目经理", "身份证", "社保", "参保证明")):
        return "personnel_certificate", "qualification_library", 0.9
    if any(token in blob for token in ("业绩", "合同", "中标通知", "资格预审通知")):
        return "project_performance", "qualification_library", 0.8
    if any(token in blob for token in ("授权委托", "授权书", "法定代表人")):
        return "authorization", "qualification_library", 0.9
    if any(token in blob for token in ("营业执照", "法人证书", "基本情况表")):
        return "business_license", "qualification_library", 0.85
    if any(token in blob for token in ("生产线", "生产装备", "制造工艺", "工序控制", "厂房", "仓库", "质量控制")):
        return "production_capacity", "product_library", 0.85
    if any(token in blob for token in ("绿色", "低碳", "碳足迹", "ESG", "环境影响", "废水", "废气", "废固", "绿电")):
        return "green_low_carbon", "product_library", 0.9
    if fact_kind == "generic_response":
        return "technical_response", "knowledge_library", 1.0
    if bid_volume == "technical":
        return "enterprise_evidence", "product_library", 0.45
    return "enterprise_evidence", "qualification_library", 0.45


def _sensitivity(original: dict[str, Any]) -> str:
    blob = " ".join(_text(original.get(key)) for key in ("title", "source_section", "notes"))
    if any(token in blob for token in ("身份证", "公章", "签名", "银行账户", "基本账户", "授权委托", "法定代表人")):
        return "restricted"
    if any(token in blob for token in ("社保", "参保证明", "财务", "审计", "股东", "出资", "银行")):
        return "sensitive"
    return "internal"


def _review_status(record_type: str, dedup_status: str) -> str:
    if record_type in {"chapter", "table"}:
        return "not_asset_reference"
    if dedup_status == "duplicate_exact":
        return "rejected_duplicate"
    if dedup_status == "fact_conflict":
        return "rejected_conflict"
    if dedup_status.startswith("possible_") or dedup_status == "same_evidence_new_rendition":
        return "needs_manual_review"
    return "needs_customer_confirmation"


def _quality_tier(sensitivity: str, review_status: str) -> str:
    if sensitivity in {"sensitive", "restricted"} or review_status == "rejected_conflict":
        return "restricted"
    return "review_only"


def _formal_title(
    evidence_label: str, record_type: str, bid_volume: str, page: Any, source_section: str
) -> str:
    volume_label = "技术标" if bid_volume == "technical" else "商务标"
    if record_type == "chapter":
        leaf = _leaf_sections(source_section)[-1]
        return f"泰昌{volume_label}历史目录参考：{leaf}"
    if record_type == "table":
        leaf = _leaf_sections(source_section)[-1]
        return f"泰昌{volume_label}历史表单参考：{leaf}"
    page_suffix = f"第{page}页" if _text(page) else ""
    return f"泰昌{evidence_label}历史候选{page_suffix}"


def _caption(evidence_type: str, evidence_label: str) -> tuple[str, str]:
    if evidence_type in {"production_capacity", "testing_capacity", "green_low_carbon", "product_image"}:
        return "formal_material_caption", f"资料：泰昌{evidence_label}"
    return "suppressed_document_page_caption", ""


def _visible_values(record: dict[str, Any]) -> list[str]:
    values = [_text(record.get(field)) for field in VISIBLE_FIELDS]
    for field in ("tags", "applicable_sections", "product_families"):
        values.extend(_text(item) for item in (record.get(field) or []))
    return values


def visible_field_violations(record: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for value in _visible_values(record):
        lowered = value.lower()
        for pattern in FORBIDDEN_VISIBLE_PATTERNS:
            if pattern.lower() in lowered:
                violations.append(pattern)
        if UUID_RE.search(value):
            violations.append("uuid")
        if HASH_RE.search(value):
            violations.append("hash")
    return sorted(set(violations))


def tag_dictionary() -> dict[str, Any]:
    return {
        "schema_version": "taichang_tag_dictionary_v1",
        "enterprise_scope": ENTERPRISE,
        "pilot_only": True,
        "source_domains": {
            "enterprise_fact": "泰昌企业事实",
            "tender_requirement": "招标要求",
            "reference_template": "历史参考资料",
            "mixed_historical_bid": "泰昌历史标书混合资料",
        },
        "target_libraries": TARGET_LIBRARY_LABELS,
        "evidence_types": EVIDENCE_LABELS,
        "product_families": {
            "CPVC": "CPVC电缆保护管",
            "MPP": "MPP电缆保护管",
            "N-HAP": "N-HAP电缆保护管",
            "UPVC": "UPVC电缆保护管",
            "cable_conduit_general": "电缆保护管通用",
            "unknown": "产品族待确认",
        },
        "applicable_volumes": {"technical": "技术标", "business": "商务标"},
        "quality_tiers": QUALITY_LABELS,
        "review_statuses": REVIEW_LABELS,
        "sensitivity_levels": SENSITIVITY_LABELS,
        "dedup_statuses": DEDUP_STATUS_LABELS,
        "origin_types": {
            "tender_mandated": "招标强制要求",
            "tender_conditional": "招标条件性要求",
            "tender_scoring_derived": "评分要素展开",
            "taichang_habitual_addition": "泰昌历史习惯补充",
            "reference_layout_only": "仅参考版式",
            "uncertain": "来源待确认",
        },
        "caption_policies": {
            "suppressed_document_page_caption": "证书、报告、合同等整页证据默认不显示题注",
            "formal_material_caption": "生产、检测、绿色低碳和产品实物资料使用正式中文题注",
        },
        "visible_field_policy": {
            "required": list(VISIBLE_FIELDS),
            "forbidden_patterns": list(FORBIDDEN_VISIBLE_PATTERNS) + ["UUID", "长哈希"],
            "rule": "内部枚举和解析路径仅保留在 metadata，页面和正式文件只展示中文字段",
        },
        "promotion_policy": {
            "default_quality_tier": "review_only",
            "requires_p0_06_approval": True,
            "new_is_not_approved": True,
            "possible_match_auto_merge_allowed": False,
            "formal_bid_ready_requires_original_evidence": True,
        },
    }


def _load_approved(path: Path | None) -> set[str]:
    if path is None:
        return set()
    payload = _json(path)
    values = payload if isinstance(payload, list) else payload.get("approved_candidate_ids", [])
    return {_text(value) for value in values if _text(value)}


def classify(
    dedup_payload: dict[str, Any],
    original_payloads: list[dict[str, Any]],
    *,
    approved_ids: set[str] | None = None,
) -> dict[str, Any]:
    approved_ids = approved_ids or set()
    originals = {
        _text(record.get("candidate_id")): record
        for payload in original_payloads
        for record in (payload.get("records") or [])
    }
    rows: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    ingestion_candidates: list[dict[str, Any]] = []
    for dedup in dedup_payload.get("records") or []:
        candidate_id = _text(dedup.get("candidate_id"))
        original = originals.get(candidate_id, {})
        bid_volume = _text(dedup.get("bid_volume") or original.get("bid_volume"))
        record_type = _text(dedup.get("record_type") or original.get("record_type"))
        dedup_status = _text(dedup.get("dedup_status"))
        evidence_type, target_library, confidence = _classify_evidence(original, bid_volume)
        evidence_label = EVIDENCE_LABELS[evidence_type]
        sensitivity = _sensitivity(original)
        review_status = _review_status(record_type, dedup_status)
        quality_tier = _quality_tier(sensitivity, review_status)
        source_section = _clean_section(original.get("source_section") or dedup.get("source_section"))
        blob = " ".join(
            _text(original.get(key))
            for key in ("title", "source_section", "applicable_product", "applicable_material")
        )
        products = _product_families(blob, evidence_type)
        source_document_name = "泰昌技术补充文件" if bid_volume == "technical" else "泰昌商务补充文件"
        title = _formal_title(evidence_label, record_type, bid_volume, dedup.get("source_page"), source_section)
        caption_policy, formal_caption = _caption(evidence_type, evidence_label)
        approved = candidate_id in approved_ids
        eligible_status = dedup_status == "new"
        eligible_record = record_type in {"media", "fact_candidate"} and _text(original.get("fact_kind")) != "generic_response"
        # P0-05 只能完成预分类。单独提供候选 ID 不等于完成质量提升；
        # 必须由 P0-06 将质量等级审核为 formal_bid_ready/knowledge_only 后才能进入入库清单。
        eligible_quality = quality_tier in {"formal_bid_ready", "knowledge_only"}
        product_ok = not (
            target_library == "product_library"
            and evidence_type in {"inspection_report", "product_parameter_table", "product_image"}
            and not products
        )
        ingestion_eligible = approved and eligible_status and eligible_record and eligible_quality and product_ok
        if not approved:
            block_reason = "尚未通过P0-06人工批准"
        elif not eligible_status:
            block_reason = "去重状态不允许新建正式资产"
        elif not eligible_record:
            block_reason = "结构参考或通用话术不属于正式资产"
        elif not eligible_quality:
            block_reason = "质量等级尚未通过P0-06审核提升"
        elif not product_ok:
            block_reason = "产品事实缺少明确产品族"
        else:
            block_reason = ""
        tags = ["泰昌", evidence_label, "历史标书候选"]
        if bid_volume:
            tags.append("技术标" if bid_volume == "technical" else "商务标")
        tags.extend(products)
        tags = list(dict.fromkeys(tags))
        sections = _leaf_sections(source_section)
        description = (
            f"来源于{source_document_name}，历史位置为“{sections[-1]}”。"
            "当前仅用于泰昌资料人工复核，未获准进入正式标书。"
        )
        row = {
            "candidate_id": candidate_id,
            "bid_volume": bid_volume,
            "record_type": record_type,
            "source_page": dedup.get("source_page", ""),
            "dedup_status": dedup_status,
            "dedup_status_label": DEDUP_STATUS_LABELS[dedup_status],
            "enterprise": ENTERPRISE,
            "doc_owner": ENTERPRISE,
            "source_domain": "mixed_historical_bid",
            "fact_source_allowed_for_enterprise": False,
            "tenant_visibility": "taichang_only",
            "access_scope": "taichang_tenant_internal",
            "target_library": target_library,
            "target_library_label": TARGET_LIBRARY_LABELS[target_library],
            "evidence_type": evidence_type,
            "evidence_type_label": evidence_label,
            "product_families": products,
            "material_category": "电缆保护管" if products else "泰昌企业资料",
            "applicable_volumes": ["技术标" if bid_volume == "technical" else "商务标"],
            "applicable_sections": sections,
            "origin_type": _text(original.get("origin_type")) or "uncertain",
            "validity_status": _text(original.get("validity_status")) or "unknown",
            "sensitivity": sensitivity,
            "sensitivity_label": SENSITIVITY_LABELS[sensitivity],
            "quality_tier": quality_tier,
            "quality_tier_label": QUALITY_LABELS[quality_tier],
            "review_status": review_status,
            "review_status_label": REVIEW_LABELS[review_status],
            "title": title,
            "source_display_name": source_document_name,
            "source_document_name": source_document_name,
            "category_label": evidence_label,
            "description": description,
            "tags": tags,
            "caption_policy": caption_policy,
            "formal_caption": formal_caption,
            "evidence_bundle_id": _text(dedup.get("evidence_bundle_id")),
            "manual_review_required": review_status in {"needs_manual_review", "needs_customer_confirmation"},
            "approved_candidate": approved,
            "ingestion_eligible": ingestion_eligible,
            "ingestion_action": "create_new_asset" if ingestion_eligible else "blocked",
            "ingestion_block_reason": block_reason,
            "classification_confidence": confidence,
            "source_file": _text(original.get("source_file") or dedup.get("source_file")),
            "source_section": source_section,
            "content_sha256": _text(dedup.get("content_sha256")),
            "media_sha256": _text(dedup.get("media_sha256")),
            "visible_field_violations": [],
        }
        row["visible_field_violations"] = visible_field_violations(row)
        rows.append(row)
        if (
            record_type in {"media", "fact_candidate"}
            and dedup_status not in {"duplicate_exact", "fact_conflict"}
            and _text(original.get("fact_kind")) != "generic_response"
        ):
            review_queue.append(row)
        if ingestion_eligible:
            ingestion_candidates.append(row)

    counts = Counter(_text(row.get("evidence_type")) for row in rows)
    quality_counts = Counter(_text(row.get("quality_tier")) for row in rows)
    review_counts = Counter(_text(row.get("review_status")) for row in rows)
    input_count = len(dedup_payload.get("records") or [])
    gate_checks = {
        "all_candidates_classified": len(rows) == input_count and all(row.get("evidence_type") for row in rows),
        "all_required_metadata_present": all(
            all(row.get(field) not in (None, "") for field in (
                "enterprise",
                "source_domain",
                "target_library",
                "evidence_type",
                "quality_tier",
                "review_status",
                "dedup_status",
                "dedup_status_label",
            )) for row in rows
        ),
        "all_visible_fields_clean": all(not row["visible_field_violations"] for row in rows),
        "duplicates_excluded_from_review_queue": all(
            row["dedup_status"] != "duplicate_exact" for row in review_queue
        ),
        "conflicts_excluded_from_review_queue": all(row["dedup_status"] != "fact_conflict" for row in review_queue),
        "ingestion_requires_explicit_approval": all(row["approved_candidate"] for row in ingestion_candidates),
        "no_unapproved_ingestion_candidate": all(row["approved_candidate"] for row in ingestion_candidates),
        "product_fact_requires_product_family": all(
            bool(row["product_families"])
            for row in ingestion_candidates
            if row["target_library"] == "product_library"
            and row["evidence_type"] in {"inspection_report", "product_parameter_table", "product_image"}
        ),
    }
    return {
        "metadata": {
            "schema_version": "taichang_asset_classification_v1",
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "enterprise": ENTERPRISE,
            "pilot_only": True,
            "read_only": True,
            "database_written": False,
            "rag_updated": False,
            "docx_selection_updated": False,
            "candidate_count": len(rows),
            "review_queue_count": len(review_queue),
            "approved_candidate_id_count": len(approved_ids),
            "ingestion_candidate_count": len(ingestion_candidates),
            "evidence_type_counts": dict(sorted(counts.items())),
            "quality_tier_counts": dict(sorted(quality_counts.items())),
            "review_status_counts": dict(sorted(review_counts.items())),
            "gate_checks": gate_checks,
        },
        "records": rows,
        "review_queue": review_queue,
        "ingestion_candidates": ingestion_candidates,
    }


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for record in records:
            row = dict(record)
            for field in ("product_families", "applicable_volumes", "applicable_sections", "tags"):
                row[field] = json.dumps(row.get(field) or [], ensure_ascii=False)
            writer.writerow(row)


def _artifact_payload(base: dict[str, Any], records: list[dict[str, Any]], artifact_role: str) -> dict[str, Any]:
    metadata = dict(base["metadata"])
    metadata["artifact_role"] = artifact_role
    metadata["record_count"] = len(records)
    return {"metadata": metadata, "records": records}


def _write_report(path: Path, result: dict[str, Any]) -> None:
    metadata = result["metadata"]
    lines = [
        "# 泰昌专版 V1 标签、分类与质量分级报告",
        "",
        f"> 生成时间：{metadata['generated_at']}",
        "> 范围：河北泰昌电力器材科技有限公司历史标书候选",
        "",
        "## 执行结论",
        "",
        f"- 已分类候选：{metadata['candidate_count']} 条。",
        f"- P0-06 人工审核队列：{metadata['review_queue_count']} 条。",
        f"- 已批准候选 ID：{metadata['approved_candidate_id_count']} 条。",
        f"- 正式增量入库候选：{metadata['ingestion_candidate_count']} 条。",
        "- 本轮未写数据库、未改变 RAG、未改变 DOCX 选图规则。",
        "",
        "## 质量等级",
        "",
        "| 质量等级 | 数量 | 处理 |",
        "| --- | ---: | --- |",
    ]
    for key, count in metadata["quality_tier_counts"].items():
        lines.append(f"| `{key}` | {count} | {QUALITY_LABELS[key]} |")
    lines.extend(["", "## 审核状态", "", "| 审核状态 | 数量 |", "| --- | ---: |"])
    for key, count in metadata["review_status_counts"].items():
        lines.append(f"| `{key}` | {count} |")
    lines.extend(
        [
            "",
            "## 关键安全结论",
            "",
            "- `new` 只代表未发现重复，不代表已批准或可入库。",
            "- 精确重复和事实冲突不进入 P0-06 审核队列。",
            "- 视觉/文本疑似重复必须人工确认，不得自动合并。",
            "- 历史 Word 图片、报告页和参数候选继续保持 `review_only`；敏感资料为 `restricted`。",
            "- 正式入库清单只接受 P0-06 明确批准且通过产品、质量、敏感性门禁的候选。",
            "",
            "## 门禁结果",
            "",
        ]
    )
    for name, passed in metadata["gate_checks"].items():
        lines.append(f"- [{'x' if passed else ' '}] `{name}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dedup", type=Path, default=DEFAULT_DEDUP)
    parser.add_argument("--technical", type=Path, default=DEFAULT_TECHNICAL)
    parser.add_argument("--business", type=Path, default=DEFAULT_BUSINESS)
    parser.add_argument("--approved-candidate-ids", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    inputs = (args.dedup, args.technical, args.business)
    result = classify(
        _json(args.dedup),
        [_json(args.technical), _json(args.business)],
        approved_ids=_load_approved(args.approved_candidate_ids),
    )
    result["metadata"]["input_sha256"] = {_display_path(path): _sha256_file(path) for path in inputs}
    dictionary = tag_dictionary()
    dictionary["generated_at"] = result["metadata"]["generated_at"]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / DEFAULT_DICTIONARY.name).write_text(
        json.dumps(dictionary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    classification = _artifact_payload(result, result["records"], "full_classification_matrix")
    review = _artifact_payload(result, result["review_queue"], "p0_06_manual_review_queue")
    ingestion = _artifact_payload(result, result["ingestion_candidates"], "approved_ingestion_candidates_only")
    (args.output_dir / DEFAULT_CLASSIFICATION_JSON.name).write_text(
        json.dumps(classification, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / DEFAULT_REVIEW_JSON.name).write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / DEFAULT_INGESTION_JSON.name).write_text(
        json.dumps(ingestion, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_csv(args.output_dir / DEFAULT_CLASSIFICATION_CSV.name, result["records"])
    _write_csv(args.output_dir / DEFAULT_REVIEW_CSV.name, result["review_queue"])
    _write_csv(args.output_dir / DEFAULT_INGESTION_CSV.name, result["ingestion_candidates"])
    _write_report(args.report, result)
    print(json.dumps(result["metadata"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

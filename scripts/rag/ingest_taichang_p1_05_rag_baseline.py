#!/usr/bin/env python3
"""构建并幂等入库泰昌 P1-05 结构化事实父子分块基线。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.supabase_client import get_bucket_name, get_supabase_client, upload_file_to_storage  # noqa: E402
from backend.rag.ingestion import _write_chunks_with_retry  # noqa: E402
from backend.rag.retrieval import invalidate_chunk_keyword_cache  # noqa: E402
from backend.rag.vector_store import get_embeddings, init_ali_client  # noqa: E402

ENTERPRISE = "河北泰昌电力器材科技有限公司"
BATCH_ID = "customer_taichang_p1_05_structured_rag_baseline_v1"
CATEGORY = "泰昌结构化企业事实"
OBJECT_PATH = f"power-grid-customer-corpus/{BATCH_ID}/taichang_structured_rag_baseline.json"
OUTPUT_DIR = PROJECT_ROOT / "docs/development/taichang-bid-v1-data/p1_05_rag_baseline"
BUSINESS_MANIFEST = PROJECT_ROOT / "docs/development/taichang-bid-v1-data/p1_03_business_ledgers/taichang_p1_03_manifest.json"
EVIDENCE_BUNDLES = PROJECT_ROOT / "docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundles.json"
PARAMETER_ROWS = PROJECT_ROOT / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/taichang_product_parameters/taichang_product_parameter_rows.json"
PERFORMANCE_ROWS = PROJECT_ROOT / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/taichang_project_performance_rows.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _families(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    for item in values:
        text = str(item or "").upper().replace("—", "-")
        if "CPVC" in text or "PVC-C" in text:
            normalized.append("CPVC电缆保护管")
        if "MPP" in text:
            normalized.append("MPP电缆保护管")
        if "UPVC" in text:
            normalized.append("UPVC电缆保护管")
        if "N-HAP" in text or "NHAP" in text:
            normalized.append("N-HAP电缆保护管")
    return list(dict.fromkeys(normalized)) or ["泰昌企业通用"]


def _materials(product_families: list[str]) -> list[str]:
    mapping = {
        "CPVC电缆保护管": "电缆保护管CPVC",
        "MPP电缆保护管": "电缆保护管MPP",
        "UPVC电缆保护管": "电缆保护管UPVC",
        "N-HAP电缆保护管": "电缆保护管N-HAP",
        "架空绝缘导线": "架空绝缘导线",
        "泰昌企业通用": "泰昌企业资料",
    }
    return [mapping[item] for item in product_families]


def _meta(
    *,
    layer: str,
    parent_index: int | None,
    evidence_type: str,
    product_families: list[str],
    source_file: str,
    source_display_name: str,
    source_page: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {
        "type": "structured_fact",
        "chunk_layer": layer,
        "parent_index": parent_index,
        "block_type": "structured_fact_group" if layer == "parent" else "structured_fact_row",
        "enterprise": "泰昌",
        "doc_owner": ENTERPRISE,
        "source_domain": "enterprise_fact",
        "fact_source_allowed_for_enterprise": True,
        "reference_only": False,
        "tenant_visibility": "taichang_only",
        "access_scope": "taichang_tenant_internal",
        "privacy_policy": "customer_confirmed_private_project_full_personnel_data_allowed",
        "doc_role": "enterprise_evidence",
        "authority_level": "enterprise_fact",
        "citation_policy": "enterprise_fact_citable_with_source_and_validity_check",
        "seed_corpus": "power_grid_customer_corpus",
        "ingestion_batch_id": BATCH_ID,
        "source_category": "structured_rag_baseline",
        "retrieval_strategy": "metadata_filter_then_child_recall_parent_backtrace_and_structured_lookup",
        "evidence_type": evidence_type,
        "product_family": product_families,
        "material_category": _materials(product_families),
        "source_file": source_file,
        "source_display_name": source_display_name,
        "source_page": source_page,
        "status": "indexed",
    }
    metadata.update(extra or {})
    return metadata


def _business_content(row: dict[str, Any]) -> str:
    kind = row.get("ledger_type")
    if kind == "personnel_roster":
        return (
            f"泰昌人员花名册：姓名={row.get('person_name') or '-'}；岗位={row.get('project_role') or '-'}；"
            f"学历={row.get('education') or '-'}；职称={row.get('professional_title') or '-'}；"
            f"社保记录={'有' if row.get('social_insurance_recorded') else '未记录'}；"
            f"劳动合同记录={'有' if row.get('labor_contract_recorded') else '未记录'}；入职年份={row.get('employment_start_year') or '-'}。"
        )
    if kind == "personnel_certificate":
        return (
            f"泰昌人员证书：姓名={row.get('person_name') or '-'}；岗位={row.get('project_role') or '-'}；"
            f"证书编号={row.get('certificate_no') or '-'}；作业类别={row.get('operation_category') or '-'}；"
            f"准操项目={row.get('permitted_operation') or '-'}；复审日期={row.get('review_date') or '-'}；"
            f"有效期至={row.get('valid_until') or '-'}；状态={row.get('validity_status') or '-'}。"
        )
    labels = {
        "equipment_calibration": ("泰昌设备校准", ["equipment_name", "model", "certificate_no", "calibration_date", "valid_until", "validity_status"]),
        "management_certificate": ("泰昌管理体系证书", ["certificate_name", "certificate_no", "valid_from", "valid_until", "validity_status"]),
        "audit_report": ("泰昌审计报告", ["audit_year", "report_no", "accounting_firm", "report_no_status"]),
        "personnel_summary": ("泰昌人员资料摘要", ["personnel_count", "certificate_record_count", "professional_title_filled_count"]),
        "inspection_report_registry": ("泰昌检验报告登记", ["product_family", "report_no", "original_report_available", "usage_status"]),
    }
    title, fields = labels.get(kind, ("泰昌企业结构化事实", sorted(row)))
    return title + "：" + "；".join(f"{field}={row.get(field) if row.get(field) not in (None, '') else '-'}" for field in fields) + "。"


def _parameter_content(row: dict[str, Any]) -> str:
    return (
        f"泰昌产品检验参数：产品={row.get('product_family')}；规格型号={row.get('specification_model')}；"
        f"公称内径={row.get('nominal_inner_diameter')}；参数={row.get('parameter_name')}；单位={row.get('unit')}；"
        f"标准要求={row.get('standard_requirement')}；检验结果={row.get('inspection_result')}；"
        f"单项结论={row.get('single_conclusion')}；报告编号={row.get('report_no')}；来源页码=第{row.get('source_page')}页。"
    )


def _bundle_content(bundle: dict[str, Any]) -> str:
    sources = [item.get("source_display_name") or Path(str(item.get("source_file") or "")).name for item in bundle.get("primary_sources") or []]
    return (
        f"泰昌证据包：证据包ID={bundle.get('evidence_bundle_id')}；名称={bundle.get('bundle_title')}；"
        f"类型={bundle.get('evidence_type_label')}；页数={bundle.get('page_count')}；页序完整={bundle.get('page_sequence_complete')}；"
        f"当前使用状态={bundle.get('usage_status')}；原始来源={'、'.join(filter(None, sources)) or '-'}；"
        f"告警={'；'.join(bundle.get('warnings') or []) or '无'}。"
    )


def _performance_content(row: dict[str, Any]) -> str:
    return (
        f"泰昌项目业绩：项目={row.get('project_name')}；招标编号={row.get('tender_no')}；包号={row.get('package_no')}；"
        f"产品={row.get('product_summary')}；数量={row.get('total_quantity')}{row.get('quantity_unit')}；"
        f"含税金额={row.get('amount_tax_included_yuan')}元；买方={row.get('buyer')}；卖方={row.get('seller')}；"
        f"中标日期={row.get('award_date') or '-'}；合同签署日期={row.get('contract_sign_date') or '原件为空，未推断'}。"
    )


def build_chunks() -> list[dict[str, Any]]:
    business = _load(BUSINESS_MANIFEST)
    bundles = _load(EVIDENCE_BUNDLES).get("bundles") or []
    parameters = _load(PARAMETER_ROWS)
    performances = _load(PERFORMANCE_ROWS)
    chunks: list[dict[str, Any]] = []

    def add_group(title: str, evidence_type: str, families: list[str], source_file: str, children: list[tuple[str, dict[str, Any]]]) -> None:
        parent_index = len(chunks)
        parent_content = f"{title}，共{len(children)}条。写作时由子块召回并回溯本组，精确值仍优先读取对应结构化行。"
        chunks.append({
            "chunk_index": parent_index,
            "content": parent_content,
            "source_section": title,
            "metadata": _meta(layer="parent", parent_index=None, evidence_type=evidence_type, product_families=families, source_file=source_file, source_display_name=title),
            "embedding": None,
        })
        for content, child_extra in children:
            index = len(chunks)
            source_display_name = str(child_extra.pop("source_display_name", title))
            source_page = child_extra.pop("source_page", None)
            child_source_file = str(child_extra.pop("source_file", source_file))
            child_families = child_extra.pop("product_families", families)
            child_evidence_type = str(child_extra.pop("evidence_type", evidence_type))
            chunks.append({
                "chunk_index": index,
                "content": content,
                "source_section": title,
                "metadata": _meta(layer="child", parent_index=parent_index, evidence_type=child_evidence_type, product_families=child_families, source_file=child_source_file, source_display_name=source_display_name, source_page=source_page, extra=child_extra),
                "embedding": "__PENDING__",
            })

    business_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in business.get("rows") or []:
        business_groups[str(row.get("ledger_type") or "enterprise_fact")].append(row)
    evidence_map = {
        "equipment_calibration": "testing_capacity",
        "management_certificate": "certification",
        "audit_report": "finance",
        "personnel_roster": "personnel_roster",
        "personnel_summary": "personnel_roster",
        "personnel_certificate": "personnel_certificate",
        "inspection_report_registry": "inspection_report",
    }
    for ledger_type, rows in sorted(business_groups.items()):
        children = []
        group_families = list(dict.fromkeys(family for row in rows for family in _families(row.get("product_family"))))
        if "泰昌企业通用" in group_families and len(group_families) > 1:
            group_families.remove("泰昌企业通用")
        for row in rows:
            children.append((_business_content(row), {
                "source_file": row.get("source_file") or str(BUSINESS_MANIFEST.relative_to(PROJECT_ROOT)),
                "source_display_name": row.get("source_display_name") or "泰昌业务台账",
                "source_page": row.get("source_page"),
                "product_families": _families(row.get("product_family")),
                "business_key": row.get("business_key"),
                "quality_tier": row.get("quality_tier"),
                "validity_status": row.get("validity_status"),
            }))
        add_group(f"泰昌{ledger_type}结构化台账", evidence_map.get(ledger_type, "enterprise_evidence"), group_families, str(BUSINESS_MANIFEST.relative_to(PROJECT_ROOT)), children)

    by_report: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in parameters:
        by_report[str(row.get("report_no"))].append(row)
    for report_no, rows in sorted(by_report.items()):
        families = _families(rows[0].get("product_family"))
        children = [(_parameter_content(row), {
            "source_file": row.get("source_file") or str(PARAMETER_ROWS.relative_to(PROJECT_ROOT)),
            "source_display_name": Path(str(row.get("source_file") or "泰昌产品检验报告")).stem,
            "source_page": row.get("source_page"),
            "report_no": report_no,
            "specification_model": row.get("specification_model"),
            "parameter_name": row.get("parameter_name"),
            "structured_row_key": f"{report_no}:{row.get('row_number')}:{row.get('parameter_name')}",
        }) for row in rows]
        add_group(f"泰昌{rows[0].get('product_family')}检验报告{report_no}", "inspection_report", families, str(PARAMETER_ROWS.relative_to(PROJECT_ROOT)), children)

    for bundle in bundles:
        families = _families(bundle.get("product_families"))
        add_group(str(bundle.get("bundle_title") or "泰昌证据包"), str(bundle.get("evidence_type") or "enterprise_evidence"), families, str(EVIDENCE_BUNDLES.relative_to(PROJECT_ROOT)), [(
            _bundle_content(bundle), {
                "source_display_name": bundle.get("bundle_title") or "泰昌证据包",
                "evidence_bundle_id": bundle.get("evidence_bundle_id"),
                "business_key": bundle.get("business_key"),
                "usage_status": bundle.get("usage_status"),
                "allowed_for_bid": bundle.get("allowed_for_bid"),
            },
        )])

    performance_children = [(_performance_content(row), {
        "source_file": row.get("source_file") or str(PERFORMANCE_ROWS.relative_to(PROJECT_ROOT)),
        "source_display_name": Path(str(row.get("source_file") or "泰昌项目业绩")).stem,
        "source_page": row.get("source_pages"),
        "product_families": _families(row.get("product_families")),
        "performance_id": row.get("performance_id"),
        "evidence_type": "project_performance",
    }) for row in performances]
    add_group("泰昌项目业绩结构化记录", "project_performance", ["CPVC电缆保护管", "MPP电缆保护管"], str(PERFORMANCE_ROWS.relative_to(PROJECT_ROOT)), performance_children)

    add_group("泰昌跨产品范围守卫", "scope_guard", ["架空绝缘导线"], "docs/development/taichang-bid-v1-priority-task-list-20260711.md", [(
        "当前结构化企业事实基线未发现与架空绝缘导线匹配的泰昌产品参数或检验报告，不得跨产品引用其他产品事实；应提示补充对应原始证据。",
        {"source_display_name": "泰昌产品事实范围说明", "is_fact_gap": True, "fact_gap_action": "request_matching_original_evidence"},
    )])
    for row in chunks:
        row["metadata"]["content_sha256"] = hashlib.sha256(row["content"].encode("utf-8")).hexdigest()
    return chunks


def _upsert_document(dataset_sha256: str) -> tuple[str, int]:
    client = get_supabase_client()
    existing = (client.table("knowledge_documents").select("id").eq("bucket", get_bucket_name("knowledge")).eq("object_path", OBJECT_PATH).limit(1).execute().data or [])
    metadata = {
        "enterprise": "泰昌", "doc_owner": ENTERPRISE, "source_domain": "enterprise_fact",
        "fact_source_allowed_for_enterprise": True, "reference_only": False, "doc_role": "enterprise_evidence",
        "seed_corpus": "power_grid_customer_corpus", "ingestion_batch_id": BATCH_ID,
        "chunker": "parent_child_structured_v1", "dataset_sha256": dataset_sha256,
        "source_display_name": "泰昌结构化企业事实基线", "category_label": CATEGORY,
    }
    payload = {"title": "泰昌结构化企业事实基线", "category": CATEGORY, "bucket": get_bucket_name("knowledge"), "object_path": OBJECT_PATH, "source_type": "structured_json", "status": "processing", "metadata": metadata}
    if existing:
        document_id = str(existing[0]["id"])
        previous = client.table("document_chunks").select("id", count="exact").eq("document_id", document_id).limit(1).execute()
        client.table("knowledge_documents").update(payload).eq("id", document_id).execute()
        return document_id, int(previous.count or 0)
    response = client.table("knowledge_documents").insert(payload).execute()
    return str(response.data[0]["id"]), 0


def run(*, execute: bool, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    chunks = build_chunks()
    parents = [row for row in chunks if row["metadata"]["chunk_layer"] == "parent"]
    children = [row for row in chunks if row["metadata"]["chunk_layer"] == "child"]
    dataset = [{key: value for key, value in row.items() if key != "embedding"} for row in chunks]
    dataset_sha256 = _sha256(dataset)
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = output_dir / "taichang_structured_rag_chunks.json"
    dataset_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    document_id = None
    previous_chunks = 0
    inserted_chunks = 0
    embedding_count = 0
    if execute:
        document_id, previous_chunks = _upsert_document(dataset_sha256)
        pending = [row for row in chunks if row["embedding"] == "__PENDING__"]
        embeddings = get_embeddings(init_ali_client(), [row["content"] for row in pending], batch_size=10, usage_context={"stage": "taichang_p1_05_structured_rag_baseline", "metadata": {"ingestion_batch_id": BATCH_ID}})
        if len(embeddings) != len(pending):
            raise RuntimeError(f"embedding 数量不一致：expected={len(pending)} actual={len(embeddings)}")
        for row, embedding in zip(pending, embeddings):
            row["embedding"] = embedding
        embedding_count = len(embeddings)
        for row in chunks:
            row["document_id"] = document_id
            if row["embedding"] == "__PENDING__":
                row["embedding"] = None
        client = get_supabase_client()
        client.table("document_chunks").delete().eq("document_id", document_id).execute()
        invalidate_chunk_keyword_cache("taichang_p1_05_refresh")
        inserted_chunks = _write_chunks_with_retry(client, chunks)
        client.table("knowledge_documents").update({"status": "indexed"}).eq("id", document_id).execute()
        invalidate_chunk_keyword_cache("taichang_p1_05_indexed")
        upload_file_to_storage(get_bucket_name("knowledge"), OBJECT_PATH, dataset_path, "application/json")
    summary = {
        "schema_version": "taichang-p1-05-structured-rag-baseline-v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "indexed" if execute else "dry_run",
        "batch_id": BATCH_ID,
        "document_id": document_id,
        "dataset_sha256": dataset_sha256,
        "parent_chunks": len(parents),
        "child_chunks": len(children),
        "total_chunks": len(chunks),
        "embedding_count": embedding_count,
        "previous_chunks": previous_chunks,
        "inserted_chunks": inserted_chunks,
        "child_metadata_complete": all(all(row["metadata"].get(key) for key in ("enterprise", "source_domain", "product_family", "material_category", "evidence_type")) for row in children),
        "by_evidence_type": dict(sorted(Counter(row["metadata"]["evidence_type"] for row in children).items())),
        "database_writes": inserted_chunks if execute else 0,
        "asset_promotions": 0,
        "docx_selection_changes": 0,
    }
    (output_dir / "taichang_p1_05_ingestion_manifest.json").write_text(json.dumps({"summary": summary, "sources": [str(path.relative_to(PROJECT_ROOT)) for path in (BUSINESS_MANIFEST, EVIDENCE_BUNDLES, PARAMETER_ROWS, PERFORMANCE_ROWS)]}, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        "# 泰昌 P1-05 结构化事实 RAG 基线入库报告", "",
        f"> 状态：`{summary['status']}`", f"> 批次：`{BATCH_ID}`", "",
        "## 结果", "",
        f"- 父块：{summary['parent_chunks']}；子块：{summary['child_chunks']}；总块：{summary['total_chunks']}。",
        f"- 子块 metadata 完整：{summary['child_metadata_complete']}；embedding：{summary['embedding_count']}。",
        f"- 数据库文档：`{document_id or 'dry-run 未写入'}`；替换前 {previous_chunks} 块，本次写入 {inserted_chunks} 块。",
        "- 结构化参数、项目业绩、业务台账仍保留直查入口；向量子块只负责语义召回，写作场景回溯父块。",
        "- 已加入架空绝缘导线范围守卫，不得跨产品引用电缆保护管事实。",
        "- 资产等级提升 0，DOCX 选图变更 0。", "",
    ]
    (output_dir / "taichang_p1_05_ingestion_report.md").write_text("\n".join(report), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="实际幂等刷新数据库；默认只生成 dry-run 产物")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    summary = run(execute=args.execute, output_dir=args.output_dir.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["child_metadata_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""生成泰昌 V1 当前数字资产基线快照。

脚本只读访问 PostgreSQL，并读取本地 staging/原始资料；不会写数据库、不会入库、
不会修改任何已有资产。输出统一 JSON/CSV，供后续历史标书候选去重和章节证据映射使用。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from psycopg.rows import dict_row


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.postgres_compat import _database_url  # noqa: E402
from backend.db.postgres_pool import pooled_connection  # noqa: E402


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs" / "development" / "taichang-bid-v1-data"
RAW_ENTERPRISE_ROOT = PROJECT_ROOT / "rag_seed" / "power_grid_resources" / "05_enterprise_documents"
PRODUCT_PARAMETER_PATH = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/"
    "staging/taichang_product_parameters/taichang_product_parameter_rows.json"
)
PROJECT_PERFORMANCE_PATH = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/"
    "staging/taichang_project_performance/taichang_project_performance_rows.json"
)
STAGING_ROOT = PROJECT_ROOT / "parsed_outputs" / "power_grid_customer_corpus"

CSV_FIELDS = [
    "record_type",
    "record_id",
    "stable_business_key",
    "asset_id",
    "document_id",
    "source_file",
    "source_sha256",
    "content_sha256",
    "page_no",
    "page_index",
    "title",
    "source_display_name",
    "category_label",
    "source_domain",
    "doc_owner",
    "enterprise",
    "evidence_type",
    "target_library",
    "product_family",
    "material_category",
    "model_specs",
    "report_or_certificate_no",
    "quality_tier",
    "allowed_for_bid",
    "review_status",
    "created_at",
    "updated_at",
    "ingestion_batch_id",
    "doc_version",
    "status",
    "source_system",
    "metadata_completeness",
    "notes",
]

SENSITIVE_PATH_TOKENS = ("身份证", "公章", "签名", "手章", "社保证明", "劳动合同")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return str(value)


def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first(*values: Any) -> Any:
    return next((value for value in values if value not in (None, "", [], {})), None)


def _iso(value: Any) -> str:
    if value is None:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_file(path: Path, cache: dict[str, str]) -> str:
    key = str(path.resolve())
    if key in cache:
        return cache[key]
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    cache[key] = digest.hexdigest()
    return cache[key]


def _resolve_source_file(source_file: Any) -> Path | None:
    value = _text(source_file).strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.is_file() else None


def _source_sha256(source_file: Any, metadata: dict[str, Any], cache: dict[str, str]) -> str:
    existing = _first(metadata.get("source_sha256"), metadata.get("sha256"), metadata.get("file_sha256"))
    if existing:
        return str(existing)
    path = _resolve_source_file(source_file)
    return _sha256_file(path, cache) if path else ""


def _quality_tier(metadata: dict[str, Any], specs: dict[str, Any], *, record_type: str) -> str:
    explicit = _first(metadata.get("quality_tier"), specs.get("quality_tier"))
    if explicit:
        return str(explicit)
    if record_type in {"staging_asset_candidate", "raw_enterprise_file"}:
        return "review_only"
    if record_type in {"product_parameter", "project_performance"}:
        return "knowledge_only"
    return "unclassified"


def _allowed_for_bid(metadata: dict[str, Any], specs: dict[str, Any], *, default: bool = False) -> bool:
    value = _first(metadata.get("allowed_for_bid"), specs.get("allowed_for_bid"))
    return default if value is None else bool(value)


def _metadata_completeness(record: dict[str, Any]) -> str:
    required = [
        "source_file",
        "source_domain",
        "doc_owner",
        "enterprise",
        "source_display_name",
        "evidence_type",
        "target_library",
        "quality_tier",
        "review_status",
    ]
    missing_markers = (None, "", "unclassified", "not_recorded")
    missing = [key for key in required if record.get(key) in missing_markers]
    return "complete" if not missing else f"missing:{','.join(missing)}"


def _record(**values: Any) -> dict[str, Any]:
    record = {field: values.get(field, "") for field in CSV_FIELDS}
    record["metadata_completeness"] = _metadata_completeness(record)
    return record


def _fetch_database_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    where = """
        coalesce(metadata->>'enterprise', '') in ('泰昌', '河北泰昌电力器材科技有限公司')
        or coalesce(metadata->>'doc_owner', '') in ('泰昌', '河北泰昌电力器材科技有限公司')
        or title ilike %s
        or metadata::text ilike %s
    """
    params = ["%泰昌%", "%泰昌%"]
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        documents = [
            dict(row)
            for row in conn.execute(
                f"""
                select id, title, category, bucket, object_path, source_type, status,
                       metadata, created_at
                from public.knowledge_documents
                where {where}
                order by created_at nulls last, id
                """,
                params,
            ).fetchall()
        ]
        document_ids = [str(row["id"]) for row in documents]
        assets = [
            dict(row)
            for row in conn.execute(
                f"""
                select id, title, description, category, asset_type, file_name, file_ext,
                       mime_type, file_size, local_path, storage_bucket, storage_path,
                       source_type, knowledge_document_id, status, metadata, specs,
                       created_at, updated_at
                from public.knowledge_assets
                where {where}
                order by created_at nulls last, id
                """,
                params,
            ).fetchall()
        ]
        chunks = [
            dict(row)
            for row in conn.execute(
                """
                select id, document_id, project_id, chunk_index, content, source_page,
                       source_section, metadata, created_at
                from public.document_chunks
                where metadata::text ilike %s
                   or document_id = any(%s::uuid[])
                order by document_id, chunk_index, id
                """,
                ["%泰昌%", document_ids],
            ).fetchall()
        ]
    return documents, assets, chunks


def _document_records(rows: Iterable[dict[str, Any]], hash_cache: dict[str, str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        metadata = _json_dict(row.get("metadata"))
        record_id = str(row["id"])
        source_file = _first(metadata.get("source_file"), row.get("object_path"))
        source_sha = _source_sha256(source_file, metadata, hash_cache)
        records.append(
            _record(
                record_type="knowledge_document",
                record_id=record_id,
                stable_business_key=_first(metadata.get("doc_identity_key"), source_sha, f"document:{record_id}"),
                document_id=record_id,
                source_file=source_file,
                source_sha256=source_sha,
                content_sha256=metadata.get("content_sha256"),
                title=row.get("title"),
                source_display_name=_first(metadata.get("source_display_name"), row.get("title")),
                category_label=_first(metadata.get("category_label"), row.get("category")),
                source_domain=metadata.get("source_domain"),
                doc_owner=metadata.get("doc_owner"),
                enterprise=metadata.get("enterprise"),
                evidence_type=metadata.get("evidence_type"),
                target_library=metadata.get("target_library"),
                product_family=_first(metadata.get("product_family"), metadata.get("applicable_product")),
                material_category=metadata.get("material_category"),
                model_specs=_first(metadata.get("model_specs"), metadata.get("specification_model")),
                report_or_certificate_no=_first(
                    metadata.get("report_no"), metadata.get("certificate_no"), metadata.get("contract_no")
                ),
                quality_tier=_quality_tier(metadata, {}, record_type="knowledge_document"),
                allowed_for_bid=metadata.get("fact_source_allowed_for_enterprise") is True,
                review_status=_first(metadata.get("review_status"), "not_recorded"),
                created_at=_iso(row.get("created_at")),
                ingestion_batch_id=metadata.get("ingestion_batch_id"),
                doc_version=metadata.get("doc_version"),
                status=row.get("status"),
                source_system="postgresql.knowledge_documents",
            )
        )
    return records


def _asset_records(rows: Iterable[dict[str, Any]], hash_cache: dict[str, str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        metadata = _json_dict(row.get("metadata"))
        specs = _json_dict(row.get("specs"))
        record_id = str(row["id"])
        source_file = _first(metadata.get("source_file"), row.get("local_path"), row.get("file_name"))
        source_sha = _source_sha256(source_file, metadata, hash_cache)
        page_identity = _first(metadata.get("page_index"), specs.get("page_index"), metadata.get("page_no"), specs.get("page_no"), "na")
        storage_identity = "".join(
            [
                _text(row.get("storage_bucket")),
                "/",
                _text(row.get("storage_path")),
            ]
        ).strip("/")
        stable_key = _first(
            metadata.get("business_key"),
            f"asset_storage:{storage_identity}" if storage_identity else None,
            f"asset_source:{source_sha}:page:{page_identity}" if source_sha else None,
            f"asset:{record_id}",
        )
        records.append(
            _record(
                record_type="knowledge_asset",
                record_id=record_id,
                stable_business_key=stable_key,
                asset_id=record_id,
                document_id=row.get("knowledge_document_id"),
                source_file=source_file,
                source_sha256=source_sha,
                content_sha256=_first(metadata.get("content_sha256"), specs.get("content_sha256")),
                page_no=_first(metadata.get("page_no"), specs.get("page_no")),
                page_index=_first(metadata.get("page_index"), specs.get("page_index")),
                title=row.get("title"),
                source_display_name=_first(metadata.get("source_display_name"), specs.get("display_name"), row.get("title")),
                category_label=_first(metadata.get("category_label"), row.get("category")),
                source_domain=metadata.get("source_domain"),
                doc_owner=metadata.get("doc_owner"),
                enterprise=metadata.get("enterprise"),
                evidence_type=_first(metadata.get("evidence_type"), specs.get("evidence_type")),
                target_library=_first(metadata.get("target_library"), specs.get("target_library")),
                product_family=_first(metadata.get("product_family"), specs.get("product_family")),
                material_category=_first(metadata.get("material_category"), specs.get("material_category")),
                model_specs=_first(metadata.get("model_specs"), specs.get("model_specs")),
                report_or_certificate_no=_first(
                    metadata.get("report_no"), metadata.get("certificate_no"), metadata.get("contract_no")
                ),
                quality_tier=_quality_tier(metadata, specs, record_type="knowledge_asset"),
                allowed_for_bid=_allowed_for_bid(metadata, specs, default=False),
                review_status=_first(metadata.get("review_status"), specs.get("review_status"), "not_recorded"),
                created_at=_iso(row.get("created_at")),
                updated_at=_iso(row.get("updated_at")),
                ingestion_batch_id=_first(metadata.get("ingestion_batch_id"), metadata.get("source_batch_id")),
                doc_version=metadata.get("doc_version"),
                status=row.get("status"),
                source_system="postgresql.knowledge_assets",
            )
        )
    return records


def _chunk_records(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        metadata = _json_dict(row.get("metadata"))
        record_id = str(row["id"])
        content_sha = _first(metadata.get("content_sha256"), _sha256_text(_text(row.get("content"))))
        source_file = metadata.get("source_file")
        records.append(
            _record(
                record_type="document_chunk",
                record_id=record_id,
                stable_business_key=f"chunk:{row.get('document_id')}:{row.get('chunk_index')}:{content_sha}",
                document_id=row.get("document_id"),
                source_file=source_file,
                source_sha256=metadata.get("source_sha256"),
                content_sha256=content_sha,
                page_no=_first(row.get("source_page"), metadata.get("page_no")),
                title=_first(row.get("source_section"), metadata.get("source_section"), metadata.get("source_display_name")),
                source_display_name=metadata.get("source_display_name"),
                category_label=metadata.get("category_label"),
                source_domain=metadata.get("source_domain"),
                doc_owner=metadata.get("doc_owner"),
                enterprise=metadata.get("enterprise"),
                evidence_type=metadata.get("evidence_type"),
                target_library=metadata.get("target_library"),
                product_family=metadata.get("product_family"),
                material_category=metadata.get("material_category"),
                model_specs=_first(metadata.get("model_specs"), metadata.get("specification_model")),
                report_or_certificate_no=_first(metadata.get("report_no"), metadata.get("certificate_no")),
                quality_tier=_quality_tier(metadata, {}, record_type="document_chunk"),
                allowed_for_bid=metadata.get("fact_source_allowed_for_enterprise") is True
                and metadata.get("exclude_from_rag") is not True,
                review_status=_first(metadata.get("review_status"), "not_recorded"),
                created_at=_iso(row.get("created_at")),
                ingestion_batch_id=metadata.get("ingestion_batch_id"),
                doc_version=metadata.get("doc_version"),
                status=_first(metadata.get("status"), "indexed"),
                source_system="postgresql.document_chunks",
                notes=f"chunk_layer={_text(metadata.get('chunk_layer'))};chunk_index={row.get('chunk_index')}",
            )
        )
    return records


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"expected JSON array: {path}")
    return [item for item in data if isinstance(item, dict)]


def _product_parameter_records(path: Path, hash_cache: dict[str, str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(_load_json_list(path), start=1):
        source_file = row.get("source_file")
        source_sha = _source_sha256(source_file, row, hash_cache)
        business_key = ":".join(
            [
                "product_parameter",
                _text(row.get("report_no")),
                _text(row.get("product_family")),
                _text(row.get("specification_model")),
                _text(row.get("parameter_name")),
                _text(row.get("row_number") or index),
            ]
        )
        records.append(
            _record(
                record_type="product_parameter",
                record_id=_sha256_text(business_key)[:24],
                stable_business_key=business_key,
                source_file=source_file,
                source_sha256=source_sha,
                content_sha256=_sha256_text(json.dumps(row, ensure_ascii=False, sort_keys=True)),
                title=row.get("parameter_name"),
                source_display_name=f"{row.get('product_family')}检验报告结构化参数",
                category_label="产品技术参数",
                source_domain=row.get("source_domain"),
                doc_owner=row.get("doc_owner"),
                enterprise=row.get("enterprise"),
                evidence_type=row.get("evidence_type"),
                target_library=row.get("target_library"),
                product_family=row.get("product_family"),
                model_specs=row.get("specification_model"),
                report_or_certificate_no=row.get("report_no"),
                quality_tier="knowledge_only",
                allowed_for_bid=False,
                review_status="structured_verified",
                ingestion_batch_id=row.get("ingestion_batch_id"),
                status="staging_structured",
                source_system=str(path.relative_to(PROJECT_ROOT)),
                notes=f"检验结果={_text(row.get('inspection_result'))};单项结论={_text(row.get('single_conclusion'))}",
            )
        )
    return records


def _project_performance_records(path: Path, hash_cache: dict[str, str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(_load_json_list(path), start=1):
        source_file = row.get("source_file")
        source_sha = _source_sha256(source_file, row, hash_cache)
        business_key = ":".join(
            [
                "project_performance",
                _text(row.get("performance_id")),
                _text(row.get("evidence_type")),
                _text(index),
            ]
        )
        records.append(
            _record(
                record_type="project_performance",
                record_id=_sha256_text(business_key)[:24],
                stable_business_key=business_key,
                source_file=source_file,
                source_sha256=source_sha,
                content_sha256=_sha256_text(json.dumps(row, ensure_ascii=False, sort_keys=True)),
                title=row.get("project_name"),
                source_display_name=row.get("evidence_type_label"),
                category_label="项目业绩",
                source_domain=row.get("source_domain"),
                doc_owner=row.get("doc_owner"),
                enterprise=row.get("enterprise"),
                evidence_type=row.get("evidence_type"),
                target_library=row.get("target_library"),
                product_family=row.get("product_families"),
                report_or_certificate_no=_first(row.get("contract_no_buyer"), row.get("tender_no")),
                quality_tier="knowledge_only",
                allowed_for_bid=False,
                review_status="structured_verified",
                status="staging_structured",
                source_system=str(path.relative_to(PROJECT_ROOT)),
                notes=(
                    f"分标={_text(row.get('section_name'))};包号={_text(row.get('package_no'))};"
                    f"数量={_text(row.get('total_quantity'))};金额={_text(row.get('amount_tax_included_yuan'))}"
                ),
            )
        )
    return records


def _raw_file_records(root: Path, hash_cache: dict[str, str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != ".DS_Store"):
        relative = str(path.relative_to(PROJECT_ROOT))
        source_sha = _sha256_file(path, hash_cache)
        sensitive = any(token in relative for token in SENSITIVE_PATH_TOKENS)
        quality_tier = "restricted" if sensitive else "review_only"
        records.append(
            _record(
                record_type="raw_enterprise_file",
                record_id=source_sha[:24],
                stable_business_key=f"raw:{source_sha}",
                source_file=relative,
                source_sha256=source_sha,
                title=path.name,
                source_display_name=path.stem,
                category_label="客户原始资料",
                source_domain="enterprise_fact",
                doc_owner="河北泰昌电力器材科技有限公司",
                enterprise="泰昌",
                evidence_type="archive_source",
                target_library="archive_only",
                quality_tier=quality_tier,
                allowed_for_bid=False,
                review_status="raw_source_not_promoted",
                status="raw_archived",
                source_system="rag_seed",
                notes=f"file_ext={path.suffix.lower()};size={path.stat().st_size}",
            )
        )
    return records


def _staging_asset_records(root: Path, hash_cache: dict[str, str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("customer*taichang*/**/asset_staging_payloads.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for index, payload in enumerate(data.get("assets") or [], start=1):
            if not isinstance(payload, dict):
                continue
            metadata = _json_dict(payload.get("metadata"))
            specs = _json_dict(payload.get("specs"))
            source_file = _first(metadata.get("source_file"), payload.get("local_path"), payload.get("file_name"))
            source_sha = _source_sha256(source_file, metadata, hash_cache)
            page_identity = _first(
                metadata.get("page_index"), specs.get("page_index"), metadata.get("page_no"), specs.get("page_no"), "na"
            )
            content_sha = _sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
            key_seed = _first(payload.get("asset_id"), f"{source_sha}:page:{page_identity}:{content_sha}", f"{path}:{index}")
            records.append(
                _record(
                    record_type="staging_asset_candidate",
                    record_id=_sha256_text(_text(key_seed))[:24],
                    stable_business_key=f"staging:{_text(key_seed)}",
                    source_file=source_file,
                    source_sha256=source_sha,
                    content_sha256=content_sha,
                    page_no=_first(metadata.get("page_no"), specs.get("page_no")),
                    page_index=_first(metadata.get("page_index"), specs.get("page_index")),
                    title=payload.get("title"),
                    source_display_name=_first(metadata.get("source_display_name"), payload.get("title")),
                    category_label=_first(metadata.get("category_label"), payload.get("category")),
                    source_domain=metadata.get("source_domain"),
                    doc_owner=metadata.get("doc_owner"),
                    enterprise=metadata.get("enterprise"),
                    evidence_type=_first(metadata.get("evidence_type"), specs.get("evidence_type")),
                    target_library=_first(metadata.get("target_library"), specs.get("target_library")),
                    product_family=_first(metadata.get("product_family"), specs.get("product_family")),
                    model_specs=_first(metadata.get("model_specs"), specs.get("model_specs")),
                    report_or_certificate_no=_first(metadata.get("report_no"), metadata.get("certificate_no")),
                    quality_tier="review_only",
                    allowed_for_bid=False,
                    review_status="parser_intermediate",
                    ingestion_batch_id=_first(metadata.get("ingestion_batch_id"), metadata.get("source_batch_id")),
                    status="staging_only",
                    source_system=str(path.relative_to(PROJECT_ROOT)),
                    notes="解析中间候选；不得直接进入正式展示、RAG或DOCX",
                )
            )
    return records


def _counter(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(_text(record.get(key)) or "(空)" for record in records).items()))


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    record_type_details: dict[str, Any] = {}
    for record_type in sorted({record["record_type"] for record in records}):
        subset = [record for record in records if record["record_type"] == record_type]
        business_keys = Counter(record["stable_business_key"] for record in subset)
        record_type_details[record_type] = {
            "count": len(subset),
            "allowed_for_bid_true": sum(record.get("allowed_for_bid") is True for record in subset),
            "unique_source_sha256": len(
                {record["source_sha256"] for record in subset if record.get("source_sha256")}
            ),
            "missing_source_sha256": sum(not record.get("source_sha256") for record in subset),
            "stable_business_key_duplicates": sum(count - 1 for count in business_keys.values() if count > 1),
            "quality_tiers": _counter(subset, "quality_tier"),
            "metadata_completeness": _counter(subset, "metadata_completeness"),
            "statuses": _counter(subset, "status"),
        }
    return {
        "total_records": len(records),
        "by_record_type": _counter(records, "record_type"),
        "by_source_domain": _counter(records, "source_domain"),
        "by_quality_tier": _counter(records, "quality_tier"),
        "by_evidence_type": _counter(records, "evidence_type"),
        "by_target_library": _counter(records, "target_library"),
        "by_metadata_completeness": _counter(records, "metadata_completeness"),
        "allowed_for_bid_true": sum(record.get("allowed_for_bid") is True for record in records),
        "unique_source_sha256": len({record["source_sha256"] for record in records if record.get("source_sha256")}),
        "stable_business_key_duplicates": sum(
            count - 1 for count in Counter(record["stable_business_key"] for record in records).values() if count > 1
        ),
        "record_type_details": record_type_details,
    }


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({key: _text(record.get(key)) for key in CSV_FIELDS})


def build_snapshot() -> dict[str, Any]:
    hash_cache: dict[str, str] = {}
    documents, assets, chunks = _fetch_database_rows()
    records = [
        *_document_records(documents, hash_cache),
        *_asset_records(assets, hash_cache),
        *_chunk_records(chunks),
        *_product_parameter_records(PRODUCT_PARAMETER_PATH, hash_cache),
        *_project_performance_records(PROJECT_PERFORMANCE_PATH, hash_cache),
        *_raw_file_records(RAW_ENTERPRISE_ROOT, hash_cache),
        *_staging_asset_records(STAGING_ROOT, hash_cache),
    ]
    return {
        "snapshot_version": "taichang_asset_baseline_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "enterprise": "河北泰昌电力器材科技有限公司",
        "write_policy": "read_only_database_and_local_inventory",
        "summary": _summary(records),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成泰昌当前数字资产基线 JSON/CSV")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    json_path = output_dir / "current_asset_baseline.json"
    csv_path = output_dir / "current_asset_baseline.csv"
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    _write_csv(csv_path, snapshot["records"])
    print(json.dumps({"json": str(json_path), "csv": str(csv_path), "summary": snapshot["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

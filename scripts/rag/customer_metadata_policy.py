"""Metadata policy gates for customer RAG corpus ingestion."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


SOURCE_DOMAIN_CITATION_POLICY = {
    "enterprise_fact": "enterprise_fact_citable",
    "tender_requirement": "tender_requirement_citable",
    "reference_template": "reference_style_only",
    "policy_regulation": "law_or_standard_citable",
    "base_seed": "summary_only",
}

SOURCE_DOMAIN_AUTHORITY_LEVEL = {
    "enterprise_fact": "enterprise_fact",
    "tender_requirement": "tender_file",
    "reference_template": "reference_template",
    "policy_regulation": "law_or_standard",
    "base_seed": "base_reference",
}

TENDER_DOC_ROLES = {
    "main_tender_file",
    "tender_notice",
    "technical_spec",
    "goods_list",
    "contract_general_terms",
    "contract_special_terms",
    "bid_instructions",
}


def _is_blank(value: Any) -> bool:
    return value in (None, "", "all")


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return None


def infer_source_domain(record: dict[str, Any], metadata: dict[str, Any]) -> str | None:
    if not _is_blank(metadata.get("source_domain")):
        return str(metadata.get("source_domain"))
    doc_role = str(record.get("doc_role") or metadata.get("doc_role") or "")
    if doc_role in TENDER_DOC_ROLES or not _is_blank(metadata.get("province")):
        return "tender_requirement"
    return None


def citation_policy_for(metadata: dict[str, Any]) -> str | None:
    explicit = metadata.get("citation_policy")
    if not _is_blank(explicit):
        return str(explicit)
    source_domain = metadata.get("source_domain")
    if _is_blank(source_domain):
        return None
    return SOURCE_DOMAIN_CITATION_POLICY.get(str(source_domain))


def authority_level_for(metadata: dict[str, Any]) -> str:
    source_domain = str(metadata.get("source_domain") or "")
    return SOURCE_DOMAIN_AUTHORITY_LEVEL.get(source_domain, "customer_reference")


def document_identity_key(record: dict[str, Any], metadata: dict[str, Any]) -> str:
    explicit = metadata.get("doc_key") or metadata.get("document_key")
    if not _is_blank(explicit):
        return str(explicit)
    parts = [
        metadata.get("source_domain"),
        metadata.get("doc_owner"),
        metadata.get("enterprise"),
        metadata.get("province"),
        metadata.get("batch_no"),
        metadata.get("package_code"),
        metadata.get("material_category"),
        metadata.get("doc_role") or record.get("doc_role"),
        metadata.get("source_file") or record.get("source_file"),
    ]
    raw_key = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(raw_key.encode("utf-8")).hexdigest()


def normalize_customer_record_metadata(record: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    metadata = dict(record.get("metadata") or {})
    warnings: list[str] = []
    errors: list[str] = []

    source_domain = infer_source_domain(record, metadata)
    if source_domain:
        metadata["source_domain"] = source_domain
    else:
        errors.append("missing source_domain")

    source_file = record.get("source_file") or metadata.get("source_file")
    if source_file:
        metadata["source_file"] = source_file
    else:
        errors.append("missing source_file")

    if _is_blank(metadata.get("doc_role")) and not _is_blank(record.get("doc_role")):
        metadata["doc_role"] = record.get("doc_role")
    if _is_blank(metadata.get("doc_version")):
        errors.append("missing doc_version")
    if _is_blank(record.get("sha256")) and _is_blank(metadata.get("source_sha256")):
        errors.append("missing source sha256")
    else:
        metadata["source_sha256"] = record.get("sha256") or metadata.get("source_sha256")

    citation_policy = citation_policy_for(metadata)
    if citation_policy:
        metadata["citation_policy"] = citation_policy
    else:
        errors.append("missing citation_policy")
    metadata["authority_level"] = authority_level_for(metadata)
    metadata["doc_identity_key"] = document_identity_key(record, metadata)
    metadata.setdefault("superseded_by", None)

    domain = metadata.get("source_domain")
    if domain == "tender_requirement":
        metadata.setdefault("reference_only", False)
        metadata.setdefault("fact_source_allowed_for_enterprise", False)
    elif domain == "reference_template":
        metadata.setdefault("reference_only", True)
        metadata.setdefault("fact_source_allowed_for_enterprise", False)

    reference_only = _as_bool(metadata.get("reference_only"))
    fact_allowed = _as_bool(metadata.get("fact_source_allowed_for_enterprise"))

    if domain == "enterprise_fact":
        if _is_blank(metadata.get("enterprise")):
            errors.append("enterprise_fact missing enterprise")
        if _is_blank(metadata.get("doc_owner")):
            errors.append("enterprise_fact missing doc_owner")
        if reference_only is not False:
            errors.append("enterprise_fact requires reference_only=false")
        if fact_allowed is not True:
            errors.append("enterprise_fact requires fact_source_allowed_for_enterprise=true")
        if metadata.get("citation_policy") != "enterprise_fact_citable":
            errors.append("enterprise_fact requires citation_policy=enterprise_fact_citable")
    elif domain == "tender_requirement":
        if fact_allowed is not False:
            errors.append("tender_requirement requires fact_source_allowed_for_enterprise=false")
        if metadata.get("citation_policy") != "tender_requirement_citable":
            errors.append("tender_requirement requires citation_policy=tender_requirement_citable")
    elif domain == "reference_template":
        if reference_only is not True:
            errors.append("reference_template requires reference_only=true")
        if fact_allowed is not False:
            errors.append("reference_template requires fact_source_allowed_for_enterprise=false")
        if metadata.get("citation_policy") != "reference_style_only":
            errors.append("reference_template requires citation_policy=reference_style_only")
    elif domain and domain not in SOURCE_DOMAIN_CITATION_POLICY:
        warnings.append(f"unknown source_domain={domain}")

    if metadata.get("status") == "superseded" and _is_blank(metadata.get("superseded_by")):
        errors.append("superseded metadata requires superseded_by")

    return metadata, warnings, errors


def comparable_doc_version(value: Any) -> tuple[int, str]:
    if isinstance(value, int):
        return value, ""
    text = str(value or "")
    if text.isdigit():
        return int(text), ""
    return 0, text


def should_supersede(existing_metadata: dict[str, Any], new_metadata: dict[str, Any]) -> bool:
    if existing_metadata.get("doc_identity_key") != new_metadata.get("doc_identity_key"):
        return False
    if existing_metadata.get("source_sha256") == new_metadata.get("source_sha256"):
        return False
    if existing_metadata.get("status") == "superseded":
        return False
    existing_version = comparable_doc_version(existing_metadata.get("doc_version"))
    new_version = comparable_doc_version(new_metadata.get("doc_version"))
    return existing_version <= new_version

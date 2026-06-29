#!/usr/bin/env python3
"""Quarantine Taichang enterprise-basic-info OCR conflicts from RAG retrieval."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.postgres_compat import _database_url
from backend.db.postgres_pool import pooled_connection
from backend.rag.enterprise_facts import _enterprise_facts


LOW_TRUST_EVIDENCE_TYPES = {
    "enterprise_profile",
    "production_capacity",
    "testing_capacity",
    "finance",
    "personnel_certificate",
    "green_low_carbon",
}

AUTHORITATIVE_EVIDENCE_TYPES = {"business_license"}
AUTHORITATIVE_SOURCE_TERMS = ["营业执照", "企业信用报告", "公共信用信息报告", "工商基础信息"]
FIELD_PATTERNS = {
    "legal_representative": [
        r"(?:法定代表人|法人代表|企业负责人)(?:（[^）]*）)?\s*[：:]\s*([\u4e00-\u9fff]{2,4})",
    ],
    "unified_social_credit_code": [
        r"(?:统一社会信用代码|社会信用代码)\s*[：:]\s*([0-9A-Z]{15,20})",
    ],
    "registered_capital": [
        r"(?:注册资本|注册资金)\s*[：:]\s*([0-9,.]+(?:万)?元(?:人民币)?|[零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+元整?)",
    ],
}


def _metadata_with_quarantine(metadata: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    notes = list(metadata.get("quality_notes") or [])
    note = "低可信/OCR片段中工商基础字段与泰昌营业执照或企业信用报告冲突，已禁止作为企业事实进入RAG。"
    if note not in notes:
        notes.append(note)
    history = list(metadata.get("repair_history") or [])
    history.append(
        {
            "run_id": "run_20260629_taichang_legal_representative_fact_fix",
            "repaired_at": now,
            "action": "exclude_conflicting_enterprise_basic_info_ocr_from_rag",
            "verified_facts": {
                "legal_representative": _enterprise_facts().get("legal_representative"),
                "unified_social_credit_code": _enterprise_facts().get("unified_social_credit_code"),
                "registered_capital": _enterprise_facts().get("registered_capital"),
                "established_date": _enterprise_facts().get("established_date"),
                "registered_address": _enterprise_facts().get("registered_address"),
            },
        }
    )
    return {
        **metadata,
        "exclude_from_rag": True,
        "rag_visibility": "internal_only",
        "fact_source_allowed_for_enterprise": False,
        "citation_policy": "internal_review_only",
        "quality_tier": "review_only",
        "quality_notes": notes,
        "repair_history": history,
    }


def _normalize_fact_value(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("人民币", "")
    text = text.replace("（", "(").replace("）", ")")
    return "".join(ch for ch in text if ch.isalnum() or "\u4e00" <= ch <= "\u9fff").lower()


def _looks_authoritative(metadata: dict[str, Any], content: str) -> bool:
    evidence_type = str(metadata.get("evidence_type") or "")
    source_name = " ".join(
        str(metadata.get(key) or "")
        for key in ["source_display_name", "source_document_name", "source_file", "doc_type", "category_label"]
    )
    text = f"{source_name} {content}"
    return evidence_type in AUTHORITATIVE_EVIDENCE_TYPES or any(term in text for term in AUTHORITATIVE_SOURCE_TERMS)


def _looks_low_trust(metadata: dict[str, Any], content: str) -> bool:
    if _looks_authoritative(metadata, content):
        return False
    evidence_type = str(metadata.get("evidence_type") or "")
    source_name = " ".join(
        str(metadata.get(key) or "")
        for key in ["source_display_name", "source_document_name", "source_file", "doc_type", "category_label"]
    )
    if evidence_type in LOW_TRUST_EVIDENCE_TYPES:
        return True
    return any(term in source_name for term in ["宣传彩页", "宣传册", "花名册", "生产线", "审计报告"])


def _extracted_basic_facts(content: str) -> dict[str, str]:
    extracted: dict[str, str] = {}
    for field, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, content)
            if match and match.group(1).strip():
                extracted[field] = match.group(1).strip()
                break
    return extracted


def _is_valid_extracted_fact(field: str, value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if field == "legal_representative":
        return bool(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", text)) and not any(
            token in text for token in ["代表", "委托", "代理", "负责", "电话", "开户"]
        )
    if field == "unified_social_credit_code":
        return bool(re.fullmatch(r"[0-9A-Z]{15,20}", text))
    if field == "registered_capital":
        return "元" in text and len(text) <= 20
    return False


def _conflicts_with_verified_facts(row: dict[str, Any], verified: dict[str, Any]) -> bool:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    content = str(row.get("content") or "")
    if not _looks_low_trust(metadata, content):
        return False
    for field, candidate in _extracted_basic_facts(content).items():
        expected = verified.get(field)
        if not expected or not _is_valid_extracted_fact(field, candidate):
            continue
        candidate_norm = _normalize_fact_value(candidate)
        expected_norm = _normalize_fact_value(expected)
        if candidate_norm and expected_norm and candidate_norm not in expected_norm and expected_norm not in candidate_norm:
            return True
    return False


def find_conflicting_chunks() -> list[dict[str, Any]]:
    verified = _enterprise_facts()
    sql = """
        select id, document_id, content, metadata
        from document_chunks
        where metadata->>'enterprise' = '泰昌'
          and metadata->>'source_domain' = 'enterprise_fact'
          and (
              content ~ '(法定代表人|法人代表|企业负责人|统一社会信用代码|社会信用代码|注册资本|注册资金|成立日期|成立时间|注册地址|住所|营业场所)'
              or metadata->>'source_display_name' = '宣传彩页'
          )
        order by created_at nulls last, id
    """
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [row for row in rows if _conflicts_with_verified_facts(row, verified)]


def quarantine_chunks(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = "update document_chunks set metadata = %s where id = %s"
    updated = 0
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            for row in rows:
                metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                cur.execute(sql, (Jsonb(_metadata_with_quarantine(metadata)), row["id"]))
                updated += cur.rowcount
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="apply metadata quarantine updates")
    args = parser.parse_args()

    rows = find_conflicting_chunks()
    print(json.dumps(
        {
            "matched_conflicting_chunks": len(rows),
            "execute": args.execute,
            "chunk_ids": [str(row.get("id")) for row in rows],
        },
        ensure_ascii=False,
        indent=2,
    ))
    if args.execute:
        print(json.dumps({"updated_chunks": quarantine_chunks(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

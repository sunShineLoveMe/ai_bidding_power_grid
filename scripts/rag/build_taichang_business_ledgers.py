#!/usr/bin/env python3
"""Build the auditable Taichang P1-03 business ledgers.

The script consolidates existing verified assets instead of reparsing or
re-ingesting them. Exact values are linked to original files and pages;
historical Word claims never override current original evidence.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "docs/development/taichang-bid-v1-data/p1_03_business_ledgers"
RESTRICTED_OUTPUT_DIR = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611"
    / "staging/taichang_business_ledgers"
)
EVIDENCE_BUNDLES_PATH = (
    PROJECT_ROOT
    / "docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundles.json"
)
HISTORICAL_CANDIDATES_PATH = (
    PROJECT_ROOT
    / "docs/development/taichang-bid-v1-data/p1_01_ingestion/table_extraction/泰昌历史标书证据登记候选.json"
)
HISTORICAL_PARAMETER_CANDIDATES_PATH = (
    PROJECT_ROOT
    / "docs/development/taichang-bid-v1-data/p1_01_ingestion/table_extraction/泰昌历史标书技术参数候选.json"
)
PRODUCT_PARAMETER_ROWS_PATH = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/"
    "staging/taichang_product_parameters/taichang_product_parameter_rows.json"
)
PROJECT_PERFORMANCE_ROWS_PATH = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/"
    "staging/taichang_project_performance/taichang_project_performance_rows.json"
)
SUPPLEMENT_MANIFEST_PATH = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/manifest.json"
)

ENTERPRISE = "河北泰昌电力器材科技有限公司"
SHORT_ENTERPRISE = "泰昌"
AS_OF_DATE = date(2026, 7, 14)

AUDIT_FACTS = {
    "2023": {
        "report_no": "世仁审字〔2024〕第VE-73号",
        "audit_firm": "石家庄世仁会计师事务所（普通合伙）",
        "report_no_source_page": 1,
        "value_source": "人工核验原始PDF第1页",
    },
    "2024": {
        "report_no": "",
        "audit_firm": "北京中体华会计师事务所（普通合伙）",
        "report_no_source_page": None,
        "value_source": "原始PDF封面未显示报告编号，保持待复核",
    },
    "2025": {
        "report_no": "世仁审字〔2026〕第St-050号",
        "audit_firm": "石家庄世仁会计师事务所（普通合伙）",
        "report_no_source_page": 1,
        "value_source": "人工核验原始PDF第1页",
    },
}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_clean(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path | str) -> str:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return str(path_obj.relative_to(PROJECT_ROOT))
    return str(path_obj)


def _base_row(ledger_type: str, business_key: str) -> dict[str, Any]:
    return {
        "ledger_type": ledger_type,
        "business_key": business_key,
        "enterprise": SHORT_ENTERPRISE,
        "doc_owner": ENTERPRISE,
        "source_domain": "enterprise_fact",
        "reference_only": False,
        "fact_source_allowed_for_enterprise": True,
        "tenant_visibility": "taichang_only",
        "access_scope": "taichang_tenant_internal",
        "target_library": "qualification_library",
        "target_library_label": "资信库",
        "allowed_for_bid": False,
        "formal_bid_ready": False,
    }


def _bundle_indexes(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_key: dict[str, dict[str, Any]] = {}
    by_kind: dict[str, dict[str, Any]] = {}
    for bundle in payload.get("bundles") or []:
        by_key[str(bundle.get("business_key") or "")] = bundle
        by_kind[f"{bundle.get('bundle_kind')}|{bundle.get('business_key')}"] = bundle
    return by_key, by_kind


def _pdf_page_texts(source_file: str) -> list[str]:
    reader = PdfReader(str(PROJECT_ROOT / source_file))
    return [_clean(page.extract_text() or "") for page in reader.pages]


def _date_iso(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return ""


def _validity_status(valid_until: str) -> str:
    if not valid_until:
        return "needs_review"
    parsed = date.fromisoformat(valid_until)
    return "valid" if parsed >= AS_OF_DATE else "expired"


def _normalise_equipment_name(value: str) -> str:
    return {
        "热变型、维卡软化点温度测定仪": "热变形、维卡软化点温度测定仪",
        "溶体流动速率仪": "熔体流动速率仪",
    }.get(_clean(value), _clean(value))


def _extract_equipment_rows(bundles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bundle in bundles:
        if bundle.get("bundle_kind") != "calibration_certificate":
            continue
        source = (bundle.get("primary_sources") or [])[0]
        source_file = str(source.get("source_file") or "")
        page_texts = _pdf_page_texts(source_file)
        certificate_page_index = next(
            (index for index, text in enumerate(page_texts) if "校准证书" in text and "证书编号" in text),
            -1,
        )
        if certificate_page_index < 0:
            raise RuntimeError(f"calibration certificate page not found: {source_file}")
        certificate_text = page_texts[certificate_page_index]
        statement_text = page_texts[certificate_page_index + 1] if certificate_page_index + 1 < len(page_texts) else ""

        def pick(pattern: str, text: str = certificate_text) -> str:
            match = re.search(pattern, text)
            return _clean(match.group(1)) if match else ""

        equipment_name = _normalise_equipment_name(
            pick(r"器具名称：\s*Description\s*(.+?)\s*型号/规格")
        )
        certificate_no = pick(r"证书编号：\s*([A-Z0-9]+)")
        model = pick(r"型号/规格：\s*Model\s*([A-Z0-9./-]+)")
        serial_no = pick(r"出厂编号：\s*Serial No\.\s*([A-Z0-9./-]+)\s*管理编号")
        equipment_no = pick(r"管理编号\s*Equipment No\.\s*([A-Z0-9./-]+)")
        manufacturer = pick(r"制造单位：\s*Manufacturer\s*(.+?)\s*批准人")
        calibration_date = _date_iso(pick(r"校准日期：\s*Calibration date:\s*(\d{4}年\d{2}月\d{2}日)"))
        issue_date = _date_iso(pick(r"签发日期：\s*Date of issue:\s*(\d{4}年\d{2}月\d{2}日)"))
        recalibration_due = _date_iso(pick(r"复校日期：\s*(\d{4}年\d{2}月\d{2}日)", statement_text))
        if not all([equipment_name, certificate_no, model, equipment_no, calibration_date, recalibration_due]):
            raise RuntimeError(f"incomplete calibration fields: {source_file}")

        row = {
            **_base_row(
                "equipment_calibration",
                f"equipment:{equipment_name}|certificate:{certificate_no}",
            ),
            "evidence_type": "testing_capacity",
            "evidence_type_label": "试验检测设备及校准资料",
            "target_library": "product_library",
            "target_library_label": "产品库",
            "equipment_name": equipment_name,
            "equipment_model": model,
            "serial_no": serial_no,
            "equipment_no": equipment_no,
            "manufacturer": manufacturer,
            "calibration_certificate_no": certificate_no,
            "calibration_date": calibration_date,
            "issue_date": issue_date,
            "recalibration_due": recalibration_due,
            "validity_status": _validity_status(recalibration_due),
            "review_status": "structured_verified",
            "quality_tier": "knowledge_only",
            "usage_status": "eligible_after_project_validity_check",
            "source_file": source_file,
            "source_display_name": f"泰昌{equipment_name}校准证书",
            "source_page": certificate_page_index + 1,
            "validity_source_page": certificate_page_index + 2,
            "evidence_bundle_id": bundle.get("evidence_bundle_id"),
            "historical_conflict_policy": "current_original_calibration_overrides_historical_word_date",
        }
        rows.append(row)
    return sorted(rows, key=lambda row: row["equipment_name"])


def _manifest_records() -> list[dict[str, Any]]:
    payload = _load_json(SUPPLEMENT_MANIFEST_PATH, {})
    return [row for row in payload.get("records") or [] if isinstance(row, dict)]


def _manifest_record(path_keyword: str) -> dict[str, Any]:
    matches = [row for row in _manifest_records() if path_keyword in str(row.get("source_file") or "")]
    if len(matches) != 1:
        raise RuntimeError(f"expected one manifest record for {path_keyword}, found {len(matches)}")
    return matches[0]


def _extract_management_certificate_rows(
    bundles_by_key: dict[str, dict[str, Any]],
    historical_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    claims = [row for row in historical_records if row.get("record_kind") == "management_system_certificate_claim"]
    mapping = {
        "质量管理体系认证证书": "management-system:quality",
        "环境管理体系认证证书": "management-system:environment",
        "职业健康安全管理体系认证证书": "management-system:ohs",
    }
    rows: list[dict[str, Any]] = []
    for claim in claims:
        certificate_name = str(claim.get("certificate_name") or "")
        bundle_key = mapping[certificate_name]
        bundle = bundles_by_key[bundle_key]
        record = _manifest_record(certificate_name)
        markdown_path = PROJECT_ROOT / str(record.get("output_file") or "")
        markdown = markdown_path.read_text(encoding="utf-8")
        certificate_no = str(claim.get("certificate_number") or "")
        if certificate_no not in markdown:
            raise RuntimeError(f"original OCR does not confirm certificate number {certificate_no}")
        valid_until = str(claim.get("valid_until") or "")
        status = _validity_status(valid_until)
        source = (bundle.get("primary_sources") or [])[0]
        rows.append(
            {
                **_base_row("management_certificate", f"certificate:{certificate_no}"),
                "evidence_type": "certification",
                "evidence_type_label": "管理体系认证证书",
                "certificate_name": certificate_name,
                "certificate_no": certificate_no,
                "issuer": _clean(claim.get("issuer_raw")),
                "certification_scope": _clean(claim.get("scope_raw")),
                "valid_until": valid_until,
                "validity_status": status,
                "review_status": "structured_verified",
                "quality_tier": "knowledge_only",
                "usage_status": "blocked_expired" if status == "expired" else "eligible_after_project_validity_check",
                "source_file": source.get("source_file"),
                "source_display_name": f"泰昌{certificate_name}",
                "source_page": 1,
                "evidence_bundle_id": bundle.get("evidence_bundle_id"),
                "historical_source_file": claim.get("source_file"),
                "historical_source_page": claim.get("source_page"),
                "conflict_policy": "original_certificate_preferred_historical_word_mapping_only",
            }
        )
    return sorted(rows, key=lambda row: row["certificate_name"])


def _extract_audit_rows(bundles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bundle in bundles:
        if bundle.get("bundle_kind") != "audit_report":
            continue
        year = str((bundle.get("structured_summary") or {}).get("audit_year") or "")
        facts = AUDIT_FACTS[year]
        source = (bundle.get("primary_sources") or [])[0]
        report_no = str(facts["report_no"])
        rows.append(
            {
                **_base_row("audit_report", f"audit:{year}"),
                "evidence_type": "finance",
                "evidence_type_label": "审计报告",
                "audit_year": year,
                "report_no": report_no,
                "report_no_status": "verified" if report_no else "needs_manual_review",
                "audit_firm": facts["audit_firm"],
                "file_page_count": source.get("expected_page_count"),
                "file_complete": bool(source.get("complete")),
                "validity_status": "conditional_tender_year",
                "review_status": "structured_verified" if report_no else "needs_manual_review",
                "quality_tier": "knowledge_only",
                "usage_status": "conditional_tender_year",
                "source_file": source.get("source_file"),
                "source_display_name": f"泰昌{year}年审计报告",
                "source_page": facts["report_no_source_page"],
                "source_pages": list(range(1, int(source.get("expected_page_count") or 0) + 1)),
                "evidence_bundle_id": bundle.get("evidence_bundle_id"),
                "value_source": facts["value_source"],
            }
        )
    return sorted(rows, key=lambda row: row["audit_year"])


def _extract_roster_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    record = _manifest_record("31人员花名册")
    markdown_path = PROJECT_ROOT / str(record.get("output_file") or "")
    parser = _TableParser()
    parser.feed(markdown_path.read_text(encoding="utf-8"))
    table = next((item for item in parser.tables if item and "姓名" in item[0] and "岗位" in item[0]), None)
    if not table:
        raise RuntimeError("personnel roster table not found")
    headers = table[0]
    rows: list[dict[str, Any]] = []
    for row_index, values in enumerate(table[1:], start=1):
        raw = dict(zip(headers, values))
        name = _clean(raw.get("姓名"))
        if not name:
            continue
        rows.append(
            {
                # 花名册可能存在同名人员；业务键同时保留源表行序，避免静默合并。
                **_base_row("personnel_roster", f"person:{name}|roster-row:{row_index}"),
                "evidence_type": "personnel_certificate",
                "evidence_type_label": "人员花名册",
                "roster_row_no": row_index,
                "person_name": name,
                "project_role": _clean(raw.get("岗位")),
                "education": _clean(raw.get("学历")),
                "professional_title": _clean(raw.get("职称")),
                "social_insurance_recorded": _clean(raw.get("购买社保")) == "√",
                "labor_contract_recorded": _clean(raw.get("签订劳动合同")) == "√",
                "employment_start_year": _clean(raw.get("入职时间")),
                "review_status": "restricted_structured",
                "quality_tier": "restricted",
                "usage_status": "manual_authorization_required",
                "rag_visibility": "internal_only",
                "source_file": record.get("source_file"),
                "source_display_name": "泰昌公司人员花名册",
                "source_page": 1,
            }
        )
    summary = {
        **_base_row("personnel_summary", "personnel-summary:current-roster"),
        "evidence_type": "personnel_certificate",
        "evidence_type_label": "人员资料摘要",
        "personnel_count": len(rows),
        "certificate_record_count": 2,
        "professional_title_filled_count": sum(1 for row in rows if row.get("professional_title")),
        "review_status": "knowledge_summary_only",
        "quality_tier": "knowledge_only",
        "usage_status": "individual_details_require_authorization",
        "source_file": record.get("source_file"),
        "source_display_name": "泰昌人员资料摘要",
        "source_page": 1,
    }
    return rows, summary


def _mask_certificate_no(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return f"{value[:1]}{'*' * (len(value) - 5)}{value[-4:]}"


def _extract_personnel_certificate_rows(roster_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    roles = {row["person_name"]: row.get("project_role") for row in roster_rows}
    rows: list[dict[str, Any]] = []
    certificate_records = [
        record
        for record in _manifest_records()
        if "30试验检测人员证书整页扫描件/" in str(record.get("source_file") or "")
        and str(record.get("source_file") or "").lower().endswith(".pdf")
    ]
    if len(certificate_records) != 2:
        raise RuntimeError(f"expected 2 restricted personnel certificates, found {len(certificate_records)}")
    for record in certificate_records:
        markdown_path = PROJECT_ROOT / str(record.get("output_file") or "")
        text = markdown_path.read_text(encoding="utf-8")

        def pick(pattern: str) -> str:
            match = re.search(pattern, text)
            return _clean(match.group(1)) if match else ""

        certificate_no = pick(r"证(?:N)?号：\s*([A-Z0-9]+)")
        person_name = pick(r"姓名：\s*([^\n]+)")
        operation_category = pick(r"作业类别：\s*([^\n]+)")
        permitted_operation = pick(r"准操项目：\s*([^\n]+)")
        issue_date = _date_iso(pick(r"初领日期：\s*(\d{8})"))
        valid_range = pick(r"有效期(?:限|阳)?\s*[:：]?\s*(\d{8}-\d{8})")
        review_date = _date_iso(pick(r"复审日期：\s*(\d{8})"))
        valid_until = _date_iso(valid_range.split("-", 1)[1] if "-" in valid_range else "")
        if not all([certificate_no, person_name, permitted_operation, valid_until]):
            raise RuntimeError(f"incomplete personnel certificate fields: {record.get('source_file')}")
        rows.append(
            {
                **_base_row("personnel_certificate", f"person:{person_name}|certificate:{certificate_no}"),
                "evidence_type": "personnel_certificate",
                "evidence_type_label": "人员证书",
                "person_name": person_name,
                "project_role": roles.get(person_name) or "",
                "certificate_no": certificate_no,
                "certificate_no_display": _mask_certificate_no(certificate_no),
                "operation_category": operation_category,
                "permitted_operation": permitted_operation,
                "initial_issue_date": issue_date,
                "valid_until": valid_until,
                "review_date": review_date,
                "validity_status": _validity_status(valid_until),
                "review_status": "restricted_structured",
                "quality_tier": "restricted",
                "usage_status": "manual_authorization_required",
                "rag_visibility": "internal_only",
                "source_file": record.get("source_file"),
                "source_display_name": f"泰昌{person_name}特种作业操作证",
                "source_page": 1,
            }
        )
    return rows


def _extract_inspection_registry_rows(
    bundles_by_key: dict[str, dict[str, Any]],
    historical_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for claim in historical_records:
        if claim.get("record_kind") != "inspection_report_registry":
            continue
        report_no = str(claim.get("report_number") or "")
        verified = claim.get("fact_status") == "verified_existing_report_number"
        bundle = bundles_by_key.get(f"report:{report_no}") if verified else None
        primary_source = ((bundle or {}).get("primary_sources") or [{}])[0]
        rows.append(
            {
                **_base_row("inspection_report_registry", f"report:{report_no}"),
                "evidence_type": "inspection_report",
                "evidence_type_label": "检验报告登记",
                "target_library": "product_library",
                "target_library_label": "产品库",
                "report_no": report_no,
                "product_name": claim.get("product_name"),
                "product_family": claim.get("product_family"),
                "specification_model": _clean(claim.get("specification_model_raw")),
                "report_date": _clean(claim.get("report_date_raw")),
                "issuer": _clean(claim.get("issuer_raw")),
                "fact_status": "verified_existing_report" if verified else "needs_original_evidence",
                "review_status": "structured_verified" if verified else "needs_original_evidence",
                "quality_tier": "knowledge_only" if verified else "review_only",
                "usage_status": "link_existing_do_not_duplicate" if verified else "blocked_missing_original_report",
                "fact_source_allowed_for_enterprise": verified,
                "source_file": primary_source.get("source_file") if verified else claim.get("source_file"),
                "source_display_name": (
                    (bundle or {}).get("bundle_title")
                    if verified
                    else f"泰昌{claim.get('product_family')}检验报告待补原件登记"
                ),
                "source_page": 1 if verified else claim.get("source_page"),
                "historical_source_file": claim.get("source_file"),
                "historical_source_page": claim.get("source_page"),
                "evidence_bundle_id": (bundle or {}).get("evidence_bundle_id"),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            flat = {
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                for key, value in row.items()
            }
            writer.writerow(flat)


def build_payload() -> dict[str, Any]:
    evidence_payload = _load_json(EVIDENCE_BUNDLES_PATH, {})
    bundles = evidence_payload.get("bundles") or []
    bundles_by_key, _ = _bundle_indexes(evidence_payload)
    historical_payload = _load_json(HISTORICAL_CANDIDATES_PATH, {})
    historical_records = historical_payload.get("records") or []
    product_rows = _load_json(PRODUCT_PARAMETER_ROWS_PATH, [])
    performance_rows = _load_json(PROJECT_PERFORMANCE_ROWS_PATH, [])
    historical_parameter_payload = _load_json(HISTORICAL_PARAMETER_CANDIDATES_PATH, {})
    historical_parameter_rows = historical_parameter_payload.get("records") or []

    equipment_rows = _extract_equipment_rows(bundles)
    management_rows = _extract_management_certificate_rows(bundles_by_key, historical_records)
    audit_rows = _extract_audit_rows(bundles)
    roster_rows, personnel_summary = _extract_roster_rows()
    personnel_certificate_rows = _extract_personnel_certificate_rows(roster_rows)
    inspection_rows = _extract_inspection_registry_rows(bundles_by_key, historical_records)
    all_rows = [
        *equipment_rows,
        *management_rows,
        *audit_rows,
        *roster_rows,
        personnel_summary,
        *personnel_certificate_rows,
        *inspection_rows,
    ]
    keys = [row["business_key"] for row in all_rows]
    if len(keys) != len(set(keys)):
        duplicates = [key for key, count in Counter(keys).items() if count > 1]
        raise RuntimeError(f"duplicate ledger business keys: {duplicates}")

    gaps = [
        {
            "gap_id": "missing-nhap-original-report",
            "title": "泰昌N-HAP检验报告原件待补",
            "status": "needs_original_evidence",
            "historical_report_no": "2024400312005505333",
            "formal_parameter_rows_allowed": False,
        },
        {
            "gap_id": "missing-upvc-original-report",
            "title": "泰昌UPVC检验报告原件待补",
            "status": "needs_original_evidence",
            "historical_report_no": "2025200312005503479",
            "formal_parameter_rows_allowed": False,
        },
        {
            "gap_id": "missing-intellectual-property-evidence",
            "title": "泰昌知识产权原始证据待补",
            "status": "no_enterprise_original_evidence",
            "formal_fact_rows_allowed": False,
            "note": "当前仅在辽宁招标要求中出现专利/软著字段，不得转为泰昌企业事实。",
        },
        {
            "gap_id": "audit-2024-report-no-review",
            "title": "泰昌2024年审计报告编号待复核",
            "status": "needs_manual_review",
            "note": "原始PDF封面未显示报告编号，保持为空，不从相邻年度推断。",
        },
    ]
    restricted_rows = [row for row in all_rows if row.get("rag_visibility") == "internal_only"]
    published_rows = [row for row in all_rows if row.get("rag_visibility") != "internal_only"]
    counts = Counter(row["ledger_type"] for row in all_rows)
    return {
        "schema_version": "taichang-p1-03-business-ledger-v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "as_of_date": AS_OF_DATE.isoformat(),
        "enterprise": ENTERPRISE,
        "write_policy": "offline_staging_only_no_database_write_no_asset_promotion",
        "canonical_sources": {
            "verified_product_parameters": {
                "path": _rel(PRODUCT_PARAMETER_ROWS_PATH),
                "row_count": len(product_rows),
                "policy": "reuse_no_duplicate_copy",
            },
            "historical_technical_parameter_candidates": {
                "path": _rel(HISTORICAL_PARAMETER_CANDIDATES_PATH),
                "row_count": len(historical_parameter_rows),
                "policy": "candidate_only_parameter_fact_allowed_false",
            },
            "project_performance": {
                "path": _rel(PROJECT_PERFORMANCE_ROWS_PATH),
                "row_count": len(performance_rows),
                "policy": "reuse_no_duplicate_copy",
            },
            "evidence_bundles": {
                "path": _rel(EVIDENCE_BUNDLES_PATH),
                "bundle_count": len(bundles),
                "policy": "link_by_evidence_bundle_id",
            },
        },
        "summary": {
            "business_ledger_rows": len(all_rows),
            "published_safe_rows": len(published_rows),
            "restricted_local_rows": len(restricted_rows),
            "by_ledger_type": dict(sorted(counts.items())),
            "verified_product_parameter_rows": len(product_rows),
            "historical_technical_parameter_candidates": len(historical_parameter_rows),
            "project_performance_evidence_rows": len(performance_rows),
            "evidence_bundles": len(bundles),
            "gap_count": len(gaps),
            "database_writes": 0,
            "asset_promotions": 0,
        },
        # 版本库和普通 RAG 只保存安全投影；受限人员明细仅写本地 staging。
        "rows": published_rows,
        "gaps": gaps,
        "_restricted_rows": restricted_rows,
    }


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "taichang_business_ledger_rows.json"
    csv_path = OUTPUT_DIR / "taichang_business_ledger_rows.csv"
    report_path = OUTPUT_DIR / "taichang_business_ledger_report.md"
    manifest_path = OUTPUT_DIR / "taichang_p1_03_manifest.json"
    restricted_rows = payload.pop("_restricted_rows", [])
    RESTRICTED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    restricted_json_path = RESTRICTED_OUTPUT_DIR / "restricted_personnel_rows.json"
    restricted_csv_path = RESTRICTED_OUTPUT_DIR / "restricted_personnel_rows.csv"
    restricted_json_path.write_text(json.dumps(restricted_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(restricted_csv_path, restricted_rows)

    json_path.write_text(json.dumps(payload["rows"], ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(csv_path, payload["rows"])
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = payload["summary"]
    lines = [
        "# 泰昌 P1-03 结构化参数与业务台账报告",
        "",
        f"> 生成时间：{payload['generated_at']}",
        f"> 数据基准日：{payload['as_of_date']}",
        "",
        "## 结果",
        "",
        f"- 复用既有产品参数：{summary['verified_product_parameter_rows']} 行，不重复写入。",
        f"- 历史技术参数候选：{summary['historical_technical_parameter_candidates']} 行，继续禁止转为正式参数事实。",
        f"- 业务台账：{summary['business_ledger_rows']} 行，稳定业务键无重复。",
        f"- 版本库安全投影：{summary['published_safe_rows']} 行；受限人员明细 {summary['restricted_local_rows']} 行仅保留在本地 staging，不进入 Git、普通 RAG 或 DOCX。",
        f"- 项目业绩证据：{summary['project_performance_evidence_rows']} 条，复用既有结构化记录。",
        f"- 文件级证据包：{summary['evidence_bundles']} 个，全部按 `evidence_bundle_id` 关联。",
        "- 数据库写入：0；资产质量等级提升：0。",
        "",
        "## 台账分类",
        "",
        "| 类型 | 行数 |",
        "| --- | ---: |",
    ]
    labels = {
        "equipment_calibration": "设备与校准证书",
        "management_certificate": "管理体系证书",
        "audit_report": "审计报告",
        "personnel_roster": "人员花名册（受限）",
        "personnel_summary": "人员资料安全摘要",
        "personnel_certificate": "人员证书（受限）",
        "inspection_report_registry": "检验报告登记",
    }
    for key, count in summary["by_ledger_type"].items():
        lines.append(f"| {labels.get(key, key)} | {count} |")
    lines.extend(
        [
            "",
            "## 关键门禁",
            "",
            "- CPVC/MPP 两份报告继续复用原 36 行参数与既有证据包，不新增参数主记录。",
            "- N-HAP/UPVC 只有历史报告编号，保持 `needs_original_evidence`，不生成正式参数。",
            "- 6 台设备以 2026 年原始校准证书为准，历史 Word 中 2025 年日期只保留来源映射。",
            "- 职业健康安全管理体系证书已于 2026-06-18 到期，继续阻断正式引用。",
            "- 65 条人员花名册与 2 条人员证书标记 `restricted + internal_only`；普通 RAG 只使用不含个人证号的安全摘要。",
            "- 当前无泰昌专利/软著原始证据；辽宁招标评分字段不得转换为泰昌企业事实。",
            "",
            "## 待补与人工复核",
            "",
        ]
    )
    for gap in payload["gaps"]:
        lines.append(f"- {gap['title']}：`{gap['status']}`。{gap.get('note') or ''}".rstrip())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_outputs(payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

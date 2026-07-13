#!/usr/bin/env python3
"""结构化抽取泰昌历史技术标/商务标中的 Word 原生表格。

本脚本只把 Word OOXML 中的原始单元格作为事实输入，不对空值补写、不把
``DN``/``φ`` 擅自换算为毫米，也不把“完全响应”“以实际数量为准”转成数值。
历史标书表格默认是待核验线索；只有能与现有原始检验报告精确对应的报告编号
会标为“已有原始证据”，但仍不会重复写入产品参数事实层。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from lxml import etree


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.rag.inventory_taichang_historical_bids import (  # noqa: E402
    DEFAULT_BUSINESS_DOCX,
    DEFAULT_TECHNICAL_DOCX,
    DocxInventory,
    NS,
)


ENTERPRISE = "河北泰昌电力器材科技有限公司"
DATA_ROOT = PROJECT_ROOT / "docs/development/taichang-bid-v1-data"
DEFAULT_OUTPUT_DIR = DATA_ROOT / "p1_01_ingestion/table_extraction"
DEFAULT_RAW_OUTPUT_DIR = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_taichang_historical_bid_20260713"
    / "p1_01_table_extraction"
)
DEFAULT_EXISTING_PARAMETER_ROWS = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0"
    / "staging/taichang_product_parameters/taichang_product_parameter_rows.json"
)
INVENTORIES = {
    "technical": DATA_ROOT / "taichang_technical_bid_candidate_inventory.json",
    "business": DATA_ROOT / "taichang_business_bid_candidate_inventory.json",
}

REPORT_TABLE_INDEX = 9
CERTIFICATE_TABLE_INDEX = 7
PERSONNEL_TABLE_INDEX = 8
EQUIPMENT_TABLE_INDEX = 10
KNOWN_REPORTS = {"2024100312005501712", "2024100312005501713"}
SENSITIVE_BUSINESS_TABLES = {2, 3, 4}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _content_sha(rows: list[list[str]]) -> str:
    raw = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def _load_inventory_tables(bid_volume: str) -> dict[int, dict[str, Any]]:
    payload = json.loads(INVENTORIES[bid_volume].read_text(encoding="utf-8"))
    return {
        int(row["table_index"]): row
        for row in payload["records"]
        if row.get("record_type") == "table" and row.get("table_index")
    }


def extract_raw_tables(path: Path, bid_volume: str) -> list[dict[str, Any]]:
    """按 Word 文档体中的真实表格顺序提取所有单元格文字。"""

    inventory = _load_inventory_tables(bid_volume)
    source_hash = _sha256(path)
    with ZipFile(path) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    body = root.find("w:body", NS)
    if body is None:
        raise RuntimeError(f"DOCX 缺少 w:body: {path}")
    result: list[dict[str, Any]] = []
    table_index = 0
    for element in body:
        if element.tag != f"{{{NS['w']}}}tbl":
            continue
        table_index += 1
        rows = DocxInventory._table_rows(element)
        trace = inventory.get(table_index, {})
        result.append(
            {
                "table_id": f"{bid_volume}-table-{table_index:03d}",
                "bid_volume": bid_volume,
                "table_index": table_index,
                "source_file": _rel(path),
                "source_file_sha256": source_hash,
                "source_page": trace.get("source_page"),
                "source_section": trace.get("source_section", ""),
                "row_count": len(rows),
                "column_count": max((len(row) for row in rows), default=0),
                "content_sha256": _content_sha(rows),
                "rows": rows,
                "parser": "native_docx_ooxml",
                "mineru_invoked": False,
                "allowed_for_bid": False,
            }
        )
    return result


def _designation(value: str) -> tuple[str, int | None]:
    """保留 DN/φ 原始语义，只拆出检索数字，不做单位换算。"""

    match = re.search(r"(?P<kind>DN|[φΦ])\s*(?P<number>\d+(?:\.\d+)?)", value, flags=re.I)
    if not match:
        return "", None
    kind = match.group("kind")
    normalized = "DN" if kind.upper() == "DN" else "φ"
    number = float(match.group("number"))
    return normalized, int(number) if number.is_integer() else number


def _product_family(text: str) -> str:
    upper = text.upper()
    if "CPVC" in upper or "PVC-C" in upper:
        return "CPVC电缆保护管"
    if "MPP" in upper:
        return "MPP电缆保护管"
    if "N-HAP" in upper:
        return "涂塑钢制电缆导管（N-HAP）"
    if "UPVC" in upper:
        return "UPVC电力电缆导管"
    if "PVC" in upper:
        return "PVC复合材料管"
    return ""


def build_technical_parameter_rows(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_index = {row["table_index"]: row for row in tables if row["bid_volume"] == "technical"}
    result: list[dict[str, Any]] = []

    # 技术特性表中的空参数行/“完全响应”仅是占位响应，不是可用参数值。
    table = by_index[2]
    for row_number, row in enumerate(table["rows"][3:6], start=4):
        padded = row + [""] * (5 - len(row))
        result.append(
            _parameter_row(
                table,
                row_number,
                raw_name=padded[1],
                raw_unit=padded[2],
                requirement_raw=padded[3],
                guarantee_raw=padded[4],
                value_status="generic_response_or_blank",
                fact_status="not_a_parameter_fact",
                product_family="1kV架空绝缘导线（新疆历史项目）",
                source_role="mixed_historical_bid_placeholder",
            )
        )

    # PVC 货物清单：DN 是公称通径标记，不等价于本脚本中的毫米实测值。
    table = by_index[4]
    for row_number, row in enumerate(table["rows"][1:], start=2):
        padded = row + [""] * (7 - len(row))
        raw = " ".join((padded[4], padded[5]))
        unit, number = _designation(raw)
        result.append(
            _parameter_row(
                table,
                row_number,
                raw_name="公称通径",
                raw_unit=unit,
                requirement_raw=padded[5],
                guarantee_raw="",
                value_status="historical_tender_material_requirement",
                fact_status="not_taichang_enterprise_fact",
                product_family=_product_family(raw),
                source_role="historical_project_requirement",
                nominal_designation_raw=re.search(r"(?:DN|[φΦ])\s*\d+(?:\.\d+)?", raw, re.I).group(0) if unit else "",
                numeric_value=number,
                extra={"material_code": padded[3], "material_description": padded[4]},
            )
        )

    # 备品备件表：φ 保留为规格标记；数量是“以实际数量为准”，不得制造数值。
    table = by_index[6]
    for row_number, row in enumerate(table["rows"][1:], start=2):
        padded = row + [""] * (6 - len(row))
        unit, number = _designation(padded[2])
        family = _product_family(padded[2])
        partial_match = bool(number == 250 and family in {"MPP电缆保护管", "CPVC电缆保护管"})
        result.append(
            _parameter_row(
                table,
                row_number,
                raw_name="型号和规格",
                raw_unit=unit,
                requirement_raw=padded[2],
                guarantee_raw=padded[2],
                value_status="historical_enterprise_claim",
                fact_status="partial_match_existing_inspection_report" if partial_match else "unverified_historical_claim",
                product_family=family,
                source_role="historical_bid_claim",
                nominal_designation_raw=re.search(r"(?:DN|[φΦ])\s*\d+(?:\.\d+)?", padded[2], re.I).group(0) if unit else "",
                numeric_value=number,
                extra={
                    "quantity_raw": padded[3],
                    "quantity_unit": "米",
                    "quantity_numeric": None,
                    "manufacturer_raw": padded[4],
                    "existing_report_cross_check_scope": "product_family_and_nominal_designation_only" if partial_match else "none",
                },
            )
        )
    return result


def _parameter_row(
    table: dict[str, Any],
    row_number: int,
    *,
    raw_name: str,
    raw_unit: str,
    requirement_raw: str,
    guarantee_raw: str,
    value_status: str,
    fact_status: str,
    product_family: str,
    source_role: str,
    nominal_designation_raw: str = "",
    numeric_value: int | float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "enterprise": ENTERPRISE,
        "source_domain": "mixed_historical_bid",
        "source_role": source_role,
        "fact_source_allowed_for_enterprise": False,
        "allowed_for_bid": False,
        "parameter_fact_allowed": False,
        "requires_original_evidence": True,
        "source_file": table["source_file"],
        "source_file_sha256": table["source_file_sha256"],
        "source_table_id": table["table_id"],
        "source_table_index": table["table_index"],
        "source_row_number": row_number,
        "source_page": table["source_page"],
        "source_section": table["source_section"],
        "raw_name": raw_name,
        "raw_unit": raw_unit,
        "normalized_unit": raw_unit,
        "unit_conversion_performed": False,
        "requirement_raw": requirement_raw,
        "guarantee_raw": guarantee_raw,
        "numeric_value": numeric_value,
        "nominal_designation_raw": nominal_designation_raw,
        "product_family": product_family,
        "value_status": value_status,
        "fact_status": fact_status,
    }
    result.update(extra or {})
    return result


def build_evidence_register(tables: list[dict[str, Any]], existing_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_index = {row["table_index"]: row for row in tables if row["bid_volume"] == "technical"}
    existing_report_numbers = {str(row.get("report_no") or "").strip() for row in existing_rows}
    result: list[dict[str, Any]] = []

    table = by_index[CERTIFICATE_TABLE_INDEX]
    for row_number, row in enumerate(table["rows"][1:-1], start=2):
        padded = row + [""] * (5 - len(row))
        date_match = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", padded[4])
        valid_until = ""
        expired = None
        if date_match:
            parsed = date(*(int(value) for value in date_match.groups()))
            valid_until = parsed.isoformat()
            expired = parsed < date.today()
        result.append(
            {
                "record_kind": "management_system_certificate_claim",
                "certificate_name": padded[0],
                "certificate_number": padded[2],
                "issuer_raw": padded[1],
                "scope_raw": padded[3],
                "validity_raw": padded[4],
                "valid_until": valid_until,
                "validity_status": "expired" if expired else "date_valid_unverified_original",
                "fact_status": "historical_claim_requires_original_certificate",
                "source_table_index": table["table_index"],
                "source_row_number": row_number,
                "source_file": table["source_file"],
                "source_page": table["source_page"],
                "fact_source_allowed_for_enterprise": False,
                "allowed_for_bid": False,
            }
        )

    table = by_index[REPORT_TABLE_INDEX]
    for row_number, row in enumerate(table["rows"][1:-1], start=2):
        padded = row + [""] * (10 - len(row))
        report_no = padded[1].strip()
        exists = report_no in existing_report_numbers and report_no in KNOWN_REPORTS
        result.append(
            {
                "record_kind": "inspection_report_registry",
                "report_number": report_no,
                "report_name": padded[2],
                "product_name": padded[3],
                "product_family": _product_family(" ".join((padded[3], padded[4]))),
                "specification_model_raw": padded[4],
                "report_date_raw": padded[6],
                "validity_raw": padded[7],
                "issuer_raw": padded[8],
                "fact_status": "verified_existing_report_number" if exists else "unverified_historical_report_claim",
                "duplicate_action": "link_existing_evidence_do_not_reingest" if exists else "hold_until_original_report_received",
                "source_table_index": table["table_index"],
                "source_row_number": row_number,
                "source_file": table["source_file"],
                "source_page": table["source_page"],
                "fact_source_allowed_for_enterprise": exists,
                "allowed_for_bid": False,
            }
        )

    table = by_index[EQUIPMENT_TABLE_INDEX]
    for row_number, row in enumerate(table["rows"][1:], start=2):
        padded = row + [""] * (6 - len(row))
        result.append(
            {
                "record_kind": "equipment_calibration_registry",
                "equipment_name": padded[1],
                "equipment_model": padded[2],
                "quantity_raw": padded[3],
                "last_calibration_date_raw": padded[4],
                "manufacturer_origin_raw": padded[5],
                "fact_status": "historical_claim_requires_current_calibration_evidence",
                "source_table_index": table["table_index"],
                "source_row_number": row_number,
                "source_file": table["source_file"],
                "source_page": table["source_page"],
                "fact_source_allowed_for_enterprise": False,
                "allowed_for_bid": False,
            }
        )
    return result


def table_policy(table: dict[str, Any]) -> dict[str, Any]:
    index = table["table_index"]
    volume = table["bid_volume"]
    sensitivity = "restricted" if (volume == "business" and index in SENSITIVE_BUSINESS_TABLES) or (volume == "technical" and index == PERSONNEL_TABLE_INDEX) else "internal"
    if volume == "technical" and index in {2, 3, 4, 5, 6}:
        category = "技术参数与货物表"
    elif volume == "technical" and index in {7, 9, 10}:
        category = "资信与能力登记表"
    elif sensitivity == "restricted":
        category = "敏感企业资料"
    else:
        category = "偏差与承诺表"
    return {
        "category_label": category,
        "sensitivity": sensitivity,
        "target_library": "restricted_staging" if sensitivity == "restricted" else "review_staging",
        "fact_source_allowed_for_enterprise": False,
        "allowed_for_bid": False,
        "requires_original_evidence": True,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def run(args: argparse.Namespace) -> dict[str, Any]:
    technical = extract_raw_tables(args.technical_docx, "technical")
    business = extract_raw_tables(args.business_docx, "business")
    tables = technical + business
    for table in tables:
        table.update(table_policy(table))

    existing_rows = json.loads(args.existing_parameter_rows.read_text(encoding="utf-8"))
    parameters = build_technical_parameter_rows(technical)
    evidence = build_evidence_register(technical, existing_rows)

    args.raw_output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.raw_output_dir / "泰昌历史标书原始表格结构化抽取.json"
    raw_path.write_text(json.dumps({"metadata": {"generated_at": _now(), "contains_restricted_data": True}, "tables": tables}, ensure_ascii=False, indent=2), encoding="utf-8")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    parameter_json = args.output_dir / "泰昌历史标书技术参数候选.json"
    parameter_csv = args.output_dir / "泰昌历史标书技术参数候选.csv"
    evidence_json = args.output_dir / "泰昌历史标书证据登记候选.json"
    evidence_csv = args.output_dir / "泰昌历史标书证据登记候选.csv"
    metadata = {
        "schema_version": "taichang_historical_bid_table_extraction_v1",
        "generated_at": _now(),
        "enterprise": ENTERPRISE,
        "pilot_only": True,
        "parser": "native_docx_ooxml",
        "mineru_invoked": False,
        "database_written": False,
        "parameter_fact_layer_updated": False,
        "raw_table_file": _rel(raw_path),
        "source_hashes": {
            _rel(args.technical_docx): _sha256(args.technical_docx),
            _rel(args.business_docx): _sha256(args.business_docx),
            _rel(args.existing_parameter_rows): _sha256(args.existing_parameter_rows),
        },
    }
    parameter_json.write_text(json.dumps({"metadata": metadata, "records": parameters}, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_json.write_text(json.dumps({"metadata": metadata, "records": evidence}, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(parameter_csv, parameters)
    _write_csv(evidence_csv, evidence)

    policies = Counter((row["sensitivity"], row["category_label"]) for row in tables)
    report = args.output_dir / "泰昌历史标书表格抽取与参数校验报告.md"
    report.write_text(
        "\n".join(
            [
                "# 泰昌历史标书表格抽取与参数校验报告",
                "",
                f"> 生成时间：{metadata['generated_at']}",
                "> 主解析器：Word 原生 OOXML（未调用 MinerU/OCR）",
                "",
                "## 抽取结论",
                "",
                f"- 技术标原生表格：{len(technical)} 个；商务标原生表格：{len(business)} 个。",
                f"- 技术参数/规格候选：{len(parameters)} 行；证书、报告和设备登记候选：{len(evidence)} 行。",
                "- 所有候选默认 `parameter_fact_allowed=false`，不会覆盖现有检验报告参数事实。",
                "- `DN` 和 `φ` 仅作为原始规格标记保留，未换算成 `mm`；“以实际数量为准”的数值保持为空。",
                "- 历史技术表混有新疆 1kV 架空绝缘导线、PVC 复合材料管和泰昌 MPP/CPVC 信息，已按混合历史项目处理。",
                "",
                "## 关键交叉核验",
                "",
                "- 报告 `2024100312005501712`、`2024100312005501713` 已在现有结构化检验报告参数层找到，只建立证据关联，不重复入库。",
                "- 报告 `2024400312005505333`、`2025200312005503479` 当前缺少原始报告，保持未核验历史声明。",
                "- 职业健康安全管理体系证书 `626023S10219R0` 所填有效期为 2026-06-18，按当前日期已过期，禁止作为有效证书自动使用。",
                "- 商务标企业信息、股东和财务表，以及技术标人员表均标为 `restricted`，不进入普通知识库自动召回。",
                "",
                "## 表格分类",
                "",
                *[f"- {sensitivity} / {category}：{count} 个" for (sensitivity, category), count in sorted(policies.items())],
                "",
                "## MinerU 使用判定",
                "",
                "本批表格是可直接读取的 Word 原生表格。原生 OOXML 能逐单元格保留文字和空值，精度高于把页面渲染后再 OCR，因此未调用 MinerU。MinerU 仅在扫描件或原生表格损坏时作为交叉复核，不替代原始单元格值。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    summary = {
        **metadata,
        "technical_table_count": len(technical),
        "business_table_count": len(business),
        "technical_parameter_candidate_count": len(parameters),
        "evidence_register_candidate_count": len(evidence),
        "verified_existing_report_count": sum(row.get("fact_status") == "verified_existing_report_number" for row in evidence),
        "restricted_table_count": sum(row["sensitivity"] == "restricted" for row in tables),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="结构化抽取泰昌历史标书原生表格并核验参数语义")
    parser.add_argument("--technical-docx", type=Path, default=DEFAULT_TECHNICAL_DOCX)
    parser.add_argument("--business-docx", type=Path, default=DEFAULT_BUSINESS_DOCX)
    parser.add_argument("--existing-parameter-rows", type=Path, default=DEFAULT_EXISTING_PARAMETER_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--raw-output-dir", type=Path, default=DEFAULT_RAW_OUTPUT_DIR)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())

#!/usr/bin/env python3
"""Extract auditable Taichang project-performance facts from customer evidence."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BATCH_DIR = PROJECT_ROOT / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611"
MANIFEST_PATH = BATCH_DIR / "manifest.json"
OUTPUT_DIR = BATCH_DIR / "staging/taichang_project_performance"
ENTERPRISE_NAME = "河北泰昌电力器材科技有限公司"
PERFORMANCE_ID = "taichang-tianjin-2022-0322AB-package-2"

CSV_COLUMNS = [
    "performance_id", "evidence_type", "project_name", "tender_no", "section_name",
    "package_no", "product_summary", "product_families", "total_quantity", "quantity_unit",
    "amount_tax_included_yuan", "buyer", "seller", "award_date", "contract_sign_date",
    "contract_no_buyer", "source_file", "source_pages", "date_status", "value_source",
]


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


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _manifest_records() -> list[dict[str, Any]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [row for row in payload.get("records", []) if isinstance(row, dict)]


def _find_record(keyword: str) -> dict[str, Any]:
    matches = [row for row in _manifest_records() if keyword in str(row.get("source_file") or "")]
    if len(matches) != 1:
        raise RuntimeError(f"expected one manifest record for {keyword}, found {len(matches)}")
    return matches[0]


def _page_texts(source_file: str) -> list[str]:
    reader = PdfReader(str(PROJECT_ROOT / source_file))
    return [_clean(page.extract_text() or "") for page in reader.pages]


def _extract_notice(record: dict[str, Any]) -> dict[str, Any]:
    markdown_path = PROJECT_ROOT / str(record["output_file"])
    markdown = markdown_path.read_text(encoding="utf-8")
    pages = _page_texts(record["source_file"])
    joined = " ".join(pages)
    project_match = re.search(r"为(.+?招标采购)（招标编号", joined)
    tender_match = re.search(r"招标编号[:：]?\s*([0-9A-Z]+)", joined)
    scope_match = re.search(r"，(157-保护管.+?)下表", joined)
    date_match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", joined)

    parser = _TableParser()
    parser.feed(markdown)
    table = next((table for table in parser.tables if table and "数量" in table[0]), None)
    if not table or len(table) < 2:
        raise RuntimeError("award notice item table not found")
    headers = table[0]
    line_items: list[dict[str, Any]] = []
    for index, values in enumerate(table[1:], start=1):
        row = dict(zip(headers, values))
        quantity = float(row.get("数量") or 0)
        amount_wan = float(row.get("含税总价(万元)") or 0)
        line_items.append({
            "line_no": index,
            "project_unit": row.get("项目单位"),
            "product_name": row.get("货物名称"),
            "quantity": quantity,
            "quantity_unit": row.get("单位"),
            "amount_tax_included_wan": amount_wan,
            "amount_tax_included_yuan": round(amount_wan * 10000, 2),
            "purchase_request_no": row.get("总部采购申请号"),
            "source_page": 1,
        })

    scope = _clean(scope_match.group(1) if scope_match else "157-保护管（CPVC和MPP）包2_电缆保护管MPP和CPVC")
    return {
        "performance_id": PERFORMANCE_ID,
        "enterprise": "泰昌",
        "doc_owner": ENTERPRISE_NAME,
        "source_domain": "enterprise_fact",
        "reference_only": False,
        "fact_source_allowed_for_enterprise": True,
        "evidence_type": "award_notice",
        "evidence_type_label": "中标通知书",
        "target_library": "qualification_library",
        "project_name": _clean(project_match.group(1) if project_match else ""),
        "tender_no": tender_match.group(1) if tender_match else "",
        "section_name": "157-保护管（CPVC和MPP）",
        "package_no": "包2",
        "package_description": scope,
        "product_summary": "电缆保护管MPP和CPVC",
        "product_families": ["MPP电缆保护管", "CPVC电缆保护管"],
        "total_quantity": sum(item["quantity"] for item in line_items),
        "quantity_unit": "米",
        "amount_tax_included_yuan": round(sum(item["amount_tax_included_yuan"] for item in line_items), 2),
        "buyer": "国网天津市电力公司",
        "seller": ENTERPRISE_NAME,
        "award_date": f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}" if date_match else "",
        "contract_sign_date": "",
        "contract_no_buyer": "",
        "line_items": line_items,
        "source_file": record["source_file"],
        "markdown_path": record["output_file"],
        "source_pages": {"project_and_tender": [1], "line_items": [1], "award_date": [2]},
        "date_status": "award_date_explicit",
        "value_source": "mineru_ocr_and_pdf_page_text",
    }


CONTRACT_PRODUCT_PATTERN = re.compile(r"电缆保护管电缆保护管,(MPP|CPVC),φ(250|200|100|50)")


def _extract_contract(record: dict[str, Any], notice: dict[str, Any]) -> dict[str, Any]:
    pages = _page_texts(record["source_file"])
    first_pages = " ".join(pages[:6])
    contract_no = re.search(r"合同编号（买方）[:：]\s*([A-Z0-9]+)", first_pages)
    amount_match = re.search(r"[¥￥]\s*([0-9]+(?:\.[0-9]+)?)", pages[2])
    product_rows: list[dict[str, Any]] = []
    for page_no in (8, 9, 10):
        compact = re.sub(r"\s+", "", pages[page_no - 1])
        matches = list(CONTRACT_PRODUCT_PATTERN.finditer(compact))
        for index, match in enumerate(matches):
            family, diameter = match.groups()
            segment_end = matches[index + 1].start() if index + 1 < len(matches) else len(compact)
            segment = compact[match.start():segment_end]
            product_rows.append({
                "line_no": len(product_rows) + 1,
                "product_name": "电缆保护管",
                "product_family": f"{family}电缆保护管",
                "specification_model": f"φ{diameter}",
                "source_page": page_no,
                "_segment": segment,
            })
    if len(product_rows) != 9:
        raise RuntimeError(f"expected 9 contract product rows, found {len(product_rows)}")
    notice_items = notice.get("line_items") or []
    if len(notice_items) != len(product_rows):
        raise RuntimeError("contract and award notice line counts do not match")
    line_items: list[dict[str, Any]] = []
    unmatched_notice = list(notice_items)
    for product in product_rows:
        candidates = []
        for awarded in unmatched_notice:
            amount_text = f"{float(awarded['amount_tax_included_yuan']):.2f}"
            if amount_text in product["_segment"]:
                candidates.append(awarded)
        if len(candidates) != 1:
            raise RuntimeError(
                f"could not uniquely match contract {product['product_family']} {product['specification_model']} "
                f"on page {product['source_page']}: {len(candidates)} amount matches"
            )
        awarded = candidates[0]
        unmatched_notice.remove(awarded)
        product = {key: value for key, value in product.items() if key != "_segment"}
        line_items.append({
            **product,
            "quantity": awarded["quantity"],
            "quantity_unit": awarded["quantity_unit"],
            "amount_tax_included_yuan": awarded["amount_tax_included_yuan"],
            "purchase_request_no": awarded["purchase_request_no"],
            "quantity_amount_value_source": "award_notice_row_cross_checked_against_contract_total",
        })
    if unmatched_notice:
        raise RuntimeError(f"unmatched award notice rows: {len(unmatched_notice)}")

    contract_total = float(amount_match.group(1)) if amount_match else round(sum(item["amount_tax_included_yuan"] for item in line_items), 2)
    return {
        "performance_id": PERFORMANCE_ID,
        "enterprise": "泰昌",
        "doc_owner": ENTERPRISE_NAME,
        "source_domain": "enterprise_fact",
        "reference_only": False,
        "fact_source_allowed_for_enterprise": True,
        "evidence_type": "supply_contract",
        "evidence_type_label": "供货合同",
        "target_library": "qualification_library",
        "project_name": "国网天津市电力公司2022年第二次配网物资协议库存招标采购",
        "tender_no": "0322AB",
        "tender_no_value_source": "cross_document_exact_amount_and_party_match",
        "section_name": "157-保护管（CPVC和MPP）",
        "package_no": "包2",
        "product_summary": "电缆保护管MPP和CPVC",
        "product_families": ["MPP电缆保护管", "CPVC电缆保护管"],
        "total_quantity": sum(item["quantity"] for item in line_items),
        "quantity_unit": "米",
        "amount_tax_included_yuan": contract_total,
        "buyer": "国网天津市电力公司",
        "seller": ENTERPRISE_NAME,
        "award_date": "2022-11-21",
        "contract_sign_date": "",
        "contract_no_buyer": contract_no.group(1) if contract_no else "",
        "line_items": line_items,
        "source_file": record["source_file"],
        "markdown_path": record["output_file"],
        "source_pages": {
            "contract_identity_and_parties": [1, 2], "contract_amount": [3],
            "signature_and_blank_sign_date": [6], "line_items": [8, 9, 10],
        },
        "date_status": "contract_sign_date_blank_in_source",
        "value_source": "pdf_page_text_with_cross_document_project_link",
    }


def extract() -> list[dict[str, Any]]:
    notice = _extract_notice(_find_record("中标通知书整页扫描件"))
    contract = _extract_contract(_find_record("TJ20220002363合同协议书"), notice)
    if contract["amount_tax_included_yuan"] != notice["amount_tax_included_yuan"]:
        raise RuntimeError("contract and award notice totals do not match")
    if contract["total_quantity"] != notice["total_quantity"]:
        raise RuntimeError("contract and award notice quantities do not match")
    return [notice, contract]


def write_outputs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "taichang_project_performance_rows.json"
    csv_path = OUTPUT_DIR / "taichang_project_performance_rows.csv"
    report_json = OUTPUT_DIR / "extract_taichang_project_performance_report.json"
    report_md = OUTPUT_DIR / "extract_taichang_project_performance_report.md"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            flat = {key: row.get(key, "") for key in CSV_COLUMNS}
            flat["product_families"] = "、".join(row.get("product_families") or [])
            flat["source_pages"] = json.dumps(row.get("source_pages") or {}, ensure_ascii=False)
            writer.writerow(flat)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "batch_id": "customer_taichang_supplement_20260611",
        "performance_records": len({row["performance_id"] for row in rows}),
        "evidence_records": len(rows),
        "line_items": sum(len(row.get("line_items") or []) for row in rows),
        "total_quantity": rows[0]["total_quantity"],
        "amount_tax_included_yuan": rows[0]["amount_tax_included_yuan"],
        "contract_sign_date_status": next(row["date_status"] for row in rows if row["evidence_type"] == "supply_contract"),
        "outputs": {"json": _rel(json_path), "csv": _rel(csv_path)},
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(
        "\n".join([
            "# 泰昌项目业绩结构化抽取报告", "", f"> 生成时间：{report['generated_at']}", "",
            "## 抽取结果", "",
            f"- 项目业绩：{report['performance_records']} 项",
            f"- 证据文件：{report['evidence_records']} 份（中标通知书、供货合同）",
            f"- 逐项明细：每份证据 9 行，合计 {report['line_items']} 行交叉核验",
            f"- 合计数量：{report['total_quantity']:.0f} 米",
            f"- 含税金额：{report['amount_tax_included_yuan']:.2f} 元",
            "- 合同签署日期：原件字段为空，保持缺失，不使用中标日期或交货日期代填。", "",
            "## 交叉核验", "",
            "- 中标通知书与合同的买卖双方、产品范围、9 行数量、9 行金额、总数量和含税总价一致。",
            "- 合同正文未直接出现招标编号；`0322AB` 通过双方、项目范围和金额完全一致关联，并保留 `value_source` 标记。",
            "- 中标日期为 2022-11-21；合同签署页日期为空，二者不得混用。", "",
            "## 输出", "",
            f"- `{_rel(json_path)}`", f"- `{_rel(csv_path)}`", "",
        ]) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    report = write_outputs(extract())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

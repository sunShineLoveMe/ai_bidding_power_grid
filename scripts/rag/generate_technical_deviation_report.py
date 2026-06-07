#!/usr/bin/env python3
"""Generate technical deviation decisions from extracted parameter rows."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_COLUMNS = [
    "ingestion_batch_id",
    "province",
    "batch_no",
    "package_no",
    "package_code",
    "material_category",
    "source_file",
    "table_index",
    "row_number",
    "table_type",
    "parameter_name",
    "required_value",
    "response_value",
    "deviation_status",
    "risk_level",
    "decision_reason",
    "suggested_action",
    "row_data",
]

COMPLIANCE_TERMS = {"满足", "响应", "符合", "无偏差", "完全响应", "按招标文件执行", "参照通用部分"}
MISSING_RESPONSE_STATUSES = {"pending_response", "missing_response"}


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def _required_value(row: dict[str, Any]) -> str:
    row_data = row.get("row_data") if isinstance(row.get("row_data"), dict) else {}
    if row.get("table_type") == "dimension_parameter_table" and row_data:
        parts: list[str] = []
        for key, value in row_data.items():
            cleaned_key = _clean(key)
            cleaned_value = _clean(value)
            if not cleaned_key or not cleaned_value:
                continue
            if cleaned_key in {"序号", "公称内径", "公称内径 （mm）", "公称内径 DN/ID"}:
                continue
            parts.append(f"{cleaned_key}: {cleaned_value}")
        if parts:
            return "；".join(parts)
    candidates = [
        row.get("project_required_value"),
        row.get("standard_value"),
        row.get("minimum_wall_thickness"),
        row.get("nominal_wall_thickness"),
        row.get("nominal_inner_diameter"),
    ]
    for value in candidates:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    for key, value in row_data.items():
        if any(token in str(key) for token in ["项目需求值", "指标", "要求", "最小壁厚", "公称壁厚", "公称内径"]):
            cleaned = _clean(value)
            if cleaned:
                return cleaned
    return ""


def _response_value(row: dict[str, Any]) -> str:
    for key in ["bidder_response_value", "bidder_guaranteed_value"]:
        cleaned = _clean(row.get(key))
        if cleaned:
            return cleaned
    deviation = _clean(row.get("deviation"))
    if deviation and deviation in {"无偏差", "正偏差"}:
        return deviation
    return ""


def _decimal_from_text(value: str) -> Decimal | None:
    text = value.replace("φ", "").replace("Φ", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def _numeric_rule(value: str) -> tuple[str, Decimal] | None:
    normalized = value.replace(" ", "")
    number = _decimal_from_text(normalized)
    if number is None:
        return None
    if any(token in normalized for token in ["≥", ">=", "不低于", "大于等于", "不少于"]):
        return "min", number
    if any(token in normalized for token in ["≤", "<=", "不高于", "小于等于", "不超过"]):
        return "max", number
    if "~" in normalized or "～" in normalized:
        numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", normalized)
        if len(numbers) >= 2:
            return "range", Decimal(numbers[0])  # caller handles range through _range_values
    return "equal", number


def _range_values(value: str) -> tuple[Decimal, Decimal] | None:
    normalized = value.replace(" ", "")
    if "~" not in normalized and "～" not in normalized:
        return None
    numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", normalized)
    if len(numbers) < 2:
        return None
    try:
        return Decimal(numbers[0]), Decimal(numbers[1])
    except InvalidOperation:
        return None


def judge_deviation(required: str, response: str) -> dict[str, str]:
    required = _clean(required)
    response = _clean(response)
    if not required:
        return {
            "deviation_status": "informational",
            "risk_level": "low",
            "decision_reason": "未识别到明确项目需求值或标准值，仅作为参数信息保留。",
            "suggested_action": "无需生成偏差判断，可在参数查询中展示。",
        }
    if not response:
        return {
            "deviation_status": "pending_response",
            "risk_level": "medium",
            "decision_reason": "存在项目需求值或标准值，但投标人响应值/保证值为空。",
            "suggested_action": "补充泰昌响应值、保证值或明确写入无偏差承诺后复核。",
        }
    if any(term in response for term in COMPLIANCE_TERMS):
        return {
            "deviation_status": "no_deviation",
            "risk_level": "low",
            "decision_reason": "响应值包含满足/响应/无偏差等明确表述。",
            "suggested_action": "可写入技术偏差表为无偏差，正式投标前仍需人工抽查。",
        }

    required_range = _range_values(required)
    response_number = _decimal_from_text(response)
    if required_range and response_number is not None:
        low, high = required_range
        if low <= response_number <= high:
            return {
                "deviation_status": "no_deviation",
                "risk_level": "low",
                "decision_reason": f"响应数值 {response_number} 位于要求范围 {low}~{high} 内。",
                "suggested_action": "可按无偏差处理。",
            }
        return {
            "deviation_status": "negative_deviation",
            "risk_level": "high",
            "decision_reason": f"响应数值 {response_number} 不在要求范围 {low}~{high} 内。",
            "suggested_action": "不得直接写无偏差，需更换响应值或人工确认。",
        }

    rule = _numeric_rule(required)
    if rule and response_number is not None:
        operator, required_number = rule
        if operator == "min":
            if response_number >= required_number:
                status = "positive_deviation" if response_number > required_number else "no_deviation"
                return {
                    "deviation_status": status,
                    "risk_level": "low",
                    "decision_reason": f"响应数值 {response_number} 不低于要求 {required_number}。",
                    "suggested_action": "可按满足要求处理。",
                }
            return {
                "deviation_status": "negative_deviation",
                "risk_level": "high",
                "decision_reason": f"响应数值 {response_number} 低于要求 {required_number}。",
                "suggested_action": "需补充符合要求的保证值或标记为负偏差风险。",
            }
        if operator == "max":
            if response_number <= required_number:
                status = "positive_deviation" if response_number < required_number else "no_deviation"
                return {
                    "deviation_status": status,
                    "risk_level": "low",
                    "decision_reason": f"响应数值 {response_number} 不高于要求 {required_number}。",
                    "suggested_action": "可按满足要求处理。",
                }
            return {
                "deviation_status": "negative_deviation",
                "risk_level": "high",
                "decision_reason": f"响应数值 {response_number} 高于上限要求 {required_number}。",
                "suggested_action": "需补充符合要求的保证值或标记为负偏差风险。",
            }
        if operator == "equal":
            if response_number == required_number:
                return {
                    "deviation_status": "no_deviation",
                    "risk_level": "low",
                    "decision_reason": f"响应数值 {response_number} 与要求 {required_number} 一致。",
                    "suggested_action": "可按无偏差处理。",
                }
            return {
                "deviation_status": "manual_review",
                "risk_level": "medium",
                "decision_reason": f"要求与响应均为数值但不完全一致：要求 {required_number}，响应 {response_number}。",
                "suggested_action": "需结合参数性质判断正偏差或负偏差。",
            }

    if required == response:
        return {
            "deviation_status": "no_deviation",
            "risk_level": "low",
            "decision_reason": "响应文本与项目需求值一致。",
            "suggested_action": "可按无偏差处理。",
        }
    return {
        "deviation_status": "manual_review",
        "risk_level": "medium",
        "decision_reason": "要求和响应无法用当前规则自动比较。",
        "suggested_action": "需人工复核该参数，确认是否为无偏差、正偏差或负偏差。",
    }


def build_deviation_rows(parameter_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in parameter_rows:
        required = _required_value(row)
        response = _response_value(row)
        decision = judge_deviation(required, response)
        rows.append(
            {
                **{column: "" for column in OUTPUT_COLUMNS},
                "ingestion_batch_id": row.get("ingestion_batch_id"),
                "province": row.get("province"),
                "batch_no": row.get("batch_no"),
                "package_no": row.get("package_no"),
                "package_code": row.get("package_code"),
                "material_category": row.get("material_category"),
                "source_file": row.get("source_file"),
                "table_index": row.get("table_index"),
                "row_number": row.get("row_number"),
                "table_type": row.get("table_type"),
                "parameter_name": row.get("parameter_name") or row.get("nominal_inner_diameter"),
                "required_value": required,
                "response_value": response,
                "row_data": row.get("row_data") or {},
                **decision,
            }
        )
    return rows


def _write_outputs(rows: list[dict[str, Any]], out_dir: Path, batch_id: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "technical_deviation_rows.json"
    csv_path = out_dir / "technical_deviation_rows.csv"
    summary_path = out_dir / "technical_deviation_summary.md"
    report_path = out_dir / "technical_deviation_report.json"

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            csv_row["row_data"] = json.dumps(row.get("row_data") or {}, ensure_ascii=False)
            writer.writerow({column: csv_row.get(column, "") for column in OUTPUT_COLUMNS})

    by_status = Counter(str(row.get("deviation_status")) for row in rows)
    by_risk = Counter(str(row.get("risk_level")) for row in rows)
    actionable = [row for row in rows if row.get("deviation_status") in MISSING_RESPONSE_STATUSES or row.get("risk_level") in {"high", "medium"}]
    report = {
        "batch_id": batch_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rows": len(rows),
        "by_status": dict(by_status),
        "by_risk": dict(by_risk),
        "actionable_rows": len(actionable),
        "outputs": {
            "json": _rel(json_path),
            "csv": _rel(csv_path),
            "summary": _rel(summary_path),
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 技术偏差辅助判断摘要",
        "",
        f"> 批次：`{batch_id}`",
        f"> 生成时间：{report['generated_at']}",
        "",
        "## 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 参数行 | {len(rows)} |",
        f"| 需处理行 | {len(actionable)} |",
        "",
        "## 按偏差状态",
        "",
        "| 状态 | 数量 |",
        "| --- | ---: |",
    ]
    for status, count in by_status.most_common():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(["", "## 按风险等级", "", "| 风险等级 | 数量 |", "| --- | ---: |"])
    for risk, count in by_risk.most_common():
        lines.append(f"| `{risk}` | {count} |")
    lines.extend(["", "## 需处理样例", "", "| 物料 | 包号 | 参数 | 要求 | 响应 | 状态 | 建议 |", "| --- | --- | --- | --- | --- | --- | --- |"])
    for row in actionable[:30]:
        lines.append(
            f"| {row.get('material_category') or '-'} | {row.get('package_no') or '-'} | "
            f"{row.get('parameter_name') or '-'} | {row.get('required_value') or '-'} | "
            f"{row.get('response_value') or '-'} | `{row.get('deviation_status')}` | {row.get('suggested_action') or '-'} |"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "summary": summary_path, "report": report_path}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("parameter_rows", type=Path)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()

    input_path = args.parameter_rows.resolve()
    parameter_rows = json.loads(input_path.read_text(encoding="utf-8"))
    batch_id = parameter_rows[0].get("ingestion_batch_id") if parameter_rows else input_path.parent.name
    out_dir = (args.out_dir or input_path.parent / "technical_deviations").resolve()
    rows = build_deviation_rows(parameter_rows)
    paths = _write_outputs(rows, out_dir, str(batch_id))
    print(f"rows={len(rows)} actionable={sum(1 for row in rows if row.get('deviation_status') in MISSING_RESPONSE_STATUSES or row.get('risk_level') in {'high','medium'})}")
    for name, path in paths.items():
        print(f"{name}={_rel(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

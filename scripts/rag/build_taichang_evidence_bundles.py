#!/usr/bin/env python3
"""构建泰昌 P1-02 文件级证据包清单。

脚本只读取 P0-02 数字资产基线和本地原始文件，不写数据库。它把同一业务证据的
完整 PDF、重复 PDF、关键页图片和结构化摘要归并到稳定 evidence_bundle_id 下，
并审计原页序、缺页、重页及正式投标使用门禁。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image
from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = PROJECT_ROOT / "docs/development/taichang-bid-v1-data/current_asset_baseline.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs/development/taichang-bid-v1-data/p1_02_evidence_bundles"
PARAMETER_ROWS = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/"
    "staging/taichang_product_parameters/taichang_product_parameter_rows.json"
)
PERFORMANCE_ROWS = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/"
    "staging/taichang_project_performance/taichang_project_performance_rows.json"
)
P0_06_REVIEW_MANIFEST = (
    PROJECT_ROOT
    / "docs/development/taichang-bid-v1-data/p0_06_review/p0_06_review_manifest.json"
)

FULL_NAME = "河北泰昌电力器材科技有限公司"
SHORT_NAME = "泰昌"
P0_06_SOURCE_PREFIX = "assets/template_words/"


@dataclass(frozen=True)
class BundleMatch:
    kind: str
    business_key: str
    title: str
    evidence_type: str
    target_library: str
    applicable_sections: tuple[str, ...]
    product_families: tuple[str, ...] = ()
    component: str = "primary"
    rendition_only: bool = False


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _stable_id(kind: str, business_key: str) -> str:
    digest = hashlib.sha256(f"{SHORT_NAME}|{kind}|{business_key}".encode("utf-8")).hexdigest()[:20]
    return f"taichang-evidence-{digest}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _local_path(source_file: str) -> Path:
    path = Path(source_file)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _page_count(path: Path) -> int:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return len(PdfReader(str(path)).pages)
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
        with Image.open(path) as image:
            return int(getattr(image, "n_frames", 1) or 1)
    return 0


def _equipment_name(source_file: str) -> str:
    parent = Path(source_file).parent.name
    name = re.sub(r"^\d+[.、]?", "", parent).strip() or Path(source_file).stem
    return {
        "溶体流动速率仪": "熔体流动速率仪",
        "热变型、维卡软化点温度测定仪": "热变形、维卡软化点温度测定仪",
    }.get(name, name)


def classify_source(source_file: str, evidence_type: str) -> BundleMatch | None:
    """把 P0 范围内的泰昌原始文件映射到业务证据；其余资料不自动扩围。"""
    name = Path(source_file).name
    suffix = Path(source_file).suffix.lower()

    if evidence_type == "inspection_report" and "CPVC" in name:
        return BundleMatch(
            "inspection_report", "report:2024100312005501713", "泰昌CPVC电缆保护管检验报告",
            "inspection_report", "product_library", ("技术标/技术响应", "商务标/资格证明"),
            ("CPVC电缆保护管",), rendition_only=suffix != ".pdf",
        )
    if evidence_type == "inspection_report" and "MPP" in name:
        return BundleMatch(
            "inspection_report", "report:2024100312005501712", "泰昌MPP电缆保护管检验报告",
            "inspection_report", "product_library", ("技术标/技术响应", "商务标/资格证明"),
            ("MPP电缆保护管",), rendition_only=suffix != ".pdf",
        )

    if evidence_type == "testing_capacity" and suffix == ".pdf" and "试验检测设备一览表" in source_file:
        equipment = _equipment_name(source_file)
        return BundleMatch(
            "calibration_certificate", f"equipment:{equipment}", f"泰昌{equipment}试验设备及校准资料",
            "calibration_certificate", "product_library", ("技术标/试验检测能力", "商务标/补充证明"),
            component=equipment,
        )

    systems = {
        "质量管理体系认证证书": "quality",
        "环境管理体系认证证书": "environment",
        "职业健康安全管理体系认证证书": "ohs",
    }
    if evidence_type == "certification":
        for label, code in systems.items():
            if label in name:
                return BundleMatch(
                    "management_system_certificate", f"management-system:{code}", f"泰昌{label}",
                    "certification", "qualification_library", ("商务标/管理体系认证", "技术标/质量管理"),
                )

    if evidence_type == "business_license" and "营业执照" in name:
        return BundleMatch(
            "business_license", "uscc:91130607056539515C", "泰昌营业执照",
            "business_license", "qualification_library", ("商务标/投标人基本情况", "商务标/资格证明"),
            rendition_only=suffix != ".pdf",
        )

    audit_match = re.search(r"(20\d{2})年审计报告", name)
    if evidence_type == "finance" and audit_match:
        year = audit_match.group(1)
        return BundleMatch(
            "audit_report", f"audit-year:{year}", f"泰昌{year}年审计报告",
            "finance", "qualification_library", ("商务标/财务状况",),
            component=year, rendition_only=suffix != ".pdf",
        )

    if evidence_type == "project_performance" and suffix == ".pdf":
        if "合同协议书" in name:
            return BundleMatch(
                "project_performance", "project:taichang-tianjin-2022-0322AB-package-2",
                "泰昌国网天津2022年电缆保护管项目业绩", "project_performance",
                "qualification_library", ("商务标/项目业绩", "技术标/供货业绩"),
                ("CPVC电缆保护管", "MPP电缆保护管"), component="供货合同",
            )
        if "中标通知书" in name:
            return BundleMatch(
                "project_performance", "project:taichang-tianjin-2022-0322AB-package-2",
                "泰昌国网天津2022年电缆保护管项目业绩", "project_performance",
                "qualification_library", ("商务标/项目业绩", "技术标/供货业绩"),
                ("CPVC电缆保护管", "MPP电缆保护管"), component="中标通知书",
            )
    return None


def _source_priority(source: dict[str, Any]) -> tuple[int, int, int, int, str]:
    path = source["source_file"]
    return (
        0 if "01_泰昌MVP试点企业资料" in path else 1,
        0 if Path(path).suffix.lower() == ".pdf" else 1,
        0 if not source["match"].rendition_only else 1,
        -len(source.get("asset_page_numbers") or []),
        path,
    )


def _page_audit(source: dict[str, Any]) -> dict[str, Any]:
    path = _local_path(source["source_file"])
    expected = _page_count(path) if path.is_file() else 0
    pages = [int(value) for value in source.get("asset_page_numbers", []) if _text(value).isdigit()]
    counts = Counter(pages)
    unique_pages = sorted(counts)
    expected_pages = list(range(1, expected + 1))
    missing = [page for page in expected_pages if page not in counts]
    duplicate = [page for page, count in sorted(counts.items()) if count > 1]
    page_order_valid = pages == sorted(pages)
    return {
        "original_file_exists": path.is_file(),
        "expected_page_count": expected,
        "asset_page_count": len(pages),
        "asset_unique_page_count": len(unique_pages),
        "asset_page_sequence": unique_pages,
        "missing_pages": missing,
        "duplicate_pages": duplicate,
        "page_order_valid": page_order_valid,
        "complete": bool(
            path.is_file()
            and expected
            and unique_pages == expected_pages
            and not duplicate
            and page_order_valid
        ),
    }


def _select_primary_sources(sources: list[dict[str, Any]], kind: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if kind == "project_performance":
        primary: list[dict[str, Any]] = []
        renditions: list[dict[str, Any]] = []
        component_order = {"中标通知书": 0, "供货合同": 1}
        for component in sorted({item["match"].component for item in sources}, key=lambda item: component_order.get(item, 9)):
            candidates = [item for item in sources if item["match"].component == component]
            candidates.sort(key=_source_priority)
            primary.append(candidates[0])
            renditions.extend(candidates[1:])
        return primary, renditions
    candidates = sorted(sources, key=_source_priority)
    primary = next((item for item in candidates if not item["match"].rendition_only), candidates[0])
    return [primary], [item for item in candidates if item is not primary]


def _structured_summary(match: BundleMatch, parameter_rows: list[dict[str, Any]], performance_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if match.kind == "inspection_report":
        report_no = match.business_key.split(":", 1)[1]
        rows = [row for row in parameter_rows if _text(row.get("report_no")) == report_no]
        products = sorted({_text(row.get("product_family") or row.get("sample_name")) for row in rows if row.get("product_family") or row.get("sample_name")})
        specs = sorted({_text(row.get("specification_model")) for row in rows if row.get("specification_model")})
        return {"report_no": report_no, "parameter_row_count": len(rows), "products": products, "spec_models": specs}
    if match.kind == "project_performance":
        rows = [row for row in performance_rows if _text(row.get("performance_id")) == "taichang-tianjin-2022-0322AB-package-2"]
        base = rows[0] if rows else {}
        return {
            "project_name": base.get("project_name") or "国网天津市电力公司2022年第二次配网物资协议库存招标采购",
            "tender_no": base.get("tender_no") or "0322AB",
            "package_no": base.get("package_no") or "包2",
            "quantity_m": base.get("total_quantity") or 54678,
            "amount_yuan": base.get("amount_tax_included_yuan") or 6372409.05,
            "structured_evidence_count": len(rows),
        }
    if match.kind == "audit_report":
        return {"audit_year": match.component, "selection_policy": "仅当本次招标文件要求该年度时选用"}
    if match.kind == "business_license":
        return {"unified_social_credit_code": "91130607056539515C", "enterprise_name": FULL_NAME}
    if match.kind == "calibration_certificate":
        return {"equipment_name": match.component, "validity_policy": "正式投标前核验校准证书有效期"}
    if match.business_key.endswith(":ohs"):
        return {"validity_status": "expired", "valid_until": "2026-06-18", "replacement_required": True}
    return {}


def _usage_gate(match: BundleMatch, source_complete: bool) -> tuple[bool, str, list[str]]:
    warnings: list[str] = []
    if not source_complete:
        return False, "blocked_incomplete_pages", ["原始文件页数与整页资产页序不一致"]
    if match.business_key.endswith(":ohs"):
        return False, "blocked_expired", ["职业健康安全管理体系证书已于2026-06-18到期，须补充有效证书"]
    if match.kind == "calibration_certificate":
        return False, "review_required_validity", ["校准/检定有效期尚未结构化，正式投标前必须复核"]
    if match.kind == "audit_report":
        return False, "conditional_tender_year", ["须按本次招标文件要求的审计年度选择，不得默认全部插入"]
    if match.kind == "management_system_certificate":
        return False, "review_required_validity", ["证书有效期尚未进入结构化台账，正式投标前必须复核"]
    return True, "eligible_from_existing_asset_policy", warnings


def build_bundles(baseline: dict[str, Any]) -> dict[str, Any]:
    parameter_rows_payload = _load_json(PARAMETER_ROWS, {})
    parameter_rows = (
        parameter_rows_payload
        if isinstance(parameter_rows_payload, list)
        else parameter_rows_payload.get("rows", [])
    )
    performance_payload = _load_json(PERFORMANCE_ROWS, {})
    performance_rows = (
        performance_payload
        if isinstance(performance_payload, list)
        else performance_payload.get("rows", [])
    )
    p0_06_manifest = _load_json(P0_06_REVIEW_MANIFEST, {})
    p0_06_metadata = p0_06_manifest.get("metadata", {}) if isinstance(p0_06_manifest, dict) else {}

    asset_records = [
        row for row in baseline.get("records", [])
        if row.get("record_type") == "knowledge_asset"
        and row.get("source_domain") == "enterprise_fact"
        and row.get("enterprise") in {SHORT_NAME, FULL_NAME}
        and not _text(row.get("source_file")).startswith(P0_06_SOURCE_PREFIX)
    ]
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in asset_records:
        by_source[_text(row.get("source_file"))].append(row)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    excluded_count = 0
    for source_file, rows in by_source.items():
        match = classify_source(source_file, _text(rows[0].get("evidence_type")))
        if not match:
            excluded_count += 1
            continue
        grouped[(match.kind, match.business_key)].append({
            "source_file": source_file,
            "source_sha256": _text(rows[0].get("source_sha256")),
            "asset_ids": [row.get("asset_id") for row in rows if row.get("asset_id")],
            "asset_page_numbers": [row.get("page_no") for row in rows if row.get("page_no") not in (None, "")],
            "allowed_for_bid_values": [bool(row.get("allowed_for_bid")) for row in rows],
            "quality_tiers": sorted({_text(row.get("quality_tier")) for row in rows if row.get("quality_tier")}),
            "match": match,
        })

    bundles: list[dict[str, Any]] = []
    page_rows: list[dict[str, Any]] = []
    for (kind, business_key), sources in sorted(grouped.items()):
        match = sources[0]["match"]
        primary_sources, renditions = _select_primary_sources(sources, kind)
        audited_sources: list[dict[str, Any]] = []
        all_complete = True
        global_order = 0
        for source in primary_sources:
            audit = _page_audit(source)
            all_complete = all_complete and audit["complete"]
            local = _local_path(source["source_file"])
            source_payload = {
                "component": source["match"].component,
                "source_file": source["source_file"],
                "source_display_name": Path(source["source_file"]).name,
                "source_sha256": source["source_sha256"] or (_sha256_file(local) if local.is_file() else ""),
                "asset_ids": source["asset_ids"],
                **audit,
            }
            audited_sources.append(source_payload)
            assets_by_page = {
                int(page): asset_id
                for page, asset_id in zip(source["asset_page_numbers"], source["asset_ids"])
                if _text(page).isdigit()
            }
            for page_no in range(1, audit["expected_page_count"] + 1):
                global_order += 1
                page_rows.append({
                    "evidence_bundle_id": _stable_id(kind, business_key),
                    "bundle_title": match.title,
                    "component": source["match"].component,
                    "global_order": global_order,
                    "page_no": page_no,
                    "asset_id": assets_by_page.get(page_no, ""),
                    "source_file": source["source_file"],
                    "page_available": page_no in assets_by_page,
                })

        allowed, usage_status, warnings = _usage_gate(match, all_complete)
        bundles.append({
            "evidence_bundle_id": _stable_id(kind, business_key),
            "bundle_title": match.title,
            "enterprise": SHORT_NAME,
            "doc_owner": FULL_NAME,
            "source_domain": "enterprise_fact",
            "reference_only": False,
            "fact_source_allowed_for_enterprise": True,
            "tenant_visibility": "taichang_only",
            "access_scope": "taichang_tenant_internal",
            "bundle_kind": kind,
            "business_key": business_key,
            "evidence_type": match.evidence_type,
            "evidence_type_label": {
                "inspection_report": "检验报告", "calibration_certificate": "试验设备校准资料",
                "certification": "管理体系认证证书", "business_license": "营业执照",
                "finance": "审计报告", "project_performance": "项目业绩",
            }.get(match.evidence_type, "企业证据"),
            "target_library": match.target_library,
            "target_library_label": "产品库" if match.target_library == "product_library" else "资信库",
            "product_families": list(match.product_families),
            "applicable_sections": list(match.applicable_sections),
            "structured_summary": _structured_summary(match, parameter_rows, performance_rows),
            "primary_sources": audited_sources,
            "renditions": [
                {
                    "source_file": item["source_file"],
                    "source_display_name": Path(item["source_file"]).name,
                    "source_sha256": item["source_sha256"],
                    "rendition_type": "reference_page_image" if item["match"].rendition_only else "duplicate_original_file",
                    "formal_page_source": False,
                }
                for item in sorted(renditions, key=_source_priority)
            ],
            "page_count": sum(item["expected_page_count"] for item in audited_sources),
            "page_sequence_complete": all_complete,
            "missing_pages": [
                {"component": item["component"], "pages": item["missing_pages"]}
                for item in audited_sources if item["missing_pages"]
            ],
            "duplicate_pages": [
                {"component": item["component"], "pages": item["duplicate_pages"]}
                for item in audited_sources if item["duplicate_pages"]
            ],
            "allowed_for_bid": allowed,
            "usage_status": usage_status,
            "warnings": warnings,
            "provenance_policy": "仅使用泰昌企业事实原始文件；辽宁招标资料和河北豪乾参考稿禁止作为事实来源",
        })

    present_kinds = {item["bundle_kind"] for item in bundles}
    gaps = [{
        "evidence_type": "prequalification_result",
        "evidence_type_label": "资格预审结果",
        "status": "missing_original_evidence",
        "action": "待客户提供原始资格预审结果文件后再建证据包；历史 Word 页面不得替代原始证据",
    }]
    summary = {
        "bundle_count": len(bundles),
        "page_count": sum(item["page_count"] for item in bundles),
        "complete_bundle_count": sum(bool(item["page_sequence_complete"]) for item in bundles),
        "allowed_for_bid_count": sum(bool(item["allowed_for_bid"]) for item in bundles),
        "blocked_or_conditional_count": sum(not item["allowed_for_bid"] for item in bundles),
        "rendition_count": sum(len(item["renditions"]) for item in bundles),
        "by_kind": dict(sorted(Counter(item["bundle_kind"] for item in bundles).items())),
        "present_kinds": sorted(present_kinds),
        "gap_count": len(gaps),
        "excluded_non_p0_source_count": excluded_count,
        "p0_06_approved_candidate_count": int(p0_06_metadata.get("approved_decision_count", 0) or 0),
        "p0_06_candidates_included_count": 0,
    }
    return {
        "schema_version": "taichang-evidence-bundle-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "write_policy": "read_only_no_database_write",
        "scope": "taichang_materials_bid_pilot",
        "summary": summary,
        "bundles": bundles,
        "pages": page_rows,
        "gaps": gaps,
    }


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(row.get(key), ensure_ascii=False) if isinstance(row.get(key), (list, dict)) else row.get(key, "") for key in fields})


def write_outputs(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "taichang_evidence_bundles.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary_fields = [
        "evidence_bundle_id", "bundle_title", "bundle_kind", "business_key", "evidence_type_label",
        "target_library_label", "product_families", "applicable_sections", "page_count",
        "page_sequence_complete", "allowed_for_bid", "usage_status", "warnings",
    ]
    _write_csv(output_dir / "taichang_evidence_bundles.csv", payload["bundles"], summary_fields)
    page_fields = ["evidence_bundle_id", "bundle_title", "component", "global_order", "page_no", "asset_id", "source_file", "page_available"]
    _write_csv(output_dir / "taichang_evidence_bundle_pages.csv", payload["pages"], page_fields)

    summary = payload["summary"]
    lines = [
        "# 泰昌 P1-02 文件级证据包审计报告", "",
        f"> 生成时间：{payload['generated_at']}",
        "> 范围：泰昌物资类投标试点；只读，不写数据库。", "",
        "## 结果概览", "",
        "| 指标 | 数量 |", "| --- | ---: |",
        f"| 证据包 | {summary['bundle_count']} |",
        f"| 原始文件总页数 | {summary['page_count']} |",
        f"| 页序完整证据包 | {summary['complete_bundle_count']} |",
        f"| 可按现有资产策略使用 | {summary['allowed_for_bid_count']} |",
        f"| 受阻或条件使用 | {summary['blocked_or_conditional_count']} |",
        f"| 重复/参考 rendition | {summary['rendition_count']} |", "",
        "## 证据包清单", "",
        "| 证据包 | 类型 | 页数 | 页序 | 使用状态 |", "| --- | --- | ---: | --- | --- |",
    ]
    for item in payload["bundles"]:
        lines.append(
            f"| {item['bundle_title']} | {item['evidence_type_label']} | {item['page_count']} | "
            f"{'完整' if item['page_sequence_complete'] else '异常'} | {item['usage_status']} |"
        )
    lines.extend(["", "## 缺口", ""])
    for gap in payload["gaps"]:
        lines.append(f"- {gap['evidence_type_label']}：{gap['action']}")
    lines.extend([
        "", "## 边界结论", "",
        "- P0-06 自动接收但尚未提取、校验和入库的历史 Word 内嵌图片未进入主证据包。",
        "- 重复 PDF 与关键页 JPG 仅作为 rendition，不形成第二个用户可见业务对象。",
        "- 职业健康安全管理体系证书过期；设备校准资料、管理体系证书有效期和审计年度均保留正式使用门禁。",
        "- 辽宁招标资料、河北豪乾参考稿未作为泰昌企业事实来源。", "",
    ])
    (output_dir / "taichang_evidence_bundle_report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建泰昌 P1-02 文件级证据包")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    baseline = _load_json(args.baseline, {})
    if not baseline.get("records"):
        raise SystemExit(f"资产基线不存在或为空：{args.baseline}")
    payload = build_bundles(baseline)
    write_outputs(payload, args.output_dir)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

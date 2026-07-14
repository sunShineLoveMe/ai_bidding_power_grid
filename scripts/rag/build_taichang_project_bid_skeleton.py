#!/usr/bin/env python3
"""用真实 SL2655 招标文件包生成 P2-01 项目动态骨架验收产物。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.project_bid_skeleton import build_project_bid_skeleton  # noqa: E402
from backend.parsing.tender_format_rules import extract_docx_format_rule_inputs  # noqa: E402


DEFAULT_PACKAGE = ROOT / "assets/template_words/包1_完整招标文件_92475576192439826"
DEFAULT_TENDER = DEFAULT_PACKAGE / "SL2655招标文件-预审.docx"
DEFAULT_SPEC = DEFAULT_PACKAGE / (
    "国家电网公司总部_一级省公司固化ID修编（9111-500021520-00001）/"
    "改性聚丙烯（MPP）电缆导管专用技术规范（内径200mm，壁厚14.0，断裂延伸率≥200%）.docx"
)
DEFAULT_PARAMETERS = ROOT / (
    "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/"
    "staging/taichang_product_parameters/taichang_product_parameter_rows.json"
)
DEFAULT_OUTPUT = ROOT / "docs/development/taichang-bid-v1-data/p2_01_project_skeleton"


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_format_rows(tender_path: Path) -> tuple[list[dict[str, Any]], list[str], str]:
    inputs = extract_docx_format_rule_inputs(tender_path, source_display_name=_rel(tender_path))
    rows = inputs.get("format_rows") or []
    if not rows:
        raise RuntimeError(inputs.get("warning") or "未找到投标文件格式表")
    return rows, inputs.get("clauses") or [], str(inputs.get("document_text") or "")


def _spec_requirements(spec_path: Path) -> list[dict[str, Any]]:
    document = Document(spec_path)
    rows: list[dict[str, Any]] = []
    wanted = {"公称内径", "公称壁厚", "断裂伸长率", "环刚度"}
    for table_index, table in enumerate(document.tables, start=1):
        for row_index, row in enumerate(table.rows, start=1):
            cells = [_clean(cell.text) for cell in row.cells]
            if len(cells) < 4:
                continue
            parameter = next((item for item in wanted if item in cells[1]), None)
            if not parameter:
                continue
            rows.append({
                "parameter": parameter,
                "unit": cells[2],
                "required_value": cells[3],
                "source_file": _rel(spec_path),
                "source_section": f"技术参数表{table_index}",
                "source_page": None,
                "row_number": row_index,
            })
    return rows


def _parameter_coverage(spec_path: Path, parameter_path: Path) -> dict[str, Any]:
    requirements = _spec_requirements(spec_path)
    source_rows = json.loads(parameter_path.read_text(encoding="utf-8"))
    facts = [row for row in source_rows if row.get("product_family") == "MPP电缆保护管"]
    mapped: list[dict[str, Any]] = []
    aliases = {"公称内径": "平均内径", "公称壁厚": "壁厚", "断裂伸长率": "断裂伸长率", "环刚度": "环刚度"}
    for requirement in requirements:
        fact = next((row for row in facts if aliases[requirement["parameter"]] in str(row.get("parameter_name") or "")), None)
        coverage = "unknown"
        reason = "未找到泰昌结构化参数行"
        if fact:
            if requirement["parameter"] in {"公称内径", "公称壁厚"}:
                coverage = "mismatch"
                reason = "泰昌报告规格与本项目需求规格不一致"
            elif requirement["parameter"] == "断裂伸长率":
                coverage = "mismatch" if float(str(fact.get("inspection_result"))) < 200 else "exact_match"
                reason = "泰昌实测值低于项目需求" if coverage == "mismatch" else "实测值达到项目需求"
            elif requirement["parameter"] == "环刚度":
                coverage = "partial_match"
                reason = "数值达到阈值，但报告规格与本项目规格不同"
        mapped.append({
            **requirement,
            "coverage": coverage,
            "coverage_reason": reason,
            "taichang_value": fact.get("inspection_result") if fact else None,
            "taichang_specification": fact.get("specification_model") if fact else None,
            "taichang_report_no": fact.get("report_no") if fact else None,
            "taichang_source_file": fact.get("source_file") if fact else None,
            "taichang_source_page": fact.get("source_page") if fact else None,
        })
    return {
        "status": "PRODUCT_FAMILY_MATCHED_BUT_SPEC_NOT_COVERED",
        "formal_export_blocked": any(item["coverage"] in {"mismatch", "unknown"} for item in mapped),
        "scope": "qa_only_not_coverage_judgement",
        "rows": mapped,
    }


def _write_markdown(output_dir: Path, skeleton: dict[str, Any]) -> None:
    rules = skeleton["rule_inventory"]
    status_labels = {
        "required": "必须提交", "conditional": "条件适用", "inherited_from_prequalification": "资格预审继承",
        "supplement_allowed": "允许补充", "update_required": "到期需更新", "not_applicable": "不适用",
        "forbidden": "禁止", "reference_only": "仅参考",
    }
    lines = [
        "# SL2655 项目级投标编制规则清单", "",
        "> 目录只由本次招标文件决定；泰昌历史标书仅用于逐项差异对照。", "",
        "| 分册 | 规则/章节 | 当前状态 | 作用域 | 提交范围 | 来源 | 页码 | 判定依据 |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for rule in rules:
        source = (rule.get("sources") or [{}])[0]
        lines.append(
            f"| {rule['volume_type']} | {rule['title'].replace('|', '\\|')} | "
            f"{status_labels.get(rule['status'], rule['status'])} | {rule['rule_scope']} | {rule['submission_scope']} | "
            f"{str(source.get('source_section') or '').replace('|', '\\|')} | {source.get('source_page') or '待复核'} | "
            f"{str(rule.get('status_reason') or '').replace('|', '\\|')} |"
        )
    (output_dir / "SL2655项目级投标编制规则清单.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    diff = skeleton["historical_difference"]
    diff_lines = [
        "# SL2655 当次招标动态骨架—泰昌历史参考骨架差异清单", "",
        "> 对照方法：规范化标题精确匹配，再使用确定性别名；不使用模糊相似度。差异不得反向覆盖本次招标。", "",
        "## 汇总", "", f"- 新增：{diff['summary']['added']}", f"- 删除：{diff['summary']['deleted']}",
        f"- 名称变化：{diff['summary']['name_changed']}", f"- 顺序变化：{diff['summary']['order_changed']}",
        f"- 条件变化：{diff['summary']['condition_changed']}", "", "## 关键结论", "",
        "- 投标保证金：本项目免收，不得因历史模板存在而纳入目录。",
        "- 资格预审申请文件：继承，不重复编制整套资料；仅按招标允许范围补充或更新。",
        "- 历史技术服务、售后、质量方案、生产装备、检测设备、制造工艺、认证证书、人员、检测报告等未被本次格式表标记为须提供，均不进入成稿目录。",
    ]
    (output_dir / "SL2655动态骨架与历史参考骨架差异清单.md").write_text("\n".join(diff_lines) + "\n", encoding="utf-8")

    scope_lines = [
        "# SL2655 批次—分标—包规则作用域清单", "", "| 文件类型 | 规则作用域 | 提交范围 | 纳入规则 | 排除规则 |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for row in skeleton["scope_matrix"]:
        scope_lines.append(
            f"| {row['volume_label']} | {row['rule_scope']} | {row['submission_scope']} | "
            f"{row['included_rule_count']} | {row['excluded_rule_count']} |"
        )
    (output_dir / "SL2655批次分标包规则作用域清单.md").write_text("\n".join(scope_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tender", type=Path, default=DEFAULT_TENDER)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--parameters", type=Path, default=DEFAULT_PARAMETERS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    format_rows, clauses, tender_text = extract_format_rows(args.tender)
    payload = {
        "project": {"id": "acceptance-sl2655", "project_name": "SL2655新疆MPP电缆保护管采购", "project_no": "SL2655", "project_mode": "taichang_reuse"},
        "analysis": {"project_meta": {"project_name": "SL2655新疆MPP电缆保护管采购", "tender_no": "SL2655"}},
        "documentChunks": [{"content": tender_text}],
        "requirements": [], "risks": [], "scoringItems": [],
        "project_rule_inputs": {"source_file": _rel(args.tender), "format_rows": format_rows, "clauses": clauses},
    }
    skeleton = build_project_bid_skeleton(payload)
    skeleton["parameter_coverage"] = _parameter_coverage(args.spec, args.parameters)
    skeleton["acceptance_sample"] = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tender_file": _rel(args.tender),
        "technical_specification": _rel(args.spec),
        "taichang_parameter_rows": _rel(args.parameters),
        "format_rows": len(format_rows),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "project_bid_skeleton.json").write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "project_bid_rules.json").write_text(json.dumps(skeleton["rule_inventory"], ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "historical_skeleton_difference.json").write_text(json.dumps(skeleton["historical_difference"], ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "scope_matrix.json").write_text(json.dumps(skeleton["scope_matrix"], ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(args.output_dir, skeleton)
    print(json.dumps({
        "output": _rel(args.output_dir / "project_bid_skeleton.json"),
        "rules": skeleton["project_rule_summary"],
        "scope_matrix": skeleton["scope_matrix"],
        "parameter_coverage": skeleton["parameter_coverage"]["status"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

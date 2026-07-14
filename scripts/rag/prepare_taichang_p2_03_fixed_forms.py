#!/usr/bin/env python3
"""生成并可选应用泰昌 P2-03 固定表单/参数响应 manifest。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.db.supabase_repo import get_project_interpretation, update_bid_section_content  # noqa: E402
from backend.services.taichang_fixed_forms import (  # noqa: E402
    build_p2_03_fixed_form_payload,
    load_parameter_rows,
)


PACKAGE_ROOT = ROOT / "assets/template_words/包1_完整招标文件_92475576192439826"
DEFAULT_MAIN_TENDER = PACKAGE_ROOT / "SL2655招标文件-预审.docx"
DEFAULT_SPEC = PACKAGE_ROOT / "国家电网公司总部_一级省公司固化ID修编（9111-500021520-00001）/改性聚丙烯（MPP）电缆导管专用技术规范（内径200mm，壁厚14.0，断裂延伸率≥200%）.docx"
DEFAULT_PARAMETER_ROWS = (
    ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0"
    / "staging/taichang_product_parameters/taichang_product_parameter_rows.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "docs/development/taichang-bid-v1-data/p2_03_fixed_forms"


def _relative(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _relative(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_relative(item) for item in value]
    if isinstance(value, str):
        try:
            path = Path(value)
            if path.is_absolute():
                return str(path.relative_to(ROOT))
        except (ValueError, OSError):
            pass
    return value


def _apply_to_project(project_id: str, manifests: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = get_project_interpretation(project_id)
    sections = payload.get("sections") or []
    updated = []
    missing = []
    for title, manifest in manifests.items():
        section = next((row for row in sections if str(row.get("title") or "").strip() == title), None)
        if not section:
            missing.append(title)
            continue
        saved = update_bid_section_content(
            project_id,
            section["id"],
            "",
            section.get("status") or "draft",
            section,
            preserve_existing_content=True,
            metadata_patch={
                "fixed_form_manifest": manifest,
                "fixed_form_formal_ready": bool(manifest.get("formal_ready")),
                "fixed_form_blocker_count": len(manifest.get("blockers") or []),
            },
        )
        updated.append({"id": saved.get("id"), "title": title})
    return {"project_id": project_id, "updated_sections": updated, "missing_sections": missing}


def _summary(payload: dict[str, Any], apply_result: dict[str, Any] | None) -> str:
    inventory = payload["inventory"]
    response = payload["technical_parameter_response"]
    counts = response.get("coverage_counts") or {}
    forms = inventory.get("forms") or {}
    rows = [
        "# P2-03 固定表单与参数响应 manifest",
        "",
        f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 原生固定表单：{len(forms)}/4；缺失：{'、'.join(inventory.get('missing_forms') or []) or '无'}",
        f"- 专项参数行：{response.get('row_count', 0)}",
        f"- 覆盖状态：exact_match={counts.get('exact_match', 0)}，partial_match={counts.get('partial_match', 0)}，mismatch={counts.get('mismatch', 0)}，unknown={counts.get('unknown', 0)}",
        f"- 已填投标人保证值：{response.get('filled_guarantee_count', 0)}",
        f"- 正式可用：{'是' if response.get('formal_ready') else '否'}",
        "- 核心边界：泰昌现有 250×22 报告不得直接覆盖项目 200×14；176% 不满足 ≥200%。",
    ]
    if apply_result:
        rows.extend([
            "",
            "## 真实项目应用",
            "",
            f"- 项目 ID：`{apply_result['project_id']}`",
            f"- 更新章节：{len(apply_result['updated_sections'])}",
            f"- 缺失章节：{'、'.join(apply_result['missing_sections']) or '无'}",
        ])
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-tender", type=Path, default=DEFAULT_MAIN_TENDER)
    parser.add_argument("--technical-spec", type=Path, action="append", default=None)
    parser.add_argument("--parameter-rows", type=Path, default=DEFAULT_PARAMETER_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--project-id")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    technical_specs = args.technical_spec or [DEFAULT_SPEC]
    parameter_rows = load_parameter_rows(args.parameter_rows)
    payload = build_p2_03_fixed_form_payload(args.main_tender, technical_specs, parameter_rows)
    payload = _relative(payload)

    apply_result = None
    if args.apply:
        if not args.project_id:
            parser.error("--apply 必须同时提供 --project-id")
        apply_result = _apply_to_project(args.project_id, payload["section_manifests"])

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "taichang_fixed_form_response_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "taichang_fixed_form_response_summary.md").write_text(
        _summary(payload, apply_result), encoding="utf-8"
    )
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "forms": len(payload["inventory"]["forms"]),
        "parameter_rows": payload["technical_parameter_response"]["row_count"],
        "coverage_counts": payload["technical_parameter_response"]["coverage_counts"],
        "filled_guarantee_count": payload["technical_parameter_response"]["filled_guarantee_count"],
        "formal_ready": payload["technical_parameter_response"]["formal_ready"],
        "apply_result": apply_result,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

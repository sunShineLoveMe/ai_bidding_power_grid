#!/usr/bin/env python3
"""Run real DOCX export checks for Taichang supplement assets."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs" / "development" / "runs"
BATCH_ID = "customer_taichang_supplement_20260611"
PROJECT_ID = "4bc3ee73-9ec5-4184-aafd-eaede9f90798"

sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")


def _read_docx_text(docx_path: Path) -> str:
    with ZipFile(docx_path) as archive:
        parts = []
        for name in archive.namelist():
            if not (
                name == "word/document.xml"
                or name.startswith("word/header")
                or name.startswith("word/footer")
            ):
                continue
            if name in archive.namelist():
                parts.append(archive.read(name).decode("utf-8", errors="ignore"))
        return "\n".join(parts)


def _count_docx_media(docx_path: Path) -> int:
    with ZipFile(docx_path) as archive:
        return len([name for name in archive.namelist() if name.startswith("word/media/")])


def _manifest_counts(manifest: list[dict[str, Any]]) -> dict[str, Any]:
    by_batch = Counter(item.get("source_batch_id") or "unknown" for item in manifest)
    by_evidence = Counter(item.get("evidence_type") or "unknown" for item in manifest)
    by_batch_evidence = Counter(
        f"{item.get('source_batch_id') or 'unknown'}|{item.get('evidence_type') or 'unknown'}"
        for item in manifest
    )
    return {
        "by_batch": dict(by_batch),
        "by_evidence": dict(by_evidence),
        "by_batch_evidence": dict(by_batch_evidence),
    }


def _rel(path: Path) -> str:
    path = path if path.is_absolute() else PROJECT_ROOT / path
    return str(path.relative_to(PROJECT_ROOT))


def _validate(report: dict[str, Any]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    image_selection = report["image_selection"]
    image_conversion = report["image_conversion"]
    field_refresh = report["field_refresh"]
    counts = report["manifest_counts"]["by_batch_evidence"]

    if image_selection.get("selected", 0) <= 0:
        failures.append("no images selected")
    if counts.get(f"{BATCH_ID}|project_performance", 0) < 2:
        failures.append("project performance assets from supplement were not selected")
    for evidence_type in ["production_capacity", "testing_capacity", "inspection_report"]:
        if counts.get(f"{BATCH_ID}|{evidence_type}", 0) < 1:
            failures.append(f"{evidence_type} asset from supplement was not selected")
    if counts.get(f"{BATCH_ID}|brand_logo", 0) < 1:
        warnings.append("brand logo is in asset library but not yet inserted into DOCX cover/header")
    if image_conversion.get("inserted", 0) <= 0 or image_conversion.get("failed", 0) != 0:
        failures.append(f"image conversion failed or inserted no images: {image_conversion}")
    if field_refresh.get("status") != "refreshed":
        failures.append(f"field refresh not refreshed: {field_refresh.get('status')}")
    for key, ok in report["docx_checks"].items():
        if not ok:
            failures.append(f"docx check failed: {key}")
    return failures, warnings


def _write_report(report: dict[str, Any]) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = report["run_id"]
    json_path = RUNS_DIR / f"{run_id}.json"
    md_path = RUNS_DIR / f"{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    status = "PASS" if not report["failures"] else "FAIL"
    lines = [
        f"# {run_id} — 泰昌补充资料 DOCX 真实导出验证",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 项目 ID：`{report['project_id']}`",
        f"- 状态：{status}",
        "",
        "## 输出文件",
        "",
        f"- Markdown：`{report['markdown_path']}`",
        f"- DOCX：`{report['docx_path']}`",
        "",
        "## 图片选择",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| candidates | {report['image_selection']['asset_candidates']} |",
        f"| selected | {report['image_selection']['selected']} |",
        f"| supplement selected | {report['manifest_counts']['by_batch'].get(BATCH_ID, 0)} |",
        f"| DOCX media files | {report['docx_media_count']} |",
        "",
        "## 补充资料证据类型",
        "",
        "| evidence_type | 数量 |",
        "| --- | ---: |",
    ]
    for key, value in sorted(report["manifest_counts"]["by_batch_evidence"].items()):
        if key.startswith(f"{BATCH_ID}|"):
            lines.append(f"| `{key.split('|', 1)[1]}` | {value} |")
    lines.extend([
        "",
        "## 转换与刷新",
        "",
        f"- 图片转换：found/inserted/skipped/failed = "
        f"{report['image_conversion'].get('found')}/"
        f"{report['image_conversion'].get('inserted')}/"
        f"{report['image_conversion'].get('skipped')}/"
        f"{report['image_conversion'].get('failed')}",
        f"- 字段刷新：`{report['field_refresh'].get('status')}`",
        "",
        "## 检查结论",
        "",
    ])
    if report["failures"]:
        lines.extend(f"- FAIL：{failure}" for failure in report["failures"])
    else:
        lines.append("- P1B-2 真实标书生成链路引用验证通过。")
    if report["warnings"]:
        lines.extend(f"- WARN：{warning}" for warning in report["warnings"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="run_20260611_taichang_supplement_p1b_docx_export")
    parser.add_argument("--project-id", default=PROJECT_ID)
    args = parser.parse_args()

    os.environ["APP_AUTH_ENABLED"] = "false"
    os.environ["APP_LOGIN_ENABLED"] = "false"
    os.environ.setdefault("APP_ENV", "testing")

    import main as flask_main  # noqa: WPS433
    from backend.api.routes import build_project_bid_markdown  # noqa: WPS433
    from backend.export.md_to_word import convert_md_to_word, refresh_docx_fields_with_soffice  # noqa: WPS433

    with flask_main.app.app_context():
        markdown_path, title, image_selection = build_project_bid_markdown(args.project_id, with_images=True)
        docx_path, image_conversion = convert_md_to_word(
            markdown_path,
            return_report=True,
            cover_fields=(image_selection or {}).get("cover_fields") or None,
        )
        docx_path, field_refresh = refresh_docx_fields_with_soffice(Path(docx_path))

    docx_path = Path(docx_path)
    docx_text = _read_docx_text(docx_path)
    manifest = image_selection.get("manifest") or []
    report = {
        "run_id": args.run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_id": args.project_id,
        "document_title": title,
        "markdown_path": _rel(Path(markdown_path)),
        "docx_path": _rel(docx_path),
        "docx_size": docx_path.stat().st_size,
        "image_selection": image_selection,
        "image_conversion": image_conversion,
        "field_refresh": field_refresh,
        "manifest_counts": _manifest_counts(manifest),
        "docx_media_count": _count_docx_media(docx_path),
        "docx_checks": {
            "no_mermaid_fence": "```mermaid" not in docx_text and "graph TD" not in docx_text,
            "no_internal_image_source": all(token not in docx_text for token in ["source_batch_id", "source_domain", "匹配依据", "metadata"]),
            "has_taichang_header": "河北泰昌电力器材科技有限公司投标文件" in docx_text,
        },
    }
    failures, warnings = _validate(report)
    report["failures"] = failures
    report["warnings"] = warnings
    md_path = _write_report(report)
    print(json.dumps({"report": str(md_path.relative_to(PROJECT_ROOT)), "failures": failures, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

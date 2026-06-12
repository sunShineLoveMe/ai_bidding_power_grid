#!/usr/bin/env python3
"""Regenerate every Taichang bid section with real DeepSeek calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs" / "development" / "runs"
PROJECT_ID = "4bc3ee73-9ec5-4184-aafd-eaede9f90798"

sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")


def _sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _clean_generation_metadata(section: dict[str, Any], run_id: str) -> dict[str, Any]:
    metadata = dict(section.get("metadata") or {})
    metadata["generation_options"] = {
        "force_fresh": True,
        "disable_continuation": True,
        "run_id": run_id,
        "generated_by": "scripts/rag/regenerate_taichang_full_bid_deepseek.py",
    }
    metadata["generation_status"] = "regenerating"
    metadata["writing_status"] = "regenerating"
    metadata["regeneration_run_id"] = run_id
    metadata["regenerated_at"] = datetime.now().isoformat(timespec="seconds")
    metadata.pop("writing_error", None)
    metadata.pop("writing_error_code", None)
    return metadata


def _generation_chapter(section: dict[str, Any], run_id: str) -> dict[str, Any]:
    chapter = dict(section)
    chapter["content"] = ""
    chapter["status"] = "draft"
    chapter["metadata"] = _clean_generation_metadata(section, run_id)
    return chapter


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_summary(path: Path, report: dict[str, Any]) -> None:
    lines = [
        f"# 泰昌完整标书 DeepSeek 全量重写记录 - {report['run_id']}",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 项目 ID：`{report['project_id']}`",
        f"- AI_PROVIDER：`{report['ai_provider']}`",
        f"- 章节写作模型：`{report['section_writing_model']}`",
        f"- 章节补写模型：`{report['section_supplement_model']}`",
        f"- 目标章节数：{report['target_sections']}",
        f"- 成功章节数：{report['success_count']}",
        f"- 失败章节数：{report['failure_count']}",
        f"- 总耗时秒：{report['elapsed_seconds']}",
        f"- 旧正文备份：`{report['backup_path']}`",
        "",
        "## 生成结论",
        "",
        "PASS" if not report["failures"] else "FAIL",
        "",
        "## 失败章节",
        "",
    ]
    if report["failures"]:
        for failure in report["failures"]:
            lines.append(f"- {failure['order_index']} {failure['title']}：{failure['error']}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 章节明细", ""])
    lines.append("| 序号 | 层级 | 章节 | 状态 | 字数估算 | 字符数 | chunks |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | ---: |")
    for item in report["sections"]:
        lines.append(
            f"| {item.get('order_index')} | {item.get('level')} | {item.get('title')} | "
            f"{item.get('status')} | {item.get('words', 0)} | {item.get('chars', 0)} | {item.get('chunks', 0)} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default=PROJECT_ID)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=0, help="Debug only. 0 means all sections.")
    parser.add_argument("--start-after-order", type=int, default=0)
    args = parser.parse_args()

    os.environ["APP_AUTH_ENABLED"] = "false"
    os.environ["APP_LOGIN_ENABLED"] = "false"
    os.environ.setdefault("APP_ENV", "testing")

    import main as flask_main  # noqa: WPS433
    from backend.core.config import get_stage_model  # noqa: WPS433
    from backend.db.supabase_repo import list_bid_sections, update_bid_section_content  # noqa: WPS433
    from backend.services.section_generation import generate_and_save_bid_section  # noqa: WPS433

    if os.getenv("AI_PROVIDER") != "deepseek":
        raise RuntimeError(f"AI_PROVIDER must be deepseek for this run, got {os.getenv('AI_PROVIDER')!r}")
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is missing")

    started = time.time()
    with flask_main.app.app_context():
        sections = list_bid_sections(args.project_id)
        sections = [section for section in sections if int(section.get("order_index") or 0) > args.start_after_order]
        if args.limit > 0:
            sections = sections[: args.limit]
        backup_rows = [
            {
                "id": section.get("id"),
                "order_index": section.get("order_index"),
                "level": section.get("level"),
                "title": section.get("title"),
                "status": section.get("status"),
                "content_sha256": _sha256_text(str(section.get("content") or "")),
                "content_chars": len(str(section.get("content") or "")),
                "metadata": section.get("metadata") or {},
            }
            for section in sections
        ]
        backup_path = RUNS_DIR / f"{args.run_id}_before_sections_backup.json"
        _write_json(backup_path, backup_rows)

        results: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for index, section in enumerate(sections, 1):
            chapter = _generation_chapter(section, args.run_id)
            update_bid_section_content(
                args.project_id,
                str(section["id"]),
                "",
                "regenerating",
                section,
                metadata_patch=chapter["metadata"],
            )
            print(
                json.dumps(
                    {
                        "event": "section_start",
                        "index": index,
                        "total": len(sections),
                        "order_index": section.get("order_index"),
                        "title": section.get("title"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            try:
                summary = generate_and_save_bid_section(args.project_id, chapter, with_images=False)
                row = {
                    "id": section.get("id"),
                    "order_index": section.get("order_index"),
                    "level": section.get("level"),
                    "title": section.get("title"),
                    "status": "generated",
                    **summary,
                }
                results.append(row)
                print(json.dumps({"event": "section_done", **row}, ensure_ascii=False), flush=True)
            except Exception as exc:  # noqa: BLE001 - report the real failed section and continue.
                failure = {
                    "id": section.get("id"),
                    "order_index": section.get("order_index"),
                    "level": section.get("level"),
                    "title": section.get("title"),
                    "error": str(exc),
                }
                failures.append(failure)
                results.append({**failure, "status": "failed", "words": 0, "chars": 0, "chunks": 0})
                print(json.dumps({"event": "section_failed", **failure}, ensure_ascii=False), flush=True)

    report = {
        "run_id": args.run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_id": args.project_id,
        "ai_provider": os.getenv("AI_PROVIDER"),
        "section_writing_model": get_stage_model("section_writing"),
        "section_supplement_model": get_stage_model("section_supplement"),
        "target_sections": len(sections),
        "success_count": len([item for item in results if item.get("status") == "generated"]),
        "failure_count": len(failures),
        "elapsed_seconds": round(time.time() - started, 2),
        "backup_path": str(backup_path.relative_to(PROJECT_ROOT)),
        "sections": results,
        "failures": failures,
    }
    json_path = RUNS_DIR / f"{args.run_id}.json"
    md_path = RUNS_DIR / f"{args.run_id}.md"
    _write_json(json_path, report)
    _write_summary(md_path, report)
    print(json.dumps({"report": str(md_path.relative_to(PROJECT_ROOT)), "failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

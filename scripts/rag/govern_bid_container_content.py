#!/usr/bin/env python3
"""Govern historical content stored on bid outline container sections.

Container sections are directory nodes. They should not hold formal bid body
content. This script inventories, backs up, marks and optionally clears legacy
container content while keeping a reversible audit trail.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs" / "development" / "runs"
DEFAULT_PROJECT_ID = "a1d853bc-ca4e-43b4-bbea-256f561c8a3d"

sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

INTERNAL_GUIDANCE_TERMS = (
    "编写要点",
    "需准备资料",
    "风险与复核",
    "目标字数",
    "硬性篇幅上限",
    "参考客户同类标书目录组织本节",
    "需人工补充",
    "避免遗漏实质性要求",
    "暂无明确风险",
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _display_path(path: Path) -> str:
    resolved = path if path.is_absolute() else PROJECT_ROOT / path
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _container_section_ids(sections: list[dict[str, Any]]) -> set[str]:
    return {str(section.get("parent_id")) for section in sections if section.get("parent_id")}


def is_container_section(section: dict[str, Any], parent_ids: set[str]) -> bool:
    metadata = section.get("metadata") if isinstance(section.get("metadata"), dict) else {}
    return (
        metadata.get("section_role") == "container"
        or metadata.get("leaf_generation") is False
        or str(section.get("id") or "") in parent_ids
    )


def classify_container_content(content: str) -> tuple[str, list[str]]:
    text = (content or "").strip()
    if not text:
        return "empty", []
    hits = [term for term in INTERNAL_GUIDANCE_TERMS if term in text]
    if hits:
        return "internal_guidance", hits
    if len(text) < 120:
        return "short_note_review", []
    return "formal_overview_candidate", []


def _backup_row(section: dict[str, Any], classification: str, guidance_hits: list[str]) -> dict[str, Any]:
    content = str(section.get("content") or "")
    return {
        "id": section.get("id"),
        "project_id": section.get("project_id"),
        "parent_id": section.get("parent_id"),
        "order_index": section.get("order_index"),
        "level": section.get("level"),
        "title": section.get("title"),
        "status": section.get("status"),
        "classification": classification,
        "guidance_hits": guidance_hits,
        "content_chars": len(content),
        "content_sha256": _sha256_text(content),
        "content": content,
        "metadata": section.get("metadata") or {},
    }


def _governance_event(
    *,
    run_id: str,
    timestamp: str,
    section: dict[str, Any],
    classification: str,
    guidance_hits: list[str],
    backup_path: Path,
    clear_content: bool,
) -> dict[str, Any]:
    content = str(section.get("content") or "")
    return {
        "run_id": run_id,
        "governed_at": timestamp,
        "classification": classification,
        "guidance_hits": guidance_hits,
        "content_chars": len(content),
        "content_sha256": _sha256_text(content),
        "backup_path": _display_path(backup_path),
        "action": "cleared_to_backup" if clear_content and content else "marked_only",
        "formal_export_policy": "ignored_for_formal_export",
    }


def build_governance_payload(
    section: dict[str, Any],
    *,
    run_id: str,
    timestamp: str,
    classification: str,
    guidance_hits: list[str],
    backup_path: Path,
    clear_content: bool,
) -> dict[str, Any]:
    metadata = dict(section.get("metadata") or {})
    event = _governance_event(
        run_id=run_id,
        timestamp=timestamp,
        section=section,
        classification=classification,
        guidance_hits=guidance_hits,
        backup_path=backup_path,
        clear_content=clear_content,
    )
    history = metadata.get("container_content_governance_history")
    if not isinstance(history, list):
        history = []
    metadata.update(
        {
            "section_role": "container",
            "leaf_generation": False,
            "container_content_policy": "ignored_for_formal_export",
            "container_content_governance": event,
            "container_note": (
                "历史父级正文已备份并从正文内容隔离；该节点仅作为目录结构和导出标题。"
                if clear_content and str(section.get("content") or "").strip()
                else "该节点仅作为目录结构和导出标题，不参与正式正文生成。"
            ),
            "migration_review_required": classification == "formal_overview_candidate",
        }
    )
    metadata["container_content_governance_history"] = [*history[-4:], event]
    payload = {"metadata": metadata}
    if clear_content and str(section.get("content") or "").strip():
        payload["content"] = ""
    return payload


def build_governance_plan(
    sections: list[dict[str, Any]],
    *,
    run_id: str,
    timestamp: str,
    backup_path: Path,
    clear_content: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    parent_ids = _container_section_ids(sections)
    container_rows: list[dict[str, Any]] = []
    backup_rows: list[dict[str, Any]] = []
    update_plans: list[dict[str, Any]] = []
    for section in sections:
        if not is_container_section(section, parent_ids):
            continue
        classification, guidance_hits = classify_container_content(str(section.get("content") or ""))
        container_rows.append(
            {
                "id": section.get("id"),
                "order_index": section.get("order_index"),
                "level": section.get("level"),
                "title": section.get("title"),
                "content_chars": len(str(section.get("content") or "")),
                "classification": classification,
                "guidance_hits": guidance_hits,
            }
        )
        backup_rows.append(_backup_row(section, classification, guidance_hits))
        update_plans.append(
            {
                "id": section.get("id"),
                "title": section.get("title"),
                "classification": classification,
                "content_chars": len(str(section.get("content") or "")),
                "payload": build_governance_payload(
                    section,
                    run_id=run_id,
                    timestamp=timestamp,
                    classification=classification,
                    guidance_hits=guidance_hits,
                    backup_path=backup_path,
                    clear_content=clear_content,
                ),
            }
        )
    return container_rows, backup_rows, update_plans


def _summary_payload(
    *,
    run_id: str,
    project_id: str,
    timestamp: str,
    apply: bool,
    clear_content: bool,
    backup_path: Path,
    container_rows: list[dict[str, Any]],
    updated: list[dict[str, Any]],
) -> dict[str, Any]:
    nonempty = [row for row in container_rows if row["content_chars"] > 0]
    formal_candidates = [row for row in container_rows if row["classification"] == "formal_overview_candidate"]
    internal_guidance = [row for row in container_rows if row["classification"] == "internal_guidance"]
    return {
        "run_id": run_id,
        "project_id": project_id,
        "timestamp": timestamp,
        "apply": apply,
        "clear_content": clear_content,
        "backup_path": _display_path(backup_path),
        "container_count": len(container_rows),
        "nonempty_container_count": len(nonempty),
        "internal_guidance_count": len(internal_guidance),
        "formal_overview_candidate_count": len(formal_candidates),
        "updated_count": len(updated),
        "updated": updated,
        "formal_overview_candidates": formal_candidates,
        "containers": container_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="治理 bid_sections 父级容器历史正文")
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID, help="项目 ID")
    parser.add_argument("--run-id", default="", help="运行编号；默认按时间生成")
    parser.add_argument("--apply", action="store_true", help="实际写回 metadata/content；默认只备份和输出计划")
    parser.add_argument("--clear-content", action="store_true", help="将父级容器 content 清空，仅保留备份和 metadata 审计")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = args.run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_bid_container_content_governance"
    backup_path = RUNS_DIR / f"{run_id}_container_content_backup.json"
    summary_path = RUNS_DIR / f"{run_id}_container_content_governance_summary.json"

    os.environ.setdefault("APP_ENV", "testing")
    import main as flask_main  # noqa: WPS433
    from backend.db.supabase_repo import get_supabase_client, list_bid_sections  # noqa: WPS433

    with flask_main.app.app_context():
        sections = list_bid_sections(args.project_id)
        container_rows, backup_rows, update_plans = build_governance_plan(
            sections,
            run_id=run_id,
            timestamp=timestamp,
            backup_path=backup_path,
            clear_content=args.clear_content,
        )
        _write_json(backup_path, backup_rows)

        updated: list[dict[str, Any]] = []
        if args.apply:
            client = get_supabase_client()
            for plan in update_plans:
                response = (
                    client.table("bid_sections")
                    .update(plan["payload"])
                    .eq("id", plan["id"])
                    .eq("project_id", args.project_id)
                    .execute()
                )
                if not response.data:
                    raise RuntimeError(f"父级容器治理写回失败: {plan['id']} {plan['title']}")
                updated.append(
                    {
                        "id": plan["id"],
                        "title": plan["title"],
                        "classification": plan["classification"],
                        "content_chars_before": plan["content_chars"],
                        "content_cleared": bool(args.clear_content and plan["content_chars"] > 0),
                    }
                )

        summary = _summary_payload(
            run_id=run_id,
            project_id=args.project_id,
            timestamp=timestamp,
            apply=bool(args.apply),
            clear_content=bool(args.clear_content),
            backup_path=backup_path,
            container_rows=container_rows,
            updated=updated,
        )
        _write_json(summary_path, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"backup_path={_display_path(backup_path)}")
        print(f"summary_path={_display_path(summary_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

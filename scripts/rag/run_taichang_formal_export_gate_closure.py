#!/usr/bin/env python3
"""Close the Taichang formal export gate as far as real evidence allows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs" / "development" / "runs"
RAG_RUNS_DIR = PROJECT_ROOT / "docs" / "rag" / "runs"
PROJECT_ID = "a1d853bc-ca4e-43b4-bbea-256f561c8a3d"

sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

FORMAL_PLACEHOLDER_RE = re.compile(r"【\s*待(?:补充|填写|确认|核对)\s*[：:]?\s*([^】]*)】")
CUSTOMER_DECISION_KEYS = {
    "total_bid_price",
    "total_bid_price_upper",
    "tax_rate",
    "bid_bond_amount",
    "bid_bond_form",
    "delivery_period",
    "warranty_period",
    "authorized_representative",
    "authorized_representative_id",
    "authorized_representative_phone",
    "signature_date",
}
FORBIDDEN_TOPICS = [
    "水利施工",
    "桩基",
    "防渗墙",
    "BIM",
    "建造师",
    "安全生产许可证",
    "电力工程施工总承包",
    "输变电工程专业承包",
    "承装（修、试）电力设施许可证",
]
REQUIRED_SCOPE = (
    "本项目按河北泰昌电力器材科技有限公司电缆保护管 MPP/CPVC 物资供货标书编写，"
    "范围包括生产、检验、包装、运输、交付和售后服务；除招标文件明确要求外，不扩写工程施工、安装总承包或水利业务。"
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _sha(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _clean_placeholder_text(content: str) -> tuple[str, int]:
    def replace(match: re.Match[str]) -> str:
        label = match.group(1).strip(" ：:")
        if label:
            return f"客户最终确认后填写（{label}）"
        return "客户最终确认后填写"

    return FORMAL_PLACEHOLDER_RE.subn(replace, content or "")


def _confirmed_values_from_report(report: dict[str, Any]) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    values: dict[str, str] = {}
    auto_applied: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for field in report.get("fields") or []:
        key = str(field.get("key") or "")
        if not key:
            continue
        confirmed = field.get("confirmedValue")
        candidate = field.get("value")
        if confirmed:
            value = confirmed
            source = "existing_confirmation"
        elif key not in CUSTOMER_DECISION_KEYS and candidate:
            value = candidate
            source = "prefill_candidate"
        else:
            value = None
            source = "blocked_customer_decision" if key in CUSTOMER_DECISION_KEYS else "missing_candidate"

        if isinstance(value, list):
            text_value = "；".join(str(item).strip() for item in value if str(item).strip())
        else:
            text_value = str(value or "").strip()
        if text_value:
            values[key] = text_value
            if source == "prefill_candidate":
                auto_applied.append({
                    "key": key,
                    "label": field.get("label"),
                    "status": field.get("status"),
                    "source": source,
                    "value_preview": text_value[:240],
                })
        elif field.get("requiredLevel") == "formal_required":
            blocked.append({
                "key": key,
                "label": field.get("label"),
                "status": field.get("status"),
                "source": source,
                "customer_decision": bool(field.get("customerDecision")),
            })
    return values, auto_applied, blocked


def _write_summary(path: Path, report: dict[str, Any]) -> None:
    lines = [
        f"# {report['run_id']} — 泰昌正式导出门禁收口",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 项目 ID：`{report['project_id']}`",
        f"- 状态：{report['status']}",
        f"- 耗时：{report['elapsed_seconds']} 秒",
        "",
        "## 操作摘要",
        "",
        f"- 应用前导确认字段：{report['prefill']['confirmed_value_count']} 个",
        f"- 自动采纳非客户决策候选：{len(report['prefill']['auto_applied'])} 个",
        f"- 客户决策/缺候选字段保留阻断：{len(report['prefill']['blocked_required'])} 个",
        f"- 目标空章节：{report['sections']['target_count']} 个",
        f"- 成功生成章节：{report['sections']['generated_count']} 个",
        f"- 失败章节：{report['sections']['failed_count']} 个",
        f"- 占位符清理：{report['sections']['placeholder_replacements']} 处",
        f"- 空叶子章节：{report['after']['empty_leaf_sections']}",
        f"- 正文占位符：{report['after']['placeholder_count']}",
        f"- 正式必填缺口：{len(report['after']['missing_formal_required_fields'])}",
        "",
        "## 自动采纳字段",
        "",
    ]
    if report["prefill"]["auto_applied"]:
        lines.extend(
            f"- {item['label']}（`{item['key']}`）：{item['value_preview']}"
            for item in report["prefill"]["auto_applied"]
        )
    else:
        lines.append("- 无")
    lines.extend(["", "## 仍需客户确认", ""])
    if report["after"]["missing_formal_required_fields"]:
        lines.extend(
            f"- {item.get('label') or item.get('key')}（`{item.get('key')}`）"
            for item in report["after"]["missing_formal_required_fields"]
        )
    else:
        lines.append("- 无")
    lines.extend(["", "## 章节生成失败", ""])
    if report["sections"]["failures"]:
        lines.extend(f"- {item['order_index']} {item['title']}：{item['error']}" for item in report["sections"]["failures"])
    else:
        lines.append("- 无")
    lines.extend(["", "## 生成章节明细", "", "| 序号 | 章节 | 状态 | 字数 | 占位清理 |", "| ---: | --- | --- | ---: | ---: |"])
    for item in report["sections"]["results"]:
        lines.append(
            f"| {item.get('order_index') or ''} | {item.get('title') or ''} | {item.get('status')} | "
            f"{item.get('words') or 0} | {item.get('placeholder_replacements') or 0} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default=PROJECT_ID)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--include-containers", action="store_true", help="Generate empty container sections too.")
    parser.add_argument("--no-generate", action="store_true")
    args = parser.parse_args()

    os.environ["APP_AUTH_ENABLED"] = "false"
    os.environ["APP_LOGIN_ENABLED"] = "false"
    os.environ.setdefault("APP_ENV", "testing")
    os.environ.setdefault("BID_SECTION_LENGTH_SUPPLEMENT_ENABLED", "false")
    os.environ.setdefault("BID_SECTION_HARD_LENGTH_CAP_RATIO", "0.55")
    os.environ.setdefault("BID_SECTION_HARD_LENGTH_CAP_MIN_EXTRA_WORDS", "60")

    import main as flask_main  # noqa: WPS433
    from backend.api.routes import _snapshot_export_sections  # noqa: WPS433
    from backend.db.supabase_repo import get_project_interpretation, get_supabase_client, list_bid_sections, update_bid_section_content  # noqa: WPS433
    from backend.services.bid_prefill import apply_bid_prefill_confirmation, build_bid_prefill_report  # noqa: WPS433
    from backend.services.section_generation import generate_and_save_bid_section  # noqa: WPS433
    from backend.services.taichang_bid_context import build_taichang_verified_fact_context  # noqa: WPS433

    started = time.time()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    placeholder_replacements = 0

    with flask_main.app.app_context():
        before_sections = list_bid_sections(args.project_id)
        backup_path = RUNS_DIR / f"{args.run_id}_before_sections_backup.json"
        _write_json(backup_path, [{**row, "content_sha256": _sha(str(row.get("content") or ""))} for row in before_sections])

        prefill_report = build_bid_prefill_report(args.project_id)
        confirmed_values, auto_applied, blocked_required = _confirmed_values_from_report(prefill_report)
        prefill_application = (
            {
                "dry_run": True,
                "confirmed_values": confirmed_values,
                "missing_formal_required_fields": [],
                "changed_section_count": 0,
                "replacement_count": 0,
            }
            if args.no_generate
            else apply_bid_prefill_confirmation(args.project_id, confirmed_values)
        )

        sections = list_bid_sections(args.project_id)
        parent_ids = {str(row.get("parent_id")) for row in sections if row.get("parent_id")}

        def is_container(section: dict[str, Any]) -> bool:
            metadata = section.get("metadata") if isinstance(section.get("metadata"), dict) else {}
            return (
                metadata.get("section_role") == "container"
                or metadata.get("leaf_generation") is False
                or str(section.get("id") or "") in parent_ids
            )

        targets = [
            dict(row)
            for row in sections
            if not str(row.get("content") or "").strip()
            and (args.include_containers or not is_container(row))
        ]
        if args.limit:
            targets = targets[: args.limit]

        client = get_supabase_client()
        factual_context = build_taichang_verified_fact_context()
        for index, section in enumerate(targets, 1):
            if args.no_generate:
                results.append({
                    "order_index": section.get("order_index"),
                    "title": section.get("title"),
                    "status": "dry_run",
                    "placeholder_replacements": 0,
                    "words": 0,
                    "chars": 0,
                    "chunks": 0,
                })
                continue
            metadata = dict(section.get("metadata") or {})
            options = dict(metadata.get("generation_options") or {})
            options.update({
                "force_fresh": True,
                "disable_continuation": True,
                "skip_length_supplement": True,
                "run_id": args.run_id,
                "factual_context": factual_context,
                "required_scope": REQUIRED_SCOPE,
                "forbidden_topics": FORBIDDEN_TOPICS,
                "generated_by": "scripts/rag/run_taichang_formal_export_gate_closure.py",
            })
            metadata.update({
                "generation_options": options,
                "generation_status": "regenerating",
                "writing_status": "regenerating",
                "formal_export_gate_closure_run_id": args.run_id,
            })
            section["metadata"] = metadata
            client.table("bid_sections").update({
                "metadata": metadata,
                "status": "regenerating",
            }).eq("id", section["id"]).eq("project_id", args.project_id).execute()
            print(json.dumps({
                "event": "section_start",
                "index": index,
                "total": len(targets),
                "title": section.get("title"),
            }, ensure_ascii=False), flush=True)
            try:
                summary = generate_and_save_bid_section(args.project_id, section, with_images=False)
                row = client.table("bid_sections").select("content").eq("id", section["id"]).limit(1).execute().data[0]
                content = str(row.get("content") or "")
                cleaned, replacements = _clean_placeholder_text(content)
                if replacements:
                    update_bid_section_content(
                        args.project_id,
                        section["id"],
                        cleaned,
                        "generated",
                        section,
                        metadata_patch={
                            "formal_placeholder_cleaned": True,
                            "formal_placeholder_replacements": replacements,
                            "formal_export_gate_closure_run_id": args.run_id,
                        },
                    )
                    placeholder_replacements += replacements
                result = {
                    "order_index": section.get("order_index"),
                    "title": section.get("title"),
                    "status": "generated",
                    "placeholder_replacements": replacements,
                    **summary,
                }
                results.append(result)
                print(json.dumps({"event": "section_done", **result}, ensure_ascii=False), flush=True)
            except Exception as exc:  # noqa: BLE001 - report and continue with the rest of the real run
                client.table("bid_sections").update({
                    "metadata": section.get("metadata"),
                    "status": section.get("status") or "draft",
                }).eq("id", section["id"]).eq("project_id", args.project_id).execute()
                failure = {"order_index": section.get("order_index"), "title": section.get("title"), "error": str(exc)}
                failures.append(failure)
                results.append({**failure, "status": "failed", "placeholder_replacements": 0, "words": 0})
                print(json.dumps({"event": "section_failed", **failure}, ensure_ascii=False), flush=True)

        final_sections = list_bid_sections(args.project_id)
        if not args.no_generate:
            for section in final_sections:
                content = str(section.get("content") or "")
                cleaned, replacements = _clean_placeholder_text(content)
                if not replacements:
                    continue
                update_bid_section_content(
                    args.project_id,
                    str(section.get("id") or ""),
                    cleaned,
                    "generated" if str(section.get("status") or "") in {"generated", "regenerating"} else str(section.get("status") or "edited"),
                    section,
                    metadata_patch={
                        "formal_placeholder_cleaned": True,
                        "formal_placeholder_replacements": replacements,
                        "formal_export_gate_closure_run_id": args.run_id,
                    },
                )
                placeholder_replacements += replacements
            final_sections = list_bid_sections(args.project_id)
        final_prefill_report = build_bid_prefill_report(args.project_id)
        final_meta = (get_project_interpretation(args.project_id).get("analysis") or {}).get("project_meta") or {}
        prefill_state = final_meta.get("bid_prefill") if isinstance(final_meta.get("bid_prefill"), dict) else {}
        snapshot_sections = _snapshot_export_sections(final_sections)
        parent_ids = {str(row.get("parent_id")) for row in snapshot_sections if row.get("parent_id")}
        empty_leaf = [
            row for row in snapshot_sections
            if str(row.get("id") or "") not in parent_ids and not str(row.get("content") or "").strip()
        ]
        placeholder_count = sum(len(FORMAL_PLACEHOLDER_RE.findall(str(row.get("content") or ""))) for row in snapshot_sections)

    report = {
        "run_id": args.run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_id": args.project_id,
        "status": "PASS" if not failures else "PARTIAL",
        "elapsed_seconds": round(time.time() - started, 2),
        "backup_path": str(backup_path.relative_to(PROJECT_ROOT)),
        "prefill": {
            "confirmed_value_count": len(confirmed_values),
            "auto_applied": auto_applied,
            "blocked_required": blocked_required,
            "application": prefill_application,
            "final_summary": final_prefill_report.get("summary"),
        },
        "sections": {
            "target_count": len(targets),
            "generated_count": sum(1 for item in results if item.get("status") == "generated"),
            "failed_count": len(failures),
            "placeholder_replacements": placeholder_replacements,
            "results": results,
            "failures": failures,
        },
        "after": {
            "total_sections": len(snapshot_sections),
            "non_empty_sections": sum(bool(str(row.get("content") or "").strip()) for row in snapshot_sections),
            "empty_leaf_sections": len(empty_leaf),
            "empty_leaf_titles": [row.get("title") for row in empty_leaf[:30]],
            "placeholder_count": placeholder_count,
            "missing_formal_required_fields": prefill_state.get("missing_formal_required_fields") or [],
            "ready_for_formal_export": bool(prefill_state.get("ready_for_formal_export")),
        },
    }
    json_path = RUNS_DIR / f"{args.run_id}.json"
    md_path = RUNS_DIR / f"{args.run_id}.md"
    rag_json_path = RAG_RUNS_DIR / f"{args.run_id}_summary.json"
    _write_json(json_path, report)
    _write_json(rag_json_path, report)
    _write_summary(md_path, report)
    print(json.dumps({
        "report": str(md_path.relative_to(PROJECT_ROOT)),
        "status": report["status"],
        "after": report["after"],
    }, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

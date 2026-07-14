#!/usr/bin/env python3
"""生成 P2-02 当前项目章节正文复用清单与能力验证样本。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.taichang_chapter_content import (  # noqa: E402
    TAICHANG_CONTENT_PROFILE,
    build_chapter_content_manifest,
    clear_taichang_chapter_content_cache,
)


SKELETON_PATH = ROOT / "docs/development/taichang-bid-v1-data/p2_01_project_skeleton/project_bid_skeleton.json"
MAPPING_PATH = ROOT / "docs/development/taichang-bid-v1-data/p1_04_chapter_evidence_mapping/taichang_bid_evidence_mapping.json"
CHUNKS_PATH = ROOT / "docs/development/taichang-bid-v1-data/p1_05_rag_baseline/taichang_structured_rag_chunks.json"
ASSETS_PATH = ROOT / "docs/development/taichang-bid-v1-data/p1_01_ingestion/taichang_historical_bid_asset_ingestion.json"
BUNDLES_PATH = ROOT / "docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundles.json"
LEDGER_PATH = ROOT / "docs/development/taichang-bid-v1-data/p1_03_business_ledgers/taichang_p1_03_manifest.json"
PARAMETER_PATH = ROOT / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/taichang_product_parameters/taichang_product_parameter_rows.json"
PERFORMANCE_PATH = ROOT / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/taichang_project_performance_rows.json"
OUTPUT_DIR = ROOT / "docs/development/taichang-bid-v1-data/p2_02_chapter_content_reuse"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _flatten_current_chapters(skeleton: dict[str, Any]) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    product_families = ["MPP电缆保护管"] if "SL2655" in str(skeleton.get("acceptance_sample") or "") else []
    for volume in skeleton.get("volumes") or []:
        for index, chapter in enumerate(volume.get("chapters") or [], 1):
            item = json.loads(json.dumps(chapter, ensure_ascii=False))
            item["id"] = item.get("id") or f"{volume.get('type')}-{index:02d}"
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            item["metadata"] = {
                **metadata,
                "volume_type": volume.get("type"),
                "product_families": product_families,
            }
            chapters.append(item)
    return chapters


def _capability_validation_chapters() -> list[dict[str, Any]]:
    """只验证资料装配能力，不把这些章节反向加入 SL2655 目录。"""
    return [
        {"id": "capability-tech-quality", "title": "产品制造质量控制", "metadata": {"volume_type": "technical", "product_families": ["MPP电缆保护管"]}},
        {"id": "capability-tech-mpp-process", "title": "MPP生产工艺", "metadata": {"volume_type": "technical", "product_families": ["MPP电缆保护管"]}},
        {"id": "capability-business-personnel", "title": "人员组织与人员证书", "metadata": {"volume_type": "business"}},
        {"id": "capability-business-performance", "title": "项目业绩", "metadata": {"volume_type": "business"}},
    ]


def _summary_counts(manifests: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "chapter_count": len(manifests),
        "structured_row_count": len({item for manifest in manifests for item in manifest.get("structured_row_ids") or []}),
        "chunk_count": len({item for manifest in manifests for item in manifest.get("chunk_ids") or []}),
        "knowledge_asset_count": len({item for manifest in manifests for item in manifest.get("knowledge_asset_ids") or []}),
        "evidence_bundle_count": len({item for manifest in manifests for item in manifest.get("evidence_bundle_ids") or []}),
        "blocker_count": sum(len(manifest.get("blockers") or []) for manifest in manifests),
        "confirmation_count": sum(len(manifest.get("confirmations") or []) for manifest in manifests),
    }


def build() -> dict[str, Any]:
    clear_taichang_chapter_content_cache()
    skeleton = load_json(SKELETON_PATH)
    current_chapters = _flatten_current_chapters(skeleton)
    current_rows = []
    current_manifests = []
    for chapter in current_chapters:
        manifest = build_chapter_content_manifest(chapter)
        current_rows.append({
            "section_id": chapter["id"],
            "section_title": chapter.get("title"),
            "volume_type": chapter.get("metadata", {}).get("volume_type"),
            "project_rule_status": chapter.get("metadata", {}).get("project_rule_status"),
            "content_mapping_status": "matched" if manifest else "no_enterprise_content_mapping",
            "semantic_key": manifest.get("semantic_key") if manifest else None,
            "reason": "命中泰昌语义章节映射" if manifest else "本章为招标原表/项目专属表单，进入 P2-03 或按原表填充，不从企业全库随机补正文",
        })
        if manifest:
            current_manifests.append(manifest)

    capability_manifests = [
        manifest
        for chapter in _capability_validation_chapters()
        if (manifest := build_chapter_content_manifest(chapter))
    ]
    mappings = (load_json(MAPPING_PATH) or {}).get("mappings") or []
    assets = (load_json(ASSETS_PATH) or {}).get("records") or []
    baseline = {
        "verified_product_parameter_rows": len(load_json(PARAMETER_PATH)),
        "business_ledger_rows": len((load_json(LEDGER_PATH) or {}).get("rows") or []),
        "evidence_bundles": len((load_json(BUNDLES_PATH) or {}).get("bundles") or []),
        "project_performance_evidence_rows": len(load_json(PERFORMANCE_PATH)),
        "structured_rag_chunks": len(load_json(CHUNKS_PATH)),
        "historical_knowledge_assets": sum(1 for row in assets if row.get("ready_for_database_ingestion") is True),
        "semantic_mappings": len(mappings),
    }
    payload = {
        "schema_version": "taichang-p2-02-chapter-content-reuse-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "enterprise": TAICHANG_CONTENT_PROFILE["enterprise"],
        "profile": TAICHANG_CONTENT_PROFILE,
        "project": {
            "project_id": skeleton.get("project_id"),
            "project_name": skeleton.get("project_name"),
            "tender_no": skeleton.get("tender_no"),
            "acceptance_sample": skeleton.get("acceptance_sample"),
        },
        "boundary": {
            "current_tender_controls_outline": True,
            "capability_samples_are_not_current_outline": True,
            "knowledge_only_docx_allowed": False,
            "precise_values_require_structured_rows_or_primary_evidence": True,
        },
        "available_baseline": baseline,
        "current_project_section_coverage": current_rows,
        "current_project_manifests": current_manifests,
        "current_project_summary": _summary_counts(current_manifests),
        "capability_validation_manifests": capability_manifests,
        "capability_validation_summary": _summary_counts(capability_manifests),
    }
    return payload


def render_report(payload: dict[str, Any]) -> str:
    baseline = payload["available_baseline"]
    current = payload["current_project_summary"]
    capability = payload["capability_validation_summary"]
    lines = [
        "# 泰昌历史资料正文复用覆盖报告",
        "",
        "> 本报告严格区分“企业资料基线”“当前 SL2655 实际目录使用”和“能力验证样本”。能力验证章节不会反向加入当前项目目录。",
        "",
        "## 企业资料基线",
        "",
        "| 资料类型 | 数量 |",
        "| --- | ---: |",
        f"| 原始检验报告结构化参数 | {baseline['verified_product_parameter_rows']} |",
        f"| 完整业务台账 | {baseline['business_ledger_rows']} |",
        f"| 文件级证据包 | {baseline['evidence_bundles']} |",
        f"| 项目业绩证据行 | {baseline['project_performance_evidence_rows']} |",
        f"| 结构化 RAG 分块 | {baseline['structured_rag_chunks']} |",
        f"| 历史知识资产 | {baseline['historical_knowledge_assets']} |",
        "",
        "## 当前 SL2655 实际使用",
        "",
        f"当前 19 个成稿目录项中，命中企业正文映射 {current['chapter_count']} 章；使用结构化行 {current['structured_row_count']}、结构化分块 {current['chunk_count']}、历史知识资料 {current['knowledge_asset_count']}、证据包 {current['evidence_bundle_count']}。其余招标原表和固定表单不从企业全库随机补内容，转由 P2-03 原表填充。",
        "",
        "| 分册 | 当前章节 | 处理 |",
        "| --- | --- | --- |",
    ]
    for row in payload["current_project_section_coverage"]:
        status = "已建立正文资料清单" if row["content_mapping_status"] == "matched" else "保留招标原表/转 P2-03"
        lines.append(f"| {row['volume_type']} | {row['section_title']} | {status} |")
    lines.extend([
        "",
        "## 生产/质量、人员/业绩能力验证",
        "",
        f"4 个指定能力样本命中 {capability['chapter_count']} 章，使用结构化行 {capability['structured_row_count']}、分块 {capability['chunk_count']}、知识资料 {capability['knowledge_asset_count']}、证据包 {capability['evidence_bundle_count']}。这些样本用于验证 P2-02 资料装配与真实生成能力，不属于 SL2655 当前目录。",
        "",
        "## 使用边界",
        "",
        "- 当次招标动态骨架决定是否生成章节；历史标书不能新增当前项目不要求的章节。",
        "- `knowledge_only` 资料可作为正文写作背景，但不得作为精确值来源，也不得直接插入正式 DOCX。",
        "- 人员、业绩、证书、参数等精确事实必须保留结构化行、原始文件和页码；有效期、产品规格和项目适用性继续执行门禁。",
        "- SL2655 的 MPP 规格缺口仍保持阻断，不因正文复用而转为“完全响应”。",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build()
    write_json(OUTPUT_DIR / "chapter_content_manifest.json", payload)
    (OUTPUT_DIR / "泰昌历史资料正文复用覆盖报告.md").write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({
        "output": str((OUTPUT_DIR / "chapter_content_manifest.json").relative_to(ROOT)),
        "baseline": payload["available_baseline"],
        "current_project": payload["current_project_summary"],
        "capability_validation": payload["capability_validation_summary"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

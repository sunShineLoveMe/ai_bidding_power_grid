from __future__ import annotations

from unittest.mock import patch

from backend.ai.section_writer import _taichang_content_reuse_context
from backend.services.section_generation import save_generated_section
from backend.services.taichang_chapter_content import (
    build_chapter_content_manifest,
    render_grounded_chapter_draft,
)
from scripts.rag.build_taichang_p2_02_chapter_content_manifest import build


def _chapter(title: str, *, product_families: list[str] | None = None) -> dict:
    return {
        "id": title,
        "title": title,
        "metadata": {
            "volume_type": "technical" if title in {"技术特性参数表", "产品制造质量控制", "MPP生产工艺"} else "business",
            "product_families": product_families or [],
        },
    }


def test_generic_parameter_table_requires_product_family() -> None:
    assert build_chapter_content_manifest(_chapter("技术特性参数表")) is None


def test_mpp_parameter_table_uses_only_mpp_verified_rows() -> None:
    manifest = build_chapter_content_manifest(_chapter("技术特性参数表", product_families=["MPP电缆保护管"]))

    assert manifest is not None
    assert manifest["semantic_key"] == "technical_characteristics.mpp"
    assert len(manifest["structured_row_ids"]) == 17
    assert len(manifest["chunk_ids"]) == 19
    assert {row["report_no"] for row in manifest["structured_rows"]} == {"2024100312005501712"}
    assert all("CPVC" not in str(row["product_family"]) for row in manifest["structured_rows"])
    assert all("CPVC" not in str(chunk.get("source_file")) for chunk in manifest["rag_chunks"])


def test_quality_knowledge_assets_are_writing_only_not_docx_assets() -> None:
    manifest = build_chapter_content_manifest(_chapter("产品制造质量控制", product_families=["MPP电缆保护管"]))

    assert manifest is not None
    assert len(manifest["knowledge_asset_ids"]) == 15
    assert manifest["knowledge_only_docx_allowed"] is False
    assert all(asset["writing_context_allowed"] is True for asset in manifest["knowledge_assets"])
    assert all(asset["docx_allowed"] is False for asset in manifest["knowledge_assets"])


def test_personnel_and_performance_keep_structured_provenance_and_blockers() -> None:
    personnel = build_chapter_content_manifest(_chapter("人员组织与人员证书"))
    performance = build_chapter_content_manifest(_chapter("项目业绩"))

    assert personnel is not None and len(personnel["structured_row_ids"]) == 68
    assert any(row["ledger_type"] == "personnel_roster" for row in personnel["structured_rows"])
    assert performance is not None and len(performance["structured_row_ids"]) == 2
    assert performance["structured_rows"][0]["raw"]["tender_no"] == "0322AB"
    assert any("合同签署日期" in blocker for blocker in performance["blockers"])


def test_grounded_renderer_uses_only_visible_facts_and_no_internal_ids() -> None:
    chapters = [
        _chapter("产品制造质量控制", product_families=["MPP电缆保护管"]),
        _chapter("MPP生产工艺", product_families=["MPP电缆保护管"]),
        _chapter("人员组织与人员证书"),
        _chapter("项目业绩"),
    ]
    contents = [render_grounded_chapter_draft(build_chapter_content_manifest(chapter)) for chapter in chapters]

    assert "06925Q10172R4" in contents[0] and "15 项" in contents[0]
    assert "2024100312005501712" in contents[1] and "不能替代 MPP 专属生产工艺文件" in contents[1]
    assert "共 65 行" in contents[2] and "T130602197408170641" in contents[2]
    assert "0322AB" in contents[3] and "合同签署日期" in contents[3]
    assert all(term not in "\n".join(contents) for term in ("taichang-", "technical-media-", "row-"))


def test_general_project_never_loads_taichang_chapter_manifest() -> None:
    chapter = _chapter("人员组织与人员证书")
    context = _taichang_content_reuse_context({"project_mode": "general"}, chapter, {})

    assert "不加载泰昌专版" in context
    assert "chapter_content_manifest" not in chapter["metadata"]


def test_taichang_project_persists_manifest_on_chapter_metadata() -> None:
    chapter = _chapter("技术特性参数表")
    context = _taichang_content_reuse_context(
        {"project_mode": "taichang_reuse"},
        chapter,
        {"matchedSupportedTerms": ["MPP", "电缆保护管"]},
    )

    manifest = chapter["metadata"]["chapter_content_manifest"]
    assert manifest["semantic_key"] == "technical_characteristics.mpp"
    assert "2024100312005501712" in context
    assert "禁止作为 DOCX 正式图片" not in context


def test_saved_section_metadata_contains_chapter_content_manifest() -> None:
    chapter = _chapter("项目业绩")
    chapter["metadata"]["chapter_content_manifest"] = build_chapter_content_manifest(chapter)
    with patch("backend.services.section_generation.update_bid_section_content") as update:
        update.return_value = {"id": "saved-section"}
        result = save_generated_section("project-1", chapter, "## 项目业绩\n\n正文")

    assert result["id"] == "saved-section"
    metadata_patch = update.call_args.kwargs["metadata_patch"]
    assert metadata_patch["chapter_content_manifest"]["semantic_key"] == "performance.project_evidence"


def test_p2_02_artifact_separates_current_outline_from_capability_samples() -> None:
    payload = build()

    assert payload["available_baseline"] == {
        "verified_product_parameter_rows": 36,
        "business_ledger_rows": 84,
        "evidence_bundles": 16,
        "project_performance_evidence_rows": 2,
        "structured_rag_chunks": 166,
        "historical_knowledge_assets": 133,
        "semantic_mappings": 20,
    }
    assert payload["current_project_summary"]["chapter_count"] == 2
    assert payload["current_project_summary"]["chunk_count"] == 19
    assert payload["capability_validation_summary"]["chapter_count"] == 4
    assert payload["capability_validation_summary"]["chunk_count"] == 91
    assert payload["boundary"]["capability_samples_are_not_current_outline"] is True

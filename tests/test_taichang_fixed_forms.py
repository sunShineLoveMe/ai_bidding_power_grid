from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from backend.services.taichang_fixed_forms import (
    audit_fixed_form_docx,
    build_p2_03_fixed_form_payload,
    export_fixed_form_manifest_to_docx,
    extract_fixed_form_inventory,
    load_parameter_rows,
    render_fixed_form_draft,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "assets/template_words/包1_完整招标文件_92475576192439826"
MAIN_TENDER = PACKAGE_ROOT / "SL2655招标文件-预审.docx"
TECHNICAL_SPEC = PACKAGE_ROOT / "国家电网公司总部_一级省公司固化ID修编（9111-500021520-00001）/改性聚丙烯（MPP）电缆导管专用技术规范（内径200mm，壁厚14.0，断裂延伸率≥200%）.docx"
PARAMETER_ROWS = (
    ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0"
    / "staging/taichang_product_parameters/taichang_product_parameter_rows.json"
)


def _payload():
    return build_p2_03_fixed_form_payload(
        MAIN_TENDER,
        [TECHNICAL_SPEC],
        load_parameter_rows(PARAMETER_ROWS),
    )


def test_inventory_finds_current_tender_forms_by_semantics_and_preserves_ooxml_trace() -> None:
    inventory = extract_fixed_form_inventory(MAIN_TENDER)

    assert inventory["complete"] is True
    assert {key: row["table_index"] for key, row in inventory["forms"].items()} == {
        "business_deviation": 18,
        "personnel_relationship": 19,
        "technical_deviation": 23,
        "technical_characteristics": 25,
    }
    relationship = inventory["forms"]["personnel_relationship"]
    assert relationship["column_count"] == 13
    assert relationship["table_xml_sha256"]
    assert any(cell["grid_span"] > 1 for row in relationship["rows"] for cell in row)
    assert relationship["parser"] == "native_docx_ooxml"
    assert relationship["mineru_invoked"] is False


def test_sl2655_parameter_manifest_keeps_all_guarantees_blank_and_classifies_gaps() -> None:
    response = _payload()["technical_parameter_response"]

    assert response["row_count"] == 22
    assert response["coverage_counts"] == {"partial_match": 10, "mismatch": 3, "unknown": 9}
    assert response["filled_guarantee_count"] == 0
    assert response["formal_ready"] is False
    assert all(row["bidder_guaranteed_value"] == "" for row in response["response_rows"])

    ring = next(row for row in response["response_rows"] if row["parameter_name"] == "环刚度")
    elongation = next(row for row in response["response_rows"] if row["parameter_name"] in {"断裂伸长率", "断裂延伸率"})
    assert ring["coverage_status"] == "partial_match"
    assert ring["candidate_inspection_result"] == "66.40"
    assert ring["formal_value_allowed"] is False
    assert elongation["coverage_status"] == "mismatch"
    assert elongation["candidate_inspection_result"] == "176"
    assert elongation["numeric_compliance"] is False


def test_fixed_form_renderer_uses_original_rows_without_filling_candidate_values() -> None:
    manifest = _payload()["section_manifests"]["技术特性参数表"]
    content = render_fixed_form_draft(manifest)

    assert "| 序号 | 参数名称 | 单位 | 项目需求值或表述 | 投标人保证值 | 备注 |" in content
    assert "| 1.2 | 环刚度 | kN/m2 | 大于等于24 |  |" in content
    assert "| 1.8 | 断裂伸长率 | / | 大于等于200 |  |" in content
    assert "66.40" not in content.split("本表按当次招标专项技术规范")[0]
    assert "176%" not in content.split("本表按当次招标专项技术规范")[0]
    assert "完全响应" not in content


def test_section_stream_bypasses_llm_for_fixed_form() -> None:
    from backend.ai import section_writer

    manifest = _payload()["section_manifests"]["技术特性参数表"]
    chapter = {"id": "section-id", "title": "技术特性参数表", "metadata": {"fixed_form_manifest": manifest}}
    with patch("backend.ai.section_writer.stream_dashscope_api") as stream_model:
        events = list(section_writer.stream_bid_section("project-id", chapter))

    assert any(event["type"] == "fixed_form_renderer" for event in events)
    assert any(event["type"] == "done" for event in events)
    assert "大于等于200" in "".join(event.get("content", "") for event in events)
    stream_model.assert_not_called()


def test_technical_form_docx_clones_two_source_tables_without_filling_guarantees(tmp_path: Path) -> None:
    manifest = _payload()["section_manifests"]["技术特性参数表"]
    output, report = export_fixed_form_manifest_to_docx(manifest, tmp_path / "技术特性参数表.docx")

    from docx import Document

    exported = Document(output)
    assert report["renderer"] == "native_docx_ooxml_clone"
    assert report["source_table_indexes"] == [1, 2]
    assert report["table_shapes"] == [{"rows": 14, "columns": 6}, {"rows": 10, "columns": 6}]
    assert report["exact_table_xml_preserved"] is True
    assert report["guarantee_value_filled_count"] == 0
    assert all(not row.cells[4].text.strip() for table in exported.tables for row in table.rows[1:])
    body_tags = [node.tag.rsplit("}", 1)[-1] for node in exported.element.body]
    first_table = body_tags.index("tbl")
    assert body_tags[first_table:first_table + 3] == ["tbl", "p", "tbl"]
    audit = audit_fixed_form_docx(manifest, output)
    assert audit["passed"] is True
    assert audit["actual_table_count"] == 2
    assert audit["guarantee_value_filled_count"] == 0


def test_personnel_form_docx_preserves_two_level_merged_header(tmp_path: Path) -> None:
    manifest = _payload()["section_manifests"]["投标人与国家电网公司系统人员关系说明"]
    _, report = export_fixed_form_manifest_to_docx(manifest, tmp_path / "人员关系说明.docx")

    assert report["source_table_indexes"] == [19]
    assert report["table_shapes"] == [{"rows": 3, "columns": 13}]
    assert report["exact_table_xml_preserved"] is True

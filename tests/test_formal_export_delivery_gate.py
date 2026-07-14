from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from backend.services.formal_export_delivery_gate import build_formal_export_delivery_gate


def _docx(path: Path, text: str = "河北泰昌电力器材科技有限公司投标文件") -> Path:
    with ZipFile(path, "w") as package:
        package.writestr("word/document.xml", f"<w:document>{text}</w:document>")
        package.writestr("word/media/image1.png", b"image")
    return path


def _selection() -> dict:
    return {
        "selected": 1,
        "selection_policy": "chapter_to_evidence_bundle_to_original_page_sequence",
        "formal_readiness": {
            "ready": True,
            "empty_section_count": 0,
            "placeholder_count": 0,
            "missing_formal_required_fields": [],
        },
        "evidence_bundle_selection": {
            "selected_page_count": 1,
            "skipped_bundle_count": 0,
        },
        "manifest": [{
            "asset_id": "asset-1",
            "asset_policy": {
                "enterprise": "泰昌",
                "doc_owner": "河北泰昌电力器材科技有限公司",
                "source_domain": "enterprise_fact",
                "quality_tier": "formal_bid_ready",
                "formal_bid_ready": True,
                "bundle_allowed_for_bid": True,
                "allowed_for_bid": True,
                "reference_only": False,
                "exclude_from_docx": False,
                "full_page": True,
            },
        }],
        "fixed_form_manifests": [],
    }


def test_post_export_gate_allows_formal_delivery_only_when_both_layers_pass(tmp_path: Path) -> None:
    gate = build_formal_export_delivery_gate(
        output_path=_docx(tmp_path / "formal.docx"),
        scope="full",
        pre_export_gate={"can_formal_export": True, "export_mode": "formal"},
        image_selection=_selection(),
        image_conversion={"inserted": 1, "failed": 0},
        field_refresh={"status": "refreshed", "manual_refresh_required": False},
    )

    assert gate["artifact_ready"] is True
    assert gate["can_formal_deliver"] is True
    assert gate["export_mode"] == "formal"


def test_post_export_gate_downgrades_to_draft_on_asset_or_docx_violation(tmp_path: Path) -> None:
    selection = _selection()
    selection["manifest"][0]["asset_policy"]["source_domain"] = "reference_template"
    gate = build_formal_export_delivery_gate(
        output_path=_docx(tmp_path / "draft.docx", "河北豪乾资质"),
        scope="full",
        pre_export_gate={"can_formal_export": True, "export_mode": "formal"},
        image_selection=selection,
        image_conversion={"inserted": 0, "failed": 1},
        field_refresh={"status": "skipped", "manual_refresh_required": True},
    )

    assert gate["artifact_ready"] is False
    assert gate["can_formal_deliver"] is False
    assert gate["export_mode"] == "draft"
    assert {row["id"] for row in gate["items"] if row["status"] == "blocked"} >= {
        "POST-003", "POST-004", "POST-005", "POST-007",
    }


def test_post_export_gate_keeps_artifact_pass_but_draft_when_business_gate_blocks(tmp_path: Path) -> None:
    gate = build_formal_export_delivery_gate(
        output_path=_docx(tmp_path / "business-draft.docx"),
        scope="full",
        pre_export_gate={"can_formal_export": False, "export_mode": "draft"},
        image_selection=_selection(),
        image_conversion={"inserted": 1, "failed": 0},
        field_refresh={"status": "refreshed", "manual_refresh_required": False},
    )

    assert gate["artifact_ready"] is True
    assert gate["source_ready"] is False
    assert gate["can_formal_deliver"] is False
    assert gate["export_mode"] == "draft"


def test_general_project_without_taichang_asset_policy_keeps_compatibility(tmp_path: Path) -> None:
    selection = _selection()
    selection.pop("selection_policy")
    selection["manifest"] = [{"asset_id": "general-asset"}]
    selection.pop("evidence_bundle_selection")
    gate = build_formal_export_delivery_gate(
        output_path=_docx(tmp_path / "general.docx"),
        scope="full",
        pre_export_gate={"can_formal_export": True, "export_mode": "formal"},
        image_selection=selection,
        image_conversion={"inserted": 1, "failed": 0},
        field_refresh={"status": "refreshed", "manual_refresh_required": False},
    )

    assert gate["artifact_ready"] is True
    assert gate["can_formal_deliver"] is True

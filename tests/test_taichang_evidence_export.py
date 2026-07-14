from __future__ import annotations

import json
from pathlib import Path

from backend.services.taichang_evidence_export import build_taichang_evidence_export_plan


ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundles.json"


def _assets() -> list[dict]:
    payload = json.loads(BUNDLES.read_text(encoding="utf-8"))
    return [
        {
            "id": page["asset_id"],
            "title": page["bundle_title"],
            "metadata": {
                "full_page": True,
                "asset_visual_type": "full_page_document_image",
                "allowed_for_bid": True,
                "enterprise": "泰昌",
                "source_domain": "enterprise_fact",
            },
        }
        for page in payload["pages"]
    ]


def _section(section_id: str, title: str, bundle_ids: list[str], order_index: int) -> dict:
    return {
        "id": section_id,
        "title": title,
        "order_index": order_index,
        "metadata": {
            "volume_type": "technical" if "参数" in title else "business",
            "chapter_content_manifest": {"evidence_bundle_ids": bundle_ids},
        },
    }


def test_sl2655_plan_selects_only_mapped_license_and_mpp_bundle_in_page_order() -> None:
    sections = [
        _section("basic", "投标人基本情况表", ["taichang-evidence-76ac5c6984a28811742d"], 6),
        _section("params", "技术特性参数表", ["taichang-evidence-5233af6e2133a8e25641"], 16),
    ]
    plan = build_taichang_evidence_export_plan(
        sections,
        _assets(),
        material_scope={"MPP电缆保护管"},
        asset_allowed=lambda asset: bool(asset["metadata"]["allowed_for_bid"]),
    )

    assert plan["selected_bundle_count"] == 2
    assert plan["selected_page_count"] == 6
    assert plan["skipped_bundle_count"] == 0
    assert [row["bundle_title"] for row in plan["selected_bundles"]] == [
        "泰昌营业执照",
        "泰昌MPP电缆保护管检验报告",
    ]
    mpp = plan["selected_bundles"][1]
    assert [page["page_no"] for page in mpp["pages"]] == [1, 2, 3, 4, 5]


def test_bundle_is_skipped_atomically_when_one_page_asset_is_missing() -> None:
    section = _section("params", "技术特性参数表", ["taichang-evidence-5233af6e2133a8e25641"], 1)
    assets = [asset for asset in _assets() if asset["id"] != "048b1963-fb91-49f4-99e0-ee282ca1eb7d"]
    plan = build_taichang_evidence_export_plan([section], assets, material_scope={"MPP电缆保护管"})

    assert plan["selected_bundle_count"] == 0
    assert plan["selected_page_count"] == 0
    assert plan["skipped_bundle_count"] == 1
    assert "原页资产不存在" in plan["skipped_bundles"][0]["reason"]


def test_bundle_is_skipped_atomically_when_budget_cannot_hold_all_pages() -> None:
    section = _section("performance", "项目业绩", ["taichang-evidence-68f40342eb06721cacc8"], 1)
    plan = build_taichang_evidence_export_plan([section], _assets(), max_pages=16)

    assert plan["selected_bundle_count"] == 0
    assert plan["selected_page_count"] == 0
    assert "整包 17 页" in plan["skipped_bundles"][0]["reason"]


def test_cross_product_bundle_is_rejected() -> None:
    section = _section("params", "技术特性参数表", ["taichang-evidence-4c9d64c00d89cb7b78f2"], 1)
    plan = build_taichang_evidence_export_plan([section], _assets(), material_scope={"MPP电缆保护管"})

    assert plan["selected_bundle_count"] == 0
    assert "产品范围" in plan["skipped_bundles"][0]["reason"]


def test_bundle_with_non_continuous_global_order_is_skipped(tmp_path: Path) -> None:
    payload = json.loads(BUNDLES.read_text(encoding="utf-8"))
    target_id = "taichang-evidence-5233af6e2133a8e25641"
    target_pages = [row for row in payload["pages"] if row["evidence_bundle_id"] == target_id]
    target_pages[2]["global_order"] = 2
    bundle_path = tmp_path / "bundles.json"
    bundle_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    section = _section("params", "技术特性参数表", [target_id], 1)
    plan = build_taichang_evidence_export_plan(
        [section],
        _assets(),
        material_scope={"MPP电缆保护管"},
        bundle_path=bundle_path,
    )

    assert plan["selected_bundle_count"] == 0
    assert "全局页序" in plan["skipped_bundles"][0]["reason"]

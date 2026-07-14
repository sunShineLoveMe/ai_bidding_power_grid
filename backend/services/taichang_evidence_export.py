"""泰昌 P2-04 正式证据包确定性编排。

只消费 P1-04 已明确写入章节 ``chapter_content_manifest`` 的证据包，不对全库做
相似度选图。证据包按原始页序原子插入：任何一页缺失、不满足正式资产门禁或
整包超出页数预算时，整包跳过，禁止截断后伪装为完整证明材料。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = REPO_ROOT / "docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundles.json"


def _load_bundles(path: str | Path = BUNDLE_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _metadata(asset: dict[str, Any]) -> dict[str, Any]:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    specs = asset.get("specs") if isinstance(asset.get("specs"), dict) else {}
    return {**specs, **metadata}


def _asset_is_full_page(asset: dict[str, Any]) -> bool:
    metadata = _metadata(asset)
    visual_type = str(metadata.get("asset_visual_type") or "")
    return bool(metadata.get("full_page")) and visual_type.startswith("full_page")


def build_taichang_evidence_export_plan(
    sections: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    *,
    material_scope: set[str] | None = None,
    max_pages: int = 24,
    asset_allowed: Callable[[dict[str, Any]], bool] | None = None,
    bundle_path: str | Path = BUNDLE_PATH,
) -> dict[str, Any]:
    """按真实章节映射生成完整证据包导出计划。"""
    payload = _load_bundles(bundle_path)
    bundles = {str(row.get("evidence_bundle_id")): row for row in payload.get("bundles") or []}
    pages_by_bundle: dict[str, list[dict[str, Any]]] = {}
    for page in payload.get("pages") or []:
        pages_by_bundle.setdefault(str(page.get("evidence_bundle_id")), []).append(page)
    for pages in pages_by_bundle.values():
        pages.sort(key=lambda row: (int(row.get("global_order") or 0), int(row.get("page_no") or 0)))

    assets_by_id = {str(asset.get("id")): asset for asset in assets if asset.get("id")}
    selected_bundles: list[dict[str, Any]] = []
    skipped_bundles: list[dict[str, Any]] = []
    seen_bundle_ids: set[str] = set()
    selected_pages = 0
    scope = set(material_scope or set())

    ordered_sections = sorted(
        sections,
        key=lambda row: (int(row.get("order_index") or 0), str(row.get("id") or "")),
    )
    for section in ordered_sections:
        metadata = section.get("metadata") if isinstance(section.get("metadata"), dict) else {}
        manifest = metadata.get("chapter_content_manifest") if isinstance(metadata.get("chapter_content_manifest"), dict) else {}
        for bundle_id in manifest.get("evidence_bundle_ids") or []:
            bundle_id = str(bundle_id)
            if not bundle_id or bundle_id in seen_bundle_ids:
                continue
            seen_bundle_ids.add(bundle_id)
            bundle = bundles.get(bundle_id)
            reason = None
            if not bundle:
                reason = "证据包清单中不存在该 ID。"
            elif not bundle.get("allowed_for_bid"):
                reason = f"证据包状态为 {bundle.get('usage_status') or '不可用于正式标书'}。"
            elif not bundle.get("page_sequence_complete"):
                reason = "证据包原始页序不完整。"
            elif bundle.get("warnings"):
                reason = "证据包仍有未解决告警。"

            product_families = set(bundle.get("product_families") or []) if bundle else set()
            if not reason and scope and product_families and product_families.isdisjoint(scope):
                reason = f"证据包产品范围 {sorted(product_families)} 与本包 {sorted(scope)} 不一致。"

            source_pages = pages_by_bundle.get(bundle_id, [])
            resolved_pages: list[dict[str, Any]] = []
            if not reason:
                if len(source_pages) != int(bundle.get("page_count") or 0):
                    reason = "证据包页记录数量与声明页数不一致。"
                elif [int(row.get("global_order") or 0) for row in source_pages] != list(range(1, len(source_pages) + 1)):
                    reason = "证据包全局页序不是从 1 开始的连续序列。"
                elif len({str(row.get("asset_id") or "") for row in source_pages}) != len(source_pages):
                    reason = "证据包包含重复原页资产。"
                else:
                    for page in source_pages:
                        asset_id = str(page.get("asset_id") or "")
                        asset = assets_by_id.get(asset_id)
                        if not asset:
                            reason = f"原页资产不存在：{asset_id or '未配置'}。"
                            break
                        if asset_allowed and not asset_allowed(asset):
                            reason = f"原页资产未通过正式标书门禁：{asset_id}。"
                            break
                        if not _asset_is_full_page(asset):
                            reason = f"原页资产不是整页渲染图：{asset_id}。"
                            break
                        resolved_pages.append({
                            "asset_id": asset_id,
                            "page_no": page.get("page_no"),
                            "global_order": page.get("global_order"),
                            "component": page.get("component"),
                            "source_file": page.get("source_file"),
                            "asset_title": asset.get("title"),
                        })

            if not reason and selected_pages + len(resolved_pages) > max_pages:
                reason = f"整包 {len(resolved_pages)} 页加入后超过 {max_pages} 页预算，按原子策略整包跳过。"

            if reason:
                skipped_bundles.append({
                    "evidence_bundle_id": bundle_id,
                    "bundle_title": bundle.get("bundle_title") if bundle else None,
                    "section_id": section.get("id"),
                    "section_title": section.get("title"),
                    "reason": reason,
                })
                continue

            selected_pages += len(resolved_pages)
            selected_bundles.append({
                "evidence_bundle_id": bundle_id,
                "bundle_title": bundle.get("bundle_title"),
                "bundle_kind": bundle.get("bundle_kind"),
                "evidence_type": bundle.get("evidence_type"),
                "section_id": section.get("id"),
                "section_title": section.get("title"),
                "volume_type": metadata.get("volume_type"),
                "product_families": sorted(product_families),
                "page_count": len(resolved_pages),
                "page_sequence_complete": True,
                "pages": resolved_pages,
            })

    return {
        "schema_version": "taichang_evidence_export_plan.v1",
        "selection_policy": "chapter_to_evidence_bundle_to_original_page_sequence",
        "bundle_atomicity": "all_pages_or_skip",
        "max_pages": max_pages,
        "material_scope": sorted(scope),
        "selected_bundle_count": len(selected_bundles),
        "selected_page_count": selected_pages,
        "skipped_bundle_count": len(skipped_bundles),
        "selected_bundles": selected_bundles,
        "skipped_bundles": skipped_bundles,
    }


def evidence_pages_by_section(plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for bundle in plan.get("selected_bundles") or []:
        section_id = str(bundle.get("section_id") or "")
        if section_id:
            result.setdefault(section_id, []).append(bundle)
    return result

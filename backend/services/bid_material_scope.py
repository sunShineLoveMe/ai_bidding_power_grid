from __future__ import annotations

import json
import re
from typing import Any, Iterable


KNOWN_MATERIAL_FAMILIES = ("CPVC", "MPP", "NHAP")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _iter_scope_values(source: Any) -> Iterable[str]:
    if isinstance(source, dict):
        for key in (
            "package_name",
            "material_category",
            "goods_list_summary",
            "technical_parameter_summary",
            "taichang_parameter_match_summary",
        ):
            value = source.get(key)
            if value:
                yield _text(value)
        for key in ("cover_fields", "bid_prefill", "project_meta"):
            nested = source.get(key)
            if isinstance(nested, dict):
                yield from _iter_scope_values(nested)
        confirmed = source.get("confirmed_values")
        if isinstance(confirmed, dict):
            yield from _iter_scope_values(confirmed)
        return
    yield _text(source)


def material_scope_from_context(*contexts: Any) -> set[str]:
    """Return material families explicitly present in confirmed tender context.

    The scope is intentionally conservative: it only recognizes well-known
    product families that appear in project meta, prefill confirmations, goods
    summaries or package names.  Empty scope means "do not filter".
    """
    blob = "\n".join(part for context in contexts for part in _iter_scope_values(context))
    normalized = blob.upper()
    return {family for family in KNOWN_MATERIAL_FAMILIES if family in normalized}


def title_has_out_of_scope_material(title: Any, allowed_families: set[str] | None) -> bool:
    allowed = {family.upper() for family in (allowed_families or set())}
    if not allowed:
        return False
    text = _text(title).upper()
    mentioned = {family for family in KNOWN_MATERIAL_FAMILIES if re.search(rf"(?<![A-Z0-9]){family}(?![A-Z0-9])", text)}
    return bool(mentioned - allowed)


def filter_sections_by_material_scope(sections: list[dict[str, Any]], allowed_families: set[str] | None) -> list[dict[str, Any]]:
    """Drop sections that explicitly target a material family outside this package.

    Descendants of a removed container are also removed.  Generic sections and
    sections that mention no known family are preserved.
    """
    allowed = {family.upper() for family in (allowed_families or set())}
    if not allowed:
        return sections

    removed_ids: set[str] = set()
    filtered: list[dict[str, Any]] = []
    for section in sorted(sections, key=lambda item: (int(item.get("order_index") or 0), str(item.get("id") or ""))):
        section_id = str(section.get("id") or "")
        parent_id = str(section.get("parent_id") or "")
        if parent_id and parent_id in removed_ids:
            if section_id:
                removed_ids.add(section_id)
            continue
        if title_has_out_of_scope_material(section.get("title"), allowed):
            if section_id:
                removed_ids.add(section_id)
            continue
        filtered.append(section)
    return filtered


def prune_outline_by_material_scope(outline: dict[str, Any], allowed_families: set[str] | None) -> dict[str, Any]:
    allowed = {family.upper() for family in (allowed_families or set())}
    if not allowed:
        return outline

    def prune_node(node: dict[str, Any]) -> dict[str, Any] | None:
        if title_has_out_of_scope_material(node.get("title"), allowed):
            return None
        children = [child for child in (prune_node(child) for child in node.get("children") or []) if child]
        next_node = {**node}
        if node.get("children") is not None:
            next_node["children"] = children
        return next_node

    next_outline = {**outline}
    if isinstance(outline.get("chapters"), list):
        next_outline["chapters"] = [node for node in (prune_node(item) for item in outline.get("chapters") or []) if node]
    if isinstance(outline.get("volumes"), list):
        next_volumes: list[dict[str, Any]] = []
        for volume in outline.get("volumes") or []:
            volume_copy = {**volume}
            if isinstance(volume.get("chapters"), list):
                volume_copy["chapters"] = [node for node in (prune_node(item) for item in volume.get("chapters") or []) if node]
            next_volumes.append(volume_copy)
        next_outline["volumes"] = next_volumes
    return next_outline

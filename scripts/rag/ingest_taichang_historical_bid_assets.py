#!/usr/bin/env python3
"""提取并增量入库泰昌历史标书中的低风险 Word 内嵌资料。

默认只执行 dry-run：提取全部已自动接收候选、重算质量指标，并与真实
``knowledge_assets`` 文件做业务身份、字节哈希和视觉三层复核。只有显式传入
``--execute`` 才会把通过门禁的资料以 ``knowledge_only`` 写入数据库。

历史 Word 内嵌图始终不是正式投标图片：脚本强制 ``allowed_for_bid=false``，
不得被 DOCX 自动选图，也不得作为精确技术参数、证书有效性或报告实测值来源。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

from dotenv import load_dotenv
from PIL import Image, ImageChops, ImageOps, ImageStat
from psycopg.rows import dict_row


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.postgres_compat import _database_url  # noqa: E402
from backend.db.postgres_pool import pooled_connection  # noqa: E402
from backend.db.supabase_repo import create_knowledge_asset, upload_knowledge_asset_file  # noqa: E402
from backend.rag.vector_store import get_embeddings, init_ali_client  # noqa: E402
from scripts.rag.deduplicate_taichang_historical_bid_assets import (  # noqa: E402
    hamming_distance,
    image_profile,
)


ENTERPRISE = "河北泰昌电力器材科技有限公司"
BATCH_ID = "customer_taichang_historical_bid_20260713_p1_01_knowledge_only_v1"
DATA_ROOT = PROJECT_ROOT / "docs/development/taichang-bid-v1-data"
DEFAULT_APPROVED = DATA_ROOT / "p0_06_review/asset_ingestion_candidates.json"
DEFAULT_INVENTORIES = (
    DATA_ROOT / "taichang_technical_bid_candidate_inventory.json",
    DATA_ROOT / "taichang_business_bid_candidate_inventory.json",
)
DEFAULT_EXTRACT_ROOT = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_taichang_historical_bid_20260713"
    / "p1_01_knowledge_assets"
)
DEFAULT_REPORT_DIR = DATA_ROOT / "p1_01_ingestion"

MIN_IMAGE_BYTES = 30 * 1024
MIN_IMAGE_SIDE = 500
VISUAL_REVIEW_MAX_DHASH = 6
FORBIDDEN_VISIBLE_PATTERNS = (
    r"\b(?:taichang|power_grid|production_capacity|green_low_carbon)\b",
    r"\b[a-f0-9]{24,}\b",
    r"页面[_-]?\d+",
    r"原图",
)
BLOCKED_CONTENT_HINTS = ("二维码", "印章", "签名", "页脚", "局部表格", "局部文字")


@dataclass(frozen=True)
class BaselineVisual:
    asset_id: str
    title: str
    source_file: str
    path: Path
    sha256: str
    profile: dict[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def _safe_chinese_file_name(title: str, suffix: str) -> str:
    clean = re.sub(r"[^\w\u4e00-\u9fff（）()、，.-]+", "", title, flags=re.UNICODE)
    clean = clean.replace("_", "").strip(" .-_、，")
    if not re.search(r"[\u4e00-\u9fff]", clean):
        raise ValueError(f"资产文件名缺少中文业务含义: {title}")
    return f"{clean[:100]}{suffix.lower()}"


def _normalize_business_name(value: Any) -> str:
    text = _text(value)
    text = text.replace(ENTERPRISE, "").replace("泰昌", "")
    text = re.sub(r"第\s*\d+\s*页", "", text)
    text = re.sub(r"知识资料第\d+项", "", text)
    text = re.sub(r"历史标书内嵌资料", "", text)
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text).lower()


def _source_group_title(row: dict[str, Any]) -> str:
    leaf = _text(row.get("source_section")).split("/")[-1].strip()
    leaf = re.sub(r"^[（(]?\d+(?:\.\d+)*[）).、]?\s*", "", leaf).strip()
    return leaf or _text(row.get("evidence_type_label")) or "企业资料"


def _source_display_name(row: dict[str, Any]) -> str:
    group = _source_group_title(row)
    return f"泰昌{group}（历史标书内嵌资料）"


def _visible_violations(values: Iterable[Any]) -> list[str]:
    blob = "\n".join(_text(value) for value in values if _text(value))
    return [pattern for pattern in FORBIDDEN_VISIBLE_PATTERNS if re.search(pattern, blob, flags=re.I)]


def _load_approved(path: Path) -> list[dict[str, Any]]:
    payload = _json(path)
    rows = payload.get("records") or []
    if not rows:
        raise RuntimeError(f"批准清单为空: {path}")
    invalid = [row.get("candidate_id") for row in rows if not row.get("ready_for_ingestion")]
    if invalid:
        raise RuntimeError(f"批准清单包含未就绪候选: {invalid[:10]}")
    return rows


def _load_inventory_rows(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        for row in _json(path).get("records") or []:
            candidate_id = _text(row.get("candidate_id"))
            if candidate_id:
                result[candidate_id] = row
    return result


def _extract_candidates(
    approved_rows: list[dict[str, Any]],
    inventory_rows: dict[str, dict[str, Any]],
    extract_root: Path,
) -> list[dict[str, Any]]:
    extract_root.mkdir(parents=True, exist_ok=True)
    archives: dict[str, ZipFile] = {}
    extracted: list[dict[str, Any]] = []
    try:
        for approved in approved_rows:
            candidate_id = _text(approved.get("candidate_id"))
            original = inventory_rows.get(candidate_id)
            if not original:
                raise RuntimeError(f"候选缺少原始 inventory 记录: {candidate_id}")
            source_file = PROJECT_ROOT / _text(original.get("source_file"))
            media_target = _text(original.get("media_target"))
            if not source_file.is_file() or not media_target:
                raise RuntimeError(f"候选来源不可用: {candidate_id}, {source_file}, {media_target}")
            archive_key = str(source_file.resolve())
            archive = archives.get(archive_key)
            if archive is None:
                archive = ZipFile(source_file)
                archives[archive_key] = archive
            data = archive.read(media_target)
            actual_sha = _sha256_bytes(data)
            expected_sha = _text(original.get("media_sha256") or approved.get("media_sha256"))
            if expected_sha and expected_sha != actual_sha:
                raise RuntimeError(
                    f"Word 媒体哈希变化，禁止继续: {candidate_id}, expected={expected_sha}, actual={actual_sha}"
                )

            suffix = Path(media_target).suffix.lower() or ".bin"
            title = _text(approved.get("reviewed_title") or approved.get("title"))
            file_name = _safe_chinese_file_name(title, suffix)
            output_path = extract_root / file_name
            if output_path.exists() and _sha256_file(output_path) != actual_sha:
                raise RuntimeError(f"中文文件名发生内容冲突: {output_path}")
            output_path.write_bytes(data)
            extracted.append(
                {
                    **approved,
                    "media_target": media_target,
                    "media_relationship_id": original.get("media_relationship_id"),
                    "media_width": original.get("media_width"),
                    "media_height": original.get("media_height"),
                    "actual_media_sha256": actual_sha,
                    "source_docx_sha256": _sha256_file(source_file),
                    "extracted_path": _relative(output_path),
                    "extracted_file_name": file_name,
                    "source_group_title": _source_group_title(approved),
                    "source_display_name_after_ingestion": _source_display_name(approved),
                }
            )
    finally:
        for archive in archives.values():
            archive.close()
    return extracted


def _resolve_asset_path(row: dict[str, Any]) -> Path | None:
    local_path = _text(row.get("local_path"))
    if local_path:
        path = PROJECT_ROOT / local_path
        if path.is_file():
            return path
    bucket = _text(row.get("storage_bucket"))
    storage_path = _text(row.get("storage_path"))
    if bucket and storage_path:
        path = PROJECT_ROOT / "storage" / bucket / storage_path
        if path.is_file():
            return path
    return None


def _fetch_existing_assets() -> list[dict[str, Any]]:
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                select id, title, description, category, asset_type, file_name, local_path,
                       storage_bucket, storage_path, metadata, specs, status
                from public.knowledge_assets
                where coalesce(metadata->>'enterprise', '') in ('泰昌', '河北泰昌电力器材科技有限公司')
                   or coalesce(metadata->>'doc_owner', '') in ('泰昌', '河北泰昌电力器材科技有限公司')
                   or title ilike %s
                order by created_at nulls last, id
                """,
                ["%泰昌%"],
            ).fetchall()
        ]


def _baseline_visuals(rows: list[dict[str, Any]]) -> tuple[list[BaselineVisual], list[dict[str, Any]]]:
    visuals: list[BaselineVisual] = []
    missing: list[dict[str, Any]] = []
    for row in rows:
        path = _resolve_asset_path(row)
        if not path:
            missing.append({"asset_id": str(row.get("id")), "title": row.get("title")})
            continue
        try:
            data = path.read_bytes()
            profile = image_profile(data)
        except Exception as exc:
            missing.append({"asset_id": str(row.get("id")), "title": row.get("title"), "error": str(exc)})
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        visuals.append(
            BaselineVisual(
                asset_id=str(row.get("id")),
                title=_text(row.get("title")),
                source_file=_text(metadata.get("source_file")),
                path=path,
                sha256=_sha256_bytes(data),
                profile=profile,
            )
        )
    return visuals, missing


def _business_identity_index(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        names = [row.get("title"), metadata.get("source_display_name")]
        source_file = _text(metadata.get("source_file"))
        if source_file:
            names.append(Path(source_file).stem)
        for name in names:
            key = _normalize_business_name(name)
            if len(key) >= 5:
                index.setdefault(key, []).append(str(row.get("id")))
    return index


def _image_quality(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    profile = image_profile(data)
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image).convert("L")
            sample = ImageOps.pad(image, (256, 256), color=255, method=Image.Resampling.LANCZOS)
            stat = ImageStat.Stat(sample)
            pixels = list(sample.getdata())
            white_ratio = sum(pixel >= 250 for pixel in pixels) / max(1, len(pixels))
            entropy = sample.entropy()
            width, height = image.size
    except Exception as exc:
        return {
            "valid": False,
            "error": str(exc),
            "file_size": len(data),
            "profile": profile,
            "quality_flags": ["image_decode_failed"],
        }

    flags: list[str] = []
    if len(data) < MIN_IMAGE_BYTES:
        flags.append("image_file_too_small")
    if min(width, height) < MIN_IMAGE_SIDE:
        flags.append("image_dimension_too_small")
    if profile.get("protection_reason"):
        flags.append(_text(profile.get("protection_reason")))
    if white_ratio >= 0.995 or (stat.mean[0] >= 250 and stat.stddev[0] < 8):
        flags.append("blank_or_near_blank_page")
    return {
        "valid": True,
        "file_size": len(data),
        "width": width,
        "height": height,
        "gray_mean": round(stat.mean[0], 4),
        "gray_stddev": round(stat.stddev[0], 4),
        "white_ratio": round(white_ratio, 6),
        "entropy": round(entropy, 4),
        "profile": profile,
        "quality_flags": sorted(set(flags)),
    }


def _normalized_image(data: bytes, size: tuple[int, int] = (256, 256)) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image).convert("L")
    return ImageOps.pad(image, size, color=255, method=Image.Resampling.LANCZOS)


def _visual_similarity(left: bytes, right: bytes) -> dict[str, float]:
    a = _normalized_image(left)
    b = _normalized_image(right)
    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    pixels = list(diff.getdata())
    return {
        "mae": round(stat.mean[0], 6),
        "rms": round(stat.rms[0], 6),
        "near_pixel_ratio": round(sum(pixel <= 8 for pixel in pixels) / max(1, len(pixels)), 6),
    }


def _aspect_ratio(profile: dict[str, Any]) -> float:
    width = float(profile.get("width") or 0)
    height = float(profile.get("height") or 0)
    return width / height if width and height else 0.0


def _business_duplicate_ids(row: dict[str, Any], index: dict[str, list[str]]) -> list[str]:
    key = _normalize_business_name(row.get("source_group_title"))
    return sorted(set(index.get(key) or [])) if len(key) >= 5 else []


def _existing_batch_index(rows: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if _text(metadata.get("source_batch_id")) != BATCH_ID:
            continue
        candidate_id = _text(metadata.get("candidate_id"))
        if candidate_id:
            result[candidate_id] = str(row.get("id"))
    return result


def analyze_extracted_candidates(
    extracted_rows: list[dict[str, Any]],
    existing_assets: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    visuals, missing_visuals = _baseline_visuals(existing_assets)
    sha_index: dict[str, list[BaselineVisual]] = {}
    for visual in visuals:
        sha_index.setdefault(visual.sha256, []).append(visual)
    business_index = _business_identity_index(existing_assets)
    batch_index = _existing_batch_index(existing_assets)
    analyzed: list[dict[str, Any]] = []

    for row in extracted_rows:
        path = PROJECT_ROOT / row["extracted_path"]
        data = path.read_bytes()
        quality = _image_quality(path)
        candidate_profile = quality.get("profile") or {}
        candidate_id = _text(row.get("candidate_id"))
        disposition = "ready_for_ingestion"
        reason = "通过来源、中文命名、图片质量和现有资产去重门禁"
        matched_ids: list[str] = []
        nearest: dict[str, Any] = {}

        if candidate_id in batch_index:
            disposition = "already_ingested"
            reason = "同一批次、同一候选已存在，幂等跳过"
            matched_ids = [batch_index[candidate_id]]
        elif not quality.get("valid"):
            disposition = "quality_blocked"
            reason = "图片无法解码，禁止入库"
        elif quality.get("quality_flags"):
            disposition = "quality_review_required"
            reason = "图片存在空白页、小图或低信息量风险，保留提取文件并转人工复核"
        elif any(keyword in f"{row.get('source_section', '')} {row.get('reviewed_title', '')}" for keyword in BLOCKED_CONTENT_HINTS):
            disposition = "quality_review_required"
            reason = "候选疑似二维码、签章、页脚或局部切图，禁止自动入库"
        elif sha_index.get(row["actual_media_sha256"]):
            disposition = "duplicate_exact_existing"
            reason = "与现有泰昌资产字节哈希完全一致，关联已有资产而不新增"
            matched_ids = [item.asset_id for item in sha_index[row["actual_media_sha256"]]]
        else:
            business_matches = _business_duplicate_ids(row, business_index)
            if business_matches:
                disposition = "same_evidence_existing"
                reason = "现有资产已包含同名完整原始报告/资料，Word 内嵌页只作历史载体追溯"
                matched_ids = business_matches

        if disposition == "ready_for_ingestion" and candidate_profile.get("dhash"):
            visual_candidates: list[tuple[int, BaselineVisual]] = []
            for visual in visuals:
                distance = hamming_distance(candidate_profile.get("dhash"), visual.profile.get("dhash"))
                if distance is not None and distance <= VISUAL_REVIEW_MAX_DHASH:
                    visual_candidates.append((distance, visual))
            scored: list[tuple[float, int, BaselineVisual, dict[str, float]]] = []
            for distance, visual in visual_candidates:
                similarity = _visual_similarity(data, visual.path.read_bytes())
                scored.append((similarity["mae"], distance, visual, similarity))
            if scored:
                _, distance, visual, similarity = min(scored, key=lambda item: (item[0], item[1]))
                left_ratio = _aspect_ratio(candidate_profile)
                right_ratio = _aspect_ratio(visual.profile)
                ratio_delta = (
                    abs(left_ratio - right_ratio) / max(left_ratio, right_ratio)
                    if left_ratio and right_ratio
                    else 1.0
                )
                nearest = {
                    "asset_id": visual.asset_id,
                    "title": visual.title,
                    "dhash_distance": distance,
                    "aspect_ratio_delta": round(ratio_delta, 6),
                    **similarity,
                }
                probable = (
                    (distance <= 2 and ratio_delta <= 0.03)
                    or (
                        distance <= VISUAL_REVIEW_MAX_DHASH
                        and similarity["mae"] <= 3.0
                        and similarity["near_pixel_ratio"] >= 0.90
                    )
                )
                if probable:
                    disposition = "duplicate_visual_existing"
                    reason = "与现有资产虽压缩编码不同，但视觉特征和归一化像素高度一致，不新增"
                    matched_ids = [visual.asset_id]
                else:
                    disposition = "possible_visual_duplicate"
                    reason = "与现有资产存在近似视觉指纹；为避免重复，转人工复核而不自动入库"
                    matched_ids = [visual.asset_id]

        title = _text(row.get("reviewed_title") or row.get("title"))
        source_display_name = _text(row.get("source_display_name_after_ingestion"))
        violations = _visible_violations(
            [
                title,
                source_display_name,
                row.get("category_label"),
                *(row.get("tags") or []),
            ]
        )
        if violations:
            disposition = "visible_name_blocked"
            reason = "中文展示字段包含内部命名或追溯痕迹，禁止入库"

        analyzed.append(
            {
                **row,
                "title_after_ingestion": title,
                "quality": {key: value for key, value in quality.items() if key != "profile"},
                "visual_dhash": candidate_profile.get("dhash"),
                "dedup_disposition": disposition,
                "dedup_reason": reason,
                "matched_existing_asset_ids": sorted(set(matched_ids)),
                "nearest_visual_match": nearest,
                "visible_field_violations": violations,
                "ready_for_database_ingestion": disposition == "ready_for_ingestion",
            }
        )

    audit = {
        "existing_asset_count": len(existing_assets),
        "existing_visual_count": len(visuals),
        "missing_or_unreadable_existing_visuals": missing_visuals,
        "disposition_counts": dict(sorted(Counter(row["dedup_disposition"] for row in analyzed).items())),
    }
    return analyzed, audit


def _asset_payload(row: dict[str, Any], embedding: list[float] | None) -> dict[str, Any]:
    path = PROJECT_ROOT / row["extracted_path"]
    title = row["title_after_ingestion"]
    category = _text(row.get("category_label") or row.get("evidence_type_label") or "企业资料")
    source_display_name = row["source_display_name_after_ingestion"]
    description = (
        f"来源于客户提供的《泰昌技术补充文件》中“{row.get('source_group_title')}”章节。"
        "该资料仅用于泰昌内部知识检索；它是历史 Word 内嵌载体，不是独立原始证据，"
        "不得直接作为精确参数、有效证书或正式投标附件使用。"
    )
    tags = list(dict.fromkeys([*list(row.get("tags") or []), "仅限知识库", "历史标书内嵌资料"]))
    applicable_sections = list(row.get("applicable_sections") or [])
    searchable_text = "\n".join([title, source_display_name, category, description, *tags, *applicable_sections])
    evidence_type = _text(row.get("evidence_type") or "enterprise_evidence")
    target_library = _text(row.get("target_library") or "product_library")
    metadata = {
        "source_batch_id": BATCH_ID,
        "candidate_id": row.get("candidate_id"),
        "source_docx_sha256": row.get("source_docx_sha256"),
        "source_media_sha256": row.get("actual_media_sha256"),
        "source_file": row.get("source_file"),
        "source_section": row.get("source_section"),
        "source_page": row.get("source_page"),
        "media_relationship_id": row.get("media_relationship_id"),
        "media_target": row.get("media_target"),
        "enterprise": "泰昌",
        "doc_owner": ENTERPRISE,
        "source_domain": "enterprise_fact",
        "origin_source_domain": "mixed_historical_bid",
        "reference_only": False,
        "fact_source_allowed_for_enterprise": True,
        "parameter_fact_allowed": False,
        "requires_fact_cross_check_for_precise_values": True,
        "tenant_visibility": "taichang_only",
        "access_scope": "taichang_tenant_internal",
        "target_library": target_library,
        "target_library_label": row.get("target_library_label") or "产品库资料",
        "evidence_type": evidence_type,
        "evidence_type_label": row.get("evidence_type_label") or category,
        "category_label": category,
        "quality_tier": "knowledge_only",
        "quality_tier_label": "仅用于知识库",
        "review_status": "policy_auto_accepted_then_quality_validated",
        "review_status_label": "系统分级接收并通过质量校验",
        "allowed_for_bid": False,
        "formal_bid_ready": False,
        "exclude_from_docx": True,
        "source_display_name": source_display_name,
        "source_document_name": "泰昌技术补充文件",
        "asset_visual_type": "word_embedded_rendition",
        "word_embedded_rendition": True,
        "full_page": False,
        "extracted_region": False,
        "display_language": "zh-CN",
        "ui_name_policy": "domestic_chinese_friendly",
        "caption_policy": "suppressed_document_page_caption",
        "formal_caption": "",
        "usage_restriction": "仅作泰昌内部知识资料，不得作为精确参数、有效证书或正式投标附件直接引用",
    }
    specs = {
        "library_type": "qualification" if target_library == "qualification_library" else "product",
        "allowed_for_bid": False,
        "user_requested_bid_usage": False,
        "quality_tier": "knowledge_only",
        "quality_tier_label": "仅用于知识库",
        "target_library": target_library,
        "target_library_label": metadata["target_library_label"],
        "evidence_type": evidence_type,
        "evidence_type_label": metadata["evidence_type_label"],
        "category_label": category,
        "product_families": row.get("product_families") or [],
        "formal_display_title": title,
    }
    width = (row.get("quality") or {}).get("width")
    height = (row.get("quality") or {}).get("height")
    return {
        "title": title,
        "description": description,
        "category": category,
        "asset_type": "qualification_image" if target_library == "qualification_library" else "product_image",
        "file_name": path.name,
        "file_ext": path.suffix.lower().lstrip("."),
        "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "file_size": path.stat().st_size,
        "local_path": _relative(path),
        "width": width,
        "height": height,
        "source_type": "customer_historical_bid_word_embedded_image",
        "license": "企业客户提供资料",
        "attribution": ENTERPRISE,
        "is_synthetic": False,
        "is_sensitive": False,
        "anonymized": True,
        "industry": "电力行业",
        "applicable_sections": applicable_sections,
        "applicable_volumes": ["technical"],
        "tags": tags,
        "specs": specs,
        "ocr_text": None,
        "ai_caption": description,
        "searchable_text": searchable_text,
        "embedding": embedding,
        "status": "indexed",
        "metadata": metadata,
    }


def _execute_ingestion(rows: list[dict[str, Any]], *, no_embedding: bool) -> list[dict[str, Any]]:
    ready = [row for row in rows if row["ready_for_database_ingestion"]]
    texts = [_asset_payload(row, None)["searchable_text"] for row in ready]
    embeddings: list[list[float] | None] = [None] * len(ready)
    if ready and not no_embedding:
        embeddings = get_embeddings(
            init_ali_client(),
            texts,
            batch_size=10,
            usage_context={
                "stage": "taichang_historical_bid_asset_ingestion",
                "metadata": {"source_batch_id": BATCH_ID, "asset_count": len(ready)},
            },
        )
        if len(embeddings) != len(ready) or any(not embedding for embedding in embeddings):
            raise RuntimeError("Embedding 数量不完整，已在写数据库前中止")

    results: list[dict[str, Any]] = []
    for index, row in enumerate(ready):
        try:
            payload = _asset_payload(row, embeddings[index] if embeddings else None)
            path = PROJECT_ROOT / row["extracted_path"]
            library_type = "qualification" if payload["metadata"]["target_library"] == "qualification_library" else "product"
            storage_info = upload_knowledge_asset_file(
                local_file_path=path,
                original_filename=path.name,
                library_type=library_type,
            )
            payload.update(
                {
                    "file_ext": storage_info.get("file_ext"),
                    "mime_type": storage_info.get("mime_type"),
                    "file_size": storage_info.get("file_size"),
                    "storage_bucket": storage_info.get("bucket"),
                    "storage_path": storage_info.get("object_path"),
                    "public_url": storage_info.get("public_url"),
                    "metadata": {
                        **payload["metadata"],
                        "thumbnail_storage_bucket": storage_info.get("thumbnail_bucket"),
                        "thumbnail_storage_path": storage_info.get("thumbnail_path"),
                        "thumbnail_mime_type": storage_info.get("thumbnail_mime_type"),
                        "thumbnail_size": storage_info.get("thumbnail_size"),
                    },
                }
            )
            created = create_knowledge_asset(payload)
            results.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "status": "imported",
                    "asset_id": str(created.get("id")),
                    "title": payload["title"],
                }
            )
        except Exception as exc:
            results.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "status": "failed",
                    "title": row.get("title_after_ingestion"),
                    "error": str(exc),
                }
            )
    return results


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "candidate_id",
        "title_after_ingestion",
        "source_group_title",
        "source_page",
        "evidence_type_label",
        "actual_media_sha256",
        "extracted_path",
        "dedup_disposition",
        "dedup_reason",
        "matched_existing_asset_ids",
        "quality",
        "nearest_visual_match",
        "ready_for_database_ingestion",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "matched_existing_asset_ids": json.dumps(row.get("matched_existing_asset_ids") or [], ensure_ascii=False),
                    "quality": json.dumps(row.get("quality") or {}, ensure_ascii=False),
                    "nearest_visual_match": json.dumps(row.get("nearest_visual_match") or {}, ensure_ascii=False),
                }
            )


def _write_report(
    output_dir: Path,
    rows: list[dict[str, Any]],
    audit: dict[str, Any],
    *,
    execute: bool,
    import_results: list[dict[str, Any]],
    approved_path: Path,
    inventories: list[Path],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    disposition_counts = Counter(row["dedup_disposition"] for row in rows)
    import_counts = Counter(row["status"] for row in import_results)
    payload = {
        "metadata": {
            "schema_version": "taichang_historical_bid_asset_ingestion_v1",
            "generated_at": _now(),
            "enterprise": ENTERPRISE,
            "pilot_only": True,
            "source_batch_id": BATCH_ID,
            "execute": execute,
            "database_written": bool(execute and import_counts.get("imported")),
            "rag_updated": bool(execute and import_counts.get("imported")),
            "docx_selection_updated": False,
            "approved_candidate_count": len(rows),
            "extracted_candidate_count": len(rows),
            "ready_for_database_ingestion_count": sum(row["ready_for_database_ingestion"] for row in rows),
            "disposition_counts": dict(sorted(disposition_counts.items())),
            "import_counts": dict(sorted(import_counts.items())),
            "input_sha256": {
                _relative(approved_path): _sha256_file(approved_path),
                **{_relative(path): _sha256_file(path) for path in inventories},
            },
        },
        "baseline_audit": audit,
        "import_results": import_results,
        "records": rows,
    }
    json_path = output_dir / "taichang_historical_bid_asset_ingestion.json"
    csv_path = output_dir / "taichang_historical_bid_asset_ingestion.csv"
    md_path = output_dir / "taichang_historical_bid_asset_ingestion_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(csv_path, rows)

    lines = [
        "# 泰昌历史标书增量资产提取与入库报告",
        "",
        f"> 批次：`{BATCH_ID}`",
        f"> 执行方式：`{'execute' if execute else 'dry-run'}`",
        f"> 生成时间：{payload['metadata']['generated_at']}",
        "",
        "## 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 策略自动接收候选 | {len(rows)} |",
        f"| 已实际提取文件 | {len(rows)} |",
        f"| 通过数据库入库门禁 | {payload['metadata']['ready_for_database_ingestion_count']} |",
        f"| 实际写入 | {import_counts.get('imported', 0)} |",
        f"| 写入失败 | {import_counts.get('failed', 0)} |",
        "",
        "## 去重与质量处置",
        "",
        "| 处置 | 数量 |",
        "| --- | ---: |",
    ]
    for key, value in sorted(disposition_counts.items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## 强制边界",
            "",
            "- 所有入库项均为 `knowledge_only + allowed_for_bid=false + formal_bid_ready=false`。",
            "- Word 内嵌页不得作为精确技术参数、证书有效性或检验报告实测值来源。",
            "- 同名完整原始 PDF/整页资产已存在时，只建立追溯关系，不新建重复资产。",
            "- 技术参数表另走结构化抽取和原始检验报告交叉校验，不从图片猜测数值或单位。",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="提取并增量入库泰昌历史标书低风险 Word 内嵌资料")
    parser.add_argument("--approved", type=Path, default=DEFAULT_APPROVED)
    parser.add_argument("--inventory", type=Path, action="append", dest="inventories")
    parser.add_argument("--extract-root", type=Path, default=DEFAULT_EXTRACT_ROOT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--execute", action="store_true", help="通过门禁后实际写入数据库；默认只 dry-run")
    parser.add_argument("--no-embedding", action="store_true", help="仅用于故障排查；正式入库不得使用")
    args = parser.parse_args()

    if args.execute and args.no_embedding:
        raise SystemExit("正式执行必须生成 embedding，不允许同时使用 --execute --no-embedding")
    approved_path = args.approved.resolve()
    inventory_paths = [path.resolve() for path in (args.inventories or DEFAULT_INVENTORIES)]
    approved_rows = _load_approved(approved_path)
    inventory_rows = _load_inventory_rows(inventory_paths)
    extracted = _extract_candidates(approved_rows, inventory_rows, args.extract_root.resolve())
    existing_assets = _fetch_existing_assets()
    analyzed, audit = analyze_extracted_candidates(extracted, existing_assets)
    import_results = _execute_ingestion(analyzed, no_embedding=args.no_embedding) if args.execute else []
    payload = _write_report(
        args.report_dir.resolve(),
        analyzed,
        audit,
        execute=args.execute,
        import_results=import_results,
        approved_path=approved_path,
        inventories=inventory_paths,
    )
    summary = payload["metadata"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if any(item.get("status") == "failed" for item in import_results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""对泰昌两份历史标书候选执行只读四层去重分析。

安全边界：
- 只读取 P0-02 基线、P0-03 候选清单、候选 Word 及其已存在的 staging 清单；
- 不连接数据库，不修改 metadata，不写入正式资产库；
- 感知哈希、标题相似和业务名称相同只能产生待复核结论；
- 所有输出仍为 review_only / allowed_for_bid=false。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

from PIL import Image, ImageStat


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "docs/development/taichang-bid-v1-data"
DEFAULT_BASELINE = DEFAULT_DATA_DIR / "current_asset_baseline.json"
DEFAULT_TECHNICAL = DEFAULT_DATA_DIR / "taichang_technical_bid_candidate_inventory.json"
DEFAULT_BUSINESS = DEFAULT_DATA_DIR / "taichang_business_bid_candidate_inventory.json"
DEFAULT_JSON = DEFAULT_DATA_DIR / "asset_dedup_matrix.json"
DEFAULT_CSV = DEFAULT_DATA_DIR / "asset_dedup_matrix.csv"
DEFAULT_REPORT = PROJECT_ROOT / "docs/development/taichang-historical-bid-asset-dedup-report-20260713.md"

VISUAL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
PROJECT_SPECIFIC_FACT_KINDS = {"project_identifier", "fixed_parameter_id"}
TEXT_REVIEW_FACT_KINDS = {
    "testing_equipment_candidate",
    "candidate_product_spec",
    "technical_parameter_candidate",
}
CSV_FIELDS = [
    "candidate_id",
    "bid_volume",
    "record_type",
    "title",
    "source_file",
    "source_section",
    "source_page",
    "fact_kind",
    "report_or_certificate_no",
    "content_sha256",
    "media_sha256",
    "media_width",
    "media_height",
    "file_exact_status",
    "visual_status",
    "visual_phash",
    "visual_hamming_distance",
    "visual_protection_reason",
    "text_status",
    "business_key",
    "business_status",
    "dedup_status",
    "match_scope",
    "matched_record_ids",
    "evidence_bundle_id",
    "manual_review_required",
    "promotion_eligible",
    "quality_tier",
    "allowed_for_bid",
    "decision_reason",
]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_text(value: Any) -> str:
    return re.sub(r"[\W_]+", "", _text(value).lower(), flags=re.UNICODE)


def _resolve_path(value: Any) -> Path | None:
    raw = _text(value)
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.is_file() else None


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def dhash_bytes(data: bytes, hash_size: int = 8) -> str:
    """计算 64 位 dHash；无法解码时返回空字符串。"""
    try:
        with Image.open(io.BytesIO(data)) as image:
            gray = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            pixels = list(gray.getdata())
    except Exception:
        return ""
    value = 0
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for col in range(hash_size):
            value = (value << 1) | int(pixels[offset + col] > pixels[offset + col + 1])
    return f"{value:0{hash_size * hash_size // 4}x}"


def hamming_distance(left: str, right: str) -> int | None:
    if not left or not right or len(left) != len(right):
        return None
    return (int(left, 16) ^ int(right, 16)).bit_count()


def image_profile(data: bytes) -> dict[str, Any]:
    """返回视觉比对需要的尺寸、dHash 和保守保护标记。"""
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            gray = image.convert("L").resize((64, 64), Image.Resampling.BILINEAR)
            mean = ImageStat.Stat(gray).mean[0]
            white_ratio = sum(1 for value in gray.getdata() if value >= 248) / (64 * 64)
    except Exception:
        return {"width": 0, "height": 0, "dhash": "", "protection_reason": "unsupported_or_broken_image"}
    protection = ""
    if white_ratio >= 0.97 or mean >= 250:
        protection = "blank_or_near_blank_page"
    elif width < 128 or height < 128:
        protection = "small_fragment_or_stamp_risk"
    return {
        "width": width,
        "height": height,
        "dhash": dhash_bytes(data),
        "protection_reason": protection,
    }


def _aspect_ratio(profile: dict[str, Any]) -> float:
    width, height = int(profile.get("width") or 0), int(profile.get("height") or 0)
    return width / height if height else 0.0


def visual_near_match(
    candidate: dict[str, Any], baseline: dict[str, Any], *, max_distance: int = 4
) -> tuple[bool, int | None]:
    """视觉近似只用于标记可能重复，不能自动合并。"""
    distance = hamming_distance(_text(candidate.get("dhash")), _text(baseline.get("dhash")))
    if distance is None or distance > max_distance:
        return False, distance
    if candidate.get("protection_reason") or baseline.get("protection_reason"):
        return True, distance
    left_ratio, right_ratio = _aspect_ratio(candidate), _aspect_ratio(baseline)
    if not left_ratio or not right_ratio:
        return False, distance
    return abs(left_ratio - right_ratio) / max(left_ratio, right_ratio) <= 0.03, distance


def _load_docx_media(source_files: Iterable[str]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for source_file in sorted(set(source_files)):
        path = _resolve_path(source_file)
        if not path:
            continue
        with ZipFile(path) as archive:
            for name in sorted(item for item in archive.namelist() if item.startswith("word/media/")):
                data = archive.read(name)
                result[(source_file, name)] = {
                    "sha256": _sha256_bytes(data),
                    "profile": image_profile(data),
                }
    return result


def _load_baseline_visuals(baseline_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从基线所引用的真实图片路径建立视觉索引，不使用解析器 JSON 指纹冒充图片哈希。"""
    source_systems = sorted(
        {
            _text(record.get("source_system"))
            for record in baseline_records
            if record.get("record_type") == "staging_asset_candidate"
            and _text(record.get("source_system")).endswith("asset_staging_payloads.json")
        }
    )
    visuals: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for source_system in source_systems:
        manifest_path = _resolve_path(source_system)
        if not manifest_path:
            continue
        for payload in (_json(manifest_path).get("assets") or []):
            if not isinstance(payload, dict):
                continue
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            if _text(metadata.get("source_domain")) != "enterprise_fact":
                continue
            local_path = _resolve_path(payload.get("local_path") or metadata.get("asset_path"))
            if not local_path or local_path.suffix.lower() not in VISUAL_EXTENSIONS:
                continue
            key = str(local_path.resolve())
            if key in seen_paths:
                continue
            seen_paths.add(key)
            data = local_path.read_bytes()
            visuals.append(
                {
                    "record_id": _text(metadata.get("asset_id")) or _sha256_text(key)[:24],
                    "source_file": _text(metadata.get("source_file")) or str(local_path.relative_to(PROJECT_ROOT)),
                    "local_path": str(local_path.relative_to(PROJECT_ROOT)),
                    "sha256": _sha256_bytes(data),
                    "profile": image_profile(data),
                    "title": _text(payload.get("title")),
                }
            )
    # 直接以原始图片存在的基线记录（如官方 Logo）也纳入视觉索引。
    for record in baseline_records:
        path = _resolve_path(record.get("source_file"))
        if not path or path.suffix.lower() not in VISUAL_EXTENSIONS:
            continue
        key = str(path.resolve())
        if key in seen_paths:
            continue
        seen_paths.add(key)
        data = path.read_bytes()
        visuals.append(
            {
                "record_id": _text(record.get("record_id")),
                "source_file": _text(record.get("source_file")),
                "local_path": str(path.relative_to(PROJECT_ROOT)),
                "sha256": _sha256_bytes(data),
                "profile": image_profile(data),
                "title": _text(record.get("title")),
            }
        )
    return sorted(visuals, key=lambda item: (item["source_file"], item["record_id"]))


def _bundle_id(kind: str, key: str) -> str:
    return f"taichang-{kind}-{_sha256_text(key)[:20]}" if key else ""


def _business_key(candidate: dict[str, Any]) -> tuple[str, str]:
    fact_kind = _text(candidate.get("fact_kind"))
    number = _text(candidate.get("report_or_certificate_no"))
    if fact_kind == "report_identifier" and number:
        return "inspection_report", f"河北泰昌电力器材科技有限公司|检验报告|{number}"
    if fact_kind == "project_identifier" and number:
        return "project_identifier", f"历史项目|{number}"
    if fact_kind == "fixed_parameter_id" and number:
        return "fixed_parameter_id", f"历史固化ID|{number}"
    return "", ""


def _candidate_fingerprint(candidate: dict[str, Any]) -> str:
    return _text(candidate.get("media_sha256") or candidate.get("content_sha256"))


def analyze(
    baseline_payload: dict[str, Any], candidate_payloads: list[dict[str, Any]]
) -> dict[str, Any]:
    baseline_records = baseline_payload.get("records") or []
    candidates = [record for payload in candidate_payloads for record in (payload.get("records") or [])]
    docx_media = _load_docx_media(_text(record.get("source_file")) for record in candidates)
    baseline_visuals = _load_baseline_visuals(baseline_records)

    baseline_hash_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    baseline_title_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    baseline_report_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in baseline_records:
        for field in ("source_sha256", "content_sha256"):
            value = _text(record.get(field))
            if value:
                baseline_hash_index[value].append(record)
        title_key = _normalize_text(record.get("title") or record.get("source_display_name"))
        if title_key:
            baseline_title_index[title_key].append(record)
        report_no = _text(record.get("report_or_certificate_no"))
        if report_no:
            baseline_report_index[report_no].append(record)
    baseline_visual_hash_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for visual in baseline_visuals:
        baseline_visual_hash_index[visual["sha256"]].append(visual)

    seen_fingerprints: dict[str, dict[str, Any]] = {}
    seen_business_keys: dict[str, dict[str, Any]] = {}
    matrix: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = _text(candidate.get("candidate_id"))
        fingerprint = _candidate_fingerprint(candidate)
        fact_kind = _text(candidate.get("fact_kind"))
        record_type = _text(candidate.get("record_type"))
        media_key = (_text(candidate.get("source_file")), _text(candidate.get("media_target")))
        media_info = docx_media.get(media_key, {}) if record_type == "media" else {}
        profile = media_info.get("profile") or {}
        exact_matches = baseline_hash_index.get(fingerprint, []) if fingerprint else []
        visual_exact_matches = baseline_visual_hash_index.get(_text(media_info.get("sha256")), [])
        prior = seen_fingerprints.get(fingerprint) if fingerprint else None
        business_kind, business_key = _business_key(candidate)
        report_matches = baseline_report_index.get(_text(candidate.get("report_or_certificate_no")), [])

        row = {field: "" for field in CSV_FIELDS}
        for field in (
            "candidate_id", "bid_volume", "record_type", "title", "source_file", "source_section",
            "source_page", "fact_kind", "report_or_certificate_no", "content_sha256", "media_sha256",
            "media_width", "media_height",
        ):
            row[field] = candidate.get(field, "")
        row.update(
            {
                "file_exact_status": "no_exact_match",
                "visual_status": "not_applicable" if record_type != "media" else "no_visual_match",
                "visual_phash": _text(profile.get("dhash")),
                "visual_hamming_distance": "",
                "visual_protection_reason": _text(profile.get("protection_reason")),
                "text_status": "not_checked",
                "business_key": business_key,
                "business_status": "not_applicable" if not business_key else "no_business_match",
                "dedup_status": "new",
                "match_scope": "",
                "matched_record_ids": [],
                "evidence_bundle_id": "",
                "manual_review_required": False,
                "promotion_eligible": False,
                "quality_tier": "review_only",
                "allowed_for_bid": False,
                "decision_reason": "未发现可自动确认的重复；仍需进入 P0-05 标签和人工审核",
            }
        )

        # 项目号和固化 ID 在新项目中属于冲突风险，优先于任何重复判定。
        if fact_kind in PROJECT_SPECIFIC_FACT_KINDS:
            row.update(
                dedup_status="fact_conflict",
                business_status="project_specific_conflict",
                manual_review_required=True,
                decision_reason="历史项目专属编号/固化ID不得复用于新项目，必须以本次招标文件覆盖",
            )
        elif visual_exact_matches:
            row.update(
                file_exact_status="exact_image_bytes_match_existing_baseline",
                visual_status="exact_visual_bytes_match",
                dedup_status="duplicate_exact",
                match_scope="existing_baseline",
                matched_record_ids=[item["record_id"] for item in visual_exact_matches],
                evidence_bundle_id=_bundle_id("exact", visual_exact_matches[0]["sha256"]),
                decision_reason="Word内嵌媒体与现有基线图片字节哈希完全一致，不得新增资产",
            )
        elif exact_matches:
            row.update(
                file_exact_status="exact_hash_match_existing_baseline",
                dedup_status="duplicate_exact",
                match_scope="existing_baseline",
                matched_record_ids=[_text(item.get("record_id")) for item in exact_matches],
                evidence_bundle_id=_bundle_id("exact", fingerprint),
                decision_reason="候选指纹与现有基线精确一致，不得新增资产",
            )
        elif report_matches and business_kind == "inspection_report":
            row.update(
                business_status="same_report_number_existing_baseline",
                dedup_status="same_evidence_new_rendition",
                match_scope="existing_baseline",
                matched_record_ids=sorted({_text(item.get("record_id")) for item in report_matches}),
                evidence_bundle_id=_bundle_id(business_kind, business_key),
                manual_review_required=True,
                decision_reason="报告编号已存在于结构化参数层；历史标书内容只能作为同一证据的另一载体待复核",
            )
        elif prior:
            row.update(
                file_exact_status="exact_hash_match_historical_candidate",
                dedup_status="duplicate_exact",
                match_scope="historical_candidate",
                matched_record_ids=[prior["candidate_id"]],
                evidence_bundle_id=prior.get("evidence_bundle_id") or _bundle_id("exact", fingerprint),
                decision_reason="候选与较早历史标书候选指纹完全一致，只保留首次出现的追溯关系",
            )
        else:
            nearest: tuple[int, dict[str, Any]] | None = None
            if record_type == "media" and profile.get("dhash"):
                for visual in baseline_visuals:
                    matched, distance = visual_near_match(profile, visual["profile"])
                    if matched and distance is not None and (nearest is None or distance < nearest[0]):
                        nearest = (distance, visual)
                if nearest:
                    distance, visual = nearest
                    protection = _text(profile.get("protection_reason") or visual["profile"].get("protection_reason"))
                    row.update(
                        visual_status="possible_visual_duplicate",
                        visual_hamming_distance=distance,
                        visual_protection_reason=protection,
                        dedup_status="possible_visual_duplicate",
                        match_scope="existing_baseline",
                        matched_record_ids=[visual["record_id"]],
                        evidence_bundle_id=_bundle_id("visual-review", visual["sha256"]),
                        manual_review_required=True,
                        decision_reason=(
                            "感知哈希近似且存在空白页/小图/签章误判风险，严禁自动合并"
                            if protection else "感知哈希近似，仅标记人工视觉复核，严禁自动合并"
                        ),
                    )

            title_key = _normalize_text(candidate.get("title"))
            title_matches = baseline_title_index.get(title_key, []) if title_key else []
            if row["dedup_status"] == "new" and fact_kind in TEXT_REVIEW_FACT_KINDS and title_matches:
                row.update(
                    text_status="possible_text_duplicate",
                    dedup_status="possible_text_duplicate",
                    match_scope="existing_baseline",
                    matched_record_ids=[_text(item.get("record_id")) for item in title_matches[:20]],
                    manual_review_required=True,
                    decision_reason="名称相同但缺少设备编号/报告号等业务主键，只能作为文本疑似重复人工确认",
                )

        if business_key:
            if report_matches:
                row["business_status"] = "same_business_key_existing_baseline"
            elif business_key in seen_business_keys:
                row["business_status"] = "same_business_key_historical_candidate"
                if row["dedup_status"] == "new":
                    earlier = seen_business_keys[business_key]
                    row.update(
                        dedup_status="same_evidence_new_rendition",
                        match_scope="historical_candidate",
                        matched_record_ids=[earlier["candidate_id"]],
                        evidence_bundle_id=earlier.get("evidence_bundle_id") or _bundle_id(business_kind, business_key),
                        manual_review_required=True,
                        decision_reason="业务主键相同但载体不同，归入同一证据包待人工确认",
                    )
            else:
                row["business_status"] = "no_business_match"
        if row["dedup_status"] in {"new", "possible_text_duplicate", "possible_visual_duplicate", "same_evidence_new_rendition"}:
            row["manual_review_required"] = True
        if record_type in {"chapter", "table"}:
            row["promotion_eligible"] = False
            row["decision_reason"] += "；该记录是结构/表单参考，不属于正式资产入库对象"
        elif fact_kind == "generic_response":
            row["promotion_eligible"] = False
            row["decision_reason"] += "；通用响应话术不得进入参数或企业事实层"

        matrix.append(row)
        if fingerprint and fingerprint not in seen_fingerprints:
            seen_fingerprints[fingerprint] = row
        if business_key and business_key not in seen_business_keys:
            seen_business_keys[business_key] = row

    status_counts = Counter(_text(row["dedup_status"]) for row in matrix)
    type_counts = Counter(_text(row["record_type"]) for row in matrix)
    return {
        "metadata": {
            "schema_version": "taichang_asset_dedup_matrix_v1",
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "enterprise": "河北泰昌电力器材科技有限公司",
            "analysis_scope": "P0-04 historical bid candidates versus frozen asset baseline",
            "read_only": True,
            "database_written": False,
            "metadata_updated": False,
            "quality_tier": "review_only",
            "allowed_for_bid": False,
            "automatic_merge_performed": False,
            "visual_near_match_policy": "manual_review_only",
            "baseline_snapshot_version": baseline_payload.get("snapshot_version"),
            "baseline_record_count": len(baseline_records),
            "baseline_visual_files_indexed": len(baseline_visuals),
            "candidate_count": len(matrix),
            "record_type_counts": dict(sorted(type_counts.items())),
            "dedup_status_counts": dict(sorted(status_counts.items())),
            "gate_checks": {
                "all_candidates_have_dedup_status": all(_text(row.get("dedup_status")) for row in matrix),
                "all_candidates_blocked_from_promotion": all(not row.get("promotion_eligible") for row in matrix),
                "all_candidates_allowed_for_bid_false": all(row.get("allowed_for_bid") is False for row in matrix),
                "possible_visual_duplicates_require_manual_review": all(
                    row.get("manual_review_required") is True
                    for row in matrix if row.get("dedup_status") == "possible_visual_duplicate"
                ),
                "exact_duplicates_blocked": all(
                    not row.get("promotion_eligible")
                    for row in matrix if row.get("dedup_status") == "duplicate_exact"
                ),
            },
        },
        "records": matrix,
    }


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["matched_record_ids"] = json.dumps(row.get("matched_record_ids") or [], ensure_ascii=False)
            writer.writerow(row)


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    metadata = payload["metadata"]
    counts = metadata["dedup_status_counts"]
    lines = [
        "# 泰昌历史标书候选资产四层去重报告",
        "",
        f"> 生成时间：{metadata['generated_at']}",
        "> 结论性质：P0-04 只读审计，不代表候选已成为正式资产。",
        "",
        "## 一、执行结论",
        "",
        f"- 冻结基线记录：{metadata['baseline_record_count']} 条。",
        f"- 历史标书候选：{metadata['candidate_count']} 条，已全部给出去重状态。",
        f"- 可访问并重新计算真实图片哈希的基线视觉文件：{metadata['baseline_visual_files_indexed']} 个。",
        "- 未连接数据库、未改 metadata、未执行自动合并、未生成任何正式入库记录。",
        "- 所有候选继续保持 `review_only / allowed_for_bid=false / promotion_eligible=false`。",
        "",
        "## 二、去重状态统计",
        "",
        "| 状态 | 数量 | 安全处理 |",
        "| --- | ---: | --- |",
    ]
    actions = {
        "duplicate_exact": "不进入增量入库，只保留来源追溯",
        "possible_visual_duplicate": "人工逐图复核，禁止自动合并",
        "possible_text_duplicate": "补业务编号/原始证据后人工复核",
        "same_evidence_new_rendition": "归入同一证据包候选，不新建业务主记录",
        "fact_conflict": "不得复用或覆盖，以当次招标文件/原始事实为准",
        "new": "仅进入 P0-05 标签和质量审核，不代表可入库",
    }
    for status, count in sorted(counts.items()):
        lines.append(f"| `{status}` | {count} | {actions.get(status, '人工复核')} |")
    lines.extend(
        [
            "",
            "## 三、四层规则与风险控制",
            "",
            "1. 文件层：仅 SHA-256 字节完全一致才判 `duplicate_exact`。",
            "2. 视觉层：从 staging 的真实 `local_path` 重新计算图片哈希；dHash 距离不超过 4 也只判 `possible_visual_duplicate`。空白页、小图、印章/签章风险图禁止自动合并。",
            "3. 文本层：名称相同但缺少报告号、证书号、设备编号等业务键时，只判 `possible_text_duplicate`。",
            "4. 业务层：报告编号相同的 Word 载体与既有结构化参数记录归入同一 `evidence_bundle_id`，不建立第二个报告主记录。",
            "",
            "## 四、明确未执行事项",
            "",
            "- 未把 Word 内嵌图片导入产品库、资信库或知识库。",
            "- 未把历史项目号、固化 ID、通用响应话术写入新项目。",
            "- 未根据感知哈希删除、覆盖或合并任何文件。",
            "- 未对证书/报告图片做 OCR，因此图片内部编号、有效期、签章和参数仍需原始文件或人工复核。",
            "",
            "## 五、P0 门禁",
            "",
        ]
    )
    for name, passed in metadata["gate_checks"].items():
        lines.append(f"- [{'x' if passed else ' '}] `{name}`")
    lines.extend(
        [
            "",
            "P0-05 只能消费本矩阵中通过后续标签、质量分级和人工审核的候选；本报告本身不授权入库。",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--technical", type=Path, default=DEFAULT_TECHNICAL)
    parser.add_argument("--business", type=Path, default=DEFAULT_BUSINESS)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    input_hashes = {_display_path(path): _sha256_file(path) for path in (args.baseline, args.technical, args.business)}
    payload = analyze(_json(args.baseline), [_json(args.technical), _json(args.business)])
    payload["metadata"]["input_sha256"] = input_hashes
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(args.output_csv, payload["records"])
    _write_report(args.report, payload)
    print(json.dumps(payload["metadata"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

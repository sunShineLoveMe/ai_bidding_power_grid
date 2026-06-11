#!/usr/bin/env python3
"""Stage Taichang supplemental qualification files for RAG and assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

BATCH_ID = "customer_taichang_supplement_20260611"
SOURCE_ROOT = PROJECT_ROOT / "rag_seed/power_grid_resources/05_enterprise_documents/02_泰昌资质文件补充_20260611/extracted"
OUT_ROOT = PROJECT_ROOT / "parsed_outputs/power_grid_customer_corpus" / BATCH_ID
BRAND_LOGO = PROJECT_ROOT / "rag_seed/power_grid_resources/05_enterprise_documents/01_泰昌MVP试点企业资料/00_brand_assets/泰昌官方Logo.png"

ENTERPRISE_FULL = "河北泰昌电力器材科技有限公司"
ENTERPRISE_SHORT = "泰昌"


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    return re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", text)


def _safe_stem(value: str) -> str:
    clean = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", value, flags=re.UNICODE).strip("_")
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{clean[:80]}_{digest}" if clean else digest


def _classify(path: Path) -> tuple[str, str, str]:
    text = str(path)
    if "公章法人章签名" in text:
        return "signature_seal", "qualification_library", "restricted_signature_or_seal_manual_use_only"
    if "检验报告" in text or "型式试验" in text:
        return "inspection_report", "product_library", "enterprise_fact"
    if any(key in text for key in ["产品实物", "生产线", "生产设备", "挤出机", "牵引机", "切割机"]):
        return "production_capacity", "product_library", "enterprise_fact"
    if any(key in text for key in ["试验", "检测", "电子天平", "维卡", "锤击", "熔体", "拉力", "人员证书", "花名册", "劳动合同", "社保"]):
        target = "product_library" if "照片" in text or "设备" in text else "qualification_library"
        return "testing_capacity", target, "enterprise_fact"
    if any(key in text for key in ["审计报告", "银行资信", "授信证明"]):
        return "finance", "qualification_library", "enterprise_fact"
    if any(key in text for key in ["绿色", "ESG", "碳足迹", "废水", "废气", "废固", "环保"]):
        return "green_low_carbon", "product_library", "enterprise_fact"
    if any(key in text for key in ["合同", "中标通知书", "供货"]):
        return "project_performance", "qualification_library", "enterprise_fact"
    if any(key in text for key in ["营业执照", "开户许可证", "信用信息", "信用中国", "法定代表人", "身份证明", "授权委托书", "保证金"]):
        return "business_license", "qualification_library", "enterprise_fact"
    if any(key in text for key in ["质量管理体系", "环境管理体系", "职业健康安全", "认证证书"]):
        return "certification", "qualification_library", "enterprise_fact"
    if "宣传彩页" in text:
        return "enterprise_profile", "knowledge_library", "enterprise_fact"
    if path == BRAND_LOGO:
        return "brand_logo", "qualification_library", "brand_asset"
    return "enterprise_evidence", "knowledge_library", "enterprise_fact"


def _category_label(evidence_type: str) -> str:
    return {
        "brand_logo": "品牌标识",
        "business_license": "基础证照",
        "certification": "资质证书",
        "enterprise_evidence": "企业证明材料",
        "enterprise_profile": "企业宣传资料",
        "finance": "财务资料",
        "green_low_carbon": "绿色低碳资料",
        "inspection_report": "检验报告",
        "production_capacity": "生产制造能力",
        "project_performance": "项目业绩",
        "signature_seal": "签章资料",
        "testing_capacity": "试验检测能力",
    }.get(evidence_type, "企业资料")


def _library_type(target_library: str) -> str:
    return "qualification" if target_library == "qualification_library" else "product"


def _asset_type(target_library: str) -> str:
    return "qualification_image" if target_library == "qualification_library" else "product_image"


def _is_sensitive(evidence_type: str, source_file: str) -> bool:
    return evidence_type in {"finance", "signature_seal"} or any(
        key in source_file for key in ["劳动合同", "社保", "人员花名册", "身份证", "保证金", "银行"]
    )


def _inventory_record(path: Path) -> dict[str, Any]:
    evidence_type, target_library, policy = _classify(path)
    record = {
        "source_file": _rel(path),
        "file_name": path.name,
        "suffix": path.suffix.lower(),
        "file_size": path.stat().st_size,
        "sha256": _sha256_file(path),
        "enterprise": ENTERPRISE_SHORT,
        "doc_owner": ENTERPRISE_FULL,
        "source_domain": "enterprise_fact",
        "reference_only": False,
        "fact_source_allowed_for_enterprise": True,
        "tenant_visibility": "taichang_only",
        "access_scope": "taichang_tenant_internal",
        "evidence_type": evidence_type,
        "evidence_type_label": _category_label(evidence_type),
        "target_library": target_library,
        "target_library_label": "资信库" if target_library == "qualification_library" else "产品库",
        "auto_usage_policy": policy,
        "doc_role": "enterprise_evidence",
        "source_category": "05_enterprise_documents",
        "batch_no": "taichang_supplement_20260611",
        "material_category": "电缆保护管CPVC/MPP",
    }
    if policy.startswith("restricted"):
        record.update({
            "fact_source_allowed_for_enterprise": False,
            "allowed_for_bid": False,
            "reference_only": True,
            "quality_flags": ["restricted_signature_or_seal_asset_manual_use_only"],
        })
    return record


def _pdf_text(path: Path) -> tuple[str, int, int, str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = _clean_text("\n\n".join(page.strip() for page in pages if page.strip()))
    recommendation = "text_pdf_parse" if len(text.strip()) >= 100 else "render_full_page_image_asset_or_ocr"
    return text, len(reader.pages), len(text.strip()), recommendation


def _render_pdf_pages(path: Path, output_dir: Path, *, scale: float = 2.0) -> list[Path]:
    import pypdfium2 as pdfium

    output_dir.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(str(path))
    rendered: list[Path] = []
    for index in range(len(document)):
        page = document[index]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        if image.mode != "RGB":
            image = image.convert("RGB")
        out = output_dir / f"{_safe_stem(path.stem)}_第{index + 1:03d}页.jpg"
        image.save(out, "JPEG", quality=92, optimize=True)
        rendered.append(out)
        page.close()
    document.close()
    return rendered


def _asset_payload(source: Path, image_path: Path, record: dict[str, Any], *, page_no: int | None, rendered_from_pdf: bool) -> dict[str, Any]:
    width = height = None
    try:
        with Image.open(image_path) as image:
            width, height = image.size
    except Exception:
        pass
    evidence_type = record["evidence_type"]
    target_library = record["target_library"]
    source_name = Path(record["source_file"]).stem
    page_text = f"第{page_no}页" if page_no is not None else "原图"
    title = "泰昌官方Logo" if evidence_type == "brand_logo" else f"泰昌{source_name}{page_text}"
    category = _category_label(evidence_type)
    tags = [ENTERPRISE_SHORT, "泰昌企业事实", category]
    for key in ["CPVC", "MPP", "检验报告", "生产线", "电子天平", "万能试验机", "绿色供应链", "ESG", "碳足迹", "营业执照"]:
        if key in record["source_file"]:
            tags.append(key)
    metadata = {
        "source_batch_id": BATCH_ID,
        "source_domain": "enterprise_fact",
        "doc_owner": ENTERPRISE_SHORT,
        "enterprise": ENTERPRISE_SHORT,
        "evidence_type": evidence_type,
        "evidence_type_label": category,
        "target_library": target_library,
        "target_library_label": record["target_library_label"],
        "source_file": record["source_file"],
        "source_display_name": title,
        "source_file_name": Path(record["source_file"]).name,
        "page_no": page_no,
        "asset_visual_type": "full_page_render" if rendered_from_pdf else "customer_original_image",
        "full_page": True,
        "rendered_from_pdf": rendered_from_pdf,
        "tenant_visibility": "taichang_only",
        "access_scope": "taichang_tenant_internal",
        "reference_only": record.get("reference_only", False),
        "fact_source_allowed_for_enterprise": record.get("fact_source_allowed_for_enterprise", True),
        "allowed_for_bid": record.get("allowed_for_bid", True),
        "do_not_mix_with": ["河北豪乾参考稿", "辽宁招标资料"],
        "display_language": "zh-CN",
        "ui_name_policy": "domestic_chinese_friendly",
    }
    if record.get("quality_flags"):
        metadata["quality_flags"] = record["quality_flags"]
    description = f"{ENTERPRISE_FULL}{category}资料，来源于客户补充文件《{Path(record['source_file']).name}》{page_text}。"
    return {
        "title": title,
        "description": description,
        "category": category,
        "asset_type": _asset_type(target_library),
        "file_name": image_path.name,
        "file_ext": image_path.suffix.lower().lstrip("."),
        "mime_type": "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg",
        "file_size": image_path.stat().st_size,
        "local_path": _rel(image_path),
        "width": width,
        "height": height,
        "source_type": "customer_pdf_full_page_render" if rendered_from_pdf else "customer_original_image",
        "license": "客户自有资料",
        "attribution": ENTERPRISE_FULL,
        "is_synthetic": False,
        "is_sensitive": _is_sensitive(evidence_type, record["source_file"]),
        "anonymized": False,
        "industry": "电力行业",
        "applicable_sections": [category],
        "applicable_volumes": ["qualification", "business"] if target_library == "qualification_library" else ["technical"],
        "tags": list(dict.fromkeys(tags)),
        "specs": {
            "evidence_type": evidence_type,
            "target_library": target_library,
            "page_no": page_no,
            "asset_visual_type": metadata["asset_visual_type"],
            "display_name": title,
        },
        "ocr_text": "",
        "ai_caption": description,
        "searchable_text": "\n".join([title, description, category, " ".join(tags), record["source_file"]]),
        "status": "indexed",
        "metadata": metadata,
    }


def build_staging(*, render_assets: bool) -> dict[str, Any]:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text_dir = OUT_ROOT / "texts"
    render_dir = OUT_ROOT / "formal_image_assets"
    records = [_inventory_record(path) for path in sorted(SOURCE_ROOT.rglob("*")) if path.is_file()]
    if BRAND_LOGO.exists():
        records.append(_inventory_record(BRAND_LOGO))

    manifest_records: list[dict[str, Any]] = []
    asset_payloads: list[dict[str, Any]] = []
    for record in records:
        source = PROJECT_ROOT / record["source_file"]
        suffix = source.suffix.lower()
        output_file = None
        text_chars = 0
        pdf_pages = None
        recommendation = record["auto_usage_policy"]
        if suffix == ".pdf":
            try:
                text, pdf_pages, text_chars, recommendation = _pdf_text(source)
                if text_chars >= 100 and not record["auto_usage_policy"].startswith("restricted"):
                    output = text_dir / f"{_safe_stem(record['source_file'])}.md"
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(f"# {source.stem}\n\n{text.strip()}\n", encoding="utf-8")
                    output_file = _rel(output)
            except Exception as exc:
                recommendation = f"needs_review: {exc}"
        elif suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            recommendation = "customer_original_image_asset"

        if suffix in {".jpg", ".jpeg", ".png", ".webp"} and not record["auto_usage_policy"].startswith("restricted"):
            asset_payloads.append(_asset_payload(source, source, record, page_no=None, rendered_from_pdf=False))
        elif suffix == ".pdf" and not record["auto_usage_policy"].startswith("restricted"):
            if render_assets:
                try:
                    rendered = _render_pdf_pages(source, render_dir / _safe_stem(record["source_file"]))
                    for index, image_path in enumerate(rendered, start=1):
                        asset_payloads.append(_asset_payload(source, image_path, record, page_no=index, rendered_from_pdf=True))
                except Exception as exc:
                    record.setdefault("quality_flags", []).append(f"render_failed:{exc}")

        record.update({
            "pdf_pages": pdf_pages,
            "text_chars": text_chars,
            "parse_recommendation": recommendation,
            "output_file": output_file,
        })
        if output_file:
            metadata = {
                "seed_corpus": "power_grid_customer_corpus",
                "source_domain": "enterprise_fact",
                "province": "河北",
                "batch_no": "taichang_supplement_20260611",
                "package_no": "",
                "package_code": "2225AC",
                "material_category": "电缆保护管CPVC/MPP",
                "doc_role": "enterprise_evidence",
                "source_file": record["source_file"],
                "source_display_name": Path(record["source_file"]).stem,
                "source_category": "05_enterprise_documents",
                "category_label": _category_label(record["evidence_type"]),
                "chunker": "parent_child_v2",
                "ingestion_batch_id": BATCH_ID,
                "doc_version": 1,
                "status": "parsed_pending_ingestion",
                "doc_owner": ENTERPRISE_SHORT,
                "enterprise": ENTERPRISE_SHORT,
                "source_type": "pdf_text",
                "parser": "pypdf_text",
                "evidence_type": record["evidence_type"],
                "evidence_type_label": _category_label(record["evidence_type"]),
                "target_library": record["target_library"],
                "target_library_label": record["target_library_label"],
                "privacy_level": "taichang_internal_private" if _is_sensitive(record["evidence_type"], record["source_file"]) else "private",
                "reference_only": False,
                "fact_source_allowed_for_enterprise": True,
                "access_scope": "taichang_tenant_internal",
                "tenant_visibility": "taichang_only",
                "sensitive_handling": "taichang_internal_use_no_redaction_required",
                "do_not_mix_with": ["河北豪乾参考稿", "辽宁招标资料"],
            }
            manifest_records.append({
                "source_file": record["source_file"],
                "output_file": output_file,
                "province": "河北",
                "batch_no": "taichang_supplement_20260611",
                "package_no": "",
                "package_code": "2225AC",
                "material_category": "电缆保护管CPVC/MPP",
                "doc_role": "enterprise_evidence",
                "qualification_mode": None,
                "source_type": "pdf",
                "parser": "pypdf_text",
                "parse_status": "parsed",
                "sha256": _sha256_text((PROJECT_ROOT / output_file).read_text(encoding="utf-8")),
                "file_size": source.stat().st_size,
                "text_chars": text_chars,
                "metadata": metadata,
            })

    summary = {
        "batch_id": BATCH_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": _rel(SOURCE_ROOT),
        "total_files": len(records),
        "manifest_records": len(manifest_records),
        "asset_payloads": len(asset_payloads),
        "by_suffix": dict(Counter(record["suffix"] for record in records)),
        "by_evidence_type": dict(Counter(record["evidence_type"] for record in records)),
        "restricted_files": [record["source_file"] for record in records if record.get("allowed_for_bid") is False],
    }
    inventory = {"summary": summary, "records": records}
    manifest = {"batch_id": BATCH_ID, "records": manifest_records}
    assets = {"batch_id": BATCH_ID, "assets": asset_payloads}
    (OUT_ROOT / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_ROOT / "asset_staging_payloads.json").write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_inventory_md(inventory)
    return summary


def _write_inventory_md(inventory: dict[str, Any]) -> None:
    summary = inventory["summary"]
    lines = [
        "# 泰昌资质文件补充批次 Inventory",
        "",
        f"- 批次：`{summary['batch_id']}`",
        f"- 文件数：{summary['total_files']}",
        f"- 文本入库候选：{summary['manifest_records']}",
        f"- 图片资产候选：{summary['asset_payloads']}",
        "",
        "## 类型统计",
        "",
        "| 类型 | 数量 |",
        "| --- | ---: |",
    ]
    for key, value in summary["by_suffix"].items():
        lines.append(f"| `{key or '无后缀'}` | {value} |")
    lines += ["", "## 证据类型统计", "", "| evidence_type | 数量 |", "| --- | ---: |"]
    for key, value in summary["by_evidence_type"].items():
        lines.append(f"| `{key}` | {value} |")
    lines += [
        "",
        "## 受限资料",
        "",
        "以下资料只作人工复核或手工签章用途，不自动进入标书配图或企业事实问答：",
    ]
    for item in summary["restricted_files"]:
        lines.append(f"- `{item}`")
    lines += [
        "",
        "## 文件清单",
        "",
        "| 文件 | 类型 | evidence_type | target_library | 处理建议 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in inventory["records"]:
        lines.append(
            f"| `{record['source_file']}` | `{record['suffix']}` | `{record['evidence_type']}` | "
            f"`{record['target_library']}` | {record.get('parse_recommendation') or record.get('auto_usage_policy')} |"
        )
    (OUT_ROOT / "inventory.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-render-assets", action="store_true")
    args = parser.parse_args()
    summary = build_staging(render_assets=not args.no_render_assets)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

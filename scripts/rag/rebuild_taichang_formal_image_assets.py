#!/usr/bin/env python3
"""Rebuild Taichang formal image assets from customer-provided PDFs/JPGs.

This script replaces MinerU extracted-region image assets with formal assets:
PDFs are rendered page-by-page as full-page images, while customer-provided
images are imported as original images. User-facing titles/categories/tags are
Chinese; technical English enums remain only in metadata/specs for filtering.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.postgres_pool import pooled_connection  # noqa: E402
from backend.db.supabase_repo import create_knowledge_asset, upload_knowledge_asset_file  # noqa: E402

BATCH_ID = "customer_liaoning_taichang_20260606_p0"
FORMAL_BATCH_ID = f"{BATCH_ID}_formal_full_page_assets_v1"
PARSED_ROOT = PROJECT_ROOT / "parsed_outputs" / "power_grid_customer_corpus" / BATCH_ID
PARSE_QUALITY = PARSED_ROOT / "parse_quality_report.json"
RENDER_ROOT = PARSED_ROOT / "formal_image_assets"
REPORT_PATH = PARSED_ROOT / "staging" / "rebuild_formal_image_assets_report.json"

TAICHANG_FULL_NAME = "河北泰昌电力器材科技有限公司"
TAICHANG_SHORT_NAME = "泰昌"


@dataclass
class SourceRecord:
    source_file: str
    evidence_type: str
    target_library: str
    recommendation: str = ""
    quality_flags: list[str] | None = None


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required")
    return url


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _safe_stem(value: str) -> str:
    clean = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", value, flags=re.UNICODE).strip("_")
    return clean[:96] or "asset"


def _load_source_records() -> list[SourceRecord]:
    report = json.loads(PARSE_QUALITY.read_text(encoding="utf-8"))
    records = [
        SourceRecord(
            source_file=item["source_file"],
            evidence_type=item.get("evidence_type") or "enterprise_fact",
            target_library=item.get("target_library") or "product_library",
            recommendation=item.get("recommendation") or "",
            quality_flags=item.get("quality_flags") or [],
        )
        for item in report.get("records", [])
        if item.get("source_file")
    ]
    account_license = PROJECT_ROOT / "rag_seed/power_grid_resources/05_enterprise_documents/01_泰昌MVP试点企业资料/extracted/泰昌资料/开户许可证.jpg"
    if account_license.exists():
        records.append(
            SourceRecord(
                source_file=_rel(account_license),
                evidence_type="bank_account_certificate",
                target_library="qualification_library",
                recommendation="direct_image_asset_candidate",
                quality_flags=["taichang_internal_private_allowed_for_tenant_use"],
            )
        )
    return records


def _delete_existing_assets(batch_ids: list[str]) -> int:
    with pooled_connection(_database_url(), row_factory=dict_row) as conn:
        cur = conn.execute(
            """
            delete from public.knowledge_assets
            where metadata->>'source_batch_id' = any(%s)
               or metadata->>'formal_source_batch_id' = any(%s)
            """,
            [batch_ids, batch_ids],
        )
        return cur.rowcount


def _library_type(target_library: str) -> str:
    return "qualification" if target_library == "qualification_library" else "product"


def _asset_type(target_library: str) -> str:
    return "qualification_image" if target_library == "qualification_library" else "product_image"


def _volume_scope(target_library: str, evidence_type: str) -> list[str]:
    if target_library == "qualification_library":
        return ["qualification", "business", "attachment"]
    if evidence_type in {"inspection_report", "green_low_carbon"}:
        return ["technical", "qualification", "business"]
    return ["technical"]


def _asset_category(evidence_type: str, source_file: str, target_library: str) -> str:
    name = Path(source_file).stem
    if evidence_type == "business_license":
        return "基础证照"
    if evidence_type == "bank_account_certificate":
        return "基础证照"
    if evidence_type == "certification":
        if any(keyword in name for keyword in ["绿色", "低碳", "ESG", "碳足迹"]):
            return "绿色低碳资料"
        return "资质证书"
    if evidence_type == "finance":
        return "财务资料"
    if evidence_type == "inspection_report":
        return "检验报告"
    if evidence_type == "testing_capacity":
        if "人员" in source_file or "劳动合同" in source_file or "社保" in source_file or "参保证明" in source_file:
            return "人员证书"
        return "试验检测设备"
    if evidence_type == "production_capacity":
        if "人员" in source_file or "劳动合同" in source_file or "社保" in source_file or "参保证明" in source_file:
            return "人员证书"
        if any(keyword in source_file for keyword in ["土地", "厂房", "电费"]):
            return "厂房仓储资料"
        return "生产制造能力"
    if evidence_type == "green_low_carbon":
        return "绿色低碳资料"
    return "企业资信资料" if target_library == "qualification_library" else "产品能力资料"


def _evidence_label(evidence_type: str) -> str:
    return {
        "business_license": "营业执照",
        "bank_account_certificate": "开户许可证",
        "certification": "资质证书",
        "finance": "财务资料",
        "inspection_report": "检验报告",
        "production_capacity": "生产制造能力",
        "testing_capacity": "试验检测能力",
        "green_low_carbon": "绿色低碳资料",
    }.get(evidence_type, "企业资料")


def _tag_values(evidence_type: str, source_file: str, target_library: str) -> list[str]:
    tags = [TAICHANG_SHORT_NAME, "泰昌企业事实", _evidence_label(evidence_type)]
    name = Path(source_file).stem
    for keyword in [
        "营业执照", "开户许可证", "质量管理体系", "环境管理体系", "职业健康安全",
        "CPVC", "MPP", "检验报告", "审计报告", "生产线", "厂房", "电子天平",
        "万能试验机", "维卡", "锤击", "熔体流动速率仪", "电子拉力试验机",
        "绿色供应链", "绿色电力", "ESG", "碳足迹", "人员证书", "社保证明",
    ]:
        if keyword in source_file or keyword in name:
            tags.append(keyword)
    tags.append("资信库" if target_library == "qualification_library" else "产品库")
    return list(dict.fromkeys(tags))


def _title_for(record: SourceRecord, page_no: int | None = None) -> str:
    name = Path(record.source_file).stem
    if record.evidence_type == "business_license":
        base = "泰昌营业执照副本"
    elif record.evidence_type == "bank_account_certificate":
        base = "泰昌开户许可证"
    else:
        base = f"泰昌{name}"
    if page_no is not None:
        return f"{base}第{page_no}页"
    return base


def _description_for(record: SourceRecord, page_no: int | None = None) -> str:
    page_text = f"第{page_no}页" if page_no is not None else "原始图片"
    return (
        f"{TAICHANG_FULL_NAME}{_evidence_label(record.evidence_type)}资料，"
        f"来源于客户已提供文件《{Path(record.source_file).name}》{page_text}。"
        "该图片为正式整页/原图资产，不是 MinerU 局部切图。"
    )


def _is_sensitive(record: SourceRecord) -> bool:
    source_file = record.source_file
    if "taichang_internal_private_allowed_for_tenant_use" in (record.quality_flags or []):
        return True
    return record.evidence_type in {"finance", "bank_account_certificate"} or any(
        keyword in source_file for keyword in ["劳动合同", "社保", "参保证明", "人员花名册", "人员证书"]
    )


def _target_metadata(record: SourceRecord, *, page_no: int | None, page_index: int | None, visual_type: str, rendered_from_pdf: bool) -> dict[str, Any]:
    metadata = {
        "source_batch_id": FORMAL_BATCH_ID,
        "formal_source_batch_id": FORMAL_BATCH_ID,
        "replaces_source_batch_id": BATCH_ID,
        "source_domain": "enterprise_fact",
        "doc_owner": TAICHANG_SHORT_NAME,
        "enterprise": TAICHANG_SHORT_NAME,
        "evidence_type": record.evidence_type,
        "target_library": record.target_library,
        "source_file": record.source_file,
        "source_file_name": Path(record.source_file).name,
        "page_no": page_no,
        "page_index": page_index,
        "asset_visual_type": visual_type,
        "full_page": True,
        "extracted_region": False,
        "rendered_from_pdf": rendered_from_pdf,
        "tenant_visibility": "taichang_only",
        "access_scope": "taichang_tenant_internal",
        "reference_only": False,
        "fact_source_allowed_for_enterprise": True,
        "do_not_mix_with": ["河北豪乾参考稿", "辽宁招标资料"],
        "display_language": "zh-CN",
        "ui_name_policy": "domestic_chinese_friendly",
    }
    if record.quality_flags:
        metadata["quality_flags"] = record.quality_flags
    return metadata


def _render_pdf_pages(record: SourceRecord, *, dpi_scale: float, max_pages: int | None) -> list[dict[str, Any]]:
    import pypdfium2 as pdfium

    source = PROJECT_ROOT / record.source_file
    document = pdfium.PdfDocument(str(source))
    page_count = len(document)
    if max_pages is not None:
        page_count = min(page_count, max_pages)
    output_dir = RENDER_ROOT / _safe_stem(Path(record.source_file).stem)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[dict[str, Any]] = []
    for index in range(page_count):
        page = document[index]
        bitmap = page.render(scale=dpi_scale)
        image = bitmap.to_pil()
        if image.mode != "RGB":
            image = image.convert("RGB")
        page_no = index + 1
        out_path = output_dir / f"{_safe_stem(Path(record.source_file).stem)}_第{page_no:03d}页.jpg"
        image.save(out_path, "JPEG", quality=92, optimize=True)
        rendered.append({"path": out_path, "page_no": page_no, "page_index": index, "page_count": len(document)})
        page.close()
    document.close()
    return rendered


def _image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def _visual_type(record: SourceRecord, rendered_from_pdf: bool) -> str:
    if record.evidence_type == "business_license":
        return "full_page_document_image"
    if record.evidence_type == "certification":
        return "full_page_certificate"
    if record.evidence_type == "inspection_report":
        return "full_page_inspection_report"
    if not rendered_from_pdf:
        return "customer_original_image"
    return "full_page_render"


def _build_payload(record: SourceRecord, image_path: Path, *, page_no: int | None, page_index: int | None, rendered_from_pdf: bool) -> dict[str, Any]:
    width, height = _image_dimensions(image_path)
    visual_type = _visual_type(record, rendered_from_pdf)
    category = _asset_category(record.evidence_type, record.source_file, record.target_library)
    tags = _tag_values(record.evidence_type, record.source_file, record.target_library)
    applicable_volumes = _volume_scope(record.target_library, record.evidence_type)
    source_label = Path(record.source_file).stem
    searchable_parts = [
        _title_for(record, page_no),
        _description_for(record, page_no),
        category,
        " ".join(tags),
        source_label,
        _evidence_label(record.evidence_type),
        TAICHANG_SHORT_NAME,
        TAICHANG_FULL_NAME,
    ]
    return {
        "title": _title_for(record, page_no),
        "description": _description_for(record, page_no),
        "category": category,
        "asset_type": _asset_type(record.target_library),
        "file_name": image_path.name,
        "file_ext": image_path.suffix.lower().lstrip("."),
        "mime_type": "image/jpeg",
        "file_size": image_path.stat().st_size,
        "local_path": _rel(image_path),
        "width": width,
        "height": height,
        "source_type": "customer_pdf_full_page_render" if rendered_from_pdf else "customer_original_image",
        "license": "客户自有资料",
        "attribution": TAICHANG_FULL_NAME,
        "is_synthetic": False,
        "is_sensitive": _is_sensitive(record),
        "anonymized": False,
        "industry": "电力行业",
        "applicable_sections": [
            "资格审查资料" if record.target_library == "qualification_library" else "技术响应文件",
            category,
        ],
        "applicable_volumes": applicable_volumes,
        "tags": tags,
        "specs": {
            "page_no": page_no,
            "page_index": page_index,
            "evidence_type": record.evidence_type,
            "target_library": record.target_library,
            "asset_visual_type": visual_type,
            "full_page": True,
            "display_name": _title_for(record, page_no),
        },
        "ocr_text": "",
        "ai_caption": _description_for(record, page_no),
        "searchable_text": "\n".join(part for part in searchable_parts if part),
        "status": "indexed",
        "metadata": _target_metadata(
            record,
            page_no=page_no,
            page_index=page_index,
            visual_type=visual_type,
            rendered_from_pdf=rendered_from_pdf,
        ),
    }


def _source_images(record: SourceRecord, *, dpi_scale: float, max_pages: int | None) -> list[dict[str, Any]]:
    source = PROJECT_ROOT / record.source_file
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        return _render_pdf_pages(record, dpi_scale=dpi_scale, max_pages=max_pages)
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return [{"path": source, "page_no": None, "page_index": None, "page_count": None}]
    return []


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = path.with_suffix(".md")
    lines = [
        "# 泰昌正式图片资产重建报告",
        "",
        f"- 批次：`{report['formal_batch_id']}`",
        f"- 生成时间：{report['generated_at']}",
        f"- dry-run：`{report['dry_run']}`",
        f"- refresh：`{report['refresh']}`",
        "",
        "## 汇总",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| source_files | {report['source_files']} |",
        f"| rendered_or_original_images | {report['images']} |",
        f"| imported | {report['imported']} |",
        f"| deleted_existing | {report['deleted_existing']} |",
        f"| failed | {report['failed']} |",
        "",
        "## 说明",
        "",
        "- 本次只使用客户已提供 PDF/JPG 的整页渲染图或原图。",
        "- MinerU 局部图片块不再作为正式资信库/产品库展示资产。",
        "- 面向用户展示的标题、分类、标签均已改为中文。",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="delete existing Taichang image assets for old/formal batches before import")
    parser.add_argument("--dpi-scale", type=float, default=2.0, help="pypdfium render scale; 2.0 is roughly 144 DPI")
    parser.add_argument("--max-pages-per-file", type=int, default=None)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    records = _load_source_records()
    RENDER_ROOT.mkdir(parents=True, exist_ok=True)

    deleted_existing = 0
    if args.refresh and not args.dry_run:
        deleted_existing = _delete_existing_assets([BATCH_ID, FORMAL_BATCH_ID])

    items: list[dict[str, Any]] = []
    imported = 0
    failed = 0
    image_count = 0
    for record in records:
        source = PROJECT_ROOT / record.source_file
        if not source.exists():
            failed += 1
            items.append({"status": "missing_source", "source_file": record.source_file})
            continue
        try:
            images = _source_images(record, dpi_scale=args.dpi_scale, max_pages=args.max_pages_per_file)
            for image in images:
                image_count += 1
                image_path = Path(image["path"])
                payload = _build_payload(
                    record,
                    image_path,
                    page_no=image["page_no"],
                    page_index=image["page_index"],
                    rendered_from_pdf=source.suffix.lower() == ".pdf",
                )
                item = {
                    "status": "dry_run" if args.dry_run else "imported",
                    "title": payload["title"],
                    "category": payload["category"],
                    "asset_type": payload["asset_type"],
                    "source_file": record.source_file,
                    "local_path": payload["local_path"],
                    "page_no": image["page_no"],
                    "width": payload["width"],
                    "height": payload["height"],
                }
                if not args.dry_run:
                    storage_info = upload_knowledge_asset_file(
                        local_file_path=image_path,
                        original_filename=image_path.name,
                        library_type=_library_type(record.target_library),
                    )
                    payload.update({
                        "file_ext": storage_info.get("file_ext"),
                        "mime_type": storage_info.get("mime_type"),
                        "file_size": storage_info.get("file_size"),
                        "storage_bucket": storage_info.get("bucket"),
                        "storage_path": storage_info.get("object_path"),
                        "public_url": storage_info.get("public_url"),
                        "metadata": {
                            **(payload.get("metadata") or {}),
                            "thumbnail_storage_bucket": storage_info.get("thumbnail_bucket"),
                            "thumbnail_storage_path": storage_info.get("thumbnail_path"),
                            "thumbnail_mime_type": storage_info.get("thumbnail_mime_type"),
                            "thumbnail_size": storage_info.get("thumbnail_size"),
                        },
                    })
                    created = create_knowledge_asset(payload)
                    item["id"] = str(created.get("id"))
                    imported += 1
                    time.sleep(0.01)
                items.append(item)
        except Exception as exc:
            failed += 1
            items.append({"status": "failed", "source_file": record.source_file, "error": str(exc)})

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_batch_id": BATCH_ID,
        "formal_batch_id": FORMAL_BATCH_ID,
        "dry_run": args.dry_run,
        "refresh": args.refresh,
        "source_files": len(records),
        "images": image_count,
        "imported": imported,
        "deleted_existing": deleted_existing,
        "failed": failed,
        "items": items,
    }
    _write_report(args.report.resolve(), report)
    print(json.dumps({k: report[k] for k in ["formal_batch_id", "dry_run", "source_files", "images", "imported", "deleted_existing", "failed"]}, ensure_ascii=False, indent=2))
    print(f"Report: {_rel(args.report.resolve())}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

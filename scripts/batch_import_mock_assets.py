#!/usr/bin/env python3
"""Batch import generated qualification/product images into knowledge_assets.

Examples:
  python scripts/batch_import_mock_assets.py --dry-run
  python scripts/batch_import_mock_assets.py
  python scripts/batch_import_mock_assets.py --no-embedding
"""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.supabase_client import get_supabase_client  # noqa: E402
from backend.db.supabase_repo import create_knowledge_asset, upload_knowledge_asset_file  # noqa: E402

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def split_words(text: str) -> list[str]:
    return [item.strip() for item in text.replace("_", " ").replace("-", " ").split() if item.strip()]


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        clean = str(item or "").strip()
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result


def infer_credit_category(title: str) -> str:
    if any(key in title for key in ["营业执照", "基本存款", "开户", "纳税", "完税", "信用查询", "声明"]):
        return "基础证照"
    if any(key in title for key in ["体系认证", "资质", "安全生产许可证"]):
        return "资质证书"
    if any(key in title for key in ["项目经理", "安全生产考核", "岗位证书", "资格证书", "施工员", "质量员", "材料员", "资料员", "造价", "安全员", "B 证", "C 证"]):
        return "人员证书"
    if any(key in title for key in ["财务", "审计", "完税"]):
        return "财务资料"
    if any(key in title for key in ["中标通知书", "施工合同", "竣工", "完工", "履约评价", "业绩"]):
        return "项目业绩"
    if any(key in title for key in ["投标函", "偏离表", "保证金", "保函", "授权", "身份证明"]):
        return "商务响应模板"
    return "企业资信"


def infer_credit_sections(category: str, title: str) -> list[str]:
    sections = {
        "基础证照": ["资格审查资料", "企业基本情况表", "企业资信证明", "商务响应文件"],
        "资质证书": ["资格审查资料", "企业资质证书", "安全生产许可", "体系认证材料"],
        "人员证书": ["项目管理机构", "主要人员简历表", "项目经理资格", "人员证书与社保"],
        "财务资料": ["近年财务状况表", "资格审查资料", "企业财务能力"],
        "项目业绩": ["类似项目业绩", "近年完成的类似工程情况表", "履约评价证明"],
        "商务响应模板": ["投标函及附录", "商务条款响应", "偏离表及承诺", "投标保证金"],
    }.get(category, ["资格审查资料", "商务响应文件"])
    if "技术偏离表" in title:
        sections = ["技术条款响应", "技术偏离表", "施工组织设计"]
    return sections


def infer_product_category(title: str) -> str:
    if any(key in title for key in ["灌浆", "旋喷", "防渗墙", "防渗"]):
        return "水库除险加固"
    if any(key in title for key in ["检测", "试验", "仪器"]):
        return "检测与试验设备"
    if any(key in title for key in ["进度", "资源配置", "组织机构", "质量保证体系", "主要机械设备", "劳动力配置"]):
        return "技术标图表模板"
    if any(key in title for key in ["安全文明", "标准化设施", "临边防护", "消防器材", "扬尘控制"]):
        return "安全文明施工设施"
    if any(key in title for key in ["闸门", "启闭机", "拦污栅", "埋件"]):
        return "金属结构与闸门"
    if any(key in title for key in ["泵", "控制柜"]):
        return "泵站设备"
    return "水利施工设备"


def infer_product_sections(category: str, title: str) -> list[str]:
    if category == "水库除险加固":
        return ["坝基防渗处理施工方案", "施工组织设计", "质量控制措施", "资源配置计划"]
    if category == "检测与试验设备":
        return ["质量保证措施", "试验检测计划", "施工过程检测", "设备配置"]
    if category == "技术标图表模板":
        if "进度" in title:
            return ["施工总进度计划", "进度保证措施", "施工组织设计"]
        if any(key in title for key in ["资源", "主要机械设备", "劳动力"]):
            return ["资源配置计划", "主要施工设备表", "劳动力计划"]
        if "组织" in title:
            return ["项目管理机构", "施工组织管理", "人员职责分工"]
        return ["质量保证体系", "质量控制流程", "施工组织设计"]
    if category == "安全文明施工设施":
        return ["安全文明施工措施", "安全生产管理", "环境保护措施", "施工现场布置"]
    return ["技术响应文件", "施工组织设计", "设备配置", "产品参数说明"]


def infer_credit_tags(title: str, category: str) -> list[str]:
    tags = ["脱敏样张", "需人工替换", "不可作为正式投标原件", category]
    keyword_tags = {
        "基本存款": ["开户信息", "银行账户", "商务标"],
        "信用": ["信用查询", "失信核查", "风险检查"],
        "纳税": ["纳税信用", "税务证明"],
        "完税": ["完税证明", "税务证明"],
        "声明": ["无重大违法记录", "承诺函"],
        "中标通知书": ["类似业绩", "中标通知书"],
        "施工合同": ["类似业绩", "合同关键页"],
        "履约评价": ["类似业绩", "履约评价"],
        "投标保证金": ["保证金", "银行回单"],
        "投标函": ["投标函", "商务响应"],
        "偏离表": ["偏离表", "条款响应"],
        "体系认证": ["体系认证", "质量安全环保"],
        "岗位证书": ["人员证书", "岗位证"],
        "项目经理": ["项目经理", "人员证书"],
        "造价": ["造价人员", "人员证书"],
        "安全生产": ["安全生产", "三类人员证"],
    }
    for key, values in keyword_tags.items():
        if key in title:
            tags.extend(values)
    return unique(tags)


def infer_product_tags(title: str, category: str) -> list[str]:
    tags = ["产品图", "白底展示", "技术参数", "可插入技术标", category]
    keyword_tags = {
        "帷幕灌浆": ["帷幕灌浆", "坝基防渗", "灌浆设备"],
        "旋喷": ["高压旋喷", "地基处理", "防渗处理"],
        "防渗墙": ["防渗墙", "成槽设备", "泥浆循环"],
        "检测": ["质量检测", "检测仪器", "试验检测"],
        "安全文明": ["安全文明施工", "标准化设施", "安全环保"],
        "标准化设施": ["安全文明施工", "标准化设施", "安全环保"],
        "主要机械设备": ["资源配置", "机械设备", "劳动力计划"],
        "劳动力": ["资源配置", "机械设备", "劳动力计划"],
        "进度": ["进度计划", "横道图", "计划模板"],
        "资源": ["资源配置", "机械设备", "劳动力计划"],
        "组织": ["组织机构", "项目管理", "岗位职责"],
        "质量保证": ["质量保证体系", "质量流程", "质量控制"],
    }
    for key, values in keyword_tags.items():
        if key in title:
            tags.extend(values)
    return unique(tags)


def asset_exists(title: str, file_name: str) -> bool:
    client = get_supabase_client()
    title_response = client.table("knowledge_assets").select("id").eq("title", title).limit(1).execute()
    if title_response.data:
        return True
    file_response = client.table("knowledge_assets").select("id").eq("file_name", file_name).limit(1).execute()
    return bool(file_response.data)


def image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def build_searchable_text(payload: dict[str, Any]) -> str:
    parts = [
        payload.get("title"),
        payload.get("description"),
        payload.get("category"),
        payload.get("asset_type"),
        payload.get("ai_caption"),
        payload.get("ocr_text"),
    ]
    parts.extend(payload.get("tags") or [])
    parts.extend(payload.get("applicable_sections") or [])
    specs = payload.get("specs") or {}
    if isinstance(specs, dict):
        parts.extend(str(value) for value in specs.values() if value)
    metadata = payload.get("metadata") or {}
    if isinstance(metadata, dict):
        parts.extend(str(value) for value in metadata.values() if isinstance(value, str))
    return "\n".join(str(part).strip() for part in parts if str(part or "").strip())


def maybe_embed(text: str, enabled: bool) -> list[float] | None:
    if not enabled:
        return None
    try:
        from backend.rag.vector_store import get_embeddings, init_ali_client

        embeddings = get_embeddings(init_ali_client(), [text])
        return embeddings[0] if embeddings else None
    except Exception:
        logging.exception("资产 embedding 生成失败，降级为仅结构化入库")
        return None


def build_credit_payload(path: Path, embedding_enabled: bool) -> dict[str, Any]:
    title = path.stem
    category = infer_credit_category(title)
    tags = infer_credit_tags(title, category)
    sections = infer_credit_sections(category, title)
    width, height = image_size(path)
    description = (
        f"{title}，企业资信库脱敏合成样张，用于资格审查、商务响应、附件材料和智能客服图文检索。"
        "该文件仅用于系统测试和标书占位，正式投标前必须替换为企业真实资料并人工复核。"
    )
    payload = {
        "title": title,
        "description": description,
        "category": category,
        "asset_type": "qualification_image",
        "file_name": path.name,
        "width": width,
        "height": height,
        "source_type": "ai_synthetic_mock",
        "license": "脱敏合成样张，仅限系统测试",
        "attribution": "AI生成脱敏测试素材",
        "is_synthetic": True,
        "is_sensitive": True,
        "anonymized": True,
        "industry": "水利行业",
        "applicable_sections": sections,
        "tags": tags,
        "specs": {
            "library_type": "qualification",
            "allowed_for_bid": True,
            "usage_note": "脱敏样张，仅用于系统演示、RAG检索和标书占位；正式投标必须替换原件。",
            "recommended_volume": "business",
            "internal_volume_type": "qualification",
            "document_role": "证明材料",
            "sensitive_level": "high",
        },
        "ai_caption": description,
        "ocr_text": "脱敏样张，字段内容均为占位符，不包含真实证书编号、真实人员信息、真实企业信息或真实公章。",
        "status": "indexed",
        "metadata": {
            "library_type": "qualification",
            "allowed_for_bid": True,
            "upload_source": "batch_mock_asset_import",
            "source_folder": "credit_database",
            "synthetic_prompt_doc": "docs/企业资信库AI生图Prompt.md",
            "must_replace_before_bid": True,
            "recommended_volume": "business",
            "internal_volume_type": "qualification",
        },
    }
    payload["searchable_text"] = build_searchable_text(payload)
    embedding = maybe_embed(payload["searchable_text"], embedding_enabled)
    if embedding:
        payload["embedding"] = embedding
    return payload


def build_product_payload(path: Path, embedding_enabled: bool) -> dict[str, Any]:
    title = path.stem
    category = infer_product_category(title)
    tags = infer_product_tags(title, category)
    sections = infer_product_sections(category, title)
    width, height = image_size(path)
    description = (
        f"{title}，产品库白底设备/图表展示图，带脱敏性能参数说明，适合技术标、施工组织设计、"
        "设备配置、质量保证措施和智能客服图文检索。"
    )
    payload = {
        "title": title,
        "description": description,
        "category": category,
        "asset_type": "product_image",
        "file_name": path.name,
        "width": width,
        "height": height,
        "source_type": "ai_synthetic_mock",
        "license": "脱敏合成样张，仅限系统测试",
        "attribution": "AI生成产品测试素材",
        "is_synthetic": True,
        "is_sensitive": False,
        "anonymized": True,
        "industry": "水利行业",
        "applicable_sections": sections,
        "tags": tags,
        "specs": {
            "library_type": "product",
            "allowed_for_bid": True,
            "usage_note": "白底产品展示图，适合技术标插图和产品能力检索；参数为脱敏占位。",
            "recommended_volume": "technical",
            "internal_volume_type": "technical",
            "document_role": "技术配图",
            "background": "white",
            "has_parameter_panel": True,
        },
        "ai_caption": description,
        "ocr_text": "白底产品图，含脱敏技术参数、性能说明和适用章节信息，不包含真实品牌、真实铭牌或真实项目名称。",
        "status": "indexed",
        "metadata": {
            "library_type": "product",
            "allowed_for_bid": True,
            "upload_source": "batch_mock_asset_import",
            "source_folder": "product_database",
            "synthetic_prompt_doc": "docs/产品库AI生图Prompt.md",
            "recommended_volume": "technical",
            "internal_volume_type": "technical",
        },
    }
    payload["searchable_text"] = build_searchable_text(payload)
    embedding = maybe_embed(payload["searchable_text"], embedding_enabled)
    if embedding:
        payload["embedding"] = embedding
    return payload


def iter_images(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTS)


def import_one(path: Path, payload: dict[str, Any], library_type: str, dry_run: bool, skip_existing: bool) -> str:
    if dry_run:
        return "dry_run"
    if skip_existing and asset_exists(payload["title"], payload["file_name"]):
        return "skipped_existing"

    storage_info = upload_knowledge_asset_file(
        local_file_path=path,
        original_filename=path.name,
        library_type=library_type,
    )
    payload = {
        **payload,
        "file_ext": storage_info.get("file_ext"),
        "mime_type": storage_info.get("mime_type") or mimetypes.guess_type(path.name)[0],
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
    }
    create_knowledge_asset(payload)
    return "imported"


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch import generated credit/product images into knowledge_assets.")
    parser.add_argument("--root", default=str(ROOT), help="Project root. Defaults to repository root.")
    parser.add_argument("--credit-dir", default="assets/credit_database", help="Credit image directory relative to root.")
    parser.add_argument("--product-dir", default="assets/product_database", help="Product image directory relative to root.")
    parser.add_argument("--dry-run", action="store_true", help="Only print inferred metadata; do not upload.")
    parser.add_argument("--no-embedding", action="store_true", help="Skip DashScope embedding generation.")
    parser.add_argument("--no-skip-existing", action="store_true", help="Do not skip assets with same title or filename.")
    parser.add_argument("--report", default="outputs/mock_asset_import_report.json", help="Write import report JSON.")
    args = parser.parse_args()

    project_root = Path(args.root).resolve()
    credit_dir = (project_root / args.credit_dir).resolve()
    product_dir = (project_root / args.product_dir).resolve()
    embedding_enabled = not args.no_embedding and not args.dry_run
    skip_existing = not args.no_skip_existing

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

    jobs: list[tuple[Path, str, dict[str, Any]]] = []
    for path in iter_images(credit_dir):
        jobs.append((path, "qualification", build_credit_payload(path, embedding_enabled)))
    for path in iter_images(product_dir):
        jobs.append((path, "product", build_product_payload(path, embedding_enabled)))

    report: list[dict[str, Any]] = []
    for path, library_type, payload in jobs:
        status = import_one(path, payload, library_type, dry_run=args.dry_run, skip_existing=skip_existing)
        item = {
            "status": status,
            "file": str(path.relative_to(project_root)),
            "library_type": library_type,
            "title": payload["title"],
            "category": payload["category"],
            "asset_type": payload["asset_type"],
            "tags": payload["tags"],
            "applicable_sections": payload["applicable_sections"],
            "recommended_volume": payload["specs"].get("recommended_volume"),
        }
        report.append(item)
        print(json.dumps(item, ensure_ascii=False))

    report_path = (project_root / args.report).resolve()
    if not args.dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report: {report_path}")
    print(f"total={len(report)} imported={sum(1 for item in report if item['status'] == 'imported')} skipped={sum(1 for item in report if item['status'].startswith('skipped'))} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

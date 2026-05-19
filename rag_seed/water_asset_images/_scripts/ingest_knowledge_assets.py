import csv
import json
import mimetypes
import sys
from hashlib import sha1
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
ASSET_ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.rag.vector_store import get_embeddings, init_ali_client  # noqa: E402
from backend.db.supabase_client import get_supabase_client, upload_file_to_storage  # noqa: E402
from unidecode import unidecode  # noqa: E402

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

BUCKET = "knowledge-assets"
INDEX_FILE = ASSET_ROOT / "index.csv"


def _read_index() -> list[dict[str, str]]:
    with INDEX_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _image_size(path: Path) -> tuple[int | None, int | None]:
    if Image is None:
        return None, None
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return None, None


def _tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.replace("，", ",").split(",") if item.strip()]


def _asset_type(row: dict[str, str]) -> str:
    raw = row.get("asset_type") or "image"
    if raw == "qualification_certificate":
        return "qualification_image"
    if raw == "project_photo":
        return "project_image"
    if raw in {"product_photo", "product_or_project_photo", "synthetic_product_spec"}:
        return "product_image"
    return raw


def _applicable_sections(row: dict[str, str], tags: list[str]) -> list[str]:
    category = row.get("category") or ""
    title = row.get("title") or ""
    joined = " ".join([category, title, *tags])
    sections = set()

    if any(keyword in joined for keyword in ["营业执照", "资质", "许可证", "资格审查", "企业资信"]):
        sections.update(["资格审查资料", "企业资信文件", "投标文件格式"])
    if any(keyword in joined for keyword in ["泵", "阀", "水轮机", "叶片", "螺栓", "螺母", "闸门", "启闭机", "控制柜"]):
        sections.update(["技术响应文件", "设备材料响应", "施工组织设计"])
    if any(keyword in joined for keyword in ["水库", "大坝", "灌区", "渠道", "水闸", "泵站"]):
        sections.update(["工程概况", "类似项目业绩", "施工方案"])
    if any(keyword in joined for keyword in ["监测", "雨量", "水位", "视频", "信息化"]):
        sections.update(["信息化建设方案", "自动化监测方案", "技术响应文件"])

    return sorted(sections) or ["企业知识库问答", "标书插图"]


def _specs(row: dict[str, str], tags: list[str]) -> dict[str, Any]:
    title = row.get("title") or ""
    specs: dict[str, Any] = {}
    for token in tags:
        if any(prefix in token for prefix in ["M", "DN", "Φ", "kW", "Francis", "Kaplan", "Pelton"]):
            specs.setdefault("keywords", []).append(token)
    if "M" in title or "DN" in title or "Φ" in title or "kW" in title:
        specs["model"] = title
    return specs


def _safe_storage_path(relative_path: str) -> str:
    path = Path(relative_path)
    safe_stem = unidecode(path.stem).lower()
    safe_stem = "".join(ch if ch.isalnum() else "-" for ch in safe_stem)
    safe_stem = "-".join(part for part in safe_stem.split("-") if part)[:80] or "asset"
    digest = sha1(relative_path.encode("utf-8")).hexdigest()[:10]
    return f"water_asset_images/{path.parent.as_posix()}/{safe_stem}-{digest}{path.suffix.lower()}"


def _searchable_text(row: dict[str, str], tags: list[str], applicable_sections: list[str]) -> str:
    title = row.get("title") or ""
    category = row.get("category") or ""
    description = row.get("description") or ""
    source_type = row.get("source_type") or ""
    license_name = row.get("license") or ""
    source_url = row.get("source_url") or ""
    return "\n".join(
        [
            f"图片名称：{title}",
            f"图片类型：{_asset_type(row)}",
            f"行业分类：{category}",
            f"关键词：{'、'.join(tags)}",
            f"适用章节：{'、'.join(applicable_sections)}",
            f"用途说明：{description}",
            f"来源类型：{source_type}",
            f"许可协议：{license_name}",
            f"来源地址：{source_url}",
            "可用于企业知识库问答、产品库检索、资信库检索、标书章节自动配图和投标附件整理。",
        ]
    )


def _existing_by_local_path(local_path: str) -> dict[str, Any] | None:
    response = (
        get_supabase_client()
        .table("knowledge_assets")
        .select("id,storage_path,public_url")
        .eq("local_path", local_path)
        .limit(1)
        .execute()
    )
    data = response.data or []
    return data[0] if data else None


def _save_asset(row: dict[str, str], embedding: list[float]) -> str:
    client = get_supabase_client()
    relative_path = row["path"]
    local_path = ASSET_ROOT / relative_path
    if not local_path.exists():
        raise FileNotFoundError(local_path)

    tags = _tags(row.get("tags"))
    applicable_sections = _applicable_sections(row, tags)
    searchable_text = _searchable_text(row, tags, applicable_sections)
    width, height = _image_size(local_path)
    mime_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    object_path = _safe_storage_path(relative_path)

    existing = _existing_by_local_path(relative_path)
    if not existing or existing.get("storage_path") != object_path:
        upload_file_to_storage(BUCKET, object_path, local_path, mime_type)

    public_url = client.storage.from_(BUCKET).get_public_url(object_path)
    payload = {
        "title": row.get("title") or local_path.stem,
        "description": row.get("description") or "",
        "category": row.get("category") or "水利行业资料",
        "asset_type": _asset_type(row),
        "file_name": local_path.name,
        "file_ext": local_path.suffix.lower().lstrip("."),
        "mime_type": mime_type,
        "file_size": local_path.stat().st_size,
        "local_path": relative_path,
        "storage_bucket": BUCKET,
        "storage_path": object_path,
        "public_url": public_url,
        "width": width,
        "height": height,
        "source_type": row.get("source_type") or "seed",
        "source_url": row.get("source_url") or None,
        "license": row.get("license") or None,
        "attribution": row.get("artist") or row.get("source_title") or None,
        "is_synthetic": (row.get("source_type") or "").startswith("synthetic"),
        "is_sensitive": row.get("asset_type") == "qualification_certificate",
        "anonymized": True,
        "industry": "水利行业",
        "applicable_sections": applicable_sections,
        "tags": tags,
        "specs": _specs(row, tags),
        "ocr_text": None,
        "ai_caption": row.get("description") or "",
        "searchable_text": searchable_text,
        "embedding": embedding,
        "status": "indexed",
        "metadata": {
            "seed_file": "rag_seed/water_asset_images/index.csv",
            "source_title": row.get("source_title"),
            "created_at_from_index": row.get("created_at"),
        },
    }

    if existing:
        response = (
            client.table("knowledge_assets")
            .update(payload)
            .eq("id", existing["id"])
            .execute()
        )
    else:
        response = client.table("knowledge_assets").insert(payload).execute()

    if not response.data:
        raise RuntimeError(f"knowledge_assets 写入失败: {relative_path}")
    return response.data[0]["id"]


def main() -> None:
    rows = _read_index()
    ali_client = init_ali_client()

    texts = []
    prepared_rows = []
    for row in rows:
        local_path = ASSET_ROOT / row["path"]
        if not local_path.exists():
            print(f"[SKIP] missing file: {row['path']}")
            continue
        tags = _tags(row.get("tags"))
        texts.append(_searchable_text(row, tags, _applicable_sections(row, tags)))
        prepared_rows.append(row)

    embeddings = get_embeddings(ali_client, texts)
    if len(embeddings) != len(prepared_rows):
        raise RuntimeError(f"embedding 数量不匹配: {len(embeddings)} / {len(prepared_rows)}")

    saved_ids = []
    for row, embedding in zip(prepared_rows, embeddings):
        saved_id = _save_asset(row, embedding)
        saved_ids.append(saved_id)
        print(f"[OK] {row.get('title')} -> {saved_id}")

    report = {
        "total": len(saved_ids),
        "bucket": BUCKET,
        "table": "knowledge_assets",
    }
    (ASSET_ROOT / "ingestion_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Done. indexed_assets={len(saved_ids)}")


if __name__ == "__main__":
    main()

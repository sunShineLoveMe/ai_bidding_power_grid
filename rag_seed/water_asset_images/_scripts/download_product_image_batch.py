#!/usr/bin/env python3
"""Download a larger public product image batch for water bidding demos.

The downloader uses Wikimedia Commons API and stores thumbnails with metadata.
It is intended for product-library / auto-illustration testing, not for final
commercial collateral without license review.
"""

from __future__ import annotations

import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "01_products"
USER_AGENT = "AI-Bidding-RAG-Seed/0.1 (product image collection; local demo)"

SEARCH_TOPICS = [
    {
        "query": "Francis turbine",
        "category": "水轮机与水电设备",
        "tags": ["水轮机", "Francis turbine", "转轮", "水电站"],
    },
    {
        "query": "Kaplan turbine",
        "category": "水轮机与水电设备",
        "tags": ["水轮机", "Kaplan turbine", "叶片", "水电站"],
    },
    {
        "query": "Pelton turbine",
        "category": "水轮机与水电设备",
        "tags": ["水轮机", "Pelton turbine", "转轮", "喷嘴"],
    },
    {
        "query": "turbine blade",
        "category": "水轮机与水电设备",
        "tags": ["叶片", "转轮叶片", "水轮机", "规格参数"],
    },
    {
        "query": "hydroelectric turbine",
        "category": "水轮机与水电设备",
        "tags": ["水电设备", "水轮发电机组", "水轮机"],
    },
    {
        "query": "hex nut",
        "category": "紧固件与标准件",
        "tags": ["螺母", "六角螺母", "标准件", "规格参数"],
    },
    {
        "query": "lock nut",
        "category": "紧固件与标准件",
        "tags": ["锁紧螺母", "螺母", "标准件"],
    },
    {
        "query": "anchor bolt",
        "category": "紧固件与标准件",
        "tags": ["地脚螺栓", "锚栓", "标准件", "水工结构"],
    },
    {
        "query": "stainless steel bolt",
        "category": "紧固件与标准件",
        "tags": ["螺栓", "不锈钢", "紧固件", "规格参数"],
    },
    {
        "query": "sluice gate",
        "category": "金属结构与闸门",
        "tags": ["水闸", "闸门", "金属结构", "启闭机"],
    },
    {
        "query": "radial gate dam",
        "category": "金属结构与闸门",
        "tags": ["弧形闸门", "大坝", "金属结构"],
    },
    {
        "query": "gate valve",
        "category": "阀门与管件",
        "tags": ["闸阀", "阀门", "管件", "规格参数"],
    },
    {
        "query": "butterfly valve",
        "category": "阀门与管件",
        "tags": ["蝶阀", "阀门", "管件", "水利设备"],
    },
    {
        "query": "centrifugal pump",
        "category": "泵站设备",
        "tags": ["离心泵", "泵站", "水泵", "机电设备"],
    },
    {
        "query": "water pump station",
        "category": "泵站设备",
        "tags": ["泵站", "水泵", "机电设备", "运行管理"],
    },
    {
        "query": "rain gauge",
        "category": "水利信息化产品",
        "tags": ["雨量计", "雨水情监测", "监测终端"],
    },
    {
        "query": "water level gauge",
        "category": "水利信息化产品",
        "tags": ["水位尺", "水位监测", "水情监测"],
    },
    {
        "query": "ultrasonic water level sensor",
        "category": "水利信息化产品",
        "tags": ["水位传感器", "超声波", "自动化监测"],
    },
    {
        "query": "electrical control cabinet",
        "category": "电气与自动化",
        "tags": ["控制柜", "电气控制", "自动化", "泵站"],
    },
    {
        "query": "concrete test cylinder",
        "category": "检测与试验设备",
        "tags": ["混凝土试验", "检测", "试验设备"],
    },
]


def safe_name(text: str, max_len: int = 72) -> str:
    text = re.sub(r"^File:", "", text, flags=re.I)
    text = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text, flags=re.UNICODE).strip("_")
    return text[:max_len] or "image"


def commons_search(topic: dict, limit: int = 8) -> list[dict]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": topic["query"],
        "gsrnamespace": 6,
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": "1200",
        "format": "json",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urlencode(params)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    payload = json.loads(urlopen(req, timeout=30).read().decode("utf-8"))
    pages = payload.get("query", {}).get("pages", {}) or {}
    results = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime") or ""
        if not mime.startswith("image/"):
            continue
        image_url = info.get("thumburl") or info.get("url")
        if not image_url:
            continue
        ext = ".jpg"
        if "png" in mime:
            ext = ".png"
        elif "webp" in mime:
            ext = ".webp"
        results.append({
            "title": re.sub(r"^File:", "", page.get("title", "")),
            "image_url": image_url,
            "source_url": info.get("descriptionurl") or info.get("url"),
            "mime": mime,
            "extension": ext,
            "license": (info.get("extmetadata") or {}).get("LicenseShortName", {}).get("value", ""),
            "artist": re.sub(r"<[^>]+>", "", (info.get("extmetadata") or {}).get("Artist", {}).get("value", "")),
            "topic": topic,
        })
    return results


def download(url: str, path: Path) -> None:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=45) as resp:
        path.write_bytes(resp.read())


def load_existing_index() -> list[dict]:
    index_path = ROOT / "index.csv"
    if not index_path.exists():
        return []
    with index_path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_index(rows: list[dict]) -> None:
    fields = [
        "path",
        "title",
        "asset_type",
        "category",
        "tags",
        "description",
        "source_type",
        "source_title",
        "source_url",
        "license",
        "artist",
        "created_at",
    ]
    with (ROOT / "index.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    with (ROOT / "index.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def update_readme(total: int) -> None:
    readme = ROOT / "README.md"
    extra = f"""

## 产品图片扩展批次

已扩展产品/工程图片范围，覆盖水轮机、叶片、螺母、螺栓、闸门、阀门、泵站、雨水情监测、控制柜、检测设备等方向。

- 当前索引图片资产：{total} 张
- 目标用途：产品库检索、图片资产库、标书自动插图、图文 RAG 测试
- 主要来源：Wikimedia Commons API 公开图片路径
- 注意：正式商用或开源演示前需复核每张图片的 license 与署名要求。
"""
    text = readme.read_text(encoding="utf-8") if readme.exists() else "# 水利行业图片资产种子库\n"
    marker = "## 产品图片扩展批次"
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n" + extra
    else:
        text = text.rstrip() + "\n" + extra
    readme.write_text(text, encoding="utf-8")


def main() -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_existing_index()
    seen_urls = {row.get("source_url") for row in existing if row.get("source_url")}
    seen_paths = {row.get("path") for row in existing if row.get("path")}
    rows = existing[:]
    now = datetime.now(timezone.utc).isoformat()

    for topic in SEARCH_TOPICS:
        if len(rows) >= 50:
            break
        print(f"[SEARCH] {topic['query']}")
        try:
            candidates = commons_search(topic, limit=8)
        except Exception as exc:
            print(f"  [FAIL search] {exc}")
            continue
        time.sleep(0.6)

        for candidate in candidates:
            if len(rows) >= 50:
                break
            if candidate["source_url"] in seen_urls:
                continue
            file_stem = safe_name(candidate["title"])
            filename = f"{len(rows)+1:02d}_{file_stem}{candidate['extension']}"
            path = TARGET_DIR / filename
            rel_path = str(path.relative_to(ROOT))
            if rel_path in seen_paths:
                continue
            try:
                download(candidate["image_url"], path)
                time.sleep(0.5)
            except Exception as exc:
                print(f"  [FAIL download] {candidate['title']}: {exc}")
                continue

            row = {
                "path": rel_path,
                "title": candidate["title"],
                "asset_type": "product_photo",
                "category": topic["category"],
                "tags": ",".join(topic["tags"]),
                "description": f"公开产品/工程示意图片，可用于{topic['category']}方向的产品库检索和标书插图测试。",
                "source_type": "public_download",
                "source_title": f"Wikimedia Commons - {candidate['title']}",
                "source_url": candidate["source_url"],
                "license": candidate["license"],
                "artist": candidate["artist"][:160],
                "created_at": now,
            }
            rows.append(row)
            seen_urls.add(candidate["source_url"])
            seen_paths.add(rel_path)
            print(f"  [OK] {row['title']} -> {rel_path}")

    write_index(rows)
    update_readme(len(rows))
    print(f"Done. indexed assets={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

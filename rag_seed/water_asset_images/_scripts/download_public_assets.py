#!/usr/bin/env python3
"""Build a public/de-identified image asset seed set for water bidding demos.

Product and project images are downloaded from public Wikimedia Commons file
paths. Credential images are synthetic placeholders to avoid collecting real
business-license or certificate scans that may contain sensitive information.
"""

from __future__ import annotations

import csv
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "Mozilla/5.0"

PUBLIC_IMAGE_ASSETS = [
    {
        "file_name": "水闸闸门_公开示意.jpg",
        "title": "水闸闸门",
        "asset_type": "product_or_project_photo",
        "category": "泵站水闸工程",
        "tags": ["水闸", "闸门", "金属结构", "启闭设施"],
        "source_title": "Wikimedia Commons - Sluice gate",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Sluice_gate.jpg",
        "description": "用于模拟水闸、闸门、金属结构安装等标书章节插图。",
    },
    {
        "file_name": "灌溉渠道_公开示意.jpg",
        "title": "灌溉渠道",
        "asset_type": "product_or_project_photo",
        "category": "灌区与渠道工程",
        "tags": ["灌区", "渠道", "节水改造", "渠道衬砌"],
        "source_title": "Wikimedia Commons - Irrigation canal",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Irrigation_canal.jpg",
        "description": "用于模拟灌区续建配套、渠道工程、节水改造等章节插图。",
    },
    {
        "file_name": "泵站_公开示意.jpg",
        "title": "泵站",
        "asset_type": "product_or_project_photo",
        "category": "泵站水闸工程",
        "tags": ["泵站", "机电设备", "水利设施", "运行管理"],
        "source_title": "Wikimedia Commons - Water Pumping Station",
        "source_url": "https://upload.wikimedia.org/wikipedia/commons/f/f6/Anglian_Water_Pumping_Station_-_geograph.org.uk_-_3172567.jpg",
        "description": "用于模拟泵站土建、机电设备安装、运行维护等章节插图。",
    },
    {
        "file_name": "雨量计_公开示意.jpg",
        "title": "雨量计",
        "asset_type": "product_photo",
        "category": "水利信息化产品",
        "tags": ["雨水情监测", "雨量计", "监测终端", "信息化"],
        "source_title": "Wikimedia Commons - Rain gauge",
        "source_url": "https://upload.wikimedia.org/wikipedia/commons/c/ca/250mm_Rain_Gauge.jpg",
        "description": "用于模拟雨水情监测、信息化平台、自动化监测设备章节插图。",
    },
    {
        "file_name": "水位尺_公开示意.jpg",
        "title": "水位尺",
        "asset_type": "product_photo",
        "category": "水利信息化产品",
        "tags": ["水位监测", "水位尺", "河道监测", "水库监测"],
        "source_title": "Wikimedia Commons - Water level gauge",
        "source_url": "https://upload.wikimedia.org/wikipedia/commons/8/8e/Water_level_gauge_board_-_geograph.org.uk_-_1050628.jpg",
        "description": "用于模拟水位监测、水库运行管理、河道水情监测等章节插图。",
    },
    {
        "file_name": "超声波水位传感器_公开示意.jpg",
        "title": "超声波水位传感器",
        "asset_type": "product_photo",
        "category": "水利信息化产品",
        "tags": ["水位传感器", "超声波", "自动化监测", "信息化"],
        "source_title": "Wikimedia Commons - Ultrasonic water level sensor",
        "source_url": "https://upload.wikimedia.org/wikipedia/commons/4/47/Ultrasonic_water_level_sensor_at_levee_in_Kashima%2C_Saga.jpg",
        "description": "用于模拟自动化水位监测设备、信息化改造和水情采集章节插图。",
    },
    {
        "file_name": "大坝工程_公开示意.jpg",
        "title": "大坝工程",
        "asset_type": "project_photo",
        "category": "水库除险加固",
        "tags": ["水库", "大坝", "除险加固", "水工建筑物"],
        "source_title": "Wikimedia Commons - Dam",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Dam.jpg",
        "description": "用于模拟水库大坝、除险加固、溢洪道及水工建筑物章节插图。",
    },
]

SYNTHETIC_CERTIFICATES = [
    {
        "file_name": "营业执照_脱敏样张.png",
        "title": "营业执照脱敏样张",
        "asset_type": "qualification_certificate",
        "category": "企业资信",
        "tags": ["营业执照", "基础证照", "资格审查"],
        "description": "脱敏合成样张，用于测试资信库图片上传、OCR 和自动插图，不代表真实证照。",
        "lines": [
            "营业执照（脱敏样张）",
            "统一社会信用代码：91XXXXXXXXXXXXXX",
            "名称：某水利工程建设企业",
            "类型：有限责任公司",
            "法定代表人：【待替换】",
            "注册资本：【待替换】万元",
            "成立日期：【待替换】",
            "住所：【待替换：注册地址】",
            "经营范围：水利水电工程施工、泵站水闸工程、河道治理、灌区改造等",
            "说明：本图片为系统测试用脱敏合成样张。",
        ],
    },
    {
        "file_name": "水利施工资质证书_脱敏样张.png",
        "title": "水利施工资质证书脱敏样张",
        "asset_type": "qualification_certificate",
        "category": "企业资信",
        "tags": ["资质证书", "水利水电工程施工总承包", "资格审查"],
        "description": "脱敏合成样张，用于测试资质证书 OCR 和投标资料自动插图。",
        "lines": [
            "建筑业企业资质证书（脱敏样张）",
            "企业名称：某水利工程建设企业",
            "资质类别及等级：水利水电工程施工总承包【待替换】级",
            "证书编号：【待替换】",
            "有效期至：【待替换】",
            "发证机关：【待替换】",
            "适用场景：资格审查、企业资质证明、投标文件附件。",
            "说明：本图片为系统测试用脱敏合成样张。",
        ],
    },
    {
        "file_name": "安全生产许可证_脱敏样张.png",
        "title": "安全生产许可证脱敏样张",
        "asset_type": "qualification_certificate",
        "category": "企业资信",
        "tags": ["安全生产许可证", "施工安全", "资格审查"],
        "description": "脱敏合成样张，用于测试安全生产许可证 OCR 和投标附件插图。",
        "lines": [
            "安全生产许可证（脱敏样张）",
            "单位名称：某水利工程建设企业",
            "许可范围：建筑施工",
            "证书编号：【待替换】",
            "有效期：【待替换】至【待替换】",
            "发证机关：【待替换】",
            "适用场景：资格审查、安全生产能力证明。",
            "说明：本图片为系统测试用脱敏合成样张。",
        ],
    },
]


def ensure_dirs() -> None:
    for folder in ["01_products", "02_qualification_images", "03_project_cases", "04_pdf_collections"]:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)


def download_public_image(asset: dict) -> dict:
    target_dir = ROOT / ("03_project_cases" if asset["asset_type"] == "project_photo" else "01_products")
    target = target_dir / asset["file_name"]
    req = Request(asset["source_url"], headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=40) as resp:
        target.write_bytes(resp.read())
    return {**asset, "path": str(target.relative_to(ROOT)), "source_type": "public_download"}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for item in candidates:
        try:
            return ImageFont.truetype(item, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def create_certificate(asset: dict) -> dict:
    target = ROOT / "02_qualification_images" / asset["file_name"]
    image = Image.new("RGB", (1400, 980), "#fffdf7")
    draw = ImageDraw.Draw(image)
    border = "#b91c1c"
    draw.rectangle((38, 38, 1362, 942), outline=border, width=6)
    draw.rectangle((70, 70, 1330, 910), outline="#f2c2a2", width=2)

    title_font = font(48)
    body_font = font(28)
    small_font = font(22)
    y = 125
    for index, line in enumerate(asset["lines"]):
        current_font = title_font if index == 0 else body_font
        fill = "#7f1d1d" if index == 0 else "#1f2937"
        wrapped = textwrap.wrap(line, width=36)
        for item in wrapped:
            draw.text((135, y), item, font=current_font, fill=fill)
            y += 68 if index == 0 else 48
        if index == 0:
            y += 24
            draw.line((135, y, 1265, y), fill="#e5b08d", width=3)
            y += 45

    draw.ellipse((1080, 665, 1270, 855), outline="#ef4444", width=8)
    draw.text((1118, 735), "脱敏\n样张", font=small_font, fill="#ef4444", align="center")
    draw.text((135, 870), "仅用于 AI 标书系统图片资产库测试，不具备法律效力。", font=small_font, fill="#9ca3af")
    image.save(target)
    return {**asset, "path": str(target.relative_to(ROOT)), "source_type": "synthetic_deidentified"}


def create_pdf_collection(rows: list[dict]) -> None:
    pdf_path = ROOT / "04_pdf_collections" / "水利产品与资信图片集合_脱敏测试版.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    page_width, page_height = A4
    c.setTitle("水利产品与资信图片集合_脱敏测试版")
    for row in rows:
        path = ROOT / row["path"]
        if not path.exists():
            continue
        c.setFont("Helvetica-Bold", 16)
        c.drawString(2 * cm, page_height - 2 * cm, row["title"])
        c.setFont("Helvetica", 9)
        c.drawString(2 * cm, page_height - 2.55 * cm, f"Category: {row['category']} | Type: {row['asset_type']}")
        c.drawString(2 * cm, page_height - 3.0 * cm, f"Source: {row.get('source_title') or row.get('source_type')}")
        try:
            with Image.open(path) as img:
                width, height = img.size
            max_w = page_width - 4 * cm
            max_h = page_height - 6 * cm
            scale = min(max_w / width, max_h / height)
            draw_w, draw_h = width * scale, height * scale
            x = (page_width - draw_w) / 2
            y = 2 * cm
            c.drawImage(str(path), x, y, width=draw_w, height=draw_h, preserveAspectRatio=True, anchor="c")
        except Exception:
            c.drawString(2 * cm, page_height - 4 * cm, "Image preview failed.")
        c.showPage()
    c.save()


def write_index(rows: list[dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
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
        "created_at",
    ]
    with (ROOT / "index.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "path": row.get("path", ""),
                "title": row.get("title", ""),
                "asset_type": row.get("asset_type", ""),
                "category": row.get("category", ""),
                "tags": ",".join(row.get("tags", [])),
                "description": row.get("description", ""),
                "source_type": row.get("source_type", ""),
                "source_title": row.get("source_title", ""),
                "source_url": row.get("source_url", ""),
                "created_at": now,
            })
    with (ROOT / "index.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            row = {**row, "created_at": now}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_readme(rows: list[dict]) -> None:
    readme = ROOT / "README.md"
    lines = [
        "# 水利行业图片资产种子库",
        "",
        "本目录用于测试后续“图片资产库 / 自动插图”能力。产品和工程示意图片来自公开网页路径；营业执照、资质证书、安全生产许可证为脱敏合成样张，不包含真实企业信息。",
        "",
        "## 目录",
        "",
        "- `01_products/`：水闸、渠道、泵站、雨量计等公开产品/工程示意图片。",
        "- `02_qualification_images/`：脱敏合成的营业执照、资质证书、安全生产许可证样张。",
        "- `03_project_cases/`：水库大坝等工程案例示意图片。",
        "- `04_pdf_collections/`：图片集合 PDF，用于测试 PDF 图片集合解析。",
        "- `index.csv` / `index.jsonl`：图片资产元数据。",
        "",
        "## 当前数量",
        "",
        f"- 图片资产：{len(rows)} 张",
        "- PDF 图片集合：1 份",
        "",
        "## 使用边界",
        "",
        "- 不使用真实企业证照扫描件作为测试数据。",
        "- 公开图片需在正式商用或开源演示前复核授权协议和署名要求。",
        "- 该目录适合测试 OCR、图片说明向量化、图片资产检索、Word 自动插图。",
        "",
        "## 建议图片 metadata",
        "",
        "```json",
        json.dumps({
            "asset_type": "qualification_certificate",
            "title": "营业执照",
            "category": "企业资信",
            "tags": ["营业执照", "资格审查"],
            "applicable_sections": ["企业基本情况表", "资格审查资料"],
            "description": "用于证明企业合法经营主体资格",
            "ocr_text": "OCR 识别文本",
            "source": "企业上传或公开授权素材"
        }, ensure_ascii=False, indent=2),
        "```",
    ]
    readme.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ensure_dirs()
    rows = []
    for asset in PUBLIC_IMAGE_ASSETS:
        try:
            rows.append(download_public_image(asset))
            print(f"[OK] downloaded {asset['title']}")
        except Exception as exc:
            print(f"[FAIL] {asset['title']}: {exc}")
    for asset in SYNTHETIC_CERTIFICATES:
        rows.append(create_certificate(asset))
        print(f"[OK] generated {asset['title']}")
    create_pdf_collection(rows)
    write_index(rows)
    write_readme(rows)
    print(f"Done. {len(rows)} image assets under {ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

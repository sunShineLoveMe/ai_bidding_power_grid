#!/usr/bin/env python3
"""Generate synthetic de-identified product/specification cards.

These cards fill product-library gaps for bidding workflow tests. They are not
real product datasheets and do not represent a specific manufacturer.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "01_products"


PRODUCTS = [
    ("六角螺母 M12", "紧固件与标准件", ["螺母", "M12", "标准件", "规格参数"], "材质：304不锈钢；强度等级：A2-70；适用：水工金属结构连接"),
    ("六角螺母 M16", "紧固件与标准件", ["螺母", "M16", "标准件", "规格参数"], "材质：45#钢镀锌；强度等级：8级；适用：闸门埋件连接"),
    ("六角螺母 M20", "紧固件与标准件", ["螺母", "M20", "标准件", "规格参数"], "材质：不锈钢；执行标准：GB/T 6170；适用：泵站设备基础"),
    ("锁紧螺母 M24", "紧固件与标准件", ["锁紧螺母", "M24", "防松", "规格参数"], "结构：尼龙锁紧；表面：热镀锌；适用：振动设备连接"),
    ("地脚螺栓 M24x600", "紧固件与标准件", ["地脚螺栓", "M24", "基础连接"], "规格：M24x600；材质：Q235B；适用：水泵机组基础固定"),
    ("地脚螺栓 M30x800", "紧固件与标准件", ["地脚螺栓", "M30", "基础连接"], "规格：M30x800；材质：Q355B；适用：启闭机基础固定"),
    ("不锈钢螺栓 M16x80", "紧固件与标准件", ["螺栓", "M16", "不锈钢"], "规格：M16x80；材质：304；适用：潮湿环境金属结构连接"),
    ("高强螺栓 M20x100", "紧固件与标准件", ["高强螺栓", "M20", "强度等级"], "规格：M20x100；强度等级：10.9级；适用：钢结构连接"),
    ("平垫圈 Φ16", "紧固件与标准件", ["垫圈", "Φ16", "标准件"], "材质：304不锈钢；用途：分散连接压力、防松保护"),
    ("弹簧垫圈 Φ20", "紧固件与标准件", ["弹簧垫圈", "Φ20", "防松"], "材质：65Mn；表面：镀锌；用途：防松连接"),
    ("Francis 水轮机转轮", "水轮机与水电设备", ["Francis", "水轮机", "转轮"], "额定水头：20-120m；适用：中高水头水电站；参数为测试样例"),
    ("Kaplan 水轮机叶片", "水轮机与水电设备", ["Kaplan", "叶片", "可调桨"], "叶片形式：可调桨；适用：低水头大流量工况；参数为测试样例"),
    ("Pelton 冲击式转轮", "水轮机与水电设备", ["Pelton", "水斗", "冲击式"], "适用：高水头小流量；结构：双水斗；参数为测试样例"),
    ("水轮机导叶组件", "水轮机与水电设备", ["导叶", "调速", "水轮机"], "材质：不锈钢铸件；功能：调节流量与水流方向"),
    ("水轮机主轴", "水轮机与水电设备", ["主轴", "水轮机", "机电设备"], "材质：合金钢锻件；检测：超声波探伤；参数为测试样例"),
    ("转轮叶片修复件", "水轮机与水电设备", ["叶片", "修复", "水电站检修"], "工艺：堆焊修复、打磨、动平衡复核；适用：检修工程"),
    ("闸门止水橡皮 P型", "金属结构与闸门", ["止水", "闸门", "橡胶"], "形式：P型止水；材质：三元乙丙；适用：平面闸门止水"),
    ("平面钢闸门埋件", "金属结构与闸门", ["闸门", "埋件", "金属结构"], "材质：Q355B；防腐：喷砂除锈+环氧涂层；参数为测试样例"),
    ("弧形闸门支铰", "金属结构与闸门", ["弧形闸门", "支铰", "金属结构"], "结构：铸钢支铰；检测：尺寸复核、无损检测"),
    ("卷扬式启闭机", "金属结构与闸门", ["启闭机", "卷扬式", "闸门"], "启闭力：2x160kN；控制方式：本地/远程；参数为测试样例"),
    ("螺杆式启闭机", "金属结构与闸门", ["启闭机", "螺杆式", "闸门"], "启闭力：100kN；适用：小型水闸和涵闸"),
    ("DN300 闸阀", "阀门与管件", ["闸阀", "DN300", "管件"], "公称通径：DN300；压力等级：PN1.0；适用：输水管线"),
    ("DN600 蝶阀", "阀门与管件", ["蝶阀", "DN600", "管件"], "公称通径：DN600；驱动：电动；适用：泵站出水管"),
    ("伸缩节 DN500", "阀门与管件", ["伸缩节", "DN500", "管件"], "材质：球墨铸铁；密封：橡胶圈；适用：管道补偿"),
    ("离心泵机组 Q=500m3h", "泵站设备", ["离心泵", "泵站", "流量参数"], "流量：500m3/h；扬程：28m；电机功率：75kW；参数为测试样例"),
    ("潜水轴流泵 22kW", "泵站设备", ["轴流泵", "潜水泵", "泵站"], "功率：22kW；适用：排涝泵站；参数为测试样例"),
    ("泵站电机 75kW", "泵站设备", ["电机", "泵站", "机电设备"], "功率：75kW；防护等级：IP55；绝缘等级：F级"),
    ("雨量监测终端", "水利信息化产品", ["雨量计", "RTU", "雨水情监测"], "采集：翻斗雨量；通信：4G/NB-IoT；供电：太阳能"),
    ("雷达水位计", "水利信息化产品", ["雷达水位计", "水位监测", "信息化"], "量程：0-20m；精度：±3mm；通信：RS485/4G"),
    ("视频监控球机", "水利信息化产品", ["视频监控", "球机", "水库监控"], "像素：400万；功能：云台、夜视、防水；适用：水库大坝"),
    ("泵站自动化控制柜", "电气与自动化", ["控制柜", "PLC", "泵站自动化"], "控制：PLC；接口：远程启停、状态采集、报警联动"),
    ("混凝土试块模具", "检测与试验设备", ["试验检测", "混凝土", "模具"], "规格：150x150x150mm；用途：混凝土强度试件制作"),
]


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Light.ttc"]:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_nut(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str) -> None:
    points = []
    for i in range(6):
        angle = math.pi / 6 + i * math.pi / 3
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=color, outline="#1e3a8a")
    draw.ellipse((cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42), fill="#f8fafc", outline="#1e3a8a", width=4)


def draw_blade(draw: ImageDraw.ImageDraw, cx: int, cy: int, color: str) -> None:
    draw.ellipse((cx - 42, cy - 42, cx + 42, cy + 42), fill="#dbeafe", outline="#1d4ed8", width=4)
    for i in range(5):
        angle = i * 2 * math.pi / 5
        x1 = cx + 28 * math.cos(angle)
        y1 = cy + 28 * math.sin(angle)
        x2 = cx + 185 * math.cos(angle + 0.22)
        y2 = cy + 112 * math.sin(angle + 0.22)
        draw.line((x1, y1, x2, y2), fill=color, width=26)
        draw.ellipse((x2 - 16, y2 - 16, x2 + 16, y2 + 16), fill=color)


def draw_device(draw: ImageDraw.ImageDraw, cx: int, cy: int, color: str) -> None:
    draw.rounded_rectangle((cx - 170, cy - 120, cx + 170, cy + 120), radius=24, fill="#eff6ff", outline=color, width=5)
    draw.rectangle((cx - 120, cy - 65, cx + 120, cy - 25), fill=color)
    draw.rectangle((cx - 120, cy + 5, cx + 80, cy + 35), fill="#bfdbfe")
    draw.ellipse((cx + 95, cy + 0, cx + 145, cy + 50), fill="#22c55e")
    draw.line((cx - 120, cy + 75, cx + 120, cy + 75), fill=color, width=8)


def create_card(index: int, product: tuple[str, str, list[str], str]) -> dict:
    title, category, tags, spec = product
    image = Image.new("RGB", (1200, 820), "#f8fbff")
    draw = ImageDraw.Draw(image)
    title_font = load_font(44)
    sub_font = load_font(26)
    body_font = load_font(24)
    small_font = load_font(20)

    draw.rounded_rectangle((34, 34, 1166, 786), radius=28, fill="#ffffff", outline="#dbeafe", width=4)
    draw.rectangle((34, 34, 1166, 145), fill="#2563eb")
    draw.text((76, 68), title, font=title_font, fill="#ffffff")
    draw.text((78, 164), category, font=sub_font, fill="#2563eb")

    color = "#2563eb"
    if "螺" in title or "垫圈" in title:
        draw_nut(draw, 320, 405, 135, color)
    elif "水轮机" in title or "叶片" in title or "转轮" in title or "导叶" in title:
        draw_blade(draw, 320, 415, color)
    else:
        draw_device(draw, 320, 410, color)

    draw.rounded_rectangle((590, 220, 1080, 620), radius=18, fill="#f1f5f9", outline="#cbd5e1")
    draw.text((625, 250), "规格参数（模拟）", font=sub_font, fill="#0f172a")
    y = 305
    for line in spec.split("；"):
        draw.text((625, y), f"· {line}", font=body_font, fill="#334155")
        y += 46

    tag_text = " / ".join(tags[:4])
    draw.rounded_rectangle((76, 675, 1080, 735), radius=18, fill="#eff6ff", outline="#bfdbfe")
    draw.text((105, 693), f"标签：{tag_text}", font=small_font, fill="#1d4ed8")
    draw.text((76, 755), "脱敏合成规格图，仅用于 AI 标书系统产品库、图片资产检索和自动插图测试。", font=small_font, fill="#94a3b8")

    filename = f"{index:02d}_{title.replace('/', '_')}_脱敏规格图.png"
    target = TARGET_DIR / filename
    image.save(target)
    return {
        "path": str(target.relative_to(ROOT)),
        "title": title,
        "asset_type": "synthetic_product_spec",
        "category": category,
        "tags": ",".join(tags),
        "description": spec,
        "source_type": "synthetic_deidentified",
        "source_title": "AI标书系统脱敏合成产品规格图",
        "source_url": "",
        "license": "synthetic-demo",
        "artist": "AI标书系统",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def load_rows() -> list[dict]:
    index = ROOT / "index.csv"
    if not index.exists():
        return []
    with index.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_rows(rows: list[dict]) -> None:
    fields = [
        "path", "title", "asset_type", "category", "tags", "description",
        "source_type", "source_title", "source_url", "license", "artist", "created_at",
    ]
    with (ROOT / "index.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    with (ROOT / "index.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def create_pdf(rows: list[dict]) -> None:
    pdf_path = ROOT / "04_pdf_collections" / "水利产品规格图片集合_50张测试版.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    for row in rows:
        path = ROOT / row["path"]
        if not path.exists():
            continue
        c.setFont("Helvetica-Bold", 15)
        c.drawString(1.6 * cm, height - 1.8 * cm, row["title"][:80])
        c.setFont("Helvetica", 8)
        c.drawString(1.6 * cm, height - 2.25 * cm, f"{row['category']} | {row['asset_type']}")
        with Image.open(path) as img:
            iw, ih = img.size
        max_w = width - 3.2 * cm
        max_h = height - 4.4 * cm
        scale = min(max_w / iw, max_h / ih)
        c.drawImage(str(path), (width - iw * scale) / 2, 1.2 * cm, width=iw * scale, height=ih * scale, preserveAspectRatio=True)
        c.showPage()
    c.save()


def main() -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    existing_titles = {row.get("title") for row in rows}
    next_index = len(rows) + 1
    for product in PRODUCTS:
        if len(rows) >= 50:
            break
        if product[0] in existing_titles:
            continue
        row = create_card(next_index, product)
        rows.append(row)
        existing_titles.add(product[0])
        print(f"[OK] {row['title']} -> {row['path']}")
        next_index += 1
    write_rows(rows)
    create_pdf(rows)
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.exists() else "# 水利行业图片资产种子库\n"
    marker = "## 50 张产品图片集合"
    section = f"""

## 50 张产品图片集合

当前已整理图片资产 `{len(rows)}` 张，包含公开图片和脱敏合成规格图。覆盖方向：

- 水轮机、转轮、叶片、导叶、主轴
- 螺母、螺栓、地脚螺栓、垫圈等标准件
- 闸门、止水、启闭机等金属结构
- 闸阀、蝶阀、伸缩节等管件
- 泵站机组、电机、控制柜
- 雨量计、水位计、视频监控等信息化产品
- 混凝土试验检测设备

集合 PDF：

- `04_pdf_collections/水利产品规格图片集合_50张测试版.pdf`
"""
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n" + section
    else:
        text = text.rstrip() + "\n" + section
    readme.write_text(text, encoding="utf-8")
    print(f"Done. assets={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

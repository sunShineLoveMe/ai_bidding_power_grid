from pathlib import Path
import logging
import markdown
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
import re
import subprocess
import tempfile
import os
import docx.oxml.shared
from docx.oxml import OxmlElement
import shutil
import uuid
import requests
import ipaddress
import socket
from datetime import datetime
from urllib.parse import parse_qs, urlparse, unquote
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET
from backend.services.formal_asset_naming import clean_formal_asset_title, formalize_legacy_image_caption

try:
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None

MARKDOWN_IMAGE_CONNECT_TIMEOUT = 4
MARKDOWN_IMAGE_READ_TIMEOUT = 8
MARKDOWN_IMAGE_MAX_BYTES = 8 * 1024 * 1024
MARKDOWN_IMAGE_MAX_COUNT = int(os.getenv("DOCX_MAX_IMAGES", "24"))
DOCX_IMAGE_MAX_EDGE_PX = int(os.getenv("DOCX_IMAGE_MAX_EDGE_PX", "2400"))
DOCX_IMAGE_MAX_BYTES = int(os.getenv("DOCX_IMAGE_MAX_BYTES", str(2 * 1024 * 1024)))
DOCX_IMAGE_JPEG_QUALITY = int(os.getenv("DOCX_IMAGE_JPEG_QUALITY", "90"))
DOCX_ALLOW_REMOTE_IMAGES = os.getenv("DOCX_ALLOW_REMOTE_IMAGES", "false").lower() in {"1", "true", "yes", "on"}
FORMAL_TEXT_SYMBOL_RE = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001faff"
    "\u2600-\u26ff"
    "\u2700-\u27bf"
    "]"
)
FORMAL_TEXT_CONTROL_RE = re.compile(r"[\u200b\u200c\u200d\ufe0e\ufe0f]")
FORMAL_BID_GENERATION_NOTE_RE = re.compile(
    r"[（(]\s*本章(?:节)?正文[^）)]{0,120}?(?:目标字数|结构完整|可用于|直接插入|共计约)[^）)]{0,240}?[）)]",
    re.S,
)
FORMAL_VOLUME_HEADING_RE = re.compile(
    r"^(?:第[一二三四五六七八九十]+[册卷篇部分][：:、.\s]*)?"
    r"(?:技术|商务|资格|报价|附件|投标|响应|投标资格|资格审查)"
    r".{0,16}(?:文件|分册|响应|资料|清单)$"
)
FORMAL_FORM_HEADING_PATTERNS = {
    "bid_letter": re.compile(r"投标函(?:及投标函附录)?"),
    "authorization": re.compile(r"法定代表人身份证明|授权委托书|法定代表人授权"),
    "business_deviation": re.compile(r"商务.{0,12}(?:偏差|偏离)表"),
    "technical_deviation": re.compile(r"技术.{0,12}(?:偏差|偏离)表"),
    "commitment": re.compile(r"承诺(?:书|函)"),
}
FORMAL_SIGNATURE_LINE_RE = re.compile(
    r"^(?:投标人(?:名称)?|法定代表人|授权代表|委托代理人|代理人|"
    r"单位名称|统一社会信用代码|通讯地址|联系电话|传真|身份证号码|"
    r"日期|投标日期|授权日期|签署日期)\s*[（(]?(?:盖章|签字|签名|签字或盖章|盖单位章)?[）)]?\s*[：:]"
)
DOCX_TOC_MAX_LEVEL = int(os.getenv("DOCX_TOC_MAX_LEVEL", "2"))
DOCX_TEMPLATE_ID = os.getenv("DOCX_TEMPLATE_ID", "formal_bid_standard")
DOCX_BIDDER_FULL_NAME = os.getenv("DOCX_BIDDER_FULL_NAME", "河北泰昌电力器材科技有限公司")
DOCX_BODY_EAST_ASIA = os.getenv("DOCX_BODY_EAST_ASIA", os.getenv("DOCX_CJK_BODY_FONT", "FangSong_GB2312"))
DOCX_HEADING_EAST_ASIA = os.getenv("DOCX_HEADING_EAST_ASIA", os.getenv("DOCX_CJK_HEADING_FONT", "SimHei"))
DOCX_LEVEL3_EAST_ASIA = os.getenv("DOCX_LEVEL3_EAST_ASIA", "KaiTi_GB2312")
DOCX_BODY_LATIN = os.getenv("DOCX_BODY_LATIN", "Times New Roman")
DOCX_BODY_FONT_SIZE = float(os.getenv("DOCX_BODY_FONT_SIZE", "12"))
_DOCX_BODY_LINE_SPACING_RAW = os.getenv("DOCX_BODY_LINE_SPACING")
_DOCX_BODY_LINE_SPACING_RULE_RAW = os.getenv("DOCX_BODY_LINE_SPACING_RULE")
if _DOCX_BODY_LINE_SPACING_RULE_RAW:
    DOCX_BODY_LINE_SPACING_RULE = _DOCX_BODY_LINE_SPACING_RULE_RAW.strip().lower()
elif _DOCX_BODY_LINE_SPACING_RAW:
    try:
        DOCX_BODY_LINE_SPACING_RULE = "exact" if float(_DOCX_BODY_LINE_SPACING_RAW) > 3 else "multiple"
    except ValueError:
        DOCX_BODY_LINE_SPACING_RULE = "multiple"
else:
    DOCX_BODY_LINE_SPACING_RULE = "multiple"
DOCX_BODY_LINE_SPACING = float(_DOCX_BODY_LINE_SPACING_RAW or ("1.5" if DOCX_BODY_LINE_SPACING_RULE == "multiple" else "22"))
DOCX_BODY_FIRST_LINE_INDENT_PT = float(os.getenv("DOCX_BODY_FIRST_LINE_INDENT_PT", str(DOCX_BODY_FONT_SIZE * 2)))
DOCX_LIST_LEFT_INDENT_PT = float(os.getenv("DOCX_LIST_LEFT_INDENT_PT", str(DOCX_BODY_FONT_SIZE * 2)))
DOCX_LIST_HANGING_INDENT_PT = float(os.getenv("DOCX_LIST_HANGING_INDENT_PT", str(DOCX_BODY_FONT_SIZE)))
DOCX_TABLE_EAST_ASIA = os.getenv("DOCX_TABLE_EAST_ASIA", DOCX_BODY_EAST_ASIA)
DOCX_TABLE_FONT_SIZE = float(os.getenv("DOCX_TABLE_FONT_SIZE", "12"))
DOCX_HEADER_MAX_CHARS = int(os.getenv("DOCX_HEADER_MAX_CHARS", "42"))
DOCX_PAGE_MARGIN_TOP_CM = float(os.getenv("DOCX_PAGE_MARGIN_TOP_CM", "2.5"))
DOCX_PAGE_MARGIN_BOTTOM_CM = float(os.getenv("DOCX_PAGE_MARGIN_BOTTOM_CM", "2.5"))
DOCX_PAGE_MARGIN_LEFT_CM = float(os.getenv("DOCX_PAGE_MARGIN_LEFT_CM", "2.8"))
DOCX_PAGE_MARGIN_RIGHT_CM = float(os.getenv("DOCX_PAGE_MARGIN_RIGHT_CM", "2.5"))
DOCX_HEADER_DISTANCE_CM = float(os.getenv("DOCX_HEADER_DISTANCE_CM", "0.8"))
DOCX_FOOTER_DISTANCE_CM = float(os.getenv("DOCX_FOOTER_DISTANCE_CM", "1.48"))
DOCX_COVER_TITLE_FONT_SIZE = float(os.getenv("DOCX_COVER_TITLE_FONT_SIZE", "36"))
DOCX_TOC_TITLE_FONT_SIZE = float(os.getenv("DOCX_TOC_TITLE_FONT_SIZE", "16"))
DOCX_TOC_ENTRY_FONT_SIZE = float(os.getenv("DOCX_TOC_ENTRY_FONT_SIZE", "10.5"))
DOCX_TOC_PAGE_NUMBER_FONT_SIZE = float(os.getenv("DOCX_TOC_PAGE_NUMBER_FONT_SIZE", "9"))
DOCX_TOC_ENTRY_LINE_SPACING = float(os.getenv("DOCX_TOC_ENTRY_LINE_SPACING", "15"))
DOCX_TABLE_LINE_SPACING = float(os.getenv("DOCX_TABLE_LINE_SPACING", "18"))
DOCX_TABLE_CELL_MARGIN_TWIPS = int(os.getenv("DOCX_TABLE_CELL_MARGIN_TWIPS", "100"))
DOCX_FOOTER_PAGE_NUMBER_FONT_SIZE = float(os.getenv("DOCX_FOOTER_PAGE_NUMBER_FONT_SIZE", "9"))
DOCX_IMAGE_CAPTION_FONT_SIZE = float(os.getenv("DOCX_IMAGE_CAPTION_FONT_SIZE", "9"))
DOCX_TAICHANG_LOGO_PATH = os.getenv("DOCX_TAICHANG_LOGO_PATH", "assets/icons/taichang_logo.png")
DOCX_COVER_LOGO_WIDTH_IN = float(os.getenv("DOCX_COVER_LOGO_WIDTH_IN", "1.65"))
DOCX_COVER_SHOW_LOGO = os.getenv("DOCX_COVER_SHOW_LOGO", "false").lower() in {"1", "true", "yes", "on"}
DOCX_HEADER_LOGO_WIDTH_IN = float(os.getenv("DOCX_HEADER_LOGO_WIDTH_IN", "0.55"))
DOCX_IMAGE_MAX_HEIGHT_IN = float(os.getenv("DOCX_IMAGE_MAX_HEIGHT_IN", "9.0"))
DOCX_IMAGE_UNIFORM_FRAME = os.getenv("DOCX_IMAGE_UNIFORM_FRAME", "true").lower() in {"1", "true", "yes", "on"}
DOCX_IMAGE_FRAME_WIDTH_IN = float(os.getenv("DOCX_IMAGE_FRAME_WIDTH_IN", "5.8"))
DOCX_IMAGE_FRAME_HEIGHT_IN = float(os.getenv("DOCX_IMAGE_FRAME_HEIGHT_IN", "8.2"))
DOCX_IMAGE_FRAME_DPI = int(os.getenv("DOCX_IMAGE_FRAME_DPI", "220"))
DOCX_IMAGE_FRAME_BACKGROUND = os.getenv("DOCX_IMAGE_FRAME_BACKGROUND", "FFFFFF")
DOCX_TOC_ENTRY_BOLD_ALL = os.getenv("DOCX_TOC_ENTRY_BOLD_ALL", "false").lower() in {"1", "true", "yes", "on"}
DOCX_REFERENCE_TEMPLATE_SOURCES = (
    {
        "path": "assets/template_words/5d2a2c833dad4bb3b3ccc0856f755b54.docx",
        "role": "primary_reference_style",
        "usage": "抽取目录、页边距、封面字段、表格和签章位风格，作为 formal_bid_standard 的参考规则，不直接套打正文。",
    },
    {
        "path": "assets/template_words/1523993.doc",
        "role": "secondary_legacy_reference",
        "usage": "旧版二进制 Word 参考稿，仅用于补充格式项比对，不作为运行时模板依赖。",
    },
)
DOCX_XINJIANG_TECHNICAL_REFERENCE_PATH = "assets/template_words/技术文件 - 10kV架空绝缘导线-新疆.docx"
DOCX_XINJIANG_BUSINESS_REFERENCE_PATH = "assets/template_words/商务文件 - 10kV架空绝缘导线-新疆(1).docx"
DOCX_REFERENCE_MARGIN_CM = 3.17
DOCX_REFERENCE_HEADER_DISTANCE_CM = 1.5
DOCX_REFERENCE_FOOTER_DISTANCE_CM = 1.75
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W_NS)

DOCX_TEMPLATE_PROFILES = {
    "formal_bid_standard": {
        "template_id": DOCX_TEMPLATE_ID,
        "template_family": "formal_bid_standard",
        "applies_to": "full_or_generic_bid",
        "reference_source": "system_default_plus_reference_templates",
        "reference_path": None,
        "runtime_policy": "内置稳定模板生成，不直接套用客户/兄弟公司成稿。",
        "margins_cm": {
            "top": DOCX_PAGE_MARGIN_TOP_CM,
            "bottom": DOCX_PAGE_MARGIN_BOTTOM_CM,
            "left": DOCX_PAGE_MARGIN_LEFT_CM,
            "right": DOCX_PAGE_MARGIN_RIGHT_CM,
        },
        "header_distance_cm": DOCX_HEADER_DISTANCE_CM,
        "footer_distance_cm": DOCX_FOOTER_DISTANCE_CM,
        "toc_max_level": DOCX_TOC_MAX_LEVEL,
        "toc_entry_font_size_pt": DOCX_TOC_ENTRY_FONT_SIZE,
        "toc_entry_line_spacing_pt": DOCX_TOC_ENTRY_LINE_SPACING,
        "toc_font": DOCX_BODY_EAST_ASIA,
        "body_font": DOCX_BODY_EAST_ASIA,
        "table_font": DOCX_TABLE_EAST_ASIA,
        "cover_font": DOCX_BODY_EAST_ASIA,
        "header_footer_font": DOCX_BODY_EAST_ASIA,
        "header_text_policy": "project_and_file_type",
        "page_number_format": "page_x_of_y",
        "different_first_page_header_footer": True,
        "section_numbering_style": "decimal_outline",
        "toc_entry_bold_all": DOCX_TOC_ENTRY_BOLD_ALL,
        "table_header_fill": "EDEDED",
        "reference_outline": [],
    },
    "technical_bid_standard": {
        "template_id": "technical_bid_standard",
        "template_family": "formal_bid_xinjiang_sgcc_reference",
        "applies_to": "technical_bid_volume",
        "reference_source": "新疆10kV架空绝缘导线中标技术文件",
        "reference_path": DOCX_XINJIANG_TECHNICAL_REFERENCE_PATH,
        "runtime_policy": "仅抽取版式、目录组织和分册结构；禁止复用参考稿企业事实、产品参数、证书和附件内容。",
        "margins_cm": {
            "top": 2.54,
            "bottom": 2.54,
            "left": DOCX_REFERENCE_MARGIN_CM,
            "right": DOCX_REFERENCE_MARGIN_CM,
        },
        "header_distance_cm": DOCX_REFERENCE_HEADER_DISTANCE_CM,
        "footer_distance_cm": DOCX_REFERENCE_FOOTER_DISTANCE_CM,
        "toc_max_level": 4,
        "toc_entry_font_size_pt": 10.5,
        "toc_entry_line_spacing_pt": 15,
        "toc_font": "宋体",
        "body_font": "宋体",
        "table_font": "宋体",
        "cover_font": "宋体",
        "header_footer_font": "宋体",
        "header_text_policy": "blank",
        "page_number_format": "plain_decimal",
        "different_first_page_header_footer": False,
        "section_numbering_style": "sgcc_mixed",
        "cover_layout": {
            "style": "sgcc_reference_volume_cover",
            "project_title_font_size_pt": 18,
            "project_title_bold": True,
            "tender_no_position": "after_project_title",
            "tender_no_font_size_pt": 18,
            "tender_no_bold": True,
            "document_title_font_size_pt": 36,
            "document_title_bold": True,
            "formal_field_font_size_pt": 14,
            "formal_field_bold": True,
            "bidder_font_size_pt": 16,
            "bidder_bold": True,
            "signer_font_size_pt": 15,
            "signer_bold": True,
            "date_font_size_pt": 16,
            "date_bold": True,
        },
        "toc_entry_bold_all": False,
        "table_header_fill": "EDEDED",
        "reference_outline": [
            "技术偏差表",
            "技术特性参数表",
            "技术规范点对点应答",
            "货物组件材料配置表",
            "评审要素补充技术文件",
            "检测检验报告",
            "其他技术附件",
        ],
    },
    "business_bid_standard": {
        "template_id": "business_bid_standard",
        "template_family": "formal_bid_xinjiang_sgcc_reference",
        "applies_to": "business_bid_volume",
        "reference_source": "新疆10kV架空绝缘导线中标商务文件",
        "reference_path": DOCX_XINJIANG_BUSINESS_REFERENCE_PATH,
        "runtime_policy": "仅抽取版式、目录组织和分册结构；禁止复用参考稿企业事实、查询报告、审计报告和授权文件内容。",
        "margins_cm": {
            "top": 2.54,
            "bottom": 2.54,
            "left": DOCX_REFERENCE_MARGIN_CM,
            "right": DOCX_REFERENCE_MARGIN_CM,
        },
        "header_distance_cm": DOCX_REFERENCE_HEADER_DISTANCE_CM,
        "footer_distance_cm": DOCX_REFERENCE_FOOTER_DISTANCE_CM,
        "toc_max_level": 4,
        "toc_entry_font_size_pt": 10.5,
        "toc_entry_line_spacing_pt": 15,
        "toc_font": "宋体",
        "body_font": "宋体",
        "table_font": "宋体",
        "cover_font": "宋体",
        "header_footer_font": "宋体",
        "header_text_policy": "blank",
        "page_number_format": "plain_decimal",
        "different_first_page_header_footer": False,
        "section_numbering_style": "sgcc_mixed",
        "cover_layout": {
            "style": "sgcc_reference_volume_cover",
            "project_title_font_size_pt": 18,
            "project_title_bold": True,
            "tender_no_position": "after_project_title",
            "tender_no_font_size_pt": 18,
            "tender_no_bold": True,
            "document_title_font_size_pt": 36,
            "document_title_bold": True,
            "formal_field_font_size_pt": 14,
            "formal_field_bold": True,
            "bidder_font_size_pt": 16,
            "bidder_bold": True,
            "signer_font_size_pt": 15,
            "signer_bold": True,
            "date_font_size_pt": 16,
            "date_bold": True,
        },
        "toc_entry_bold_all": False,
        "table_header_fill": "EDEDED",
        "reference_outline": [
            "商务偏差表",
            "补充文件",
            "查询报告及截图",
            "财务状况",
            "评审要素补充商务材料",
            "授权委托书",
            "其他商务附件",
        ],
    },
}

BODY_SUBHEADING_COMMENT_RE = re.compile(r"^<!--\s*BID_BODY_SUBHEADING:\s*(.+?)\s*-->\s*$")

COVER_FIELD_LABELS = (
    "项目名称",
    "文件类型",
    "招标编号",
    "分标编号",
    "分标名称",
    "包号",
    "包名称",
    "招标人",
    "招标代理机构",
)


def _is_invalid_cover_field_value(value: str) -> bool:
    normalized = re.sub(r"[\s：:、,，;；|]+", "", clean_formal_bid_text(value or ""))
    labels = {re.sub(r"[\s：:、,，;；|]+", "", label) for label in COVER_FIELD_LABELS}
    return not normalized or normalized in labels


def _copy_template_profile(profile_id: str) -> dict:
    source = DOCX_TEMPLATE_PROFILES.get(profile_id) or DOCX_TEMPLATE_PROFILES["formal_bid_standard"]
    profile: dict = {}
    for key, value in source.items():
        if isinstance(value, dict):
            profile[key] = dict(value)
        elif isinstance(value, list):
            profile[key] = list(value)
        else:
            profile[key] = value
    return profile


def resolve_docx_template_profile(cover_fields: dict | None = None) -> dict:
    """Select the formal DOCX rendering profile from the delivery file type."""
    file_type = clean_formal_bid_text((cover_fields or {}).get("文件类型") or "")
    if "技术" in file_type:
        return _copy_template_profile("technical_bid_standard")
    if "商务" in file_type:
        return _copy_template_profile("business_bid_standard")
    return _copy_template_profile("formal_bid_standard")


def _is_xinjiang_reference_profile(profile: dict | None) -> bool:
    return (profile or {}).get("template_family") == "formal_bid_xinjiang_sgcc_reference"


def _heading_run_spec_for_profile(profile: dict | None, level: int) -> tuple[str, float, bool]:
    if _is_xinjiang_reference_profile(profile):
        return ("宋体", 12, True)
    if level == 1:
        return (DOCX_HEADING_EAST_ASIA, 22, True)
    if level == 2:
        return (DOCX_HEADING_EAST_ASIA, 15, True)
    return (DOCX_LEVEL3_EAST_ASIA, 14, True)


def _template_profile_value(profile: dict | None, key: str, default):
    if isinstance(profile, dict) and key in profile:
        return profile[key]
    return default


def _template_profile_margins(profile: dict | None) -> dict:
    margins = _template_profile_value(profile, "margins_cm", {}) or {}
    return {
        "top": float(margins.get("top", DOCX_PAGE_MARGIN_TOP_CM)),
        "bottom": float(margins.get("bottom", DOCX_PAGE_MARGIN_BOTTOM_CM)),
        "left": float(margins.get("left", DOCX_PAGE_MARGIN_LEFT_CM)),
        "right": float(margins.get("right", DOCX_PAGE_MARGIN_RIGHT_CM)),
    }


def _profile_body_font(profile: dict | None) -> str:
    return str(_template_profile_value(profile, "body_font", DOCX_BODY_EAST_ASIA))


def _profile_table_font(profile: dict | None) -> str:
    return str(_template_profile_value(profile, "table_font", DOCX_TABLE_EAST_ASIA))


def _profile_cover_font(profile: dict | None) -> str:
    return str(_template_profile_value(profile, "cover_font", DOCX_BODY_EAST_ASIA))


def _profile_cover_layout(profile: dict | None) -> dict:
    layout = _template_profile_value(profile, "cover_layout", {}) or {}
    return dict(layout) if isinstance(layout, dict) else {}


def clean_formal_bid_text(text):
    """Remove emoji/decorative symbols that are unsuitable for formal bid DOCX output."""
    if text is None:
        return ""
    cleaned = FORMAL_BID_GENERATION_NOTE_RE.sub("", str(text))
    cleaned = re.sub(r"(?m)^\s*\[?\s*建议插入图片[：:][^\n]*(?:\]|\n|$)", "", cleaned)
    cleaned = re.sub(r"(?m)^\s*[（(]\s*此处插入[^）)\n]*(?:[）)]|\n|$)", "", cleaned)
    cleaned = re.sub(r"(?m)^\s*[（(]\s*本章节附图为[：:][^）)\n]*(?:[）)]|\n|$)", "", cleaned)
    cleaned = re.sub(r"泰昌\s*\d+[.．]\s*MPP生产线[_\-\s]*(?:页面|页码|page)[_\-\s]*\d+(?:[/、，,]\s*\d+)*(?:原图)?", "MPP生产线资料", cleaned, flags=re.I)
    cleaned = re.sub(r"泰昌试验设备台账原图", "试验设备台账", cleaned)
    cleaned = re.sub(r"泰昌绿色发展规划报告第\s*\d+\s*(?:页|–|-|至)\s*第?\s*\d*\s*页?", "绿色发展规划报告", cleaned)
    cleaned = re.sub(r"泰昌绿色电力认证证书第\s*\d+\s*页", "绿色电力认证证书", cleaned)
    cleaned = re.sub(r"泰昌\d+[.．]\s*职业健康安全管理体系认证证书第\s*\d+\s*页", "职业健康安全管理体系认证证书", cleaned)
    cleaned = re.sub(r"泰昌\d+[.．]\s*质量管理体系认证证书第\s*\d+\s*页", "质量管理体系认证证书", cleaned)
    cleaned = re.sub(r"泰昌\d+[.．]\s*环境管理体系认证证书第\s*\d+\s*页", "环境管理体系认证证书", cleaned)
    cleaned = re.sub(r"源自《[^》]*(?:页面|原图|\.jpg|\.png)[^》]*》", "源自客户原始资料", cleaned, flags=re.I)
    cleaned = re.sub(r"(?:页面|页码|page)[_\-\s]*\d+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"原图", "", cleaned)
    cleaned = re.sub(r"第\s*\d+\s*页\s*(?:至|到|[-–])\s*第?\s*\d+\s*页", "相关章节", cleaned)
    cleaned = FORMAL_TEXT_CONTROL_RE.sub("", cleaned)
    cleaned = FORMAL_TEXT_SYMBOL_RE.sub("", cleaned)
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])", "", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def should_start_heading_on_new_page(level: int, text: str, heading_count: int) -> bool:
    """Formal bid exports should start only major chapters on a fresh page."""
    if heading_count <= 0:
        return False
    clean_text = clean_formal_bid_text(text)
    if level == 1:
        return True
    if FORMAL_VOLUME_HEADING_RE.match(clean_text):
        return True
    return False


def apply_run_font(run, *, east_asia=DOCX_BODY_EAST_ASIA, latin=DOCX_BODY_LATIN, size=None, bold=None):
    run.font.name = east_asia
    run._element.rPr.rFonts.set(qn('w:ascii'), east_asia)
    run._element.rPr.rFonts.set(qn('w:hAnsi'), east_asia)
    run._element.rPr.rFonts.set(qn('w:eastAsia'), east_asia)
    run._element.rPr.rFonts.set(qn('w:cs'), east_asia)
    lang = run._element.rPr.find(qn('w:lang'))
    if lang is None:
        lang = OxmlElement('w:lang')
        run._element.rPr.append(lang)
    lang.set(qn('w:val'), 'zh-CN')
    lang.set(qn('w:eastAsia'), 'zh-CN')
    lang.set(qn('w:bidi'), 'zh-CN')
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    run.font.italic = False
    run.font.underline = False
    run.font.color.rgb = RGBColor(0, 0, 0)


def apply_body_line_spacing(paragraph_format, *, line_spacing=DOCX_BODY_LINE_SPACING, rule=DOCX_BODY_LINE_SPACING_RULE) -> None:
    normalized_rule = (rule or "multiple").strip().lower()
    if normalized_rule in {"multiple", "1.5", "one_point_five", "one-and-half", "one_and_half"}:
        paragraph_format.line_spacing = float(line_spacing)
    elif normalized_rule in {"single", "1"}:
        paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        paragraph_format.line_spacing = 1.0
    else:
        paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        paragraph_format.line_spacing = Pt(float(line_spacing))


def apply_paragraph_format(paragraph, *, first_line_chars=2, line_spacing=DOCX_BODY_LINE_SPACING, space_before=0, space_after=0):
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(DOCX_BODY_FIRST_LINE_INDENT_PT if first_line_chars else 0)
    apply_body_line_spacing(fmt, line_spacing=line_spacing)
    fmt.space_before = Pt(space_before)
    fmt.space_after = Pt(space_after)


def apply_heading_paragraph_format(paragraph, level: int) -> None:
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(0)
    fmt.left_indent = Pt(0)
    fmt.right_indent = Pt(0)
    apply_body_line_spacing(fmt)
    fmt.space_before = Pt(6 if level <= 2 else 3)
    fmt.space_after = Pt(3)


def apply_list_paragraph_format(paragraph) -> None:
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(-DOCX_LIST_HANGING_INDENT_PT)
    fmt.left_indent = Pt(DOCX_LIST_LEFT_INDENT_PT)
    fmt.right_indent = Pt(0)
    apply_body_line_spacing(fmt)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)


def apply_table_paragraph_format(paragraph, *, alignment=WD_ALIGN_PARAGRAPH.CENTER) -> None:
    paragraph.alignment = alignment
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(0)
    fmt.left_indent = Pt(0)
    fmt.right_indent = Pt(0)
    fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    fmt.line_spacing = Pt(DOCX_TABLE_LINE_SPACING)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)


def _set_rfonts(rpr, *, east_asia: str, latin: str = DOCX_BODY_LATIN) -> None:
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), east_asia)
    rfonts.set(qn("w:hAnsi"), east_asia)
    rfonts.set(qn("w:eastAsia"), east_asia)
    rfonts.set(qn("w:cs"), east_asia)


def _set_font_size(rpr, size_pt: float) -> None:
    half_points = str(int(round(size_pt * 2)))
    for tag in ("w:sz", "w:szCs"):
        node = rpr.find(qn(tag))
        if node is None:
            node = OxmlElement(tag)
            rpr.append(node)
        node.set(qn("w:val"), half_points)


def _set_rpr_color(rpr, value: str = "000000") -> None:
    color = rpr.find(qn("w:color"))
    if color is None:
        color = OxmlElement("w:color")
        rpr.append(color)
    color.set(qn("w:val"), value)


def _remove_paragraph_marker_controls(ppr) -> None:
    if ppr is None:
        return
    for tag in ("w:keepLines", "w:keepNext", "w:pageBreakBefore"):
        node = ppr.find(qn(tag))
        while node is not None:
            ppr.remove(node)
            node = ppr.find(qn(tag))


def remove_black_square_paragraph_markers(doc) -> None:
    """Remove pagination controls that Word/WPS renders as black square format marks."""
    for style in doc.styles:
        if style.type == WD_STYLE_TYPE.PARAGRAPH:
            _remove_paragraph_marker_controls(style._element.pPr)
    for paragraph in doc.paragraphs:
        _remove_paragraph_marker_controls(paragraph._p.pPr)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    _remove_paragraph_marker_controls(paragraph._p.pPr)


def scrub_docx_black_square_markers(docx_path: str | Path) -> dict:
    """Remove Word pagination marker XML that appears as black squares in format-mark view."""
    source = Path(docx_path)
    if not source.exists():
        return {"enabled": True, "status": "skipped", "reason": "docx not found"}
    targets = {"word/document.xml", "word/styles.xml"}
    marker_re = re.compile(
        r"<w:(?:keepLines|keepNext|pageBreakBefore)(?:\s+[^>]*)?/>"
        r"|<w:(?:keepLines|keepNext|pageBreakBefore)(?:\s+[^>]*)?>\s*</w:(?:keepLines|keepNext|pageBreakBefore)>"
    )
    counts_before = {"keepLines": 0, "keepNext": 0, "pageBreakBefore": 0}
    counts_after = {"keepLines": 0, "keepNext": 0, "pageBreakBefore": 0}
    changed = False
    temp_path = source.with_suffix(f".{uuid.uuid4().hex}.tmp.docx")
    try:
        with ZipFile(source, "r") as zin, ZipFile(temp_path, "w", ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename in targets:
                    text = data.decode("utf-8")
                    for marker in counts_before:
                        counts_before[marker] += text.count(f"w:{marker}")
                    cleaned = marker_re.sub("", text)
                    for marker in counts_after:
                        counts_after[marker] += cleaned.count(f"w:{marker}")
                    if cleaned != text:
                        changed = True
                    data = cleaned.encode("utf-8")
                zout.writestr(item, data)
    except BadZipFile:
        temp_path.unlink(missing_ok=True)
        return {"enabled": True, "status": "skipped", "reason": "not a valid docx zip"}
    if changed:
        os.replace(temp_path, source)
    else:
        temp_path.unlink(missing_ok=True)
    return {
        "enabled": True,
        "status": "cleaned" if changed else "unchanged",
        "counts_before": counts_before,
        "counts_after": counts_after,
    }


def _w_tag(local_name: str) -> str:
    return f"{{{W_NS}}}{local_name}"


def _set_xml_run_size(run: ET.Element, half_points: int) -> bool:
    rpr = run.find(_w_tag("rPr"))
    if rpr is None:
        rpr = ET.Element(_w_tag("rPr"))
        run.insert(0, rpr)

    changed = False
    for tag_name in ("sz", "szCs"):
        node = rpr.find(_w_tag(tag_name))
        if node is None:
            node = ET.Element(_w_tag(tag_name))
            rpr.append(node)
        if node.get(_w_tag("val")) != str(half_points):
            node.set(_w_tag("val"), str(half_points))
            changed = True
    return changed


def _normalize_document_pageref_sizes(xml_text: str, half_points: int) -> tuple[str, int]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    updated = 0
    for paragraph in root.iter(_w_tag("p")):
        field_codes = "".join(node.text or "" for node in paragraph.iter(_w_tag("instrText")))
        if "PAGEREF" not in field_codes.upper():
            continue
        for run in paragraph.findall(_w_tag("r")):
            visible_text = "".join(node.text or "" for node in run.iter(_w_tag("t"))).strip()
            if re.fullmatch(r"\d+", visible_text or "") and _set_xml_run_size(run, half_points):
                updated += 1
    return ET.tostring(root, encoding="unicode"), updated


def _normalize_footer_field_sizes(xml_text: str, half_points: int) -> tuple[str, int]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    updated = 0
    for run in root.iter(_w_tag("r")):
        # Footer content is intentionally small and quiet; enforce it after
        # LibreOffice rewrites PAGE/NUMPAGES cached field results.
        if _set_xml_run_size(run, half_points):
            updated += 1
    return ET.tostring(root, encoding="unicode"), updated


def normalize_docx_field_result_fonts(docx_path: str | Path) -> dict:
    """Keep refreshed TOC page numbers and footer page fields at formal small size."""
    source = Path(docx_path)
    report = {
        "enabled": True,
        "status": "skipped",
        "toc_page_number_font_size_pt": DOCX_TOC_PAGE_NUMBER_FONT_SIZE,
        "footer_page_number_font_size_pt": DOCX_FOOTER_PAGE_NUMBER_FONT_SIZE,
        "toc_page_number_runs": 0,
        "footer_runs": 0,
    }
    if not source.exists():
        report["reason"] = "docx not found"
        return report

    toc_half_points = int(round(DOCX_TOC_PAGE_NUMBER_FONT_SIZE * 2))
    footer_half_points = int(round(DOCX_FOOTER_PAGE_NUMBER_FONT_SIZE * 2))
    changed = False
    temp_path = source.with_suffix(f".{uuid.uuid4().hex}.tmp.docx")
    try:
        with ZipFile(source, "r") as zin, ZipFile(temp_path, "w", ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    text, updated = _normalize_document_pageref_sizes(data.decode("utf-8"), toc_half_points)
                    report["toc_page_number_runs"] += updated
                    if updated:
                        changed = True
                        data = text.encode("utf-8")
                elif re.fullmatch(r"word/footer\d+\.xml", item.filename):
                    text, updated = _normalize_footer_field_sizes(data.decode("utf-8"), footer_half_points)
                    report["footer_runs"] += updated
                    if updated:
                        changed = True
                        data = text.encode("utf-8")
                zout.writestr(item, data)
    except (BadZipFile, ET.ParseError, UnicodeDecodeError) as exc:
        temp_path.unlink(missing_ok=True)
        report.update({"status": "skipped", "reason": str(exc)})
        return report

    if changed:
        os.replace(temp_path, source)
    else:
        temp_path.unlink(missing_ok=True)
    report["status"] = "normalized" if changed else "unchanged"
    return report


def ensure_docx_table_header_repeat(docx_path: str | Path) -> dict:
    """Ensure first table rows keep repeat-header metadata after LibreOffice roundtrip."""
    source = Path(docx_path)
    report = {"table_count": 0, "updated": 0, "failed": False}
    if not source.exists():
        report.update({"failed": True, "reason": "docx not found"})
        return report
    try:
        doc = Document(str(source))
        for table in doc.tables:
            report["table_count"] += 1
            if not table.rows:
                continue
            tr_pr = table.rows[0]._tr.get_or_add_trPr()
            tbl_header = tr_pr.find(qn("w:tblHeader"))
            if tbl_header is None:
                tbl_header = OxmlElement("w:tblHeader")
                tr_pr.append(tbl_header)
                report["updated"] += 1
            if tbl_header.get(qn("w:val")) != "true":
                tbl_header.set(qn("w:val"), "true")
                report["updated"] += 1
        if report["updated"]:
            doc.save(str(source))
    except Exception as exc:
        logging.exception("DOCX 表格表头重复属性兜底失败: %s", source)
        report.update({"failed": True, "reason": str(exc)})
    return report


def _truncate_header_text(text: str, max_chars: int = DOCX_HEADER_MAX_CHARS) -> str:
    text = clean_formal_bid_text(text)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars - 1]}…"


def taichang_bid_document_title(project_name: str) -> str:
    """Convert a tender project name into a Taichang bidder document title."""
    value = clean_formal_bid_text(project_name) or "投标文件"
    value = re.sub(r"招标文件$", "", value).strip()
    value = re.sub(r"招标文件", "", value).strip()
    if value.endswith("投标文件"):
        return value
    return f"{value}投标文件"


def _extract_cover_field_value(md_content: str, label: str) -> str:
    label_pattern = re.escape(label)
    patterns = [
        rf"(?:^|\n)\s*(?:[-*+]\s*)?(?:\*\*)?{label_pattern}\s*[:：](?:\*\*)?\s*(.+?)(?:\n|$)",
        rf"(?:^|\n)\s*(?:[-*+]\s*)?(?:\*\*)?{label_pattern}(?:\*\*)?\s*[:：]\s*(.+?)(?:\n|$)",
        rf"(?:^|\n)\s*\|\s*(?:\*\*)?{label_pattern}(?:\*\*)?\s*\|\s*(.+?)\s*\|",
    ]
    for pattern in patterns:
        match = re.search(pattern, md_content)
        if match:
            value = clean_formal_bid_text(re.sub(r"\*\*(.*?)\*\*", r"\1", match.group(1))).strip()
            value = re.sub(r"^[*：:\s]+", "", value).strip()
            value = re.split(r"\s{2,}|\s*\|\s*", value)[0].strip()
            if value and value not in {"无", "暂无", "待补充", "【待补充】"} and not _is_invalid_cover_field_value(value):
                return value[:80]
    return ""


def extract_bid_cover_fields(md_content: str) -> dict:
    fields = {
        label: value
        for label in COVER_FIELD_LABELS
        if (value := _extract_cover_field_value(md_content, label))
    }
    if not fields.get("文件类型"):
        title_match = re.search(r"^\s*#\s+(.+?)\s*$", md_content, re.MULTILINE)
        title = clean_formal_bid_text(title_match.group(1).strip()) if title_match else ""
        for candidate in ("商务投标文件", "技术投标文件", "资格投标文件", "价格投标文件", "投标文件"):
            if candidate in title:
                fields["文件类型"] = candidate
                break
    return fields


def merge_bid_cover_fields(markdown_fields: dict | None, structured_fields: dict | None = None) -> dict:
    """Prefer uploaded tender structured fields over markdown fallback fields."""
    merged: dict[str, str] = {}
    for source in (markdown_fields or {}, structured_fields or {}):
        if not isinstance(source, dict):
            continue
        for label in COVER_FIELD_LABELS:
            value = clean_formal_bid_text(source.get(label) or "")
            if value and not _is_invalid_cover_field_value(value):
                merged[label] = value[:120]
    return merged


def docx_template_report(cover_fields: dict | None = None) -> dict:
    profile = resolve_docx_template_profile(cover_fields)
    header_file_type = clean_formal_bid_text((cover_fields or {}).get("文件类型") or "投标文件") or "投标文件"
    header_text_policy = str(profile.get("header_text_policy") or "project_and_file_type")
    page_number_format = str(profile.get("page_number_format") or "page_x_of_y")
    return {
        "template_id": profile.get("template_id") or DOCX_TEMPLATE_ID,
        "template_family": profile.get("template_family"),
        "applies_to": profile.get("applies_to"),
        "reference_source": profile.get("reference_source"),
        "reference_path": profile.get("reference_path"),
        "runtime_policy": profile.get("runtime_policy"),
        "reference_outline": profile.get("reference_outline") or [],
        "bidder_full_name": DOCX_BIDDER_FULL_NAME,
        "body_font": _profile_body_font(profile),
        "body_latin_font": DOCX_BODY_LATIN,
        "body_font_size_pt": DOCX_BODY_FONT_SIZE,
        "body_line_spacing_rule": DOCX_BODY_LINE_SPACING_RULE,
        "body_line_spacing": DOCX_BODY_LINE_SPACING,
        "body_line_spacing_pt": None if DOCX_BODY_LINE_SPACING_RULE in {"multiple", "1.5", "one_point_five", "one-and-half", "one_and_half"} else DOCX_BODY_LINE_SPACING,
        "body_first_line_indent_pt": DOCX_BODY_FIRST_LINE_INDENT_PT,
        "list_left_indent_pt": DOCX_LIST_LEFT_INDENT_PT,
        "list_hanging_indent_pt": DOCX_LIST_HANGING_INDENT_PT,
        "heading_keep_with_next": False,
        "cover_title_font_size_pt": DOCX_COVER_TITLE_FONT_SIZE,
        "toc_title_font_size_pt": DOCX_TOC_TITLE_FONT_SIZE,
        "toc_max_level": int(profile.get("toc_max_level") or DOCX_TOC_MAX_LEVEL),
        "section_numbering_style": profile.get("section_numbering_style") or "decimal_outline",
        "toc_font": profile.get("toc_font") or DOCX_BODY_EAST_ASIA,
        "toc_entry_font_size_pt": float(profile.get("toc_entry_font_size_pt") or DOCX_TOC_ENTRY_FONT_SIZE),
        "toc_page_number_font_size_pt": DOCX_TOC_PAGE_NUMBER_FONT_SIZE,
        "toc_entry_line_spacing_pt": float(profile.get("toc_entry_line_spacing_pt") or DOCX_TOC_ENTRY_LINE_SPACING),
        "table_font": _profile_table_font(profile),
        "table_font_size_pt": DOCX_TABLE_FONT_SIZE,
        "table_line_spacing_pt": DOCX_TABLE_LINE_SPACING,
        "table_cell_margin_twips": DOCX_TABLE_CELL_MARGIN_TWIPS,
        "table_header_fill": profile.get("table_header_fill") or "EDEDED",
        "cover_layout": _profile_cover_layout(profile),
        "toc_entry_bold_all": bool(profile.get("toc_entry_bold_all", DOCX_TOC_ENTRY_BOLD_ALL)),
        "reference_templates": list(DOCX_REFERENCE_TEMPLATE_SOURCES),
        "reference_template_policy": "assets/template_words 仅作为格式参考源，按文件类型选择 technical_bid_standard / business_bid_standard / formal_bid_standard，不直接套用参考稿事实内容。",
        "image_layout": {
            "uniform_frame_enabled": DOCX_IMAGE_UNIFORM_FRAME,
            "frame_width_in": DOCX_IMAGE_FRAME_WIDTH_IN,
            "frame_height_in": DOCX_IMAGE_FRAME_HEIGHT_IN,
            "frame_dpi": DOCX_IMAGE_FRAME_DPI,
            "frame_background": DOCX_IMAGE_FRAME_BACKGROUND,
            "content_policy": "contain_no_crop_no_distortion",
        },
        "page_size": "A4",
        "margins_cm": _template_profile_margins(profile),
        "heading_font": DOCX_HEADING_EAST_ASIA,
        "heading_level3_font": DOCX_LEVEL3_EAST_ASIA,
        "header_footer": {
            "header_font": profile.get("header_footer_font") or DOCX_BODY_EAST_ASIA,
            "header_font_size_pt": 9,
            "footer_font": profile.get("header_footer_font") or DOCX_BODY_EAST_ASIA,
            "footer_font_size_pt": DOCX_FOOTER_PAGE_NUMBER_FONT_SIZE,
            "header_logo": False,
            "text_color": "000000",
            "page_number_format": "纯数字页码" if page_number_format == "plain_decimal" else "第 X 页 共 Y 页",
            "page_number_field": "PAGE" if page_number_format == "plain_decimal" else "PAGE + NUMPAGES",
            "different_first_page_header_footer": bool(profile.get("different_first_page_header_footer", True)),
            "header_text_policy": header_text_policy,
            "header_text": "" if header_text_policy == "blank" else f"左侧项目名称，右侧{header_file_type}",
            "header_max_chars": DOCX_HEADER_MAX_CHARS,
        },
        "cover_fields": cover_fields or {},
        "image_caption": {
            "font_size_pt": DOCX_IMAGE_CAPTION_FONT_SIZE,
            "alignment": "center",
            "prefix": "资料：",
            "policy": "清洗图片资产检索标题，仅保留正式材料说明，不展示内部参数命名或检索来源字段。",
        },
    }


def apply_image_paragraph_format(paragraph):
    """Prevent formal fixed body line spacing from clipping inline images in Word."""
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(0)
    fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
    fmt.line_spacing = 1.0
    fmt.space_before = Pt(6)
    fmt.space_after = Pt(6)


def _formal_image_caption_text(text: str) -> str | None:
    value = clean_formal_bid_text(re.sub(r"\*\*(.*?)\*\*", r"\1", text or "")).strip()
    return formalize_legacy_image_caption(value)


def _add_formal_image_caption(doc, caption_text: str, template_profile: dict | None = None) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(0)
    fmt.left_indent = Pt(0)
    fmt.right_indent = Pt(0)
    fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
    fmt.line_spacing = 1.0
    fmt.space_before = Pt(2)
    fmt.space_after = Pt(8)
    run = paragraph.add_run(caption_text)
    apply_run_font(run, east_asia=_profile_body_font(template_profile), size=DOCX_IMAGE_CAPTION_FONT_SIZE, bold=False)


def _markdown_heading_lines(md_content: str) -> tuple[int | None, list[dict]]:
    title_line_index: int | None = None
    entries: list[dict] = []
    for index, raw_line in enumerate(md_content.split("\n")):
        line = raw_line.strip()
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue

        level = len(match.group(1))
        text = clean_formal_bid_text(re.sub(r"\*\*(.*?)\*\*", r"\1", match.group(2))).strip()
        if not text:
            continue
        if title_line_index is None and level == 1:
            title_line_index = index
            continue

        bookmark_index = len(entries) + 1
        entries.append({
            "line_index": index,
            "level": level,
            "text": text,
            "anchor": f"bid_heading_{bookmark_index}",
            "bookmark_id": bookmark_index,
        })
    return title_line_index, entries


def _add_bookmark(paragraph, name: str, bookmark_id: int) -> None:
    bookmark_start = OxmlElement("w:bookmarkStart")
    bookmark_start.set(qn("w:id"), str(bookmark_id))
    bookmark_start.set(qn("w:name"), name)
    paragraph._p.insert(0, bookmark_start)

    bookmark_end = OxmlElement("w:bookmarkEnd")
    bookmark_end.set(qn("w:id"), str(bookmark_id))
    paragraph._p.append(bookmark_end)


def _add_internal_hyperlink(paragraph, text: str, anchor: str) -> None:
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("w:anchor"), anchor)

    run_element = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "none")
    _set_rpr_color(rpr)
    rpr.append(underline)
    _set_rpr_language(rpr)
    run_element.append(rpr)

    text_element = OxmlElement("w:t")
    text_element.text = text
    run_element.append(text_element)
    hyperlink.append(run_element)
    paragraph._p.append(hyperlink)


def _page_text_width_twips(doc) -> int:
    section = doc.sections[0]
    return max(7200, int((section.page_width - section.left_margin - section.right_margin) / 635))


def _length_to_inches(value) -> float:
    return float(value) / 914400


def _page_text_width_inches(doc) -> float:
    section = doc.sections[0]
    return max(1.0, _length_to_inches(section.page_width - section.left_margin - section.right_margin))


def _page_text_height_inches(doc) -> float:
    section = doc.sections[0]
    return max(1.0, _length_to_inches(section.page_height - section.top_margin - section.bottom_margin))


def _image_pixel_size(image_path: str | Path) -> tuple[int, int] | None:
    if Image is None:
        return None
    try:
        with Image.open(image_path) as image:
            return image.size
    except Exception:
        logging.exception("读取图片尺寸失败: %s", image_path)
        return None


def _parse_rgb_hex(value: str, default: tuple[int, int, int] = (255, 255, 255)) -> tuple[int, int, int]:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", value or "")[:6]
    if len(cleaned) != 6:
        return default
    try:
        return tuple(int(cleaned[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return default


def _image_resample_filter():
    resampling = getattr(Image, "Resampling", None) if Image is not None else None
    return getattr(resampling, "LANCZOS", getattr(Image, "LANCZOS", 1))


def _fit_image_dimensions_for_docx(
    image_path: str | Path,
    *,
    max_width_in: float,
    max_height_in: float | None = None,
) -> tuple[float, float | None, dict]:
    """Return dimensions that fit the image without cropping or aspect distortion."""
    pixel_size = _image_pixel_size(image_path)
    if not pixel_size:
        return max_width_in, None, {
            "pixel_width": None,
            "pixel_height": None,
            "display_width_in": max_width_in,
            "display_height_in": None,
            "aspect_ratio_preserved": None,
        }
    pixel_width, pixel_height = pixel_size
    if pixel_width <= 0 or pixel_height <= 0:
        return max_width_in, None, {
            "pixel_width": pixel_width,
            "pixel_height": pixel_height,
            "display_width_in": max_width_in,
            "display_height_in": None,
            "aspect_ratio_preserved": None,
        }
    max_height_in = max_height_in or DOCX_IMAGE_MAX_HEIGHT_IN
    ratio = pixel_height / pixel_width
    display_width = max_width_in
    display_height = display_width * ratio
    if display_height > max_height_in:
        display_height = max_height_in
        display_width = display_height / ratio
    aspect_delta = abs((display_width / display_height) - (pixel_width / pixel_height)) if display_height else 0
    return display_width, display_height, {
        "pixel_width": pixel_width,
        "pixel_height": pixel_height,
        "display_width_in": round(display_width, 4),
        "display_height_in": round(display_height, 4),
        "aspect_ratio_preserved": aspect_delta < 0.001,
    }


def _docx_image_frame_size(doc) -> tuple[float, float]:
    width = min(DOCX_IMAGE_FRAME_WIDTH_IN, _page_text_width_inches(doc))
    height = min(DOCX_IMAGE_FRAME_HEIGHT_IN, max(1.0, _page_text_height_inches(doc) - 0.35))
    return round(width, 4), round(height, 4)


def _standardize_image_frame_for_docx(
    image_path: str | Path,
    *,
    frame_width_in: float,
    frame_height_in: float,
) -> tuple[str, bool, dict]:
    """Render the source into a fixed white frame while preserving source content ratio."""
    source_path = Path(image_path)
    if Image is None or not DOCX_IMAGE_UNIFORM_FRAME:
        width, height, metrics = _fit_image_dimensions_for_docx(
            source_path,
            max_width_in=frame_width_in,
            max_height_in=frame_height_in,
        )
        metrics.update({
            "uniform_frame_enabled": False,
            "content_display_width_in": width,
            "content_display_height_in": height,
            "content_aspect_ratio_preserved": metrics.get("aspect_ratio_preserved"),
        })
        return str(source_path), False, metrics

    try:
        with Image.open(source_path) as source:
            image = ImageOps.exif_transpose(source) if ImageOps is not None else source.copy()
            source_width, source_height = image.size
            if source_width <= 0 or source_height <= 0:
                raise ValueError("invalid image size")

            background = _parse_rgb_hex(DOCX_IMAGE_FRAME_BACKGROUND)
            if image.mode in {"RGBA", "LA"} or ("transparency" in image.info):
                rgba = image.convert("RGBA")
                base = Image.new("RGBA", rgba.size, (*background, 255))
                base.alpha_composite(rgba)
                image = base.convert("RGB")
            elif image.mode != "RGB":
                image = image.convert("RGB")

            frame_width_px = max(1, int(round(frame_width_in * DOCX_IMAGE_FRAME_DPI)))
            frame_height_px = max(1, int(round(frame_height_in * DOCX_IMAGE_FRAME_DPI)))
            scale = min(frame_width_px / source_width, frame_height_px / source_height)
            content_width_px = max(1, int(round(source_width * scale)))
            content_height_px = max(1, int(round(source_height * scale)))
            resized = image.resize((content_width_px, content_height_px), _image_resample_filter())
            canvas = Image.new("RGB", (frame_width_px, frame_height_px), background)
            offset_x = (frame_width_px - content_width_px) // 2
            offset_y = (frame_height_px - content_height_px) // 2
            canvas.paste(resized, (offset_x, offset_y))

            temp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            temp.close()
            canvas.save(
                temp.name,
                "JPEG",
                quality=DOCX_IMAGE_JPEG_QUALITY,
                optimize=True,
                progressive=True,
                dpi=(DOCX_IMAGE_FRAME_DPI, DOCX_IMAGE_FRAME_DPI),
            )
            source_ratio = source_width / source_height
            content_ratio = content_width_px / content_height_px
            frame_ratio = frame_width_px / frame_height_px
            return temp.name, True, {
                "uniform_frame_enabled": True,
                "source_pixel_width": source_width,
                "source_pixel_height": source_height,
                "source_aspect_ratio": round(source_ratio, 6),
                "pixel_width": frame_width_px,
                "pixel_height": frame_height_px,
                "display_width_in": round(frame_width_in, 4),
                "display_height_in": round(frame_height_in, 4),
                "frame_aspect_ratio": round(frame_ratio, 6),
                "content_pixel_width": content_width_px,
                "content_pixel_height": content_height_px,
                "content_display_width_in": round(content_width_px / DOCX_IMAGE_FRAME_DPI, 4),
                "content_display_height_in": round(content_height_px / DOCX_IMAGE_FRAME_DPI, 4),
                "content_offset_x_px": offset_x,
                "content_offset_y_px": offset_y,
                "aspect_ratio_preserved": True,
                "content_aspect_ratio_preserved": abs((content_ratio - source_ratio) / source_ratio) < 0.01,
                "frame_background": DOCX_IMAGE_FRAME_BACKGROUND,
            }
    except Exception:
        logging.exception("图片统一尺寸框处理失败，退回等比例缩放: %s", image_path)
        width, height, metrics = _fit_image_dimensions_for_docx(
            source_path,
            max_width_in=frame_width_in,
            max_height_in=frame_height_in,
        )
        metrics.update({
            "uniform_frame_enabled": False,
            "uniform_frame_fallback": True,
            "display_width_in": width,
            "display_height_in": height,
            "content_display_width_in": width,
            "content_display_height_in": height,
            "content_aspect_ratio_preserved": metrics.get("aspect_ratio_preserved"),
        })
        return str(source_path), False, metrics


def _taichang_logo_path() -> Path | None:
    path = Path(DOCX_TAICHANG_LOGO_PATH)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path if path.exists() and path.is_file() else None


def _prepare_logo_image_for_docx(logo_path: Path) -> tuple[str, bool]:
    if Image is None:
        return str(logo_path), False
    try:
        with Image.open(logo_path) as source:
            image = ImageOps.exif_transpose(source) if ImageOps is not None else source.copy()
            image = image.convert("RGBA")
            width, height = image.size
            if width <= 0 or height <= 0:
                return str(logo_path), False

            bg = image.getpixel((0, 0))[:3]
            pixels = image.load()
            left, top, right, bottom = width, height, -1, -1
            for y in range(height):
                for x in range(width):
                    r, g, b, a = pixels[x, y]
                    if a <= 8:
                        continue
                    delta = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
                    if delta > 45:
                        left = min(left, x)
                        top = min(top, y)
                        right = max(right, x)
                        bottom = max(bottom, y)
            if right < left or bottom < top:
                return str(logo_path), False
            pad_x = max(8, int((right - left + 1) * 0.04))
            pad_y = max(8, int((bottom - top + 1) * 0.08))
            crop_box = (
                max(0, left - pad_x),
                max(0, top - pad_y),
                min(width, right + pad_x + 1),
                min(height, bottom + pad_y + 1),
            )
            if crop_box == (0, 0, width, height):
                return str(logo_path), False
            cropped = image.crop(crop_box)
            temp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            temp.close()
            cropped.save(temp.name, "PNG", optimize=True)
            return temp.name, True
    except Exception:
        logging.exception("Logo 自动裁白失败，继续使用原图: %s", logo_path)
        return str(logo_path), False


def _add_taichang_logo(paragraph, *, width_in: float, max_height_in: float, report: dict | None = None, placement: str = "unknown") -> bool:
    logo_path = _taichang_logo_path()
    if not logo_path:
        if report is not None:
            report.setdefault("logo", {})[placement] = {"inserted": False, "reason": "logo file missing"}
        return False
    prepared_logo, cleanup = _prepare_logo_image_for_docx(logo_path)
    width, height, metrics = _fit_image_dimensions_for_docx(
        prepared_logo,
        max_width_in=width_in,
        max_height_in=max_height_in,
    )
    try:
        run = paragraph.add_run()
        run.add_picture(str(prepared_logo), width=Inches(width), height=Inches(height) if height else None)
        if report is not None:
            report.setdefault("logo", {})[placement] = {
                "inserted": True,
                "path": str(logo_path),
                "auto_cropped": bool(cleanup),
                **metrics,
            }
    finally:
        if cleanup and os.path.exists(prepared_logo):
            os.unlink(prepared_logo)
    return True


def _set_table_element_value(parent, tag: str, **attrs) -> OxmlElement:
    node = parent.find(qn(tag))
    if node is None:
        node = OxmlElement(tag)
        parent.append(node)
    for key, value in attrs.items():
        node.set(qn(f"w:{key}"), str(value))
    return node


def _set_table_cell_margins(table, margin_twips: int = DOCX_TABLE_CELL_MARGIN_TWIPS) -> None:
    tbl_pr = table._tbl.tblPr
    cell_margin = tbl_pr.find(qn("w:tblCellMar"))
    if cell_margin is None:
        cell_margin = OxmlElement("w:tblCellMar")
        tbl_pr.append(cell_margin)
    for side in ("top", "bottom", "left", "right"):
        _set_table_element_value(cell_margin, f"w:{side}", w=margin_twips, type="dxa")


def _set_cell_margins(cell, margin_twips: int = DOCX_TABLE_CELL_MARGIN_TWIPS) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    cell_margin = tc_pr.find(qn("w:tcMar"))
    if cell_margin is None:
        cell_margin = OxmlElement("w:tcMar")
        tc_pr.append(cell_margin)
    for side in ("top", "bottom", "left", "right"):
        _set_table_element_value(cell_margin, f"w:{side}", w=margin_twips, type="dxa")


def _set_row_repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = tr_pr.find(qn("w:tblHeader"))
    if tbl_header is None:
        tbl_header = OxmlElement("w:tblHeader")
        tr_pr.append(tbl_header)
    tbl_header.set(qn("w:val"), "true")


def _set_row_cant_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = tr_pr.find(qn("w:cantSplit"))
    if cant_split is None:
        cant_split = OxmlElement("w:cantSplit")
        tr_pr.append(cant_split)
    cant_split.set(qn("w:val"), "true")


def _set_cell_width(cell, width_twips: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    _set_table_element_value(tc_pr, "w:tcW", w=max(720, width_twips), type="dxa")


def _set_table_grid_widths(table, widths: list[int]) -> None:
    table_grid = table._tbl.tblGrid
    for grid_col in list(table_grid):
        table_grid.remove(grid_col)
    for width in widths:
        grid_col = OxmlElement("w:gridCol")
        grid_col.set(qn("w:w"), str(max(720, width)))
        table_grid.append(grid_col)


def _shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        tc_pr.append(shading)
    shading.set(qn("w:fill"), fill)


def _is_centered_table_column(header_text: str) -> bool:
    return any(keyword in header_text for keyword in ("序号", "编号", "代码", "单位", "数量", "页码", "响应情况", "结论", "结果"))


def _formal_form_type(text: str) -> str | None:
    clean_text = clean_formal_bid_text(text)
    for form_type, pattern in FORMAL_FORM_HEADING_PATTERNS.items():
        if pattern.search(clean_text):
            return form_type
    return None


def _formal_bracket_heading(text: str) -> tuple[str, str] | None:
    match = re.match(r"^【\s*(.+?)\s*】$", clean_formal_bid_text(text))
    if not match:
        return None
    heading = match.group(1).strip()
    form_type = _formal_form_type(heading)
    return (form_type, heading) if form_type else None


def _add_formal_subheading(doc, text: str, template_profile: dict | None = None) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    apply_heading_paragraph_format(paragraph, 3)
    run = paragraph.add_run(text)
    east_asia = _profile_body_font(template_profile) if _is_xinjiang_reference_profile(template_profile) else DOCX_LEVEL3_EAST_ASIA
    apply_run_font(run, east_asia=east_asia, size=14, bold=True)


def _add_body_subheading(doc, text: str, template_profile: dict | None = None) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    apply_heading_paragraph_format(paragraph, 4)
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(3)
    run = paragraph.add_run(clean_formal_bid_text(text))
    east_asia, size, bold = _heading_run_spec_for_profile(template_profile, 4)
    apply_run_font(run, east_asia=east_asia, size=size, bold=bold)


def _formal_table_widths(header_cells: list[str], page_text_width: int, form_type: str | None) -> list[int]:
    headers = [clean_formal_bid_text(cell) for cell in header_cells]
    col_count = len(headers)
    if form_type == "technical_deviation" and col_count == 5:
        ratios = (0.08, 0.18, 0.24, 0.32, 0.18)
    elif form_type == "business_deviation" and col_count == 4:
        ratios = (0.08, 0.38, 0.34, 0.20)
    elif form_type == "bid_letter" and col_count == 6:
        ratios = (0.07, 0.15, 0.14, 0.24, 0.30, 0.10)
    else:
        ratios = tuple(1 / max(1, col_count) for _ in headers)
    widths = [max(720, int(page_text_width * ratio)) for ratio in ratios]
    if widths:
        widths[-1] += page_text_width - sum(widths)
    return widths


def _add_formal_signature_paragraph(doc, text: str, template_profile: dict | None = None) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(0)
    fmt.left_indent = Pt(0)
    fmt.right_indent = Pt(14)
    apply_body_line_spacing(fmt)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    run = paragraph.add_run(text)
    apply_run_font(run, east_asia=_profile_body_font(template_profile), size=DOCX_BODY_FONT_SIZE)


def _set_paragraph_right_dot_leader_tab(paragraph, *, position_twips: int) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    tabs = ppr.find(qn("w:tabs"))
    if tabs is None:
        tabs = OxmlElement("w:tabs")
        ppr.append(tabs)
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:leader"), "dot")
    tab.set(qn("w:pos"), str(position_twips))
    tabs.append(tab)


def _mark_field_dirty(fld_char) -> None:
    """Force Word/ONLYOFFICE/LibreOffice to recalculate field results on open."""
    fld_char.set(qn("w:dirty"), "true")
    fld_char.set(qn("w:fldLock"), "false")


def _add_pageref_field(paragraph, bookmark_name: str, *, placeholder: str = "1", bold: bool = False, size: float = DOCX_TOC_ENTRY_FONT_SIZE, east_asia: str = DOCX_BODY_EAST_ASIA) -> None:
    """Add a Word PAGEREF field. Word/LibreOffice refreshes it into the real page number."""
    begin = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    _mark_field_dirty(fld_begin)
    begin._r.append(fld_begin)

    instr = paragraph.add_run()
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = f" PAGEREF {bookmark_name} \\h "
    instr._r.append(instr_text)

    separate = paragraph.add_run()
    fld_separate = OxmlElement("w:fldChar")
    fld_separate.set(qn("w:fldCharType"), "separate")
    separate._r.append(fld_separate)

    result = paragraph.add_run(placeholder)
    apply_run_font(result, east_asia=east_asia, size=size, bold=bold)

    end = paragraph.add_run()
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    end._r.append(fld_end)


def _add_page_number_field(paragraph, *, placeholder: str = "1", size: float = DOCX_FOOTER_PAGE_NUMBER_FONT_SIZE, east_asia: str = DOCX_BODY_EAST_ASIA) -> None:
    begin = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    _mark_field_dirty(fld_begin)
    begin._r.append(fld_begin)

    instr = paragraph.add_run()
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = " PAGE  \\* MERGEFORMAT "
    instr._r.append(instr_text)

    separate = paragraph.add_run()
    fld_separate = OxmlElement("w:fldChar")
    fld_separate.set(qn("w:fldCharType"), "separate")
    separate._r.append(fld_separate)

    result = paragraph.add_run(placeholder)
    apply_run_font(result, east_asia=east_asia, size=size, bold=False)

    end = paragraph.add_run()
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    end._r.append(fld_end)


def _toc_entry_text(entry: dict) -> str:
    return clean_formal_bid_text(entry.get("text") or "").strip()


def _add_formal_toc_entry(doc, entry: dict, *, tab_position_twips: int, template_profile: dict | None = None) -> None:
    toc_max_level = int(_template_profile_value(template_profile, "toc_max_level", DOCX_TOC_MAX_LEVEL))
    toc_entry_font_size = float(_template_profile_value(template_profile, "toc_entry_font_size_pt", DOCX_TOC_ENTRY_FONT_SIZE))
    toc_entry_line_spacing = float(_template_profile_value(template_profile, "toc_entry_line_spacing_pt", DOCX_TOC_ENTRY_LINE_SPACING))
    toc_entry_bold = bool(_template_profile_value(template_profile, "toc_entry_bold_all", DOCX_TOC_ENTRY_BOLD_ALL))
    toc_font = str(_template_profile_value(template_profile, "toc_font", DOCX_BODY_EAST_ASIA))
    level = max(1, min(int(entry.get("level") or 1), toc_max_level))
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(0)
    fmt.left_indent = Pt((level - 1) * 18)
    fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    fmt.line_spacing = Pt(toc_entry_line_spacing)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    _set_paragraph_right_dot_leader_tab(paragraph, position_twips=tab_position_twips)

    text_run = paragraph.add_run(_toc_entry_text(entry))
    apply_run_font(text_run, east_asia=toc_font, size=toc_entry_font_size, bold=toc_entry_bold)
    paragraph.add_run("\t")
    _add_pageref_field(
        paragraph,
        str(entry.get("anchor") or ""),
        placeholder="1",
        bold=toc_entry_bold,
        size=DOCX_TOC_PAGE_NUMBER_FONT_SIZE,
        east_asia=toc_font,
    )


def _split_cover_title_lines(project_title: str) -> list[str]:
    title = clean_formal_bid_text(project_title)
    if not title:
        return []
    match = re.match(r"^(.*?第[一二三四五六七八九十百千万0-9]+次物资协议)\s*(库存.*)$", title)
    if match:
        return [match.group(1).strip(), match.group(2).strip()]
    if len(title) <= 22:
        return [title]
    split_at = len(title) // 2
    for token in ("协议", "采购", "招标"):
        idx = title.find(token)
        if 8 <= idx <= len(title) - 8:
            split_at = idx + len(token)
            break
    return [title[:split_at].strip(), title[split_at:].strip()]


def _add_cover_page(
    doc,
    project_name: str,
    cover_fields: dict | None = None,
    image_report: dict | None = None,
    template_profile: dict | None = None,
) -> None:
    bid_title = taichang_bid_document_title((cover_fields or {}).get("项目名称") or project_name)
    cover_font = _profile_cover_font(template_profile)
    cover_layout = _profile_cover_layout(template_profile)
    reference_cover = cover_layout.get("style") == "sgcc_reference_volume_cover"
    project_title_size = float(cover_layout.get("project_title_font_size_pt") or 18)
    project_title_bold = bool(cover_layout.get("project_title_bold", True))
    tender_no_size = float(cover_layout.get("tender_no_font_size_pt") or 14.04)
    tender_no_bold = bool(cover_layout.get("tender_no_bold", False))
    document_title_size = float(cover_layout.get("document_title_font_size_pt") or DOCX_COVER_TITLE_FONT_SIZE)
    document_title_bold = bool(cover_layout.get("document_title_bold", True))
    formal_field_size = float(cover_layout.get("formal_field_font_size_pt") or 14.04)
    formal_field_bold = bool(cover_layout.get("formal_field_bold", False))
    bidder_size = float(cover_layout.get("bidder_font_size_pt") or 12)
    bidder_bold = bool(cover_layout.get("bidder_bold", False))
    signer_size = float(cover_layout.get("signer_font_size_pt") or 12)
    signer_bold = bool(cover_layout.get("signer_bold", False))
    date_size = float(cover_layout.get("date_font_size_pt") or 12)
    date_bold = bool(cover_layout.get("date_bold", False))
    if DOCX_COVER_SHOW_LOGO:
        logo_para = doc.add_paragraph()
        logo_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        apply_image_paragraph_format(logo_para)
        logo_para.paragraph_format.space_before = Pt(0)
        logo_para.paragraph_format.space_after = Pt(18)
        _add_taichang_logo(
            logo_para,
            width_in=DOCX_COVER_LOGO_WIDTH_IN,
            max_height_in=1.1,
            report=image_report,
            placement="cover",
        )
    elif image_report is not None:
        image_report.setdefault("logo", {})["cover"] = {
            "inserted": False,
            "reason": "reference_template_cover_has_no_logo",
        }

    top_spacer = doc.add_paragraph()
    top_spacer.paragraph_format.first_line_indent = Pt(0)
    top_spacer.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    top_spacer.paragraph_format.line_spacing = Pt(34 if not DOCX_COVER_SHOW_LOGO else 10)
    top_spacer.paragraph_format.space_before = Pt(0)
    top_spacer.paragraph_format.space_after = Pt(0)

    project_title = clean_formal_bid_text((cover_fields or {}).get("项目名称") or project_name or "")
    for line in _split_cover_title_lines(project_title):
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.first_line_indent = Pt(0)
        para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        para.paragraph_format.line_spacing = Pt(28)
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(0)
        run = para.add_run(line)
        apply_run_font(
            run,
            east_asia=cover_font if _is_xinjiang_reference_profile(template_profile) else DOCX_HEADING_EAST_ASIA,
            size=project_title_size,
            bold=project_title_bold,
        )

    tender_no = clean_formal_bid_text((cover_fields or {}).get("招标编号") if cover_fields else "")
    if reference_cover and tender_no:
        tender_para = doc.add_paragraph()
        tender_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        tender_para.paragraph_format.first_line_indent = Pt(0)
        tender_para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        tender_para.paragraph_format.line_spacing = Pt(28)
        tender_para.paragraph_format.space_before = Pt(0)
        tender_para.paragraph_format.space_after = Pt(0)
        tender_run = tender_para.add_run(f"招标编号：{tender_no}")
        apply_run_font(tender_run, east_asia=cover_font, size=tender_no_size, bold=tender_no_bold)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.first_line_indent = Pt(0)
    title.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    title.paragraph_format.line_spacing = Pt(50)
    title.paragraph_format.space_before = Pt(18)
    title.paragraph_format.space_after = Pt(20)
    display_file_type = clean_formal_bid_text((cover_fields or {}).get("文件类型") if cover_fields else "") or "投标文件"
    if display_file_type == "投标文件" and "商务" in bid_title:
        display_file_type = "商务投标文件"
    if _is_xinjiang_reference_profile(template_profile):
        display_file_type = "投标文件"
    title_run = title.add_run(display_file_type)
    apply_run_font(
        title_run,
        east_asia=cover_font if _is_xinjiang_reference_profile(template_profile) else DOCX_HEADING_EAST_ASIA,
        size=document_title_size,
        bold=document_title_bold,
    )

    file_category = ""
    if _is_xinjiang_reference_profile(template_profile):
        raw_type = clean_formal_bid_text((cover_fields or {}).get("文件类型") if cover_fields else "")
        if "技术" in raw_type:
            file_category = "技术"
        elif "商务" in raw_type:
            file_category = "商务"
    formal_field_items = [
        ("招标编号", "招标编号", cover_fields.get("招标编号") if cover_fields else ""),
        ("分标编号", "分标编号", cover_fields.get("分标编号") if cover_fields else ""),
        ("分标名称", "分标名称", cover_fields.get("分标名称") if cover_fields else ""),
        ("包号", "包    号" if reference_cover else "包号", cover_fields.get("包号") if cover_fields else ""),
        ("包名称", "包名称", cover_fields.get("包名称") if cover_fields else ""),
        ("文件类别", "文件类别", file_category),
        ("招标人", "招标人", cover_fields.get("招标人") if cover_fields else ""),
        ("招标代理机构", "招标代理机构", cover_fields.get("招标代理机构") if cover_fields else ""),
    ]
    visible_formal_fields = [
        (display_label, value)
        for field_key, display_label, value in formal_field_items
        if value and not (reference_cover and field_key == "招标编号")
    ]
    for label, value in visible_formal_fields:
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.first_line_indent = Pt(0)
        para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        para.paragraph_format.line_spacing = Pt(29)
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(0)
        run = para.add_run(f"{label}：{value}")
        apply_run_font(run, east_asia=cover_font, size=formal_field_size, bold=formal_field_bold)

    bidder = doc.add_paragraph()
    bidder.alignment = WD_ALIGN_PARAGRAPH.CENTER
    bidder.paragraph_format.first_line_indent = Pt(0)
    bidder.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    bidder.paragraph_format.line_spacing = Pt(26)
    bidder.paragraph_format.space_before = Pt(16 if _is_xinjiang_reference_profile(template_profile) else max(105, min(205, 285 - len(visible_formal_fields) * 20)))
    bidder.paragraph_format.space_after = Pt(0)
    bidder_suffix = "（盖单位章）" if _is_xinjiang_reference_profile(template_profile) else ""
    bidder_run = bidder.add_run(f"投标人：{DOCX_BIDDER_FULL_NAME}{bidder_suffix}")
    apply_run_font(bidder_run, east_asia=cover_font, size=bidder_size, bold=bidder_bold)

    signer_para = doc.add_paragraph()
    signer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    signer_para.paragraph_format.first_line_indent = Pt(0)
    signer_para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    signer_para.paragraph_format.line_spacing = Pt(26)
    signer_para.paragraph_format.space_before = Pt(0)
    signer_para.paragraph_format.space_after = Pt(0)
    signer_text = "法定代表人（单位负责人）或其授权代表人：       （签字）" if _is_xinjiang_reference_profile(template_profile) else "法定代表人或其委托代理人：        （签名）"
    signer_run = signer_para.add_run(signer_text)
    apply_run_font(signer_run, east_asia=cover_font, size=signer_size, bold=signer_bold)

    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_para.paragraph_format.first_line_indent = Pt(0)
    date_para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    date_para.paragraph_format.line_spacing = Pt(26)
    date_para.paragraph_format.space_before = Pt(0)
    date_para.paragraph_format.space_after = Pt(0)
    date_run = date_para.add_run(datetime.today().strftime("%Y年%m月%d日"))
    apply_run_font(date_run, east_asia=cover_font, size=date_size, bold=date_bold)
    doc.add_page_break()


def _add_toc_page(doc, project_name: str, heading_entries: list[dict], cover_fields: dict | None = None, image_report: dict | None = None, template_profile: dict | None = None) -> None:
    _add_cover_page(doc, project_name, cover_fields=cover_fields, image_report=image_report, template_profile=template_profile)

    toc_title = doc.add_paragraph()
    toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    toc_title.paragraph_format.first_line_indent = Pt(0)
    toc_title.paragraph_format.space_before = Pt(0)
    toc_title.paragraph_format.space_after = Pt(12)
    toc_run = toc_title.add_run("目  录")
    apply_run_font(toc_run, east_asia=DOCX_HEADING_EAST_ASIA, size=DOCX_TOC_TITLE_FONT_SIZE, bold=True)

    toc_max_level = int(_template_profile_value(template_profile, "toc_max_level", DOCX_TOC_MAX_LEVEL))
    formal_entries = [
        entry for entry in heading_entries
        if 1 <= int(entry.get("level") or 1) <= toc_max_level and _toc_entry_text(entry)
    ]
    if not formal_entries:
        empty = doc.add_paragraph()
        empty.paragraph_format.first_line_indent = Pt(0)
        empty_run = empty.add_run("暂无章节目录，请先生成章节大纲。")
        apply_run_font(empty_run, east_asia=_profile_body_font(template_profile), size=DOCX_BODY_FONT_SIZE)
    tab_position_twips = _page_text_width_twips(doc)
    for entry in formal_entries:
        _add_formal_toc_entry(doc, entry, tab_position_twips=tab_position_twips, template_profile=template_profile)

    doc.add_page_break()


def convert_mermaid_to_image(mermaid_code):
    """将 Mermaid 代码转换为图片"""
    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix='.mmd', delete=False, mode='w', encoding='utf-8') as f:
        # 添加主题和样式设置
        mermaid_config = """
%%{init: {'theme': 'default', 'themeVariables': { 'fontSize': '16px', 'fontFamily': '%s' }}}%%
"""
        f.write((mermaid_config % DOCX_BODY_EAST_ASIA) + mermaid_code)
        mmd_file = f.name
    
    # 创建输出图片文件
    png_file = mmd_file.replace('.mmd', '.png')
    
    try:
        # 使用 mmdc 命令转换，设置统一的图片大小和背景
        subprocess.run([
            'mmdc',
            '-i', mmd_file,
            '-o', png_file,
            '-w', '800',  # 设置宽度
            '-H', '600',  # 设置高度
            '-b', 'transparent',  # 设置透明背景
            '-s', '3',  # 设置缩放比例
            '-c', 'config.json'  # 使用配置文件
        ], check=True)
        return png_file
    except (subprocess.CalledProcessError, FileNotFoundError):
        logging.exception("转换流程图失败")
        return None
    finally:
        # 清理临时文件
        if os.path.exists(mmd_file):
            os.unlink(mmd_file)

def create_mermaid_config():
    """创建 Mermaid 配置文件"""
    config = {
        "theme": "default",
        "themeVariables": {
            "fontSize": "16px",
            "fontFamily": DOCX_BODY_EAST_ASIA,
            "primaryColor": "#1f77b4",
            "primaryTextColor": "#000000",
            "primaryBorderColor": "#1f77b4",
            "lineColor": "#1f77b4",
            "secondaryColor": "#ff7f0e",
            "tertiaryColor": "#2ca02c"
        },
        "flowchart": {
            "curve": "basis",
            "padding": 15,
            "nodeSpacing": 50,
            "rankSpacing": 50
        }
    }
    
    with open('config.json', 'w', encoding='utf-8') as f:
        import json
        json.dump(config, f, indent=2)

def process_mermaid(doc, mermaid_code):
    """处理 Mermaid 流程图"""
    # 转换 Mermaid 代码为图片
    png_file = convert_mermaid_to_image(mermaid_code)
    if png_file and os.path.exists(png_file):
        display_path = png_file
        display_cleanup = False
        try:
            frame_width_in, frame_height_in = _docx_image_frame_size(doc)
            display_path, display_cleanup, _ = _standardize_image_frame_for_docx(
                png_file,
                frame_width_in=frame_width_in,
                frame_height_in=frame_height_in,
            )
            # 添加图片到文档
            doc.add_picture(display_path, width=Inches(frame_width_in), height=Inches(frame_height_in))
            
            # 设置图片居中
            last_paragraph = doc.paragraphs[-1]
            last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            apply_image_paragraph_format(last_paragraph)
            
            # 添加图片说明（可选）
            caption = doc.add_paragraph()
            caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
            caption_run = caption.add_run("图 X-X 流程图")
            caption_run.font.name = DOCX_BODY_EAST_ASIA
            caption_run._element.rPr.rFonts.set(qn('w:eastAsia'), DOCX_BODY_EAST_ASIA)
            caption_run.font.size = Pt(10.5)
        finally:
            # 清理临时图片文件
            if display_cleanup and display_path and os.path.exists(display_path):
                os.unlink(display_path)
            os.unlink(png_file)
        return True
    return False


def _image_suffix_from_response(image_ref, response=None):
    path_suffix = Path(unquote(urlparse(image_ref).path)).suffix.lower()
    if path_suffix in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}:
        return path_suffix
    content_type = response.headers.get('content-type', '').lower() if response is not None else ''
    if 'jpeg' in content_type or 'jpg' in content_type:
        return '.jpg'
    if 'png' in content_type:
        return '.png'
    if 'gif' in content_type:
        return '.gif'
    if 'bmp' in content_type:
        return '.bmp'
    if 'webp' in content_type:
        return '.webp'
    return '.png'


def _append_image_report(report, event: dict) -> None:
    if report is not None:
        report.setdefault("events", []).append(event)


def _is_safe_remote_image_url(image_ref: str) -> bool:
    if not DOCX_ALLOW_REMOTE_IMAGES:
        return False
    parsed = urlparse(image_ref)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    if hostname in {"localhost"} or hostname.endswith(".localhost"):
        return False
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except Exception:
        logging.warning("远程图片地址解析失败，已跳过: %s", image_ref)
        return False
    for family, _, _, _, sockaddr in addresses:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            logging.warning("远程图片地址指向非公网地址，已跳过: %s", image_ref)
            return False
    return True


def _resolve_api_asset_image(image_ref):
    parsed = urlparse(image_ref)
    match = re.match(r"^/api/(?:bidding/)?knowledge/assets/([^/]+)/file$", parsed.path)
    if not match:
        return None

    asset_id = unquote(match.group(1))
    variant = (parse_qs(parsed.query).get("variant") or ["original"])[0] or "original"
    from backend.db.supabase_repo import download_knowledge_asset_file_variant

    result = download_knowledge_asset_file_variant(asset_id, variant=variant)
    if not result:
        return None
    asset, data = result
    if len(data) > MARKDOWN_IMAGE_MAX_BYTES:
        raise ValueError(f"图片超过大小限制: {image_ref}")

    mime_type = str(asset.get("mime_type") or "").lower()
    file_suffix = Path(str(asset.get("file_name") or "")).suffix.lower()
    suffix = file_suffix if file_suffix in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'} else ".png"
    if not file_suffix:
        if "jpeg" in mime_type or "jpg" in mime_type:
            suffix = ".jpg"
        elif "webp" in mime_type:
            suffix = ".webp"
        elif "gif" in mime_type:
            suffix = ".gif"
        elif "bmp" in mime_type:
            suffix = ".bmp"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temp.write(data)
        return temp.name, True


def _resolve_markdown_image(image_ref, image_cache=None):
    image_ref = (image_ref or '').strip().strip('"').strip("'")
    if not image_ref:
        return None, False
    if image_cache is not None and image_ref in image_cache:
        return image_cache[image_ref]
    api_image = _resolve_api_asset_image(image_ref)
    if api_image:
        if image_cache is not None:
            image_cache[image_ref] = api_image
        return api_image
    if image_ref.startswith(('http://', 'https://')):
        if not _is_safe_remote_image_url(image_ref):
            raise ValueError("远程图片未启用或地址不安全")
        response = requests.get(
            image_ref,
            timeout=(MARKDOWN_IMAGE_CONNECT_TIMEOUT, MARKDOWN_IMAGE_READ_TIMEOUT),
            stream=True,
        )
        response.raise_for_status()
        suffix = _image_suffix_from_response(image_ref, response)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            total = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    total += len(chunk)
                    if total > MARKDOWN_IMAGE_MAX_BYTES:
                        raise ValueError(f"图片超过大小限制: {image_ref}")
                    temp.write(chunk)
            result = (temp.name, True)
            if image_cache is not None:
                image_cache[image_ref] = result
            return result

    local_path = Path(image_ref)
    if not local_path.is_absolute():
        local_path = Path.cwd() / local_path
    if local_path.exists() and local_path.is_file():
        result = (str(local_path), False)
        if image_cache is not None:
            image_cache[image_ref] = result
        return result
    return None, False


def _prepare_docx_image(image_path):
    """Use original image unless it is too large for a practical DOCX payload."""
    if Image is None or not image_path:
        return image_path, False

    suffix = Path(image_path).suffix.lower()
    if suffix not in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
        return image_path, False

    try:
        source_size = os.path.getsize(image_path)
        with Image.open(image_path) as source:
            image = ImageOps.exif_transpose(source) if ImageOps is not None else source.copy()
            width, height = image.size
            needs_resize = max(width, height) > DOCX_IMAGE_MAX_EDGE_PX
            needs_compress = source_size > DOCX_IMAGE_MAX_BYTES
            if not needs_resize and not needs_compress:
                return image_path, False

            image.thumbnail((DOCX_IMAGE_MAX_EDGE_PX, DOCX_IMAGE_MAX_EDGE_PX), Image.Resampling.LANCZOS)
            has_alpha = image.mode in {"RGBA", "LA"} or ("transparency" in image.info)
            if has_alpha:
                if image.mode != "RGBA":
                    image = image.convert("RGBA")
                temp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                temp.close()
                image.save(temp.name, "PNG", optimize=True)
                return temp.name, True

            if image.mode != "RGB":
                image = image.convert("RGB")
            temp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            temp.close()
            image.save(temp.name, "JPEG", quality=DOCX_IMAGE_JPEG_QUALITY, optimize=True, progressive=True)
            return temp.name, True
    except Exception:
        logging.exception("图片清晰压缩失败，继续使用原图: %s", image_path)
        return image_path, False


def process_markdown_image(doc, alt_text, image_ref, image_cache=None, image_report=None):
    """处理 Markdown 图片语法，插入居中图片和中文图注。"""
    image_path = None
    cleanup = False
    prepared_path = None
    prepared_cleanup = False
    frame_path = None
    frame_cleanup = False
    clean_alt = clean_formal_asset_title(clean_formal_bid_text(alt_text), "未命名图片")
    try:
        image_path, cleanup = _resolve_markdown_image(image_ref, image_cache=image_cache)
        if not image_path:
            _append_image_report(image_report, {
                "status": "skipped",
                "reason": "图片路径不存在或无法解析",
                "alt": clean_alt,
                "ref": image_ref,
            })
            return False
        prepared_path, prepared_cleanup = _prepare_docx_image(image_path)
        frame_width_in, frame_height_in = _docx_image_frame_size(doc)
        frame_path, frame_cleanup, metrics = _standardize_image_frame_for_docx(
            prepared_path,
            frame_width_in=frame_width_in,
            frame_height_in=frame_height_in,
        )
        width_in = metrics.get("display_width_in") or frame_width_in
        height_in = metrics.get("display_height_in") or frame_height_in
        doc.add_picture(frame_path, width=Inches(width_in), height=Inches(height_in) if height_in else None)
        image_para = doc.paragraphs[-1]
        image_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        apply_image_paragraph_format(image_para)

        _append_image_report(image_report, {
            "status": "inserted",
            "alt": clean_alt,
            "ref": image_ref,
            "source_path": str(image_path),
            "prepared": bool(prepared_cleanup),
            "fit": metrics,
        })
        return True
    except Exception as exc:
        logging.exception("插入图片失败: %s", image_ref)
        _append_image_report(image_report, {
            "status": "failed",
            "reason": str(exc)[:300],
            "alt": clean_alt,
            "ref": image_ref,
        })
        return False
    finally:
        if frame_cleanup and frame_path and os.path.exists(frame_path):
            os.unlink(frame_path)
        if prepared_cleanup and prepared_path and os.path.exists(prepared_path):
            os.unlink(prepared_path)

def set_document_styles(doc, template_profile: dict | None = None):
    """设置文档样式"""
    body_font = _profile_body_font(template_profile)
    styles = doc.styles
    normal = styles['Normal']
    normal.font.name = body_font
    normal._element.rPr.rFonts.set(qn('w:ascii'), body_font)
    normal._element.rPr.rFonts.set(qn('w:hAnsi'), body_font)
    normal._element.rPr.rFonts.set(qn('w:eastAsia'), body_font)
    normal._element.rPr.rFonts.set(qn('w:cs'), body_font)
    normal.font.size = Pt(DOCX_BODY_FONT_SIZE)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    apply_body_line_spacing(normal.paragraph_format)
    normal.paragraph_format.first_line_indent = Pt(DOCX_BODY_FIRST_LINE_INDENT_PT)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)

    heading_specs = {
        1: (DOCX_HEADING_EAST_ASIA, 22, True),
        2: (DOCX_HEADING_EAST_ASIA, 15, True),
        3: (DOCX_LEVEL3_EAST_ASIA, 14, True),
        4: (DOCX_LEVEL3_EAST_ASIA, 14, True),
    }
    for i in range(1, 5):
        style = styles[f'Heading {i}']
        east_asia, size, bold = heading_specs[i]
        style.font.name = east_asia
        style._element.rPr.rFonts.set(qn('w:ascii'), east_asia)
        style._element.rPr.rFonts.set(qn('w:hAnsi'), east_asia)
        style._element.rPr.rFonts.set(qn('w:eastAsia'), east_asia)
        style._element.rPr.rFonts.set(qn('w:cs'), east_asia)
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.italic = False
        style.font.underline = False
        style.font.color.rgb = RGBColor(0, 0, 0)
        apply_body_line_spacing(style.paragraph_format)
        style.paragraph_format.first_line_indent = Pt(0)
        style.paragraph_format.space_before = Pt(6 if i <= 2 else 3)
        style.paragraph_format.space_after = Pt(3)

    for style_name in ['List Bullet', 'List Number']:
        style = styles[style_name]
        style.font.name = body_font
        style._element.rPr.rFonts.set(qn('w:ascii'), body_font)
        style._element.rPr.rFonts.set(qn('w:hAnsi'), body_font)
        style._element.rPr.rFonts.set(qn('w:eastAsia'), body_font)
        style._element.rPr.rFonts.set(qn('w:cs'), body_font)
        style.font.size = Pt(DOCX_BODY_FONT_SIZE)
        style.font.color.rgb = RGBColor(0, 0, 0)
        apply_body_line_spacing(style.paragraph_format)
        style.paragraph_format.first_line_indent = Pt(-DOCX_LIST_HANGING_INDENT_PT)
        style.paragraph_format.left_indent = Pt(DOCX_LIST_LEFT_INDENT_PT)
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(0)

def _set_rpr_language(rpr):
    lang = rpr.find(qn('w:lang'))
    if lang is None:
        lang = OxmlElement('w:lang')
        rpr.append(lang)
    lang.set(qn('w:val'), 'zh-CN')
    lang.set(qn('w:eastAsia'), 'zh-CN')
    lang.set(qn('w:bidi'), 'zh-CN')

def set_document_language(doc, template_profile: dict | None = None):
    """设置 DOCX 默认校对语言为简体中文，避免 ONLYOFFICE 状态栏显示 English - United States。"""
    body_font = _profile_body_font(template_profile)
    styles_element = doc.styles.element
    doc_defaults = styles_element.find(qn('w:docDefaults'))
    if doc_defaults is None:
        doc_defaults = OxmlElement('w:docDefaults')
        styles_element.insert(0, doc_defaults)

    rpr_default = doc_defaults.find(qn('w:rPrDefault'))
    if rpr_default is None:
        rpr_default = OxmlElement('w:rPrDefault')
        doc_defaults.append(rpr_default)

    rpr = rpr_default.find(qn('w:rPr'))
    if rpr is None:
        rpr = OxmlElement('w:rPr')
        rpr_default.append(rpr)
    _set_rfonts(rpr, east_asia=body_font)
    _set_font_size(rpr, DOCX_BODY_FONT_SIZE)
    _set_rpr_color(rpr)
    _set_rpr_language(rpr)

    for style in doc.styles:
        if style.type in {WD_STYLE_TYPE.PARAGRAPH, WD_STYLE_TYPE.CHARACTER, WD_STYLE_TYPE.TABLE}:
            rpr = style._element.get_or_add_rPr()
            if style.type in {WD_STYLE_TYPE.PARAGRAPH, WD_STYLE_TYPE.CHARACTER} and style.name in {"Normal", "Body Text", "List Bullet", "List Number"}:
                _set_rfonts(rpr, east_asia=body_font)
                _set_font_size(rpr, DOCX_BODY_FONT_SIZE)
            _set_rpr_color(rpr)
            _set_rpr_language(rpr)

    settings = doc.settings.element
    theme_lang = settings.find(qn('w:themeFontLang'))
    if theme_lang is None:
        theme_lang = OxmlElement('w:themeFontLang')
        settings.append(theme_lang)
    theme_lang.set(qn('w:val'), 'zh-CN')
    theme_lang.set(qn('w:eastAsia'), 'zh-CN')
    theme_lang.set(qn('w:bidi'), 'zh-CN')

    # 目录页码、页脚页码和总页数字段依赖 Word/LibreOffice 的版面引擎刷新。
    # 打开文档时要求办公软件更新域，避免目录页码停留在占位值。
    update_fields = settings.find(qn('w:updateFields'))
    if update_fields is None:
        update_fields = OxmlElement('w:updateFields')
        settings.append(update_fields)
    update_fields.set(qn('w:val'), 'true')

def set_document_format(doc, project_name, image_report: dict | None = None, file_type: str = "投标文件", template_profile: dict | None = None):
    """设置文档格式"""
    project_name = clean_formal_bid_text(project_name) or "投标文件"
    margins = _template_profile_margins(template_profile)
    header_distance_cm = float(_template_profile_value(template_profile, "header_distance_cm", DOCX_HEADER_DISTANCE_CM))
    footer_distance_cm = float(_template_profile_value(template_profile, "footer_distance_cm", DOCX_FOOTER_DISTANCE_CM))
    header_footer_font = str(_template_profile_value(template_profile, "header_footer_font", DOCX_BODY_EAST_ASIA))
    header_text_policy = str(_template_profile_value(template_profile, "header_text_policy", "project_and_file_type"))
    page_number_format = str(_template_profile_value(template_profile, "page_number_format", "page_x_of_y"))
    different_first_page = bool(_template_profile_value(template_profile, "different_first_page_header_footer", True))
    # 设置页面边距
    sections = doc.sections
    for section in sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(margins["top"])
        section.bottom_margin = Cm(margins["bottom"])
        section.left_margin = Cm(margins["left"])
        section.right_margin = Cm(margins["right"])
        section.header_distance = Cm(header_distance_cm)
        section.footer_distance = Cm(footer_distance_cm)
        section.different_first_page_header_footer = different_first_page
        first_header = section.first_page_header
        if first_header.paragraphs:
            first_header.paragraphs[0].text = ""
        
        # 添加页眉
        header = section.header
        header_para = header.paragraphs[0]
        header_para.text = ""
        header_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        header_para.paragraph_format.first_line_indent = Pt(0)
        header_para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        header_para.paragraph_format.line_spacing = 1.0
        header_para.paragraph_format.space_before = Pt(0)
        header_para.paragraph_format.space_after = Pt(0)
        header_para.paragraph_format.tab_stops.add_tab_stop(
            section.page_width - section.left_margin - section.right_margin,
            WD_TAB_ALIGNMENT.RIGHT,
        )
        if image_report is not None:
            image_report.setdefault("logo", {})["header"] = {
                "inserted": False,
                "reason": "formal_header_has_no_logo",
            }
        if header_text_policy != "blank":
            header_left = _truncate_header_text(project_name, max_chars=DOCX_HEADER_MAX_CHARS)
            header_file_type = clean_formal_bid_text(file_type or "投标文件") or "投标文件"
            text_run = header_para.add_run(f"{header_left}\t{header_file_type}")
            apply_run_font(text_run, east_asia=header_footer_font, size=9)
            for run in header_para.runs:
                apply_run_font(run, east_asia=header_footer_font, size=9)
        
        # 添加页脚
        footer = section.footer
        footer_para = footer.paragraphs[0]
        footer_para.text = ""
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if page_number_format == "plain_decimal":
            _add_page_number_field(
                footer_para,
                placeholder="1",
                size=DOCX_FOOTER_PAGE_NUMBER_FONT_SIZE,
                east_asia=header_footer_font,
            )
        else:
            footer_para.add_run("第 ")
            # 当前页码
            run = footer_para.add_run()
            fldChar1 = OxmlElement('w:fldChar')
            fldChar1.set(qn('w:fldCharType'), 'begin')
            _mark_field_dirty(fldChar1)
            run._r.append(fldChar1)
            instrText = OxmlElement('w:instrText')
            instrText.text = 'PAGE'
            run._r.append(instrText)
            fldChar2 = OxmlElement('w:fldChar')
            fldChar2.set(qn('w:fldCharType'), 'end')
            run._r.append(fldChar2)
            footer_para.add_run(" 页 共 ")
            # 总页数
            run = footer_para.add_run()
            fldChar1 = OxmlElement('w:fldChar')
            fldChar1.set(qn('w:fldCharType'), 'begin')
            _mark_field_dirty(fldChar1)
            run._r.append(fldChar1)
            instrText = OxmlElement('w:instrText')
            instrText.text = 'NUMPAGES'
            run._r.append(instrText)
            fldChar2 = OxmlElement('w:fldChar')
            fldChar2.set(qn('w:fldCharType'), 'end')
            run._r.append(fldChar2)
            footer_para.add_run(" 页")
        for run in footer_para.runs:
            apply_run_font(run, east_asia=header_footer_font, size=9)

def process_table(md_table, doc, *, form_type: str | None = None, form_report: dict | None = None, template_profile: dict | None = None):
    """处理 Markdown 表格"""
    lines = md_table.strip().split('\n')
    if len(lines) < 3:  # 至少需要表头、分隔行和一行数据
        return
    
    # 计算列数
    header_cells = lines[0].strip('|').split('|')
    col_count = len(header_cells)
    
    # 创建表格
    table = doc.add_table(rows=1, cols=col_count)
    table_font = _profile_table_font(template_profile)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.allow_autofit = False
    tbl_pr = table._tbl.tblPr
    _set_table_element_value(tbl_pr, "w:tblW", w="5000", type="pct")
    _set_table_element_value(tbl_pr, "w:tblLayout", type="fixed")
    _set_table_cell_margins(table)
    page_text_width = _page_text_width_twips(doc)
    col_widths = _formal_table_widths(header_cells, page_text_width, form_type)
    _set_table_grid_widths(table, col_widths)
    if form_type and form_report is not None:
        form_report["tables"] = int(form_report.get("tables") or 0) + 1
    
    # 添加表头
    header_row = table.rows[0]
    _set_row_repeat_header(header_row)
    _set_row_cant_split(header_row)
    for i, cell in enumerate(header_cells):
        clean_cell = clean_formal_bid_text(cell)
        header_row.cells[i].text = clean_cell
        header_row.cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        _set_cell_width(header_row.cells[i], col_widths[i])
        _set_cell_margins(header_row.cells[i])
        _shade_cell(header_row.cells[i], str(_template_profile_value(template_profile, "table_header_fill", "EDEDED")))
        # 设置表头格式
        for paragraph in header_row.cells[i].paragraphs:
            apply_table_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER)
            for run in paragraph.runs:
                run.bold = True
                apply_run_font(run, east_asia=table_font, size=DOCX_TABLE_FONT_SIZE, bold=True)
    
    # 添加数据行
    for line in lines[2:]:  # 跳过表头和分隔行
        cells = line.strip('|').split('|')
        if len(cells) == col_count:
            row = table.add_row()
            _set_row_cant_split(row)
            if form_type and form_report is not None:
                form_report["non_split_rows"] = int(form_report.get("non_split_rows") or 0) + 1
            for i, cell in enumerate(cells):
                clean_cell = clean_formal_bid_text(cell)
                row.cells[i].text = clean_cell
                row.cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                _set_cell_width(row.cells[i], col_widths[i])
                _set_cell_margins(row.cells[i])
                # 设置单元格格式
                header_text = clean_formal_bid_text(header_cells[i]) if i < len(header_cells) else ""
                alignment = WD_ALIGN_PARAGRAPH.CENTER if _is_centered_table_column(header_text) else WD_ALIGN_PARAGRAPH.LEFT
                for paragraph in row.cells[i].paragraphs:
                    apply_table_paragraph_format(paragraph, alignment=alignment)
                    for run in paragraph.runs:
                        apply_run_font(run, east_asia=table_font, size=DOCX_TABLE_FONT_SIZE)


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _soffice_bin() -> str | None:
    configured = (os.getenv("SOFFICE_BIN") or "").strip()
    if configured:
        return configured
    return shutil.which("soffice") or (
        "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        if Path("/Applications/LibreOffice.app/Contents/MacOS/soffice").exists()
        else None
    )


def _docx_refresh_user_message(status: str, reason: str | None = None) -> str:
    if status == "refreshed":
        return "DOCX 已完成自动刷新，目录页码、页脚页码和总页数字段已重新保存。"
    if status == "skipped":
        return "DOCX 已生成，但当前环境关闭了自动页码刷新；请在 Word/WPS 中打开后全选并刷新域。"
    detail = f"（{reason}）" if reason else ""
    return f"DOCX 已生成，但服务器未能自动刷新目录页码{detail}；请打开 Word/WPS 后全选并刷新域，或联系管理员检查 LibreOffice。"


def _update_refresh_report(report: dict, *, status: str, reason: str | None = None, **extra) -> dict:
    report.update({
        "status": status,
        "manual_refresh_required": status != "refreshed",
        "user_message": _docx_refresh_user_message(status, reason),
    })
    if reason:
        report["reason"] = reason
    report.update(extra)
    return report


def refresh_docx_fields_with_soffice(docx_path: str | Path) -> tuple[Path, dict]:
    """Refresh DOCX fields with LibreOffice headless while keeping the output as DOCX."""
    source = Path(docx_path)
    report = {
        "enabled": _bool_env("DOCX_REFRESH_FIELDS", True),
        "status": "skipped",
        "tool": "libreoffice",
        "soffice_bin": None,
        "input_path": str(source),
    }
    if not report["enabled"]:
        _update_refresh_report(report, status="skipped", reason="DOCX_REFRESH_FIELDS is disabled")
        return source, report
    if not source.exists():
        _update_refresh_report(report, status="failed", reason="DOCX file does not exist")
        return source, report

    soffice_bin = _soffice_bin()
    report["soffice_bin"] = soffice_bin
    if not soffice_bin:
        _update_refresh_report(report, status="failed", reason="soffice executable not found")
        return source, report
    if os.path.sep in soffice_bin and not Path(soffice_bin).exists():
        _update_refresh_report(report, status="failed", reason=f"soffice executable does not exist: {soffice_bin}")
        return source, report

    timeout = int(os.getenv("DOCX_REFRESH_TIMEOUT_SECONDS", "180"))
    report["timeout_seconds"] = timeout
    with tempfile.TemporaryDirectory(prefix="docx-refresh-") as tmpdir:
        work_dir = Path(tmpdir)
        input_dir = work_dir / "input"
        output_dir = work_dir / "output"
        profile_dir = work_dir / "profile"
        input_dir.mkdir()
        output_dir.mkdir()
        profile_dir.mkdir()
        temp_input = input_dir / source.name
        shutil.copy2(source, temp_input)

        cmd = [
            soffice_bin,
            "--headless",
            "--invisible",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--nofirststartwizard",
            "--norestore",
            "-env:UserInstallation=" + profile_dir.as_uri(),
            "--convert-to",
            "docx",
            "--outdir",
            str(output_dir),
            str(temp_input),
        ]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            logging.warning("LibreOffice 刷新 DOCX 字段超时: %s timeout=%s", source, timeout)
            _update_refresh_report(report, status="failed", reason=f"LibreOffice refresh timed out after {timeout} seconds")
            return source, report
        except Exception as exc:
            logging.exception("LibreOffice 刷新 DOCX 字段失败: %s", source)
            _update_refresh_report(report, status="failed", reason=str(exc))
            return source, report

        report.update({
            "returncode": completed.returncode,
            "stdout": (completed.stdout or "")[-2000:],
            "stderr": (completed.stderr or "")[-2000:],
        })
        refreshed = output_dir / source.name
        if completed.returncode != 0 or not refreshed.exists() or refreshed.stat().st_size == 0:
            _update_refresh_report(report, status="failed", reason="LibreOffice did not produce refreshed DOCX")
            logging.warning("LibreOffice 未生成刷新后的 DOCX: %s report=%s", source, report)
            return source, report

        temp_refreshed = source.with_name(f".{source.stem}.refreshed-{uuid.uuid4().hex}.docx")
        shutil.copy2(refreshed, temp_refreshed)
        os.replace(str(temp_refreshed), str(source))
        _update_refresh_report(report, status="refreshed", output_path=str(source), size=source.stat().st_size)
        report["table_header_repeat"] = ensure_docx_table_header_repeat(source)
        report["marker_cleanup"] = scrub_docx_black_square_markers(source)
        report["field_font_normalization"] = normalize_docx_field_result_fonts(source)
        report["size"] = source.stat().st_size
        logging.info("LibreOffice 已刷新 DOCX 字段: %s", source)
        return source, report


def convert_md_to_word(md_file, return_report: bool = False, cover_fields: dict | None = None):
    """将Markdown文件转换为Word文档"""
    # 读取Markdown文件
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = clean_formal_bid_text(f.read())

    title_match = re.search(r'^\s*#\s+(.+?)\s*$', md_content, re.MULTILINE)
    markdown_project_name = clean_formal_bid_text(title_match.group(1).strip()) if title_match else Path(md_file).stem
    markdown_cover_fields = extract_bid_cover_fields(md_content)
    resolved_cover_fields = merge_bid_cover_fields(markdown_cover_fields, cover_fields)
    template_profile = resolve_docx_template_profile(resolved_cover_fields)
    project_name = resolved_cover_fields.get("项目名称") or markdown_project_name
    project_name = taichang_bid_document_title(project_name)

    # 创建Word文档
    doc = Document()
    set_document_styles(doc, template_profile=template_profile)
    set_document_language(doc, template_profile=template_profile)
    body_font = _profile_body_font(template_profile)
    image_report = {
        "max_images": MARKDOWN_IMAGE_MAX_COUNT,
        "found": 0,
        "inserted": 0,
        "skipped": 0,
        "failed": 0,
        "events": [],
        "logo": {},
        "mermaid": {
            "found": 0,
            "inserted": 0,
            "skipped": 0,
        },
        "captions": {
            "detected": 0,
            "formalized": 0,
            "samples": [],
        },
        "formal_forms": {
            "detected_types": [],
            "tables": 0,
            "subheadings": 0,
            "subheading_page_breaks": 0,
            "signature_lines": 0,
            "non_split_rows": 0,
        },
    }
    
    # 设置文档格式
    set_document_format(
        doc,
        project_name,
        image_report=image_report,
        file_type=resolved_cover_fields.get("文件类型") or "投标文件",
        template_profile=template_profile,
    )
    title_line_index, heading_entries = _markdown_heading_lines(md_content)
    heading_entry_by_line = {entry["line_index"]: entry for entry in heading_entries}
    _add_toc_page(
        doc,
        project_name,
        heading_entries,
        cover_fields=resolved_cover_fields,
        image_report=image_report,
        template_profile=template_profile,
    )
    
    # 处理Markdown内容
    lines = md_content.split('\n')
    i = 0
    image_cache = {}
    inserted_image_count = 0
    heading_count = 0
    current_form_type = None
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', line):
            i += 1
            continue

        body_subheading_match = BODY_SUBHEADING_COMMENT_RE.match(line)
        if body_subheading_match:
            heading_text = clean_formal_bid_text(body_subheading_match.group(1)).strip()
            detected_form_type = _formal_form_type(heading_text)
            if detected_form_type:
                previous_form_type = current_form_type
                current_form_type = detected_form_type
                detected_types = image_report["formal_forms"]["detected_types"]
                if detected_form_type not in detected_types:
                    detected_types.append(detected_form_type)
                if previous_form_type and previous_form_type != detected_form_type:
                    doc.add_page_break()
                    image_report["formal_forms"]["subheading_page_breaks"] += 1
                _add_formal_subheading(doc, heading_text, template_profile=template_profile)
                image_report["formal_forms"]["subheadings"] += 1
            elif heading_text:
                _add_body_subheading(doc, heading_text, template_profile=template_profile)
            i += 1
            continue

        fence_match = re.match(r"^(```|~~~)\s*([A-Za-z0-9_-]+)?\s*$", line)
        if fence_match:
            fence = fence_match.group(1)
            lang = (fence_match.group(2) or "").lower()
            block_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                block_lines.append(lines[i])
                i += 1
            if i < len(lines) and lines[i].strip().startswith(fence):
                i += 1
            if lang == "mermaid":
                image_report["mermaid"]["found"] += 1
                if process_mermaid(doc, "\n".join(block_lines)):
                    image_report["mermaid"]["inserted"] += 1
                else:
                    image_report["mermaid"]["skipped"] += 1
                    _append_image_report(image_report, {
                        "status": "skipped",
                        "reason": "Mermaid 流程图转换失败，正式 DOCX 已省略源码块。",
                        "type": "mermaid",
                    })
                continue
            for code_line in block_lines:
                text = clean_formal_bid_text(code_line)
                if text:
                    p = doc.add_paragraph()
                    run = p.add_run(text)
                    apply_run_font(run, east_asia=body_font, size=DOCX_BODY_FONT_SIZE)
                    apply_paragraph_format(p)
            continue

        image_match = re.match(r'^!\[(.*?)\]\((.*?)\)\s*$', line)
        if image_match:
            image_report["found"] += 1
            if inserted_image_count < MARKDOWN_IMAGE_MAX_COUNT:
                if process_markdown_image(doc, image_match.group(1), image_match.group(2), image_cache=image_cache, image_report=image_report):
                    inserted_image_count += 1
                    image_report["inserted"] += 1
                else:
                    last_status = (image_report.get("events") or [{}])[-1].get("status")
                    if last_status == "failed":
                        image_report["failed"] += 1
                    else:
                        image_report["skipped"] += 1
            else:
                image_report["skipped"] += 1
                _append_image_report(image_report, {
                    "status": "skipped",
                    "reason": f"超过整份文档插图数量上限 {MARKDOWN_IMAGE_MAX_COUNT}",
                    "alt": clean_formal_bid_text(image_match.group(1)) or "未命名图片",
                    "ref": image_match.group(2),
                })
            i += 1
            continue
        
        # 处理表格
        if line.startswith('|'):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i])
                i += 1
            process_table(
                '\n'.join(table_lines),
                doc,
                form_type=current_form_type,
                form_report=image_report["formal_forms"],
                template_profile=template_profile,
            )
            continue
        
        # 处理标题
        if line.startswith('#'):
            if title_line_index is not None and i == title_line_index:
                i += 1
                continue
            level = len(re.match(r'^#+', line).group())
            # 移除标题中的加粗标记
            text = clean_formal_bid_text(re.sub(r'\*\*(.*?)\*\*', r'\1', line.lstrip('#').strip()))
            detected_form_type = _formal_form_type(text)
            if detected_form_type:
                current_form_type = detected_form_type
                detected_types = image_report["formal_forms"]["detected_types"]
                if detected_form_type not in detected_types:
                    detected_types.append(detected_form_type)
            elif level <= 2:
                current_form_type = None
            if should_start_heading_on_new_page(level, text, heading_count):
                doc.add_page_break()
            word_heading_level = min(level, 4)
            p = doc.add_heading(text, level=word_heading_level)
            apply_heading_paragraph_format(p, word_heading_level)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if _is_xinjiang_reference_profile(template_profile) else (WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT)
            east_asia, size, bold = _heading_run_spec_for_profile(template_profile, level)
            for run in p.runs:
                apply_run_font(run, east_asia=east_asia, size=size, bold=bold)
            if i in heading_entry_by_line:
                entry = heading_entry_by_line[i]
                _add_bookmark(p, entry["anchor"], int(entry["bookmark_id"]))
            heading_count += 1
        
        # 处理列表
        elif line.startswith(('- ', '* ', '+ ')):
            # 移除列表标记
            text = line[2:].strip()
            # 移除加粗标记
            text = clean_formal_bid_text(re.sub(r'\*\*(.*?)\*\*', r'\1', text))
            p = doc.add_paragraph(style='List Bullet')
            run = p.add_run(text)
            apply_run_font(run, east_asia=body_font, size=DOCX_BODY_FONT_SIZE)
            apply_list_paragraph_format(p)
        
        # 处理数字列表。保留 Markdown 原始序号，避免 Word/LibreOffice 将全文
        # 共用的 List Number 样式连续累计到数百位；章节内的 1.1、2.1 等层级
        # 编号也应按模型原文展示，不能被错误改写为全局自动编号。
        elif re.match(r'^\d+(?:\.\d+)*\.?(?:\s+|$)', line):
            marker_match = re.match(r'^(\d+(?:\.\d+)*\.?)\s*', line)
            marker = marker_match.group(1) if marker_match else ""
            text = line[marker_match.end():].strip() if marker_match else line.strip()
            # 移除加粗标记
            text = clean_formal_bid_text(re.sub(r'\*\*(.*?)\*\*', r'\1', text))
            p = doc.add_paragraph()
            run = p.add_run(f"{marker} {text}".strip())
            apply_run_font(run, east_asia=body_font, size=DOCX_BODY_FONT_SIZE)
            apply_list_paragraph_format(p)
        
        # 处理普通段落
        elif line:
            # 移除加粗标记
            text = clean_formal_bid_text(re.sub(r'\*\*(.*?)\*\*', r'\1', line))
            bracket_heading = _formal_bracket_heading(text)
            caption_text = _formal_image_caption_text(text)
            if caption_text:
                _add_formal_image_caption(doc, caption_text, template_profile=template_profile)
                image_report["captions"]["detected"] += 1
                image_report["captions"]["formalized"] += 1
                if len(image_report["captions"]["samples"]) < 8:
                    image_report["captions"]["samples"].append({
                        "source": text[:160],
                        "caption": caption_text[:160],
                    })
            elif bracket_heading:
                previous_form_type = current_form_type
                current_form_type, heading_text = bracket_heading
                detected_types = image_report["formal_forms"]["detected_types"]
                if current_form_type not in detected_types:
                    detected_types.append(current_form_type)
                if previous_form_type and previous_form_type != current_form_type:
                    doc.add_page_break()
                    image_report["formal_forms"]["subheading_page_breaks"] += 1
                _add_formal_subheading(doc, heading_text, template_profile=template_profile)
                image_report["formal_forms"]["subheadings"] += 1
            elif current_form_type and FORMAL_SIGNATURE_LINE_RE.match(text):
                _add_formal_signature_paragraph(doc, text, template_profile=template_profile)
                image_report["formal_forms"]["signature_lines"] += 1
            else:
                p = doc.add_paragraph()
                run = p.add_run(text)
                apply_run_font(run, east_asia=body_font, size=DOCX_BODY_FONT_SIZE)
                apply_paragraph_format(p)
        
        i += 1
    
    # 保存文档：目标文件名与 md 同名（.docx），先写入临时文件再替换，遇到被占用时退化为带唯一后缀的文件
    parent = Path(md_file).parent
    parent.mkdir(parents=True, exist_ok=True)
    output_file = Path(md_file).with_suffix('.docx')
    remove_black_square_paragraph_markers(doc)

    temp_path = None
    try:
        tf = tempfile.NamedTemporaryFile(dir=str(parent), suffix='.docx', delete=False)
        temp_path = Path(tf.name)
        tf.close()

        # 保存到临时文件
        doc.save(str(temp_path))

        # 尝试原子替换目标文件
        try:
            os.replace(str(temp_path), str(output_file))
            saved_path = output_file
        except PermissionError:
            # 目标被占用（常见于 Windows），改为生成带唯一后缀的备份文件
            alt_name = parent / f"{output_file.stem}_{uuid.uuid4().hex}.docx"
            shutil.move(str(temp_path), str(alt_name))
            saved_path = alt_name
            logging.warning("目标文件被占用，已生成备用文件: %s", saved_path)

        logging.info("已生成 Word 文档: %s", saved_path)
        image_report["marker_cleanup"] = scrub_docx_black_square_markers(saved_path)
        image_report["field_font_normalization"] = normalize_docx_field_result_fonts(saved_path)
        if return_report:
            image_report["template"] = docx_template_report(cover_fields=resolved_cover_fields)
            return Path(saved_path), image_report
        return Path(saved_path)
    finally:
        for image_path, cleanup in set(image_cache.values()):
            if cleanup and image_path and os.path.exists(image_path):
                try:
                    os.unlink(image_path)
                except Exception:
                    pass
        # 清理残留临时文件（如果存在）
        try:
            if temp_path and temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(convert_md_to_word(sys.argv[1]))
    else:
        print("请传入md文件路径，例如：python md_to_word.py data/output/项目名/项目名_完整投标文件.md")

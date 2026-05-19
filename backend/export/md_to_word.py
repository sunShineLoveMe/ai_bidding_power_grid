from pathlib import Path
import logging
import markdown
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
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
from urllib.parse import parse_qs, urlparse, unquote

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
DOCX_TOC_MAX_LEVEL = int(os.getenv("DOCX_TOC_MAX_LEVEL", "4"))


def clean_formal_bid_text(text):
    """Remove emoji/decorative symbols that are unsuitable for formal bid DOCX output."""
    if text is None:
        return ""
    cleaned = FORMAL_BID_GENERATION_NOTE_RE.sub("", str(text))
    cleaned = FORMAL_TEXT_CONTROL_RE.sub("", cleaned)
    cleaned = FORMAL_TEXT_SYMBOL_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def should_start_heading_on_new_page(level: int, text: str, heading_count: int) -> bool:
    """Formal bid exports should start major volumes/chapters on a fresh page."""
    if heading_count <= 0:
        return False
    clean_text = clean_formal_bid_text(text)
    if level == 1:
        return True
    if level == 2 and FORMAL_VOLUME_HEADING_RE.match(clean_text):
        return True
    return False


def apply_run_font(run, *, east_asia='宋体', latin='Times New Roman', size=None, bold=None):
    run.font.name = latin
    run._element.rPr.rFonts.set(qn('w:eastAsia'), east_asia)
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


def apply_paragraph_format(paragraph, *, first_line_chars=2, line_spacing=28, space_before=0, space_after=0):
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(first_line_chars * 12)
    fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    fmt.line_spacing = Pt(line_spacing)
    fmt.space_before = Pt(space_before)
    fmt.space_after = Pt(space_after)


def apply_image_paragraph_format(paragraph):
    """Prevent formal fixed body line spacing from clipping inline images in Word."""
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(0)
    fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
    fmt.line_spacing = 1.0
    fmt.space_before = Pt(6)
    fmt.space_after = Pt(6)


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
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1F4E79")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(color)
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


def _add_pageref_field(paragraph, bookmark_name: str, *, placeholder: str = "1") -> None:
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
    apply_run_font(result, east_asia="宋体", size=12)

    end = paragraph.add_run()
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    end._r.append(fld_end)


def _toc_entry_text(entry: dict) -> str:
    return clean_formal_bid_text(entry.get("text") or "").strip()


def _add_formal_toc_entry(doc, entry: dict, *, tab_position_twips: int) -> None:
    level = max(1, min(int(entry.get("level") or 1), DOCX_TOC_MAX_LEVEL))
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(0)
    fmt.left_indent = Pt((level - 1) * 18)
    fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    fmt.line_spacing = Pt(22)
    fmt.space_after = Pt(2)
    _set_paragraph_right_dot_leader_tab(paragraph, position_twips=tab_position_twips)

    text_run = paragraph.add_run(_toc_entry_text(entry))
    apply_run_font(text_run, east_asia="宋体", size=12, bold=(level == 1))
    paragraph.add_run("\t")
    _add_pageref_field(paragraph, str(entry.get("anchor") or ""), placeholder="1")


def _add_toc_page(doc, project_name: str, heading_entries: list[dict]) -> None:
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.first_line_indent = Pt(0)
    title.paragraph_format.space_after = Pt(16)
    title_run = title.add_run(project_name)
    apply_run_font(title_run, east_asia="黑体", size=20, bold=True)

    toc_title = doc.add_paragraph()
    toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    toc_title.paragraph_format.first_line_indent = Pt(0)
    toc_title.paragraph_format.space_after = Pt(14)
    toc_run = toc_title.add_run("目录")
    apply_run_font(toc_run, east_asia="黑体", size=16, bold=True)

    formal_entries = [
        entry for entry in heading_entries
        if 1 <= int(entry.get("level") or 1) <= DOCX_TOC_MAX_LEVEL and _toc_entry_text(entry)
    ]
    if not formal_entries:
        empty = doc.add_paragraph()
        empty.paragraph_format.first_line_indent = Pt(0)
        empty_run = empty.add_run("暂无章节目录，请先生成章节大纲。")
        apply_run_font(empty_run, east_asia="仿宋", size=12)
    tab_position_twips = _page_text_width_twips(doc)
    for entry in formal_entries:
        _add_formal_toc_entry(doc, entry, tab_position_twips=tab_position_twips)

    doc.add_page_break()


def convert_mermaid_to_image(mermaid_code):
    """将 Mermaid 代码转换为图片"""
    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix='.mmd', delete=False, mode='w', encoding='utf-8') as f:
        # 添加主题和样式设置
        mermaid_config = """
%%{init: {'theme': 'default', 'themeVariables': { 'fontSize': '16px', 'fontFamily': '宋体' }}}%%
"""
        f.write(mermaid_config + mermaid_code)
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
    except subprocess.CalledProcessError:
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
            "fontFamily": "宋体",
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
        try:
            # 添加图片到文档
            doc.add_picture(png_file, width=Inches(6))  # 先插入图片
            
            # 设置图片居中
            last_paragraph = doc.paragraphs[-1]
            last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            apply_image_paragraph_format(last_paragraph)
            
            # 添加图片说明（可选）
            caption = doc.add_paragraph()
            caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
            caption_run = caption.add_run("图 X-X 流程图")
            caption_run.font.name = '宋体'
            caption_run.font.size = Pt(10.5)
        finally:
            # 清理临时图片文件
            os.unlink(png_file)


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
    clean_alt = clean_formal_bid_text(alt_text) or "未命名图片"
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
        doc.add_picture(prepared_path, width=Inches(5.8))
        image_para = doc.paragraphs[-1]
        image_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        apply_image_paragraph_format(image_para)

        _append_image_report(image_report, {
            "status": "inserted",
            "alt": clean_alt,
            "ref": image_ref,
            "source_path": str(image_path),
            "prepared": bool(prepared_cleanup),
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
        if prepared_cleanup and prepared_path and os.path.exists(prepared_path):
            os.unlink(prepared_path)

def set_document_styles(doc):
    """设置文档样式"""
    styles = doc.styles
    normal = styles['Normal']
    normal.font.name = 'Times New Roman'
    normal._element.rPr.rFonts.set(qn('w:eastAsia'), '仿宋')
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    normal.paragraph_format.line_spacing = Pt(28)
    normal.paragraph_format.first_line_indent = Pt(24)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)

    heading_specs = {
        1: ('黑体', 18, True),
        2: ('黑体', 16, True),
        3: ('黑体', 15, True),
        4: ('黑体', 12, True),
    }
    for i in range(1, 5):
        style = styles[f'Heading {i}']
        east_asia, size, bold = heading_specs[i]
        style.font.name = 'Times New Roman'
        style._element.rPr.rFonts.set(qn('w:eastAsia'), east_asia)
        style.font.size = Pt(size)
        style.font.bold = bold
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        style.paragraph_format.line_spacing = Pt(28)
        style.paragraph_format.first_line_indent = Pt(0)
        style.paragraph_format.space_before = Pt(8 if i <= 2 else 4)
        style.paragraph_format.space_after = Pt(6 if i <= 2 else 4)

    for style_name in ['List Bullet', 'List Number']:
        style = styles[style_name]
        style.font.name = 'Times New Roman'
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '仿宋')
        style.font.size = Pt(12)
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        style.paragraph_format.line_spacing = Pt(28)

def _set_rpr_language(rpr):
    lang = rpr.find(qn('w:lang'))
    if lang is None:
        lang = OxmlElement('w:lang')
        rpr.append(lang)
    lang.set(qn('w:val'), 'zh-CN')
    lang.set(qn('w:eastAsia'), 'zh-CN')
    lang.set(qn('w:bidi'), 'zh-CN')

def set_document_language(doc):
    """设置 DOCX 默认校对语言为简体中文，避免 ONLYOFFICE 状态栏显示 English - United States。"""
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
    _set_rpr_language(rpr)

    for style in doc.styles:
        if style.type in {WD_STYLE_TYPE.PARAGRAPH, WD_STYLE_TYPE.CHARACTER, WD_STYLE_TYPE.TABLE}:
            rpr = style._element.get_or_add_rPr()
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

def set_document_format(doc, project_name):
    """设置文档格式"""
    project_name = clean_formal_bid_text(project_name) or "投标文件"
    # 设置页面边距
    sections = doc.sections
    for section in sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(3.18)
        section.right_margin = Cm(3.18)
        section.header_distance = Cm(1.5)
        section.footer_distance = Cm(1.75)
        
        # 添加页眉
        header = section.header
        header_para = header.paragraphs[0]
        header_para.text = f"{project_name}投标文件"
        header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in header_para.runs:
            apply_run_font(run, east_asia='宋体', size=9)
        
        # 添加页脚
        footer = section.footer
        footer_para = footer.paragraphs[0]
        footer_para.text = "第 "
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
        footer_para.add_run(" 页，共 ")
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
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in footer_para.runs:
            apply_run_font(run, east_asia='宋体', size=9)

def process_table(md_table, doc):
    """处理 Markdown 表格"""
    lines = md_table.strip().split('\n')
    if len(lines) < 3:  # 至少需要表头、分隔行和一行数据
        return
    
    # 计算列数
    header_cells = lines[0].strip('|').split('|')
    col_count = len(header_cells)
    
    # 创建表格
    table = doc.add_table(rows=1, cols=col_count)
    table.style = 'Table Grid'
    
    # 添加表头
    header_row = table.rows[0]
    for i, cell in enumerate(header_cells):
        header_row.cells[i].text = clean_formal_bid_text(cell)
        header_row.cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        # 设置表头格式
        for paragraph in header_row.cells[i].paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.bold = True
                apply_run_font(run, east_asia='黑体', size=10.5, bold=True)
    
    # 添加数据行
    for line in lines[2:]:  # 跳过表头和分隔行
        cells = line.strip('|').split('|')
        if len(cells) == col_count:
            row = table.add_row()
            for i, cell in enumerate(cells):
                row.cells[i].text = clean_formal_bid_text(cell)
                row.cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                # 设置单元格格式
                for paragraph in row.cells[i].paragraphs:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in paragraph.runs:
                        apply_run_font(run, east_asia='仿宋', size=10.5)


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
        report["reason"] = "DOCX_REFRESH_FIELDS is disabled"
        return source, report
    if not source.exists():
        report["status"] = "failed"
        report["reason"] = "DOCX file does not exist"
        return source, report

    soffice_bin = _soffice_bin()
    report["soffice_bin"] = soffice_bin
    if not soffice_bin:
        report["reason"] = "soffice executable not found"
        return source, report

    timeout = int(os.getenv("DOCX_REFRESH_TIMEOUT_SECONDS", "180"))
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
            "--nologo",
            "--nofirststartwizard",
            "-env:UserInstallation=" + profile_dir.as_uri(),
            "--convert-to",
            "docx",
            "--outdir",
            str(output_dir),
            str(temp_input),
        ]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except Exception as exc:
            logging.exception("LibreOffice 刷新 DOCX 字段失败: %s", source)
            report.update({
                "status": "failed",
                "reason": str(exc),
            })
            return source, report

        report.update({
            "returncode": completed.returncode,
            "stdout": (completed.stdout or "")[-2000:],
            "stderr": (completed.stderr or "")[-2000:],
        })
        refreshed = output_dir / source.name
        if completed.returncode != 0 or not refreshed.exists() or refreshed.stat().st_size == 0:
            report.update({
                "status": "failed",
                "reason": "LibreOffice did not produce refreshed DOCX",
            })
            logging.warning("LibreOffice 未生成刷新后的 DOCX: %s report=%s", source, report)
            return source, report

        temp_refreshed = source.with_name(f".{source.stem}.refreshed-{uuid.uuid4().hex}.docx")
        shutil.copy2(refreshed, temp_refreshed)
        os.replace(str(temp_refreshed), str(source))
        report.update({
            "status": "refreshed",
            "output_path": str(source),
            "size": source.stat().st_size,
        })
        logging.info("LibreOffice 已刷新 DOCX 字段: %s", source)
        return source, report


def convert_md_to_word(md_file, return_report: bool = False):
    """将Markdown文件转换为Word文档"""
    # 读取Markdown文件
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = clean_formal_bid_text(f.read())
    
    # 创建Word文档
    doc = Document()
    set_document_styles(doc)
    set_document_language(doc)
    
    # 设置文档格式
    title_match = re.search(r'^\s*#\s+(.+?)\s*$', md_content, re.MULTILINE)
    project_name = clean_formal_bid_text(title_match.group(1).strip()) if title_match else Path(md_file).stem
    set_document_format(doc, project_name)
    title_line_index, heading_entries = _markdown_heading_lines(md_content)
    heading_entry_by_line = {entry["line_index"]: entry for entry in heading_entries}
    _add_toc_page(doc, project_name, heading_entries)
    
    # 处理Markdown内容
    lines = md_content.split('\n')
    i = 0
    image_cache = {}
    inserted_image_count = 0
    image_report = {
        "max_images": MARKDOWN_IMAGE_MAX_COUNT,
        "found": 0,
        "inserted": 0,
        "skipped": 0,
        "failed": 0,
        "events": [],
    }
    heading_count = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', line):
            i += 1
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
            process_table('\n'.join(table_lines), doc)
            continue
        
        # 处理标题
        if line.startswith('#'):
            if title_line_index is not None and i == title_line_index:
                i += 1
                continue
            level = len(re.match(r'^#+', line).group())
            # 移除标题中的加粗标记
            text = clean_formal_bid_text(re.sub(r'\*\*(.*?)\*\*', r'\1', line.lstrip('#').strip()))
            if should_start_heading_on_new_page(level, text, heading_count):
                doc.add_page_break()
            word_heading_level = min(level, 4)
            p = doc.add_heading(text, level=word_heading_level)
            if level == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in p.runs:
                    apply_run_font(run, east_asia='黑体', size=18, bold=True)
            elif level == 2:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in p.runs:
                    apply_run_font(run, east_asia='黑体', size=16, bold=True)
            elif level == 3:
                for run in p.runs:
                    apply_run_font(run, east_asia='黑体', size=15, bold=True)
            else:
                for run in p.runs:
                    apply_run_font(run, east_asia='黑体', size=12, bold=True)
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
            apply_run_font(run, east_asia='仿宋', size=12)
            apply_paragraph_format(p, first_line_chars=0)
        
        # 处理数字列表
        elif re.match(r'^\d+\.', line):
            # 移除数字和点
            text = re.sub(r'^\d+\.', '', line).strip()
            # 移除加粗标记
            text = clean_formal_bid_text(re.sub(r'\*\*(.*?)\*\*', r'\1', text))
            p = doc.add_paragraph(style='List Number')
            run = p.add_run(text)
            apply_run_font(run, east_asia='仿宋', size=12)
            apply_paragraph_format(p, first_line_chars=0)
        
        # 处理普通段落
        elif line:
            # 移除加粗标记
            text = clean_formal_bid_text(re.sub(r'\*\*(.*?)\*\*', r'\1', line))
            p = doc.add_paragraph()
            run = p.add_run(text)
            apply_run_font(run, east_asia='仿宋', size=12)
            apply_paragraph_format(p)
        
        i += 1
    
    # 保存文档：目标文件名与 md 同名（.docx），先写入临时文件再替换，遇到被占用时退化为带唯一后缀的文件
    parent = Path(md_file).parent
    parent.mkdir(parents=True, exist_ok=True)
    output_file = Path(md_file).with_suffix('.docx')

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
        if return_report:
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

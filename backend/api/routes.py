import logging
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
import os
import uuid
import json
import jwt
import requests
from datetime import datetime
from pathlib import Path
import mammoth
from unidecode import unidecode
import re
from werkzeug.utils import secure_filename
import codecs
import PyPDF2
from urllib.parse import quote
from backend.ai.qwen_client import call_dashscope_api, generate_bid_section
from backend.export.md_to_word import DOCX_BIDDER_FULL_NAME, clean_formal_bid_text, convert_md_to_word, resolve_docx_template_profile, taichang_bid_document_title
from backend.ai.chapter_planner import generate_bid_outline, stream_bid_outline
from backend.ai.section_writer import estimate_bid_content_words, stream_bid_section
from backend.ai.interpreter import generate_ai_interpretation_report
from backend.ai.compliance_checker import build_compliance_report
from backend.ai.semantic_compliance import build_semantic_compliance_report
from backend.db.supabase_repo import cancel_bid_generation_task, create_bid_export_task, create_bid_generation_task, create_knowledge_asset, delete_bid_project, delete_bid_section, download_bid_file_to_local, download_knowledge_asset_file_variant, get_ai_usage_overview, get_bid_export_task, get_bid_file, get_latest_bid_file_for_project, get_latest_bid_generation_task, get_onlyoffice_document, get_project_interpretation, list_bid_history, list_bid_sections, list_knowledge_assets, list_recent_bid_projects, reorder_bid_sections, reset_bid_sections_generation, save_onlyoffice_document, sync_uploaded_tender_to_supabase, update_bid_analysis_project_meta, update_bid_export_task, update_bid_file_parse_status, update_bid_generation_task_item, update_bid_section_content, update_knowledge_asset, upload_knowledge_asset_file, upsert_bid_section
from backend.core.llm_json_utils import strip_llm_json
from backend.core.bid_volumes import asset_applicable_volumes, asset_matches_volume, delivery_volume_file_type, delivery_volume_type, normalize_volume_list, section_volume_type, volume_name
from backend.ai.length_settings import apply_length_allocations_to_sections, allocate_chapter_length_targets, evaluate_length_feasibility, normalize_length_settings
import threading
import shutil
from datetime import timedelta
from backend.core.config import DEFAULT_SETTINGS, build_enterprise_context, get_setting, load_runtime_settings, save_runtime_settings
from backend.core.security import UploadValidationError, safe_upload_filename, validate_uploaded_file
from backend.services.bid_material_scope import filter_sections_by_material_scope, material_scope_from_context
from backend.services.formal_placeholders import apply_confirmed_values_to_export_text, count_formal_placeholders, finalize_confirmed_formal_export_text
from backend.services.bid_prefill import formal_required_confirmation_gaps
from backend.services.formal_asset_naming import caption_policy, formal_asset_caption, formal_asset_title
from backend.services.taichang_evidence_export import build_taichang_evidence_export_plan, evidence_pages_by_section

# 操作向量数据库的函数
from backend.parsing.document_parser import ingest_artifacts as ingest_mineru_artifacts_to_supabase, import_mineru_result_zip, parse_and_index_tender_file, read_parse_status, retry_mineru_result_download, write_parse_status

# 共享对象集中定义在 backend.api._shared，避免后续按业务域拆分子模块时出现多份副本。
# 下列导入保持 routes 命名空间中原有的符号可见（main.py / 单元测试依赖 routes.bp、
# routes.DOCX_VOLUME_IMAGE_LIMITS 等属性）。
from backend.api._shared import (
    APP_HOST,
    BACKEND_URL_FOR_DOCKER,
    DOCX_TOTAL_ASSET_IMAGE_LIMIT,
    DOCX_VOLUME_IMAGE_LIMITS,
    ONLYOFFICE_JWT_SECRET,
    _temp_store_lock,
    bp,
    knowledge_bp,
    temp_analysis_store,
)


def _onlyoffice_jwt_secret() -> str:
    secret = os.getenv('ONLYOFFICE_JWT_SECRET', '').strip() or ONLYOFFICE_JWT_SECRET
    if not secret:
        raise RuntimeError("ONLYOFFICE_JWT_SECRET 未配置，无法生成 ONLYOFFICE 编辑配置。")
    return secret

def _with_http_scheme(base_url):
    base_url = (base_url or '').strip().rstrip('/')
    if not base_url:
        return ''
    if base_url.startswith(('http://', 'https://')):
        return base_url
    return f'http://{base_url}'

def get_backend_public_base_url():
    """Return the backend URL reachable by the OnlyOffice document server."""
    return _with_http_scheme(
        os.getenv('APP_PUBLIC_BASE_URL')
        or os.getenv('BACKEND_URL_FOR_DOCKER')
        or BACKEND_URL_FOR_DOCKER
        or APP_HOST
    )

def get_backend_self_base_url():
    """Return the backend URL used by this service when it needs to fetch its own files."""
    return _with_http_scheme(
        os.getenv('APP_PUBLIC_BASE_URL')
        or os.getenv('APP_HOST')
        or APP_HOST
        or os.getenv('BACKEND_URL_FOR_DOCKER')
        or BACKEND_URL_FOR_DOCKER
    )

def get_db():
    """SQLite 已下线，业务数据统一使用 PostgreSQL。

    历史 legacy 路由仍引用本函数；保留显式报错以避免静默回退到本地 SQLite 文件，
    同时提示调用方该路径已废弃。
    """
    raise RuntimeError("SQLite 数据通道已下线，请使用 PostgreSQL 数据访问层（backend.db.supabase_repo）。")


# ---- settings / usage 路由已迁移至 backend/api/settings.py ----
# 路由注册通过 routes.py 末尾的 import 触发，此处不再重复定义。

def read_tender_file(bidding_id):
    """历史招标文件读取入口（基于已下线的 SQLite bidding 表）。

    新流程统一通过 PostgreSQL 项目与文件记录处理，此函数仅为兼容旧 legacy 路由保留。
    """
    raise RuntimeError("read_tender_file 依赖的 SQLite bidding 表已下线，请使用新的 PostgreSQL 文件流程。")

def _read_pdf(file_path):
    """读取PDF文件"""
    text = ""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return jsonify({'error': f'读取文件失败: {str(e)}'}), 500
    
def save_bid_section(content, section_name, output_dir, tender_name):
    '''保存投标文件小节'''
    output_path = Path(output_dir) / tender_name / f"{section_name}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
    except Exception as e:
            logging.error(f"保存章节 {section_name} 时出错: {e}")

def merge_sections(output_dir, tender_name, sections):
        """合并所有章节内容为一个完整的文档"""
        sections_dir = Path(output_dir) / tender_name
        if not sections_dir.exists():
            logging.error(f"目录 {sections_dir} 不存在！")
            return
        
        # 获取所有章节文件
        section_files = list(sections_dir.glob("*.txt"))
        if not section_files:
            logging.error(f"在 {sections_dir} 目录下未找到章节文件！")
            return
        
        # 创建合并后的文档
        merged_content = ["# 投标文件\n\n"] + [
            f"## {section_name}\n\n{content}\n\n"
            for section_name in sections
            if (section_file := sections_dir / f"{section_name}.txt").exists()
            for content in [section_file.read_text(encoding='utf-8')]
        ]
        output_file = sections_dir / f"{tender_name}_完整投标文件.md"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(merged_content))
            logging.info(f"已生成完整投标文件：{output_file}")
            return output_file
        except Exception as e:
            logging.error(f"保存合并文件时出错: {e}")
            return None    


def _slug_filename(name: str, fallback: str = "bid-document") -> str:
    base = secure_filename(unidecode(name or "").strip()) or fallback
    return base


def _display_filename(name: str, fallback: str = "投标文件") -> str:
    """Keep Chinese project names in user-facing generated document filenames."""
    value = clean_formal_bid_text(name or "") or fallback
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", value)
    value = re.sub(r"\s+", " ", value).strip(" ._-")
    return (value or fallback)[:120]


def _filename_token(value: object, fallback: str = "", *, max_chars: int = 28) -> str:
    text = clean_formal_bid_text(str(value or "")) or fallback
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text)
    text = re.sub(r"\s+", "", text).strip(" ._-")
    text = re.sub(r"（.*?）|\(.*?\)", "", text)
    return (text or fallback)[:max_chars]


def _first_cover_value(project: dict, project_meta: dict, cover_fields: dict, keys: list[str]) -> str:
    for key in keys:
        for source in (cover_fields, project_meta, project):
            value = source.get(key) if isinstance(source, dict) else None
            if value not in (None, ""):
                return str(value)
    return ""


def _export_download_stem(
    *,
    project_id: str,
    project: dict,
    project_meta: dict,
    cover_fields: dict,
    volume_type: str | None,
    focus_section: dict | None,
    with_images: bool,
) -> str:
    bidder = "泰昌"
    tender_no = _filename_token(
        _first_cover_value(project, project_meta, cover_fields, ["tender_no", "project_no", "招标编号", "项目编号"]),
        f"项目{project_id[:8]}",
        max_chars=24,
    )
    package_no = _filename_token(
        _first_cover_value(project, project_meta, cover_fields, ["package_no", "包号", "package_name", "包名称"]),
        "",
        max_chars=12,
    )
    if focus_section:
        file_type = _filename_token(focus_section.get("title") or "章节", "章节", max_chars=16)
    else:
        file_type = _filename_token(delivery_volume_file_type(volume_type), "投标文件", max_chars=10)
    date_token = datetime.now().strftime("%Y%m%d")
    parts = [bidder, tender_no]
    if package_no:
        parts.append(package_no)
    parts.extend([file_type, date_token])
    if with_images:
        parts.append("图文")
    stem = "_".join(part for part in parts if part)
    return _display_filename(stem, fallback=f"泰昌_投标文件_{date_token}")[:90]


def _output_url_for_path(path: Path) -> str:
    gen_folder = Path(current_app.config.get('GENERATED_FOLDER', 'outputs')).resolve()
    relative_path = Path(path).resolve().relative_to(gen_folder).as_posix()
    return f"/api/outputs/{quote(relative_path)}"


def _absolute_output_url_for_path(path: Path) -> str:
    return f"{get_backend_public_base_url()}{_output_url_for_path(path)}"


def _section_markdown_heading(level: int, title: str) -> str:
    depth = max(1, min(level, 6))
    return f'{"#" * depth} {title}\n\n'


def _clean_section_title(title: str, order: str | int | None = None) -> str:
    clean_title = (title or "未命名章节").strip()
    if not order:
        return clean_title
    order_text = str(order).strip()
    return re.sub(rf"^{re.escape(order_text)}\.?\s*", "", clean_title).strip() or clean_title


def _section_display_title(section: dict) -> str:
    order = section.get("order")
    title = _clean_section_title(section.get("title") or "未命名章节", order)
    if not order:
        return title
    order_text = str(order).strip()
    prefix = f"{order_text} " if "." in order_text else f"{order_text}. "
    return f"{prefix}{title}"


def _strip_existing_section_number(title: str) -> str:
    value = clean_formal_bid_text(title or "未命名章节").strip()
    value = re.sub(r"^\s*[（(][一二三四五六七八九十百]+[）)]\s*", "", value)
    value = re.sub(r"^\s*[（(]\d+[）)]\s*", "", value)
    value = re.sub(r"^\s*\d+[）)]\s*", "", value)
    value = re.sub(r"^\s*\d+(?:\.\d+)*(?:[\.、]\s*|\s+)", "", value)
    value = re.sub(r"^\s*[一二三四五六七八九十百]+[、.．]\s*", "", value)
    value = re.sub(r"^\s*第[一二三四五六七八九十百]+[章节篇部分][、:：.\s]*", "", value)
    return value.strip() or clean_formal_bid_text(title or "未命名章节").strip() or "未命名章节"


def _strip_repeated_parent_title_prefix(title: str) -> str:
    value = _strip_existing_section_number(title)
    if " - " not in value and "－" not in value:
        return value
    parts = re.split(r"\s*[-－]\s*", value, maxsplit=1)
    if len(parts) != 2:
        return value
    parent, child = [part.strip(" ：:、，,。") for part in parts]
    if parent and child and len(parent) >= 4 and len(child) <= 24:
        return child
    return value


def _chinese_ordinal(value: int) -> str:
    numerals = "零一二三四五六七八九"
    if value <= 0:
        return str(value)
    if value < 10:
        return numerals[value]
    if value == 10:
        return "十"
    if value < 20:
        return f"十{numerals[value % 10]}"
    if value < 100:
        tens, ones = divmod(value, 10)
        return f"{numerals[tens]}十{numerals[ones] if ones else ''}"
    return str(value)


def _export_order_for_style(counters: list[int], level: int, numbering_style: str) -> str:
    if numbering_style != "sgcc_mixed":
        return ".".join(str(value) for value in counters)
    if level == 1:
        return str(counters[0])
    numeric_parts = counters[1:level]
    return ".".join(str(value) for value in numeric_parts) if numeric_parts else str(counters[0])


def _export_title_prefix_for_style(counters: list[int], level: int, numbering_style: str) -> str:
    if numbering_style != "sgcc_mixed":
        number = ".".join(str(value) for value in counters)
        return f"{number}. " if "." not in number else f"{number} "
    if level == 1:
        return f"（{_chinese_ordinal(counters[0])}）"
    if level == 5:
        return f"{counters[4]}） "
    numeric_parts = counters[1:level]
    number = ".".join(str(value) for value in numeric_parts) if numeric_parts else str(counters[0])
    return f"{number}. " if level == 2 else f"{number} "


def _numbered_export_sections(sections: list[dict], numbering_style: str = "decimal_outline") -> list[dict]:
    raw_levels = [max(1, min(int(section.get("level") or 1), 6)) for section in sections]
    counters: list[int] = []
    numbered: list[dict] = []
    raw_stack: list[int] = []
    for section, raw_level in zip(sections, raw_levels):
        # 真实大纲偶尔会出现从二级开始或从一级直接跳到三级的脏层级。
        # 用 raw level 栈按上下文压平，避免 0.1 / 18.0.1，也避免把后续子节误升成大章。
        if not raw_stack:
            level = 1
            raw_stack = [raw_level]
        elif raw_level > raw_stack[-1]:
            level = min(len(raw_stack) + 1, 6)
            raw_stack.append(raw_level)
        else:
            while raw_stack and raw_level < raw_stack[-1]:
                raw_stack.pop()
            if raw_stack and raw_level == raw_stack[-1]:
                level = len(raw_stack)
            else:
                level = 1 if not raw_stack else min(len(raw_stack) + 1, 6)
                raw_stack.append(raw_level)
        level = max(1, min(level, 6))
        while len(counters) < level:
            counters.append(0)
        counters = counters[:level]
        counters[level - 1] += 1
        number = _export_order_for_style(counters, level, numbering_style)
        raw_title = _strip_existing_section_number(section.get("title") or "未命名章节")
        clean_title = _strip_repeated_parent_title_prefix(raw_title) if level > 1 else raw_title
        title_prefix = _export_title_prefix_for_style(counters, level, numbering_style)
        numbered.append({
            **section,
            "_export_original_level": raw_level,
            "level": level,
            "_export_order": number,
            "_export_numbering_style": numbering_style,
            "_export_title": f"{title_prefix}{clean_title}",
        })
    return numbered


def _strip_duplicate_section_heading(content: str, section: dict) -> str:
    lines = (content or "").strip().splitlines()
    if not lines:
        return ""
    first = lines[0].strip()
    if not first.startswith("#"):
        return content.strip()
    heading_text = re.sub(r"^#{1,6}\s*", "", first).strip()
    order = section.get("order")
    clean_heading = _clean_section_title(heading_text, order)
    clean_title = _clean_section_title(section.get("title") or "未命名章节", order)
    if (
        clean_heading == clean_title
        or _strip_existing_section_number(clean_heading) == _strip_existing_section_number(clean_title)
        or heading_text == _section_display_title(section)
    ):
        return "\n".join(lines[1:]).strip()
    return content.strip()


def _strip_redundant_section_label(content: str, section: dict) -> str:
    if not content:
        return ""
    raw_title = _strip_existing_section_number(section.get("title") or "")
    export_title = _strip_existing_section_number(section.get("_export_title") or "")
    candidates = {
        clean_formal_bid_text(raw_title).strip(),
        clean_formal_bid_text(export_title).strip(),
        _strip_repeated_parent_title_prefix(raw_title),
        _strip_repeated_parent_title_prefix(export_title),
    }
    candidates = {candidate for candidate in candidates if candidate}
    output: list[str] = []
    removed = False
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        label = stripped.strip("【】[]（）()# ：:、，,。")
        label = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", label)
        label = _strip_existing_section_number(label)
        if not removed and label in candidates:
            removed = True
            continue
        output.append(raw_line)
    return "\n".join(output).strip()


BODY_SUBHEADING_COMMENT_PREFIX = "BID_BODY_SUBHEADING:"
BODY_SUBHEADING_COMMENT_RE = re.compile(r"^<!--\s*BID_BODY_SUBHEADING:\s*(.+?)\s*-->\s*$")
EXPORT_GUIDANCE_LABELS = {
    "编写要点",
    "需准备资料",
    "风险与复核",
    "投标确认清单",
    "投标确认清单：",
}
GENERIC_BODY_OUTLINE_HEADINGS = {
    "商务文件",
    "技术文件",
    "投标文件",
    "商务响应文件",
    "技术响应文件",
    "商务投标文件",
    "技术投标文件",
    "商务分册",
    "技术分册",
}


def _normalize_export_guidance_label(text: str) -> str:
    label = re.sub(r"<!--\s*BID_BODY_SUBHEADING:\s*(.*?)\s*-->", r"\1", text or "").strip()
    label = re.sub(r"\*\*(.*?)\*\*", r"\1", label).strip()
    label = label.strip("【】[]（）()# ：:、，,。")
    label = _strip_existing_section_number(label)
    label = re.sub(r"^\d+(?:[.．]\d+)*\s*", "", label).strip(" ：:、，,。")
    return label


def _body_subheading_comment(title: str) -> str:
    clean_title = clean_formal_bid_text(title or "").replace("--", " ").strip(" ：:、，,。")
    clean_title = clean_title.replace("【", "").replace("】", "").strip(" ：:、，,。")
    return f"<!-- {BODY_SUBHEADING_COMMENT_PREFIX} {clean_title} -->" if clean_title else ""


def _strip_export_guidance_blocks(content: str) -> str:
    if not content:
        return ""
    output: list[str] = []
    skip_next = 0
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        visible = re.sub(r"\*\*(.*?)\*\*", r"\1", stripped).strip()
        visible = visible.strip("【】[]（）() ：:、，,。")
        normalized_visible = _normalize_export_guidance_label(visible)
        if skip_next > 0 and (
            stripped.startswith(("#", "<!--"))
            or BODY_SUBHEADING_COMMENT_PREFIX in stripped
        ):
            skip_next = 0
        if skip_next > 0:
            if (
                not stripped
                or stripped.startswith(("（需", "需人工", "暂无明确风险", "以下信息需", "1. 产品实测参数"))
                or stripped.startswith(("以下信息已", "为完善本节内容", "为确保本节内容"))
                or re.match(r"^[-*+]\s+", stripped)
                or re.match(r"^\d+[\.、]\s+", stripped)
            ):
                continue
            skip_next = 0
        bracket_match = re.match(r"^【\s*(.+?)\s*】$", stripped)
        label = bracket_match.group(1).strip() if bracket_match else ""
        normalized_label = _normalize_export_guidance_label(label)
        if (
            normalized_label in EXPORT_GUIDANCE_LABELS
            or normalized_visible in EXPORT_GUIDANCE_LABELS
            or "投标确认清单" in normalized_visible
            or normalized_visible == "已确认事项清单"
        ):
            skip_next = 99
            continue
        output.append(raw_line)
    return "\n".join(output).strip()


def _sanitize_export_visible_markup(content: str) -> str:
    if not content:
        return ""
    output: list[str] = []
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if BODY_SUBHEADING_COMMENT_PREFIX in stripped:
            output.append(raw_line.replace("【", "").replace("】", ""))
            continue
        visible = re.sub(r"\*\*(.*?)\*\*", r"\1", stripped).strip()
        visible_no_brackets = visible.strip("【】[]（）() ：:、，,。")
        if visible_no_brackets.startswith(("插入：", "图：", "建议附图：")):
            continue
        line = raw_line
        line = re.sub(r"【\s*(已确认|已完成|待确认|需确认)\s*】", "", line)
        line = re.sub(r"\*\*（建议附图：.*?）\*\*", "", line)
        line = re.sub(r"（建议附图：.*?）", "", line)
        line = line.replace("【", "").replace("】", "")
        output.append(line)
    return "\n".join(output).strip()


def _renumber_body_markdown_headings(content: str, section: dict) -> str:
    """Rewrite model-emitted body heading numbers under the official export section number."""
    if not content:
        return ""
    base_order = str(section.get("_export_order") or section.get("order") or "").strip()
    if not base_order:
        return content.strip()

    section_title = _strip_existing_section_number(section.get("title") or section.get("_export_title") or "")

    def heading_number_depth(value: str) -> int | None:
        match = re.match(r"^(\d+(?:\.\d+)*)[\.、]?\s+", (value or "").strip())
        if not match:
            return None
        return len([part for part in match.group(1).split(".") if part])

    def should_skip_body_heading(clean_title: str) -> bool:
        if not clean_title:
            return False
        if section_title and clean_title == section_title:
            return True
        return clean_title in {"商务文件", "技术文件", "投标文件", "商务响应文件", "技术响应文件"}

    heading_levels: list[int] = []
    explicit_depths: list[int] = []
    scan_in_fence = False
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            scan_in_fence = not scan_in_fence
            continue
        if scan_in_fence:
            continue
        heading_match = re.match(r"^(\s{0,3})(#{1,6})\s+(.+?)\s*#*\s*$", raw_line)
        if not heading_match:
            continue
        _, marks, title_text = heading_match.groups()
        clean_title = clean_formal_bid_text(re.sub(r"\*\*(.*?)\*\*", r"\1", title_text)).strip()
        clean_title = _strip_existing_section_number(clean_title)
        if should_skip_body_heading(clean_title):
            continue
        heading_levels.append(max(1, min(len(marks), 6)))
        explicit_depth = heading_number_depth(title_text)
        if explicit_depth:
            explicit_depths.append(explicit_depth)
    min_heading_level = min(heading_levels) if heading_levels else 1
    min_explicit_depth = min(explicit_depths) if explicit_depths else None

    output: list[str] = []
    counters: list[int] = []
    in_fence = False
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            output.append(raw_line)
            continue
        if in_fence:
            output.append(raw_line)
            continue

        heading_match = re.match(r"^(\s{0,3})(#{1,6})\s+(.+?)\s*#*\s*$", raw_line)
        if not heading_match:
            output.append(raw_line)
            continue

        prefix, marks, title_text = heading_match.groups()
        clean_title = clean_formal_bid_text(re.sub(r"\*\*(.*?)\*\*", r"\1", title_text)).strip()
        clean_title = _strip_existing_section_number(clean_title)
        if should_skip_body_heading(clean_title):
            continue
        explicit_depth = heading_number_depth(title_text)
        relative_depth = (
            explicit_depth - (min_explicit_depth or explicit_depth) + 1
            if explicit_depth
            else len(marks) - min_heading_level + 1
        )
        relative_depth = max(1, min(relative_depth, 4))
        while len(counters) < relative_depth:
            counters.append(0)
        counters = counters[:relative_depth]
        for index in range(relative_depth - 1):
            if counters[index] == 0:
                counters[index] = 1
        counters[relative_depth - 1] += 1
        next_order = ".".join([base_order, *[str(value) for value in counters]])
        output.append(f"{prefix}{marks} {next_order} {clean_title}")

    return "\n".join(output).strip()


def _demote_body_markdown_headings(content: str) -> str:
    """Keep DOCX navigation tied to bid_sections, not headings emitted inside body text."""
    lines = (content or "").splitlines()
    if not lines:
        return ""

    output: list[str] = []
    in_fence = False
    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            output.append(raw_line)
            continue
        if in_fence:
            output.append(raw_line)
            continue

        heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", raw_line)
        if heading_match:
            title = clean_formal_bid_text(re.sub(r"\*\*(.*?)\*\*", r"\1", heading_match.group(1))).strip()
            if title:
                output.append(_body_subheading_comment(title))
            continue

        next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if stripped and re.match(r"^(=+|-+)$", next_line):
            output.append(_body_subheading_comment(stripped))
            continue
        if re.match(r"^(=+|-+)$", stripped) and output and BODY_SUBHEADING_COMMENT_PREFIX in output[-1]:
            continue
        output.append(raw_line)

    return "\n".join(output).strip()


def _extract_body_heading_candidate(stripped: str) -> tuple[str, int | None, bool] | None:
    if not stripped:
        return None
    comment_match = BODY_SUBHEADING_COMMENT_RE.match(stripped)
    from_comment = bool(comment_match)
    if comment_match:
        stripped = comment_match.group(1).strip()
    elif stripped.startswith("<!--"):
        return None
    stripped = re.sub(r"\*\*(.*?)\*\*", r"\1", stripped).strip()
    bracket_match = re.match(r"^【\s*(.+?)\s*】$", stripped)
    heading = bracket_match.group(1).strip() if bracket_match else stripped
    if not heading or len(heading) > 48:
        return None
    if heading.strip(" ：:、，,。") in EXPORT_GUIDANCE_LABELS:
        return None
    numeric_match = re.match(r"^(\d+(?:\.\d+)*)(?:[\.、])?\s+(.+?)\s*$", heading)
    if numeric_match:
        body = numeric_match.group(2).strip().strip("【】[]（）() ：:、，,。")
        if "：" in body[:16] or ":" in body[:16] or body.endswith(("。", "；", ";")):
            return None
        return (body or _strip_existing_section_number(heading), len(numeric_match.group(1).split(".")), from_comment)
    chinese_match = re.match(r"^[一二三四五六七八九十百]+[、.．]\s*(.+?)\s*$", heading)
    if chinese_match:
        return (_strip_existing_section_number(heading), 1, from_comment)
    chapter_match = re.match(r"^第[一二三四五六七八九十百]+[章节篇部分]\s*(.+?)\s*$", heading)
    if chapter_match:
        clean = _strip_existing_section_number(heading)
        if clean in GENERIC_BODY_OUTLINE_HEADINGS:
            return None
        return (clean, 1, from_comment)
    if bracket_match and len(heading) <= 24 and not heading.endswith(("。", "；", ";")):
        return (_strip_existing_section_number(heading), None, from_comment)
    return None


def _normalize_body_outline_lines(content: str, section: dict) -> str:
    """Convert stale model/template body headings into clean non-TOC subheadings."""
    if not content:
        return ""
    base_order = str(section.get("_export_order") or section.get("order") or "").strip()
    if not base_order:
        return content.strip()
    section_title = _strip_existing_section_number(section.get("title") or section.get("_export_title") or "")

    def should_skip_body_heading(clean_title: str) -> bool:
        if not clean_title:
            return False
        if section_title and clean_title == section_title:
            return True
        return clean_title in GENERIC_BODY_OUTLINE_HEADINGS

    candidates: list[tuple[int, int | None]] = []
    in_fence = False
    lines = content.splitlines()
    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        candidate = _extract_body_heading_candidate(stripped)
        if candidate:
            clean_title, depth, _ = candidate
            if should_skip_body_heading(clean_title):
                continue
            candidates.append((index, depth))
    numeric_depths = [depth for _, depth in candidates if depth]
    min_numeric_depth = min(numeric_depths) if numeric_depths else None

    output: list[str] = []
    counters: list[int] = []
    in_fence = False
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            output.append(raw_line)
            continue
        if in_fence:
            output.append(raw_line)
            continue
        candidate = _extract_body_heading_candidate(stripped)
        if not candidate:
            output.append(raw_line)
            continue
        clean_title, explicit_depth, from_comment = candidate
        if should_skip_body_heading(clean_title):
            continue
        # 正式目录层级只来自 bid_sections。正文里的 Markdown 标题、加粗伪标题、
        # 旧模板编号和 `BID_BODY_SUBHEADING` 都只能作为当前章节下一级正文小标题，
        # 否则商务标/完整投标文件会叠出 2.10.1.1.2、6.1.2.1.1.1.1 等深层串号。
        relative_depth = 1
        while len(counters) < relative_depth:
            counters.append(0)
        counters = counters[:relative_depth]
        for index in range(relative_depth - 1):
            if counters[index] == 0:
                counters[index] = 1
        counters[relative_depth - 1] += 1
        next_order = ".".join([base_order, *[str(value) for value in counters]])
        output.append(_body_subheading_comment(f"{next_order} {clean_title}"))
    return "\n".join(output).strip()


def _full_export_should_use_sgcc_mixed_numbering(sections: list[dict]) -> bool:
    delivery_volumes = {delivery_volume_type(section) for section in sections}
    return {"business", "technical"}.issubset(delivery_volumes)


def _strip_untrusted_export_images(content: str, *, remove_all: bool = False) -> str:
    """Keep formal DOCX images tied to curated knowledge assets or real local files."""
    if not content:
        return ""

    def replace(match: re.Match) -> str:
        alt = clean_formal_bid_text(match.group(1) or "图片")
        ref = (match.group(2) or "").strip().strip('"').strip("'")
        if re.match(r"^/api/(?:bidding/)?knowledge/assets/[^/]+/file(?:\?|$)", ref):
            return match.group(0)
        candidate = Path(ref)
        if candidate.is_absolute() and candidate.exists() and candidate.is_file():
            return match.group(0)
        if remove_all:
            logging.info("导出 DOCX 时移除章节正文历史图片引用: alt=%s ref=%s", alt, ref)
            return "\n__EXPORT_IMAGE_REMOVED__\n"
        logging.warning("导出 DOCX 时移除未入库或不可解析图片引用: alt=%s ref=%s", alt, ref)
        return ""

    stripped = re.sub(r"!\[(.*?)\]\((.*?)\)", replace, content)
    if remove_all:
        output_lines: list[str] = []
        skip_legacy_caption = False
        for line in stripped.splitlines():
            if "__EXPORT_IMAGE_REMOVED__" in line:
                skip_legacy_caption = True
                continue
            if skip_legacy_caption and not line.strip():
                output_lines.append(line)
                continue
            if skip_legacy_caption and re.match(r"^\s*(?:资料|图\s*\d+(?:[.-]\d+)?|图片)[：:][^\n]{1,120}\s*$", line):
                skip_legacy_caption = False
                continue
            skip_legacy_caption = False
            output_lines.append(line)
        stripped = "\n".join(output_lines)
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


def _asset_text(asset: dict) -> str:
    parts = [
        asset.get("title"),
        asset.get("description"),
        asset.get("category"),
        asset.get("asset_type"),
        asset.get("searchable_text"),
    ]
    parts.extend(asset.get("tags") or [])
    parts.extend(asset.get("applicable_sections") or [])
    parts.extend(asset_applicable_volumes(asset))
    for container_name in ("metadata", "specs"):
        container = asset.get(container_name) or {}
        if isinstance(container, dict):
            for value in container.values():
                if isinstance(value, list):
                    parts.extend(str(item) for item in value if item)
                elif isinstance(value, (str, int, float, bool)):
                    parts.append(str(value))
    return " ".join(str(item) for item in parts if item).lower()


def _section_text(section: dict) -> str:
    metadata = section.get("metadata") or {}
    plan = metadata.get("writing_plan") or {}
    parts = [
        _section_display_title(section),
        section.get("title"),
        section.get("content"),
        section.get("purpose"),
        plan.get("chapter_type"),
        plan.get("importance"),
    ]
    for key in ("response_points", "required_materials", "evidence_needs", "mapped_requirements"):
        value = section.get(key) or plan.get(key)
        if isinstance(value, list):
            parts.extend(value)
        elif value:
            parts.append(value)
    return " ".join(str(item) for item in parts if item).lower()


def _section_heading_text(section: dict) -> str:
    return f"{_section_display_title(section)} {section.get('title') or ''}".lower()


def _section_planned_evidence_text(section: dict) -> str:
    metadata = section.get("metadata") or {}
    plan = metadata.get("writing_plan") if isinstance(metadata.get("writing_plan"), dict) else {}
    parts = [
        _section_heading_text(section),
        section.get("purpose"),
        plan.get("chapter_type"),
        plan.get("importance"),
    ]
    for key in ("response_points", "required_materials", "evidence_needs", "mapped_requirements"):
        value = section.get(key) or plan.get(key)
        if isinstance(value, list):
            parts.extend(value)
        elif value:
            parts.append(value)
    return " ".join(str(item) for item in parts if item).lower()


def _section_is_form_or_summary(section: dict) -> bool:
    title_text = _section_heading_text(section)
    raw_title = _strip_existing_section_number(section.get("title") or "").lower()
    if raw_title in {"认证证书", "资质证书", "证书附件", "证明材料"}:
        return True
    form_keywords = [
        "投标人基本情况表",
        "基本情况表",
        "商务偏差表",
        "技术偏差表",
        "技术特性参数表",
        "货物清单",
        "报价汇总表",
        "分项报价表",
        "明细表",
        "说明书",
        "响应文件",
        "支撑材料",
        "资料清单",
        "附件清单",
        "索引",
        "基本情况表",
        "商务偏差表",
        "投标保证保险",
        "保险购买凭证",
        "投标保证金",
        "银行基本账户",
    ]
    return any(keyword in title_text for keyword in form_keywords)


def _section_needs_image(section: dict) -> bool:
    metadata = section.get("metadata") or {}
    plan = metadata.get("writing_plan") or {}
    volume_type = section_volume_type(section)
    if volume_type == "price":
        return False
    title_text = _section_heading_text(section)
    if _section_is_form_or_summary(section):
        # 表格/说明/索引章节应以正文结构为主，不能靠宽泛关键词自动塞图。
        return False
    if volume_type == "business":
        explicit_business_evidence_titles = [
            "营业执照", "资质证书", "认证证书", "证书附件", "授权委托书",
            "法定代表人身份证明", "银行保函", "项目业绩证明", "合同协议书", "中标通知书",
        ]
        return any(keyword in title_text for keyword in explicit_business_evidence_titles) or (
            bool(plan.get("needs_image")) and any(keyword in _section_planned_evidence_text(section) for keyword in ["证书扫描件", "营业执照", "合同扫描件", "中标通知书", "银行保函"])
        )
    if plan.get("needs_image"):
        return True
    explicit_image_title_keywords = [
        "附件", "营业执照", "资质", "证书", "业绩", "合同", "中标通知书",
        "生产", "生产线", "制造", "检测", "试验", "设备", "绿色", "低碳", "碳足迹",
        "检验报告", "检测报告", "产品", "厂房", "仓储", "logo", "Logo",
    ]
    generic_titles = ["编制依据", "工程概况", "总体部署", "响应要求", "有效性说明", "条款响应", "承诺事项", "偏离说明"]
    if any(title == title_text.strip() or title in title_text for title in generic_titles):
        return False
    if int(section.get("level") or 1) <= 2 and not any(keyword in title_text for keyword in explicit_image_title_keywords):
        return False
    text = _section_text(section)
    keywords = [
        "资质", "证书", "营业执照", "许可", "业绩", "合同", "中标通知书", "产品", "设备", "材料", "施工",
        "输变电", "配网", "变电站", "线路", "电缆", "开关柜", "变压器", "箱变",
        "继电保护", "自动化", "调试", "试验", "运维", "检修", "组织实施", "工程范围",
    ]
    return any(keyword in text for keyword in keywords)


def _asset_meta_value(asset: dict, key: str) -> str:
    metadata = asset.get("metadata") or {}
    specs = asset.get("specs") or {}
    for container in (metadata, specs, asset):
        if isinstance(container, dict) and container.get(key) not in (None, ""):
            return str(container.get(key)).lower()
    return ""


def _asset_meta_bool(asset: dict, key: str, *, default: bool = False) -> bool:
    metadata = asset.get("metadata") or {}
    specs = asset.get("specs") or {}
    for container in (metadata, specs, asset):
        if not isinstance(container, dict) or container.get(key) in (None, ""):
            continue
        value = container.get(key)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y"}
    return default


def _section_asset_profile(section: dict) -> dict[str, set[str]]:
    heading_text = _section_heading_text(section)
    evidence_text = _section_planned_evidence_text(section)
    profile_text = f"{heading_text} {evidence_text}"
    profile = {"evidence_types": set(), "libraries": set()}
    if _section_is_form_or_summary(section):
        return profile
    if any(keyword in profile_text for keyword in ["营业执照", "执照"]):
        profile["evidence_types"].add("business_license")
        profile["libraries"].add("qualification_library")
    if any(keyword in profile_text for keyword in ["资信", "资质", "证书", "体系认证", "认证证书", "许可"]):
        profile["evidence_types"].add("certification")
        profile["libraries"].add("qualification_library")
    if any(keyword in profile_text for keyword in ["生产制造", "生产线", "产线", "车间", "厂房", "制造能力", "生产能力", "生产设备", "产品制造质量控制"]):
        profile["evidence_types"].add("production_capacity")
        profile["libraries"].add("product_library")
    if any(keyword in profile_text for keyword in ["试验检测", "检测能力", "试验能力", "检测设备", "试验设备", "质量检测", "电子天平", "万能试验机", "维卡", "锤击", "溶体流动"]):
        profile["evidence_types"].add("testing_capacity")
        profile["libraries"].add("product_library")
    if any(keyword in profile_text for keyword in ["设备", "产品图", "产品图片", "施工设备", "产品资料"]):
        profile["libraries"].add("product_library")
    if any(keyword in profile_text for keyword in ["证明材料", "承诺附件", "承诺函", "商务条款"]):
        profile["libraries"].add("qualification_library")
    if any(keyword in profile_text for keyword in ["绿色供应链", "绿电", "绿证", "绿色低碳", "低碳", "esg", "碳足迹", "废水废气", "环保"]):
        profile["evidence_types"].add("green_low_carbon")
    if any(keyword in profile_text for keyword in ["检验报告", "检测报告", "型式试验", "内径250"]):
        profile["evidence_types"].add("inspection_report")
        profile["libraries"].add("product_library")
    if any(keyword in heading_text for keyword in [
        "同类业绩",
        "类似业绩",
        "项目业绩",
        "业绩文件",
        "业绩证明",
        "新增业绩合同",
        "产品购销合同",
        "同类项目",
        "合同协议书",
        "供货合同",
        "中标通知书",
    ]):
        profile["evidence_types"].add("project_performance")
        profile["libraries"].add("qualification_library")
    if any(keyword in heading_text for keyword in ["logo", "Logo", "标识", "企业形象", "封面"]):
        profile["evidence_types"].add("brand_logo")
        profile["libraries"].add("qualification_library")
    return profile


def _score_asset_for_section(asset: dict, section: dict) -> int:
    asset_text = _asset_text(asset)
    section_text = _section_text(section)
    volume_type = section_volume_type(section)
    profile = _section_asset_profile(section)
    evidence_type = _asset_meta_value(asset, "evidence_type")
    target_library = _asset_meta_value(asset, "target_library")
    score = 0

    for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", section_text):
        if token in asset_text:
            score += 2 if len(token) >= 4 else 1

    category = str(asset.get("category") or "")
    asset_type = str(asset.get("asset_type") or "")
    library_type = ""
    metadata = asset.get("metadata") or {}
    specs = asset.get("specs") or {}
    if isinstance(metadata, dict):
        library_type = str(metadata.get("library_type") or "")
    if not library_type and isinstance(specs, dict):
        library_type = str(specs.get("library_type") or "")

    if volume_type == "technical":
        if library_type == "product" or any(keyword in asset_text for keyword in ["产品", "设备", "参数", "工艺", "变压器", "开关柜", "电缆", "保护装置", "自动化", "控制柜"]):
            score += 22
        if library_type == "qualification":
            score -= 10
    elif volume_type == "qualification":
        if library_type == "qualification" or any(keyword in asset_text for keyword in ["资质", "证书", "营业执照", "许可", "业绩", "人员", "社保"]):
            score += 24
        if library_type == "product":
            score -= 12
    elif volume_type == "business":
        if any(keyword in asset_text for keyword in ["授权", "保证金", "保函", "承诺", "证明", "营业执照", "资质"]):
            score += 10
        if any(keyword in asset_text for keyword in ["产品", "设备", "工艺", "施工现场"]):
            score -= 18
    elif volume_type == "attachment":
        score += 6
    elif volume_type == "price":
        return -100

    if any(keyword in section_text for keyword in ["资质", "证书", "营业执照", "许可"]):
        if any(keyword in asset_text for keyword in ["资质", "证书", "营业执照", "许可", "脱敏"]):
            score += 18
    if any(keyword in section_text for keyword in ["产品", "设备", "材料", "报价", "清单"]):
        if any(keyword in asset_text for keyword in ["产品", "设备", "材料", "参数", "变压器", "开关柜", "电缆", "保护装置"]):
            score += 14
    if any(keyword in section_text for keyword in ["施工", "安装", "调试", "试验", "运维", "检修", "工程", "输变电", "配网", "变电站", "线路"]):
        if any(keyword in asset_text for keyword in ["施工", "安装", "调试", "试验", "运维", "检修", "工程", "输变电", "配网", "现场", "项目"]):
            score += 12
    if category and category.lower() in section_text:
        score += 6
    if asset_type and asset_type.lower() in section_text:
        score += 4
    preferred_evidence = profile["evidence_types"]
    preferred_libraries = profile["libraries"]
    if preferred_evidence:
        if evidence_type in preferred_evidence:
            score += 36
        elif evidence_type:
            score -= 28
    if preferred_libraries:
        if target_library in preferred_libraries:
            score += 12
        elif target_library:
            score -= 10
    return score


def _asset_image_ref(asset: dict) -> str:
    asset_id = str(asset.get("id") or "").strip()
    if asset_id:
        return f"/api/bidding/knowledge/assets/{quote(asset_id)}/file?variant=original"

    local_path = str(asset.get("local_path") or "").strip()
    if local_path:
        candidate = Path(local_path)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    public_url = str(asset.get("public_url") or "").strip()
    if public_url.startswith(("http://", "https://")):
        return public_url.replace("variant=thumb", "variant=original")

    storage_path = str(asset.get("storage_path") or "").strip()
    if storage_path.startswith(("http://", "https://")):
        return storage_path.replace("variant=thumb", "variant=original")
    return ""


def _asset_library_label(asset: dict) -> str:
    metadata = asset.get("metadata") or {}
    specs = asset.get("specs") or {}
    library_type = ""
    if isinstance(metadata, dict):
        library_type = str(metadata.get("library_type") or "")
    if not library_type and isinstance(specs, dict):
        library_type = str(specs.get("library_type") or "")
    if library_type == "product":
        return "企业产品库"
    if library_type == "qualification":
        return "企业资信库"
    return "企业知识资产库"


def _asset_caption(asset: dict, match_reason: str | None = None) -> str:
    caption = formal_asset_caption(asset)
    if caption:
        return caption
    fallback = formal_asset_title(asset, "企业证明材料")
    return f"资料：{fallback}" if fallback else "资料：企业证明材料"


def _asset_match_reason(asset: dict, section: dict, score: int) -> str:
    volume_type = section_volume_type(section)
    section_text = _section_text(section)
    asset_text = _asset_text(asset)
    reasons: list[str] = []
    library_label = _asset_library_label(asset)
    if volume_type == "technical" and library_label == "企业产品库":
        reasons.append("技术标优先使用产品/设备资料")
    elif volume_type == "qualification" and library_label == "企业资信库":
        reasons.append("资格文件优先使用资信/证照资料")
    elif volume_type == "business":
        reasons.append("商务文件仅插入证明或附件类资料")

    evidence_type = _asset_meta_value(asset, "evidence_type")
    profile = _section_asset_profile(section)
    if evidence_type and evidence_type in profile["evidence_types"]:
        evidence_labels = {
            "business_license": "营业执照",
            "certification": "资信/认证证书",
            "production_capacity": "生产制造能力",
            "testing_capacity": "试验检测能力",
            "green_low_carbon": "绿色低碳资料",
            "inspection_report": "检验/检测报告",
            "project_performance": "同类项目业绩",
            "brand_logo": "企业 Logo",
        }
        reasons.append(f"匹配章节证据类型：{evidence_labels.get(evidence_type, evidence_type)}")

    for keyword in ["产品", "设备", "工艺", "施工", "资质", "证书", "营业执照", "业绩", "合同", "中标通知书", "人员", "授权", "保证金", "保函"]:
        if keyword in section_text and keyword in asset_text:
            reasons.append(f"章节与资产同时命中“{keyword}”")
            if len(reasons) >= 3:
                break
    if not reasons:
        reasons.append(f"综合匹配分 {score}")
    return "；".join(reasons[:3])


def _manifest_evidence_counts(image_manifest: list[dict] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in image_manifest or []:
        evidence_type = str(item.get("evidence_type") or "")
        if evidence_type:
            counts[evidence_type] = counts.get(evidence_type, 0) + 1
    return counts


def _asset_evidence_allowed_by_manifest(asset: dict, image_manifest: list[dict] | None) -> bool:
    evidence_type = _asset_meta_value(asset, "evidence_type")
    counts = _manifest_evidence_counts(image_manifest)
    selected_total = len(image_manifest or [])
    if (
        selected_total >= max(0, DOCX_TOTAL_ASSET_IMAGE_LIMIT - 2)
        and counts.get("project_performance", 0) < 2
        and evidence_type != "project_performance"
    ):
        return False
    caps = {
        # A long bid can otherwise spend the whole 24-image budget on early
        # certificate/business pages before performance and inspection-report
        # chapters are reached.
        "certification": 7,
        "business_license": 4,
        "testing_capacity": 4,
        "green_low_carbon": 4,
        "inspection_report": 5,
    }
    cap = caps.get(evidence_type)
    if not cap:
        return True
    return counts.get(evidence_type, 0) < cap


def _asset_allowed_for_volume(asset: dict, section: dict) -> bool:
    volume_type = section_volume_type(section)
    if volume_type == "price":
        return False
    if not asset_matches_volume(asset, volume_type, allow_unscoped=True):
        return False
    profile = _section_asset_profile(section)
    evidence_type = _asset_meta_value(asset, "evidence_type")
    if not profile["evidence_types"] and not profile["libraries"]:
        return False
    if profile["evidence_types"] and evidence_type and evidence_type not in profile["evidence_types"]:
        return False
    asset_text = _asset_text(asset)
    raw_title = _strip_existing_section_number(section.get("title") or "").lower()
    if "认证证书" in raw_title and evidence_type and evidence_type not in {"certification", "green_low_carbon"}:
        return False
    specific_certificate_requirements = [
        ("质量管理体系认证证书", ["质量管理体系", "iso9001"]),
        ("职业健康安全管理体系认证证书", ["职业健康安全", "iso45001"]),
        ("环境管理体系认证证书", ["环境管理体系", "iso14001"]),
        ("能源管理体系认证证书", ["能源管理体系"]),
    ]
    for title_keyword, asset_keywords in specific_certificate_requirements:
        if title_keyword in raw_title and not any(keyword.lower() in asset_text for keyword in asset_keywords):
            return False
    if evidence_type == "business_license" and not any(keyword in asset_text for keyword in ["营业执照", "统一社会信用代码", "法人证书", "组织登记证书"]):
        return False
    if evidence_type == "certification" and not any(keyword in asset_text for keyword in ["认证证书", "体系认证", "质量管理体系", "环境管理体系", "职业健康安全", "iso9001", "iso14001", "iso45001"]):
        return False
    if evidence_type == "project_performance" and not any(keyword in asset_text for keyword in ["中标通知书", "合同", "业绩", "供货", "购销"]):
        return False
    metadata = asset.get("metadata") or {}
    specs = asset.get("specs") or {}
    library_type = ""
    if isinstance(metadata, dict):
        library_type = str(metadata.get("library_type") or "")
    if not library_type and isinstance(specs, dict):
        library_type = str(specs.get("library_type") or "")

    if volume_type == "technical":
        if evidence_type == "project_performance":
            return True
        return library_type != "qualification" or any(keyword in asset_text for keyword in ["设备", "产品", "参数", "工艺", "施工", "现场"])
    if volume_type == "qualification":
        return library_type != "product" or any(keyword in asset_text for keyword in ["业绩", "证明", "资质", "证书"])
    if volume_type == "business":
        if not profile["evidence_types"]:
            return False
        return any(keyword in asset_text for keyword in ["授权", "保证金", "保函", "承诺", "证明", "营业执照", "资质", "扫描件"])
    return True


def _build_section_image_markdown(
    section: dict,
    assets: list[dict],
    used_asset_ids: set[str],
    image_manifest: list[dict] | None = None,
    remaining_limit: int | None = None,
) -> str:
    if not assets or not _section_needs_image(section):
        return ""
    if remaining_limit is not None and remaining_limit <= 0:
        return ""

    candidates: list[tuple[int, dict]] = []
    for asset in assets:
        image_ref = _asset_image_ref(asset)
        if not image_ref:
            continue
        asset_id = str(asset.get("id") or image_ref)
        if asset_id in used_asset_ids:
            continue
        display_key = f"display::{_asset_meta_value(asset, 'evidence_type')}::{formal_asset_title(asset, '企业证明材料')}"
        if display_key in used_asset_ids:
            continue
        if not _asset_evidence_allowed_by_manifest(asset, image_manifest):
            continue
        if not _asset_allowed_for_volume(asset, section):
            continue
        score = _score_asset_for_section(asset, section)
        if score > 0:
            candidates.append((score, asset))

    if not candidates:
        return ""

    candidates.sort(key=lambda item: item[0], reverse=True)
    volume_type = section_volume_type(section)
    section_limit = max(0, DOCX_VOLUME_IMAGE_LIMITS.get(volume_type, DOCX_VOLUME_IMAGE_LIMITS["other"]))
    if remaining_limit is not None:
        section_limit = min(section_limit, remaining_limit)
    if section_limit <= 0:
        return ""
    snippets: list[str] = []
    for score, asset in candidates[:section_limit]:
        image_ref = _asset_image_ref(asset)
        asset_id = str(asset.get("id") or image_ref)
        display_key = f"display::{_asset_meta_value(asset, 'evidence_type')}::{formal_asset_title(asset, '企业证明材料')}"
        if asset_id in used_asset_ids or display_key in used_asset_ids:
            continue
        used_asset_ids.add(asset_id)
        alt = re.sub(r"[\[\]\(\)]", "", formal_asset_title(asset, "电网行业配图")).strip()
        used_asset_ids.add(display_key)
        match_reason = _asset_match_reason(asset, section, score)
        caption = _asset_caption(asset, match_reason)
        caption_block = f"\n\n{caption}" if caption else ""
        snippets.append(f"\n\n![{alt}]({image_ref}){caption_block}\n\n")
        if image_manifest is not None:
            image_manifest.append({
                "asset_id": asset.get("id"),
                "asset_title": asset.get("title"),
                "asset_formal_title": alt,
                "asset_category": asset.get("category"),
                "asset_type": asset.get("asset_type"),
                "evidence_type": _asset_meta_value(asset, "evidence_type"),
                "target_library": _asset_meta_value(asset, "target_library"),
                "source_batch_id": _asset_meta_value(asset, "source_batch_id") or _asset_meta_value(asset, "ingestion_batch_id"),
                "library": _asset_library_label(asset),
                "section_id": section.get("id"),
                "section_title": _section_display_title(section),
                "volume_type": volume_type,
                "volume_name": volume_name(volume_type),
                "score": score,
                "reason": match_reason,
                "image_ref": image_ref,
                "caption": caption,
                "caption_policy": "formal_material_caption" if caption else caption_policy(asset),
                "sensitive": bool(asset.get("is_sensitive")),
                "anonymized": bool(asset.get("anonymized")),
            })
    return "".join(snippets)


def _build_taichang_evidence_bundle_markdown(
    section: dict,
    bundles: list[dict],
    assets_by_id: dict[str, dict],
    used_asset_ids: set[str],
    image_manifest: list[dict],
) -> str:
    """按证据包原页序插入整页证据，不显示内部检索信息或调试题注。"""
    chunks: list[str] = []
    for bundle in bundles:
        chunks.append(f"### {clean_formal_bid_text(bundle.get('bundle_title') or '企业证明材料')}\n\n")
        for page in bundle.get("pages") or []:
            asset_id = str(page.get("asset_id") or "")
            asset = assets_by_id.get(asset_id)
            if not asset or asset_id in used_asset_ids:
                continue
            image_ref = _asset_image_ref(asset)
            if not image_ref:
                continue
            used_asset_ids.add(asset_id)
            alt = clean_formal_bid_text(
                f"{bundle.get('bundle_title') or '企业证明材料'}第{page.get('global_order') or page.get('page_no')}页"
            )
            chunks.append(f"![{alt}]({image_ref})\n\n")
            image_manifest.append({
                "asset_id": asset_id,
                "asset_title": asset.get("title"),
                "asset_formal_title": alt,
                "asset_category": asset.get("category"),
                "asset_type": asset.get("asset_type"),
                "evidence_type": bundle.get("evidence_type"),
                "target_library": _asset_meta_value(asset, "target_library"),
                "source_batch_id": _asset_meta_value(asset, "source_batch_id") or _asset_meta_value(asset, "ingestion_batch_id"),
                "library": _asset_library_label(asset),
                "section_id": section.get("id"),
                "section_title": _section_display_title(section),
                "volume_type": section_volume_type(section),
                "volume_name": volume_name(section_volume_type(section)),
                "score": None,
                "reason": "章节—证据包确定性映射",
                "image_ref": image_ref,
                "caption": "",
                "caption_policy": "suppressed_document_page_caption",
                "evidence_bundle_id": bundle.get("evidence_bundle_id"),
                "evidence_bundle_title": bundle.get("bundle_title"),
                "bundle_page_no": page.get("page_no"),
                "bundle_global_order": page.get("global_order"),
                "bundle_component": page.get("component"),
                "selection_policy": "chapter_to_evidence_bundle_to_original_page_sequence",
                "asset_policy": {
                    "enterprise": _asset_meta_value(asset, "enterprise") or asset.get("enterprise"),
                    "doc_owner": _asset_meta_value(asset, "doc_owner"),
                    "source_domain": _asset_meta_value(asset, "source_domain"),
                    "quality_tier": _asset_meta_value(asset, "quality_tier"),
                    "formal_bid_ready": _asset_meta_bool(asset, "formal_bid_ready"),
                    "bundle_allowed_for_bid": bool(bundle.get("allowed_for_bid")),
                    "bundle_usage_status": bundle.get("usage_status"),
                    "allowed_for_bid": _asset_meta_bool(asset, "allowed_for_bid"),
                    "reference_only": _asset_meta_bool(asset, "reference_only"),
                    "exclude_from_docx": _asset_meta_bool(asset, "exclude_from_docx"),
                    "full_page": _asset_meta_bool(asset, "full_page"),
                    "asset_visual_type": _asset_meta_value(asset, "asset_visual_type"),
                },
                "sensitive": bool(asset.get("is_sensitive")),
                "anonymized": bool(asset.get("anonymized")),
            })
    return "".join(chunks)


def _asset_allowed_for_bid(asset: dict) -> bool:
    metadata = asset.get("metadata") or {}
    specs = asset.get("specs") or {}
    if isinstance(metadata, dict) and metadata.get("allowed_for_bid") is False:
        return False
    if isinstance(specs, dict) and specs.get("allowed_for_bid") is False:
        return False
    quality_tier = ""
    if isinstance(metadata, dict):
        quality_tier = str(metadata.get("quality_tier") or "").strip()
    if not quality_tier and isinstance(specs, dict):
        quality_tier = str(specs.get("quality_tier") or "").strip()
    if quality_tier and quality_tier != "formal_bid_ready":
        return False
    reference_only_values = [
        metadata.get("reference_only") if isinstance(metadata, dict) else None,
        specs.get("reference_only") if isinstance(specs, dict) else None,
        asset.get("reference_only"),
    ]
    if any(value is True or str(value).lower() == "true" for value in reference_only_values if value is not None):
        return False

    enterprise_values = [
        metadata.get("enterprise") if isinstance(metadata, dict) else None,
        specs.get("enterprise") if isinstance(specs, dict) else None,
        asset.get("enterprise"),
        metadata.get("doc_owner") if isinstance(metadata, dict) else None,
        specs.get("doc_owner") if isinstance(specs, dict) else None,
    ]
    enterprise_text = " ".join(str(value) for value in enterprise_values if value)
    if "泰昌" not in enterprise_text and DOCX_BIDDER_FULL_NAME not in enterprise_text:
        return False

    source_domain = _asset_meta_value(asset, "source_domain")
    if source_domain and source_domain != "enterprise_fact":
        return False
    return True


def _section_with_descendants(sections: list[dict], section_id: str) -> list[dict]:
    selected_ids = {section_id}
    changed = True
    while changed:
        changed = False
        for section in sections:
            if section.get("parent_id") in selected_ids and section.get("id") not in selected_ids:
                selected_ids.add(section["id"])
                changed = True
    return [section for section in sections if section.get("id") in selected_ids]


def _snapshot_export_sections(sections_snapshot: list[dict] | None) -> list[dict] | None:
    if not isinstance(sections_snapshot, list):
        return None
    sections: list[dict] = []
    for index, section in enumerate(sections_snapshot):
        if not isinstance(section, dict):
            continue
        title = clean_formal_bid_text(str(section.get("title") or "")).strip()
        if not title:
            continue
        try:
            level = max(1, min(int(section.get("level") or 1), 6))
        except (TypeError, ValueError):
            level = 1
        try:
            order_index = int(section.get("order_index") or index + 1)
        except (TypeError, ValueError):
            order_index = index + 1
        metadata = section.get("metadata") if isinstance(section.get("metadata"), dict) else {}
        sections.append({
            **section,
            "title": title,
            "content": str(section.get("content") or ""),
            "level": level,
            "order_index": order_index,
            "metadata": metadata,
        })
    if not sections:
        return None
    return sorted(sections, key=lambda item: (int(item.get("order_index") or 0), str(item.get("id") or "")))


def build_project_bid_markdown(
    project_id: str,
    focus_section_id: str | None = None,
    with_images: bool = False,
    volume_type: str | None = None,
    sections_snapshot: list[dict] | None = None,
) -> tuple[Path, str, dict]:
    payload = get_project_interpretation(project_id)
    project = payload.get("project") or {}
    analysis = payload.get("analysis") or {}
    project_meta = analysis.get("project_meta") if isinstance(analysis.get("project_meta"), dict) else {}
    sections = _snapshot_export_sections(sections_snapshot) or list_bid_sections(project_id)
    if not sections:
        raise RuntimeError("当前项目暂无章节内容，请先生成章节大纲或正文。")

    project_name = (
        project_meta or {}
    ).get("project_name") or project.get("project_name") or "投标文件"
    project_name = clean_formal_bid_text(project_name) or "投标文件"
    report_cover_fields = dict(project_meta.get("cover_fields") if isinstance(project_meta.get("cover_fields"), dict) else {})
    folder_name = _slug_filename(project_id[:8], f"project-{project_id[:8]}")
    output_dir = Path(current_app.config.get('GENERATED_FOLDER', 'outputs')) / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    focus_section = None
    if focus_section_id:
        focus_section = next((section for section in sections if section.get("id") == focus_section_id), None)
        if focus_section:
            sections = _section_with_descendants(sections, focus_section_id)
    elif volume_type:
        if volume_type in {"technical", "business"}:
            sections = [section for section in sections if delivery_volume_type(section) == volume_type]
        else:
            sections = [section for section in sections if section_volume_type(section) == volume_type]
        if not sections:
            raise RuntimeError(f"当前项目暂无{volume_name(volume_type)}章节，请先生成或调整章节分册。")

    display_suffix = ""
    if focus_section:
        section_title = clean_formal_bid_text(focus_section.get('title') or "章节")
        display_suffix = f"-{section_title}-{focus_section_id[:8]}"
    elif volume_type:
        display_suffix = f"-{volume_name(volume_type)}"
    if with_images:
        display_suffix = f"{display_suffix}-图文"

    delivery_file_type = delivery_volume_file_type(volume_type if not focus_section_id else None)
    if delivery_file_type != "投标文件":
        report_cover_fields["文件类型"] = delivery_file_type

    image_assets: list[dict] = []
    deterministic_bundle_export = False
    evidence_bundle_plan: dict = {}
    evidence_bundle_sections: dict[str, list[dict]] = {}
    export_image_report: dict = {
        "enabled": bool(with_images),
        "scope": "section" if focus_section_id else ("volume" if volume_type else "full"),
        "volume_type": volume_type,
        "volume_name": volume_name(volume_type) if volume_type else "完整投标文件",
        "delivery_file_type": delivery_file_type,
        "section_count": len(sections),
        "asset_candidates": 0,
        "selected": 0,
        "max_total": DOCX_TOTAL_ASSET_IMAGE_LIMIT,
        "manifest": [],
        "warnings": [],
        "cover_fields": report_cover_fields,
        "cover_field_sources": project_meta.get("cover_field_sources") if isinstance(project_meta.get("cover_field_sources"), dict) else {},
        "cover_field_missing": project_meta.get("cover_field_missing") if isinstance(project_meta.get("cover_field_missing"), list) else [],
        "cover_field_source": "uploaded_tender_structured_extract" if isinstance(project_meta.get("cover_fields"), dict) and project_meta.get("cover_fields") else "markdown_fallback",
    }
    if focus_section:
        focus_metadata = focus_section.get("metadata") if isinstance(focus_section.get("metadata"), dict) else {}
        fixed_form_manifest = focus_metadata.get("fixed_form_manifest") if isinstance(focus_metadata.get("fixed_form_manifest"), dict) else None
        if fixed_form_manifest:
            export_image_report["fixed_form_manifest"] = fixed_form_manifest
            export_image_report["fixed_form_export"] = {
                "enabled": True,
                "renderer": "native_docx_ooxml_clone",
                "model_bypassed": True,
                "source_form_key": fixed_form_manifest.get("form_key"),
            }
    prefill_state = project_meta.get("bid_prefill") if isinstance(project_meta.get("bid_prefill"), dict) else {}
    confirmed_values = prefill_state.get("confirmed_values") if isinstance(prefill_state.get("confirmed_values"), dict) else {}
    material_scope = material_scope_from_context(project_meta, report_cover_fields, confirmed_values)
    if material_scope:
        before_count = len(sections)
        sections = filter_sections_by_material_scope(sections, material_scope)
        if len(sections) != before_count:
            export_image_report["warnings"].append(
                f"已按本包物料范围（{'、'.join(sorted(material_scope))}）过滤非本包物料章节 {before_count - len(sections)} 个。"
            )
            export_image_report["material_scope_filter"] = {
                "allowed_families": sorted(material_scope),
                "before": before_count,
                "after": len(sections),
                "removed": before_count - len(sections),
            }
    fixed_form_manifests = [
        metadata["fixed_form_manifest"]
        for section in sections
        if isinstance((metadata := section.get("metadata")), dict)
        and isinstance(metadata.get("fixed_form_manifest"), dict)
    ]
    if fixed_form_manifests:
        export_image_report["fixed_form_manifests"] = fixed_form_manifests
    parent_section_ids = {str(section.get("parent_id")) for section in sections if section.get("parent_id")}

    def is_container_section(section: dict) -> bool:
        metadata = section.get("metadata") if isinstance(section.get("metadata"), dict) else {}
        return (
            metadata.get("section_role") == "container"
            or metadata.get("leaf_generation") is False
            or str(section.get("id") or "") in parent_section_ids
        )

    empty_section_count = sum(
        1 for section in sections
        if not is_container_section(section) and not str(section.get("content") or "").strip()
    )
    placeholder_count = count_formal_placeholders(str(section.get("content") or "") for section in sections)
    if confirmed_values.get("package_no"):
        report_cover_fields["包号"] = str(confirmed_values.get("package_no"))
    if confirmed_values.get("package_name"):
        report_cover_fields["包名称"] = str(confirmed_values.get("package_name"))
    if confirmed_values.get("project_name"):
        report_cover_fields["项目名称"] = str(confirmed_values.get("project_name"))
    if confirmed_values.get("tender_no"):
        report_cover_fields["招标编号"] = str(confirmed_values.get("tender_no"))
    export_image_report["cover_fields"] = report_cover_fields
    missing_required = formal_required_confirmation_gaps(confirmed_values)
    template_profile = resolve_docx_template_profile(report_cover_fields)
    numbering_style = str(template_profile.get("section_numbering_style") or "decimal_outline")
    if not focus_section_id and not volume_type and _full_export_should_use_sgcc_mixed_numbering(sections):
        numbering_style = "sgcc_mixed"
    export_image_report["formal_readiness"] = {
        "template_id": template_profile.get("template_id") or "formal_bid_standard",
        "template_family": template_profile.get("template_family"),
        "reference_path": template_profile.get("reference_path"),
        "section_numbering_style": numbering_style,
        "reference_template_policy": "tender_format_then_customer_reference_then_system_default",
        "bidder": DOCX_BIDDER_FULL_NAME,
        "empty_section_count": empty_section_count,
        "placeholder_count": placeholder_count,
        "missing_formal_required_fields": missing_required,
        "export_confirmation_replacements": 0,
        "ready": empty_section_count == 0 and placeholder_count == 0 and not missing_required,
    }
    if empty_section_count:
        export_image_report["warnings"].append(f"仍有 {empty_section_count} 个章节没有正文，当前文件只能作为草稿。")
    if placeholder_count:
        export_image_report["warnings"].append(f"仍有 {placeholder_count} 处待补充/待确认占位，当前文件尚未达到正式投标文件标准。")
    if missing_required:
        export_image_report["warnings"].append(f"仍有 {len(missing_required)} 个正式必填字段未确认，请返回投标信息确认步骤补齐。")
    if with_images:
        try:
            image_assets = [
                asset for asset in list_knowledge_assets()
                if _asset_image_ref(asset)
                and _asset_allowed_for_bid(asset)
                and str(asset.get("asset_type") or "").lower() not in {"document", "markdown", "text"}
            ]
            export_image_report["asset_candidates"] = len(image_assets)
        except Exception:
            logging.exception("加载知识库图片资产失败，继续生成无配图 DOCX: %s", project_id)
            image_assets = []
            export_image_report["warnings"].append("加载知识库图片资产失败，已降级为无配图导出。")

    if with_images and str(project.get("project_mode") or "") == "taichang_reuse":
        deterministic_bundle_export = True
        evidence_bundle_plan = build_taichang_evidence_export_plan(
            sections,
            image_assets,
            material_scope=material_scope,
            max_pages=DOCX_TOTAL_ASSET_IMAGE_LIMIT,
            asset_allowed=_asset_allowed_for_bid,
        )
        evidence_bundle_sections = evidence_pages_by_section(evidence_bundle_plan)
        export_image_report["evidence_bundle_selection"] = evidence_bundle_plan
        export_image_report["selection_policy"] = evidence_bundle_plan.get("selection_policy")
        if evidence_bundle_plan.get("skipped_bundle_count"):
            export_image_report["warnings"].append(
                f"有 {evidence_bundle_plan['skipped_bundle_count']} 个证据包因页序、适用范围或正式门禁未通过而整包跳过。"
            )

    base_document_title = taichang_bid_document_title(project_name)
    document_title = f"{base_document_title}-{volume_name(volume_type)}" if volume_type and not focus_section else base_document_title
    file_stem = _export_download_stem(
        project_id=project_id,
        project=project,
        project_meta=project_meta,
        cover_fields=report_cover_fields,
        volume_type=volume_type if not focus_section_id else None,
        focus_section=focus_section,
        with_images=with_images,
    )
    markdown_path = output_dir / f"{file_stem}.md"
    export_image_report["download_file_name"] = f"{file_stem}.docx"
    export_image_report["download_markdown_name"] = f"{file_stem}.md"
    export_image_report["output_naming"] = {
        "scheme": "short_bidder_tender_package_volume_date.v1",
        "physicalFolder": folder_name,
        "fileStem": file_stem,
        "legacyDisplaySuffix": display_suffix,
    }
    chunks: list[str] = [f"# {document_title}\n\n"]
    used_asset_ids: set[str] = set()
    for section in _numbered_export_sections(sections, numbering_style=numbering_style):
        title = section.get("_export_title") or _section_display_title(section)
        container_section = is_container_section(section)
        content = "" if container_section else _strip_untrusted_export_images(
            _strip_redundant_section_label(
                _sanitize_export_visible_markup(
                    _normalize_body_outline_lines(
                        _strip_export_guidance_blocks(
                            _demote_body_markdown_headings(
                                _renumber_body_markdown_headings(
                                    _strip_duplicate_section_heading(section.get("content") or "", section),
                                    section,
                                )
                            )
                        ),
                        section,
                    ),
                ),
                section,
            ),
            remove_all=with_images,
        )
        if confirmed_values:
            content, confirmation_replacements = apply_confirmed_values_to_export_text(content, confirmed_values)
            export_image_report["formal_readiness"]["export_confirmation_replacements"] += confirmation_replacements
        content, finalization_replacements = finalize_confirmed_formal_export_text(content, confirmed_values)
        export_image_report["formal_readiness"]["export_confirmation_replacements"] += finalization_replacements
        chunks.append(_section_markdown_heading(int(section.get("level") or 1), title))
        if content:
            chunks.append(f"{content}\n\n" if content.endswith("\n") else f"{content}\n\n")
        elif not container_section:
            chunks.append("待补充章节正文。\n\n")
        if with_images and deterministic_bundle_export and not container_section:
            snippet = _build_taichang_evidence_bundle_markdown(
                section,
                evidence_bundle_sections.get(str(section.get("id") or ""), []),
                {str(asset.get("id")): asset for asset in image_assets if asset.get("id")},
                used_asset_ids,
                export_image_report["manifest"],
            )
            if snippet:
                chunks.append(snippet)
        elif with_images and not container_section and "![" not in content:
            remaining = DOCX_TOTAL_ASSET_IMAGE_LIMIT - len(export_image_report["manifest"])
            snippet = _build_section_image_markdown(
                section,
                image_assets,
                used_asset_ids,
                image_manifest=export_image_report["manifest"],
                remaining_limit=remaining,
            )
            if snippet:
                chunks.append(snippet)

    if with_images and image_assets and not deterministic_bundle_export:
        evidence_counts = _manifest_evidence_counts(export_image_report["manifest"])
        required_project_performance = 2
        missing_project_performance = max(
            0,
            required_project_performance - evidence_counts.get("project_performance", 0),
        )
        remaining = DOCX_TOTAL_ASSET_IMAGE_LIMIT - len(export_image_report["manifest"])
        if missing_project_performance and remaining > 0:
            project_assets: list[tuple[int, dict]] = []
            for asset in image_assets:
                image_ref = _asset_image_ref(asset)
                if not image_ref:
                    continue
                asset_id = str(asset.get("id") or image_ref)
                if asset_id in used_asset_ids:
                    continue
                display_key = f"display::{_asset_meta_value(asset, 'evidence_type')}::{formal_asset_title(asset, '企业证明材料')}"
                if display_key in used_asset_ids:
                    continue
                if _asset_meta_value(asset, "evidence_type") != "project_performance":
                    continue
                score = 20
                asset_text = _asset_text(asset)
                if _asset_meta_value(asset, "source_batch_id") == "customer_taichang_supplement_20260611":
                    score += 20
                if any(keyword in asset_text for keyword in ["中标通知书", "合同", "业绩", "购销"]):
                    score += 12
                project_assets.append((score, asset))

            if project_assets:
                chunks.append("## 同类项目业绩证明补充附件\n\n")
                project_assets.sort(key=lambda item: item[0], reverse=True)
                for score, asset in project_assets[: min(missing_project_performance, remaining)]:
                    image_ref = _asset_image_ref(asset)
                    asset_id = str(asset.get("id") or image_ref)
                    display_key = f"display::{_asset_meta_value(asset, 'evidence_type')}::{formal_asset_title(asset, '企业证明材料')}"
                    if asset_id in used_asset_ids or display_key in used_asset_ids:
                        continue
                    used_asset_ids.add(asset_id)
                    alt = re.sub(r"[\[\]\(\)]", "", formal_asset_title(asset, "同类项目业绩证明")).strip()
                    used_asset_ids.add(display_key)
                    match_reason = "正式投标文件业绩证明最低配图要求"
                    caption = _asset_caption(asset, match_reason)
                    chunks.append(f"\n\n![{alt}]({image_ref})\n\n{caption}\n\n")
                    export_image_report["manifest"].append({
                        "asset_id": asset.get("id"),
                        "asset_title": asset.get("title"),
                        "asset_category": asset.get("category"),
                        "asset_type": asset.get("asset_type"),
                        "evidence_type": _asset_meta_value(asset, "evidence_type"),
                        "target_library": _asset_meta_value(asset, "target_library"),
                        "source_batch_id": _asset_meta_value(asset, "source_batch_id") or _asset_meta_value(asset, "ingestion_batch_id"),
                        "library": _asset_library_label(asset),
                        "section_id": None,
                        "section_title": "同类项目业绩证明补充附件",
                        "volume_type": "attachment",
                        "volume_name": volume_name("attachment"),
                        "score": score,
                        "reason": match_reason,
                        "image_ref": image_ref,
                        "caption": caption,
                        "caption_policy": "formal_material_caption" if caption else caption_policy(asset),
                        "sensitive": bool(asset.get("is_sensitive")),
                        "anonymized": bool(asset.get("anonymized")),
                    })

        evidence_counts = _manifest_evidence_counts(export_image_report["manifest"])
        supplement_testing_count = sum(
            1 for item in export_image_report["manifest"]
            if item.get("source_batch_id") == "customer_taichang_supplement_20260611"
            and item.get("evidence_type") == "testing_capacity"
        )
        remaining = DOCX_TOTAL_ASSET_IMAGE_LIMIT - len(export_image_report["manifest"])
        if volume_type != "business" and supplement_testing_count < 1 and remaining > 0:
            testing_assets: list[tuple[int, dict]] = []
            for asset in image_assets:
                image_ref = _asset_image_ref(asset)
                if not image_ref:
                    continue
                asset_id = str(asset.get("id") or image_ref)
                if asset_id in used_asset_ids:
                    continue
                display_key = f"display::{_asset_meta_value(asset, 'evidence_type')}::{formal_asset_title(asset, '企业证明材料')}"
                if display_key in used_asset_ids:
                    continue
                if _asset_meta_value(asset, "evidence_type") != "testing_capacity":
                    continue
                if _asset_meta_value(asset, "source_batch_id") != "customer_taichang_supplement_20260611":
                    continue
                score = 24
                asset_text = _asset_text(asset)
                if any(keyword in asset_text for keyword in ["试验", "检测", "设备", "万能试验机", "电子天平"]):
                    score += 16
                testing_assets.append((score, asset))

            if testing_assets:
                chunks.append("## 试验检测能力证明补充附件\n\n")
                testing_assets.sort(key=lambda item: item[0], reverse=True)
                for score, asset in testing_assets[:1]:
                    image_ref = _asset_image_ref(asset)
                    asset_id = str(asset.get("id") or image_ref)
                    display_key = f"display::{_asset_meta_value(asset, 'evidence_type')}::{formal_asset_title(asset, '企业证明材料')}"
                    if asset_id in used_asset_ids or display_key in used_asset_ids:
                        continue
                    used_asset_ids.add(asset_id)
                    alt = re.sub(r"[\[\]\(\)]", "", formal_asset_title(asset, "试验检测能力证明")).strip()
                    used_asset_ids.add(display_key)
                    match_reason = "正式投标文件试验检测能力最低配图要求"
                    caption = _asset_caption(asset, match_reason)
                    chunks.append(f"\n\n![{alt}]({image_ref})\n\n{caption}\n\n")
                    export_image_report["manifest"].append({
                        "asset_id": asset.get("id"),
                        "asset_title": asset.get("title"),
                        "asset_category": asset.get("category"),
                        "asset_type": asset.get("asset_type"),
                        "evidence_type": _asset_meta_value(asset, "evidence_type"),
                        "target_library": _asset_meta_value(asset, "target_library"),
                        "source_batch_id": _asset_meta_value(asset, "source_batch_id") or _asset_meta_value(asset, "ingestion_batch_id"),
                        "library": _asset_library_label(asset),
                        "section_id": None,
                        "section_title": "试验检测能力证明补充附件",
                        "volume_type": "attachment",
                        "volume_name": volume_name("attachment"),
                        "score": score,
                        "reason": match_reason,
                        "image_ref": image_ref,
                        "caption": caption,
                        "caption_policy": "formal_material_caption" if caption else caption_policy(asset),
                        "sensitive": bool(asset.get("is_sensitive")),
                        "anonymized": bool(asset.get("anonymized")),
                    })

    markdown_text = "".join(chunks)
    final_placeholder_count = count_formal_placeholders([markdown_text])
    export_image_report["formal_readiness"]["final_placeholder_count"] = final_placeholder_count
    export_image_report["formal_readiness"]["ready"] = (
        empty_section_count == 0 and final_placeholder_count == 0 and not missing_required
    )
    markdown_path.write_text(markdown_text, encoding="utf-8")
    export_image_report["selected"] = len(export_image_report["manifest"])
    if with_images and image_assets and export_image_report["selected"] >= DOCX_TOTAL_ASSET_IMAGE_LIMIT:
        export_image_report["warnings"].append(f"已达到整份文档自动插图上限 {DOCX_TOTAL_ASSET_IMAGE_LIMIT} 张。")
    return markdown_path, document_title, export_image_report


def save_onlyoffice_document_mapping(*, document_key: str, project_id: str, title: str, file_path: str, download_url: str) -> None:
    save_onlyoffice_document(
        document_key=document_key,
        project_id=project_id,
        title=title,
        file_path=file_path,
        download_url=download_url,
    )

def sync_and_parse_tender_in_background(file_path, original_filename, parse_id, supabase_sync=None):
    supabase_file_id = supabase_sync.get('file', {}).get('id') if supabase_sync else None
    try:
        if not supabase_sync:
            write_parse_status(parse_id, {
                "parse_status": "syncing_supabase",
                "parser": "mineru",
                "source_file": file_path,
                "file_name": original_filename,
            })
            supabase_sync = sync_uploaded_tender_to_supabase(file_path, original_filename)
            supabase_file_id = supabase_sync.get('file', {}).get('id') if supabase_sync else None
            write_parse_status(parse_id, {
                "parse_status": "supabase_synced",
                "project_id": supabase_sync.get('project', {}).get('id') if supabase_sync else None,
                "supabase_file_id": supabase_file_id,
            })
    except Exception as e:
        logging.exception("Supabase 招标文件后台同步失败，继续走本地 MinerU 解析: %s", file_path)
        write_parse_status(parse_id, {
            "parse_status": "supabase_sync_failed",
            "supabase_sync_error": str(e),
        })

    parse_and_index_tender_file(
        file_path=file_path,
        original_filename=original_filename,
        parse_id=parse_id,
        supabase_file_id=supabase_file_id,
    )

# ---- projects / mineru 路由已迁移至 backend/api/projects.py 和 backend/api/mineru.py ----
# 路由注册通过 routes.py 末尾的 import 触发，此处不再重复定义。

# ---- interpret / outline / length 路由已迁移至对应子模块 ----
# get_interpretation → backend/api/interpret.py
# generate_interpretation_ai_report → backend/api/interpret.py
# generate_interpretation_bid_outline → backend/api/outline.py
# stream_interpretation_bid_outline → backend/api/outline.py
# save_interpretation_length_settings → backend/api/length.py
# 路由注册通过 routes.py 末尾的 import 触发，此处不再重复定义。

# ---- compliance 路由已迁移至 backend/api/compliance.py ----
# get_interpretation_compliance_check → backend/api/compliance.py
# run_interpretation_semantic_compliance_check → backend/api/compliance.py
# 路由注册通过 routes.py 末尾的 import 触发，此处不再重复定义。



# ---- sections / compliance 路由已迁移至对应子模块 ----
# stream_interpretation_bid_section → backend/api/sections.py
# generate_compliance_supplement → backend/api/compliance.py
# get_bid_sections → backend/api/sections.py
# save_bid_section_api → backend/api/sections.py
# reorder_bid_sections_api → backend/api/sections.py
# reset_bid_sections_generation_api → backend/api/sections.py
# get_latest_section_generation_task_api → backend/api/sections.py
# create_section_generation_task_api → backend/api/sections.py
# update_section_generation_task_item_api → backend/api/sections.py
# cancel_section_generation_task_api → backend/api/sections.py
# remove_bid_section → backend/api/sections.py
# 路由注册通过 routes.py 末尾的 import 触发，此处不再重复定义。

# ---- export / onlyoffice 路由已迁移至对应子模块 ----
# generate_onlyoffice_config → backend/api/onlyoffice.py
# download_bid_docx → backend/api/export.py
# _run_bid_docx_export_task → backend/api/export.py
# get_bid_export_task_api → backend/api/export.py
# save_callback → backend/api/onlyoffice.py
# 路由注册通过 routes.py 末尾的 import 触发，此处不再重复定义。
    
# ---- legacy 路由已迁移至 backend/api/legacy.py ----
# pre_analysis_bid → backend/api/legacy.py
# chapter_analysis_bid → backend/api/legacy.py
# chapter_design → backend/api/legacy.py
# generate_bid_document → backend/api/legacy.py
# 路由注册通过 routes.py 末尾的 import 触发，此处不再重复定义。
# ---- knowledge / assets 路由已迁移至对应子模块 ----
# sync_and_parse_knowledge_in_background → backend/api/knowledge.py
# upload_knowledge → backend/api/knowledge.py
# search_knowledge → backend/api/knowledge.py
# stream_search_knowledge → backend/api/knowledge.py
# generate_knowledge_followups → backend/api/knowledge.py
# get_knowledge_documents → backend/api/knowledge.py
# get_knowledge_document → backend/api/knowledge.py
# get_knowledge_assets → backend/api/assets.py
# get_knowledge_asset → backend/api/assets.py
# get_knowledge_asset_file → backend/api/assets.py
# upload_knowledge_asset → backend/api/assets.py
# update_knowledge_asset_api → backend/api/assets.py
# 路由注册通过 routes.py 末尾的 import 触发，此处不再重复定义。
# ---- 子模块路由注册触发 -------------------------------------------------------
# 各业务域路由已按模块拆分，通过下方 import 触发对 bp / knowledge_bp 的 @route 注册。
# 顺序：先 import _shared（已在文件顶部完成），再 import 各子模块。
# 注意：这些 import 必须放在文件末尾，确保 bp / knowledge_bp 已经被创建后才注册路由。
from backend.api import settings as _settings_routes  # noqa: F401, E402
from backend.api import projects as _projects_routes  # noqa: F401, E402
from backend.api import mineru as _mineru_routes  # noqa: F401, E402
from backend.api import interpret as _interpret_routes  # noqa: F401, E402
from backend.api import outline as _outline_routes  # noqa: F401, E402
from backend.api import length as _length_routes  # noqa: F401, E402
from backend.api import sections as _sections_routes  # noqa: F401, E402
from backend.api import compliance as _compliance_routes  # noqa: F401, E402
from backend.api import export as _export_routes  # noqa: F401, E402
from backend.api import onlyoffice as _onlyoffice_routes  # noqa: F401, E402
from backend.api import knowledge as _knowledge_routes  # noqa: F401, E402
from backend.api import assets as _assets_routes  # noqa: F401, E402
from backend.api import prefill as _prefill_routes  # noqa: F401, E402
from backend.api import formal_check as _formal_check_routes  # noqa: F401, E402
from backend.api import ai_editing as _ai_editing_routes  # noqa: F401, E402
from backend.api import legacy as _legacy_routes  # noqa: F401, E402

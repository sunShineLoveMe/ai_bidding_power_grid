import logging
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
import os
import sqlite3
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
from backend.export.md_to_word import clean_formal_bid_text, convert_md_to_word
from backend.ai.chapter_planner import generate_bid_outline, stream_bid_outline
from backend.ai.section_writer import estimate_bid_content_words, stream_bid_section
from backend.ai.interpreter import generate_ai_interpretation_report
from backend.ai.compliance_checker import build_compliance_report
from backend.ai.semantic_compliance import build_semantic_compliance_report
from backend.db.supabase_repo import cancel_bid_generation_task, create_bid_export_task, create_bid_generation_task, create_knowledge_asset, delete_bid_project, delete_bid_section, download_bid_file_to_local, download_knowledge_asset_file_variant, get_ai_usage_overview, get_bid_export_task, get_bid_file, get_latest_bid_file_for_project, get_latest_bid_generation_task, get_onlyoffice_document, get_project_interpretation, list_bid_history, list_bid_sections, list_recent_bid_projects, reorder_bid_sections, reset_bid_sections_generation, save_onlyoffice_document, sync_uploaded_tender_to_supabase, update_bid_analysis_project_meta, update_bid_export_task, update_bid_file_parse_status, update_bid_generation_task_item, update_bid_section_content, update_knowledge_asset, upload_knowledge_asset_file, upsert_bid_section
from backend.core.llm_json_utils import strip_llm_json
from backend.core.bid_volumes import asset_applicable_volumes, asset_matches_volume, delivery_volume_type, normalize_volume_list, section_volume_type, volume_name
from backend.ai.length_settings import apply_length_allocations_to_sections, allocate_chapter_length_targets, evaluate_length_feasibility, normalize_length_settings
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import shutil
from datetime import timedelta
from backend.core.config import DEFAULT_SETTINGS, build_enterprise_context, get_setting, load_runtime_settings, save_runtime_settings
from backend.core.security import UploadValidationError, safe_upload_filename, validate_uploaded_file

# 操作向量数据库的函数
from backend.parsing.document_parser import ingest_artifacts as ingest_mineru_artifacts_to_supabase, import_mineru_result_zip, parse_and_index_tender_file, read_parse_status, retry_mineru_result_download, write_parse_status

from backend.rag.vector_store import query_chroma

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
    """获取数据库连接"""
    conn = sqlite3.connect('bidding.db')
    conn.row_factory = sqlite3.Row
    return conn


# ---- settings / usage 路由已迁移至 backend/api/settings.py ----
# 路由注册通过 routes.py 末尾的 import 触发，此处不再重复定义。

def read_tender_file(bidding_id):
    """读取招标文件"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bidding WHERE id = ?', (bidding_id,))
        bidding = cursor.fetchone()
        conn.close()
        if not bidding:
            return jsonify({'error': '招标书不存在'}), 404
        file_path = Path(bidding['storage_path'])
        if file_path.suffix.lower() == '.pdf':
            return _read_pdf(file_path)
        else:
            with open(bidding['storage_path'], 'rb') as f:
                result = mammoth.extract_raw_text(f)
            return result.value
    except Exception as e:
        return jsonify({'error': f'读取文件失败: {str(e)}'}), 500

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
    value = re.sub(r"^\s*\d+(?:\.\d+)*[\.、]?\s*", "", value)
    value = re.sub(r"^\s*[一二三四五六七八九十百]+[、.．]\s*", "", value)
    value = re.sub(r"^\s*第[一二三四五六七八九十百]+[章节篇部分][、:：.\s]*", "", value)
    return value.strip() or clean_formal_bid_text(title or "未命名章节").strip() or "未命名章节"


def _numbered_export_sections(sections: list[dict]) -> list[dict]:
    raw_levels = [max(1, min(int(section.get("level") or 1), 6)) for section in sections]
    base_level = min(raw_levels) if raw_levels else 1
    counters: list[int] = []
    numbered: list[dict] = []
    raw_level_map: dict[int, int] = {}
    for section, raw_level in zip(sections, raw_levels):
        if raw_level in raw_level_map:
            level = raw_level_map[raw_level]
        else:
            level = raw_level - base_level + 1 if base_level > 1 else raw_level
            level = max(1, min(level, 6))
            # 真实大纲偶尔会出现从一级直接跳到三级的脏层级。
            # Word 目录不能出现 18.0.1 这类编号，导出时压平成紧邻的下一层。
            if counters and level > len(counters) + 1:
                level = len(counters) + 1
            raw_level_map[raw_level] = level
        level = max(1, min(level, 6))
        while len(counters) < level:
            counters.append(0)
        counters = counters[:level]
        counters[level - 1] += 1
        number = ".".join(str(value) for value in counters)
        clean_title = _strip_existing_section_number(section.get("title") or "未命名章节")
        title_prefix = f"{number}. " if "." not in number else f"{number} "
        numbered.append({
            **section,
            "_export_original_level": raw_level,
            "level": level,
            "_export_order": number,
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
                output.append(f"【{title}】")
            continue

        next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if stripped and re.match(r"^(=+|-+)$", next_line):
            output.append(f"【{clean_formal_bid_text(stripped)}】")
            continue
        if re.match(r"^(=+|-+)$", stripped) and output and output[-1].startswith("【"):
            continue
        output.append(raw_line)

    return "\n".join(output).strip()


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


def _section_needs_image(section: dict) -> bool:
    metadata = section.get("metadata") or {}
    plan = metadata.get("writing_plan") or {}
    volume_type = section_volume_type(section)
    if volume_type == "price":
        return False
    if volume_type == "business":
        text = _section_text(section)
        return any(keyword in text for keyword in ["附件", "证明材料", "授权委托", "保证金", "保函", "扫描件"])
    if plan.get("needs_image"):
        return True
    text = _section_text(section)
    keywords = [
        "资质", "证书", "营业执照", "许可", "业绩", "产品", "设备", "材料", "施工",
        "水库", "泵站", "闸门", "大坝", "渠道", "除险", "加固", "组织实施", "工程范围",
    ]
    return any(keyword in text for keyword in keywords)


def _score_asset_for_section(asset: dict, section: dict) -> int:
    asset_text = _asset_text(asset)
    section_text = _section_text(section)
    volume_type = section_volume_type(section)
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
        if library_type == "product" or any(keyword in asset_text for keyword in ["产品", "设备", "参数", "工艺", "水轮机", "泵", "闸门", "控制柜"]):
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
        if any(keyword in asset_text for keyword in ["产品", "设备", "材料", "参数", "水轮机", "螺母", "叶片"]):
            score += 14
    if any(keyword in section_text for keyword in ["施工", "组织", "工程", "水库", "大坝", "渠道", "泵站", "除险", "加固"]):
        if any(keyword in asset_text for keyword in ["施工", "工程", "水库", "泵站", "渠道", "现场", "项目"]):
            score += 12
    if category and category.lower() in section_text:
        score += 6
    if asset_type and asset_type.lower() in section_text:
        score += 4
    return score


def _asset_image_ref(asset: dict) -> str:
    local_path = str(asset.get("local_path") or "").strip()
    if local_path:
        candidate = Path(local_path)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    asset_id = str(asset.get("id") or "").strip()
    if asset_id:
        return f"/api/bidding/knowledge/assets/{quote(asset_id)}/file?variant=original"

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
    title = str(asset.get("title") or "知识库图片资产").strip()
    category = str(asset.get("category") or "水利行业资料").strip()
    sensitive_note = "，脱敏示意图，不替代正式资质文件" if asset.get("is_sensitive") or asset.get("anonymized") else ""
    source_note = f"来源：{_asset_library_label(asset)}"
    reason_note = f"；匹配依据：{match_reason}" if match_reason else ""
    return f"图示：{title}（{category}{sensitive_note}；{source_note}{reason_note}）"


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

    for keyword in ["产品", "设备", "工艺", "施工", "资质", "证书", "营业执照", "业绩", "人员", "授权", "保证金", "保函"]:
        if keyword in section_text and keyword in asset_text:
            reasons.append(f"章节与资产同时命中“{keyword}”")
            if len(reasons) >= 3:
                break
    if not reasons:
        reasons.append(f"综合匹配分 {score}")
    return "；".join(reasons[:3])


def _asset_allowed_for_volume(asset: dict, section: dict) -> bool:
    volume_type = section_volume_type(section)
    if volume_type == "price":
        return False
    if not asset_matches_volume(asset, volume_type, allow_unscoped=True):
        return False
    asset_text = _asset_text(asset)
    metadata = asset.get("metadata") or {}
    specs = asset.get("specs") or {}
    library_type = ""
    if isinstance(metadata, dict):
        library_type = str(metadata.get("library_type") or "")
    if not library_type and isinstance(specs, dict):
        library_type = str(specs.get("library_type") or "")

    if volume_type == "technical":
        return library_type != "qualification" or any(keyword in asset_text for keyword in ["设备", "产品", "参数", "工艺", "施工", "现场"])
    if volume_type == "qualification":
        return library_type != "product" or any(keyword in asset_text for keyword in ["业绩", "证明", "资质", "证书"])
    if volume_type == "business":
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
        if not _asset_allowed_for_volume(asset, section):
            continue
        score = _score_asset_for_section(asset, section)
        if asset_id in used_asset_ids:
            score -= 8
        if score > 0:
            candidates.append((score, asset))

    if not candidates:
        section_text = _section_text(section)
        fallback_keywords = ["产品", "设备", "施工", "工程", "水库", "泵站", "渠道", "现场", "资质", "证书", "营业执照"]
        for asset in assets:
            image_ref = _asset_image_ref(asset)
            if not image_ref:
                continue
            if not _asset_allowed_for_volume(asset, section):
                continue
            asset_text = _asset_text(asset)
            if any(keyword in asset_text for keyword in fallback_keywords) or any(keyword in section_text for keyword in fallback_keywords):
                candidates.append((1, asset))
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
        used_asset_ids.add(asset_id)
        alt = re.sub(r"[\[\]\(\)]", "", str(asset.get("title") or "水利行业配图")).strip()
        match_reason = _asset_match_reason(asset, section, score)
        caption = _asset_caption(asset, match_reason)
        snippets.append(f"\n\n![{alt}]({image_ref})\n\n{caption}\n\n")
        if image_manifest is not None:
            image_manifest.append({
                "asset_id": asset.get("id"),
                "asset_title": asset.get("title"),
                "asset_category": asset.get("category"),
                "asset_type": asset.get("asset_type"),
                "library": _asset_library_label(asset),
                "section_id": section.get("id"),
                "section_title": _section_display_title(section),
                "volume_type": volume_type,
                "volume_name": volume_name(volume_type),
                "score": score,
                "reason": match_reason,
                "image_ref": image_ref,
                "caption": caption,
                "sensitive": bool(asset.get("is_sensitive")),
                "anonymized": bool(asset.get("anonymized")),
            })
    return "".join(snippets)


def _asset_allowed_for_bid(asset: dict) -> bool:
    metadata = asset.get("metadata") or {}
    specs = asset.get("specs") or {}
    if isinstance(metadata, dict) and metadata.get("allowed_for_bid") is False:
        return False
    if isinstance(specs, dict) and specs.get("allowed_for_bid") is False:
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
    sections = _snapshot_export_sections(sections_snapshot) or list_bid_sections(project_id)
    if not sections:
        raise RuntimeError("当前项目暂无章节内容，请先生成章节大纲或正文。")

    project_name = (
        (payload.get("analysis") or {}).get("project_meta", {}) or {}
    ).get("project_name") or project.get("project_name") or "投标文件"
    project_name = clean_formal_bid_text(project_name) or "投标文件"
    folder_name = _slug_filename(project_name, f"project-{project_id[:8]}")
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

    image_assets: list[dict] = []
    export_image_report: dict = {
        "enabled": bool(with_images),
        "asset_candidates": 0,
        "selected": 0,
        "max_total": DOCX_TOTAL_ASSET_IMAGE_LIMIT,
        "manifest": [],
        "warnings": [],
    }
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

    document_title = f"{project_name}-{volume_name(volume_type)}" if volume_type and not focus_section else project_name
    file_stem = _display_filename(f"{project_name}{display_suffix}", fallback=document_title)
    markdown_path = output_dir / f"{file_stem}.md"
    chunks: list[str] = [f"# {document_title}\n\n"]
    used_asset_ids: set[str] = set()
    for section in _numbered_export_sections(sections):
        title = section.get("_export_title") or _section_display_title(section)
        content = _demote_body_markdown_headings(
            _strip_duplicate_section_heading(section.get("content") or "", section)
        )
        chunks.append(_section_markdown_heading(int(section.get("level") or 1), title))
        if content:
            chunks.append(f"{content}\n\n" if content.endswith("\n") else f"{content}\n\n")
        else:
            chunks.append("待补充章节正文。\n\n")
        if with_images and "![" not in content:
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

    markdown_path.write_text("".join(chunks), encoding="utf-8")
    export_image_report["selected"] = len(export_image_report["manifest"])
    if with_images and image_assets and export_image_report["selected"] >= DOCX_TOTAL_ASSET_IMAGE_LIMIT:
        export_image_report["warnings"].append(f"已达到整份文档自动插图上限 {DOCX_TOTAL_ASSET_IMAGE_LIMIT} 张。")
    return markdown_path, document_title, export_image_report


def save_onlyoffice_document_mapping(*, document_key: str, project_id: str, title: str, file_path: str, download_url: str) -> None:
    try:
        save_onlyoffice_document(
            document_key=document_key,
            project_id=project_id,
            title=title,
            file_path=file_path,
            download_url=download_url,
        )
        return
    except Exception:
        logging.exception("Supabase onlyoffice_documents 写入失败，回退 SQLite: %s", document_key)

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            '''
            INSERT INTO onlyoffice_documents (document_key, project_id, title, file_path, download_url)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(document_key) DO UPDATE SET
              project_id=excluded.project_id,
              title=excluded.title,
              file_path=excluded.file_path,
              download_url=excluded.download_url,
              updated_at=CURRENT_TIMESTAMP
            ''',
            (document_key, project_id, title, file_path, download_url),
        )
        conn.commit()
    finally:
        conn.close()

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
from backend.api import legacy as _legacy_routes  # noqa: F401, E402

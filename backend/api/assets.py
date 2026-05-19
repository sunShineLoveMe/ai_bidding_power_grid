"""
知识资产路由模块。

负责（每条路由均双蓝图注册）：
  - GET   /api/knowledge/assets + /api/bidding/knowledge/assets                    查询资产列表
  - GET   /api/knowledge/assets/<id> + /api/bidding/knowledge/assets/<id>          查询资产详情
  - GET   /api/knowledge/assets/<id>/file + /api/bidding/knowledge/assets/<id>/file 下载资产文件
  - POST  /api/knowledge/assets/upload + /api/bidding/knowledge/assets/upload       上传资产
  - PATCH /api/knowledge/assets/<id> + /api/bidding/knowledge/assets/<id>           更新资产

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from collections import OrderedDict
from pathlib import Path

import requests

from flask import Response, current_app, jsonify, request

from backend.api._shared import bp, knowledge_bp
from backend.core.bid_volumes import normalize_volume_list
from backend.core.security import UploadValidationError, safe_upload_filename, validate_uploaded_file
from backend.db.supabase_repo import (
    create_knowledge_asset,
    download_knowledge_asset_file_variant,
    get_knowledge_asset_detail,
    get_knowledge_asset_signed_urls,
    list_knowledge_assets,
    update_knowledge_asset,
    upload_knowledge_asset_file,
)

# ---------------------------------------------------------------------------
# 进程内图片缓存（LRU，最多 200 条，缓解 Supabase Storage 串行下载瓶颈）
# key: (asset_id, variant)  value: (asset_dict, bytes)
# ---------------------------------------------------------------------------
_ASSET_FILE_CACHE_MAX = 200
_asset_file_cache: OrderedDict[tuple, tuple] = OrderedDict()
_asset_file_cache_lock = threading.Lock()


def _get_cached_asset_file(asset_id: str, variant: str):
    key = (asset_id, variant)
    with _asset_file_cache_lock:
        if key in _asset_file_cache:
            _asset_file_cache.move_to_end(key)   # LRU：命中则移到末尾
            return _asset_file_cache[key]
    return None


def _put_cached_asset_file(asset_id: str, variant: str, value: tuple) -> None:
    key = (asset_id, variant)
    with _asset_file_cache_lock:
        _asset_file_cache[key] = value
        _asset_file_cache.move_to_end(key)
        if len(_asset_file_cache) > _ASSET_FILE_CACHE_MAX:
            _asset_file_cache.popitem(last=False)  # 淘汰最久未用的条目


def _split_form_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass
    return [item.strip() for item in re.split(r"[,，\n]", value) if item.strip()]


def _build_asset_searchable_text(payload: dict) -> str:
    parts = [
        payload.get("title"),
        payload.get("description"),
        payload.get("category"),
        payload.get("asset_type"),
        payload.get("ai_caption"),
    ]
    parts.extend(payload.get("tags") or [])
    parts.extend(payload.get("applicable_sections") or [])
    parts.extend(payload.get("applicable_volumes") or [])
    specs = payload.get("specs") or {}
    if isinstance(specs, dict):
        parts.extend(str(value) for value in specs.values() if value)
    return "\n".join(str(part).strip() for part in parts if str(part or "").strip())


def _asset_payload_from_form(storage_info: dict | None = None, existing: dict | None = None) -> dict:
    existing = existing or {}
    storage_info = storage_info or {}
    library_type = request.form.get('library_type') or (existing.get("metadata") or {}).get("library_type") or (existing.get("specs") or {}).get("library_type") or 'qualification'
    if library_type not in {'qualification', 'product'}:
        raise ValueError('library_type 仅支持 qualification 或 product')

    asset_type = request.form.get('asset_type') or existing.get("asset_type") or ('qualification_image' if library_type == 'qualification' else 'product_image')
    category = request.form.get('category') or existing.get("category") or ('企业资信' if library_type == 'qualification' else '产品资料')
    title = (request.form.get('title') or existing.get("title") or '').strip()
    description = (request.form.get('description') or existing.get("description") or '').strip()
    tags = _split_form_list(request.form.get('tags')) if 'tags' in request.form else (existing.get("tags") or [])
    applicable_sections = _split_form_list(request.form.get('applicable_sections')) if 'applicable_sections' in request.form else (existing.get("applicable_sections") or [])
    fallback_volumes = (
        existing.get("applicable_volumes")
        or (existing.get("specs") or {}).get("applicable_volumes")
        or (existing.get("metadata") or {}).get("applicable_volumes")
        or (["technical"] if library_type == "product" else ["qualification", "business", "attachment"])
    )
    applicable_volumes = (
        normalize_volume_list(_split_form_list(request.form.get('applicable_volumes')))
        if 'applicable_volumes' in request.form
        else normalize_volume_list(fallback_volumes)
    )
    allowed_for_bid = request.form.get('allowed_for_bid', str((existing.get("specs") or {}).get("allowed_for_bid", True))).lower() in {'1', 'true', 'yes', 'on'}
    is_sensitive = request.form.get('is_sensitive', str(existing.get("is_sensitive", False))).lower() in {'1', 'true', 'yes', 'on'}
    anonymized = request.form.get('anonymized', str(existing.get("anonymized", True))).lower() in {'1', 'true', 'yes', 'on'}
    specs = {
        **(existing.get("specs") or {}),
        "library_type": library_type,
        "allowed_for_bid": allowed_for_bid,
        "applicable_volumes": applicable_volumes,
        "usage_note": request.form.get('usage_note') or (existing.get("specs") or {}).get("usage_note") or '',
        "certificate_no": request.form.get('certificate_no') or (existing.get("specs") or {}).get("certificate_no") or '',
        "issuer": request.form.get('issuer') or (existing.get("specs") or {}).get("issuer") or '',
        "product_model": request.form.get('product_model') or (existing.get("specs") or {}).get("product_model") or '',
    }
    metadata = {
        **(existing.get("metadata") or {}),
        "library_type": library_type,
        "allowed_for_bid": allowed_for_bid,
        "applicable_volumes": applicable_volumes,
        "upload_source": "enterprise_library_page",
    }
    if storage_info:
        metadata.update({
            "thumbnail_storage_bucket": storage_info.get("thumbnail_bucket"),
            "thumbnail_storage_path": storage_info.get("thumbnail_path"),
            "thumbnail_mime_type": storage_info.get("thumbnail_mime_type"),
            "thumbnail_size": storage_info.get("thumbnail_size"),
        })

    payload = {
        "title": title,
        "description": description,
        "category": category,
        "asset_type": asset_type,
        "source_type": existing.get("source_type") or "user_upload",
        "license": request.form.get('license') or existing.get("license") or "企业自有资料",
        "attribution": request.form.get('attribution') or existing.get("attribution") or "用户上传",
        "is_synthetic": bool(existing.get("is_synthetic", False)),
        "is_sensitive": is_sensitive,
        "anonymized": anonymized,
        "industry": existing.get("industry") or "水利行业",
        "applicable_sections": applicable_sections,
        "applicable_volumes": applicable_volumes,
        "tags": tags,
        "specs": specs,
        "ai_caption": description,
        "status": "indexed",
        "metadata": metadata,
    }
    if storage_info:
        payload.update({
            "file_name": storage_info.get("file_name"),
            "file_ext": storage_info.get("file_ext"),
            "mime_type": storage_info.get("mime_type"),
            "file_size": storage_info.get("file_size"),
            "storage_bucket": storage_info.get("bucket"),
            "storage_path": storage_info.get("object_path"),
            "public_url": storage_info.get("public_url"),
        })
    payload["searchable_text"] = _build_asset_searchable_text(payload)
    return payload


def _maybe_attach_asset_embedding(payload: dict) -> None:
    try:
        from backend.rag.vector_store import init_ali_client, get_embeddings
        embeddings = get_embeddings(init_ali_client(), [payload["searchable_text"]])
        if embeddings:
            payload["embedding"] = embeddings[0]
    except Exception:
        logging.exception("知识资产 embedding 生成失败，将仅保存结构化资产")


@knowledge_bp.route('/assets', methods=['GET'])
@bp.route('/knowledge/assets', methods=['GET'])
def get_knowledge_assets():
    try:
        asset_type = request.args.get('asset_type')
        category = request.args.get('category')
        assets = list_knowledge_assets(asset_type=asset_type, category=category)
        return jsonify(assets), 200
    except Exception as e:
        logging.exception("查询知识资产列表失败")
        return jsonify({'error': f'查询失败: {str(e)}'}), 500


@knowledge_bp.route('/assets/<asset_id>', methods=['GET'])
@bp.route('/knowledge/assets/<asset_id>', methods=['GET'])
def get_knowledge_asset(asset_id):
    try:
        asset = get_knowledge_asset_detail(asset_id)
        if not asset:
            return jsonify({'error': '知识资产不存在'}), 404
        return jsonify(asset), 200
    except Exception as e:
        logging.exception("查询知识资产详情失败")
        return jsonify({'error': f'查询失败: {str(e)}'}), 500


@knowledge_bp.route('/assets/<asset_id>/file', methods=['GET'])
@bp.route('/knowledge/assets/<asset_id>/file', methods=['GET'])
def get_knowledge_asset_file(asset_id):
    try:
        variant = request.args.get("variant") or "original"

        # 先查进程内缓存，命中则直接返回，避免重复从 Supabase Storage 下载
        cached = _get_cached_asset_file(asset_id, variant)
        if cached:
            asset, data = cached
            mime_type = asset.get("mime_type") or "application/octet-stream"
            filename = asset.get("file_name") or asset.get("title") or asset_id
            return Response(
                data,
                mimetype=mime_type,
                headers={
                    "Content-Disposition": f"inline; filename*=UTF-8''{requests.utils.quote(str(filename))}",
                    "Cache-Control": "private, max-age=86400" if variant == "thumb" else "private, max-age=300",
                    "X-Cache": "HIT",
                },
            )

        result = download_knowledge_asset_file_variant(asset_id, variant=variant)
        if not result:
            return jsonify({'error': '知识资产文件不存在'}), 404

        asset, data = result
        # 写入缓存（只缓存合理大小的图片，超过 8 MB 的不缓存避免内存压力）
        if len(data) <= 8 * 1024 * 1024:
            _put_cached_asset_file(asset_id, variant, (asset, data))

        mime_type = asset.get("mime_type") or "application/octet-stream"
        filename = asset.get("file_name") or asset.get("title") or asset_id
        return Response(
            data,
            mimetype=mime_type,
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{requests.utils.quote(str(filename))}",
                "Cache-Control": "private, max-age=86400" if variant == "thumb" else "private, max-age=300",
                "X-Cache": "MISS",
            },
        )
    except Exception as e:
        logging.exception("读取知识资产文件失败")
        return jsonify({'error': f'读取文件失败: {str(e)}'}), 500


@knowledge_bp.route('/assets/signed-urls', methods=['POST'])
@bp.route('/knowledge/assets/signed-urls', methods=['POST'])
def get_knowledge_asset_signed_urls_api():
    """
    批量生成知识资产的 Supabase Storage 签名 URL。

    请求体：{ "assetIds": ["uuid1", "uuid2", ...], "expiresIn": 3600 }
    返回：{ "urls": { "uuid1": "https://...", "uuid2": "https://..." } }

    前端拿到签名 URL 后直接请求 Supabase CDN，无需经过后端中转，
    彻底消除章节配图时的串行下载瓶颈。
    """
    try:
        payload = request.get_json(silent=True) or {}
        asset_ids = payload.get("assetIds") or []
        expires_in = int(payload.get("expiresIn") or 3600)
        expires_in = max(60, min(expires_in, 7 * 24 * 3600))  # 限制在 1 分钟到 7 天之间

        if not isinstance(asset_ids, list) or not asset_ids:
            return jsonify({"urls": {}}), 200

        # 最多一次处理 50 个，防止滥用
        asset_ids = [str(aid) for aid in asset_ids[:50] if aid]

        urls = get_knowledge_asset_signed_urls(asset_ids, expires_in=expires_in)
        return jsonify({"urls": urls}), 200
    except Exception as e:
        logging.exception("批量生成资产签名 URL 失败")
        return jsonify({"error": f"生成签名 URL 失败: {str(e)}"}), 500


@knowledge_bp.route('/assets/upload', methods=['POST'])
@bp.route('/knowledge/assets/upload', methods=['POST'])
def upload_knowledge_asset():
    try:
        file = request.files.get('file')
        if not file or not file.filename:
            return jsonify({'error': '请上传图片或附件文件'}), 400
        try:
            validate_uploaded_file(file, kind="asset")
        except UploadValidationError as exc:
            return jsonify({'error': str(exc)}), 400

        upload_dir = Path(current_app.config['UPLOAD_FOLDER'])
        upload_dir.mkdir(parents=True, exist_ok=True)
        original_filename = file.filename
        unique_filename = f"asset-{uuid.uuid4()}-{safe_upload_filename(original_filename, 'asset')}"
        local_path = upload_dir / unique_filename
        file.save(local_path)

        storage_info = upload_knowledge_asset_file(
            local_file_path=local_path,
            original_filename=original_filename,
            library_type=request.form.get('library_type') or 'qualification',
        )
        storage_info["file_name"] = original_filename

        payload = _asset_payload_from_form(storage_info=storage_info)
        _maybe_attach_asset_embedding(payload)

        asset = create_knowledge_asset(payload)
        return jsonify(asset), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.exception("上传知识资产失败")
        return jsonify({'error': f'上传失败: {str(e)}'}), 500


@knowledge_bp.route('/assets/<asset_id>', methods=['PATCH'])
@bp.route('/knowledge/assets/<asset_id>', methods=['PATCH'])
def update_knowledge_asset_api(asset_id):
    try:
        existing = get_knowledge_asset_detail(asset_id)
        if not existing:
            return jsonify({'error': '知识资产不存在'}), 404

        file = request.files.get('file')
        storage_info = None
        if file and file.filename:
            try:
                validate_uploaded_file(file, kind="asset")
            except UploadValidationError as exc:
                return jsonify({'error': str(exc)}), 400
            library_type = request.form.get('library_type') or (existing.get("metadata") or {}).get("library_type") or (existing.get("specs") or {}).get("library_type") or 'qualification'
            upload_dir = Path(current_app.config['UPLOAD_FOLDER'])
            upload_dir.mkdir(parents=True, exist_ok=True)
            original_filename = file.filename
            unique_filename = f"asset-{uuid.uuid4()}-{safe_upload_filename(original_filename, 'asset')}"
            local_path = upload_dir / unique_filename
            file.save(local_path)
            storage_info = upload_knowledge_asset_file(
                local_file_path=local_path,
                original_filename=original_filename,
                library_type=library_type,
            )
            storage_info["file_name"] = original_filename

        payload = _asset_payload_from_form(storage_info=storage_info, existing=existing)
        _maybe_attach_asset_embedding(payload)
        asset = update_knowledge_asset(asset_id, payload)
        return jsonify(asset), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.exception("更新知识资产失败")
        return jsonify({'error': f'更新失败: {str(e)}'}), 500

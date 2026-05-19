"""
项目与历史记录路由模块。

负责：
  - POST   /api/bidding/upload                          上传招标文件
  - GET    /api/bidding/history                         历史记录列表
  - POST   /api/bidding/history/<project_id>/retry-parse 重试解析
  - DELETE /api/bidding/history/<project_id>            删除历史项目
  - GET    /api/bidding/interpretations/latest          获取最新解读

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import current_app, jsonify, request

from backend.api._shared import bp, temp_analysis_store, _temp_store_lock  # noqa: F401
from backend.core.security import UploadValidationError, safe_upload_filename, validate_uploaded_file
from backend.db.supabase_repo import (
    delete_bid_project,
    download_bid_file_to_local,
    get_latest_bid_file_for_project,
    get_project_interpretation,
    list_bid_history,
    list_recent_bid_projects,
    sync_uploaded_tender_to_supabase,
    update_bid_file_parse_status,
)
from backend.parsing.document_parser import (
    parse_and_index_tender_file,
    read_parse_status,
    write_parse_status,
)


# ---------------------------------------------------------------------------
# 私有辅助函数（仅本模块使用）
# ---------------------------------------------------------------------------

def _find_local_parse_status_for_supabase_file(supabase_file_id):
    if not supabase_file_id:
        return None
    status_root = Path("parsed_outputs")
    if not status_root.exists():
        return None
    latest_status = None
    latest_mtime = 0.0
    for status_path in status_root.glob("*/mineru_status.json"):
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("supabase_file_id") != supabase_file_id:
            continue
        mtime = status_path.stat().st_mtime
        if mtime >= latest_mtime:
            latest_mtime = mtime
            payload["_parse_id"] = status_path.parent.name
            latest_status = payload
    return latest_status


def _sync_and_parse_tender_in_background(file_path, original_filename, parse_id, supabase_sync=None):
    """后台线程：同步 Supabase 并触发 MinerU/OCR 解析。"""
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


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

@bp.route('/upload', methods=['POST'])
def upload_bidding():
    """上传招标文件 —— 仅保存文件并写入 DB，不生成 OnlyOffice 配置"""
    if 'file' not in request.files:
        return jsonify({'error': '未接收到招标文件，请重新上传。'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择招标文件，请选择后重新上传。'}), 400
    try:
        validate_uploaded_file(file, kind="tender")
    except UploadValidationError as exc:
        return jsonify({'error': str(exc)}), 400

    user_id = request.form.get('userId')
    if not user_id:
        return jsonify({'error': '未获取到当前操作人员身份，请刷新页面后重试。'}), 400

    try:
        original_filename = file.filename
        safe_filename = safe_upload_filename(original_filename, "tender")
        unique_filename = f"{uuid.uuid4()}-{safe_filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)

        file.save(file_path)

        parse_id = str(uuid.uuid4())
        write_parse_status(parse_id, {
            "parse_status": "uploaded",
            "parser": "mineru",
            "source_file": file_path,
            "file_name": original_filename,
        })

        supabase_sync = sync_uploaded_tender_to_supabase(file_path, original_filename)
        project_id = supabase_sync.get('project', {}).get('id')
        supabase_file_id = supabase_sync.get('file', {}).get('id')
        if not project_id or not supabase_file_id:
            return jsonify({'error': 'Supabase 项目或文件记录创建失败，请检查数据库配置。'}), 500

        write_parse_status(parse_id, {
            "parse_status": "supabase_synced",
            "parser": "mineru",
            "source_file": file_path,
            "file_name": original_filename,
            "project_id": project_id,
            "supabase_file_id": supabase_file_id,
        })

        threading.Thread(
            target=_sync_and_parse_tender_in_background,
            args=(file_path, original_filename, parse_id, supabase_sync),
            daemon=True,
        ).start()

        return jsonify({
            'message': '招标文件已上传，正在后台解析并生成结构化数据。',
            'biddingId': None,
            'originalFilename': original_filename,
            'projectId': project_id,
            'fileId': parse_id,
            'supabaseFileId': supabase_file_id,
            'supabaseSynced': True,
            'supabaseSyncError': None
        }), 201

    except Exception as e:
        logging.exception("招标文件上传处理失败")
        return jsonify({'error': f'招标文件上传处理失败: {str(e)}'}), 500


@bp.route('/interpretations/latest', methods=['GET'])
def get_latest_interpretation():
    """获取最近一个已有结构化解读的招标项目。"""
    try:
        projects = list_recent_bid_projects(limit=20)
        for project in projects:
            try:
                payload = get_project_interpretation(project["id"])
            except Exception:
                logging.exception("跳过异常历史项目，继续查询最新招标解读: %s", project.get("id"))
                continue
            if payload.get("analysis"):
                return jsonify(payload)
        return jsonify({
            'project': projects[0] if projects else None,
            'analysis': None,
            'requirements': [],
            'risks': [],
            'scoringItems': [],
            'chapterSuggestions': [],
            'documentChunks': [],
        })
    except Exception as e:
        logging.exception("查询最新招标解读失败")
        return jsonify({'error': f'查询最新招标解读失败: {str(e)}'}), 500


@bp.route('/history', methods=['GET'])
def get_bid_history():
    try:
        limit = int(request.args.get("limit", 100))
        items = list_bid_history(limit=limit)
        for item in items:
            local_status = _find_local_parse_status_for_supabase_file(item.get("latest_file_id"))
            if not local_status:
                continue
            parse_status = local_status.get("parse_status") or item.get("parse_status")
            item["parse_status"] = parse_status
            item["parse_task_id"] = local_status.get("_parse_id")
            item["parse_error"] = (
                local_status.get("user_message")
                or local_status.get("error")
                or local_status.get("reason")
                or local_status.get("supabase_sync_error")
            )
            item["parse_raw_error"] = (
                local_status.get("error")
                or local_status.get("reason")
                or local_status.get("supabase_sync_error")
            )
            item["parse_retryable"] = bool(local_status.get("retryable"))
            item["parse_failure_stage"] = local_status.get("failure_stage")
            item["parse_error_type"] = local_status.get("error_type")
            item["parse_download_retry_count"] = int(local_status.get("download_retry_count") or 0)
            item["parse_updated_at"] = local_status.get("updated_at")
            if parse_status in {
                "mineru_failed",
                "index_failed",
                "ocr_required",
                "mineru_download_failed",
                "mineru_import_failed",
                "supabase_sync_failed",
            }:
                item["stage"] = "解析失败"
                item["action"] = "查看"
                item["parse_retryable"] = True
            elif parse_status in {
                "uploaded",
                "pending",
                "syncing_supabase",
                "supabase_synced",
                "mineru_submitted",
                "mineru_running",
                "mineru_split_submitted",
                "mineru_split_running",
                "mineru_downloading",
                "mineru_download_retrying",
                "mineru_importing_zip",
                "mineru_fallback_native",
            } and not item.get("chunk_count"):
                item["stage"] = "解析中"
                item["action"] = "查看状态"
        return jsonify({"items": items}), 200
    except Exception as e:
        logging.exception("查询历史记录失败")
        return jsonify({'error': f'查询历史记录失败: {str(e)}'}), 500


@bp.route('/history/<project_id>/retry-parse', methods=['POST'])
def retry_bid_history_parse(project_id):
    try:
        uuid.UUID(project_id)
        file_record = get_latest_bid_file_for_project(project_id)
        if not file_record:
            return jsonify({'error': '未找到该项目的招标文件记录，无法重试解析。'}), 404

        local_status = _find_local_parse_status_for_supabase_file(file_record.get("id")) or {}
        source_file = local_status.get("source_file")
        if source_file and Path(source_file).exists():
            local_path = Path(source_file)
        else:
            local_path = download_bid_file_to_local(file_record, current_app.config['UPLOAD_FOLDER'])

        parse_id = str(uuid.uuid4())
        original_filename = file_record.get("file_name") or local_path.name
        update_bid_file_parse_status(file_record["id"], "pending")
        write_parse_status(parse_id, {
            "parse_status": "supabase_synced",
            "parser": "mineru",
            "source_file": str(local_path),
            "file_name": original_filename,
            "project_id": project_id,
            "supabase_file_id": file_record["id"],
            "retry_from": local_status.get("_parse_id"),
        })
        threading.Thread(
            target=parse_and_index_tender_file,
            kwargs={
                "file_path": str(local_path),
                "original_filename": original_filename,
                "parse_id": parse_id,
                "supabase_file_id": file_record["id"],
            },
            daemon=True,
        ).start()
        return jsonify({
            "message": "解析重试任务已启动",
            "projectId": project_id,
            "fileId": parse_id,
            "supabaseFileId": file_record["id"],
        }), 202
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400
    except Exception as e:
        logging.exception("重试解析历史记录失败: %s", project_id)
        return jsonify({'error': f'重试解析失败: {str(e)}'}), 500


@bp.route('/history/<project_id>', methods=['DELETE'])
def delete_bid_history_project(project_id):
    try:
        delete_bid_project(project_id)
        return jsonify({"message": "历史项目已删除", "projectId": project_id}), 200
    except Exception as e:
        logging.exception("删除历史项目失败: %s", project_id)
        return jsonify({'error': f'删除历史项目失败: {str(e)}'}), 500

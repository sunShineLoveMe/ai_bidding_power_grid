"""
MinerU 解析状态路由模块。

负责：
  - GET  /api/bidding/parse-status/<file_id>              查询解析状态
  - POST /api/bidding/parse-status/<file_id>/result-zip   手动上传 MinerU 结果 zip
  - POST /api/bidding/parse-status/<file_id>/ingest       触发 MinerU 产物落库

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import jsonify, request

from backend.api._shared import bp
from backend.core.security import UploadValidationError, validate_uploaded_file
from backend.db.supabase_repo import get_bid_file
from backend.parsing.document_parser import (
    ingest_artifacts as ingest_mineru_artifacts_to_supabase,
    import_mineru_result_zip,
    read_parse_status,
    retry_mineru_result_download,
    write_parse_status,
)
from backend.api.projects import _find_local_parse_status_for_supabase_file, _sync_and_parse_tender_in_background


def _uuid_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


@bp.route('/parse-status/<file_id>', methods=['GET'])
def get_parse_status(file_id):
    """查询招标文件解析状态，合并 Supabase 当前状态与本地 MinerU 产物状态。"""
    try:
        local_status = read_parse_status(file_id) or {}
        hinted_project_id = _uuid_or_none(request.args.get("projectId"))
        hinted_supabase_file_id = _uuid_or_none(request.args.get("supabaseFileId"))
        bind_payload = {}
        if hinted_project_id and not local_status.get("project_id"):
            bind_payload["project_id"] = hinted_project_id
        if hinted_supabase_file_id and not local_status.get("supabase_file_id"):
            bind_payload["supabase_file_id"] = hinted_supabase_file_id
        if bind_payload:
            write_parse_status(file_id, bind_payload)
            local_status = read_parse_status(file_id) or local_status

        parse_status = local_status.get("parse_status")
        source_file = local_status.get("source_file")
        recovery_started_at = local_status.get("parse_recovery_started_at")
        recovery_is_stale = True
        if recovery_started_at:
            try:
                started_at = datetime.fromisoformat(str(recovery_started_at).replace("Z", ""))
                recovery_is_stale = (datetime.utcnow() - started_at).total_seconds() > int(
                    os.getenv("PARSE_RECOVERY_STALE_SECONDS", "120")
                )
            except Exception:
                recovery_is_stale = True
        if (
            parse_status == "supabase_synced"
            and source_file
            and os.path.exists(str(source_file))
            and not local_status.get("batch_id")
            and recovery_is_stale
        ):
            write_parse_status(file_id, {
                "parse_recovery_started_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "user_message": "后台解析任务未继续推进，系统正在自动恢复解析。",
                "retryable": True,
            })
            supabase_sync = {
                "project": {"id": local_status.get("project_id")},
                "file": {"id": local_status.get("supabase_file_id")},
            }
            threading.Thread(
                target=_sync_and_parse_tender_in_background,
                args=(str(source_file), local_status.get("file_name") or Path(str(source_file)).name, file_id, supabase_sync),
                daemon=True,
            ).start()
            local_status = read_parse_status(file_id) or local_status

        download_retry_count = int(local_status.get("download_retry_count") or 0)
        max_download_retries = int(os.getenv("MINERU_DOWNLOAD_AUTO_RETRIES", "6"))
        retry_started_at = local_status.get("download_retry_started_at")
        retry_is_stale = True
        if retry_started_at:
            try:
                started_at = datetime.fromisoformat(str(retry_started_at).replace("Z", ""))
                retry_is_stale = (datetime.utcnow() - started_at).total_seconds() > int(
                    os.getenv("MINERU_DOWNLOAD_RETRY_STALE_SECONDS", "120")
                )
            except Exception:
                retry_is_stale = True
        if (
            local_status.get("parse_status") in {"mineru_failed", "mineru_download_failed", "mineru_download_retrying"}
            and local_status.get("batch_id")
            and local_status.get("mineru_state") == "done"
            and not local_status.get("artifacts")
            and download_retry_count < max_download_retries
            and (
                local_status.get("parse_status") != "mineru_download_retrying"
                or retry_is_stale
            )
        ):
            write_parse_status(file_id, {
                "parse_status": "mineru_download_retrying",
                "user_message": "MinerU 结果下载失败，系统正在自动断点重试。",
                "retryable": True,
            })
            threading.Thread(target=retry_mineru_result_download, args=(file_id,), daemon=True).start()
            local_status = read_parse_status(file_id) or local_status

        artifacts = local_status.get("artifacts")
        ingest_status = local_status.get("supabase_ingest_status")
        if (
            artifacts
            and local_status.get("project_id")
            and ingest_status in {None, "skipped", "failed"}
        ):
            write_parse_status(file_id, {
                "supabase_ingest_status": "running",
                "supabase_ingest_reason": None,
                "user_message": "解析结果已下载，正在补充写入项目解读数据。",
                "retryable": True,
            })
            threading.Thread(
                target=ingest_mineru_artifacts_to_supabase,
                args=(file_id, artifacts),
                daemon=True,
            ).start()
            local_status = read_parse_status(file_id) or local_status

        supabase_file = None
        supabase_lookup_id = local_status.get("supabase_file_id") or file_id
        try:
            uuid.UUID(supabase_lookup_id)
            if local_status.get("supabase_file_id") or not local_status:
                supabase_file = get_bid_file(supabase_lookup_id)
        except ValueError:
            logging.warning("跳过 Supabase 查询，file_id 不是合法 UUID: %s", supabase_lookup_id)
        except Exception:
            logging.exception("查询 Supabase bid_files 失败: %s", supabase_lookup_id)

        effective_status = local_status.get('parse_status') or (supabase_file or {}).get('parse_status')
        ingest_done = local_status.get("supabase_ingest_status") == "done"
        has_artifacts = bool(local_status.get("artifacts"))
        parse_completed = effective_status == "indexed" or (ingest_done and has_artifacts)
        user_message = None if parse_completed else local_status.get('user_message')

        return jsonify({
            'fileId': file_id,
            'parseStatus': effective_status,
            'parseCompleted': parse_completed,
            'failureStage': local_status.get('failure_stage'),
            'errorType': local_status.get('error_type'),
            'error': local_status.get('error') or local_status.get('reason'),
            'userMessage': user_message,
            'retryable': bool(local_status.get('retryable')) and not parse_completed,
            'downloadRetryCount': int(local_status.get('download_retry_count') or 0),
            'supabaseFile': supabase_file,
            'mineru': local_status,
        })
    except Exception as e:
        logging.exception("查询解析状态失败: %s", file_id)
        return jsonify({'error': f'查询解析状态失败: {str(e)}'}), 500


@bp.route('/parse-status/<file_id>/result-zip', methods=['POST'])
def upload_mineru_result_zip(file_id):
    """手动上传 MinerU 结果 zip，用于本机无法访问 MinerU CDN 的场景。"""
    if 'file' not in request.files:
        return jsonify({'error': '未接收到 MinerU 结果 zip 文件。'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择 MinerU 结果 zip 文件。'}), 400
    try:
        validate_uploaded_file(file, kind="mineru_zip")
    except UploadValidationError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        output_dir = Path("parsed_outputs") / file_id
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / "manual_mineru_result.zip"
        file.save(zip_path)
        artifacts = import_mineru_result_zip(file_id, zip_path)
        return jsonify({
            'message': 'MinerU 结果 zip 已导入并完成解析产物处理。',
            'fileId': file_id,
            'artifacts': artifacts,
        })
    except Exception as e:
        logging.exception("导入 MinerU 结果 zip 失败: %s", file_id)
        write_parse_status(file_id, {"parse_status": "mineru_import_failed", "error": str(e)})
        return jsonify({'error': f'导入 MinerU 结果 zip 失败: {str(e)}'}), 500


@bp.route('/parse-status/<file_id>/ingest', methods=['POST'])
def ingest_mineru_artifacts(file_id):
    """将已完成的 MinerU 解析产物写入 Supabase 业务表。"""
    try:
        local_status = read_parse_status(file_id) or {}
        artifacts = local_status.get("artifacts")
        if not artifacts:
            return jsonify({'error': '当前任务尚无 MinerU 解析产物，请等待 mineru_done。'}), 400
        project_id = _uuid_or_none((request.get_json(silent=True) or {}).get("projectId") or request.form.get("projectId"))
        supabase_file_id = _uuid_or_none((request.get_json(silent=True) or {}).get("supabaseFileId") or request.form.get("supabaseFileId"))
        bind_payload = {}
        if project_id and not local_status.get("project_id"):
            bind_payload["project_id"] = project_id
        if supabase_file_id and not local_status.get("supabase_file_id"):
            bind_payload["supabase_file_id"] = supabase_file_id
        if bind_payload:
            write_parse_status(file_id, bind_payload)

        threading.Thread(target=ingest_mineru_artifacts_to_supabase, args=(file_id, artifacts), daemon=True).start()
        return jsonify({
            'message': 'MinerU 解析产物已进入 Supabase 落库任务。',
            'fileId': file_id,
        })
    except Exception as e:
        logging.exception("触发 MinerU 产物落库失败: %s", file_id)
        return jsonify({'error': f'触发 MinerU 产物落库失败: {str(e)}'}), 500

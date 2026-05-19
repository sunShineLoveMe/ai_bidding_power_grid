"""
OnlyOffice 集成路由模块。

负责：
  - POST /api/bidding/interpretations/<project_id>/onlyoffice-config  生成 ONLYOFFICE 编辑配置
  - POST /api/bidding/save-callback                                    OnlyOffice 保存回调

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
辅助函数（_onlyoffice_jwt_secret、get_backend_public_base_url 等）保留在 routes.py，
此处通过导入使用，避免循环依赖。
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from pathlib import Path

import jwt
import requests

from flask import current_app, jsonify, request

from backend.api._shared import bp
from backend.db.supabase_repo import get_onlyoffice_document
from backend.export.md_to_word import convert_md_to_word, refresh_docx_fields_with_soffice
from backend.api.routes import (
    _onlyoffice_jwt_secret,
    get_backend_public_base_url,
    get_backend_self_base_url,
    save_onlyoffice_document_mapping,
    build_project_bid_markdown,
    _display_filename,
    _slug_filename,
    _output_url_for_path,
    _absolute_output_url_for_path,
    get_db,
)


@bp.route('/interpretations/<project_id>/onlyoffice-config', methods=['POST'])
def generate_onlyoffice_config(project_id):
    """基于 bid_sections 生成 DOCX，并返回 ONLYOFFICE editorConfig。"""
    try:
        uuid.UUID(project_id)
    except ValueError:
        return jsonify({'error': 'project_id 不是合法 UUID。'}), 400

    try:
        request_payload = request.get_json(silent=True) or {}
        focus_section_id = request_payload.get("sectionId")
        if focus_section_id:
            try:
                uuid.UUID(focus_section_id)
            except ValueError:
                focus_section_id = None

        markdown_path, project_name, _ = build_project_bid_markdown(project_id, focus_section_id)
        generated_docx_path = convert_md_to_word(markdown_path)
        if not generated_docx_path or not Path(generated_docx_path).exists():
            raise RuntimeError("DOCX 生成失败，未找到输出文件。")

        generated_docx_path = Path(generated_docx_path)
        generated_docx_path, _ = refresh_docx_fields_with_soffice(generated_docx_path)
        gen_folder = Path(current_app.config.get('GENERATED_FOLDER', 'outputs'))
        gen_folder.mkdir(parents=True, exist_ok=True)

        target_name = generated_docx_path.name
        target = gen_folder / target_name
        if generated_docx_path.resolve() != target.resolve():
            shutil.copy2(str(generated_docx_path), str(target))

        backend_url = get_backend_public_base_url()
        file_url = _absolute_output_url_for_path(target)
        callback_url = f"{backend_url}/api/bidding/save-callback"
        doc_key = str(uuid.uuid4())
        display_title = f"{project_name}.docx"

        payload = {
            'document': {
                'fileType': 'docx',
                'key': doc_key,
                'title': display_title,
                'url': file_url,
                'permissions': {
                    'chat': False,
                    'comment': False,
                    'copy': True,
                    'download': True,
                    'edit': True,
                    'fillForms': False,
                    'modifyContentControl': False,
                    'modifyFilter': False,
                    'print': True,
                    'protect': False,
                    'review': False,
                },
            },
            'documentType': 'word',
            'editorConfig': {
                'callbackUrl': callback_url,
                'lang': 'zh-CN',
                'region': 'zh-CN',
                'mode': 'edit',
                'user': {
                    'id': f"project-{project_id[:8]}",
                    'name': '企业标书编制岗',
                },
                'customization': {
                    'autosave': True,
                    'chat': False,
                    'comments': False,
                    'compactHeader': True,
                    'compactToolbar': True,
                    'feedback': False,
                    'forcesave': True,
                    'help': False,
                    'hideRightMenu': True,
                    'hideRulers': False,
                    'toolbarNoTabs': True,
                    'uiTheme': 'theme-light',
                },
            }
        }
        token = jwt.encode(payload, _onlyoffice_jwt_secret(), algorithm='HS256')
        editor_config_with_token = {**payload, 'token': token}

        save_onlyoffice_document_mapping(
            document_key=doc_key,
            project_id=project_id,
            title=project_name,
            file_path=str(target),
            download_url=_output_url_for_path(target),
        )

        return jsonify({
            'message': 'ONLYOFFICE 配置生成成功',
            'markdown': str(markdown_path),
            'editorConfig': editor_config_with_token,
            'fileUrl': file_url,
            'downloadUrl': _output_url_for_path(target),
        }), 201
    except Exception as e:
        logging.exception("生成 ONLYOFFICE 配置失败: %s", project_id)
        return jsonify({'error': f'生成 ONLYOFFICE 配置失败: {str(e)}'}), 500


@bp.route('/save-callback', methods=['POST'])
def save_callback():
    """OnlyOffice 保存回调"""
    try:
        body = request.get_json(force=True)
        logging.info(f'[INFO] Save callback received: {json.dumps(body, indent=2, ensure_ascii=False)}')

        # OnlyOffice status 2 = readyForSave, 6 = mustSave
        if body.get('status') in [2, 6]:
            download_url = body.get('url')
            document_key = body.get('key')

            if not download_url:
                logging.warning(f'No download URL provided for key {document_key}')
                return jsonify({'error': 0})

            doc_row = None
            try:
                doc_row = get_onlyoffice_document(document_key)
            except Exception:
                logging.exception("Supabase onlyoffice_documents 查询失败，回退 SQLite: %s", document_key)
                conn = get_db()
                try:
                    cursor = conn.cursor()
                    cursor.execute('SELECT * FROM onlyoffice_documents WHERE document_key = ?', (document_key,))
                    doc_row = cursor.fetchone()
                finally:
                    conn.close()

            if doc_row:
                target_path = doc_row['file_path']
                Path(target_path).parent.mkdir(parents=True, exist_ok=True)
                resp = requests.get(download_url, stream=True, timeout=60)
                resp.raise_for_status()
                with open(target_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                logging.info('ONLYOFFICE 文档已保存到 %s', target_path)
                return jsonify({'error': 0})

            conn = get_db()
            try:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM bidding WHERE document_key = ?', (document_key,))
                bidding = cursor.fetchone()

                if not bidding:
                    logging.error(f'Bidding with key {document_key} not found')
                    return jsonify({'error': 0})

                target_path = bidding['bid_document'] or bidding['storage_path']
                Path(target_path).parent.mkdir(parents=True, exist_ok=True)

                resp = requests.get(download_url, stream=True, timeout=60)
                resp.raise_for_status()
                with open(target_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # 更新 DB 状态为已编辑，并保存 bid_document 路径
                cursor.execute('UPDATE bidding SET status=?, bid_document=? WHERE id=?',
                               ('已编辑', target_path, bidding['id']))
                conn.commit()
                logging.info(f'投标文件 {bidding["original_filename"]} 已保存至 {target_path}')
            finally:
                conn.close()

        # OnlyOffice 要求返回 { "error": 0 }
        return jsonify({'error': 0})

    except Exception as e:
        logging.exception('OnlyOffice 保存回调处理失败')
        return jsonify({'error': 0})

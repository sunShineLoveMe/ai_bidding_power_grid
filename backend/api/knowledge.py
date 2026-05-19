"""
知识库路由模块。

负责（每条路由均双蓝图注册）：
  - POST /api/knowledge/upload + /api/bidding/knowledge/upload                上传知识文档
  - POST /api/knowledge/search + /api/bidding/knowledge/search                知识库检索问答
  - POST /api/knowledge/search/stream + /api/bidding/knowledge/search/stream  流式检索问答
  - POST /api/knowledge/followups + /api/bidding/knowledge/followups          生成追问建议
  - GET  /api/knowledge/documents + /api/bidding/knowledge/documents          查询文档列表
  - GET  /api/knowledge/documents/<id> + /api/bidding/knowledge/documents/<id> 查询文档详情

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from pathlib import Path

from flask import Response, current_app, jsonify, request, stream_with_context

from backend.api._shared import bp, knowledge_bp
from backend.ai.qwen_client import call_dashscope_api
from backend.core.bid_volumes import asset_applicable_volumes
from backend.core.config import get_stage_model
from backend.core.llm_json_utils import strip_llm_json
from backend.core.security import UploadValidationError, safe_upload_filename, validate_uploaded_file
from backend.db.supabase_repo import (
    get_knowledge_document_detail,
    list_knowledge_documents,
)
from backend.parsing.document_parser import write_parse_status
from backend.rag.ingestion import (
    create_knowledge_document,
    ingest_knowledge_document,
    update_knowledge_document_status,
)
from backend.rag.retrieval import (
    generate_knowledge_answer,
    search_knowledge_assets,
    search_knowledge_base,
    stream_knowledge_answer,
)


def sync_and_parse_knowledge_in_background(file_path, original_filename, parse_id, document_id):
    try:
        write_parse_status(parse_id, {
            "parse_status": "mineru_submitted",
            "parser": "mineru",
            "source_file": file_path,
            "file_name": original_filename,
        })
        # For simplicity, we directly call mineru tasks here
        # Assuming parse_and_index_tender_file creates the mineru batch, but we want our own ingestion logic
        # So we can use the same run mineru logic but with custom ingestion
        from backend.parsing.document_parser import _run_mineru_parse_and_index, has_mineru_token, _should_use_mineru_first
        from backend.parsing.mineru_client import download_and_extract_zip, wait_for_batch_file_result, create_local_file_batch_task
        
        output_dir = Path("parsed_outputs") / parse_id
        
        task = create_local_file_batch_task(
            local_file_path=file_path,
            file_name=original_filename,
            data_id=parse_id,
        )
        
        def on_progress(result: dict) -> None:
            pass
            
        result = wait_for_batch_file_result(batch_id=task.batch_id, data_id=parse_id, on_progress=on_progress)
        full_zip_url = result.get("full_zip_url")
        if not full_zip_url:
            raise RuntimeError(f"MinerU finished without full_zip_url")
            
        artifacts = download_and_extract_zip(full_zip_url, output_dir)
        
        # Now call our custom ingestion
        ingest_knowledge_document(
            document_id=document_id,
            original_filename=original_filename,
            markdown_path=artifacts.get("markdown_path"),
            extract_dir=str(output_dir)
        )
        
    except Exception as e:
        logging.exception("知识库解析入库失败")
        update_knowledge_document_status(document_id, "failed")


@knowledge_bp.route('/upload', methods=['POST'])
@bp.route('/knowledge/upload', methods=['POST'])
def upload_knowledge():
    if 'file' not in request.files:
        return jsonify({'error': '未接收到知识库文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择知识库文件'}), 400
    try:
        validate_uploaded_file(file, kind="knowledge")
    except UploadValidationError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        original_filename = file.filename
        safe_filename = safe_upload_filename(original_filename, "knowledge")
        unique_filename = f"{uuid.uuid4()}-{safe_filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        # 1. Create Knowledge Document DB Record
        document_id = create_knowledge_document(
            title=original_filename,
            category="general",
            bucket="knowledge",
            object_path=f"temp/{unique_filename}",
            source_type=Path(original_filename).suffix.lstrip(".")
        )

        parse_id = str(uuid.uuid4())
        
        threading.Thread(
            target=sync_and_parse_knowledge_in_background,
            args=(file_path, original_filename, parse_id, document_id),
            daemon=True,
        ).start()

        return jsonify({
            'message': '知识文档已上传，正在后台提取图文特征',
            'documentId': document_id
        }), 201

    except Exception as e:
        logging.exception("知识库文件上传处理失败")
        return jsonify({'error': f'文件上传失败: {str(e)}'}), 500


@knowledge_bp.route('/search', methods=['POST'])
@bp.route('/knowledge/search', methods=['POST'])
def search_knowledge():
    data = request.get_json()
    query = data.get('query')
    if not query:
        return jsonify({'error': '缺少检索问题 query'}), 400
        
    try:
        # 1. 向量化并检索 Supabase
        contexts = search_knowledge_base(query, match_threshold=0.3, match_count=8)
        assets = search_knowledge_assets(query, match_count=8)
        
        # 2. RAG 生成回答
        result = generate_knowledge_answer(query, contexts, assets)
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.exception("知识库检索问答失败")
        return jsonify({'error': f'检索问答失败: {str(e)}'}), 500


@knowledge_bp.route('/search/stream', methods=['POST'])
@bp.route('/knowledge/search/stream', methods=['POST'])
def stream_search_knowledge():
    data = request.get_json() or {}
    query = (data.get('query') or '').strip()
    if not query:
        return jsonify({'error': '缺少检索问题 query'}), 400

    def is_relevant_knowledge_query(text: str) -> bool:
        keywords = [
            "水利", "水库", "除险", "加固", "招标", "投标", "标书", "资格", "资质", "评标",
            "评分", "废标", "否决", "施工", "监理", "勘察", "设计", "EPC", "总承包",
            "工期", "质量", "安全", "环保", "水保", "防汛", "度汛", "灌区", "泵站",
            "水闸", "堤防", "河道", "合同", "报价", "工程量清单", "投标文件", "招标文件",
            "企业知识库", "企业资信", "资信库", "企业产品", "产品库", "标准话术", "政策法规",
            "水利标准", "章节", "正文", "图片", "附件", "材料", "样张", "业绩", "类似业绩",
            "营业执照", "执照", "许可证", "安全生产许可", "人员", "社保", "缴纳证明",
            "证书", "证件", "产品", "设备", "图册", "参考图", "配图",
        ]
        lowered = text.lower()
        ascii_keywords = ["bid", "tender", "rag", "qualification", "water", "reservoir", "product", "asset", "certificate"]
        return any(keyword in text for keyword in keywords) or any(keyword in lowered for keyword in ascii_keywords)

    def emit(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @stream_with_context
    def generate():
        yield emit({"type": "start"})
        try:
            yield emit({"type": "status", "message": "正在检索企业知识库和图片资产..."})
            contexts = search_knowledge_base(query, match_threshold=0.3, match_count=8)
            assets = search_knowledge_assets(query, match_count=8)
            if not contexts and not assets and not is_relevant_knowledge_query(query):
                yield emit({
                    "type": "chunk",
                    "content": "抱歉，当前企业知识库主要服务于水利招投标、标书编制、企业资信、产品资料、业绩材料、人员证书、施工组织设计和废标风险等问题。这个问题与当前知识库范围不太相关，我暂时不能基于本知识库给出可靠回答。",
                })
                yield emit({"type": "done"})
                return
            yield emit({
                "type": "status",
                "message": f"已召回 {len(contexts)} 条资料、{len(assets)} 个图片资产，正在生成回答..."
            })
            for event in stream_knowledge_answer(query, contexts, assets):
                yield emit(event)
        except Exception as e:
            logging.exception("知识库流式检索问答失败")
            yield emit({"type": "error", "error": "检索问答失败，请查看后端日志。"})

    return Response(generate(), mimetype='text/event-stream')


def _compact_followup_assets(assets: list[dict]) -> list[dict]:
    compacted = []
    for index, asset in enumerate((assets or [])[:8], 1):
        compacted.append({
            "index": index,
            "title": asset.get("title"),
            "category": asset.get("category"),
            "asset_type": asset.get("asset_type"),
            "description": asset.get("description"),
            "tags": asset.get("tags") or [],
            "applicable_sections": asset.get("applicable_sections") or [],
            "applicable_volumes": asset_applicable_volumes(asset),
        })
    return compacted


def _compact_followup_sources(sources: list[dict]) -> list[dict]:
    compacted = []
    for index, source in enumerate((sources or [])[:5], 1):
        metadata = source.get("metadata") or {}
        compacted.append({
            "index": index,
            "title": metadata.get("source_org") or metadata.get("source_file") or metadata.get("category_label") or metadata.get("category"),
            "doc_type": metadata.get("doc_type"),
            "content_preview": str(source.get("content") or "").replace("\n", " ")[:240],
        })
    return compacted


def _normalize_followups(payload: dict) -> dict:
    intent = str(payload.get("intent") or "general_qa").strip() or "general_qa"
    followups = payload.get("followups")
    if not isinstance(followups, list):
        followups = []

    cleaned = []
    seen = set()
    for item in followups:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        if len(text) > 80:
            text = text[:80].rstrip("，。；;,. ") + "？"
        if not text.endswith(("?", "？")):
            text += "？"
        cleaned.append(text)
        seen.add(text)
        if len(cleaned) >= 3:
            break

    return {
        "intent": intent,
        "followups": cleaned,
    }


def _parse_followup_model_content(content) -> dict:
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        parsed = strip_llm_json(content)
        return parsed if isinstance(parsed, dict) else {}
    return {}


@knowledge_bp.route('/followups', methods=['POST'])
@bp.route('/knowledge/followups', methods=['POST'])
def generate_knowledge_followups():
    data = request.get_json() or {}
    question = str(data.get("question") or "").strip()
    answer = str(data.get("answer") or "").strip()
    if not question or not answer:
        return jsonify({"intent": "general_qa", "followups": []}), 200

    assets = data.get("assets") if isinstance(data.get("assets"), list) else []
    sources = data.get("sources") if isinstance(data.get("sources"), list) else []
    prompt_payload = {
        "user_question": question[:800],
        "assistant_answer": answer[:2600],
        "retrieved_assets": _compact_followup_assets(assets),
        "retrieved_sources": _compact_followup_sources(sources),
    }
    prompt = f"""你是 AI 标书系统的企业知识库问答意图识别器。
请根据用户问题、助手回答、召回资料和图片资产，判断用户下一步最可能需要什么，并生成 3 个专业、具体、可点击的后续问题。

要求：
1. 问题必须服务于水利招投标、标书编制、企业资信、产品资料、业绩材料、风险核查或材料入库。
2. 问题要像业务人员自然会追问的话，不能泛泛而谈。
3. 如果回答涉及图片资产，要优先引导"图片适合放在哪个章节""哪些能插入正文/附件""还缺哪些原件或证明"。
4. 如果回答涉及资质、人员、社保、营业执照、许可证，要优先引导材料完整性和废标风险核查。
5. 如果回答涉及产品、设备、参数，要优先引导技术响应配图和参数匹配。
6. 只输出 JSON，不要输出 Markdown，不要解释。

JSON 格式：
{{
  "intent": "asset_lookup | qualification_check | bid_writing | risk_check | product_matching | material_gap | general_qa",
  "followups": ["问题1", "问题2", "问题3"]
}}

输入：
{json.dumps(prompt_payload, ensure_ascii=False)}
"""
    try:
        response = call_dashscope_api(
            [
                {"role": "system", "content": "你只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            model=get_stage_model("knowledge_followup"),
            json_mode=True,
            usage_context={
                "stage": "knowledge_followup_generation",
                "operation_type": "text_generation",
            },
        )
        content = (
            response.get("output", {})
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _parse_followup_model_content(content)
        return jsonify(_normalize_followups(parsed)), 200
    except Exception:
        logging.exception("生成知识库追问建议失败")
        return jsonify({"intent": "general_qa", "followups": []}), 200


@knowledge_bp.route('/documents', methods=['GET'])
@bp.route('/knowledge/documents', methods=['GET'])
def get_knowledge_documents():
    try:
        docs = list_knowledge_documents()
        return jsonify(docs), 200
    except Exception as e:
        logging.exception("查询知识库文档列表失败")
        return jsonify({'error': f'查询失败: {str(e)}'}), 500


@knowledge_bp.route('/documents/<document_id>', methods=['GET'])
@bp.route('/knowledge/documents/<document_id>', methods=['GET'])
def get_knowledge_document(document_id):
    try:
        detail = get_knowledge_document_detail(document_id)
        if not detail:
            return jsonify({'error': '知识库文档不存在'}), 404
        return jsonify(detail), 200
    except Exception as e:
        logging.exception("查询知识库文档详情失败")
        return jsonify({'error': f'查询失败: {str(e)}'}), 500

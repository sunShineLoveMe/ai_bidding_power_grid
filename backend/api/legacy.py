# 旧版标书链路，保留兼容，新链路请使用 /api/bidding/upload → /api/bidding/interpretations/* 流程
"""
旧版标书生成链路路由模块。

负责：
  - POST /api/bidding/pre-analysis_bid       预处理招标文件
  - POST /api/bidding/chapter-analysis_bid   招标文件章节分析
  - POST /api/bidding/chapter-design         投标文件章节设计
  - POST /api/bidding/generate-bid-document  生成完整投标书文件

视图函数逻辑与原 routes.py 完全一致，仅做文件搬迁，不改任何业务逻辑。
"""

from __future__ import annotations

import json
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import jwt

from flask import current_app, jsonify, request

from backend.api._shared import bp, temp_analysis_store, _temp_store_lock
from backend.ai.qwen_client import call_dashscope_api, generate_bid_section
from backend.core.config import build_enterprise_context
from backend.core.llm_json_utils import strip_llm_json
from backend.export.md_to_word import convert_md_to_word, refresh_docx_fields_with_soffice
from backend.rag.vector_store import query_chroma
from backend.api.routes import (
    get_db,
    read_tender_file,
    save_bid_section,
    merge_sections,
    _display_filename,
    _absolute_output_url_for_path,
    _output_url_for_path,
    get_backend_public_base_url,
    _onlyoffice_jwt_secret,
)


@bp.route('/pre-analysis_bid', methods=['POST'])
def pre_analysis_bid():
    """预处理招标文件"""
    data = request.get_json()
    bidding_id = data.get('biddingId')
    if not bidding_id:
        return jsonify({'error': '缺少招标文件业务编号。'}), 400
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bidding WHERE id = ?', (bidding_id,))
        bidding = cursor.fetchone()
        conn.close()
        if not bidding:
            return jsonify({'error': '招标书不存在'}), 404
        # 读取文件内容
        bid_content = read_tender_file(bidding_id)

        enterprise_context = build_enterprise_context()
        pre_analysis_prompt =  f'''
        你是资深招投标文件分析师，熟悉水利工程、设备配套、质量、安全、交付和商务响应要求。
        企业画像：
        {enterprise_context}
        请根据以下招标书内容，提炼出完整信息，并严格按照下面的JSON格式返回你的分析结果，不要有任何多余的解释，只返回以下json内容。
        {{
            "bidding_requirements":"...",
            "bidding_summary":"...",
            "bidding_meta":"..."
        }}
        "bidding_requirements": 必须包含的文件和材料。
        "bidding_summary":对招标书内容的总结，包括采购/施工/供货内容、服务期限、服务地点、质量标准、交付要求、验收要求等。
        "bidding_meta":招标书中具体的实质性要求内容、资质要求、技术规范、商务条款和评分标准。
        招标书内容如下:
        ---
        {bid_content}
        ---
        '''
        response = call_dashscope_api([
            {'role': 'user', 'content': pre_analysis_prompt}
        ])
        # print(f'[INFO] Pre-analysis response: {response}')
        # 兼容不同返回结构
        try:
            http_data = response['output']['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            return jsonify({'error': 'API响应格式错误'}), 500

        try:
            analysis_result = strip_llm_json(http_data)
            # 将 pre-analysis 的结果写入临时存储（如果存在对应的 bidding_id）
            try:
                with _temp_store_lock:
                    if bidding_id in temp_analysis_store:
                        temp_analysis_store[bidding_id]['analysisData'] = analysis_result
                    else:
                        temp_analysis_store[bidding_id] = {
                            'biddingId': bidding_id,
                            'analysisData': analysis_result,
                            'directoryStructure': None,
                        }
            except Exception:
                logging.exception('写入 temp_analysis_store.analysisData 失败')
        except Exception as e:
            logging.exception("招标文件预分析 JSON 解析失败")
            return jsonify({'error': 'API返回内容解析失败'}), 500
        return jsonify(analysis_result)

    except Exception as e:
        logging.exception("招标文件预分析失败，业务编号 %s", bidding_id)
        return jsonify({'error': '预分析失败，请稍后重试。'}), 500        


@bp.route('/chapter-analysis_bid', methods=['POST'])
def chapter_analysis_bid():
    """招标文件章节分析"""
    data = request.get_json()
    
    bidding_id = data.get('biddingId')
    if not bidding_id:
        return jsonify({'error': '缺少招标文件业务编号。'}), 400
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bidding WHERE id = ?', (bidding_id,))
        bidding = cursor.fetchone()
        conn.close()
        if not bidding:
            return jsonify({'error': '招标书不存在'}), 404
        # 读取文件内容
        bid_content = read_tender_file(bidding_id)
        enterprise_context = build_enterprise_context()
        post_analysis_prompt = f'''
        你是资深招投标文件结构分析师，熟悉水利工程投标文件的技术、商务、资质、质量、安全、交付和售后响应要求。
        企业画像：
        {enterprise_context}
        请根据以下招标书内容，输出投标书其他响应文件的格式章节内容（除封面章节），并严格按照下面的JSON格式返回你的分析结果，不要有任何多余的解释。
        {{
            "chapter_format":"..."
        }}
        "chapter_format":招标书中的其他响应文件格式，如果有表格内容，请用Markdown表格的形式返回。
        招标书内容如下:
        ---
        {bid_content}
        ---
        '''
        response = call_dashscope_api([
                {'role': 'user', 'content': post_analysis_prompt}
            ])
        try:
             http_data = response['output']['choices'][0]['message']['content']
             temp_analysis_store[bidding_id]['directoryStructure'] = http_data
        except (KeyError, IndexError, TypeError):
             return jsonify({'error': 'API响应格式错误'}), 500


        analysis_result = strip_llm_json(http_data)
        return jsonify(analysis_result)

    except Exception as e:
        logging.exception("招标文件章节提取失败，业务编号 %s", bidding_id)
        return jsonify({'error': '章节提取分析失败，请稍后重试。'}), 500
    

@bp.route('/chapter-design', methods=['POST'])
def chapter_design():
    """投标文件章节设计"""
    data = request.get_json()
    bidding_id = data.get('biddingId') 
    logging.debug("temp_analysis_store keys: %s", list(temp_analysis_store.keys()))
    # 获取分析结果和目录结构
    analysis_data = temp_analysis_store.get(bidding_id, {}).get('analysisData')
    directory_structure = temp_analysis_store.get(bidding_id, {}).get('directoryStructure')

    if not all([bidding_id, analysis_data, directory_structure]):
        return jsonify({'error': '招标文件分析数据不完整，请按流程重新执行预分析与章节提取。'}), 400

    # 提取招标书信息
    bidding_requirements = analysis_data.get('bidding_requirements', '')
    bidding_summary = analysis_data.get('bidding_summary', '')
    bidding_meta = analysis_data.get('bidding_meta', '')

    # 构建提示词
    enterprise_context = build_enterprise_context()
    chapter_design_prompt = (
        f"你是资深投标文件目录结构设计专家，熟悉水利工程施工、设备配套和供应链项目投标规范。\n"
        f"企业画像：\n{enterprise_context}\n\n"
        f"请根据以下信息，整理出最终的标书章节结构：\n\n"
        f"必须包含的文件和材料：{bidding_requirements}\n"
        f"招标书内容总结：{bidding_summary}\n"
        f"招标书具体要求和评分标准：{bidding_meta}\n"
        f"投标书章节大纲：{directory_structure}\n\n"
        "基于以上招标文件要求和企业画像，请补充章节的子节目录，确保投标文件完整、严谨、可执行且符合要求。\n"
        "要求：\n"
        "1、输出的投标书章节结构必须遵循目录结构，并包含所有必要的子章节。\n"
        "2、章节大纲中某一章如果是xxx表、xxx函、xxx清单、封面等，则该章下不需要再细分子节，返回原本的章节内容。\n"
        "3、输出必须是有效的JSON格式，格式如下：\n"
        '''{
  "chapters": [
    {
      "title": "",
      "type": "normal|table",
      "content": "",
      "sections": [
        {
          "title": "",
          "subsections": [
            {
              "title": "",
              "describe": ""
            }
          ]
        }
      ]
    }
  ]
}'''
        "字段说明：\n"
        "title：章节标题。\n"
        "type：章节类型，normal表示文本章节，table表示表格章节。\n"
        "content：table章节需填写原本章节内容。\n"
        "sections：二级标题。\n"
        "subsections：三级标题，最少5-7点三级标题。\n"
        "describe：三级标题内容的描述。\n"
    )

    try:
        # 调用 LLM API
        response = call_dashscope_api([
            {'role': 'user', 'content': chapter_design_prompt}
        ])
        logging.debug("章节设计模型响应已返回")

        # 获取返回内容
        try:
            http_data = response['output']['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            return jsonify({'error': 'API响应格式错误'}), 500

        try:
            analysis_result = strip_llm_json(http_data)
        except json.JSONDecodeError as e:
            logging.exception("章节设计 JSON 解析失败，响应片段: %s", http_data[:500])
            return jsonify({'error': 'JSON解析失败，请稍后重试。'}), 500

        return jsonify(analysis_result)

    except Exception as e:
        logging.exception("投标章节设计失败，业务编号 %s", bidding_id)
        return jsonify({'error': '章节生成失败，请稍后重试。'}), 500

    


@bp.route('/generate-bid-document', methods=['POST'])
def generate_bid_document():
    """生成完整投标书文件，并在生成 .docx 后构造 OnlyOffice editorConfig 返回"""
    data = request.get_json()
    bidding_id = data.get('biddingId')
    chapter_design = data.get('chapterDesign')
    if not bidding_id:
        return jsonify({'error': '缺少招标文件业务编号。'}), 400
    if not chapter_design:
        return jsonify({'error': '缺少投标文件章节设计结果。'}), 400

    # 如果前端传的是字符串形式的 JSON，尝试解析
    if isinstance(chapter_design, str):
        try:
            chapter_design = json.loads(chapter_design)
        except Exception as e:
            logging.error(f"chapterDesign JSON 解析失败: {e}")
            return jsonify({'error': 'chapterDesign JSON 解析失败'}), 400
    if isinstance(chapter_design, dict) and 'chapters' in chapter_design:
        chapter_design = chapter_design['chapters']
    if not isinstance(chapter_design, list):
        return jsonify({'error': 'chapterDesign 格式错误，应为章节数组或包含 chapters 的对象'}), 400

    try:
        # 读取 bidding 记录
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bidding WHERE id = ?', (bidding_id,))
        bidding = cursor.fetchone()
        conn.close()
        if not bidding:
            return jsonify({'error': '招标书不存在'}), 404

        tender_name = Path(bidding['original_filename']).stem
        # 如果已经生成 markdown，直接转换
        markdown_file = Path("outputs") / tender_name / f"{tender_name}_完整投标文件.md"
        if markdown_file.exists():
            logging.info("已存在生成的 Markdown 文件，直接调用转换函数。")
            try:
                generated_docx_path = convert_md_to_word(markdown_file)
            except Exception as e:
                logging.exception("已生成 Markdown 转 Word 失败")
                return jsonify({'error': '已存在 Markdown，但转换为 Word 失败'}), 500

            if not generated_docx_path or not Path(generated_docx_path).exists():
                logging.error(f"convert_md_to_word 未返回有效路径或文件不存在: {generated_docx_path}")
                return jsonify({'error': '已生成 Markdown，但 docx 未找到'}), 500

            generated_docx_path = Path(generated_docx_path)
            generated_docx_path, _ = refresh_docx_fields_with_soffice(generated_docx_path)

            # 继续到下面的步骤（复制到 GENERATED_FOLDER、构造 editorConfig 等）
        else:
            # 按原逻辑生成章节内容并合并为 markdown
            # 用你原来的生成逻辑（这里为最小改动保留）
            saved_section_names = []
            for chapter in chapter_design:
                c_type = (chapter.get('type') or "normal").strip().lower()
                c_title = chapter.get('title', "")
                c_content = chapter.get('content', "")
                if c_type == 'table':
                    if c_content:
                        save_bid_section(c_content, c_title, "outputs", tender_name)
                        saved_section_names.append(c_title)
                elif c_type == 'normal':
                    sections = chapter.get('sections', [])
                    tasks = []
                    with ThreadPoolExecutor(max_workers=8) as executor:
                        for section in sections:
                            subsections = section.get('subsections', [])
                            for subsection in subsections:
                                sub_title = subsection.get('title', '')
                                sub_content = subsection.get('describe', '')
                                vector_context = query_chroma(sub_content)
                                if not sub_title or not sub_content:
                                    logging.warning(f"跳过无效的 subsection：{sub_title}")
                                    continue
                                future = executor.submit(generate_bid_section, sub_title, sub_content, vector_context)
                                tasks.append((future, sub_title))
                        for future, sub_title in tasks:
                            try:
                                generated_content = future.result()
                                save_bid_section(generated_content, sub_title, "outputs", tender_name)
                                saved_section_names.append(sub_title)
                            except Exception:
                                logging.exception("投标正文小节生成失败: %s", sub_title)
                else:
                    logging.warning(f"未知的 chapter type '{c_type}'，跳过：{c_title}")

            merged_md_path = merge_sections("outputs", tender_name, saved_section_names)
            if not merged_md_path:
                logging.error("合并章节生成 Markdown 失败。")
                return jsonify({'error': '合并章节失败'}), 500

            try:
                generated_docx_path = convert_md_to_word(merged_md_path)
            except Exception:
                logging.exception("Markdown 转 Word 失败")
                return jsonify({'error': 'Markdown 转 Word 失败'}), 500

            if not generated_docx_path or not Path(generated_docx_path).exists():
                logging.error(f"convert_md_to_word 未返回有效路径或文件不存在: {generated_docx_path}")
                return jsonify({'error': '生成的 docx 文件不存在'}), 500

            generated_docx_path = Path(generated_docx_path)
            generated_docx_path, _ = refresh_docx_fields_with_soffice(generated_docx_path)

        # === 下面开始：把生成的 docx 放到 GENERATED_FOLDER 并构造 OnlyOffice editorConfig（内联实现） ===
        

        gen_folder = Path(current_app.config.get('GENERATED_FOLDER', 'outputs'))
        gen_folder.mkdir(parents=True, exist_ok=True)

        target = gen_folder / _display_filename(generated_docx_path.stem, "投标文件")
        target = target.with_suffix(generated_docx_path.suffix)
        if generated_docx_path.resolve() != target.resolve():
            shutil.copy2(str(generated_docx_path), str(target))

        backend_url = get_backend_public_base_url()
        file_url = _absolute_output_url_for_path(target)
        callback_url = f"{backend_url}/api/bidding/save-callback"

        # document key（用于 OnlyOffice 缓存），使用 DB 中已有的或者新生成
        doc_key = bidding[4]

        payload = {
            'document': {
                'fileType': 'docx',
                'key': doc_key,
                'title': bidding['original_filename'],
                'url': file_url,
            },
            'documentType': 'word',
            'editorConfig': {
                'callbackUrl': callback_url,
                'mode': 'edit',
                'user': {
                    'id': f"user-{bidding['user_id']}",
                    'name': '企业标书编制岗'
                },
                'customization': {'forcesave': True}
            }
        }

        # 生成JWT令牌
        token = jwt.encode(payload, _onlyoffice_jwt_secret(), algorithm='HS256')
        editor_config_with_token = {**payload, 'token': token}
        

        # 更新 DB：记录生成的 docx 路径与 document_key、状态
        conn = get_db()
        cur = conn.cursor()
        cur.execute('UPDATE bidding SET bid_document=?, document_key=?, status=? WHERE id=?',
                    (str(target), doc_key, '已生成', bidding['id']))
        conn.commit()
        conn.close()

        # 返回 editorConfig 给前端，前端用此配置初始化 OnlyOffice
        return jsonify({
            'message': '投标文件已生成',
            'markdown': str(markdown_file if markdown_file.exists() else merged_md_path),
            'editorConfig': editor_config_with_token,
            'fileUrl': file_url,
            'downloadUrl': _output_url_for_path(target)
        }), 201

    except Exception as e:
        logging.exception(f"生成投标书过程出错: {e}")
        return jsonify({'error': f'生成投标书失败: {str(e)}'}), 500

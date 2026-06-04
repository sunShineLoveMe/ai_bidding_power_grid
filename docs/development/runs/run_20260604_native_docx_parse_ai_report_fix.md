# Native DOCX 解析后 AI 解读 500 修复记录

日期：2026-06-04

## 触发现象

上传 `国网山西电力2026年第二次物资协议库存公开招标采购招标文件.docx` 后，前端第一步流程在生成 AI 解读时报错：

```text
POST /api/bidding/interpretations/50ae3a91-f725-4cc1-b0d3-d7c3a33a5211/ai-report 500
```

## 根因

该文件为 `.docx`，走 native text 解析路径。原逻辑只执行：

- `ensure_extractable_text(file_path)`
- 将 `bid_files.parse_status` 更新为 `indexed`

但没有生成业务解读依赖的数据：

- `bid_analysis`
- `bid_requirements`
- `bid_risks`
- `bid_scoring_items`
- `bid_chapter_suggestions`
- `document_chunks`

因此前端看到 `parse_status=indexed` 后进入 AI 解读，后端 `generate_ai_interpretation_report` 读取不到 `analysis`，抛出“当前项目尚无结构化解读数据”。

## 修复

文件：

- `backend/parsing/document_parser.py`

改动：

- 新增 `_native_text_artifacts`。
- 对 `.docx` / 原生可抽取文本文件生成 MinerU-like artifacts：
  - `full.md`
  - `native_content_list.json`
- native text 路径复用 `ingest_mineru_artifacts_to_supabase`，统一生成 `bid_analysis` 和 `document_chunks`。
- 入库成功后再将 parse status 标记为 `indexed`。

## 当前项目补救

已对失败项目手动补跑 native 解析入库：

- project_id: `50ae3a91-f725-4cc1-b0d3-d7c3a33a5211`
- bid_file_id: `553dc3bc-7da9-4510-8f90-83c5a85d0c33`

补跑后结果：

- `bid_analysis`: 1 条
- `document_chunks`: 8 条
- 资格要求：25 条
- 风险项：40 条

随后真实调用 `generate_ai_interpretation_report` 成功返回，AI 解读已写入 `project_meta.ai_report`。

## 验证

已执行：

```bash
.venv/bin/python -m unittest tests.test_native_parse_ingestion tests.test_api_sections tests.test_section_generation_autoresume
```

结果：通过，10 个测试 OK。

已执行：

```bash
.venv/bin/python -m py_compile backend/parsing/document_parser.py backend/ai/interpreter.py backend/tasks/parse_tasks.py
```

结果：通过。

## 注意

当前运行中的 Celery worker 是修复前启动的。如果继续上传新的 `.docx` 测试文件，必须重启 Celery worker，确保解析任务加载修复后的 `document_parser.py`。

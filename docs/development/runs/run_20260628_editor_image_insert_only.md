# 2026-06-28 在线编辑器图片插入功能回归

## 背景

本分支从 `feat/aliyun-test-readiness` 新建，范围限定为在线类 Word 编辑器图片插入能力。连续滚动需求延后到下期，不进入本分支。

## 实现范围

- Tiptap 工具栏新增“插入图片”按钮。
- 支持从产品库/资信库选择已入库图片。
- 资产选择弹窗从单页 48 条改为分页拉取当前库最多 500 条图片资产，避免人员证书、项目业绩等资信图片因排序靠后不显示。
- 资产选择弹窗支持按分类和关键词筛选，并在图片卡片上显示分类和使用范围。
- 支持本地上传图片并写入中文标题、库类型、用途等 metadata。
- 编辑器预览使用授权 object URL，保存 Markdown 使用 canonical `/api/knowledge/assets/<id>/file?variant=original`。
- DOCX 导出保留可信手工插入资产图片，确保编辑器插入图片和修改文字后可进入 Word。
- 修复旧题注识别过宽问题，避免“图片之后继续编辑文字...”被误判为图片题注。
- 企业产品库/资信库“使用范围”文案调整：历史资产不再因缺少 `quality_tier` 默认显示为“仅用于知识库”；根据 `allowed_for_bid`、`formal_bid_excluded` 和质量等级展示“可用于标书正文”或“知识库/需复核”。人工插入与自动配图规则分开表达。

## 回归记录

- `python3 -m py_compile backend/api/routes.py backend/services/formal_asset_naming.py backend/export/md_to_word.py`：通过。
- `npm run build`：通过；仅保留既有 Vite chunk 体积和混合 import 警告。
- `.venv/bin/python -m pytest tests/test_docx_export.py::DocxExportRegressionTest::test_plain_paragraph_after_image_prefix_is_not_caption tests/test_docx_export.py::DocxExportRegressionTest::test_formal_image_caption_is_sanitized_centered_and_small tests/test_docx_export.py::DocxExportRegressionTest::test_manual_asset_image_survives_formal_export_image_cleanup -q`：通过。
- 2026-06-28 追加回归：
  - `npm run build`：通过。
  - `.venv/bin/python -m pytest tests/test_docx_export.py::DocxExportRegressionTest::test_plain_paragraph_after_image_prefix_is_not_caption tests/test_docx_export.py::DocxExportRegressionTest::test_manual_asset_image_survives_formal_export_image_cleanup -q`：`2 passed, 1 warning`。
  - `python3 -m py_compile backend/api/routes.py backend/services/formal_asset_naming.py backend/export/md_to_word.py`：通过。

## 边界

- 本分支不包含正文连续滚动、章节流预览、多章节 dirty 保存等下期体验优化。
- 本分支不提交 `output/` 和 `parsed_outputs/` 本地运行产物。

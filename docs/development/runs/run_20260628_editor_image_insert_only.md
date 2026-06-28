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

## 2026-06-28 交互与命名复查

### 问题

- 用户点击资产图片上的“预览”原本只是想查看图片，但旧交互会直接插入正文，缺少确认动作。
- 部分图片名称出现 `社保证明（）` 这类空括号，属于无意义符号，不能展示给客户。
- 本地上传图片后的输入框含义不清，用户不确定它是标题还是标签。

### 修复

- 资产库图片改为“预览/选择/确认插入”：
  - 点击图片预览只打开 AntD 图片预览，不改正文。
  - 点击卡片或“选择”按钮只选中资产。
  - 底部“插入选中图片”才真正写入编辑器正文。
- 本地上传输入框改为显式标签 `图片标题`，占位文案改为“用于正文图片替代文字”，不再像标签输入。
- 前端统一清洗图片展示名称中的空括号和只有标点/空白的括号。
- 后端 `clean_formal_asset_title` 同步清洗空括号，避免正式题注或 DOCX 兜底标题再次出现类似符号。
- Tiptap 编辑器消息提示切换为 AntD `App.useApp()`，并在入口补 `AntdApp` provider，避免插入图片时控制台出现 AntD static message 警告。

### 真实回归

- 服务：使用用户已启动的本地 `5173` 前端和 `3012` 后端。
- 页面：`http://127.0.0.1:5173/bid-editor?projectId=5d064d0a-29ba-41bb-ab07-9d51e6c9e084`。
- Playwright 结果：
  - 点击图片预览后，正文图片数 `0 -> 0`，`previewDidNotInsert=true`。
  - 预览层正常打开，`previewVisible=true`。
  - 选择图片后底部按钮可用，`selectedClass=true`，`okDisabledAfterSelect=false`。
  - 点击“插入选中图片”后，正文图片数 `0 -> 1`，`insertedAfterConfirm=true`。
  - 弹窗内未发现空括号，`hasEmptyBracketsBeforeInsert=false`。
  - 本地上传区域显示 `图片标题`，`titleLabelVisible=true`。
  - 干净会话控制台错误 `0`，警告 `0`。
- 截图：`.playwright-cli/page-2026-06-28T08-35-51-134Z.png`。

### 命令回归

- `npm run build`：通过；仅保留既有 Vite chunk 体积和混合 import 警告。
- `.venv/bin/python -m pytest tests/test_docx_export.py::DocxExportRegressionTest::test_formal_asset_title_removes_empty_brackets tests/test_docx_export.py::DocxExportRegressionTest::test_plain_paragraph_after_image_prefix_is_not_caption tests/test_docx_export.py::DocxExportRegressionTest::test_manual_asset_image_survives_formal_export_image_cleanup -q`：`3 passed, 1 warning`。
- `python3 -m py_compile backend/services/formal_asset_naming.py backend/export/md_to_word.py backend/api/routes.py`：通过。

# 第六章格式表单保真真实回归记录

- Run ID：`run_20260625_docx_sixth_chapter_form_fidelity`
- 日期：2026-06-25
- 项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 投标人：河北泰昌电力器材科技有限公司
- 结论：`PASS`

## 本轮实现

- 识别投标函、法定代表人身份证明/授权委托书、商务偏差表、技术偏差表、承诺函等正式表单上下文。
- 签章信息行按正式表单右对齐输出。
- 商务偏差表、技术偏差表按字段语义分配列宽，并在 LibreOffice 刷新后保留表格网格宽度。
- 表格行写入禁止跨页拆分属性，避免偏差表单行被分页切断。
- 导出 metadata 新增 `formal_forms`，记录识别类型、表格数、小标题数、签章行数和禁止拆分行数。
- 正式 readiness 每次根据当前确认值重新计算；带“内部测试”等模拟标记的客户字段不得通过正式版门禁。

## 自动化回归

```text
PYTHONPATH=. .venv/bin/pytest \
  tests/test_docx_export.py \
  tests/test_bid_prefill.py \
  tests/test_formal_bid_check.py -q
```

结果：`54 passed, 1 warning`。

提交前扩大到 Celery 导出任务回归后，结果为 `65 passed, 7 warnings`。

## 真实 DOCX 链路

执行链路：

```text
build_project_bid_markdown
-> convert_md_to_word
-> refresh_docx_fields_with_soffice
```

验收结果：

- 五类正式表单全部识别。
- 表单表格 `38` 个，小标题 `38` 个，签章行 `76` 行，禁止跨页拆分行 `244` 行。
- LibreOffice 刷新后 `76` 行签章信息仍保持右对齐。
- 商务偏差表和技术偏差表语义列宽、表格网格宽度均保留。
- 偏差表抽样行全部保留禁止跨页拆分属性。
- 目录、页码和总页数字段刷新成功。
- 模拟客户确认值形成 `12` 个正式必填缺口，`formal_readiness.ready=false`。
- 模板 ID 为 `formal_bid_standard`。

详细机器记录：`docs/development/runs/run_20260625_docx_sixth_chapter_form_fidelity.json`。

## 真实 API 与浏览器回归

- 真实下载 API 创建任务：`fd40ab53-841b-482b-b1b0-1ecb31117a87`。
- API 返回 `export_mode=draft`，正式门禁存在 `8` 个阻断项，任务正常完成。
- 导出任务 metadata 中字段刷新状态为 `refreshed`，并包含五类 `formal_forms` 统计。
- 浏览器从标书编辑页点击“标书下载”，先展示条款覆盖风险确认；继续下载后明确提示“正式检查仍有 8 个阻断项，本次仅创建草稿版 DOCX 导出任务”。
- 浏览器控制台仅有 Ant Design 静态 `Modal/message` 上下文警告，不影响本轮导出链路；后续可随前端基础设施清理。
- 截图：`output/playwright/docx-sixth-chapter-download-gate-20260625.png`（运行产物，不提交仓库）。

## 结论与边界

内置 `formal_bid_standard` 已具备第六章常见表单的基础结构保真能力，DOCX 正式交付排版 P0 可关闭。若客户提供可编辑 Word 原模板，像素级套表、原始签章位和复杂合并单元格仍应进入 `template_docx` 模式处理。

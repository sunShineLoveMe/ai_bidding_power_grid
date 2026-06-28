# 2026-06-28 辽宁 CPVC/MPP 正式投标导出 P0 修复回测记录

## 背景

基于项目 `ae6b7da5-a7b3-473f-a28f-13990ead304e` 的真实投标流程回归结果，针对正式上线前暴露的 P0 问题进行修复和复测。重点处理：正式导出门禁误降级、正文占位符、内部图片路径泄露、NHAP 串包、施工类口径、正文过长和分页过密。

## 修复范围

- 正式检查按“用户可见正文”扫描，不再把 Markdown 图片中间路径当作最终 DOCX 正文。
- 导出正文统一执行真实正式化清洗：使用人工确认字段替换旧占位，移除 `待补充/人工复核/客户确认后填写/用户确认/占位符` 等系统工作流语言。
- 增加本包物料范围过滤：CPVC/MPP 包导出时过滤 NHAP 等非本包物料章节。
- 供货类写作策略收敛：降低默认篇幅目标，禁用施工组织、建造师、安全生产许可证等工程承包口径。
- 物资供货场景正式导出术语归一化：`施工组织/施工方案/项目经理/施工现场` 仅在物资供货上下文中归一为 `供货组织/供货实施方案/项目负责人/现场交接区域`。
- DOCX 一级标题以下分页策略收敛，只对一级标题和正式分册起始强制分页，减少正文被拆成大量空白页。
- 产品适配检查分离“招标原文识别”和“人工确认补充识别”：招标原文明确不匹配时仍阻断，原文缺失时可用人工确认字段补足。

## 真实导出任务

三份文件均走真实链路：

`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`

| 文件 | 任务 ID | 字段刷新 | 图片插入 | readiness |
| --- | --- | --- | --- | --- |
| 技术投标文件 | `36171ec6-100c-4b44-b067-9381f61e696a` | `refreshed` | `14/14/0` | `ready=true` |
| 商务投标文件 | `193934a4-9dc3-473c-bb61-af7cc47ee17c` | `refreshed` | `6/6/0` | `ready=true` |
| 完整投标文件 | `b6d8fe33-a8ed-43e3-ac6a-2d9c476bc19b` | `refreshed` | `19/19/0` | `ready=true` |

输出 DOCX：

- `outputs/ae6b7da5/泰昌_2225AC_包1_技术投标文件_20260628_图文.docx`
- `outputs/ae6b7da5/泰昌_2225AC_包1_商务投标文件_20260628_图文.docx`
- `outputs/ae6b7da5/泰昌_2225AC_包1_投标文件_20260628_图文.docx`

PDF 抽查：

- `docs/development/runs/pdf_check_20260628/泰昌_2225AC_包1_技术投标文件_20260628_图文.pdf`，`225` 页
- `docs/development/runs/pdf_check_20260628/泰昌_2225AC_包1_商务投标文件_20260628_图文.pdf`，`268` 页
- `docs/development/runs/pdf_check_20260628/泰昌_2225AC_包1_投标文件_20260628_图文.pdf`，`475` 页

## DOCX 成品审计

直接审计 DOCX 文本和 XML：

| 检查项 | 技术标 | 商务标 | 完整标书 |
| --- | --- | --- | --- |
| `待补充/人工复核/客户确认后填写/用户确认/占位符` | `0` | `0` | `0` |
| `/api/bidding/knowledge/assets/parsed_outputs/taichang_/power_grid_` | `0` | `0` | `0` |
| `NHAP` | `0` | `0` | `0` |
| `施工组织/施工方案/项目经理/施工现场` | `0` | `0` | `0` |
| `【5.1】` 类括号编号标题 | `0` | `0` | `0` |

正式检查结果（完整标书任务 `b6d8fe33-a8ed-43e3-ac6a-2d9c476bc19b`）：

- 规则总数：`62`
- 通过：`61`
- 阻断：`0`
- 人工确认：`0`
- Warning：`1`
- `canFormalExport=true`

剩余 warning：`Q-007 社保证明或人员证明归类正确`，发现 `26` 条人员证书资产仍带有 `试验检测能力` 标签。导出 manifest 已确认未把这些人员资料误插到试验检测章节；该项保留为资产治理待办，不作为本轮 DOCX 正式导出阻断。

## 自动化回归

- `.venv/bin/python -m pytest tests/test_formal_bid_check.py tests/test_formal_placeholders.py tests/test_bid_material_scope.py -q`
  - 结果：`15 passed, 1 warning`
- `.venv/bin/python -m pytest tests/test_bid_material_scope.py tests/test_formal_placeholders.py tests/test_section_writer_formal_quality.py tests/test_formal_bid_check.py tests/test_chapter_planner.py tests/test_length_settings.py tests/test_section_prompt_policy.py tests/test_docx_export.py::DocxExportRegressionTest::test_bid_markdown_formal_readiness_rejects_simulated_customer_values tests/test_docx_export.py::DocxExportRegressionTest::test_export_sections_are_numbered_for_word_outline tests/test_docx_export.py::DocxExportRegressionTest::test_docx_first_page_is_formal_toc_and_title_is_not_outline_heading -q`
  - 结果：`46 passed, 1 warning`

## 结论

本轮 P0 正式导出问题已收口：正式门禁不再降级为草稿，成品 DOCX 不再出现占位符、内部路径、NHAP 串包、施工类口径和括号编号标题。整体页数从约 `499` 页降至 `475` 页，但仍偏长；原因主要是真实正文体量和证据附件较多，后续应继续做“章节篇幅预算 + 附件独立分册/按需插图”优化，不作为本轮阻断项。

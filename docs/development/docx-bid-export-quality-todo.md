# 标书文档编写与正式导出质量待办清单

更新日期：2026-06-18

范围：标书正文编写、封面/目录/页眉页脚、图表与表格、DOCX 字段刷新、真实导出验收、后续 PDF/模板化能力。本文档用于管理客户最终交付物质量，优先级高于普通导出功能优化。

## 当前结论

- MVP 默认采用 `sgcc_taichang_bid`，即“国网/泰昌标准格式”。
- 普通用户默认不直接进入全量自定义格式；自定义能力作为后续高级功能。
- 若招标文件明确第六章格式、前附表或否决项要求，优先按招标文件要求。
- 若客户提供可编辑 Word 模板，优先进入 `template_docx` 模式。
- 真实验证必须走项目导出链路：`build_project_bid_markdown` -> `convert_md_to_word` -> `refresh_docx_fields_with_soffice`，不得只用 mock 替代。

## P0 必须完成

| 状态 | 任务 | 验收口径 |
| --- | --- | --- |
| 已完成 | 默认正式模板固定为 `sgcc_taichang_bid` | metadata 记录模板 ID、正文/目录/页边距、页眉页脚设置 |
| 已完成 | 封面正式字段补齐第一阶段 | 封面包含标题、投标人、日期，并在正文可提取时自动加入招标编号、分标编号、分标名称、包号/包名称、文件类型 |
| 已完成 | 封面字段结构化来源补齐 | 从项目解析 metadata 或招标文件结构化结果稳定补齐分标编号、分标名称、包号/包名称，不依赖正文猜测 |
| 已完成 | 目录稳定性验收 | 独立目录页、最多 3-4 级、点引导线、页码右对齐、字段刷新成功 |
| 已完成 | 目录标题去重 | 子章节不得重复父章节前缀，例如 `2.1.1 响应要求`，不得输出 `2.1.1 企业基本资格资料 - 响应要求` |
| 已完成 | 正文格式统一 | 字体、字号、行距、首行缩进、标题层级、分页规则稳定 |
| 已完成 | Mermaid/流程图源码清理 | Mermaid 能转图则插入图片，转换失败不得把源码块写入正式 DOCX |
| 已完成 | 表格正式化 | A4 内可读、边框清晰、表头加粗、必要时重复表头、不大面积越界 |
| 已完成 | 图片资产正式化 | 只允许泰昌企业事实资产，禁止虚假图片路径，正式 DOCX 不展示内部来源库、匹配依据或得分，记录图片候选/选中/插入/失败数 |
| 已完成 | 真实导出验收记录 | 用真实项目导出 DOCX，记录封面、目录、正文、表格、图片、页眉页脚、字段刷新状态 |

## P1 应该完成

| 状态 | 任务 | 验收口径 |
| --- | --- | --- |
| 待办 | 格式方案选择 | 提供“国网/泰昌标准格式、通用正式标书、紧凑上传版、图文展示版”，默认国网/泰昌 |
| 脚本版已完成 | 格式预检报告 | `scripts/rag/verify_taichang_full_bid_acceptance.py` 已检查目录缺失、页码字段、表格格式、图片失败/裁剪/比例、内部字段泄露、重复父章节标题和补充包资产选中；后续再接入页面/导出任务 metadata |
| 待办 | 分册格式 | 商务标、技术标、资信标支持不同封面字段、目录和页眉文案 |
| 待办 | 第六章格式表单保真 | 偏差表、承诺函、签章表单等优先保留结构和占位 |
| 待办 | 导出任务 metadata 扩充 | 记录格式方案、封面字段、目录层级、图表题注、格式告警 |

## P2 后续增强

| 状态 | 任务 | 验收口径 |
| --- | --- | --- |
| 待办 | 高级自定义格式面板 | 参考竞品开放编号、正文、页面、图表设置，并支持恢复默认 |
| 待办 | 企业模板保存 | 用户可另存企业模板，并在后续项目复用 |
| 待办 | 可编辑 Word 模板导入 | 上传 Word 模板后进入 `template_docx` 模式 |
| 待办 | PDF 预览与导出 | DOCX 刷新后可转 PDF 预览，便于提交前检查 |
| 待办 | 招标文件格式约束抽取 | 自动抽取第六章/前附表格式要求，并提示用户确认 |

## P0 第一阶段执行记录

### 2026-06-09

- 新增本待办清单，作为标书文档交付质量专项跟踪入口。
- 将标准 DOCX 导出 SOP 同步到 `AGENTS.md`。
- 封面字段补齐进入实现：从生成 Markdown 中提取 `文件类型`、`招标编号`、`分标编号`、`分标名称`、`包号`、`包名称`，并写入封面和 `docx_template.cover_fields`。
- 单元测试：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_celery_export_tasks.py -q`，结果 `30 passed, 5 warnings`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260609_docx_quality_p0_real_export.md` 和 `docs/development/runs/run_20260609_docx_quality_p0_real_export.json`。
- 本次真实导出结果：模板 `sgcc_taichang_bid`，封面提取 `文件类型=投标文件`、`招标编号=2225AC`，图片 found/inserted/skipped/failed 为 `24/24/0/0`，LibreOffice 字段刷新成功。

### 2026-06-09 二次验收发现

- 问题 1：正式 DOCX 中出现 Mermaid 源码块，说明流程图转换失败时没有在导出层兜底清理。
- 问题 2：目录小节标题重复父章节前缀，例如 `企业基本资格资料 - 响应要求`，应改为 `响应要求`；系统生成章节目录源头也应同步修正。
- 问题 3：图片 caption 展示了内部来源库和匹配依据，正式交付版应去掉，仅在 metadata/manifest 中保留。
- 处理要求：这三项均纳入 P0，必须修复后复跑真实导出链路并新增 run 记录。

### 2026-06-09 二次问题修复记录

- 目录标题去重已修复：系统章节拆分源头不再生成 `父章节 - 子章节` 标题，导出层也会兜底移除重复父章节前缀。
- Mermaid/流程图源码清理已修复：Mermaid 转图成功时插入图片；当前环境未安装 `mmdc` 时记录 skipped，正式 DOCX 不再输出 ```mermaid 源码块。
- 图片资产正式化已修复：正式 DOCX caption 只保留 `图示：资料标题`，内部来源库、匹配依据、得分等只保留在 metadata/manifest。
- 单元与集成测试：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q`，结果 `48 passed, 5 warnings`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260609_docx_quality_p0_cleanup_real_export.md` 和 `docs/development/runs/run_20260609_docx_quality_p0_cleanup_real_export.json`。
- 本次真实导出结果：`cleanup_checks.contains_mermaid_fence=false`，`cleanup_checks.contains_internal_image_source=false`，`repeated_title_patterns_found=[]`；图片 found/inserted/skipped/failed 为 `24/24/0/0`，Mermaid found/inserted/skipped 为 `1/0/1`，LibreOffice 字段刷新成功。

### 2026-06-11 表格正式化修复记录

- 表格正式化已修复：Markdown 表格导出为 100% 可用页宽、固定布局、居中表格、表头浅灰底、表头加粗、表头跨页重复、单元格边距、表格内 16pt 固定行距且不首行缩进。
- 正文样式未作为本轮完整 P0 关闭项；本轮只处理与表格同源的表格内段落样式，正文全篇分页、空行和标题间距仍按后续 `正文格式统一` 任务继续验收。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q`，结果 `49 passed, 5 warnings`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260611_docx_quality_p0_table_real_export.md` 和 `docs/development/runs/run_20260611_docx_quality_p0_table_real_export.json`。
- 本次真实导出结果：表格数量 `60`；表格抽样检查 `table_count_gt_zero`、`all_sample_tables_full_width`、`all_sample_tables_fixed_layout`、`all_sample_tables_repeat_header`、`all_sample_tables_have_cell_margin`、`all_sample_data_rows_no_first_line_indent`、`all_sample_data_rows_line_spacing_16pt`、`all_sample_data_rows_alignment_readable` 全部为 `true`；LibreOffice 字段刷新成功。

### 2026-06-11 正文格式统一修复记录

- 正文格式统一已修复：正文段落宋体 `10.5pt`、固定行距 `20pt`、首行缩进 `21pt`、段前段后 `0pt`；后续因格式标记观感要求，已移除会显示黑色方块的分页控制。
- 标题格式已统一：标题不首行缩进，固定行距 `20pt`；后续因格式标记观感要求，已移除 `keep_with_next/keep_together`。
- 列表格式已统一：列表固定行距 `20pt`，左缩进 `21pt`，悬挂缩进 `10.5pt`；LibreOffice roundtrip 后会把 `left` 规范化为 `start`，真实验收按刷新后 XML 口径检查。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q`，结果 `50 passed, 5 warnings`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260611_docx_quality_p0_body_real_export.md` 和 `docs/development/runs/run_20260611_docx_quality_p0_body_real_export.json`。
- 本次真实导出结果：正文、标题、列表、表格抽样检查全部通过；正文范围最大连续空段落数为 `1`；Mermaid 源码、内部图片来源/匹配依据、重复父章节标题均未出现在正式 DOCX；LibreOffice 字段刷新成功。

### 2026-06-11 目录格式标记修复记录

- 二次验收发现：Word/WPS 显示格式标记时，目录左侧出现竖向黑色小方块。
- 原因：`Normal` 样式继承了正文段落的 `keep lines together` 分页控制，目录条目使用 `Normal` 样式，因此在显示格式标记时出现黑色方块；这不是目录页码刷新失败，也不是会打印的正文字符。
- 修复：移除 `Normal` 样式上的全局分页控制，仅对正文段落和标题段落直接设置分页控制，避免目录条目继承。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q`，结果 `51 passed, 5 warnings`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260611_docx_quality_p0_toc_marker_cleanup.md` 和 `docs/development/runs/run_20260611_docx_quality_p0_toc_marker_cleanup.json`。
- 本次真实导出结果：`normal_style_has_no_keep_lines=true`，`all_toc_samples_have_no_direct_keep_lines=true`，`all_body_samples_still_keep_lines=true`，LibreOffice 字段刷新成功。

### 2026-06-11 全文格式标记清理记录

- 三次验收发现：正文区域也会显示同类黑色方块，说明正式 DOCX 不应保留 `keep lines together`、`keep with next`、`page break before` 这类会显示黑色方块的分页控制。
- 修复：导出层停止写入 `keepLines/keepNext/pageBreakBefore`，并在 DOCX 保存后、LibreOffice 字段刷新后对 `word/document.xml` 和 `word/styles.xml` 做最终 XML 清理。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q`，结果 `51 passed, 5 warnings`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260611_docx_quality_p0_full_marker_cleanup.md` 和 `docs/development/runs/run_20260611_docx_quality_p0_full_marker_cleanup.json`。
- 本次真实导出结果：`document_keepLines=0`、`document_keepNext=0`、`document_pageBreakBefore=0`、`styles_keepLines=0`、`styles_keepNext=0`、`styles_pageBreakBefore=0`；正文、标题、列表、目录抽样格式仍通过；LibreOffice 字段刷新成功。

### 2026-06-11 目录稳定性验收记录

- 目录稳定性验收已完成：目录标题唯一且位于正文之前，目录条目存在，层级控制在 4 级以内，点引导线、右侧页码和 `PAGEREF` 字段均保留。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q`，结果 `52 passed, 5 warnings`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260611_docx_quality_p0_toc_stability.md` 和 `docs/development/runs/run_20260611_docx_quality_p0_toc_stability.json`。
- 本次真实导出结果：`toc_entry_count=7`，`toc_max_level=1`，目录页码范围 `4-73`；`toc_entries_have_dot_leader=true`、`toc_entries_have_pageref_field=true`、`toc_entries_have_refreshed_page_numbers=true`、`toc_entries_no_black_square_markers=true`、`toc_no_repeated_parent_title_pattern=true`；LibreOffice 字段刷新成功。

### 2026-06-12 Logo 与图片资产版式验收记录

- 高清 Logo 已接入正式 DOCX：默认使用 `assets/icons/taichang_logo.png`，不使用旧低清 `taichang.png`，WebP 仅作为网页端备选。
- 封面和页眉均插入泰昌 Logo，保持原始宽高比；封面显示尺寸约 `1.65in x 1.1in`，页眉约 `0.55in x 0.3667in`。
- Markdown 图片插入策略已改为按可用宽高等比例缩放，不做裁剪、不填充固定框；整页 PDF 渲染图、合同页、证书页和检验报告页均保持完整页面。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q`，结果 `59 passed, 1 warning`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260612_taichang_supplement_p1b6_logo_image_layout.md` 和 `docs/development/runs/run_20260612_taichang_supplement_p1b6_logo_image_layout.json`。
- 本次真实导出结果：图片 candidates/selected 为 `597/24`，补充包选中 `18` 张；DOCX 图片 found/inserted/skipped/failed 为 `24/24/0/0`；DOCX 图片裁剪标记 `0`，内联图片比例检查 `27` 个，最大比例偏差 `0.000101`，LibreOffice 字段刷新成功。

### 2026-06-11 封面字段结构化来源修复记录

- 封面字段结构化来源补齐已完成：招标文件解析阶段新增 `project_meta.cover_fields`、`cover_field_sources`、`cover_field_missing`，DOCX 导出优先读取结构化字段，OnlyOffice 预览和 Celery 正式导出均接入同一链路。
- 抽取字段范围：`项目名称`、`文件类型`、`招标编号`、`分标编号`、`分标名称`、`包号`、`包名称`、`招标人`、`招标代理机构`。
- 安全策略：字段缺失时记录缺失，不编造；当解析文本出现 `项目名称： 招标编号： 分标名称：` 这类空字段串联时，不把字段名误识别为字段值。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_native_parse_ingestion.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q`，结果 `57 passed, 5 warnings`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260611_docx_quality_p0_structured_cover_fields.md` 和 `docs/development/runs/run_20260611_docx_quality_p0_structured_cover_fields.json`。
- 本次真实导出结果：封面字段来源 `uploaded_tender_structured_extract`，封面包含 `项目名称=国网辽宁电力2025年第三次物资协议库存招标采购`、`文件类型=投标文件`、`招标编号=2225AC`；当前历史解析文本缺失可靠的 `分标编号/分标名称/包号/包名称`，已记录在 `cover_field_missing`，未做猜测填充。

### 2026-06-11 泰昌补充资料图文导出验证记录

- 背景：客户补充 `泰昌资质文件(补充).zip` 和官方 Logo 后，需要验证新增企业事实资产能否进入正式投标文件图文导出。
- 修复：自动插图章节画像新增 `project_performance`、`brand_logo` 等证据类型；图片 manifest 增加 `evidence_type`、`target_library`、`source_batch_id`；收紧泛化章节自动插图，避免编制依据、工程概况、总体部署等章节过早耗尽图片额度。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py::DocxExportRegressionTest::test_bid_markdown_with_images_prefers_project_performance_assets tests/test_docx_export.py::DocxExportRegressionTest::test_bid_markdown_with_images_loads_taichang_assets tests/test_docx_export.py::DocxExportRegressionTest::test_bid_markdown_with_images_does_not_repeat_same_asset -q`，结果 `3 passed, 1 warning`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260611_taichang_supplement_p1b_docx_export.md` 和 `docs/development/runs/run_20260611_taichang_supplement_p1b_docx_export.json`。
- 本次真实导出结果：图片候选 `597`，选中 `24`，插入 `24`，失败 `0`；其中 `18` 张来自 `customer_taichang_supplement_20260611`，覆盖基础证照、资质证书、项目业绩、中标通知书/合同、生产制造、试验检测和检验报告；LibreOffice 字段刷新成功。
- 后续状态：官方 Logo 封面/页眉插入已在 2026-06-12 P1B-6 中关闭。

### 2026-06-12 客户演示完整标书验收记录

- 背景：客户演示前需要真实生成一份完整泰昌投标文件，并做硬性成品验收。
- 新增验收脚本：`scripts/rag/verify_taichang_full_bid_acceptance.py`。
- 首轮真实验收发现并修复：
  - 正文小标题仍残留 `父章节 - 子章节` 样式，例如 `发包人要求响应 - 总体部署`，已在导出层清理编号前缀后兜底移除。
  - LibreOffice roundtrip 后个别表格丢失首行重复表头属性，已在字段刷新后统一补 `w:tblHeader`。
  - 验收脚本页脚字段检查改为读取全 DOCX XML，避免漏检 footer 中的 `PAGE/NUMPAGES` 字段。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q`，结果 `58 passed, 1 warning`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`，并用 LibreOffice 额外生成 PDF 预览。
- 验证记录：`docs/development/runs/run_20260612_taichang_full_bid_customer_acceptance.md` 和 `docs/development/runs/run_20260612_taichang_full_bid_customer_acceptance.json`。
- 本次真实验收结果：状态 `PASS`；源项目 74 个章节节点、53 个有正文；DOCX 目录条目 65、表格 60、图片选中 24/插入 24/失败 0；表格全宽、固定布局、表头跨页重复均通过；页脚 `PAGE/NUMPAGES` 字段存在；LibreOffice 字段刷新成功；PDF 预览 127 页。

### 2026-06-12 DeepSeek 全量重写与客户版 DOCX/PDF 验收记录

- 背景：客户验收反馈上一版封面首页页眉多出 Logo、PDF 字体替换异常、`投标函及投标函附录` 等章节未真实生成正文。
- 修复：封面首页启用独立首页页眉并清空，正文页仍保留泰昌页眉；Logo 插入前自动裁白，封面/页眉图片段落改为单倍行距，避免固定 20pt 行距裁切图片；DOCX 正文使用 LibreOffice 可稳定解析的 `SimSun`，标题使用 `Arial Unicode MS`，并统一写入 `ascii/hAnsi/eastAsia/cs` 字体字段，避免 macOS PDF 导出替换字体；验收脚本新增首页页眉为空和配置中文字体检查。
- 真实 DeepSeek 全量重写：执行 `scripts/rag/regenerate_taichang_full_bid_deepseek.py --run-id run_20260612_taichang_deepseek_full_rewrite`，模型 `deepseek-v4-flash`，74 个章节全部清空后重新生成，成功 74、失败 0，旧正文哈希备份见 `docs/development/runs/run_20260612_taichang_deepseek_full_rewrite_before_sections_backup.json`。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q`，结果 `58 passed, 1 warning`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`，并用 LibreOffice 生成 PDF。
- 验证记录：`docs/development/runs/run_20260612_taichang_deepseek_full_rewrite.md`、`docs/development/runs/run_20260612_taichang_full_bid_final_v6.md` 和对应 JSON。
- 本次真实验收结果：状态 `PASS`；源项目 74 个章节节点、74 个有正文；Markdown `166913` 字符；DOCX 段落 `2747`、标题 `74`、目录条目 `65`、表格 `109`；图片选中 `24`、插入 `24`、失败 `0`；封面首页页眉为空、目录点引导线和 `PAGEREF` 存在、页脚 `PAGE/NUMPAGES` 字段存在、配置中文字体检查通过、无内部检索字段泄漏、无重复父章节标题、无黑色方块分页标记、PDF 预览生成成功。

### 2026-06-12 编号与 PDF 差异复核记录

- 根因：数字列表统一使用 Word `List Number` 样式，导致各章节的序号共享同一 `numId`，LibreOffice/Word 排版后连续累计到 300 以上。
- 修复：正式导出改为保留 Markdown 原始数字标记，普通业务列表可在各章节从 `1.` 重新开始，`5.4.1` 等业务层级编号不再被改写成全文连续序号。
- 字号对照：客户提供的 362 页参考标书抽样页正文主字体为宋体，主字号约 `10.6pt`；当前正文 `10.5pt` 与参考稿一致，本轮不放大字号。
- PDF 说明：当前流程为 DOCX 生成后由 LibreOffice headless 刷新字段并另行排版导出 PDF；不是 Word 原生“另存为 PDF”，因此字体映射和分页不能保证像素级一致。本机 Word 原生自动导出因应用交互/权限阻塞未纳入无人值守链路。
- 自动化回归：`.venv/bin/python -m pytest tests/test_docx_export.py -q`，结果 `37 passed, 1 warning`。
- 真实导出：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice -> LibreOffice PDF`，状态 PASS；PDF `208` 页，图片 `24/24/0`，表格 `109`，字段刷新成功。
- 编号专项检查：普通数字列表最大序号 `12`，PDF 中原异常 `360.`、`361.`、`362.`、`367.`、`368.` 均不存在。
- 验证记录：`docs/development/runs/run_20260612_taichang_bid_numbering_final.md`。

### 2026-06-12 泰昌企业事实约束重写与最终演示版验收记录

- 背景：客户继续反馈完整标书仍存在事实缺口和旧模板污染，需要按泰昌真实企业事实重新收口，并对残留 `【待补充】` 做客户可执行归类。
- 修复：新增 `scripts/rag/regenerate_taichang_fact_grounded_bid.py`，将泰昌企业事实包注入章节写作约束，禁止水利施工、桩基、防渗墙、BIM、建造师、施工总承包等不适用内容；74 个章节全部通过真实 `deepseek-v4-flash` 重写。
- 事实约束重写记录：`docs/development/runs/run_20260612_taichang_fact_grounded_full_rewrite.md`，状态 PASS；目标/成功/失败为 `74/74/0`，标题修正 `30`，占位从 `845` 降至成品 `649`，禁用主题命中 `0`。
- 真实导出链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice -> LibreOffice PDF`，验收记录 `docs/development/runs/run_20260612_taichang_fact_grounded_final.md`。
- 本次真实验收结果：状态 PASS；源项目 74 个章节节点、74 个有正文；DOCX 段落 `2834`、标题 `74`、目录条目 `65`、表格 `130`；图片候选/选中/插入/失败为 `597/24/24/0`；页眉页脚、目录点引导线、`PAGEREF`、`PAGE/NUMPAGES`、中文字体、无黑色方块、无重复父标题、无图片裁剪均通过；LibreOffice 字段刷新成功。
- 残留占位归类：`docs/rag/taichang-bid-remaining-placeholders-classification-20260612.md` 和 CSV `docs/rag/runs/run_20260612_taichang_fact_grounded_remaining_placeholders.csv`；649 处逐项归类为 P0 `436`、P1 `155`、P2 `58`。
- 自动化回归：`.venv/bin/python -m pytest tests/test_length_settings.py tests/test_section_generation_autoresume.py tests/test_docx_export.py -q`，结果 `51 passed, 1 warning`。

### 2026-06-14 正文编辑与 DOCX 导出一致性验收记录

- 背景：确认用户在系统正文编辑器中修改正文后，实际 Word 导出是否严格使用修改后的正文。
- 代码链路复核：前端 `BidEditor.downloadDocx` 会传入当前 `chapters` 生成的 `sectionsSnapshot`；后端 `download-docx` 任务将 `sectionsSnapshot` 传给 `build_project_bid_markdown`，导出时优先使用快照正文，否则读取 `bid_sections.content`。
- 真实回归：`docs/development/runs/run_20260614_editor_content_export_consistency.md` 和对应 JSON。
- 验证项目：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`。
- 验证链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证结果：状态 PASS；已保存到 `bid_sections.content` 的唯一标记进入 DOCX；未保存但通过 `sectionsSnapshot` 传入的唯一标记也进入 DOCX；测试结束后已恢复数据库原章节正文。
- 结论：正文编辑功能对正式 Word 导出有效。后续修改前端导出参数、章节保存接口或后台导出任务时，必须保留该回归。

### 2026-06-17 泰昌参考模板标书成品度收口验收记录

- 背景：客户反馈生成标书像半成品，且没有贴近客户提供的参考标书结构。本轮按正式投标文件标准收口真实项目导出观感，同时保持泰昌/辽宁/河北豪乾资料边界。
- 修复：
  - 纯物资供货大纲改为 23 节参考结构，覆盖业绩、投标函、商务响应、技术响应、报价文件和附件索引，禁止施工组织、水利、BIM、建造师等模板污染。
  - 章节写作注入泰昌核验事实包，并新增正式占位归并，避免 `【待补充】` 大量重复铺满正文和表格。
  - DOCX 导出记录 `formal_readiness`，包含模板 ID、参考策略、空章节数、占位数和正式必填缺口；前端导出完成提示优先展示未达正式标准原因。
  - 容器章节不再写入 `待补充章节正文。`，空章节统计排除容器节点。
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`。
- 真实导出链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice -> LibreOffice PDF`。
- 验证记录：`docs/development/runs/run_20260617_p1c7_taichang_reference_bid.md` 和对应 JSON。
- 本次真实验收结果：源项目 23 个章节节点、19 个叶子章节、19 个叶子章节有正文、空叶子章节 0；DOCX 段落 `1799`、标题 `23`、表格 `36`；图片 selected/inserted/failed 为 `24/24/0`；目录标题、页眉、`PAGE/NUMPAGES/PAGEREF` 字段、宋体配置和 PDF 预览均通过；禁用主题命中 0。
- 正式状态：readiness 为 `false`，原因是仍有 `39` 处客户确认占位和 `15` 个正式必填字段未确认。系统不得编造报价、税率、保证金、授权代表、签署日期等客户决策字段，必须由客户或招标文件补齐后重新导出最终版。

### 2026-06-18 正式导出门禁真实验收记录

- 背景：P4-11 已完成章节候选确认值批量应用与导出前门禁，需要确认真实 DOCX/PDF 验收不会把“可生成文件”误判为“可正式交付”。
- 修复：`scripts/rag/verify_taichang_full_bid_acceptance.py` 已读取导出 metadata 中的 `formal_readiness`；当 `ready=false` 时，验收脚本直接 FAIL，并在报告中输出空叶子章节、正文占位符和正式必填缺口。
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`。
- 真实导出链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice -> LibreOffice PDF`。
- 验证记录：`docs/development/runs/run_20260618_formal_export_gate_real_acceptance.md` 和对应 JSON。
- 本次真实验收结果：状态 `FAIL`，符合门禁预期；章节节点 `102`，有正文章节 `14`，空叶子章节 `63`，正文占位符 `26`，正式必填缺口 `17`；图片候选/选中/插入/失败为 `597/24/24/0`；目录、页眉页脚字段、图片比例、表格格式和 LibreOffice 字段刷新通过，但 `has_supplement_testing_assets` 仍失败。
- 缺口字段包括：招标人、包号、包名称、货物清单摘要、投标总价、投标总价大写、税率、投标保证金金额、投标保证金形式、交货期承诺、质保期承诺、投标有效期、授权代表、授权代表身份证号、签署日期、技术参数表候选摘要、技术偏差表候选。
- 自动化回归：`.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_docx_export.py -q`，结果 `46 passed, 1 warning`；本地 RAG 门禁 `run_20260618_formal_export_gate_real_acceptance` PASS。
- 结论：当前项目链路可以真实生成 DOCX/PDF，但尚不能作为正式投标文件交付。下一步必须先补齐客户确认字段、清理 26 处正文占位符、补生成剩余 63 个空叶子章节，再复跑本验收脚本。

### 2026-06-18 P1C-10 正式导出门禁正文与图片收口记录

- 背景：承接上一轮门禁失败项，继续在真实项目中收口空章节、正文占位符和补充包图片覆盖，不自动填写报价、保证金、授权代表、签署日期等客户决策字段。
- 修复：
  - 新增 `scripts/rag/run_taichang_formal_export_gate_closure.py`，用真实 Flask/app 上下文应用可确认字段、生成剩余叶子章节、清理正式占位符并输出收口报告。
  - 前导预填增加辽宁招标人兜底识别，可从“国网辽宁”项目语境确定 `国网辽宁省电力有限公司`，不再把招标人留为人工缺口。
  - DOCX 自动插图增加补充包项目业绩最低覆盖逻辑，在 24 张总上限内保证项目业绩证明资产不少于 2 张，同时保持泰昌企业事实过滤。
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`。
- 章节生成记录：`docs/development/runs/run_20260618_p1c10_formal_gate_closure.md`，状态 `PASS`；目标空章节 `88`，成功生成 `88`，失败 `0`，占位符清理 `157` 处；收口后空叶子章节 `0`，正文占位符 `0`，正式必填缺口 `11`。
- 真实导出链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice -> LibreOffice PDF`。
- 验证记录：`docs/development/runs/run_20260618_p1c10_formal_gate_acceptance_final6.md` 和对应 JSON。
- 本次真实验收结果：状态 `FAIL`，但仅因客户确认字段阻断；章节节点 `102`，有正文章节 `102`，空叶子章节 `0`，正文占位符 `0`，正式必填缺口 `11`；图片候选/选中/插入/失败为 `597/23/23/0`；补充包项目业绩资产 `2`、检测能力资产 `4`、检验报告资产 `5`；表格 `166` 个；封面、目录、页眉页脚、字体、表格、图片比例、内部字段泄露检查和 LibreOffice 字段刷新均通过。
- 剩余缺口字段：投标总价、投标总价大写、税率、投标保证金金额、投标保证金形式、交货期承诺、质保期承诺、投标有效期、授权代表、授权代表身份证号、签署日期。
- 自动化回归：`.venv/bin/python -m pytest tests/test_docx_export.py -q`，结果 `37 passed, 1 warning`；本地 RAG 门禁 `run_20260618_p1c10_formal_gate_closure` PASS。
- 结论：DOCX/PDF 的正文完整度、图片资产、版式和字段刷新已达到自动化门禁要求；正式交付门禁仍应保持阻断，直到客户确认 11 个投标决策字段后重新导出。

### 2026-06-19 P1C-11 内部演示完整标书验收记录

- 背景：客户未回复正式投标决策字段，但当前目标是先参考客户提供的标书模板，真实输出一份完整标书用于内部演示和系统回归。
- 处理方式：`scripts/rag/run_taichang_formal_export_gate_closure.py` 新增 `--simulate-formal-fields` 显式开关，仅在内部演示回归时补齐投标总价、税率、保证金、交货期、质保期、投标有效期、授权代表、身份证号和签署日期等 11 个字段；metadata 标记 `simulated_for_regression=true`，并记录“非正式投标承诺”说明。
- 模拟值口径：投标总价 `8888888.00 元`、税率 `13%`、投标保证金 `100000.00 元`、投标保证金形式 `投标保证保险`、交货期模拟合同签订后 30 日内供货、质保期模拟到货验收合格后 12 个月、投标有效期 `90` 天、授权代表和身份证号使用测试值。
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`。
- 模拟确认值应用记录：`docs/development/runs/run_20260619_p1c11_simulated_complete_bid.md`，状态 `PASS`；应用前导确认字段 `31` 个，其中内部测试模拟字段 `11` 个；收口后空叶子章节 `0`，正文占位符 `0`，正式必填缺口 `0`。
- 真实导出链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice -> LibreOffice PDF`。
- 验证记录：`docs/development/runs/run_20260619_p1c11_simulated_complete_bid_acceptance.md` 和对应 JSON。
- 本次真实验收结果：状态 `PASS`；章节节点 `102`，有正文章节 `102`，目录条目 `102`，表格 `166` 个；图片候选/选中/插入/失败为 `597/23/23/0`；补充包项目业绩资产 `2`、检测能力资产 `4`、检验报告资产 `5`；封面、目录、页眉页脚、字体、表格、图片比例、内部字段泄露检查、页码字段和 LibreOffice 字段刷新均通过。
- 输出文件：
  - DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`
  - PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.pdf`
- 自动化回归：`.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_docx_export.py -q`，结果 `46 passed, 1 warning`；本地 RAG 门禁 `run_20260619_p1c11_simulated_complete_bid` PASS。
- 结论：完整标书演示版已真实生成并通过 DOCX/PDF 成品结构验收；该版本依赖模拟字段，只能用于内部演示/回归测试，正式投标前必须替换为客户真实确认值并复跑验收。

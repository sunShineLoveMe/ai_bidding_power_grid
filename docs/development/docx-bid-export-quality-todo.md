# 标书文档编写与正式导出质量待办清单

更新日期：2026-06-11

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
| 待办 | 格式预检报告 | 检查目录缺失、页码未刷新、表格越界、图片失败、非泰昌资产误用 |
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

### 2026-06-11 封面字段结构化来源修复记录

- 封面字段结构化来源补齐已完成：招标文件解析阶段新增 `project_meta.cover_fields`、`cover_field_sources`、`cover_field_missing`，DOCX 导出优先读取结构化字段，OnlyOffice 预览和 Celery 正式导出均接入同一链路。
- 抽取字段范围：`项目名称`、`文件类型`、`招标编号`、`分标编号`、`分标名称`、`包号`、`包名称`、`招标人`、`招标代理机构`。
- 安全策略：字段缺失时记录缺失，不编造；当解析文本出现 `项目名称： 招标编号： 分标名称：` 这类空字段串联时，不把字段名误识别为字段值。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_native_parse_ingestion.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q`，结果 `57 passed, 5 warnings`。
- 真实导出链路：项目 `4bc3ee73-9ec5-4184-aafd-eaede9f90798`，执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260611_docx_quality_p0_structured_cover_fields.md` 和 `docs/development/runs/run_20260611_docx_quality_p0_structured_cover_fields.json`。
- 本次真实导出结果：封面字段来源 `uploaded_tender_structured_extract`，封面包含 `项目名称=国网辽宁电力2025年第三次物资协议库存招标采购`、`文件类型=投标文件`、`招标编号=2225AC`；当前历史解析文本缺失可靠的 `分标编号/分标名称/包号/包名称`，已记录在 `cover_field_missing`，未做猜测填充。

# 标书文档编写与正式导出质量待办清单

更新日期：2026-06-09

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
| 待办 | 封面字段结构化来源补齐 | 从项目解析 metadata 或招标文件结构化结果稳定补齐分标编号、分标名称、包号/包名称，不依赖正文猜测 |
| 待办 | 目录稳定性验收 | 独立目录页、最多 3-4 级、点引导线、页码右对齐、字段刷新成功 |
| 已完成 | 目录标题去重 | 子章节不得重复父章节前缀，例如 `2.1.1 响应要求`，不得输出 `2.1.1 企业基本资格资料 - 响应要求` |
| 待办 | 正文格式统一 | 字体、字号、行距、首行缩进、标题层级、分页规则稳定 |
| 已完成 | Mermaid/流程图源码清理 | Mermaid 能转图则插入图片，转换失败不得把源码块写入正式 DOCX |
| 待办 | 表格正式化 | A4 内可读、边框清晰、表头加粗、必要时重复表头、不大面积越界 |
| 已完成 | 图片资产正式化 | 只允许泰昌企业事实资产，禁止虚假图片路径，正式 DOCX 不展示内部来源库、匹配依据或得分，记录图片候选/选中/插入/失败数 |
| 待办 | 真实导出验收记录 | 用真实项目导出 DOCX，记录封面、目录、正文、表格、图片、页眉页脚、字段刷新状态 |

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

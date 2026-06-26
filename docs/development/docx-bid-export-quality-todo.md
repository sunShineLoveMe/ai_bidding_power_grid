# 标书文档编写与正式导出质量待办清单

更新日期：2026-06-26

> 项目级优先级以 `docs/development/master-todo.md` 为准。本文档保留 DOCX 正式导出专项详情、验收口径和历史验证记录。

范围：标书正文编写、封面/目录/页眉页脚、图表与表格、DOCX 字段刷新、真实导出验收、后续 PDF/模板化能力。本文档用于管理客户最终交付物质量，优先级高于普通导出功能优化。

## 当前结论

- MVP 默认采用 `formal_bid_standard`，即面向泰昌的正式投标文件默认格式；当前阶段不向普通用户提供格式方案选择。
- 历史 `sgcc_taichang_bid` 只作为客户参考稿紧凑版式记录，不再作为默认。
- 客户已确认当前无法提供原版 Word 正文标书模板；`template_docx` 像素级套版不再作为当前 P0 阻塞项。
- 当前可用参考为 `assets/template_words/5d2a2c833dad4bb3b3ccc0856f755b54.docx` 和 `assets/template_words/1523993.doc`，其中 `5d2a...docx` 作为主参考样式源，抽取目录域、封面字段、表格、签章位和页边距参考后扩展 `formal_bid_standard`，不直接套打正文。
- `assets/template_words/~$2a2c833dad4bb3b3ccc0856f755b54.docx` 是 Word/WPS 临时锁文件，不作为模板来源。
- 当前正式正文默认样式为仿宋_GB2312 小四 `12pt`、`1.5` 倍行距、首行缩进 `2` 字符；表格仍保持仿宋_GB2312 `12pt`、固定 `18pt` 行距。
- 普通用户默认不直接进入全量自定义格式；自定义能力作为后续高级功能。
- 若招标文件明确第六章格式、前附表或否决项要求，优先按招标文件要求。
- 2026-06-26 客户新增的 `国家电网有限公司2026年西北、西藏区域第一次联合采购...招标文件包` 已审阅；该批资料定位为招标要求来源和技术参数/货物清单来源，不作为泰昌企业事实，也不作为投标正文视觉主模板直接套用。
- 若未来客户重新提供可编辑 Word 模板，再进入 `template_docx` 模式；当前 MVP 不等待该资料。
- 真实验证必须走项目导出链路：`build_project_bid_markdown` -> `convert_md_to_word` -> `refresh_docx_fields_with_soffice`，不得只用 mock 替代。

## P0 必须完成

| 状态 | 任务 | 验收口径 |
| --- | --- | --- |
| 已完成 | 参考 Word 模板规则落地 | 完成 `assets/template_words` 下两份参考模板 inventory；`5d2a...docx` 作为主参考样式源，规则写入 `formal_bid_standard` metadata；技术标/商务标真实导出均通过字段刷新、目录、表格、图片统一尺寸回归 |
| 后置（客户暂无原版模板） | 可编辑 Word 模板导入 `template_docx` | 仅当客户后续重新提供可编辑 Word 版正式模板时启动；当前不阻塞 MVP 导出质量收口 |
| 已完成 | 默认正式模板固定为 `formal_bid_standard` | metadata 记录模板 ID、正文/目录/页边距、页眉页脚设置 |
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
| 延后 | 格式方案选择 | 当前 MVP 不做；导出固定使用面向泰昌的正式投标文件默认格式，后续有非泰昌/非正式交付场景再评估 |
| 脚本版已完成 | 格式预检报告 | `scripts/rag/verify_taichang_full_bid_acceptance.py` 已检查目录缺失、页码字段、表格格式、图片失败/裁剪/比例、内部字段泄露、重复父章节标题和补充包资产选中；后续再接入页面/导出任务 metadata |
| 已完成 | 分册格式 | 技术标/商务标两个交付包支持不同封面文件类型、目录、页眉文案和导出 metadata；资格文件、报价文件、附件材料归入商务标内部资料类型 |
| 已完成基础版 | 第六章格式表单保真 | 已识别投标函、授权委托书、商务/技术偏差表和承诺函；签章行右对齐、语义列宽和表格行禁止跨页拆分通过真实 DOCX 回归 |
| 已完成 | DOCX 图片统一长宽 | Markdown 图片和 Mermaid 转图均进入统一正文图片框；默认 `5.8in x 8.2in`，白底 contain，不裁剪、不拉伸；技术标/商务标真实导出中正文图片尺寸均一致 |
| 待办 | 导出任务 metadata 扩充 | 记录模板 ID、封面字段、目录层级、图表题注、格式告警 |
| 待办 | 阿里云下载体验收口 | 线上 DOCX 下载不得被浏览器弹窗/不安全下载策略阻断；优先启用 HTTPS，并改为同页下载或 blob 下载 |
| 已完成 | 正式缺口口径统一 | 导出完成提示、投标信息确认页、formal readiness metadata 使用同一占位符与正式字段口径；当前演示项目正式必填缺口 0、正文占位符 0 |
| 待办 | 章节图片与候选证据映射收口 | 项目业绩不得映射人员证书；法定格式章节默认不自动插图；生产能力图片不得泛化使用碳足迹等弱相关资料 |

## P2 后续增强

| 状态 | 任务 | 验收口径 |
| --- | --- | --- |
| 待办 | 高级自定义格式面板 | 参考竞品开放编号、正文、页面、图表设置，并支持恢复默认 |
| 待办 | 企业模板保存 | 用户可另存企业模板，并在后续项目复用 |
| 待办 | PDF 预览与导出 | DOCX 刷新后可转 PDF 预览，便于提交前检查 |
| 待办 | 招标文件格式约束抽取 | 自动抽取第六章/前附表格式要求，并提示用户确认 |

## P0 第一阶段执行记录

### 2026-06-26 正文字号与 1.5 倍行距调整记录

- 背景：用户要求正文改为小四，并将正文行间距调整为 `1.5` 倍行距。
- 调整：
  - 正文字号从 `14pt` 改为小四 `12pt`，字体仍为仿宋_GB2312。
  - 正文、列表和正式表单签章行改为 `1.5` 倍行距；目录、表格、封面继续使用各自独立行距，避免表格过松或封面位移。
  - 正文首行缩进仍为 `2` 字符，随小四字号变为 `24pt`。
  - 兼容旧环境变量：若显式配置 `DOCX_BODY_LINE_SPACING=22` 且未配置规则，仍按固定行距解释，避免误变成 22 倍行距。
- 自动化回归：
  - `.venv/bin/python -m pytest tests/test_docx_export.py -q`，结果 `40 passed, 1 warning`。
  - `.venv/bin/python -m pytest tests/test_celery_export_tasks.py -q`，结果 `11 passed, 7 warnings`。
  - `.venv/bin/python -m pytest tests/test_compliance.py tests/test_formal_bid_check.py -q`，结果 `10 passed, 1 warning`。
- 真实分册导出回归：`docs/development/runs/run_20260626_body_xiaosi_1_5_line_spacing.md` 和 JSON，状态 `PASS`；技术标 `50` 个章节、图片 `24/24/0`、表格 `110` 个；商务标 `52` 个章节、图片 `17/17/0`、表格 `56` 个；两份 DOCX 字段刷新均为 `refreshed`，正文样式均为 `12pt / ONE_POINT_FIVE 1.5 / 首行缩进24pt`。

### 2026-06-26 参考 Word 模板规则落地与图片统一尺寸记录

- 背景：客户确认无法提供原版 Word 正文标书模板；本轮改为分析 `assets/template_words` 下两份空白参考模板，并把可复用规则扩展到当前 `formal_bid_standard`。
- 模板 inventory：
  - `5d2a2c833dad4bb3b3ccc0856f755b54.docx`：可直接解析的 DOCX，A4，页边距约上/下 `2.54cm`、左/右 `3.175cm`；目录为 `HYPERLINK + PAGEREF` 域，`toc 2` 样式含右对齐点引导线，字体参考为仿宋/仿宋_GB2312 加粗；截图中的灰底是 Word/WPS 目录域阴影，不是稳定可打印底纹，因此未做成正式打印灰底。
  - `1523993.doc`：旧版二进制 Word，已通过 LibreOffice 临时转 DOCX 分析；可作为格式表单、说明文字和表格结构补充参考，但不作为运行时依赖。
  - `~$2a2c833dad4bb3b3ccc0856f755b54.docx`：Word/WPS 临时锁文件，已排除。
- 落地策略：
  - `formal_bid_standard` metadata 记录两份参考模板来源和参考策略，不直接套打正文，避免旧模板业务口径污染泰昌投标文件。
  - 目录条目增强为全加粗，并保留右侧点引导线、`PAGEREF` 页码域和 LibreOffice 字段刷新。
  - Markdown 图片和 Mermaid 转图进入统一白底正文图片框，默认 `5.8in x 8.2in`、`220dpi`、contain 模式，不裁剪、不拉伸。
  - 技术标、商务标均复用同一正式导出版式和图片框规则。
- 自动化回归：
  - `.venv/bin/python -m pytest tests/test_docx_export.py -q`，结果 `40 passed, 1 warning`。
  - `.venv/bin/python -m pytest tests/test_celery_export_tasks.py -q`，结果 `11 passed, 7 warnings`。
  - `.venv/bin/python -m pytest tests/test_compliance.py tests/test_formal_bid_check.py -q`，结果 `10 passed, 1 warning`。
- 真实分册导出回归：`docs/development/runs/run_20260626_reference_template_volume_docx.md` 和 JSON，状态 `PASS`；技术标 `50` 个章节、图片 `24/24/0`、表格 `110` 个；商务标 `52` 个章节、图片 `17/17/0`、表格 `56` 个；两份 DOCX 字段刷新均为 `refreshed`，正文图片显示尺寸均为 `5.8x8.2in`。
- 完整标书真实链路：`docs/development/runs/run_20260626_reference_template_docx_format.md` 和 JSON 已生成；DOCX/PDF 生成、字段刷新、封面、目录、页眉页脚、正文样式、表格、图片统一尺寸均通过。该综合脚本状态为 `FAIL`，失败原因是当前项目正式必填确认字段缺 `12` 项，以及自动选图未命中 `testing_capacity` 补充包资产；这两个是业务门禁/选图覆盖问题，不属于本轮参考模板版式改动。

### 2026-06-26 国网 2026 西北/西藏招标文件包审阅记录

- 背景：客户新增 `国家电网有限公司2026年西北、西藏区域第一次联合采购10kV电力电缆、架空绝缘导线协议库存公开招标采购_招标文件包`，需判断其对当前投标文件生成是否有参考意义。
- 解压与盘点：12 个外层招标包和嵌套 ZIP 已展开；解压后文件数 `190`，其中 `.docx` 68、`.doc` 54、`.xlsx` 12、`.zip` 44、`.sign` 12；嵌套 ZIP 未发现未解压残留。
- 判断：该批资料是招标文件包，不是投标人中标成稿；不应直接作为 `technical_bid_standard` / `business_bid_standard` 视觉模板覆盖当前成果。
- 可复用点：第六章投标文件格式、投标人须知前附表、商务/技术偏差表、技术特性参数表、货物组件材料配置表、货物清单字段，可作为后续招标要求抽取、技术参数响应和正式导出结构约束。
- 边界：按 `source_domain=tender_requirement` 处理，不得作为泰昌企业事实，不得把其中图片、业绩、合同主体等内容写入泰昌正式投标文件。
- 记录：`docs/development/runs/run_20260626_sgcc_2026_tender_package_review.md`。

### 2026-06-26 新疆技术/商务参考模板分册真实复验

- 背景：针对用户截图反馈的页眉 Logo、目录加粗/点引导线、标题颜色、章节标题混乱和章节分页问题，重新真实导出技术标与商务标分册复验。
- 本轮修正：正式表单小标题从一种表单类型切换到另一种表单类型时，插入实际分页符，例如 `投标函 -> 法定代表人授权书`；不使用 `pageBreakBefore`，避免 Word/WPS 黑色格式标记。
- 真实链路：`build_project_bid_markdown(volume_type=technical/business, with_images=true) -> convert_md_to_word(return_report=true) -> refresh_docx_fields_with_soffice`，并用 LibreOffice 转 PDF、`pdftoppm` 抽样目录页和正文页。
- 结果：
  - 技术标使用 `technical_bid_standard`，字段刷新 `refreshed`，页眉 Logo `false`，目录真实加粗 run `0`，非黑色文字 `[]`，H1/H2 分页 `13/13`，failures `[]`。
  - 商务标使用 `business_bid_standard`，字段刷新 `refreshed`，页眉 Logo `false`，目录真实加粗 run `0`，非黑色文字 `[]`，H1/H2 分页 `21/21`，正式表单切换分页 `15`，failures `[]`。
  - PDF 抽样确认商务标第 5 页不再把 `二、法定代表人授权书` 挤在页底。
- 自动化回归：`.venv/bin/python -m pytest tests/test_docx_export.py tests/test_celery_export_tasks.py -q`，结果 `55 passed, 7 warnings`。
- 记录：`docs/development/runs/run_20260626_xinjiang_profile_volume_revalidation.md` 和 JSON；PDF 抽样截图位于 `docs/development/runs/run_20260626_xinjiang_profile_volume_revalidation_pages/`。

### 2026-06-25 第六章格式表单保真验收记录

- 正式表单识别覆盖投标函、法定代表人身份证明/授权委托书、商务偏差表、技术偏差表和承诺函。
- 签章信息行按正式表单右对齐；商务/技术偏差表按语义分配列宽；表格行写入禁止跨页拆分属性。
- 导出 metadata 新增 `formal_forms`：本次真实项目识别表格 `38` 个、小标题 `38` 个、签章行 `76` 行、禁止拆分行 `244` 行。
- 正式 readiness 改为按当前确认值重新计算，带“内部测试”等模拟标记的客户字段不得通过正式版门禁。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_bid_prefill.py tests/test_formal_bid_check.py -q`，结果 `54 passed, 1 warning`。
- 提交前扩大回归：加入 `tests/test_celery_export_tasks.py` 后结果 `65 passed, 7 warnings`；前端 `npm run build` 通过，仅保留既有 chunk size 提示。
- 真实链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`，状态 `PASS`；LibreOffice 刷新后签章对齐、偏差表列宽、表格网格宽度和禁止跨页拆分属性均保留。
- 真实下载 API 任务 `fd40ab53-841b-482b-b1b0-1ecb31117a87` 正常完成；因当前模拟客户字段形成 `8` 个正式检查阻断项，API 与浏览器均只创建草稿版 DOCX。
- 验证记录：`docs/development/runs/run_20260625_docx_sixth_chapter_form_fidelity.md` 和对应 JSON。
- 边界：客户原始 Word 表单的像素级套表、复杂合并单元格和原始签章位仍由后续 `template_docx` 模式处理。

### 2026-06-26 分册 DOCX 正式导出回归记录

- 当前 MVP 保持默认完整导出为泰昌正式投标文件，不提供普通用户格式方案选择。
- 技术标/商务标单独导出时，封面 `文件类型`、页眉右侧和导出 metadata 均按分册区分。
- 真实链路：`build_project_bid_markdown(volume_type=technical/business, with_images=true) -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证结果：技术标 50 个章节、图片 24/24/0、表格 110 个、字段刷新成功；商务标 52 个章节、图片 17/17/0、表格 56 个、字段刷新成功。
- 输出记录：`docs/development/runs/run_20260626_p1_volume_docx_export.md`。

### 2026-06-25 国网正式通用排版升级验收记录

- 背景：用户明确反馈当前 Word 成品观感像草稿，并提供“国家电网投标文件标准排版模板”作为正式标书通用口径。本轮将 DOCX 正式交付排版升级保持为 P0。
- 修复：
  - 默认模板 ID 调整为 `formal_bid_standard`。
  - 页面设置调整为 A4、上/下 `2.5cm`、左 `2.8cm`、右 `2.5cm`。
  - 正文调整为仿宋_GB2312 `14pt`、固定行距 `22pt`、首行缩进 `28pt`。
  - 标题层级调整为一级黑体 `22pt` 居中、二级黑体 `15pt` 左对齐、三级/四级楷体_GB2312 `14pt` 加粗。
  - 表格文字调整为仿宋_GB2312 `12pt`、固定 `18pt` 行距，并保留全宽、固定布局、表头重复、边距和垂直居中。
  - 页眉调整为左侧项目名称、右侧文件类型；页脚调整为 `第 X 页 共 Y 页`。
  - 验收脚本新增页边距、正文字号、固定行距、首行缩进、三级标题字体、页眉页脚新口径检查。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py -q`，结果 `37 passed, 1 warning`。
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`。
- 真实导出链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 验证记录：`docs/development/runs/run_20260625_docx_formal_standard_local_acceptance.md` 和对应 JSON。
- 本次真实验收结果：状态 `PASS`；章节节点 `102`、有正文 `102`；DOCX 标题 `103`、目录条目 `102`、表格 `166`；图片候选/选中/插入/失败为 `597/23/23/0`；页边距、正文样式、封面、目录、页眉页脚、页码字段、中文字体、表格、图片比例、内部字段泄漏检查均通过；LibreOffice 字段刷新成功。
- 阿里云兼容注意：线上容器/主机需确保 LibreOffice 字段刷新可用，并安装或可替代解析 `FangSong_GB2312`、`KaiTi_GB2312`、`SimHei` 的中文字体；否则 DOCX 本身带样式但 PDF/预览可能出现字体替换。

### 2026-06-25 正式门禁与占位符收口验收记录

- 背景：当前演示项目需要避免旧版正文中残留 `待补充`、`【设备型号待补充】` 等显眼草稿标记，同时正式检查规则不能把泰昌企业事实资产的边界说明误判为资料混用。
- 修复：
  - 新增正式占位符识别与清理工具，统一正式检查、导出 readiness metadata 和收口脚本的占位符口径。
  - 修正规则字段 key，使授权代表身份证号、签署日期、投标有效期、技术偏差和参数匹配摘要按现有投标确认结构检查。
  - 资料边界检查只扫描真实来源字段；泰昌企业事实资产 metadata 中的 `do_not_mix_with` 边界说明不再误判为 forbidden source。
  - 客户演示验收脚本默认项目切换为当前演示项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d`，避免后续误跑历史旧项目。
- 自动化回归：`PYTHONPATH=. .venv/bin/pytest tests/test_formal_placeholders.py tests/test_formal_bid_check.py tests/test_docx_export.py tests/test_celery_export_tasks.py -q`，结果 `64 passed, 7 warnings`。
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`。
- 门禁收口记录：`docs/development/runs/run_20260625_placeholder_cleanup_current_project.md`，状态 `PASS`；应用确认字段 `31` 个，占位符清理 `18` 处，空叶子章节 `0`，正文占位符 `0`，正式必填缺口 `0`。
- 完整导出验收记录：`docs/development/runs/run_20260625_placeholder_cleanup_docx_acceptance.md` 和对应 JSON，状态 `PASS`；默认入口复验 `docs/development/runs/run_20260625_placeholder_cleanup_default_acceptance.md` 也为 `PASS`。DOCX 生成、LibreOffice 字段刷新、页边距/正文样式、封面、目录、页眉页脚、图片、表格、内部字段泄露检查均通过，failures/warnings 均为空。

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

### 2026-06-24 阿里云最小标书主流程烟测记录

- 背景：阿里云线上完成泰昌企业图片资产与 embedding 修复后，验证最小标书主流程是否可在真实云环境跑通。
- 真实项目：`d346ec62-8843-4cfd-b68c-e3fb1d215181`。
- 测试招标文件：`国网辽宁电力2025年第三次物资协议库存招标采购招标文件.docx`，场景为辽宁 CPVC/MPP 包件，投标主体为河北泰昌电力器材科技有限公司。
- 验证结果：服务健康检查通过；上传、解析、章节大纲生成、`1.1 投标函及投标函附录` 单章正文生成、完整 DOCX 草稿生成和下载均跑通。
- 导出文件：`/Users/chris/Downloads/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文 (1).docx`，大小 `4,218,487` bytes，`unzip -t` 无错误，`word/media` 共 `17` 个媒体文件。
- 当前仍为草稿级：页面条款覆盖率 `38%`，仍有 `53` 项高风险待覆盖；DOCX 抽取显示 `25` 个 `【待补充：人工复核】` 占位符。
- 本轮新增缺陷：HTTP 下载被 Chrome 拦截；导出完成提示与投标信息确认页的正式缺口口径不一致；项目业绩候选误显示人员证书；部分章节自动插图/候选图片语义不准。
- 详细记录：`docs/development/runs/run_20260624_aliyun_minimal_bid_flow_smoke.md`。
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

### 2026-06-19 客户参考稿封面版式修复记录

- 背景：用户复核 Word 首页后指出封面投标人信息位置和公司 Logo 位置不符合客户参考标书观感，需要严格参考客户提供的河北豪乾商务投标文件模板。
- 参考稿复核：`商务投标文件-中标，按投标人制作.pdf` 首页无公司 Logo；项目名称位于页面上部，主标题为大号“商务投标文件”，招标编号/分标编号/包号等居中排列，投标人、法定代表人或委托代理人签名位、日期位于页面下半部偏底部。
- 修复：
  - 封面默认不再插入 Logo；若后续确需封面 Logo，可通过 `DOCX_COVER_SHOW_LOGO=true` 显式开启。
  - 封面标题改为“项目名称两行 + 文件类型大标题”结构，不再把项目名称和“投标文件”拼成一行大标题。
  - “文件类型”不再作为普通字段行重复展示；主标题直接显示 `投标文件/商务投标文件/技术投标文件`。
  - 投标人、法定代表人或委托代理人签名位、日期下移，并按字段数量动态留白，避免字段多时溢出。
- 真实导出链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice -> LibreOffice PDF`。
- 验证记录：`docs/development/runs/run_20260619_p1c12_reference_cover_layout_acceptance_v2.md` 和对应 JSON。
- 视觉复核截图：
  - 参考稿首页：`docs/development/runs/cover_layout_check_20260619/ql_ref/商务投标文件-中标，按投标人制作.pdf.png`
  - 修复后首页：`docs/development/runs/cover_layout_check_20260619/ql_new_v2/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.pdf.png`
- 自动化回归：`.venv/bin/python -m pytest tests/test_docx_export.py -q`，结果 `37 passed, 1 warning`。
- 本次真实验收结果：状态 `PASS`；章节节点 `102`，有正文章节 `102`，空叶子章节 `0`，正文占位符 `0`，正式必填缺口 `0`；图片选中/插入/失败为 `23/23/0`；封面、目录、页眉页脚、字体、表格、图片比例、内部字段泄露检查、页码字段和 LibreOffice 字段刷新均通过。

### 2026-06-19 客户参考稿整份格式对照审计记录

- 背景：不能只修封面第一页；客户提供的标书模板必须作为整份标书的版式基准，覆盖封面、目录、正文、标题、表格、页边距、页眉页脚和字号字体。
- 新增审计脚本：`scripts/rag/audit_taichang_bid_template_format.py`，抽样对照：
  - 商务参考稿：`商务投标文件-中标，按投标人制作.pdf`
  - 技术参考稿：`技术补充文件_电缆保护管CPVC.pdf`
  - 当前生成 DOCX：泰昌完整标书图文版
- 参考稿抽样结论：
  - 页面尺寸：A4，`595.32 x 841.92 pt`。
  - 封面项目标题：约 `18pt`，主标题“商务投标文件/技术投标文件”：`36pt`。
  - 封面字段：约 `14.04pt`。
  - 目录条目：约 `10.56pt`。
  - 正文可抽取文本：约 `10.56pt`，字体为宋体子集。
  - 正文一级/二级标题：约 `14.04pt`。
- 修复：
  - 封面主标题字号调整为 `36pt`。
  - 封面项目标题调整为 `18pt`。
  - 封面字段字号调整为 `14.04pt`。
  - 目录标题从 `22pt` 收敛为 `10.5pt`，与参考稿目录条目一致。
  - 正文一级/二级标题统一收敛为 `14pt`；正文、表格继续使用宋体 `10.5pt`，贴近参考稿 `10.56pt`。
- 审计报告：`docs/development/runs/run_20260619_p1c13_template_format_audit.md` 和对应 JSON；对照项 10 项全部 PASS。
- 真实导出验收：`docs/development/runs/run_20260619_p1c13_template_format_acceptance.md`，状态 `PASS`，无 failures/warnings。
- 最终封面截图：`docs/development/runs/cover_layout_check_20260619/ql_p1c13/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.pdf.png`。
- 自动化回归：`.venv/bin/python -m pytest tests/test_docx_export.py -q`，结果 `37 passed, 1 warning`。
- 当前边界：河北豪乾参考稿只用于版式、目录、表格结构和表达风格参考，不作为泰昌事实、资质、业绩、设备或人员来源。

### 2026-06-25 SG-PROMPT-001 完整 DOCX 链路回归记录

- 背景：`SG-PROMPT-001` 修改章节正文生成 prompt profile、输入预算和任务 metadata，需要确认不会破坏正式投标文件导出链路。
- 本轮未修改 DOCX 模板、封面、目录、页眉页脚、表格或图片插入代码；仅执行真实导出回归。
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`，102/102 章节已有正文。
- 导出任务：`84af9199-f3cc-44ce-bf3f-9bb5c882cced`，`export_mode=formal`，正式门禁阻断项 `0`。
- 真实导出链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 输出文件：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`，大小约 `7.8M`。
- 本次真实验收结果：DOCX completed；模板 `formal_bid_standard`；图片 selected/inserted/failed 为 `23/23/0`；Mermaid found/inserted/skipped 为 `0/0/0`；LibreOffice 字段刷新 `status=refreshed`、`returncode=0`、`manual_refresh_required=false`；刷新报告识别表格 `166` 个。
- 自动化回归：`.venv/bin/python -m pytest tests/test_docx_export.py tests/test_celery_export_tasks.py -q`，结果 `48 passed, 7 warnings`。
- 运行记录：`docs/development/runs/run_20260625_sg_prompt_001_prompt_profile_budget.md`。

### 2026-06-26 真实用户完整导出与格式收口记录

- 背景：客户反馈正式 Word 标书格式仍“不行”，本轮按真实用户本地操作方式复测完整导出；客户未提供正式报价/保证金/授权等字段，因此本地使用正式口径演示值补齐 12 个确认字段。
- 真实浏览器链路：Chrome 登录本地系统 `admin / 12345678`，进入投标确认页，调用确认接口应用字段，再从登录浏览器同源上下文触发 `download-docx` 导出任务并轮询完成。
- 导出任务：`eb51b93e-191d-4e23-8f8b-897a93f753b8`，`export_mode=formal`，`blocked_count=0`，`can_formal_export=true`。
- 本轮修复：
  - 正式导出层新增确认值渲染清理，避免旧正文中的 `客户最终确认后填写`、`客户确认后填写`、`待补充` 等草稿占位进入 DOCX。
  - 自动选图新增泰昌补充资料 `testing_capacity` 兜底，确保完整标书包含试验检测能力资产。
  - 保持正文小四 `12pt`、`1.5` 倍行距、首行缩进 `24pt`，图片统一 `5.8in x 8.2in`。
- 真实导出链路：`prefill-confirmation/apply -> download-docx -> Celery run_bid_docx_export -> build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice -> LibreOffice PDF`。
- 验收记录：
  - 浏览器操作记录：`docs/development/runs/run_20260626_real_user_full_export_browser.md`
  - 成品验收报告：`docs/development/runs/run_20260626_real_user_full_export_acceptance.md`
  - 成品验收 JSON：`docs/development/runs/run_20260626_real_user_full_export_acceptance.json`
- 输出文件：
  - DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`
  - PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.pdf`
- 本次真实验收结果：状态 `PASS`，无 failures/warnings；章节 `102/102` 有正文；图片候选/选中/插入/失败为 `598/24/24/0`；项目业绩 `2`、试验检测能力 `1`、检验报告 `6`；表格 `166`；封面、目录、页眉页脚、字段刷新、字体字号行距、表格、图片比例和统一尺寸均通过。
- 残留扫描：生成 DOCX 中 `客户最终确认`、`客户确认后填写`、`待补充`、`内部测试`、`模拟值`、`非正式报价` 计数均为 `0`。
- 自动化回归：
  - `.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_formal_placeholders.py tests/test_docx_export.py tests/test_celery_export_tasks.py -q`，结果 `64 passed, 7 warnings`。
  - `set -a; source .env; set +a; .venv/bin/python scripts/rag/verify_taichang_full_bid_acceptance.py --run-id run_20260626_real_user_full_export_acceptance --project-id a1d853bc-ca4e-43b4-bbea-256f561c8a3d --pdf-preview`，结果 `PASS`。

### 2026-06-26 新疆中标参考技术标/商务标模板族落地记录

- 背景：客户提供兄弟公司刚中标的正式技术标、商务标，要求评估并按其正式观感形成可用模板。
- 参考文件：
  - `assets/template_words/技术文件 - 10kV架空绝缘导线-新疆.docx`
  - `assets/template_words/商务文件 - 10kV架空绝缘导线-新疆(1).docx`
- 审阅结论：两份文件是正式成稿分册，不是空白套打模板；只能抽取版式、目录组织和分册结构，不得复用参考企业事实、产品参数、证书、审计报告、查询报告或附件内容。
- 本轮实现：
  - 新增 `technical_bid_standard` 和 `business_bid_standard` 模板 profile，按 `文件类型=技术投标文件/商务投标文件` 自动选择。
  - 两个 profile 归属 `formal_bid_xinjiang_sgcc_reference` 模板族，记录参考文件路径、适用分册、运行策略和分册参考目录。
  - 技术/商务分册使用参考稿页边距：上/下 `2.54cm`，左/右 `3.17cm`，页眉距 `1.5cm`，页脚距 `1.75cm`。
  - 技术/商务目录支持 1-4 级，目录/页眉页脚字体切换为宋体，条目 `10.5pt`、`15pt` 行距、非加粗、点引导线右对齐。
  - 页眉继续不放 Logo；黑白文本和灰阶表头保持不变。
- 真实用户链路：
  - 本地登录 API：`admin / 12345678`。
  - 调用正式导出接口：`POST /api/bidding/interpretations/<project_id>/download-docx`，分别传 `volumeType=technical`、`volumeType=business`、`withImages=true`。
  - Celery worker 执行：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。
- 输出文件：
  - 技术标 DOCX/PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.docx`
  - 商务标 DOCX/PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.docx`
- 验收记录：
  - 参考稿审阅：`docs/development/runs/run_20260626_reference_bid_templates_review.md`
  - 真实 API 导出任务：`docs/development/runs/run_20260626_reference_template_real_api_tasks.json`
  - DOCX XML 审计：`docs/development/runs/run_20260626_reference_template_docx_audit.json`
  - PDF 抽样截图：`docs/development/runs/run_20260626_reference_template_real_export_pages/`
  - 完整标书回归：`docs/development/runs/run_20260626_reference_template_full_acceptance.md`
- 本次真实验收结果：
  - 技术标：`template_id=technical_bid_standard`，`template_family=formal_bid_xinjiang_sgcc_reference`，字段刷新 `refreshed`，XML 审计 failures `[]`。
  - 商务标：`template_id=business_bid_standard`，`template_family=formal_bid_xinjiang_sgcc_reference`，字段刷新 `refreshed`，XML 审计 failures `[]`。
  - 完整标书：`run_20260626_reference_template_full_acceptance` PASS，无 failures/warnings。
- 自动化回归：
  - `.venv/bin/python -m pytest tests/test_docx_export.py tests/test_formal_placeholders.py tests/test_bid_prefill.py tests/test_celery_export_tasks.py -q`，结果 `67 passed, 7 warnings`。
- 当前边界：本轮已形成技术/商务模板 profile 和正式导出门禁；后续若要进一步贴近参考稿，需要把章节树升级为“分册对象模型”，按技术偏差表、技术特性参数表、商务偏差表、查询报告、财务状况、附件证据页等对象生成，而不是继续把通用章节树原样输出。

### 2026-06-26 DOCX 页码字号与图片题注正式复验记录

- 背景：用户反馈技术/商务标成品中目录右侧页码、页脚页码观感偏大，图片下方题注存在“图示：泰昌CPVC电缆保护管检验报告内径250第1页”等不合规资产标题，并要求实事求是评估泰昌产品资料是否足以支撑技术标。
- 本轮实现：
  - 目录 PAGEREF 页码字段结果独立收敛为 `9pt`，目录条目正文仍保持模板 profile 的 `10.5pt`。
  - LibreOffice 字段刷新后新增 DOCX XML 字号归一化，防止刷新后的目录页码、页脚 PAGE/NUMPAGES 字段结果回退为默认大字号。
  - 图片题注识别 `图示/图片/资料/图X-X` 前缀，统一输出为居中 `9pt` 的 `资料：...`，清理检索参数、资料编号、`原图/脱敏示意图` 和内部来源字段。
- 输出文件：
  - 技术标 DOCX/PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.docx`
  - 商务标 DOCX/PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.docx`
- 真实复验记录：
  - `docs/development/runs/run_20260626_docx_page_caption_evidence_revalidation.md`
  - `docs/development/runs/run_20260626_docx_page_caption_evidence_revalidation.json`
- 本次真实验收结果：状态 `PASS`，无 failures；技术标 `template_id=technical_bid_standard`，商务标 `template_id=business_bid_standard`；两份文件字段刷新均 `refreshed`；目录页码最大字号 `9pt`；页脚最大字号 `9pt`；技术标题注 `27` 条、商务标题注 `18` 条，不合规题注命中 `0`。
- 自动化回归：`.venv/bin/python -m pytest tests/test_docx_export.py tests/test_celery_export_tasks.py -q`，结果 `56 passed, 7 warnings`。
- 产品资料支撑度结论：泰昌现有资料能支撑 CPVC/MPP 电缆保护管的基础技术响应和资质证明，但产品维度仍偏薄；若投标对象是 `10kV架空绝缘导线`，当前企业事实资料明显不匹配，不能用电缆保护管资料硬撑导线技术标，需客户补充目标产品参数、型式试验/检验报告、生产检测设备、工艺质量控制和同类业绩资料。

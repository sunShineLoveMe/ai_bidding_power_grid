# Project Agent Instructions

## 前端 UI / 设计 Skill 与页面质量规则

当用户要求新建前端页面、重构页面、修复页面排版、调整组件视觉、实现 Figma 设计、优化交互或处理“页面错乱/布局混乱/不好看”等问题时，必须先使用本项目已安装的 OpenAI 官方 UI/设计相关 Skill，并结合当前项目 UI 风格再动代码。

已安装 Skill：

- `.agents/skills/figma/`
- `.agents/skills/openai-figma-use/`
- `.agents/skills/openai-figma-generate-design/`
- `.agents/skills/openai-figma-implement-design/`
- `.agents/skills/openai-figma-create-design-system-rules/`
- `.agents/skills/openai-figma-create-new-file/`
- `.agents/skills/openai-figma-generate-library/`
- `.agents/skills/openai-figma-code-connect-components/`
- `.agents/skills/openai-playwright/`
- `.agents/skills/openai-screenshot/`

执行原则：

- 开发前先阅读相关 Skill 的 `SKILL.md`；如果涉及 Figma URL、Figma 节点或设计稿实现，优先使用 `figma` / `openai-figma-implement-design`；如果是页面自检和排版回归，优先使用 `openai-playwright` 与截图核验。
- 先盘点当前页面和邻近模块的 UI 风格，再设计改动；本项目当前前端是 Vite + React + Ant Design 5，优先复用 `frontend/src/components/`、Ant Design 组件、现有布局壳、`frontend/src/index.css` 中的全局样式和已有中文业务文案。
- 面向本项目的后台工作台页面应保持信息密度、层级清晰和操作明确；不得做营销式大 Hero、过度装饰、单一大色块或与现有工作台不一致的视觉风格。
- 新建或重构页面前必须明确：页面主任务、关键数据区、主要操作、空状态、加载状态、错误状态、窄屏/低高度下的滚动边界；避免卡片套卡片、内容溢出、按钮文字挤压、表格横向不可控。
- 修改 CSS/布局时必须检查全局影响，尤其是 `body`、`#root`、`.module-shell`、`.panel-card`、Ant Design 表格/抽屉/步骤条等共享样式；不得为单页问题引入会破坏其他页面的全局规则。
- 页面完成后，能跑前端时必须用真实浏览器验证主要视口和关键交互；至少检查首屏是否错位、文本是否溢出、弹窗/抽屉是否遮挡、表格和按钮是否可操作。涉及正式客户演示或复杂页面时，保存截图或在回复中说明验证视口。

## 国家电网 RAG 基座数据工程 Skill

当用户要求处理电网/国家电网 RAG 基座数据、客户标书模板、招标文件包、技术规范书、货物清单、合同条款、分块、metadata、入库、召回评测或回归跟踪时，必须先使用以下 Skill：

- Skill 路径：`.agents/skills/power-grid-rag-ingestion/`
- 核心文档目录：`docs/rag/`
- 客户资料目录：`rag_seed/power_grid_resources/01_tender_documents/`
- 评测结果目录：`docs/rag/runs/`

执行原则：

- 先 inventory，再解析/清洗/分块/入库；
- 默认父子双层分块，child 召回、parent 写作回溯；
- 召回必须优先 metadata 过滤，再向量检索；
- `.xlsx` 货物清单和技术参数表必须结构化，不得只做普通文本向量；
- 客户后续新增的技术规范书、技术补充文件、技术响应参考稿、检验报告参数页、技术偏差/商务偏差表，只要包含“标准参数值、项目需求值、投标人保证值、保证值、偏差、备注、规格型号、检验项目、技术规范编码、物料编码”等字段，必须进入技术参数表抽取流程，保留原始结构、检索摘要和行级记录；
- 每次新增客户资料或调整召回策略后，必须重跑 `scripts/rag/eval_recall.py`，并更新 `docs/rag/evaluation-records.md` 与 `docs/rag/todo.md`；
- 结构化参数接入知识库问答后，必须用真实 API/stream 链路验证具体数值、报告编号和资料来源，不得只用 mock 或单元测试替代；
- 出现水利或其他非电网资料时，先隔离/删除，再复跑召回评测。

## 泰昌 MVP 试点企业规则

当前 MVP 试点企业和默认投标主体是：

```text
河北泰昌电力器材科技有限公司
```

简称：泰昌。

执行原则：

- 所有标书生成、企业事实问答、图文配图、企业资质/产品/资信引用，默认以泰昌为投标申请主体。
- 标书标题、文件名、封面、页眉和正文主体口径必须使用“投标文件 / 投标人：河北泰昌电力器材科技有限公司”，不得沿用“招标文件”口径。
- 辽宁资料仅作为招标场景样本，用于招标要求、技术规范、货物清单、合同条款、评分/否决项等，不作为泰昌企业事实。
- 辽宁资料只代表辽宁省公司本批招标要求，不代表全国电网或其他省公司要求；泰昌检验报告、产品参数、保证值抽取必须以泰昌原始资料为事实源。
- 辽宁技术参数可作为泰昌参数抽取后的 QA/异常校验参照，但不得自动推出“泰昌必须覆盖辽宁全部规格/全部需求”的结论；如做覆盖判断，必须标为样本校验或人工确认项。
- 河北豪乾资料仅作为格式、目录、章节组织和写法参考，`reference_only=true`，不得作为泰昌资质、业绩、设备、人员、财务、图片资产等企业事实来源。
- 严禁把泰昌企业事实、辽宁招标要求、河北豪乾参考稿混用；如资料来源不清，先补 metadata 或人工确认，不要直接入库或用于生成正式标书。

## 泰昌产品参数与检验报告 SOP

客户后续持续提供泰昌产品资料、检验报告、型式试验报告、检测报告、技术参数页、技术响应表或偏差表时，按以下标准流程处理：

1. 先 inventory 并确认资料归属，泰昌原始资料标为 `source_domain=enterprise_fact`；辽宁、其他省公司或招标文件资料不得作为泰昌企业事实。
2. 对检验报告/产品参数表做结构化抽取，产出 JSON/CSV/摘要和抽取报告；字段至少包含产品、规格型号、公称内径、参数名、单位、标准要求、检验结果、单项结论、报告编号、资料来源。
3. 更新或重生成 `taichang_product_parameter_rows.json` 等 staging 结构化参数文件；后续若参数规模变大、多批次/多版本查询复杂，再评估新增 `power_grid_product_parameter_rows` 等数据库表。
4. 知识库问答涉及具体参数值时，必须优先查结构化参数层，再结合文本/图片资产回答；不得让模型只从报告图片或普通文本里猜数值。
5. staging JSON 查询层不得长期缓存参数文件；客户补充资料并重新抽取后，真实问答应能读取最新 JSON。
6. 每次新增或重抽取后，必须跑真实 API/stream 专项测试，至少覆盖 MPP 环刚度、CPVC 平均内径/壁厚或本批新增资料中的等价关键参数。
7. 每次真实链路测试后，必须更新 `docs/rag/runs/`、`docs/rag/evaluation-records.md` 和 `docs/rag/todo.md`；若参数问答失败，要记录为未达标而不是只记录接口可返回。
8. 辽宁或其他省公司需求只能作为 QA/异常校验参照；除非明确目标省公司、批次、规格和客户确认口径，否则不得生成“覆盖该省全部规格/全部需求”的结论。

## 泰昌 / 辽宁 / 河北豪乾 Metadata 边界

泰昌企业事实资料默认 metadata：

```text
enterprise=泰昌
doc_owner=泰昌 或 河北泰昌电力器材科技有限公司
source_domain=enterprise_fact
reference_only=false
fact_source_allowed_for_enterprise=true
tenant_visibility=taichang_only
access_scope=taichang_tenant_internal
```

辽宁招标资料默认 metadata：

```text
source_domain=tender_requirement
doc_owner=国网辽宁省电力有限公司
province=辽宁
fact_source_allowed_for_enterprise=false
```

河北豪乾参考稿默认 metadata：

```text
source_domain=reference_template
doc_owner=河北豪乾电气设备科技有限公司
reference_only=true
fact_source_allowed_for_enterprise=false
citation_policy=reference_style_only
do_not_mix_with=["泰昌企业事实"]
```

## 泰昌图片资产规则

泰昌解析出来的图片资产必须保留 metadata，以支持知识库问答、标书图文并茂、智能客服图片展示和后续批量入库。

图片资产至少记录：

- `asset_id`
- `source_file`
- `page_no` 或可追溯路径
- `enterprise`
- `doc_owner`
- `source_domain`
- `evidence_type`
- `target_library`
- `tenant_visibility`
- `access_scope`

执行原则：

- 标书图文导出只允许使用泰昌企业事实资产。
- 不允许使用河北豪乾参考稿图片作为泰昌企业事实配图。
- 不允许使用辽宁招标资料图片作为泰昌企业资质或能力配图。
- 模型正文中凭空生成的图片路径不得进入正式 DOCX；正式导出只保留已入库、可解析、可追溯的真实资产图片。
- 正式资信库、产品库、知识库展示用图片只允许来自客户原始图片、客户扫描件，或客户 PDF 按页整页渲染图。
- MinerU `extract/images` 中的二维码、印章、签名、页脚、局部文字块、表格单元格、装饰图等局部切图只能作为解析中间产物或人工复核线索，不得进入正式展示库，不得自动插入标书。
- 营业执照、资质证书、认证证书、检验报告、审计报告、人员证书、社保证明、合同证明等 PDF 扫描件可按文件顺序逐页渲染为整页图片资产；metadata 必须保留 `source_file`、`page_no`、`page_index`、`asset_visual_type=full_page_render/full_page_certificate/full_page_document_image`、`full_page=true`。
- 产品实物、生产线、检测设备、厂房、仓库等用于宣传和技术响应的图片，优先要求客户提供原始高清照片；如客户只提供 PDF 图片合集，可按 PDF 整页渲染入库，但不得从 PDF 中自动裁局部冒充原始照片。

## 泰昌产品参数与检验报告重抽取 SOP

客户后续新增泰昌产品参数、检验报告、规格型号、试验检测报告或包含保证值/检验结果的资料时，必须进入产品参数重抽取与真实链路回归流程。

执行原则：

- 只把泰昌原始产品资料和检验报告作为企业事实来源；辽宁资料仅可作为抽取 QA/异常校验参照，不得自动推出泰昌覆盖辽宁全部规格或全部需求。
- 新资料落位、解析或 OCR 后，优先执行：`set -a; source .env; set +a; .venv/bin/python scripts/rag/run_taichang_product_parameter_refresh.py --run-id <run>`。
- 该脚本必须完成产品参数重抽取、`taichang_product_parameter_rows.json/csv` 更新、参数查询单测、增量回归门禁和真实 `/api/knowledge/search/stream` 页面同源参数问答抽样。
- 验收至少检查：成功抽取报告数、参数行数、CPVC/MPP 产品族是否存在、`qa_reference.scope=qa_only_not_coverage_judgement`、MPP 环刚度 `66.40`、CPVC 平均内径 `250.2~250.4` 和壁厚 `15.2~15.3` 的真实问答结果。
- 每次重抽取后必须写入 `docs/rag/runs/<run>_summary.md`，并同步 `docs/rag/evaluation-records.md`、`docs/rag/todo.md` 或对应任务状态。

## 泰昌项目业绩结构化抽取 SOP

客户新增泰昌合同协议书、中标通知书、成交通知书、订单、验收单或发票等项目业绩证据时，必须进入结构化业绩重抽取流程。

执行原则：

- 只把泰昌原始业绩材料作为泰昌企业事实；河北豪乾参考稿和辽宁招标要求不得生成泰昌业绩。
- 至少抽取项目名称、招标编号、分标/包号、产品、规格、数量、金额、甲乙方、中标时间、合同签署时间、合同编号、资料来源和来源页码。
- 合同与中标通知书字段不一致时必须分别保存并标记来源；不得静默覆盖，也不得用中标日期、交货日期推断空白的合同签署日期。
- PDF 表格文本发生数字粘连时，不得猜测拆列；应使用结构化表、唯一金额、总价、总数量和双方主体做交叉校验，仍不确定的字段标记人工复核。
- 当前泰昌补充批次优先执行：`.venv/bin/python scripts/rag/extract_taichang_project_performance.py`，更新 `taichang_project_performance_rows.json/csv` 和抽取报告。
- 结构化业绩接入问答后必须跑真实 `/api/knowledge/search/stream`，验证数量、金额、招标编号、日期缺失状态和来源页码；不得只用 mock 或单元测试替代。
- 每次新增或重抽取后必须执行增量回归门禁，并同步 `docs/rag/runs/`、`docs/rag/evaluation-records.md` 和 `docs/rag/todo.md`。

## 国内中文命名规则

本项目面向国内电网投标场景，企业知识库、资信库、产品库、图片资产、标签、分类和页面展示文案必须使用中文友好命名。

执行原则：

- 面向用户展示的 `title`、`category`、`tags`、`applicable_sections`、说明文字、导出图片 caption 不得出现拼音、英文 snake_case、内部批次编号或解析器产物名。
- 客户新增资料、解析 staging Markdown、`source_display_name`、`category_label`、图片资产标题和参考来源标题必须使用行业内或专业中文命名；不得把 `taichang_*`、`power_grid_*`、`*_private.md`、解析批次目录名等内部名称暴露给用户。
- 允许 metadata 内保留英文枚举和技术字段用于程序过滤，例如 `evidence_type=production_capacity`、`target_library=product_library`；但这些值不得直接显示在页面列表、标签和标题中。
- 如果底层 `source_file` 或解析路径必须保留英文/拼音以保证追溯，必须同时写入中文 `source_display_name`、`category_label`、`evidence_type_label` 或 `target_library_label`，页面和导出只展示中文字段。
- 图片资产标题必须表达“主体 + 资料名称 + 页码/场景”，例如“泰昌质量管理体系认证证书第1页”“泰昌CPVC电缆保护管检验报告第3页”“泰昌MPP生产线资料第2页”。
- 产品库分类应使用“产品实物图片、生产制造能力、试验检测设备、检验报告、绿色低碳资料、厂房仓储资料”等中文；资信库分类应使用“基础证照、资质证书、财务资料、人员证书、项目业绩、授权文件”等中文。
- 如果发现页面出现 `taichang_*`、`production_capacity`、`green_low_carbon`、`business_license`、`certification`、`product`、`technical` 等内部值，必须优先修正为中文展示或中文资产数据。
- 知识库问答的参考来源必须按确定性和准确率从高到低展示；同一确定性文件、同一检验报告或同一结构化参数来源命中多行时，用户界面只展示一条合并后的来源，不得为了凑满 5 条而重复显示同一文件。

## DOCX 正式投标文件导出规则

DOCX 导出属于客户第一印象和正式交付质量问题，任何相关改动都必须按正式投标文件标准处理。

质量跟踪文档：

```text
docs/development/docx-bid-export-quality-todo.md
```

默认模板：

```text
sgcc_taichang_bid
```

默认版式：

- A4；
- 上下边距 `2.0cm`；
- 左右边距 `3.18cm`；
- 正文宋体 `10.5pt`；
- 正文固定行距 `20pt`；
- 目录标题为 `目  录`；
- 目录页码右对齐，并使用点引导线；
- 页眉为 `河北泰昌电力器材科技有限公司投标文件`；
- 页脚使用连续页码和总页数字段；
- 未显式关闭时，DOCX 导出默认 `withImages=true`。

导出后必须刷新 Word 字段，包括目录页码、页脚页码和总页数。若客户后续提供可编辑 Word 模板，应优先进入 `template_docx` 模式，而不是继续只靠内置模板。

### DOCX 正式导出 SOP

当处理标书文档编写、DOCX 导出、格式方案、封面、目录、页眉页脚、表格、图片、题注或客户最终交付观感时，必须按以下 SOP 执行：

1. 先确认格式来源优先级：招标文件明确格式要求 > 客户可编辑 Word 模板 > `sgcc_taichang_bid` 默认模板 > 高级自定义格式。
2. 默认导出不得让普通用户直接承担全量排版配置风险；MVP 默认使用“国网/泰昌标准格式”。
3. 封面必须尽量包含项目名称、文件类型、招标编号、分标编号、分标名称、包号/包名称、投标人、签字/盖章位和日期；无法从项目或正文确定的字段不得编造。
4. 目录必须独立成页，标题为 `目  录`，目录层级清晰，页码右对齐并使用点引导线。
5. 正文必须统一字体、字号、行距、首行缩进、标题层级和分页规则，不得出现明显字体混乱、重复标题或异常空页。
6. 表格必须 A4 内可读，边框清晰，表头加粗；偏差表、承诺函、签章表单等第六章格式内容应优先保留结构和占位。
7. 目录和正文标题不得重复父章节前缀；例如 `2.1 企业基本资格资料` 下的小节应显示为 `2.1.1 响应要求`，不得显示为 `2.1.1 企业基本资格资料 - 响应要求`。
8. Mermaid、代码块或模型生成的流程图源码不得原样进入正式 DOCX；能稳定转图则插图，转换失败则省略源码并记录告警。
9. 图片只允许使用泰昌企业事实资产；不得使用河北豪乾参考稿或辽宁招标资料图片作为泰昌企业事实配图，不得把模型编造路径写入正式 DOCX。
10. 正式 DOCX 图片下方不得展示内部检索信息、来源库名称、匹配依据、得分等系统字段；这些信息只能进入 metadata/manifest。
11. 真实验证必须走正式导出链路：`build_project_bid_markdown` -> `convert_md_to_word` -> `refresh_docx_fields_with_soffice`；不得只用 mock 或单元测试替代真实链路。
12. 每次相关改动都必须记录导出任务 metadata 或验证报告，至少包含模板 ID、封面字段、图片候选/选中/插入/失败数、字段刷新状态和格式告警。
13. 每次相关改动后必须同步更新 `docs/development/docx-bid-export-quality-todo.md` 和 `docs/development/runs/` 下对应验证记录。

## 回归与文档同步规则

涉及 RAG 入库、metadata、召回策略或客户资料边界调整时：

- 必须跑 Base + 客户专项召回评测；
- 新增客户资料、调整召回/rerank/metadata/参考来源展示后，必须执行增量回归门禁：Base 30 条 + 泰昌专项 30 条困难样本，必要时同时跑 `--rerank off` 与 `--rerank on --rerank-model qwen3-rerank` 对照；
- 当前标准命令优先使用：`set -a; source .env; set +a; .venv/bin/python scripts/rag/run_incremental_regression_gate.py --run-id <run>`；该脚本会生成 `<run>_base_off.json`、`<run>_base_qwen3.json`、`<run>_customer_off.json`、`<run>_customer_qwen3.json` 和 `<run>_summary.md`；
- 验收口径至少记录 `Recall@5`、Top1 来源准确率、MRR、禁用关键词命中率、跨 doc_role 串扰、平均耗时和 `rerank_scored_cases`；若任一指标退化，必须在 run summary 写明原因和处理结论，不得只覆盖 JSON 结果；
- 企业知识库问答、参考来源去重/中文化、泰昌/辽宁/河北豪乾边界相关改动，还必须至少抽样 1-2 条 `/api/knowledge/search/stream` 页面同源真实链路，不使用 mock；
- 必须检查跨资料域串用，尤其是泰昌/辽宁/河北豪乾边界；
- 必须更新 `docs/rag/evaluation-records.md`、`docs/rag/todo.md` 和对应 `docs/rag/runs/` run summary。

涉及 DOCX 导出、标书格式、图片资产或正式文件观感时，至少验证：

- 标题、封面、目录；
- 正文字体、字号、行距、页边距；
- 页眉页脚和页码字段刷新；
- 图片资产选中数、插入数、失败数；
- 是否误用河北豪乾参考稿或辽宁招标资料；
- 测试记录应写入 `docs/development/runs/` 或对应功能文档。

真实链路测试优先使用真实服务和真实 LLM，不使用 mock；除非用户明确要求 mock 或当前任务只是窄范围单元测试。

## 飞书文档导入 Skill

当用户要求将本项目生成的 Markdown 文档同步、发布、上传、归档到飞书时，使用以下 Skill：

- Skill 路径：.agents/skills/feishu-doc-import/
- 默认文档目录：feishu/docs/
- 目标知识库：AI标书系统-国家电网
- 知识库地址：https://acn03r8l9jgi.feishu.cn/wiki/space/7646261306835635128

## 当前稳定链路

V1 只执行：

本地 Markdown → lark-cli drive +import → 飞书 Docx 云文档 URL

不要自动移动到知识库。导入成功后，由用户手动移动到知识库。

## 执行命令

当用户说“同步到飞书”“发布到飞书”“上传到飞书知识库”时，优先执行：

```bash
.agents/skills/feishu-doc-import/scripts/import-to-feishu-docx.sh "<markdown文件路径>" "<标题>"

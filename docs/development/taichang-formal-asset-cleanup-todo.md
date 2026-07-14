# 泰昌正式资料资产中文化与标书配图质量治理待办

> 状态日期：2026-07-14
> 适用范围：泰昌企业事实资料、企业知识库、产品库、资信库、图片资产、RAG 问答、正式 DOCX 导出、阿里云线上环境。

## 背景与目标

当前真实导出的技术标 DOCX 中已确认存在不适合正式投标场景的图片说明，例如：

- `图示：泰昌CPVC电缆保护管检验报告内径250第1页`
- `图示：泰昌MPP电缆保护管检验报告内径250第5页`
- `图示：泰昌试验设备台账原图`
- `图示：泰昌热变型、维卡软化点温度测定仪_页面_4原图`

问题本质不是单个题注字符串，而是资料资产的内部追溯名称、RAG 选图标题、DOCX 图片题注和正式导出门禁没有分层。正式投标文件中不得暴露内部文件名、拼音/英文枚举、解析批次、页码型追溯、`原图`、`页面_`、UUID、API 路径或检索字段。

本次治理目标：

1. 面向国内招投标场景，所有用户可见标题、分类、图片名称、题注、参考来源均使用中文正式表达。
2. 清理泰昌真实资料资产中不适合展示和不适合入标书正文的图片资产，尤其是 MinerU 局部切图、二维码、印章、签名、页脚、局部文字块、无意义表格单元格。
3. 保留完整追溯能力，但追溯信息只进入 metadata、manifest、审计报告，不进入正式正文。
4. 修复不影响现有企业知识库问答、RAG 召回、标书生成、图片预览和阿里云线上操作。
5. 所有验收必须走真实链路，不以 mock 代替真实 API、真实数据库、真实 DOCX 导出和真实浏览器验证。

## 状态标记

| 标记 | 含义 |
| --- | --- |
| `[x]` | 已完成并通过真实验证 |
| `[~]` | 进行中 |
| `[ ]` | 未开始 |
| `[!]` | 阻塞或需业务确认 |

## 泰昌历史标书复用专项记录

| 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- |
| [x] | 历史标书候选标签、分类与质量分级 | `scripts/rag/classify_taichang_historical_bid_candidates.py`、`docs/development/taichang-bid-v1-data/tag_dictionary.json`、分类矩阵和人工复核队列、`docs/rag/runs/run_20260713_taichang_p0_05_tag_classification_summary.md` | 896 条候选全部分类；P0-05 原始分类保持 838 条 `review_only`、58 条 `restricted`，后续 P0-06 v2 已基于客户来源授权将其中 169 条低风险资料自动接收为 `knowledge_only`；用户可见字段禁用表达命中 0 |
| [~] | P0-06 分级自动接收、异常复核与增量入库批准 | `scripts/rag/prepare_taichang_p0_06_asset_review.py`、`docs/development/taichang-bid-v1-data/p0_06_review/泰昌历史标书资产增量入库审批表.xlsx`、自动接收/异常复核/关联阻断/批准清单、`docs/rag/runs/run_20260713_taichang_p0_06_tiered_acceptance_summary.md` | 客户主动提供两份历史标书视为来源处理授权：896 条分流为低风险知识资料自动接收 169、异常复核 290（60 个证据组）、自动关联/阻断/仅参考 437；策略批准和可进入提取校验流程均为 169，人工批准为 0。P1-01 已进一步以真实库重去重和质量校验，实际新增 133 条 `knowledge_only`，36 条因已有证据、视觉重复/疑似重复或低质量未入库；剩余 290 条异常项继续人工复核 |
| [x] | P1-01 历史标书低风险资产实际提取、去重与增量入库 | `scripts/rag/ingest_taichang_historical_bid_assets.py`、`scripts/rag/extract_taichang_historical_bid_tables.py`、`docs/development/taichang-bid-v1-data/p1_01_ingestion/`、`docs/rag/runs/run_20260713_taichang_p1_01_historical_bid_ingestion_summary.md` | 169 个媒体全部提取；133 个真实写库并有 embedding，5 个同证据、2 个视觉重复、24 个视觉疑似、5 个低质量未入库；第二次执行新增 0；全部排除正式标书和参数事实层；技术表 20 行单位保真，Base+泰昌最终门禁、真实 stream、后端 413 项测试通过 |
| [x] | P1-02 文件级证据包 | `scripts/rag/build_taichang_evidence_bundles.py`、`docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/`、`docs/rag/runs/run_20260713_taichang_p1_02_evidence_bundles_summary.md` | 基于真实 PostgreSQL 599 个现有资产重建 16 个业务证据包、149 页，页序完整、缺页 0、重页 0；21 个重复 PDF/关键页图仅作 rendition；过期证书、校准有效期、审计年度和资格预审原件缺口均有门禁；P0-06 自动接收但尚未提取/入库的 169 条候选和跨资料域来源均未进入；专项 30 项、后端全量 400 项及 2 个子测试通过 |
| [x] | P1-03 结构化参数和业务台账 | `scripts/rag/build_taichang_business_ledgers.py`、`backend/rag/business_ledgers.py`、`docs/development/taichang-bid-v1-data/p1_03_business_ledgers/`、`docs/rag/runs/run_20260714_taichang_p1_03_business_ledgers_summary.md` | 生成 84 行统一台账并复用 36 行产品参数、2 行项目业绩证据和 16 个证据包；版本库只保存 17 行安全投影，67 行人员明细仅保留在本地受限 staging；过期证书阻断、缺原件报告不生成参数；真实 stream 7/7、Base+泰昌门禁、后端全量 423 项及 2 个子测试通过；数据库写入、资产提升和 DOCX 选图变更均为 0 |

## P0：正式投标文件阻断项

| 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- |
| [x] | P0-1 全量盘点泰昌真实资料资产 | `docs/development/runs/run_20260627_taichang_formal_asset_audit*.md/json` | 本地真实库完成多轮扫描；最终 `run_20260627_taichang_formal_asset_audit_visible_and_rag_zero` 中真实图片资产 599、知识文档 77、文档分块 6347 的正式可见/RAG 可见问题均为 0。历史 staging payload 仍有 539 条中间产物问题，已按“解析中间产物”记录，不作为正式展示/RAG/DOCX 来源 |
| [x] | P0-2 建立正式展示字段与命名规则 | `backend/services/formal_asset_naming.py` | 已区分正式标题、正式题注和 `caption_policy`；追溯信息保留在 metadata/manifest，不直接进入用户可见标题、问答来源和正式 DOCX |
| [x] | P0-3 修复 RAG/标书选图 caption 生成 | `backend/api/routes.py`、`tests/test_rag_asset_scoring.py` | `_asset_caption()` 已改为正式题注策略；检验报告/证书/营业执照/合同/中标通知书等整页证据默认不再生成“在某报告第几页”式正文题注 |
| [x] | P0-4 修复 DOCX 题注兜底清洗 | `backend/export/md_to_word.py`、`tests/test_docx_export.py` | DOCX 层对历史旧式题注、正文图片占位和 `原图/页面_` 追溯痕迹做兜底清洗；已修正“试验设备台账原图”误归类为身份证明文件的问题 |
| [x] | P0-5 新增正式导出门禁规则 | `backend/services/formal_bid_check.py`、`rules/power_grid/formal_bid_check_rules.v1.json` | 已新增 `D-007` 正式图片题注阻断规则，覆盖 `图示：`、`原图`、`页面_`、UUID、API 路径、内部枚举和 `检验报告.*第\\d+页` 等正式投标禁用表达 |
| [x] | P0-6 泰昌资产中文正式标题批量回填 | `scripts/rag/repair_taichang_formal_asset_display.py`、执行报告 | 已批量回填真实库图片资产正式标题、中文展示名、正式题注策略和正文可用策略；最终真实图片资产正式可见问题数为 0 |
| [x] | P0-7 清理不适合入标书正文的图片资产 | `scripts/rag/repair_taichang_rag_source_display.py`、执行报告 | 已将 mock/test、MinerU 局部切图、资产索引中间 chunk、解析路径类 chunk 标为 `exclude_from_rag=true` / `rag_visibility=internal_only` / `allowed_for_bid=false` 或等价隔离策略，不参与正式问答和标书选图 |
| [~] | P0-8 重新生成泰昌正式图片资产 | 本轮以真实库修复和隔离为主 | 未重新批量渲染全部原件；现有正式整页/原图资产继续保留并完成正式展示治理。历史 staging payload 仍保留解析中间产物问题，后续新增资料应按 SOP 重新生成整页正式资产 |
| [x] | P0-9 真实导出技术标/商务标复验 | `docs/development/runs/run_20260627_formal_docx_asset_cleanup_v2/` | 已走 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`；技术标选图 16、商务标选图 5，字段刷新均 `refreshed`，DOCX XML 审计 `forbidden_hits=[]`、`caption_page_hits=[]` |
| [x] | P0-10 阿里云线上同步与复验 | `docs/development/runs/run_20260627_aliyun_browser_full_regression.md`、`export_tasks.json`、线上执行报告 | 阿里云已执行正式资产修复和来源显示修复；修复后审计真实图片资产 596、知识文档 77、文档分块 6347 的正式可见/RAG 可见问题均为 0。Chrome 真实回归覆盖企业知识库、产品库、资信库、知识库助手、6 类 stream 问答、技术标/商务标 DOCX 导出和下载文件 XML 审计，用户可见禁用字段命中 0 |

## P1：不影响现有功能的回归收口

| 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- |
| [x] | P1-1 企业知识库问答回归 | `docs/development/runs/run_20260627_aliyun_browser_full_regression.md`、本地真实 stream 抽样记录 | 本地和阿里云均已抽样真实 `/api/knowledge/search/stream`；CPVC 检验报告参数、MPP 检验报告、生产制造能力、试验检测设备、资质证书、绿色低碳资料 6 类问答 HTTP 200，禁用字段命中 0 |
| [x] | P1-2 Base + 泰昌专项增量门禁 | `docs/rag/runs/run_20260627_taichang_formal_asset_cleanup_gate_v2_summary.md`、`tests/rag/customer_liaoning_taichang_testset.jsonl` | 已按正式投标资料治理口径更新泰昌专项评测集：不再要求召回 `asset_path/bbox/parsed_outputs` 等内部字段，企业事实用例显式限定 `doc_role=enterprise_evidence`，河北豪乾参考稿只允许 `reference_only=true`。标准门禁 PASS：Base qwen3 Recall@5 96.7%、Top1 100%、串扰 0；泰昌专项 qwen3 Recall@5 100%、Top1 100%、禁用关键词 0、串扰 0 |
| [x] | P1-3 图片资产检索与选图回归 | `tests/test_rag_asset_scoring.py`、`tests/test_docx_export.py` | 定向测试 12 passed；真实技术标/商务标 DOCX 中禁用题注命中为 0 |
| [x] | P1-4 产品库/资信库页面展示回归 | `product_page.png`、`qualification_page.png`、`docs/development/runs/run_20260627_aliyun_browser_full_regression.md` | 阿里云 Chrome 真实页面复验通过；企业产品库、企业资信库用户可见页面未出现内部枚举、解析路径、英文/拼音资产名或旧题注字段 |
| [x] | P1-5 上传入口新资产规则回归 | `backend/api/assets.py`、`backend/rag/display_names.py`、`tests/test_knowledge_asset_upload_payload.py`、`docs/rag/runs/run_20260627_upload_entry_formal_asset_regression.md` | 已走真实登录、真实 `/api/knowledge/assets/upload`、列表/详情和 `/api/knowledge/search/stream`；新上传测试资产返回 `泰昌MPP生产线资料`，用户侧禁用字段命中 0，RAG 可召回，测试资产已删除；定向测试 40 passed，标准增量门禁 PASS |
| [x] | P1-6 导出任务 metadata 扩充 | `run_20260627_formal_docx_asset_cleanup_v2/summary.json`、`run_20260627_aliyun_browser_full_regression/export_tasks.json` | 本地和阿里云异步导出任务均已记录模板链路、题注清洗、候选/插入/失败、字段刷新和正式门禁；下载后的 DOCX XML 禁用表达命中 0。metadata 中保留追溯 source 属于后台审计字段，不进入正式正文 |

## P2：长期可维护能力

| 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- |
| [x] | P2-1 建立资产正式化 SOP | `.agents/skills/formal-bid-asset-ingestion/`、`AGENTS.md` | 已抽取为项目 Skill；客户新增图片、PDF、Word、Excel、CSV、产品/资信/企业知识库资料时，必须先 inventory、确认来源域、生成正式中文标题/分类/标签/题注策略和追溯 metadata，不允许直接用原始文件名入库展示 |
| [x] | P2-2 建立图片资产质量分级 | `.agents/skills/formal-bid-asset-ingestion/references/asset-policy.md` | 已定义 `formal_bid_ready`、`knowledge_only`、`review_only`、`restricted`；正式标书自动选图只允许 `formal_bid_ready`，MinerU 局部切图、二维码、印章、签名、页脚、局部表格单元格默认仅作 `review_only` |
| [ ] | P2-3 建立云端修复发布 runbook | `docs/deployment/` 或 run 记录 | 本地修复脚本、阿里云执行命令、回滚方式、验证命令固定化，避免线上线下数据不一致 |
| [x] | P2-4 产品库/资信库上传表单资料规范产品化 | `frontend/src/utils/assetUploadGuidance.ts`、产品库/资信库页面、后端质量门禁、`docs/development/runs/run_20260627_asset_upload_form_productization.md` | 已将正式投标资产 SOP 产品化到用户上传表单：中文资料类型、推荐格式、文件质量预检、Excel/CSV 支持、质量等级入库、DOCX 自动配图门禁、真实 API 上传和 Chrome 页面回归均通过 |
| [ ] | P2-5 客户补资料清单模板 | 飞书/Markdown 清单 | 明确要求客户提供原始高清产品照片、生产线照片、检测设备照片、完整 PDF 扫描件，不鼓励提供碎片截图 |

## 正式命名规则

### 禁止进入用户可见字段

- 英文或拼音内部名：`taichang_*`、`power_grid_*`、`production_capacity`、`testing_capacity`、`green_low_carbon`、`business_license`、`certification`
- 解析或文件追溯痕迹：`原图`、`页面_5`、`第1页` 作为图题后缀、UUID、哈希、`asset_id`
- 系统路径和接口：`/api/bidding/knowledge/assets`、`parsed_outputs`、`rag_seed`、`source_display_name`
- MinerU 中间产物：局部二维码、印章、签名、页脚、局部文字块、表格单元格截图

### 推荐正式表达

| 场景 | 正式表达 |
| --- | --- |
| 检验报告整页扫描件 | `CPVC电缆保护管型式检验报告` |
| 认证证书 | `质量管理体系认证证书` |
| 营业执照 | `营业执照副本` |
| 中标通知书 | `同类项目中标通知书` |
| 合同协议书 | `同类项目合同协议书` |
| 生产线照片 | `MPP电缆保护管生产线实景` |
| 检测设备照片 | `试验检测设备实景` |
| 绿色低碳资料 | `绿色发展规划资料`、`产品碳足迹报告` |

## 真实验收命令基线

```bash
set -a; source .env; set +a; .venv/bin/python scripts/rag/run_incremental_regression_gate.py --run-id <run>
```

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_formal_bid_check.py tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q
```

真实 DOCX 链路必须覆盖：

```text
build_project_bid_markdown(volume_type=technical/business, with_images=true)
-> convert_md_to_word(return_report=true)
-> refresh_docx_fields_with_soffice
-> DOCX XML audit
```

真实 API/页面链路必须覆盖：

```text
/api/knowledge/search/stream
/api/bidding/interpretations/<project_id>/download-docx
标书编制页真实浏览器下载技术标、商务标
```

## 执行记录

### 2026-06-27 本地正式资产治理收口

- 资产审计：最终 `run_20260627_taichang_formal_asset_audit_visible_and_rag_zero` 扫描真实图片资产 599、知识文档 77、文档分块 6347，正式可见/RAG 可见问题均为 0。
- 数据修复：执行 `repair_taichang_formal_asset_display.py` 与 `repair_taichang_rag_source_display.py` 多轮修复，完成正式标题、中文展示字段、题注策略、正文可用策略和内部 chunk 隔离。
- 代码修复：新增 `formal_asset_naming.py`，并接入 RAG 选图、DOCX 兜底清洗、知识问答公开字段脱敏和正式导出门禁。
- 真实 API：本地 `/api/knowledge/search/stream` 抽样未再暴露 `图示：`、`原图`、`页面_`、解析路径、内部枚举、向量字段或 API 资产路径。
- 真实 DOCX：`run_20260627_formal_docx_asset_cleanup_v2` 中技术标/商务标均完成字段刷新，DOCX XML 审计 `forbidden_hits=[]`、`caption_page_hits=[]`。技术标仍有 59 处待补充/待确认、商务标仍有 92 处待补充/待确认，属于客户确认字段和正文完整性问题，不属于本轮图片题注问题。
- 回归门禁：Base 30 未退化；泰昌专项门禁失败，需更新旧测试集，避免继续要求召回已被正式隔离的资产索引中间 chunk。
- 未完成项：阿里云线上修复脚本执行、线上真实浏览器导出复验、产品库/资信库页面截图复验、新上传入口样本复验仍未完成。

### 2026-06-27 本地服务真实回归确认

- 总记录：`docs/development/runs/run_20260627_local_formal_asset_regression.md`。
- 服务状态：本地后端 `3012`、前端 `5173`、Celery worker 均已启动并参与验证。
- 资产审计：真实图片资产 599、知识文档 77、文档分块 6347 的正式可见/RAG 可见问题均为 0。
- 真实 stream：CPVC 检验报告参数、MPP 检验报告、生产制造能力、试验检测设备、资质证书、绿色低碳资料 6 类真实 API 均 HTTP 200，禁用字段命中 0。
- 浏览器页面：Chrome 打开企业知识库列表和知识库助手 CPVC 参数问答，页面渲染后禁用字段命中 0；截图见 `run_20260627_local_browser_knowledge_page.png` 和 `run_20260627_local_browser_knowledge_assistant_cpvc.png`。
- DOCX：技术标/商务标真实导出字段刷新均 `refreshed`，禁用表达和页码型题注命中均为 0。
- 自动化测试：题注/选图定向测试 `12 passed, 1 warning`。
- 增量门禁：Base 未退化；泰昌专项仍因旧评测集期待内部资产索引 chunk 被召回而失败，作为 P1 评测集更新任务处理。
- 本地结论：本地正式资产治理确认完成，可以进入阿里云测试环境发布与线上复验。

### 2026-06-27 上传入口新资产规则回归

- 总记录：`docs/rag/runs/run_20260627_upload_entry_formal_asset_regression.md`。
- 代码收口：`backend/api/assets.py` 在上传/更新资产入库前生成正式中文标题、分类、标签、说明、`source_display_name` 和 `formal_caption`；`searchable_text` 不再拼入 `product_image/technical/production_capacity` 等内部枚举。
- 用户侧清洗：`backend/rag/display_names.py` 补充证据类型中文标签，并将 SSE/问答返回的 `product_image/qualification_image` 映射为“产品图片/资信图片”。
- 真实 API：本地登录后上传测试图 `泰昌MPP生产线_页面_9原图.png`，返回标题 `泰昌MPP生产线资料`、分类 `生产制造能力`、标签 `泰昌/生产制造能力`，列表/详情禁用字段命中 0。
- 真实 stream：`泰昌MPP生产线资料可以作为技术标生产制造能力配图吗？` 召回 4 条资料、4 个图片资产、4 张图片，新上传资产被召回；SSE 和回答正文禁用字段命中 0。
- 清理：测试资产 `b522d9fb-5011-43e7-840f-f9b85710b14e` 已从数据库删除，避免 1x1 回归样张进入正式产品库或 RAG。
- 回归：`tests/test_knowledge_asset_upload_payload.py tests/test_rag_display_names.py tests/test_rag_retrieval.py` 为 40 passed；`run_20260627_upload_entry_formal_asset_gate` 标准增量门禁 PASS。

### 2026-06-27 正式投标资产入库 SOP Skill 化

- Skill：`.agents/skills/formal-bid-asset-ingestion/`。
- 接入规则：已在 `AGENTS.md` 增加“正式投标资产入库与上传资料清洗 Skill”，后续处理客户上传图片、PDF、Word、Excel、CSV、产品库/资信库/企业知识库资料、RAG 图片资产或 DOCX 配图时必须先使用。
- 核心流程：客户资料先 inventory，再做来源域、证据类型、目标库、质量等级、正文可用性和正式中文展示字段判断；内部枚举、解析路径、`页面_`、`原图`、UUID 和 API 路径只允许留在 metadata 或审计记录中。
- 质量分级：`formal_bid_ready`、`knowledge_only`、`review_only`、`restricted` 已固化在 `references/asset-policy.md`。
- 验证门禁：真实上传、列表/详情、`/api/knowledge/search/stream`、Base+泰昌专项增量门禁、DOCX 导出和文档同步要求已固化在 `references/validation-gates.md`。
- 校验：`.venv/bin/python /Users/chris/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/formal-bid-asset-ingestion` 通过。

### 2026-06-27 产品库/资信库上传表单资料规范产品化

- 总记录：`docs/development/runs/run_20260627_asset_upload_form_productization.md`。
- 前端：产品库和资信库上传弹窗新增正式中文资料类型、推荐格式提示和文件质量预检；`.xls/.xlsx/.csv` 已进入上传选择范围。
- 后端：上传入库统一写入 `quality_tier/quality_tier_label/quality_notes/user_requested_bid_usage`；表格默认 `knowledge_only`，小图、二维码、印章、签名、局部截图默认 `review_only`；DOCX 自动选图只允许 `formal_bid_ready`。
- 真实 API：上传 `泰昌上传表单回归产品参数表.csv` 返回 `quality_tier=knowledge_only`、`allowed_for_bid=false`，响应不再暴露 `embedding`，内部 `searchable_text` 已压平；测试资产已删除。
- Chrome 页面：产品库上传 CSV 出现“资料预检：仅用于知识库”；资信库上传 1x1 局部截图出现“资料预检：需人工复核”；截图见 `docs/development/runs/screenshots/run_20260627_asset_upload_product_form.png` 和 `docs/development/runs/screenshots/run_20260627_asset_upload_qualification_form.png`。
- 回归：上传 payload 测试 `5 passed, 2 subtests passed`；DOCX/RAG/display 定向回归 `95 passed, 1 warning`；前端 build PASS；`run_20260627_asset_upload_form_productization_gate` 标准增量门禁 PASS。

### 2026-06-27 阿里云线上真实浏览器全流程回归确认

- 总记录：`docs/development/runs/run_20260627_aliyun_browser_full_regression.md`。
- 线上服务：`http://8.160.187.226`，Chrome 真实登录 `admin` 成功；`/api/health` 返回 `status=ok`。
- 线上修复：执行 `repair_taichang_formal_asset_display.py --execute`，扫描图片资产 596，变更 97，重写标题 51，抑制旧题注 97；执行 `repair_taichang_rag_source_display.py --execute`，扫描知识文档 77、分块 6347，更新文档 2、分块 10。
- 线上审计：`audit_taichang_formal_assets.py` 显示真实图片资产、知识文档、文档分块问题数均为 0；历史 staging payload 仍为解析中间产物问题，不进入正式展示/RAG/DOCX。
- 页面回归：企业知识库、企业产品库、企业资信库、知识库助手 CPVC 参数问答均未出现 `图示：`、`原图`、`页面_`、内部枚举、解析路径或 API 资产路径。
- 真实 stream：CPVC 检验报告参数、MPP 检验报告、生产制造能力、试验检测设备、资质证书、绿色低碳资料 6 类同源流式问答均 HTTP 200，禁用字段命中 0。
- 真实 DOCX：阿里云技术标、商务标均通过 `download-docx -> Celery -> build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`；技术标插图 24、商务标插图 24，失败 0，字段刷新均 `refreshed`。
- 文件级审计：下载后的 `aliyun_technical_export.docx` 和 `aliyun_business_export.docx` 解包扫描 `word/*.xml`，禁用表达命中 0。
- 正式门禁：当前新疆 10kV 导线项目仍有 12 个正式阻断项，导出为 `draft`，其中 `T-000` 明确提示泰昌 CPVC/MPP 资料与导线包不匹配；该阻断符合真实投标场景，不能绕过。
- 阿里云结论：测试环境正式资产治理主链路通过，可以关闭本轮 P0/P1 页面与 DOCX 线上验收；正式投标前仍需客户补齐确认字段并确认目标产品适配。

### 2026-06-27 泰昌专项评测集与豪乾参考稿 metadata 收口

- 总记录：`docs/rag/runs/run_20260627_taichang_formal_asset_cleanup_gate_v2_summary.md`。
- 触发原因：旧泰昌专项评测集仍期待历史资产索引 chunk、`asset_path/bbox/display_contexts` 等解析内部字段；这些内容已按正式投标要求隔离，不应再作为召回成功条件。
- 数据修复：执行 `scripts/rag/repair_haoqian_reference_metadata.py --execute`，修复河北豪乾参考文档 2 个、chunk 70 个；统一为 `source_domain=reference_template`、`reference_only=true`、`fact_source_allowed_for_enterprise=false`、`citation_policy=reference_style_only`。
- 评测集修复：更新 `tests/rag/customer_liaoning_taichang_testset.jsonl`，企业事实用例显式加 `doc_role=enterprise_evidence`，正式资产用例改为检查中文正式资料口径和禁用内部字段，豪乾参考用例改为检查参考稿边界。
- 标准门禁：`run_20260627_taichang_formal_asset_cleanup_gate_v2` PASS。Base qwen3 Recall@5 96.7%、Top1 100%、跨 doc_role 串扰 0；泰昌专项 qwen3 Recall@5 100%、Top1 100%、禁用关键词 0、跨 doc_role 串扰 0。
- 结论：本轮正式资料资产治理的长期 RAG 回归门禁已闭环；剩余 P1-5 新上传入口样本复验和 P2 SOP 固化可作为后续增强项。

## 当前执行顺序

1. P0-1 全量盘点和问题资产分类。
2. P0-2/P0-3/P0-4/P0-5 建立正式字段、生成规则和门禁。
3. P0-6/P0-7/P0-8 批量回填和资产隔离/重建。
4. P1-1/P1-2/P1-3 确认 RAG 问答、召回、选图不退化。
5. P0-9/P0-10 本地和阿里云正式导出复验。
6. P2 SOP 固化，防止新增资料再次引入同类问题。

### 2026-07-13 泰昌历史标书媒体候选隔离记录

- P0-03 已只读解析《技术补充文件》《商务补充文件》，识别 691 个媒体文件、698 次媒体出现。
- 所有 Word 内嵌媒体仅记录关系、页序、尺寸和哈希，统一为 `review_only + allowed_for_bid=false`；没有解包到产品库/资信库，也没有自动进入 RAG 或正式 DOCX。
- 图片内部证书有效期、签章、个人信息、报告参数和表格数值未做 OCR，不作为事实候选；后续 P0-04 必须与客户原始文件和当前 599 个数据库资产进行四层去重后，才能决定是否建立证据包映射。
- 运行记录：`docs/rag/runs/run_20260713_taichang_p0_03_historical_bid_inventory_summary.md`。

### 2026-07-13 泰昌历史标书四层去重安全审计

- 已对 896 条历史标书候选执行文件、视觉、文本和业务主键四层只读比对；结果为精确重复 270、视觉疑似 142、文本疑似 5、同证据不同载体 2、事实冲突 15、新候选 462。
- staging 的 `content_sha256` 是记录指纹，不等于图片文件哈希；本轮已从真实 `local_path` 重新计算 543 个视觉文件，避免错误精确匹配。
- 所有视觉疑似项均为 `manual_review_required=true`，空白/近空白页和小图/印章风险图不得基于感知哈希自动合并。
- 所有候选继续保持 `review_only + allowed_for_bid=false + promotion_eligible=false`；未写数据库、未改 metadata、未执行自动合并或正式入库。
- 两个既有检验报告编号已归入同一证据包候选；历史项目号、固化 ID 按事实冲突阻断；缺原始证据的报告仍不得提升。
- 定向与 P0-02/P0-03 回归共 18 项通过，重复执行结果一致，冻结输入哈希未变化。
- 产物：`docs/development/taichang-bid-v1-data/asset_dedup_matrix.json/csv`；运行记录：`docs/rag/runs/run_20260713_taichang_p0_04_asset_dedup_summary.md`。

### 2026-07-14 泰昌 P1-04 章节—事实—证据映射收口

- 已建立 19 个动态语义章节映射，按技术标/商务标分表输出，不绑定历史章节号。
- 只有 5 个“已有资料”章节可进入自动引用候选；10 个“部分可用”、3 个“缺原件”和 1 个“人工确认”章节均保留正式投标门禁。
- 15 个唯一证据包只按 ID 跨章节复用，不复制资产；历史 Word 知识资产继续保持 `knowledge_only`，不提升为正式配图或正式附件。
- N-HAP/UPVC 缺原件、职业健康安全证书过期、资格预审无独立原件、2024 审计编号待复核、授权委托与签章人工确认等边界均已固化。
- 人员受限明细纳入映射 0；辽宁招标资料和河北豪乾参考稿进入泰昌事实引用 0。
- 专项 `29 passed`、后端全量 `432 passed、2 subtests passed`；本轮数据库写入、metadata 改写、资产复制/提升和 DOCX 选图变更均为 0。

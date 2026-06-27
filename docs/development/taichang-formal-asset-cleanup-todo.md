# 泰昌正式资料资产中文化与标书配图质量治理待办

> 状态日期：2026-06-27
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
| [!] | P0-10 阿里云线上同步与复验 | 待云端发布/执行记录 | 本轮完成本地真实数据库、真实 API 和真实 DOCX 链路；尚未在阿里云线上执行同等修复脚本和浏览器导出复验，不能关闭线上验收 |

## P1：不影响现有功能的回归收口

| 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- |
| [~] | P1-1 企业知识库问答回归 | 本地真实 stream 抽样记录 | 已抽样真实 `/api/knowledge/search/stream`，返回内容未暴露 `图示：/原图/页面_/asset_path/parsed_outputs/source_domain/target_library/specs/file_name` 等内部字段；尚未完成 6 类全量专项 stream 抽样 |
| [!] | P1-2 Base + 泰昌专项增量门禁 | `docs/rag/runs/run_20260627_taichang_formal_asset_cleanup_gate_summary.md` | 已执行门禁：Base off/qwen3 均 96.7%/100%/0 串扰；泰昌专项失败。失败原因是旧专项用例仍期待历史资产索引/解析中间 chunk 被召回，而本轮已按正式投标要求主动隔离这些内部 chunk；需更新专项评测集后复跑 |
| [x] | P1-3 图片资产检索与选图回归 | `tests/test_rag_asset_scoring.py`、`tests/test_docx_export.py` | 定向测试 12 passed；真实技术标/商务标 DOCX 中禁用题注命中为 0 |
| [~] | P1-4 产品库/资信库页面展示回归 | 待前端浏览器复验 | API/RAG 输出已做公开字段脱敏和中文化；本轮未执行产品库/资信库页面真实浏览器截图复验 |
| [~] | P1-5 上传入口新资产规则回归 | 待新增上传样本复验 | 生成/清洗 helper 已覆盖新资产正式标题策略；本轮未重新走上传入口新增样本 |
| [~] | P1-6 导出任务 metadata 扩充 | `run_20260627_formal_docx_asset_cleanup_v2/summary.json` | 本地 run 已记录模板链路、题注清洗、候选/选中、字段刷新和阻断词扫描；异步导出任务 metadata 与阿里云同步状态仍需补齐 |

## P2：长期可维护能力

| 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- |
| [ ] | P2-1 建立资产正式化 SOP | `docs/rag/customer-template-ingestion-sop.md` 更新 | 客户新增资料后，必须先 inventory，再生成正式标题、正式 caption、正文可用策略、追溯 metadata，不允许直接用文件名入库展示 |
| [ ] | P2-2 建立图片资产质量分级 | 资产质量枚举与文档 | `formal_bid_ready`、`knowledge_only`、`review_only`、`restricted` 等分级清晰；选图只用 `formal_bid_ready` |
| [ ] | P2-3 建立云端修复发布 runbook | `docs/deployment/` 或 run 记录 | 本地修复脚本、阿里云执行命令、回滚方式、验证命令固定化，避免线上线下数据不一致 |
| [ ] | P2-4 客户补资料模板 | 飞书/Markdown 清单 | 明确要求客户提供原始高清产品照片、生产线照片、检测设备照片、完整 PDF 扫描件，不鼓励提供碎片截图 |

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

## 当前执行顺序

1. P0-1 全量盘点和问题资产分类。
2. P0-2/P0-3/P0-4/P0-5 建立正式字段、生成规则和门禁。
3. P0-6/P0-7/P0-8 批量回填和资产隔离/重建。
4. P1-1/P1-2/P1-3 确认 RAG 问答、召回、选图不退化。
5. P0-9/P0-10 本地和阿里云正式导出复验。
6. P2 SOP 固化，防止新增资料再次引入同类问题。

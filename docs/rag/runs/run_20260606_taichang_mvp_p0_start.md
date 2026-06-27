# 泰昌 MVP 试点资料 P0 启动记录

> 日期：2026-06-06
> 批次 ID：`customer_liaoning_taichang_20260606_p0`
> 范围：泰昌 MVP 试点企业资料、辽宁电缆保护管招标资料、河北豪乾中标参考稿。

## 目标

本轮目标不是直接全量入库，而是先补齐 P0 级边界与解析前置条件：

1. 完成 RAG P0 中旧部署/历史文档的迁移参考标注，避免误用旧脚本。
2. 为泰昌 MVP 批次建立强隔离 manifest，防止“泰昌事实”和“河北豪乾参考稿”混用。
3. 验证 MinerU/OCR 对泰昌扫描件的可用性。
4. 为 MinerU 解析出的图片资源生成后续知识库、产品库、资信库批量入库所需 metadata。

## P0 基座状态

`docs/rag/todo.md` 中 P0 已全部完成。最后一项“旧部署/历史文档标注迁移参考”已在以下文档补充边界：

- `docs/deployment/supabase-setup.md`
- `docs/deployment/supabase-to-postgres-migration.md`
- `docs/deployment/local-postgres-docker.md`
- `docs/deployment/gitee-ai-bid-runbook.md`

新环境入口统一指向：

- PostgreSQL 正式迁移链：`migrations/postgres/`
- 电网 RAG v2 入库：`scripts/rag/ingest_power_grid_v2.py`
- 客户批次入库与评测：`scripts/rag/ingest_customer_corpus.py`、`scripts/rag/eval_recall.py`

## 批次 Manifest

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/manifest.json`

摘要：

| 指标 | 数量 |
| --- | ---: |
| 文件总数 | 230 |
| 泰昌企业事实文件 | 44 |
| 辽宁招标要求文件 | 184 |
| 河北豪乾参考稿文件 | 2 |
| 敏感私有文件 | 17 |
| MinerU/OCR 候选 | 45 |
| 图片抽取候选 | 145 |

强边界：

| source_domain | doc_owner | 允许用途 | 禁止用途 |
| --- | --- | --- | --- |
| `enterprise_fact` | 泰昌 | 泰昌企业资质、产品、生产、检测、绿色低碳等事实 | 河北豪乾事实 |
| `tender_requirement` | 国网辽宁省电力有限公司 | 招标要求、货物清单、合同、技术规范 | 任一投标人企业事实 |
| `reference_template` | 河北豪乾电气设备科技有限公司 | 标书目录、格式、章节组织、写法参考 | 泰昌企业事实或泰昌业绩 |

## MinerU/OCR Smoke

样本：

- `rag_seed/power_grid_resources/05_enterprise_documents/01_泰昌MVP试点企业资料/extracted/泰昌资料/营业执照副本.pdf`

原因：

- 单页；
- 属于泰昌企业事实；
- 原生 PDF 文本抽取为空，能验证扫描件 OCR 价值。

结果：

| 项 | 结果 |
| --- | --- |
| MinerU token | 已配置 |
| DashScope / DeepSeek key | 已配置 |
| MinerU 状态 | `mineru_done` |
| 页数 | 1 |
| Markdown | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/extract/full.md` |
| Content list | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/extract/bb1e2413-db49-49b8-b777-7ac42e77d30a_content_list.json` |
| Layout / model | 已产出 `layout.json`、`*_model.json` |
| 图片资产 | 1 个 |
| 下载方式 | requests 失败后使用 curl fallback，zip 完整 |

OCR 抽取到的关键字段包括：

- 统一社会信用代码；
- 企业名称：河北泰昌电力器材科技有限公司；
- 法定代表人；
- 经营范围，包含电缆保护管研发、制造、加工；
- 注册资本；
- 成立日期、营业期限、住所。

## 图片资产 Metadata

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/asset_manifest.json`

当前样本产出 1 个图片资产，metadata 已包含：

- `source_domain=enterprise_fact`
- `doc_owner=泰昌`
- `enterprise=泰昌`
- `evidence_type=business_license`
- `target_library=qualification_library`
- `privacy_level=taichang_internal_private`
- `reference_only=false`
- `fact_source_allowed_for_enterprise=true`
- `page_idx/page_no/bbox`
- `asset_sha256`
- `usage_policy=enterprise_fact_evidence`
- `do_not_mix_with=河北豪乾参考稿`

这个结构可扩展到后续资信库、产品库、知识库批量入库。

## 后续 P0 队列

1. 全量泰昌扫描 PDF MinerU/OCR：按 `manifest.json` 中 `parse_plan` 执行，敏感件标 `taichang_internal_private`，先产物化，不直接入库。
2. 辽宁货物清单结构化：兼容 `dimension ref=A1` 但 worksheet XML 实际多行多列的异常，输出 87 条去重需求行。
3. 河北豪乾参考稿格式抽取：只抽封面、目录、章节组织、页眉页脚、表格和签章位，metadata 固定 `reference_only=true`。
4. 泰昌事实与参考稿隔离评测：新增专项测试集，验证问泰昌事实不召回河北豪乾事实，问格式参考可召回河北豪乾但不改写主体。
5. 全量 OCR 后生成 parse quality report，再决定哪些资料进入知识库、产品库、资信库。

## 2026-06-06 后续推进

### 辽宁货物清单结构化

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/goods_tables/goods_rows.json`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/goods_tables/goods_summary.json`

结果：

- 解析文件数：6 个 `.xlsx`
- 去重需求行：87 条
- 解析器：`xlsx_worksheet_xml`
- 说明：本批 Excel 的 workbook dimension 标记为 `A1`，普通 openpyxl 读取会误判为空表；本轮直接解析 worksheet XML，保留分标编号、包名称、需求单位、物资名称、物资描述、数量、交货日期、技术规范编码等字段。

### 河北豪乾参考稿基础模板数据

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/reference_templates/haoqian_reference_templates.json`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/reference_templates/haoqian_reference_templates.md`

抽取范围：

- 封面字段；
- 招标编号、分标名称、包号；
- 目录结构；
- 章节粒度；
- 可作为格式/目录/写法参考的材料清单。

硬边界：

- `source_domain=reference_template`
- `doc_owner=河北豪乾电气设备科技有限公司`
- `reference_only=true`
- `fact_source_allowed_for_enterprise=false`

禁止用途：

- 泰昌资质事实；
- 泰昌业绩事实；
- 泰昌生产/检测/财务事实；
- 自动填充泰昌企业能力证明。

### 泰昌 OCR 优先级计划

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/ocr_plan/taichang_ocr_plan.json`

摘要：

| evidence_type | 文件数 | 页数 | 空文本/低文本 |
| --- | ---: | ---: | ---: |
| `finance` | 3 | 67 | 3 |
| `certification` | 6 | 28 | 3 |
| `inspection_report` | 2 | 10 | 0 |
| `production_capacity` | 15 | 47 | 14 |
| `testing_capacity` | 12 | 55 | 12 |
| `green_low_carbon` | 3 | 91 | 0 |
| `business_license` | 1 | 1 | 1 |

### 泰昌首批 MinerU OCR

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_batch/`

已完成文件：

| 文件 | evidence_type | 状态 | 图片资产 |
| --- | --- | --- | ---: |
| `营业执照副本.pdf` | `business_license` | `mineru_done` | 1 |
| `2.环境管理体系认证证书.pdf` | `certification` | `mineru_done` | 10 |
| `1.质量管理体系认证证书.pdf` | `certification` | `mineru_done` | 9 |
| `3.职业健康安全管理体系认证证书.pdf` | `certification` | `mineru_done` | 7 |
| `生产设备台账.pdf` | `production_capacity` | `mineru_done` | 1 |

累计：

- OCR 文件：5 份
- 图片资产 metadata：28 个

每个图片资产 metadata 均包含：

- `source_domain=enterprise_fact`
- `doc_owner=泰昌`
- `enterprise=泰昌`
- `evidence_type`
- `target_library`
- `privacy_level`
- `reference_only=false`
- `fact_source_allowed_for_enterprise=true`
- `page_idx/page_no/bbox`
- `asset_sha256`
- `do_not_mix_with=河北豪乾参考稿`

## 2026-06-06 泰昌 MVP 图片智能选图 P0

### 边界修正

本次按客户确认重新收口：

- 泰昌是 MVP 试点企业，企业事实和图片资产主线固定为 `enterprise=泰昌`、`doc_owner=泰昌`、`source_domain=enterprise_fact`。
- 辽宁资料只是客户提供的电缆保护管招标场景样本，用于招标要求、技术规范、货物清单和合同条款，不作为 MVP 企业主体事实。
- 河北豪乾资料仅作格式、目录、章节组织、写法参考，`reference_only=true`，不得作为泰昌企业事实。

### 已完成代码任务

- `backend/rag/retrieval.py`：`search_knowledge_assets()` 增加 `metadata_filter`，并把 `metadata/specs` 写入资产检索文本；补 `evidence_type` 查询意图加权。
- `backend/api/knowledge.py`：智能问答检索泰昌问题时自动把图片资产限定为泰昌企业事实，避免参考稿和其他企业资产混入。
- `backend/api/routes.py`：标书导出“图文并茂”按章节推断 `evidence_type`，强约束生产制造、试验检测、绿色低碳、营业执照/证书、检验报告。
- `tests/test_rag_asset_scoring.py`、`tests/test_rag_retrieval.py`：补泰昌生产/试验/绿色/资信图片选择与 metadata 隔离回归。

### 验证记录

真实库候选池：

- `knowledge_assets` 图片候选：242 个。

真实库章节选图模拟：

| 章节 | 选中 evidence_type |
| --- | --- |
| 泰昌企业资信与营业执照 | `business_license`、`certification` |
| 泰昌生产制造能力 | `production_capacity` |
| 泰昌试验检测能力 | `testing_capacity` |
| 泰昌绿色低碳与绿色供应链能力 | `green_low_carbon` |

智能问答资产检索模拟：

| 查询 | Top evidence_type |
| --- | --- |
| 泰昌营业执照图片 | `business_license` |
| 泰昌 MPP 生产线图片 | `production_capacity` |
| 泰昌电子天平和万能试验机图片 | `testing_capacity` |
| 泰昌绿色供应链证书图片 | `green_low_carbon` |

回归评测：

- Base filtered：`docs/rag/runs/run_20260606_taichang_mvp_asset_p0_base_filtered.json`，Recall@5 86.7%。
- 泰昌 MVP 专项 filtered：`docs/rag/runs/run_20260606_taichang_mvp_asset_p0_customer_filtered.json`，Recall@5 100%，禁用关键词命中率 0%。

单测：

- `PYTHONPATH=. .venv/bin/pytest tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q`
- 结果：16 passed。

## 2026-06-06 泰昌 MVP 真实生产链路回归

### 服务状态

真实链路启动前确认：

- 前端：`http://127.0.0.1:5173` 返回 200。
- 后端：`http://127.0.0.1:8000/api/ready` 返回 `status=ok`。
- Celery：`checks.celery.status=ok`，在线 worker 数 1。
- PostgreSQL / Redis：均健康。
- 模型配置：`deepseek_api_key`、`dashscope_api_key`、`mineru_api_token` 均存在。

### 真实全链路 3 章节

样本文件：

- `rag_seed/power_grid_resources/01_tender_documents/22_国网辽宁电力2025年第三次物资协议库存招标采购/extracted/电缆保护管CPVC/包1_完整招标文件_53488484541066181/国网辽宁电力2025年第三次物资协议库存招标采购招标文件.docx`

报告：

- `docs/development/runs/run_20260606_taichang_mvp_real_flow_3_sections.md`

结果：

| 步骤 | 结果 |
| --- | --- |
| 上传解析 | indexed，parser=`native_text` |
| AI 解读 | 真实 DeepSeek 调用通过，约 345 秒 |
| 大纲 | 74 章节 |
| 章节生成 | 3/3 done，约 34 秒 |
| 合规检查 | 220 rows，覆盖率 27% |
| DOCX 导出 | completed，LibreOffice 字段刷新成功 |

### 真实全链路 30 章节长任务

报告：

- `docs/development/runs/run_20260606_taichang_mvp_real_flow_30_sections.md`

结果：

| 步骤 | 结果 |
| --- | --- |
| 章节生成任务 | `b6d7da7c-d49b-4cfb-8a39-bdea9b79ef50` |
| 章节数 | 30 |
| 完成情况 | 30/30 done |
| 耗时 | 278151 ms |
| 合规检查 | 220 rows，覆盖率 36% |
| DOCX 导出 | `5653a7b6-384b-4a06-9509-6321e8208888` completed |
| DOCX 文件 | `outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购招标文件.docx` |

### 泰昌图片问答与图文并茂

智能问答：

- 查询：泰昌电子天平、万能试验机等试验检测能力。
- 真实 LLM 返回答案，`assets=8`、`images=8`。
- Top 资产均为 `enterprise=泰昌`、`reference_only=false`、`evidence_type=testing_capacity`。
- 结果 JSON：`docs/development/runs/run_20260606_taichang_mvp_real_knowledge_qa_images.json`

图文并茂章节：

- 创建真实章节：`泰昌生产制造与试验检测能力`。
- `withImages=true` 流式生成通过，章节保存为 `generated`。
- 正文包含 2 个泰昌图片链接，均为 `/api/bidding/knowledge/assets/.../file?variant=original`。
- SSE 记录：`docs/development/runs/run_20260606_taichang_mvp_real_image_section_sse_saved.txt`

### 本轮发现并修复

- 问题：图文并茂章节中，知识库图片资产原先优先输出本机 `parsed_outputs/...` 绝对路径，浏览器端无法稳定显示。
- 修复：`backend/api/routes.py::_asset_image_ref()` 改为资产有 `id` 时优先输出 `/api/bidding/knowledge/assets/<id>/file?variant=original`，本地路径仅作无资产 id 的兜底。
- 回归：`PYTHONPATH=. .venv/bin/pytest tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py tests/test_docx_export.py -q`，31 passed。

### 剩余风险

- AI 解读阶段耗时约 345 秒，真实客户文件下可用，但需要后续考虑后台化或进度可视化。
- 泰昌 CPVC/MPP 检验报告“内径250”与辽宁 φ50/100/150/175/200 需求的覆盖关系仍需业务确认。
- 30 章节无图导出时发现模型偶发输出非资产图片占位，导出会跳过；正式图文并茂应继续依赖系统资产选择链路。

### 泰昌第二批 MinerU OCR

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_batch_02/`

本批目标是补齐生产制造能力、厂房与试验检测设备材料，支撑后续技术标图文插入和知识库问答中的图片展示。

已完成文件：

| 文件 | evidence_type | 页数 | 状态 | 图片资产 |
| --- | --- | ---: | --- | ---: |
| `2.土地使用证明.pdf` | `production_capacity` | 1 | `mineru_done` | 1 |
| `4.电费发票.pdf` | `production_capacity` | 3 | `mineru_done` | 0 |
| `1.土地租赁协议.pdf` | `production_capacity` | 4 | `mineru_done` | 4 |
| `3.厂房图片.pdf` | `production_capacity` | 6 | `mineru_done` | 6 |
| `电子天平.pdf` | `testing_capacity` | 6 | `mineru_done` | 7 |
| `1.CPVC63三层复合管材挤出生产线.pdf` | `production_capacity` | 7 | `mineru_done` | 5 |
| `2.CPVC110三层复合管材挤出生产线.pdf` | `production_capacity` | 7 | `mineru_done` | 5 |
| `溶体流动速率仪.pdf` | `testing_capacity` | 7 | `mineru_done` | 8 |
| `3.MPP生产线.pdf` | `production_capacity` | 8 | `mineru_done` | 7 |
| `微机控制电子万能试验机.pdf` | `testing_capacity` | 8 | `mineru_done` | 7 |

本批新增：

- OCR 文件：10 份
- 图片资产 metadata：50 个

累计：

- OCR 文件：15 份
- 图片资产 metadata：78 个

### 统一图片资产索引

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/asset_index.json`

摘要：

| target_library | 图片资产数 |
| --- | ---: |
| `qualification_library` | 27 |
| `product_library` | 51 |

| evidence_type | 图片资产数 |
| --- | ---: |
| `business_license` | 1 |
| `certification` | 26 |
| `production_capacity` | 29 |
| `testing_capacity` | 22 |

统一索引中每个资产均要求包含：

- 图片显示：`asset_path`、`asset_sha256`、`page_no`、`bbox`
- 问答召回：`retrieval_text`、`caption_candidate`、`ocr_context`
- 入库边界：`source_domain=enterprise_fact`、`doc_owner=泰昌`、`enterprise=泰昌`
- 目标库：`target_library=qualification_library/product_library`
- 展示场景：`display_contexts=[bid_writing, knowledge_chat, asset_search]`
- 防串用：`reference_only=false`、`fact_source_allowed_for_enterprise=true`、`do_not_mix_with=河北豪乾参考稿`

## 回归验证

命令：

```bash
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/manifest.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/asset_manifest.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/status.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/goods_tables/goods_rows.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/goods_tables/goods_summary.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/reference_templates/haoqian_reference_templates.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/ocr_plan/taichang_ocr_plan.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_batch/batch_summary.json
PYTHONPATH=. .venv/bin/pytest tests/test_mineru_status.py -q
```

结果：

- JSON 产物校验通过。
- 语义检查通过：辽宁货物清单 87 条；河北豪乾 2 份参考稿均为 `reference_only=true` 且 `fact_source_allowed_for_enterprise=false`；首批 MinerU batch 全部 `mineru_done`。
- 统一图片资产索引语义检查通过：78 个资产全部为泰昌企业事实，均有 `asset_path/asset_sha256/page_no/bbox`，且全部禁止混用河北豪乾参考稿。
- `docs/rag/todo.md` P0 核查通过，P0 行全部为 `[x]`。
- `tests/test_mineru_status.py`：5 passed。
- 单测有 PyPDF2 / `datetime.utcnow()` deprecation warnings，不影响本轮 P0 资料处理结论。

## 2026-06-06 第三批 OCR

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_batch_03/`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/asset_index.json`

本批目标：

- 补齐试验检测设备图片资料；
- 解析人员证书、社保证明、花名册等受限私有资料；
- 验证 `taichang_internal_private` 图片资产必须带授权展示 metadata。

已完成文件：

| 文件 | evidence_type | 页数 | privacy_level | 状态 | 图片资产 |
| --- | --- | ---: | --- | --- | ---: |
| `锤击试验装置.pdf` | `testing_capacity` | 8 | `private` | `mineru_done` | 9 |
| `电子拉力试验机.pdf` | `testing_capacity` | 8 | `private` | `mineru_done` | 8 |
| `热变型、维卡软化点温度测定仪.pdf` | `testing_capacity` | 9 | `private` | `mineru_done` | 14 |
| `1.陈仙瑞.pdf` | `production_capacity` | 1 | `taichang_internal_private` | `mineru_done` | 1 |
| `2.晁坤琳.pdf` | `production_capacity` | 1 | `taichang_internal_private` | `mineru_done` | 2 |
| `泰昌社保证明.pdf` | `production_capacity` | 1 | `taichang_internal_private` | `mineru_done` | 2 |
| `1.陈仙瑞.pdf` | `testing_capacity` | 1 | `taichang_internal_private` | `mineru_done` | 1 |
| `2.晁坤琳.pdf` | `testing_capacity` | 1 | `taichang_internal_private` | `mineru_done` | 2 |
| `泰昌社保证明.pdf` | `testing_capacity` | 1 | `taichang_internal_private` | `mineru_done` | 2 |
| `公司人员花名册.pdf` | `production_capacity` | 2 | `taichang_internal_private` | `mineru_done` | 0 |

本批新增：

- OCR 文件：10 份
- 图片资产 metadata：41 个

累计：

- OCR 文件：25 份
- 图片资产 metadata：119 个

统一图片资产索引刷新后：

| 维度 | 数量 |
| --- | ---: |
| 全部图片资产 | 119 |
| `qualification_library` | 27 |
| `product_library` | 92 |
| `private` | 108 |
| `taichang_internal_private` | 11 |

按 evidence_type：

| evidence_type | 图片资产数 |
| --- | ---: |
| `business_license` | 1 |
| `certification` | 26 |
| `production_capacity` | 34 |
| `testing_capacity` | 58 |

受限资产规则：

- `taichang_internal_private` 资产在泰昌租户内 `requires_authorization=false`；
- 展示场景为 `bid_writing` / `knowledge_chat` / `asset_search`；
- metadata 中写入 `sensitive_handling=taichang_internal_use_no_redaction_required`；
- 可进入泰昌租户内普通知识库问答图片展示，但禁止跨企业/跨租户展示。

第三批回归：

```bash
find parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0 -name '*.json' -maxdepth 5 -print0 | xargs -0 -I{} .venv/bin/python -m json.tool {} >/dev/null
PYTHONPATH=. .venv/bin/pytest tests/test_mineru_status.py -q
```

结果：

- JSON 全量校验：`all_json_ok`
- 图片资产语义检查：`asset_semantic_checks_ok`
- MinerU 状态单测：5 passed

## 2026-06-06 全量 OCR 补齐

用户确认 OCR 额度充足后，本轮将剩余 17 份 PDF 全部走 MinerU，包括原生文本可抽取但需要版式/图片资产的检验报告、绿色低碳材料和审计报告。

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_batch_04/`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/asset_index.json`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/ocr_coverage_report.json`

第四批完成文件：

| evidence_type | 文件数 | 图片资产 |
| --- | ---: | ---: |
| `certification` | 3 | 15 |
| `production_capacity` | 3 | 3 |
| `testing_capacity` | 3 | 2 |
| `inspection_report` | 2 | 2 |
| `green_low_carbon` | 3 | 38 |
| `finance` | 3 | 63 |

最终 OCR 覆盖：

| 指标 | 数量 |
| --- | ---: |
| 泰昌 PDF 总数 | 42 |
| MinerU 完成 | 42 |
| 缺失 | 0 |
| 图片资产 | 242 |
| 资产 manifest | 42 |

按目标库：

| target_library | 图片资产数 |
| --- | ---: |
| `qualification_library` | 105 |
| `product_library` | 137 |

按 evidence_type：

| evidence_type | 图片资产数 |
| --- | ---: |
| `business_license` | 1 |
| `certification` | 41 |
| `finance` | 63 |
| `green_low_carbon` | 38 |
| `inspection_report` | 2 |
| `production_capacity` | 37 |
| `testing_capacity` | 60 |

按敏感级别：

| privacy_level | 图片资产数 |
| --- | ---: |
| `private` | 164 |
| `taichang_internal_private` | 78 |

受限资产规则继续保持：

- `taichang_internal_private` 资产全部包含 `requires_authorization=false`；
- 展示场景为 `bid_writing` / `knowledge_chat` / `asset_search`；
- metadata 中写入 `sensitive_handling=taichang_internal_use_no_redaction_required`；
- 可进入泰昌租户内普通问答图片展示，禁止跨企业/跨租户展示。

全量补齐回归：

```bash
find parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0 -name '*.json' -maxdepth 5 -print0 | xargs -0 -I{} .venv/bin/python -m json.tool {} >/dev/null
PYTHONPATH=. .venv/bin/pytest tests/test_mineru_status.py -q
```

结果：

- JSON 全量校验：`all_json_ok`
- 覆盖率和图片资产语义检查：`coverage_and_asset_semantic_checks_ok`
- MinerU 状态单测：5 passed

## 2026-06-06 Parse Quality 与专项测试集

### Parse Quality Report

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/parse_quality_report.json`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/parse_quality_report.md`

摘要：

| 指标 | 数量 |
| --- | ---: |
| PDF 总数 | 42 |
| MinerU 完成 | 42 |
| 文本字符数 | 284019 |
| 图片资产 | 242 |
| 泰昌内部私有图片资产 | 78 |

按资料类型：

| evidence_type | 文件数 | 文本字符 | 图片资产 | 泰昌内部私有文件 |
| --- | ---: | ---: | ---: | ---: |
| `finance` | 3 | 91859 | 63 | 3 |
| `certification` | 6 | 24997 | 41 | 0 |
| `inspection_report` | 2 | 8825 | 2 | 0 |
| `production_capacity` | 15 | 33036 | 37 | 6 |
| `testing_capacity` | 12 | 60938 | 60 | 6 |
| `green_low_carbon` | 3 | 63806 | 38 | 0 |
| `business_license` | 1 | 558 | 1 | 1 |

入库建议：

| 建议 | 文件数 |
| --- | ---: |
| `ready_for_private_ingestion` | 24 |
| `ready_for_taichang_internal_ingestion` | 16 |
| `ingest_with_spec_coverage_warning` | 2 |

质量标记：

| 标记 | 数量 | 处理 |
| --- | ---: | --- |
| `taichang_internal_private_allowed_for_tenant_use` | 16 | 泰昌租户内可直接展示或入普通问答 |
| `spec_coverage_needs_business_confirmation` | 2 | CPVC/MPP 内径 250 检验报告需确认与辽宁清单规格覆盖关系 |
| `no_image_assets` | 3 | 可保留文本，不影响 OCR 完成状态 |

### 辽宁/泰昌专项评测集

产物：

- `tests/rag/customer_liaoning_taichang_testset.jsonl`

用例数：17 条。

覆盖场景：

- 辽宁 `2225AC` CPVC/MPP 货物清单；
- 辽宁技术规范和合同条款；
- 泰昌营业执照、三体系认证、生产制造能力、试验检测能力、绿色低碳、检验报告；
- 图片资产召回和展示 metadata；
- 河北豪乾商务/技术参考稿仅作为格式模板；
- 负样本：禁止河北豪乾参考稿变成泰昌事实，禁止泰昌企业事实污染辽宁招标要求，允许泰昌租户内企业自有图片在普通问答展示，但禁止跨企业/跨租户展示。

说明：

- 当前测试集已作为正式入库后的召回门禁运行。
- 结果已追加到 `docs/rag/evaluation-records.md`。

验证：

```bash
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/parse_quality_report.json >/dev/null
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/ocr_coverage_report.json >/dev/null
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/asset_index.json >/dev/null
PYTHONPATH=. .venv/bin/pytest tests/test_mineru_status.py -q
```

结果：

- JSON / JSONL 校验：`all_json_and_jsonl_ok`
- 专项测试集语义校验：`testset_semantic_checks_ok`
- Parse quality 语义校验：`parse_quality_semantic_checks_ok`
- MinerU 状态单测：5 passed

## 2026-06-06 正式入库与召回回归

### Staging / Dry-run

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/staging_manifest.json`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/asset_staging_payloads.json`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/chunk_dry_run_report.md`

Dry-run 结果：

| 指标 | 数量 |
| --- | ---: |
| staging records | 124 |
| chunked documents | 122 |
| table ready documents | 2 |
| needs_review | 0 |
| parent chunk | 2021 |
| child/table 检索块 | 27571 |
| table rows | 89 |
| asset payload | 242 |

### 正式入库

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/formal_ingestion_summary.md`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/ingest_taichang_assets_report.md`

入库结果：

| 表 / 对象 | 数量 |
| --- | ---: |
| `knowledge_documents` | 124 |
| `document_chunks` | 29683 |
| `power_grid_goods_list_rows` | 87 |
| `knowledge_assets` | 242 |
| `knowledge_assets.embedding` | 242 |

图片资产目标库：

| target_library | 数量 |
| --- | ---: |
| `qualification_library` | 105 |
| `product_library` | 137 |

### 回归评测

命令：

```bash
.venv/bin/python scripts/rag/eval_recall.py --k 5 --save docs/rag/runs/run_20260606_taichang_mvp_base_filtered.json
.venv/bin/python scripts/rag/eval_recall.py --k 5 --no-filter --save docs/rag/runs/run_20260606_taichang_mvp_base_nofilter.json
.venv/bin/python scripts/rag/eval_recall.py --k 5 --testset tests/rag/customer_liaoning_taichang_testset.jsonl --save docs/rag/runs/run_20260606_taichang_mvp_customer_filtered.json
PYTHONPATH=. .venv/bin/pytest tests/test_mineru_status.py -q
```

结果：

| 测试 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 86.7% | 93.3% | 86.7% | 0.0% | - |
| Base no-filter | 73.3% | 66.7% | 90.0% | 43.3% | - |
| 辽宁/泰昌专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

单测：`tests/test_mineru_status.py` 5 passed。

### 本轮修复

- 新增 `scripts/rag/stage_liaoning_taichang_mvp.py`，把辽宁招标文本、泰昌 OCR 文本、河北豪乾参考模板、泰昌图片资产目录统一转为 staging manifest。
- 新增 `scripts/rag/ingest_taichang_assets.py`，把 242 个泰昌图片资产写入 `knowledge_assets`。
- 修复 `backend/db/supabase_repo.py` 中缺失的 `_knowledge_asset_bucket()`，否则资产上传会全部失败。
- 增加 1 条 `self_phrase` Base 回归话术，恢复 T23 命中，Base Recall@5 保持 86.7%。

### 剩余业务确认

- 泰昌 CPVC/MPP 检验报告为“内径250”，与辽宁清单规格覆盖关系仍需业务确认。
- 河北豪乾资料只作为 `reference_template`，不得作为泰昌事实来源。

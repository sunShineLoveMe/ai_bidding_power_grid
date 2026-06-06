# 国家电网 RAG 基座数据工程待办清单

> 状态日期：2026-06-06
> 适用范围：电网/国家电网招投标 RAG 基座数据、客户标书模板、行业资料、召回评测与上线门禁。

本文档用于跟踪 RAG 基座数据工程的优先级、完成度和验收口径。全局产品路线仍看 `docs/development/roadmap.md`；本清单只记录 RAG 数据工程相关任务。

## 状态标记

| 标记 | 含义 |
| --- | --- |
| `[x]` | 已完成并通过基本验证 |
| `[~]` | 进行中或部分完成 |
| `[ ]` | 未开始 |
| `[!]` | 阻塞或需业务确认 |

## P0：基座闭环与防回退

目标：保证现有电网种子库可复跑、可评测、主检索走场景化过滤，避免后续客户资料越加越乱。

| 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- |
| [x] | 水利历史资料清理 | `docs/rag/water-data-cleanup.md` | `rag_seed` 下不再保留 water/水利干扰资料 |
| [x] | 父子双层分块 v2 | `backend/rag/chunking.py` | 支持按 `doc_role` 父子分块，并已补标题-only parent 过滤单测 |
| [x] | 电网种子库 v2 入库脚本 | `scripts/rag/ingest_power_grid_v2.py` | 支持 `--dry-run`、按 `doc_role` 分块、仅 child embedding |
| [x] | metadata 过滤 RPC 与 HNSW | `migrations/postgres/006_rag_p0_filtered_recall.sql` | 支持 `match_knowledge_chunks_filtered`、`get_parent_chunk` |
| [x] | Base 测试集与基线记录 | `tests/rag/base_testset.jsonl`、`docs/rag/evaluation-records.md` | 30 条用例，Recall@5 86.7%，串扰 0% |
| [x] | 主检索接入 filtered RPC | `backend/rag/retrieval.py`、`backend/api/knowledge.py` | 单测确认不再默认调用老 `match_knowledge_chunks` |
| [x] | 写作场景父块回溯 | `backend/rag/retrieval.py`、`backend/ai/chapter_planner.py` | writing 场景 child 命中后可返回 parent |
| [x] | 核心文档改为 v2 链路 | `docs/features/rag-knowledge-base.md`、`rag_seed/power_grid_resources/README.md` | 当前操作指南不再指向旧入库脚本 |
| [x] | 旧部署/历史文档标注迁移参考 | `docs/deployment/*` | 已在 Supabase/旧 RAG 入口文档标注“历史/迁移参考”，新环境指向 `migrations/postgres/` 与 v2 RAG 入库链路 |

## P1：客户江西/山西标书模板入库

目标：把客户真实资料纳入 RAG 样本和评测，不再只依赖公开种子库。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P1-1 | [x] | 梳理江西/山西压缩包文件清单 | `docs/rag/customer-corpus-inventory.md` | 按省份、批次、包号、文件类型、是否铁构件/接地铁相关标注 |
| P1-2 | [x] | 解析 `.docx` 主招标文件 | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/`、入库前 manifest | 20 个 `.docx` 已抽文本并统计段落/表格/标题，待正式分块入库 |
| P1-3 | [x] | 解析 `.doc` 老二进制文件 | 转换后的 `.docx/.md` 与解析报告 | 3 个 `.doc` 已通过 LibreOffice 转 `.docx` 后解析，`needs_review=0` |
| P1-4 | [x] | 解析 `.xlsx` 货物清单/技术参数表 | 结构化 JSON、表格摘要 | 2 个货物清单已用 openpyxl 解析，保留 sheet、行列、合并单元格和包号 |
| P1-5 | [x] | 客户资料 metadata 规范化 | `manifest.json` | manifest 已包含 `province/batch_no/package_no/package_code/material_category/doc_role/source_file` 等字段 |
| P1-6 | [x] | 江西/山西批次负样本 | `tests/rag/customer_jx_sx_testset.jsonl` | 已加入 `must_not_include_keywords`，覆盖江西 `1826AA` / 山西 `0526AB` 跨包隔离 |
| P1-7 | [x] | 铁构件/接地铁首批真实用例 | `tests/rag/customer_jx_sx_testset.jsonl` | 17 条客户真实场景，覆盖 qa/writing/compliance/table |
| P1-8 | [x] | 入库后回归评测 | `docs/rag/evaluation-records.md` Run 4 | 客户 filtered Recall@5 100%，Base filtered 保持 86.7%，跨 doc_role 串扰 0% |
| P1-9 | [x] | 客户资料父子分块 dry-run | `chunk_dry_run_report.md` | 21 个文本资料产出 221 parent / 3908 child，2 个表格资料 107 行，`needs_review=0` |
| P1-10 | [x] | 客户资料解析 QA 门禁 | `docs/rag/customer-parse-qa-checklist.md` | 12 条解析 QA 全部通过，命中率 100% |
| P1-11 | [x] | 客户资料 staging 入库 | `scripts/rag/ingest_customer_corpus.py` | 23 文档 indexed，223 parent / 4015 检索块，按 `ingestion_batch_id` 隔离 |

## P2：持续客户模板治理

目标：客户后续持续提供模板时，形成稳定收口机制，而不是每次临时处理。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P2-1 | [x] | 客户资料入库 SOP | `docs/rag/customer-template-ingestion-sop.md` | 已沉淀从收件、inventory、解析、图片 metadata、入库、回归到归档的全流程；固化泰昌企业事实、辽宁招标要求、河北豪乾参考稿隔离边界 |
| P2-2 | [x] | 每批资料 manifest 规范 | `docs/rag/customer-batch-manifest-template.md` | 已定义批次级与文件级字段、取值约束、泰昌/辽宁/河北豪乾强校验和入库前检查命令 |
| P2-3 | [x] | 解析质量报告模板 | `docs/rag/parse-quality-report-template.md` | 已覆盖空文本、乱码、表格丢失、页码缺失、扫描件、图片资产、metadata 完整性和真实链路回归记录 |
| P2-4 | [ ] | 版本与去重策略 | `content_sha256`、`doc_version`、`superseded_by` | 同一模板新旧版本不会同时污染召回 |
| P2-5 | [ ] | 模板可引用边界 | `citation_policy` 规则 | 区分客户模板、公开法规、企业话术，避免把模板当强制条款 |
| P2-6 | [x] | 批次回滚机制 | `scripts/rag/rollback_customer_corpus.py`、`docs/rag/runs/rollback_customer_jx_sx_20260602_p1_dry_run_20260602_165145.md` | 支持按 `ingestion_batch_id` dry-run/execute 删除，当前 dry-run 覆盖 23 文档、4238 chunk、105 结构化行 |

## P1A：泰昌 MVP 试点资料入库与辽宁招标样本隔离

目标：以泰昌为 MVP 试点企业事实主线；辽宁资料仅作为客户提供的电缆保护管招标场景样本，不作为 MVP 企业主体事实来源。所有问答、写作、图片资产展示必须避免把泰昌事实、辽宁招标要求、河北豪乾参考稿混用。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P1A-1 | [x] | 解压并 inventory 辽宁/泰昌新增资料 | `docs/rag/liaoning-taichang-mvp-corpus-review.md`、`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_inventory.json` | 已保留原始包，辽宁 185 个文件、泰昌 45 个文件已登记 |
| P1A-2 | [x] | 判断资料完整性和可用边界 | `docs/rag/liaoning-taichang-mvp-corpus-review.md`、`docs/development/runs/run_20260606_taichang_mvp_real_flow_30_sections.md` | 已确认泰昌为 MVP 企业事实主线、辽宁仅作招标样本、河北豪乾仅作参考稿；真实链路完成 30 章节生成与 DOCX 导出。剩余业务风险：CPVC/MPP 各规格检验报告覆盖仍需客户确认 |
| P1A-3 | [x] | 辽宁货物清单结构化解析兼容 | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/goods_tables/` | 已兼容 `dimension ref=A1` 异常并输出 87 条去重需求行 |
| P1A-4 | [x] | 泰昌扫描 PDF OCR 与图片资产 metadata | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/ocr_coverage_report.json`、`asset_index.json` | 泰昌 42 份 PDF 已全部 MinerU 完成，生成 242 个图片资产 metadata，其中 78 个 `taichang_internal_private` 资产可在泰昌租户内问答/写作/资产检索展示；覆盖率和资产语义校验通过 |
| P1A-5 | [x] | 河北豪乾参考稿隔离入库 | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/reference_templates/` | 已抽取 2 份河北豪乾参考稿基础模板数据，均标记 `reference_only=true`，不得作为泰昌企业事实来源 |
| P1A-6 | [x] | 辽宁/泰昌专项评测集 | `tests/rag/customer_liaoning_taichang_testset.jsonl`、`docs/rag/runs/run_20260606_taichang_mvp_customer_filtered.json` | 17 条用例已跑正式召回，Recall@5 100%，禁用关键词命中率 0%，覆盖 CPVC/MPP 型号、包号、技术规范编码、泰昌事实、图片资产、河北豪乾参考稿隔离和泰昌租户内图片展示策略 |
| P1A-7 | [x] | 泰昌 OCR parse quality report | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/parse_quality_report.md` | 已汇总 42 份 PDF 的文本量、图片资产、敏感级别、人工复核项和可入库建议 |
| P1A-8 | [x] | 辽宁/泰昌 MVP 正式入库与回归 | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/formal_ingestion_summary.md`、`docs/rag/runs/run_20260606_taichang_mvp_base_filtered.json` | 已写入 124 个 `knowledge_documents`、29683 个 `document_chunks`、87 条结构化货物清单、242 个图片资产；Base Recall@5 保持 86.7%，专项 Recall@5 100% |
| P1A-9 | [x] | P0：泰昌 MVP 图片智能问答与图文并茂选图准确性 | `backend/rag/retrieval.py`、`backend/api/knowledge.py`、`backend/api/routes.py`、`tests/test_rag_asset_scoring.py`、`tests/test_rag_retrieval.py`、`docs/rag/runs/run_20260606_taichang_mvp_asset_p0_*` | 问答资产检索已按泰昌企业事实 metadata 过滤；标书配图已按 `evidence_type` 强约束生产制造、试验检测、绿色低碳、营业执照/证书、检验报告；真实库 242 个资产模拟通过，Base Recall@5 86.7%，泰昌专项 Recall@5 100% |

## P3：召回质量增强

目标：从“能召回”升级到“可控、可解释、可持续优化”。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P3-1 | [ ] | Query Rewrite | 查询改写模块/规则 | 标准号、物料名、包号、条号可被规范化 |
| P3-2 | [ ] | 关键词补召回 | 混合检索策略 | 技术参数表、包号、物料编码不只依赖向量 |
| P3-3 | [ ] | authority 排序 | 排序规则 | 法规/国网规则优先于模板话术，客户招标文件优先于通用样例 |
| P3-4 | [ ] | Rerank 对比实验 | 评测记录新 run | 对比无 rerank、DashScope rerank、本地 rerank 的 Recall/MRR |
| P3-5 | [ ] | 评测集扩到 40-60 条 | 扩展 JSONL | qa/writing/compliance/table 四类均有样本 |
| P3-6 | [ ] | 增量回归门禁 | CI/脚本说明 | 新批次入库后必须跑评测，指标退化需记录原因 |

## P4：表格与结构化知识

目标：解决 `.xlsx`、技术参数表、货物清单、偏差表这类“向量文本化容易丢信息”的资料。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P4-1 | [x] | 表格三形态存储 | 原始结构 + 检索摘要 + 行级记录 | 货物清单已保留 JSON 原始结构、staging table summary/table row，并写入 `power_grid_goods_list_rows` 结构化行表 |
| P4-2 | [ ] | 技术参数表抽取 | JSON/CSV + summary chunk | 保证值、项目需求值、备注字段不丢失 |
| P4-3 | [x] | 货物清单解析 | `scripts/rag/ingest_customer_goods_tables.py`、`scripts/rag/query_customer_goods_tables.py` | 江西 7 行、山西 98 行已可按包号、物料名称、单位、数量、技术规范编码、物料编码过滤 |
| P4-4 | [ ] | 技术偏差/商务偏差辅助 | 偏差表生成依据 | 能定位招标要求和响应模板来源 |

## 每批客户资料入库检查清单

1. 文件解压到 `rag_seed/power_grid_resources/01_tender_documents/<批次目录>/`，保留原始压缩包。
2. 建立批次 manifest，标注省份、批次、包号、物料类型、文件角色。
3. 对 `.pdf/.doc/.docx/.xlsx` 分别选择解析器，失败文件标 `needs_review`。
4. 清洗页眉页脚、目录、网页导航、乱码和重复段落。
5. 按 `doc_role` 和表格类型分块，写入 metadata。
6. 跑 dry-run，检查 parent/child/table 数量是否异常。
7. 入库后跑 Base + 批次负样本评测。
8. 将评测结果追加到 `docs/rag/evaluation-records.md`。
9. 若 Recall、来源准确率或串扰退化，先修数据/metadata，不直接调模型参数掩盖问题。

## 当前最近任务

1. 进入 P2-4/P2-5：补版本去重策略和模板可引用边界，避免旧模板、参考稿和企业事实污染召回。
2. 进入 P3 Query Rewrite / 关键词补召回 / authority 排序，提升标准号、包号、物料编码精确召回。
3. 向客户确认泰昌 CPVC/MPP 各规格检验报告覆盖关系，尤其是“内径250”报告能否覆盖辽宁 φ50/100/150/175/200 需求。
4. 扩展泰昌 MVP 专项评测集到 40-60 条，并加入更多包号、技术规范编码、合同条款、图片问答和参考稿隔离负样本。
5. 追加导出观感人工验收：打开 30 章节真实 DOCX，检查封面、目录、正文、表格、页眉页脚、页码和图片占位告警。

# 国家电网 RAG 基座数据工程待办清单

> 状态日期：2026-06-12
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
| P2-4 | [x] | 版本与去重策略 | `scripts/rag/customer_metadata_policy.py`、`scripts/rag/ingest_customer_corpus.py`、`docs/rag/runs/run_20260607_p2_version_citation_summary.md` | 入库门禁校验 `source_sha256/doc_identity_key/doc_version/superseded_by`；同一逻辑资料新版本正式入库后会将旧版本置为 `superseded`；dry-run 已验证泰昌/辽宁与江西/山西 manifest `blocked_metadata=0` |
| P2-5 | [x] | 模板可引用边界 | `scripts/rag/customer_metadata_policy.py`、`docs/rag/customer-template-ingestion-sop.md`、`tests/test_customer_metadata_policy.py` | `enterprise_fact/tender_requirement/reference_template/policy_regulation/base_seed` 均有明确 `citation_policy`；企业事实、招标要求、参考稿边界已单测覆盖并纳入入库 dry-run 门禁 |
| P2-6 | [x] | 批次回滚机制 | `scripts/rag/rollback_customer_corpus.py`、`docs/rag/runs/rollback_customer_jx_sx_20260602_p1_dry_run_20260602_165145.md` | 支持按 `ingestion_batch_id` dry-run/execute 删除，当前 dry-run 覆盖 23 文档、4238 chunk、105 结构化行 |

## P1A：泰昌 MVP 试点资料入库与辽宁招标样本隔离

目标：以泰昌为 MVP 试点企业事实主线；辽宁资料仅作为客户提供的电缆保护管招标场景样本，不作为 MVP 企业主体事实来源。所有问答、写作、图片资产展示必须避免把泰昌事实、辽宁招标要求、河北豪乾参考稿混用。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P1A-1 | [x] | 解压并 inventory 辽宁/泰昌新增资料 | `docs/rag/liaoning-taichang-mvp-corpus-review.md`、`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_inventory.json` | 已保留原始包，辽宁 185 个文件、泰昌 45 个文件已登记 |
| P1A-2 | [x] | 判断资料完整性和可用边界 | `docs/rag/liaoning-taichang-mvp-corpus-review.md`、`docs/development/runs/run_20260606_taichang_mvp_real_flow_30_sections.md` | 已确认泰昌为 MVP 企业事实主线、辽宁仅作招标样本、河北豪乾仅作参考稿；真实链路完成 30 章节生成与 DOCX 导出。若具体省公司投标需引用检验报告覆盖某规格，必须按目标省公司/批次/规格单独人工确认 |
| P1A-3 | [x] | 辽宁货物清单结构化解析兼容 | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/goods_tables/` | 已兼容 `dimension ref=A1` 异常并输出 87 条去重需求行 |
| P1A-4 | [x] | 泰昌扫描 PDF OCR 与正式图片资产 metadata | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/ocr_coverage_report.json`、`asset_index.json`、`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/rebuild_formal_image_assets_report.md` | 泰昌 42 份 PDF 已全部 MinerU/OCR 完成；原 242 个 MinerU 局部图片资产已删除，改用客户已提供 PDF/JPG 生成 300 个正式整页/原图图片资产；标题、分类、标签均为中文展示 |
| P1A-5 | [x] | 河北豪乾参考稿隔离入库 | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/reference_templates/` | 已抽取 2 份河北豪乾参考稿基础模板数据，均标记 `reference_only=true`，不得作为泰昌企业事实来源 |
| P1A-6 | [x] | 辽宁/泰昌专项评测集 | `tests/rag/customer_liaoning_taichang_testset.jsonl`、`docs/rag/runs/run_20260606_taichang_mvp_customer_filtered.json` | 17 条用例已跑正式召回，Recall@5 100%，禁用关键词命中率 0%，覆盖 CPVC/MPP 型号、包号、技术规范编码、泰昌事实、图片资产、河北豪乾参考稿隔离和泰昌租户内图片展示策略 |
| P1A-7 | [x] | 泰昌 OCR parse quality report | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/parse_quality_report.md` | 已汇总 42 份 PDF 的文本量、图片资产、敏感级别、人工复核项和可入库建议 |
| P1A-8 | [x] | 辽宁/泰昌 MVP 正式入库与回归 | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/formal_ingestion_summary.md`、`docs/rag/runs/run_20260606_taichang_mvp_base_filtered.json`、`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/rebuild_formal_image_assets_report.md` | 已写入 124 个 `knowledge_documents`、29683 个 `document_chunks`、87 条结构化货物清单；图片资产已从 242 个 MinerU 局部图重建为 300 个正式整页/原图资产；Base Recall@5 保持 86.7%，专项 Recall@5 100% |
| P1A-9 | [x] | P0：泰昌 MVP 图片智能问答与图文并茂选图准确性 | `backend/rag/retrieval.py`、`backend/api/knowledge.py`、`backend/api/routes.py`、`frontend/src/pages/KnowledgeBase/KnowledgeSearchDrawer.tsx`、`tests/test_rag_asset_scoring.py`、`tests/test_rag_retrieval.py`、`docs/rag/runs/run_20260606_taichang_mvp_asset_p0_*`、`scripts/rag/rebuild_taichang_formal_image_assets.py` | 问答资产检索与企业知识库问答已按泰昌企业事实 metadata 过滤；企业助手不再暴露资料范围/问答类型选择；参考来源按相关度降序、最多 5 条，且不明示江西/山西/辽宁等招标资料标签；标书配图已按 `evidence_type` 强约束生产制造、试验检测、绿色低碳、营业执照/证书、检验报告；真实库现为 300 个正式整页/原图资产；页面展示标题、分类、标签使用中文命名 |
| P1A-10 | [x] | 企业知识库参考来源中文化与确定性来源去重 | `backend/rag/display_names.py`、`scripts/rag/repair_chinese_display_names.py`、`scripts/rag/stage_liaoning_taichang_mvp.py`、`frontend/src/pages/KnowledgeBase/KnowledgeSearchDrawer.tsx`、`docs/rag/runs/run_20260608_chinese_display_names_*` | 已修复参考来源中 `taichang_*`、`power_grid_*`、`*_private.md` 等内部命名展示；9 个遗留资产目录 md 已改为中文文件名；真实库 metadata 已补充中文 `source_display_name/category_label/source_file`；同一 MPP 检验报告命中 5 行结构化参数时页面去重为 1 条确定性来源；Base Recall@5 96.7%，泰昌专项 Recall@5 100% |
| P1A-11 | [x] | 泰昌资质补充包与官方 Logo 入库 | `scripts/rag/stage_taichang_supplement_20260611.py`、`parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/`、`docs/rag/runs/run_20260611_taichang_supplement_full_summary.md` | 已处理 `泰昌资质文件(补充).zip` 和 `taichang.png`；70 个文件完成 inventory，13 份文本资料入库，297 个正式图片资产入库；签章/签名图片仅归档不自动用于标书；增量回归门禁 PASS，真实 stream 验证 CPVC/MPP 参数、Logo/生产线资产和中标通知书专项问答 |

## P1B：泰昌资质补充资料后续质量增强

目标：把 `customer_taichang_supplement_20260611` 从“已入库可检索”推进到“稳定支撑真实标书生成、业绩结构化和 DOCX 正式交付观感”。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P1B-1 | [x] | 补充资料入库质量复核 | `docs/rag/runs/run_20260611_taichang_supplement_p1b_quality.md`、`docs/rag/runs/run_20260611_taichang_supplement_p1b_quality.json` | 真实库复核通过：13 个文档、364 个 chunk、297 个图片资产、异常资产 metadata=0；Logo、检验报告、生产线、检测设备、合同协议书、中标通知书等均保留泰昌企业事实边界 |
| P1B-2 | [x] | 真实标书生成链路引用验证 | `docs/development/runs/run_20260611_taichang_supplement_p1b_docx_export.md`、导出 DOCX | 已走真实 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice` 链路；24 张图片全部插入，18 张来自补充包，覆盖项目业绩、生产制造、试验检测、检验报告、资质证书、基础证照 |
| P1B-3 | [x] | 复合问答漏答修复 | `backend/rag/retrieval.py`、`docs/rag/runs/run_20260611_taichang_supplement_p1b_quality.md`、`docs/rag/runs/run_20260611_taichang_supplement_p1b_compound_fix_summary.md` | “合同或中标通知书”类复合问题已通过真实 stream 回归；回答同时覆盖合同和中标通知书，并包含招标编号 `0322AB`；增量回归门禁 PASS |
| P1B-4 | [x] | 补充包扫描 PDF OCR 增强 | `scripts/rag/run_taichang_supplement_mineru_ocr.py`、`parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/p1b_mineru_ocr_report.md`、`docs/rag/runs/run_20260612_taichang_supplement_p1b_mineru_ocr_fix2_summary.md` | 15 份低文本/无文本扫描 PDF 已走真实 MinerU OCR，Manifest 更新 15 份；本批文本资料入库扩展为 24 份、1900 个 chunk；真实 stream 与增量回归门禁 PASS |
| P1B-5 | [x] | 项目业绩结构化抽取 | `scripts/rag/extract_taichang_project_performance.py`、`parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/`、`docs/rag/runs/run_20260612_taichang_project_performance_p1b5_summary.md` | 已从合同协议书和中标通知书交叉抽取 1 项业绩、2 份证据、每份 9 行明细；确认招标编号 `0322AB`、包2、总数量 54,678 米、含税金额 6,372,409.05 元；合同签署日期原件为空且未推断；真实 stream 与 Base+泰昌专项增量门禁 PASS |
| P1B-6 | [x] | Logo 与图片资产 DOCX 版式验证 | `backend/export/md_to_word.py`、`scripts/rag/verify_taichang_supplement_docx.py`、`docs/development/runs/run_20260612_taichang_supplement_p1b6_logo_image_layout.md` | 已接入高清 `assets/icons/taichang_logo.png`，封面和页眉均插入 Logo；真实 DOCX 导出 selected 24、inserted 24、failed 0，补充包图片 18 张；DOCX 图片裁剪标记 0，27 个内联图片比例检查通过，最大比例偏差 0.000101；LibreOffice 字段刷新成功 |
| P1B-7 | [x] | 泰昌 MVP 资料完整性评分 | `docs/rag/taichang-material-completeness-scorecard.md`、`docs/rag/runs/run_20260612_taichang_material_completeness_scorecard_summary.md`、`docs/rag/runs/run_20260612_taichang_material_completeness_scorecard_stream.md` | 已按标书章节和资料域标出资料充足/缺口：MVP 演示可用度 86/100、正式投标资料完整度 76/100；真实增量回归门禁 PASS，真实 DB + stream 验证 PASS |
| P1B-8 | [x] | DeepSeek 全量章节重写与客户版 DOCX/PDF 验收 | `scripts/rag/regenerate_taichang_full_bid_deepseek.py`、`docs/development/runs/run_20260612_taichang_deepseek_full_rewrite.md`、`docs/development/runs/run_20260612_taichang_full_bid_final_v6.md`、`docs/rag/runs/run_20260612_taichang_full_bid_deepseek_rewrite_regression_summary.md` | 已按 74 个章节清空旧正文后真实调用 `deepseek-v4-flash` 全量重写，成功 74、失败 0；正式导出链路 PASS，74/74 章节有正文，封面首页页眉为空，Logo 完整显示，错误分标占位已过滤，PDF 字体使用 `SimSun` / `Arial Unicode MS` 且视觉验证正常，图片 24/24 插入，表格 109 个；Base + 泰昌专项增量回归 Gate PASS |

## P3：召回质量增强

目标：从“能召回”升级到“可控、可解释、可持续优化”。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P3-1 | [x] | Query Rewrite | `backend/rag/retrieval.py`、`tests/test_rag_retrieval.py`、`docs/rag/runs/run_20260607_p3_query_keyword_summary.md` | 已提取标准号、包号、技术规范编码、物料编码、供应商管理、不良行为、施工工艺等关键词，并拼入 embedding 查询文本 |
| P3-2 | [x] | 关键词补召回 | `backend/rag/retrieval.py`、`scripts/rag/eval_recall.py`、`docs/rag/runs/run_20260607_p3_query_keyword_*` | 向量召回不足或高精度关键词未命中时补查 `document_chunks`；已改为分页扫描并补充质量安全环保领域词；Base Recall@5 86.7% -> 96.7%，泰昌专项保持 100%，跨域串扰 0% |
| P3-3 | [x] | authority 排序 | `backend/rag/retrieval.py`、`tests/test_rag_retrieval.py` | 法规/标准、招标要求、企业事实加权；`reference_style_only` 降权，单测覆盖参考模板不得压过正式依据 |
| P3-7 | [x] | 国网规则网页噪声重洗 | `scripts/rag/repair_sgcc_rule_seed_docs.py`、`docs/rag/runs/run_20260607_sgcc_rule_clean_summary.md` | 三份异常国网规则资料已由门户首页噪声改为明确标注的检索种子摘要，`02_policy_regulations` 与 `04_standard_phrases` 已重入库；Base Recall@5 96.7%，泰昌专项 100% |
| P3-4 | [x] | Rerank 对比实验 | `backend/ai/rerank_client.py`、`backend/rag/retrieval.py`、`scripts/rag/eval_recall.py`、`docs/rag/runs/run_20260608_p3_rerank_summary.md` | 已完成无 rerank vs 在线 `qwen3-rerank` 对照；Base Recall@5/MRR 均为 96.7%/0.944，泰昌专项均为 100%/0.971；在线 rerank 无退化但平均耗时增加，先保持可控开关，不扩大默认候选 |
| P3-5 | [x] | 评测集扩到 40-60 条 | `tests/rag/customer_liaoning_taichang_testset.jsonl`、`docs/rag/runs/run_20260608_p3_hard_eval_summary.md` | Base 30 + 泰昌专项 30，合计 60 条；新增 13 条困难样本，覆盖相似报告、企业事实/招标要求/参考模板隔离、图片资产目录、合同/货物清单混淆和内部资料边界；在线 `qwen3-rerank` 将泰昌专项 Recall@5 从 96.7% 提升到 100%，MRR 从 0.950 提升到 0.983 |
| P3-6 | [x] | 增量回归门禁 | `scripts/rag/run_incremental_regression_gate.py`、`tests/test_incremental_regression_gate.py`、`docs/rag/runs/run_20260608_p3_incremental_gate_summary.md` | 已固化一键门禁脚本，自动跑 Base/泰昌专项的 `rerank off` 与 `qwen3-rerank` 四组真实召回评测；本轮 Gate PASS，Base qwen3 Recall@5 96.7%、泰昌专项 qwen3 Recall@5 100%、跨 doc_role 串扰 0%、禁用关键词命中 0% |

## P4：表格与结构化知识

目标：解决 `.xlsx`、技术参数表、货物清单、偏差表这类“向量文本化容易丢信息”的资料。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P4-1 | [x] | 表格三形态存储 | 原始结构 + 检索摘要 + 行级记录 | 货物清单已保留 JSON 原始结构、staging table summary/table row，并写入 `power_grid_goods_list_rows` 结构化行表 |
| P4-2 | [x] | 技术参数表抽取 | `scripts/rag/extract_customer_technical_parameters.py`、`technical_parameter_rows.json/csv`、`technical_parameter_summary.md`、`docs/rag/runs/run_20260607_p4_technical_parameters_summary.md` | 辽宁/泰昌 39 份 CPVC/MPP 技术规范已抽取 928 行参数，覆盖尺寸参数、性能指标、投标响应参数表；保留项目需求值、投标响应值、投标保证值、偏差、备注等字段 |
| P4-3 | [x] | 货物清单解析 | `scripts/rag/ingest_customer_goods_tables.py`、`scripts/rag/query_customer_goods_tables.py` | 江西 7 行、山西 98 行已可按包号、物料名称、单位、数量、技术规范编码、物料编码过滤 |
| P4-4 | [x] | 技术偏差/商务偏差辅助 | `scripts/rag/generate_technical_deviation_report.py`、`technical_deviation_rows.json/csv`、`technical_deviation_summary.md`、`docs/rag/runs/run_20260607_p4_deviation_summary.md` | 已基于 928 行技术参数生成偏差辅助判断，支持 `pending_response/no_deviation/positive_deviation/negative_deviation/manual_review/informational`；本批 900 行因投标响应/保证值为空被标为待响应，避免误写无偏差 |
| P4-5 | [x] | 泰昌产品/检验报告参数抽取 | `scripts/rag/extract_taichang_product_parameters.py`、`taichang_product_parameter_rows.json/csv`、`taichang_product_parameter_summary.md`、`docs/rag/runs/run_20260608_taichang_product_params_summary.md` | 已抽取 2 份泰昌检验报告、36 行企业事实参数；辽宁参数仅作 QA/异常校验参照，不自动形成泰昌覆盖辽宁全部规格的结论 |
| P4-6 | [x] | 泰昌产品参数真实查询接入 | `backend/rag/product_parameters.py`、`backend/api/knowledge.py`、`tests/test_taichang_product_parameter_query.py`、`docs/rag/runs/run_20260608_taichang_product_params_json_query_summary.md` | 已把 `taichang_product_parameter_rows.json` 作为 staging 查询层接入真实 API / 页面同源 stream 问答；MPP 环刚度、CPVC 平均内径/壁厚可返回具体值；辽宁边界仍正确 |
| P4-7 | [x] | 泰昌产品参数自动重抽取与真实链路回归 | `scripts/rag/run_taichang_product_parameter_refresh.py`、`tests/test_taichang_product_parameter_refresh.py`、`docs/rag/runs/run_20260608_taichang_product_parameter_refresh_summary.md` | 已固化客户新增泰昌产品/检验报告后的重抽取 SOP；一键完成结构化抽取、参数查询测试、增量回归门禁和真实页面同源 stream 抽样；本轮抽取 2 份检验报告、36 行参数，MPP 环刚度与 CPVC 平均内径/壁厚真实问答通过 |

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

1. 评估是否新增 `power_grid_technical_parameter_rows`、`power_grid_product_parameter_rows` 和 `power_grid_technical_deviation_rows` 数据库表，让页面和问答可直接按企业、产品、规格、参数名精确查询。
2. 仅在明确目标省公司/批次/规格和客户确认口径后，再把泰昌产品参数用于具体投标偏差判断；不得默认以辽宁样本推出泰昌覆盖义务。
3. P1B 泰昌补充资料质量增强已完成；后续新增资料按 `docs/rag/taichang-material-completeness-scorecard.md` 的 P0/P1/P2 补资料清单更新评分，并重跑真实回归。
4. 客户演示完整标书已完成 DeepSeek 全量章节重写和真实 DOCX/PDF 验收：见 `docs/development/runs/run_20260612_taichang_full_bid_final_v6.md`；后续若客户更换目标招标文件或 Word 模板，需重新生成章节、重新导出并复跑验收。

# 国家电网 RAG 基座数据工程待办清单

> 状态日期：2026-06-25
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
| P1B-9 | [x] | 标书编号、PDF 差异与待补充资料审计 | `backend/export/md_to_word.py`、`tests/test_docx_export.py`、`docs/rag/taichang-bid-information-gap-audit-20260612.md`、`docs/development/runs/run_20260612_taichang_bid_numbering_final.md`、`docs/rag/runs/run_20260612_taichang_bid_information_gap_audit_summary.md` | 数字列表改为保留章节原始序号，不再使用全文共享 Word 自动编号；客户参考稿正文主字号实测约 10.6pt，与当前 10.5pt 一致；正式链路重新导出 DOCX/PDF，原 360+ 连续编号已消失；完成 845 处占位审计并区分已提供、待结构化、客户确认和不适用四类；Base + 泰昌专项增量回归 Gate PASS |
| P1B-10 | [x] | 泰昌企业事实字段回填与不适用章节清理 | `scripts/rag/regenerate_taichang_fact_grounded_bid.py`、`docs/development/runs/run_20260612_taichang_fact_grounded_full_rewrite.md`、`docs/development/runs/run_20260612_taichang_fact_grounded_final.md`、`docs/rag/taichang-bid-remaining-placeholders-classification-20260612.md`、`docs/rag/runs/run_20260612_taichang_fact_grounded_full_rewrite_summary.md` | 已构建可追溯泰昌企业事实包，真实 DeepSeek 逐章重写 74/74 章节，旧正文备份完整；施工/水利/BIM/建造师等禁用主题命中 0；正式 DOCX/PDF 链路 PASS，74/74 章节有正文，图片 24/24 插入，表格 130 个，LibreOffice 字段刷新成功；649 处残留占位已逐项归类为 P0 436、P1 155、P2 58；专项真实 stream PASS，Base+泰昌专项增量回归 Gate PASS |
| P1B-11 | [~] | 投标前导确认页与变量回填产品化 | `docs/development/bid-prefill-guide-page-priority-20260614.md`、`docs/development/runs/run_20260614_editor_content_export_consistency.md` | 已确认前导页仍有必要，但定位为生成正文前的投标信息确认/变量收口页，不替代章节目录编辑和正文编辑；正文编辑导出一致性真实回归 PASS。下一步需完成变量 schema v1、变量回填引擎、招标文件/企业库自动预填和缺口报告 |

## P1C：云环境暂挂期间的泰昌本地试点质量收口

目标：阿里云测试环境账号暂未提供时，先处理本地真实环境可验证、且直接影响泰昌客户试用稳定性的任务。云上 ECS/RDS/OSS/Redis 联调继续列为外部条件阻塞，不占用当前 P0 执行序列。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P1C-1 | [x] | 泰昌 20260606 正式图片资产 embedding backfill | `scripts/rag/backfill_knowledge_asset_embeddings.py`、`docs/rag/runs/run_20260616_taichang_asset_embedding_backfill_asset_embedding_backfill.md`、`docs/rag/runs/run_20260616_taichang_asset_embedding_backfill_gate_summary.md` | 已使用本地 Ollama `qwen3-embedding:0.6b` 对 `customer_liaoning_taichang_20260606_p0_formal_full_page_assets_v1` 执行真实 backfill：选中 300、更新 300、失败 0，批次 missing embedding 从 300 降为 0；真实资产召回覆盖营业执照、MPP生产线、检测设备、CPVC/MPP检验报告、绿色低碳资料；真实 stream 抽样均返回 `done`；Base + 泰昌专项增量回归 Gate PASS |
| P1C-2 | [x] | 关键词兜底缓存失效机制 | `backend/rag/retrieval.py`、`backend/rag/ingestion.py`、`tests/test_rag_retrieval.py`、`docs/rag/runs/run_20260616_p1c2_keyword_cache_invalidation_summary.md`、`docs/rag/runs/run_20260616_p1c2_keyword_cache_invalidation_gate_summary.md` | 已实现 `document_chunks` 水位指纹（总数 + 最新 `created_at` + 最新 `id`）驱动的关键词兜底缓存自动重建，并在知识库入库删除旧分片/写入新分片后显式清理进程内缓存；真实 stream 先预热旧缓存，再插入带完整泰昌企业事实 metadata 的测试 chunk，不重启 Web 即命中新增口令并返回 `done`；`pytest tests/test_rag_retrieval.py` 16 passed；Base + 泰昌专项增量回归 Gate PASS |
| P1C-3 | [x] | RAG 本地门禁自动化入口 | `scripts/rag/run_local_rag_gate.py`、`tests/test_local_rag_gate.py`、`docs/rag/runs/run_20260616_p1c3_local_rag_gate_summary.md`、`docs/rag/runs/run_20260616_p1c3_local_rag_gate_incremental_summary.md` | 已固化本地一键 RAG 门禁：真实 `/api/ready`、RAG 相关单测、Base + 泰昌专项增量回归门禁、真实 `/api/knowledge/search/stream` 抽样；真实运行 `run_20260616_p1c3_local_rag_gate` PASS，stream 返回 contexts=5、assets=8、images=8、done=true；脚本输出 JSON/Markdown 汇总和失败步骤定位 |
| P1C-4 | [x] | 前导确认页变量 schema v1 与预填缺口报告 | `backend/services/bid_prefill.py`、`backend/api/prefill.py`、`frontend/src/pages/BidPrefill/index.tsx`、`tests/test_bid_prefill.py`、`docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_feature_summary.md` | 已完成旁路只读投标信息确认页与真实项目报告接口：schema v1 共 32 个字段，按“系统已识别/企业库带出/客户需填写/待人工确认”分组；真实项目接口返回客户需填写 10、待人工确认 10、正式必填缺口 15；不写入 `bid_sections`，不影响 `sectionsSnapshot` DOCX 导出契约；前端页面真实登录访问 PASS，Base + 泰昌专项增量回归 Gate PASS |
| P1C-5 | [x] | AI 深度解读后台任务化与进度轮询 | `backend/tasks/interpretation_tasks.py`、`backend/api/interpret.py`、`frontend/src/api/bidProject.ts`、`frontend/src/pages/Interpretation/index.tsx`、`frontend/src/components/workflow/BidWorkflow.tsx`、`migrations/postgres/008_bid_interpretation_tasks.sql`、`docs/development/runs/run_20260617_interpretation_async_task.md` | 已新增 `bid_interpretation_tasks`、Celery 任务 `bid.interpretation.generate_report` 和 `/ai-report-tasks` 创建/查询接口；前端上传工作流和招标解读页改为创建任务 + 轮询状态，显示分段/融合进度；真实 PostgreSQL 迁移 PASS，真实 API 缓存命中 PASS，真实 Redis/Celery worker 投递 PASS；`pytest` 定向 11 passed，`npm run build` PASS |
| P1C-6 | [x] | 前导确认页接入主流程与可编辑 UI | `frontend/src/components/workflow/BidWorkflow.tsx`、`frontend/src/pages/BidPrefill/index.tsx`、`frontend/src/components/layout/AppLayout.tsx`、`docs/development/runs/run_20260617_prefill_workflow_editable_ui.md` | 已从左侧一级菜单移除“投标确认”，并在自动流程中插入“投标信息确认”步骤：上传 → 解析 → 解读 → 分册大纲 → 投标确认 → 标书编制；前导页改为可编辑字段卡片，支持客户确认值本地草稿；真实页面回归确认左侧菜单无投标确认、流程含投标信息确认、33 个可编辑输入框、1440 宽无横向溢出；`pytest` 定向 10 passed，`npm run build` PASS |
| P1C-7 | [x] | 泰昌参考模板标书成品度收口 | `backend/ai/chapter_planner.py`、`backend/ai/section_writer.py`、`backend/services/bid_prefill.py`、`backend/services/taichang_bid_context.py`、`backend/services/section_generation.py`、`backend/api/routes.py`、`docs/development/runs/run_20260617_p1c7_taichang_reference_bid.md`、`docs/rag/runs/run_20260617_p1c7_taichang_reference_bid_summary.md` | 已完成前导确认应用、泰昌 fact pack 注入、重复占位归并和正式 readiness metadata；首轮使用 23 节兜底目录压住施工模板污染，但已在 P1C-8 改为客户参考稿 TOC 解析；正式 DOCX/PDF 链路 PASS，readiness 因 15 个客户/招标确认字段保持 `false`；后端 67 passed、前端 build PASS、RAG 本地门禁 PASS |
| P1C-8 | [x] | 客户参考模板目录解析修复 | `backend/ai/chapter_planner.py`、`tests/test_chapter_planner.py`、`docs/development/runs/run_20260617_p1c8_reference_outline_rebuild.md` | 已修复供货类大纲只用 23 节手写兜底结构的问题，改为读取 `haoqian_reference_templates.json` 的商务/技术参考稿 `toc_lines`，清洗点引导线、页码和目录噪声，并泛化河北豪乾供应商、专利、软件、历史业绩等具体事实；真实项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d` 目录从 23 节重建为 102 节，最大 4 级，豪乾具体事实标题命中 0，已有正文回填 14 个同名章节；`pytest tests/test_chapter_planner.py` 10 passed |
| P1C-9 | [x] | 正式导出门禁真实验收与回归 | `scripts/rag/verify_taichang_full_bid_acceptance.py`、`docs/development/runs/run_20260618_formal_export_gate_real_acceptance.md`、`docs/rag/runs/run_20260618_formal_export_gate_real_acceptance_summary.md` | 验收脚本已把 `formal_readiness.ready=false` 纳入失败项；真实项目可生成 DOCX/PDF，但因空叶子章节 63、正文占位符 26、正式必填缺口 17，验收结果按预期 FAIL；`pytest tests/test_bid_prefill.py tests/test_docx_export.py -q` 为 46 passed；本地 RAG 门禁 PASS |
| P1C-10 | [x] | 正式导出门禁正文与图片收口回归 | `scripts/rag/run_taichang_formal_export_gate_closure.py`、`backend/services/bid_prefill.py`、`backend/api/routes.py`、`docs/development/runs/run_20260618_p1c10_formal_gate_closure.md`、`docs/development/runs/run_20260618_p1c10_formal_gate_acceptance_final6.md`、`docs/rag/runs/run_20260618_p1c10_formal_gate_closure_summary.md` | 已在真实项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d` 自动应用可确认字段、生成剩余 88 个叶子章节并清理占位；最终正式导出链路生成 DOCX/PDF，102/102 章节有正文，空叶子章节 0，正文占位符 0，图片选中/插入/失败 23/23/0，补充包项目业绩/检测能力/检验报告资产检查通过，LibreOffice 字段刷新成功；正式 ready 仍为 false，仅因投标总价、保证金、交货期、质保期、授权代表、签署日期等 11 个客户决策字段未确认；`pytest tests/test_docx_export.py -q` 37 passed，本地 RAG 门禁 PASS |
| P1C-11 | [x] | 内部演示完整标书模拟确认值回归 | `scripts/rag/run_taichang_formal_export_gate_closure.py`、`docs/development/runs/run_20260619_p1c11_simulated_complete_bid.md`、`docs/development/runs/run_20260619_p1c11_simulated_complete_bid_acceptance.md`、`docs/rag/runs/run_20260619_p1c11_simulated_complete_bid_summary.md` | 在客户未回复前，为演示完整标书生成显式模拟确认值并写入 metadata：`simulated_for_regression=true`，模拟字段覆盖投标总价、税率、保证金、交货期、质保期、投标有效期、授权代表、身份证号、签署日期；真实导出验收 PASS，102/102 章节有正文，空叶子章节 0，正文占位符 0，正式必填缺口 0，图片选中/插入/失败 23/23/0，DOCX/PDF 生成并刷新字段；该版本仅可作为内部演示/回归测试，不代表正式投标承诺；`pytest tests/test_bid_prefill.py tests/test_docx_export.py -q` 46 passed，本地 RAG 门禁 PASS |
| P1C-12 | [x] | 企业库客户测试展示与人员证书归库修复 | `frontend/src/pages/QualificationBase/index.tsx`、`frontend/src/pages/ProductBase/index.tsx`、`frontend/src/pages/KnowledgeBase/KnowledgeSearchDrawer.tsx`、`frontend/src/utils/assetDisplay.ts`、`backend/api/assets.py`、`scripts/rag/repair_enterprise_asset_library_display.py`、`docs/rag/runs/run_20260621_enterprise_asset_display_repair_summary.md` | 客户反馈的人员证书误在产品库问题已修复：26 条人员相关资产归为企业资信库“人员证书”，其中 18 条从 `product_image` 迁为 `qualification_image`；企业资信库/产品库/知识库页面使用中文友好展示名，编辑弹窗展示当前图片/附件预览；前端 build、定向测试和本地 RAG 门禁 PASS。阿里云已执行同脚本，596 条资产扫描、18 条更新、18 条人员资产迁移，页面复测通过 |
| P1C-13 | [x] | 招标项目项目化上下文与解读页可用性回归 | `frontend/src/pages/Interpretation/index.tsx`、`frontend/src/pages/History/index.tsx`、`frontend/src/components/home/RecentTasks.tsx`、`tests/test_project_latest_interpretation.py`、`docs/rag/runs/run_20260621_interpretation_project_context_summary.md` | 招标项目页已明确默认展示“最近一次已完成解读”，显示项目 ID、创建时间、招标编号、招标文件名，并支持下拉切换历史项目；历史记录/首页操作区区分“查看解读”和“继续编制”；红框标签真实可用性已回归，当前项目要求 80、风险 60、评分 80、章节建议兼容旧字段为空并展示 253 条候选/章节；浏览器验证无横向溢出，前端 build、定向测试和本地 RAG 门禁 PASS |
| P1C-14 | [x] | 阿里云企业知识库问答事实与来源修复 | `docs/rag/runs/run_20260624_aliyun_enterprise_knowledge_qa_smoke.md`、`docs/rag/runs/run_20260624_p1c14_local_final_summary.md`、`docs/rag/runs/run_20260624_p1c14_local_final_three_question_stream_summary.md`、`docs/rag/runs/run_20260624_aliyun_online_rag_regression.md` | 本地真实环境已修复并通过；阿里云 formal 图片资产已重建且 embedding 补齐，三问主答案线上复测可用，二维码/局部裁剪图问题消失；人员/社保证明归库修复已在云上执行，Chrome 真实页面复测“泰昌社保证明”为“人员证书 · 资信库资料” |
| P1C-15 | [~] | 阿里云企业库展示与来源收敛收口 | `scripts/rag/repair_enterprise_asset_library_display.py`、`docs/rag/runs/run_20260624_aliyun_online_rag_regression.md` | 人员/社保证明云上归库已完成；剩余收口项是优化证书类参考来源混入 ESG/废水报告、CPVC 报告规格覆盖措辞冲突，以及公网 80 端口入口说明/反代 |

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
| P4-8 | [x] | 货物清单结构化联动前导页候选 | `backend/services/bid_prefill.py`、`tests/test_bid_prefill.py`、`docs/rag/runs/run_20260617_p4_structured_prefill_linkage_impl.md` | 前导页包号、包名称、物料类别、货物清单摘要已优先读取 `goods_rows.json` 行级记录；证据标记为招标要求且不可作为泰昌企业事实；定向测试 17 passed，本地 RAG 门禁 PASS |
| P4-9 | [x] | 技术参数表联动章节占位与偏差表候选 | `backend/services/bid_prefill.py`、`tests/test_bid_prefill.py`、`docs/rag/runs/run_20260618_p4_technical_parameter_linkage_impl.md` | 前导页新增技术参数表候选摘要、技术偏差表候选和泰昌参数佐证摘要；辽宁参数/偏差为招标要求且不可作为泰昌事实，泰昌检验报告仅作企业事实佐证；定向测试 18 passed，本地 RAG 门禁 PASS |
| P4-10 | [x] | 章节级候选展示与缺口清单 UI 收口 | `backend/services/bid_prefill.py`、`frontend/src/pages/BidPrefill/index.tsx`、`frontend/src/api/bidProject.ts`、`frontend/src/index.css`、`tests/test_bid_prefill.py`、`docs/rag/runs/run_20260618_p4_section_candidate_ui_impl.md` | 前导页新增 `sectionCandidates`，把货物清单、技术参数表、技术偏差表和泰昌参数佐证按真实章节归类展示；真实项目展示 22 个章节候选、25 个缺口，技术特性参数表、技术偏差表、报价文件及货物清单、产品制造与质量控制均可见；定向测试 8 passed，前端 build PASS，真实浏览器验证 PASS，本地 RAG 门禁 PASS |
| P4-11 | [x] | 章节候选确认值批量应用与导出前门禁 | `backend/services/bid_prefill.py`、`frontend/src/pages/BidPrefill/index.tsx`、`frontend/src/api/bidProject.ts`、`frontend/src/index.css`、`tests/test_bid_prefill.py`、`docs/rag/runs/run_20260618_p4_11_prefill_gate_apply_impl.md` | 页面新增导出前门禁和“采纳本章候选”按钮；后端应用结果新增 `export_gate` 与 `section_application_summary`；真实项目显示 22 个章节候选、10 个正式必填缺口、39 个正文占位符，仍明确阻断正式导出；定向测试 9 passed，前端 build PASS，真实浏览器验证 PASS，本地 RAG 门禁 PASS |

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

1. **P1C-1 已完成：泰昌 20260606 正式图片资产 embedding backfill。** 当前真实库 `knowledge_assets=597`，已有 embedding `597`，缺失 `0`。
2. **P1C-2 已完成：关键词兜底缓存失效机制。** 新增/重入库 `document_chunks` 后，关键词兜底缓存可自动识别水位变化并重建；真实 stream 已验证不重启 Web 命中新 chunk。
3. **P1C-3 已完成：RAG 本地门禁自动化入口。** 以后本地 RAG 改动优先执行 `set -a; source .env; set +a; .venv/bin/python scripts/rag/run_local_rag_gate.py --run-id <run>`。
4. **P1C-4 已完成：前导确认页变量 schema v1 与预填缺口报告。** 当前为旁路只读确认页，不替代章节正文编辑，不写入 `bid_sections`，不影响 `sectionsSnapshot` DOCX 导出契约。
5. **P1C-5 已完成：AI 深度解读后台任务化与进度轮询。** `ai-report-tasks` 创建任务后由 Celery worker 执行，前端轮询 `bid_interpretation_tasks` 状态，不再用长 HTTP 等待完整 DeepSeek 分段/merge。
6. **P1C-6 已完成：前导确认页接入主流程与可编辑 UI。** “投标确认”不再是一级菜单，而是生成分册大纲后、进入标书编制前的确认步骤；页面支持客户编辑确认值并避免表格溢出。
7. **P1C-7 已完成：前导确认应用与泰昌参考模板标书成品度收口。** 变量确认值可显式回填章节占位，泰昌 fact pack 已接入，报价、保证金、授权签章等客户决策字段仍不得自动补全。
8. **P1C-8 已完成：客户参考模板目录解析修复。** 供货类大纲不再只用 23 节兜底结构，已改为解析豪乾参考稿 TOC 并泛化参考稿企业事实；真实项目目录已重建为 102 节。
9. **P4-8 已完成：货物清单结构化联动前导页候选。** 包号、包名称、物料类别、货物清单摘要已从结构化行级记录带出候选，仍需客户确认后才应用到正文占位符。
10. **P4-9 已完成：技术参数表联动章节占位与偏差表候选。** 技术参数表、技术偏差表和泰昌检验报告参数已进入前导页候选层；仍需客户确认后才应用到正文占位符。
11. **P4-10 已完成：章节级候选展示与缺口清单 UI 收口。** 前导页已把 P4-8/P4-9 的结构化候选按章节归类展示，真实项目显示 22 个章节候选、25 个缺口；本轮不生成正文、不处理 PDF 字体或乱码。
12. **P4-11 已完成：章节候选确认值批量应用与导出前门禁。** 前导页支持按章节采纳候选到客户确认草稿，后端应用结果可返回章节级应用摘要和正式导出 gate；真实项目仍因 10 个正式必填缺口和 39 个正文占位符被正确阻断。
13. **P1C-9 已完成：正式导出门禁真实验收与回归。** 验收脚本已能正确阻断半成品：上一轮真实项目因空叶子章节 63、正文占位符 26、正式必填缺口 17 被判定 FAIL。
14. **P1C-10 已完成：正式导出门禁正文与图片收口回归。** 当前真实项目已收口为 102/102 章节有正文、空叶子章节 0、正文占位符 0、图片成品检查通过；正式 ready 仍因 11 个客户决策字段保持 `false`，这些字段不得自动编造。
15. **P1C-11 已完成：内部演示完整标书模拟确认值回归。** 客户未回复前，已用明确标记的模拟确认值生成完整标书演示版；真实 DOCX/PDF 验收 PASS，`missing_required=0`。该版本只用于内部演示/回归测试，不得作为正式投标承诺。
16. **P1C-12 已完成：企业库客户测试展示与人员证书归库修复。** 26 条人员相关资产已归到企业资信库“人员证书”，产品库不再残留人员证书；页面展示名和编辑预览已优化。阿里云已执行 `scripts/rag/repair_enterprise_asset_library_display.py --execute`，596 条资产扫描、18 条更新、18 条人员资产迁移。
17. **P1C-13 已完成：招标项目项目化上下文与解读页可用性回归。** 招标项目页不再让客户猜测当前是哪次解析；默认入口标注为“最近一次已完成解读”，并提供历史项目下拉、查看全部历史和进入标书编制入口；红框标签已按真实接口和当前项目数据回归。
18. **P1C-14 已完成：企业知识库问答事实与来源修复。** 阿里云 `:8080` 真实页面三问主答案可用，formal 图片资产和 embedding 已恢复，二维码/局部裁剪图问题消失；社保证明归库 P0 已修复，页面复测显示为“人员证书 · 资信库资料”。
19. **P1C-15 进行中：阿里云企业库展示与来源收敛收口。** 剩余优化资质证书问题参考来源混入 ESG/废水报告、CPVC 报告规格覆盖措辞冲突，以及公网 80 端口入口说明/反代；P0 关闭后可并行进入最小标书主流程云上冒烟。
20. **SG-PROMPT-001 已完成：Prompt profile 分级瘦身与生成输入预算。** 章节生成已按 profile 控制 RAG/企业资料/事实包/prompt 字符预算，并把 profile 指标写入生成任务 metadata；本地 RAG 门禁 `run_20260625_sg_prompt_001` PASS，完整 DOCX 导出链路 PASS。
21. 评估是否新增 `power_grid_technical_parameter_rows`、`power_grid_product_parameter_rows` 和 `power_grid_technical_deviation_rows` 数据库表；仅在参数规模变大、多批次查询复杂或页面精确查询成为瓶颈后启动。
22. P1B 泰昌补充资料质量增强已完成；后续新增资料按 `docs/rag/taichang-material-completeness-scorecard.md` 的 P0/P1/P2 补资料清单更新评分，并重跑真实回归。
23. 客户演示完整标书已完成 DeepSeek 全量章节重写和真实 DOCX/PDF 验收：见 `docs/development/runs/run_20260612_taichang_full_bid_final_v6.md`；后续若客户更换目标招标文件或 Word 模板，需重新生成章节、重新导出并复跑验收。

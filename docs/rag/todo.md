# 国家电网 RAG 基座数据工程待办清单

> 状态日期：2026-06-02
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
| [x] | 父子双层分块 v2 | `backend/rag/chunking.py` | dry-run 产出 298 parent / 2449 child |
| [x] | 电网种子库 v2 入库脚本 | `scripts/rag/ingest_power_grid_v2.py` | 支持 `--dry-run`、按 `doc_role` 分块、仅 child embedding |
| [x] | metadata 过滤 RPC 与 HNSW | `migrations/postgres/006_rag_p0_filtered_recall.sql` | 支持 `match_knowledge_chunks_filtered`、`get_parent_chunk` |
| [x] | Base 测试集与基线记录 | `tests/rag/base_testset.jsonl`、`docs/rag/evaluation-records.md` | 30 条用例，Recall@5 86.7%，串扰 0% |
| [x] | 主检索接入 filtered RPC | `backend/rag/retrieval.py`、`backend/api/knowledge.py` | 单测确认不再默认调用老 `match_knowledge_chunks` |
| [x] | 写作场景父块回溯 | `backend/rag/retrieval.py`、`backend/ai/chapter_planner.py` | writing 场景 child 命中后可返回 parent |
| [x] | 核心文档改为 v2 链路 | `docs/features/rag-knowledge-base.md`、`rag_seed/power_grid_resources/README.md` | 当前操作指南不再指向旧入库脚本 |
| [~] | 旧部署/历史文档标注迁移参考 | `docs/deployment/*` | 旧脚本引用必须标注“历史/迁移参考”，避免新成员误用 |

## P1：客户江西/山西标书模板入库

目标：把客户真实资料纳入 RAG 样本和评测，不再只依赖公开种子库。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P1-1 | [x] | 梳理江西/山西压缩包文件清单 | `docs/rag/customer-corpus-inventory.md` | 按省份、批次、包号、文件类型、是否铁构件/接地铁相关标注 |
| P1-2 | [ ] | 解析 `.docx` 主招标文件 | `parsed_outputs/`、入库 manifest | 标题层级、条款、资格要求、评分办法可抽取 |
| P1-3 | [ ] | 解析 `.doc` 老二进制文件 | 转换后的 `.docx/.md` 与解析报告 | LibreOffice/MinerU 至少一种路径可稳定处理，失败标 `needs_review` |
| P1-4 | [ ] | 解析 `.xlsx` 货物清单/技术参数表 | 结构化 JSON/CSV、表格摘要 chunk | 保留 sheet、表头、行列、合并单元格语义和包号 |
| P1-5 | [ ] | 客户资料 metadata 规范化 | 入库 manifest | 至少包含 `province/batch_no/package_no/material_category/doc_role/source_file` |
| P1-6 | [~] | 江西/山西批次负样本 | `tests/rag/base_testset.jsonl` 或独立扩展集 | 已新增场景测试集；待客户资料入库后补跨省/跨批次负样本 |
| P1-7 | [~] | 铁构件/接地铁首批真实用例 | 测试集 15-20 条 | 已建立铁构件/接地铁 inventory；待解析入库后补真实用例 |
| P1-8 | [ ] | 入库后回归评测 | `docs/rag/evaluation-records.md` 新 run | Recall@5 不低于当前基线，跨批次串扰可解释且受控 |

## P2：持续客户模板治理

目标：客户后续持续提供模板时，形成稳定收口机制，而不是每次临时处理。

| 优先级 | 状态 | 任务 | 交付物 | 验收口径 |
| --- | --- | --- | --- | --- |
| P2-1 | [ ] | 客户资料入库 SOP | `docs/rag/customer-template-ingestion-sop.md` | 从收件、解压、杀毒/脱敏、解析、入库、评测到归档全流程可执行 |
| P2-2 | [ ] | 每批资料 manifest 规范 | `manifest.json` 模板 | 每个文件都有来源、批次、角色、解析状态、质量评分 |
| P2-3 | [ ] | 解析质量报告模板 | `docs/rag/parse-quality-report-template.md` | 能标记空文本、乱码、表格丢失、页码缺失、扫描件 |
| P2-4 | [ ] | 版本与去重策略 | `content_sha256`、`doc_version`、`superseded_by` | 同一模板新旧版本不会同时污染召回 |
| P2-5 | [ ] | 模板可引用边界 | `citation_policy` 规则 | 区分客户模板、公开法规、企业话术，避免把模板当强制条款 |
| P2-6 | [ ] | 批次回滚机制 | 入库批次记录与删除脚本 | 某批资料质量差时可按批次撤回 |

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
| P4-1 | [ ] | 表格三形态存储 | 原始结构 + 检索摘要 + 行级记录 | 技术参数可按物料/字段精确查询 |
| P4-2 | [ ] | 技术参数表抽取 | JSON/CSV + summary chunk | 保证值、项目需求值、备注字段不丢失 |
| P4-3 | [ ] | 货物清单解析 | 行级结构化数据 | 包号、物料名称、单位、数量可过滤 |
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

1. 建立江西/山西客户资料 inventory。
2. 选择铁构件/接地铁作为首个真实物料场景。
3. 跑 `.doc/.docx/.xlsx` 解析样例，确认 MinerU/LibreOffice/openpyxl 的组合路径。
4. 补 15-20 条客户真实场景测试集，含跨省/跨批次负样本。
5. 入库后追加 Run 2 评测记录。

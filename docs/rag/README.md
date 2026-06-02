# 国网招投标 RAG 工程文档

本目录沉淀 RAG 基座数据工程的实现记录，便于团队复用、回归与对外技术分享。

## 文档索引

| 文档 | 说明 |
| --- | --- |
| [chunking-strategy.md](chunking-strategy.md) | 父子双层分块策略与按文件类型的切分规则（实现依据） |
| [water-data-cleanup.md](water-data-cleanup.md) | 水利历史数据清理记录（范围、备份、执行、校验） |
| [base-testset.md](base-testset.md) | Base 测试集设计、标注规范与用例清单 |
| [evaluation-records.md](evaluation-records.md) | 召回评测记录（基线 / 各次迭代对比） |
| [todo.md](todo.md) | RAG 基座数据工程待办清单、优先级与完成度跟踪 |
| [customer-corpus-inventory.md](customer-corpus-inventory.md) | 江西/山西客户真实标书资料清单与入库优先级 |
| [customer-corpus-parse-runs.md](customer-corpus-parse-runs.md) | 客户真实资料每批解析准备记录、manifest 与质量报告 |
| [customer-parse-qa-checklist.md](customer-parse-qa-checklist.md) | 客户资料解析 QA 门禁、测试集与本批结果 |
| [runs/](runs/) | 每次召回评测的原始 JSON 与摘要 |

## 相关代码

| 路径 | 作用 |
| --- | --- |
| `backend/rag/chunking.py` | 父子分块器（按 doc_role 路由） |
| `scripts/rag/ingest_power_grid_v2.py` | 电网种子库 v2 入库脚本（父子分块 + metadata） |
| `scripts/rag/prepare_customer_corpus.py` | 客户江西/山西标书资料入库前解析准备脚本（manifest + 质量报告） |
| `scripts/rag/dry_run_customer_chunks.py` | 基于客户资料 manifest 跑父子分块 dry-run，输出 parent/child/table 统计 |
| `scripts/rag/eval_parse_quality.py` | 基于解析产物和 QA 用例检查关键证据是否保留 |
| `scripts/rag/ingest_customer_corpus.py` | 基于客户 manifest 做 staging 入库，按 `ingestion_batch_id` 隔离 |
| `scripts/rag/ingest_customer_goods_tables.py` | 将客户 `.xlsx` 货物清单写入结构化行表 `power_grid_goods_list_rows` |
| `scripts/rag/query_customer_goods_tables.py` | 按批次、省份、包号、关键词查询结构化货物清单 |
| `scripts/rag/rollback_customer_corpus.py` | 按 `ingestion_batch_id` dry-run 或执行删除客户批次数据 |
| `scripts/rag/cleanup_water_data.py` | 水利数据清理脚本（带备份） |
| `scripts/rag/eval_recall.py` | Base 测试集召回评测脚本 |
| `tests/rag/base_testset.jsonl` | Base 测试集（JSONL 标注） |
| `tests/rag/scenario_testset.jsonl` | 场景化测试集（qa / writing_parent / compliance / table） |
| `tests/rag/customer_parse_qa_cases.jsonl` | 客户资料解析 QA 用例 |
| `tests/rag/customer_jx_sx_testset.jsonl` | 江西/山西客户资料召回评测用例 |
| `migrations/postgres/007_power_grid_goods_list_rows.sql` | 货物清单结构化行表和索引 |

## 战略文档

技术路线与方案评审见 `feishu/docs/国家电网物资协议库存标书RAG技术路线评审稿.md`。本目录是该方案的**落地实现记录**。

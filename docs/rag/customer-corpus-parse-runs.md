# 客户标书资料解析批次记录

> 用途：记录客户新增资料在正式 RAG 入库前的解析准备结果，包括 manifest、解析质量报告、文本/表格产物和需复核项。

## Run 1 — 江西/山西铁构件资料解析准备（2026-06-02）

| 项 | 值 |
| --- | --- |
| 批次 ID | `customer_jx_sx_20260602_p1` |
| 源目录 | `rag_seed/power_grid_resources/01_tender_documents/20_国网江西电力2026年第一次配网省网协议库存物资类公开招标采购/` |
| 源目录 | `rag_seed/power_grid_resources/01_tender_documents/21_国网山西电力2026年第二次物资协议库存公开招标采购/` |
| Manifest | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/manifest.json` |
| 质量报告 | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/parse_quality_report.md` |
| 分块 dry-run | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/chunk_dry_run_report.md` |
| 解析 QA | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/parse_qa_report.md` |
| staging 入库 | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/ingest_customer_corpus_report.md` |
| 召回评测 | `docs/rag/runs/run_20260602_customer_jx_sx_summary.md` |
| 解析脚本 | `scripts/rag/prepare_customer_corpus.py` |
| 分块脚本 | `scripts/rag/dry_run_customer_chunks.py` |
| QA 脚本 | `scripts/rag/eval_parse_quality.py` |
| 入库脚本 | `scripts/rag/ingest_customer_corpus.py` |

### 结果摘要

| 指标 | 数量 |
| --- | ---: |
| 文件总数 | 44 |
| 已解析 `.doc/.docx/.xlsx` | 23 |
| 仅归档 `.zip/.rar/.sign/.zb` | 21 |
| 需复核 | 0 |
| 文本字符数 | 650301 |
| 表格行数 | 107 |

### 分块 dry-run

| 指标 | 数量 |
| --- | ---: |
| 文本可分块文档 | 21 |
| 表格可结构化文档 | 2 |
| 需复核 | 0 |
| parent chunk | 233 |
| child chunk | 3942 |
| 表格 sheet | 2 |
| 表格行 | 107 |

### 解析 QA

| 指标 | 数量 |
| --- | ---: |
| QA 用例 | 12 |
| 命中 | 12 |
| 命中率 | 100.0% |
| 无候选文件 | 0 |

### staging 入库

| 指标 | 数量 |
| --- | ---: |
| `knowledge_documents` | 23 |
| `document_chunks` | 4284 |
| parent chunk | 235 |
| child/table 检索块 | 4049 |
| embedding | 4049 |

### 召回评测

| 指标 | 过滤 ON | 过滤 OFF |
| --- | ---: | ---: |
| Recall@5 | 100.0% | 76.5% |
| 来源类别准确率(top1) | 100.0% | 64.7% |
| 跨 doc_role 串扰均值 | 0.0% | 49.4% |

### 按角色统计

| doc_role | 数量 | 说明 |
| --- | ---: | --- |
| `archive_only` | 21 | 原始包、签名文件、平台文件，仅归档 |
| `technical_spec` | 9 | 江西铁附件、山西接地铁/铁构件/电缆支架技术规范 |
| `contract_general_terms` | 2 | 10kV 及以下协议库存合同通用条款 |
| `contract_special_terms` | 4 | 合同模板与专用条款 |
| `bid_instructions` | 1 | 江西投标注意事项 V3 |
| `tender_notice` | 3 | 江西资格预审/后审公告、山西公告 |
| `goods_list` | 2 | 江西 `1826AA`、山西 `0526AB` 货物清单 |
| `main_tender_file` | 2 | 江西 V2 招标文件、山西招标文件 |

### 解析链路

| 文件类型 | 解析器 | 本次结果 |
| --- | --- | --- |
| `.docx` | `mammoth` + `python-docx` 统计段落/表格/标题 | 成功 |
| `.doc` | LibreOffice 转 `.docx` 后 `mammoth` 抽取 | 成功，产出 `converted_docx/` |
| `.xlsx` | `openpyxl` 结构化解析 | 成功，产出 `tables/*.json` |
| `.zip/.rar/.sign/.zb` | `archive_only` | 不入 RAG，仅进 manifest 追溯 |

### 入库前结论

- 本批 23 个可解析文件已经完成父子分块 dry-run，长文档已按多个 parent 拆分，具备开发正式客户资料入库脚本的基础。
- `.xlsx` 货物清单已经保留 sheet、行列、合并单元格和检索摘要，不应压成长文本直接向量化。
- 当前 `needs_review=0`，但 Mammoth 对部分 Word 版式元素有 warning，正式入库前仍建议抽样检查主招标文件、公告和合同表格是否有关键字段丢失。
- 本批已完成 staging 入库和客户召回评测；上线前仍需补批次回滚脚本、结构化表查询和写作 parent 人工抽查。

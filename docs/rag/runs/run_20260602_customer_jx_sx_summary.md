# Run 4 — 江西/山西客户资料 staging 入库与召回评测（2026-06-02）

## 触发原因

客户江西、山西铁构件/接地铁样本资料已完成本地解析 QA，需要验证：

- 本地解析产物是否能支撑 RAG；
- staging 入库后客户真实问题是否能准确召回；
- metadata 过滤是否能控制省份、包号、doc_role 串扰；
- 新增客户资料是否影响原 Base 基线。

## 数据与入库

| 项 | 值 |
| --- | ---: |
| 批次 ID | `customer_jx_sx_20260602_p1` |
| `knowledge_documents` | 23 |
| `document_chunks` | 4238 |
| parent chunk | 223 |
| child/table 检索块 | 4015 |
| embedding | 4015 |
| 结构化货物清单行 | 105 |
| 归档文件 | 21 |

入库报告：

- `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/ingest_customer_corpus_report.md`

## 解析 QA

| 指标 | 结果 |
| --- | ---: |
| QA 用例 | 12 |
| 命中 | 12 |
| 命中率 | 100.0% |
| 无候选文件 | 0 |

解析 QA 报告：

- `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/parse_qa_report.md`

## 客户召回 A/B

测试集：`tests/rag/customer_jx_sx_testset.jsonl`（17 条）

| 指标 | 过滤 ON | 过滤 OFF | 差值 |
| --- | ---: | ---: | ---: |
| Recall@5 | **100.0%** | 70.6% | +29.4pp |
| 来源类别准确率(top1) | **100.0%** | 58.8% | +41.2pp |
| 关键词命中率 | **100.0%** | 88.2% | +11.8pp |
| 跨 doc_role 串扰均值 | **0.0%** | 50.9% | -50.9pp |
| 禁用关键词命中率 | **0.0%** | 0.0% | 0.0pp |

分场景 Recall@5：

| scenario | 过滤 ON | 过滤 OFF |
| --- | ---: | ---: |
| qa | 100% | 43% |
| compliance | 100% | 100% |
| writing | 100% | 67% |
| table | 100% | 100% |

分指标 Recall@5：

| metric | 过滤 ON | 过滤 OFF |
| --- | ---: | ---: |
| `customer_qa_recall` | 100% | 25% |
| `technical_spec_recall` | 100% | 67% |
| `customer_compliance_recall` | 100% | 100% |
| `customer_writing_parent_coverage` | 100% | 67% |
| `customer_table_recall` | 100% | 100% |

原始结果：

- `docs/rag/runs/run_20260602_customer_jx_sx_filtered.json`
- `docs/rag/runs/run_20260602_customer_jx_sx_nofilter.json`

## Base 回归

新增客户资料后复跑原 Base filtered：

| 指标 | 结果 |
| --- | ---: |
| Recall@5 | 86.7% |
| 来源类别准确率(top1) | 100.0% |
| 关键词命中率 | 86.7% |
| 跨 doc_role 串扰均值 | 0.0% |

结果与入库前基线一致，新增客户资料没有造成原公开种子库 filtered 召回退化。

原始结果：

- `docs/rag/runs/run_20260602_post_customer_base_filtered.json`

## 结论

1. 本地解析链路在本批客户样本上通过 QA，暂不需要强制切到 MinerU。
2. 客户 staging 入库可用，过滤 ON 时客户测试集 Recall@5 达到 100%。
3. metadata 过滤是必要门禁；过滤 OFF 后 Recall@5 降至 70.6%，跨 doc_role 串扰升至 50.9%。
4. 表格召回在本轮测试集中表现稳定；本批已补 `power_grid_goods_list_rows` 结构化表，可按包号、物料、技术规范编码、物料编码等字段精确查询。
5. 写作场景在测试集上通过 parent 回溯；本轮 spot-check 后已修复标题-only parent 噪声，刷新后本批 chunk 数从 4284 降为 4238。

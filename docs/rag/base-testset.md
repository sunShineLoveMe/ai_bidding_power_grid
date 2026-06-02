# Base 测试集设计

> 数据：`tests/rag/base_testset.jsonl`、`tests/rag/scenario_testset.jsonl`、`tests/rag/customer_jx_sx_testset.jsonl`
> 评测：`scripts/rag/eval_recall.py`
> 方案依据：`feishu/docs/国家电网物资协议库存标书RAG技术路线评审稿.md` §12

## 1. 作用

- 客观衡量召回质量（不是“能入库”，而是“能否准确召回”）。
- 作为持续增量入库的**回归基线**：新批次资料入库后重跑，指标退化则阻断上线。
- 量化对比有/无 metadata 过滤、有/无 Rerank、不同分块策略的收益。

## 2. 规模与分布（第一版）

第一版 30 条，覆盖当前 power_grid 种子库已入库内容（铁构件标书原件尚为 .docx/.doc/.xlsx，待 P1 解析后纳入）。

| scenario | 条数 | 验证目标 |
| --- | ---: | --- |
| qa | 15 | 条文/段落级精确召回 |
| writing | 11 | 标准/话术/技术响应覆盖 |
| compliance | 4 | 否决项/资格/不良行为召回 |

补充场景化测试集 `tests/rag/scenario_testset.jsonl` 12 条，用于单独跟踪项目关键能力：

| metric | 条数 | 验证目标 |
| --- | ---: | --- |
| `qa_recall` | 3 | 知识库问答召回 |
| `writing_parent_coverage` | 3 | 写作场景 child 命中后 parent 回溯覆盖 |
| `compliance_recall` | 3 | 合规/否决项召回 |
| `table_recall` | 3 | 标准目录/表格类资料基础召回 |

客户江西/山西测试集 `tests/rag/customer_jx_sx_testset.jsonl` 17 条，用于跟踪真实客户资料 staging 入库后的召回质量：

| metric | 条数 | 验证目标 |
| --- | ---: | --- |
| `customer_qa_recall` | 4 | 江西/山西主招标文件、公告的问答召回 |
| `technical_spec_recall` | 3 | 铁构件、接地铁、不锈钢电缆支架技术规范召回 |
| `customer_compliance_recall` | 3 | 否决项、报价一致性、实质性响应要求召回 |
| `customer_writing_parent_coverage` | 3 | 写作场景 child 命中后 parent 回溯覆盖 |
| `customer_table_recall` | 4 | 江西 `1826AA`、山西 `0526AB` 货物清单行级召回 |

## 3. 标注格式（JSONL）

```json
{
  "id": "T01",
  "scenario": "qa",
  "metric": "qa_recall",
  "question": "招标投标法规定哪些工程建设项目必须进行招标？",
  "metadata_filter": {"doc_role": "policy_regulation"},
  "return_parent": false,
  "must_include_keywords": ["必须进行招标", "工程建设项目"],
  "expected_doc_role": "policy_regulation"
}
```

字段说明：

- `scenario`：qa / writing / compliance，用于分场景统计。
- `metric`：可选；用于更细指标分组，如 `qa_recall`、`writing_parent_coverage`、`compliance_recall`、`table_recall`。
- `metadata_filter`：召回时下发给 `match_knowledge_chunks_filtered` 的 jsonb 过滤条件。
- `return_parent`：可选；为 `true` 时，评测脚本会用 child 命中的 `parent_index` 回溯 parent，并在 parent 内容上做关键词/role 判定，服务写作场景。
- `must_include_keywords`：命中判定关键词（任一出现即算关键词命中）。
- `must_not_include_keywords`：禁用关键词，任一出现在 top-k 即判定该用例未通过，用于跨省/跨包串扰检查。
- `expected_doc_role`：期望来源类别，用于来源准确率与串扰统计。

## 4. 指标定义

| 指标 | 含义 |
| --- | --- |
| `Recall@k` | top-k 中存在“doc_role 正确且含关键词”的片段 |
| 来源类别准确率(top1) | top-1 的 doc_role == 期望 doc_role |
| 关键词命中率 | top-k 任一片段含关键词 |
| 跨 doc_role 串扰均值 | top-k 中非期望 doc_role 的平均占比（越低越好） |

## 5. 后续扩展（待 P1 客户标书解析后）

- 加入江西/山西铁构件标书的真实用例（技术参数保证值、合同专用条款、货物清单结构化查询）。
- **加入跨批次负样本**：问山西 0526AB，断言结果中不得出现江西 1826AA（`must_not_include`），单独统计批次串扰率。
- 扩到 40~50 条，覆盖评审稿 §12.1 的 7 个类别。

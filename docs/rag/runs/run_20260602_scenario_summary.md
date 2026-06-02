# Run 3 场景化召回评测摘要

> 运行时间：2026-06-02 15:46 CST
> 测试集：`tests/rag/scenario_testset.jsonl`（12 条）
> 脚本：`scripts/rag/eval_recall.py --testset tests/rag/scenario_testset.jsonl`
> 原始结果：
> - `docs/rag/runs/run_20260602_scenario_filtered.json`
> - `docs/rag/runs/run_20260602_scenario_nofilter.json`

## 目的

在原 Base 测试集之外，单独跟踪四类项目关键指标：

- `qa_recall`：知识库问答召回；
- `writing_parent_coverage`：写作场景 child 命中后 parent 回溯覆盖；
- `compliance_recall`：合规/否决项召回；
- `table_recall`：标准目录/表格类资料的基础召回。

## A/B 结果

| 指标 | 过滤 ON | 过滤 OFF | 差值 |
| --- | ---: | ---: | ---: |
| Recall@5 | 100.0% | 75.0% | +25.0pp |
| 来源类别准确率(top1) | 100.0% | 83.3% | +16.7pp |
| 关键词命中率 | 100.0% | 75.0% | +25.0pp |
| 跨 doc_role 串扰均值 | 0.0% | 41.7% | -41.7pp |

## 分指标 Recall@5

| metric | 过滤 ON | 过滤 OFF |
| --- | ---: | ---: |
| `qa_recall` | 100% | 67% |
| `writing_parent_coverage` | 100% | 67% |
| `compliance_recall` | 100% | 67% |
| `table_recall` | 100% | 100% |

## 结论

新增场景测试集验证了 metadata 过滤对真实使用场景的重要性：关闭过滤后，问答、合规和写作父块覆盖均出现明显退化，并产生跨 `doc_role` 串扰。写作父块回溯当前在样例集上可用，但样本量仍少，后续必须加入江西/山西客户真实标书和 `.xlsx` 表格样本。

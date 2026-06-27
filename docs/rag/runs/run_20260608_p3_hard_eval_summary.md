# Run 20260608 — P3-5 困难样本评测集扩展与真实链路回归

## 背景

P3-4 已证明在线 `qwen3-rerank` 可用，但原有 47 条评测样本不够难，无法充分判断 rerank 是否值得默认强化。本轮把评测集扩展到 60 条，并加入更容易误引、串资料域或混淆相似来源的困难样本。

## 评测集变更

- Base 测试集：30 条，保持不变。
- 泰昌 MVP 专项测试集：从 17 条扩展到 30 条。
- 新增 13 条困难样本，覆盖：
  - 泰昌营业执照 vs 河北豪乾参考稿/辽宁资格要求；
  - 泰昌 CPVC vs MPP 相似检验报告；
  - 辽宁货物清单/技术规范 vs 泰昌检验报告/生产线资料；
  - 河北豪乾参考模板只作格式参考，不得作为泰昌事实或保证值；
  - 泰昌生产制造能力、试验检测能力、绿色低碳资料相似资产目录；
  - 合同条款 vs 货物清单/企业资料混淆；
  - 泰昌内部资料跨企业展示边界。

## 真实链路命令

```bash
set -a; source .env; set +a; .venv/bin/python scripts/rag/eval_recall.py --k 5 --rerank off --save docs/rag/runs/run_20260608_p3_hard_base_off.json
set -a; source .env; set +a; .venv/bin/python scripts/rag/eval_recall.py --k 5 --rerank on --rerank-model qwen3-rerank --save docs/rag/runs/run_20260608_p3_hard_base_qwen3.json
set -a; source .env; set +a; .venv/bin/python scripts/rag/eval_recall.py --k 5 --testset tests/rag/customer_liaoning_taichang_testset.jsonl --rerank off --save docs/rag/runs/run_20260608_p3_hard_customer_off.json
set -a; source .env; set +a; .venv/bin/python scripts/rag/eval_recall.py --k 5 --testset tests/rag/customer_liaoning_taichang_testset.jsonl --rerank on --rerank-model qwen3-rerank --save docs/rag/runs/run_20260608_p3_hard_customer_qwen3.json
```

## 评测结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base 30 | off | 96.7% | 100.0% | 0.944 | 0.0% | 375 ms | 0/30 |
| Base 30 | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 741 ms | 28/30 |
| 泰昌专项 30 | off | 96.7% | 100.0% | 0.950 | 3.3% | 451 ms | 0/30 |
| 泰昌专项 30 | qwen3-rerank | 100.0% | 100.0% | 0.983 | 0.0% | 756 ms | 30/30 |

## 页面同源真实 stream 抽样

结果文件：`docs/rag/runs/run_20260608_p3_hard_real_stream.json`

- 泰昌 CPVC 检验报告 vs MPP 参数混淆样本：通过，5 条上下文，无错误可见来源。
- 泰昌生产制造能力 vs 河北豪乾/辽宁招标混淆样本：通过，5 条上下文，无错误可见来源。

## 结论

- 扩展后的困难集让 rerank 的收益显现：泰昌专项 Recall@5 从 96.7% 提升到 100%，MRR 从 0.950 提升到 0.983，禁用关键词命中率从 3.3% 降到 0。
- Base 测试集仍无退化，说明在线 rerank 没有破坏法规/标准/通用话术基础召回。
- 代价是平均耗时增加约 300 ms/case。建议下一步 P3-6 把这套评测变成增量门禁，并在真实问答默认策略上保持可控开关；如果后续新增资料导致相似资料混淆增多，可优先对企业知识库问答和困难 query 打开 `qwen3-rerank`。

## 回归验证

- `.venv/bin/python -m pytest tests/test_rerank_client.py tests/test_rag_retrieval.py tests/test_rag_display_names.py tests/test_taichang_product_parameter_query.py -q`
- 结果：21 passed，1 个 PyPDF2 deprecation warning。
- `py_compile`：通过。

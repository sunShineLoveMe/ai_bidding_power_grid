# Run 20260608 — P3-4 在线 Rerank 对比实验

## 背景

用户确认在线 rerank 可用。本轮验证 `qwen3-rerank` 是否应在企业知识库问答链路中默认使用，并补齐可复跑的 A/B 评测能力。

## 实现内容

- `backend/ai/rerank_client.py`：支持显式 `enabled` 和 `model` 覆盖，便于实验强制关闭或指定 `qwen3-rerank`，不受运行时配置文件干扰。
- `backend/rag/retrieval.py`：`search_knowledge_base` 支持 `rerank_enabled`、`rerank_model` 参数，默认行为保持兼容。
- `scripts/rag/eval_recall.py`：新增 `--rerank default|off|on`、`--rerank-model`、MRR、平均耗时、`rerank_scored_cases` 指标。
- `tests/test_rerank_client.py`：新增强制关闭 rerank、显式模型覆盖的单测。

## 实验命令

```bash
set -a; source .env; set +a; .venv/bin/python scripts/rag/eval_recall.py --k 5 --rerank off --save docs/rag/runs/run_20260608_p3_rerank_base_off.json
set -a; source .env; set +a; .venv/bin/python scripts/rag/eval_recall.py --k 5 --rerank on --rerank-model qwen3-rerank --save docs/rag/runs/run_20260608_p3_rerank_base_qwen3.json
set -a; source .env; set +a; .venv/bin/python scripts/rag/eval_recall.py --k 5 --testset tests/rag/customer_liaoning_taichang_testset.jsonl --rerank off --save docs/rag/runs/run_20260608_p3_rerank_customer_off.json
set -a; source .env; set +a; .venv/bin/python scripts/rag/eval_recall.py --k 5 --testset tests/rag/customer_liaoning_taichang_testset.jsonl --rerank on --rerank-model qwen3-rerank --save docs/rag/runs/run_20260608_p3_rerank_customer_qwen3.json
```

## 对比结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 396 ms | 0/30 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 781 ms | 28/30 |
| 泰昌 MVP 专项 | off | 100.0% | 100.0% | 0.971 | 689 ms | 0/17 |
| 泰昌 MVP 专项 | qwen3-rerank | 100.0% | 100.0% | 0.971 | 1000 ms | 17/17 |

## 结论

- 在线 `qwen3-rerank` 可用，且没有造成 Recall、Top1 来源准确率、MRR 或跨域隔离退化。
- 当前评测集已经被 metadata 过滤、关键词补召回和规则排序处理得较稳，`qwen3-rerank` 在现有 47 条用例上没有带来可见指标提升。
- 在线 rerank 的平均耗时明显增加：Base 约 +385 ms/case，泰昌专项约 +311 ms/case。
- 建议保持 rerank 为可控开关；暂不扩大召回候选数或强依赖 rerank。下一步应扩展 P3-5 评测集，加入更多“相似但不应引用”的困难样本，再决定是否默认开启更大候选池 rerank。

## 回归

- `.venv/bin/python -m pytest tests/test_rerank_client.py tests/test_rag_retrieval.py tests/test_rag_display_names.py tests/test_taichang_product_parameter_query.py -q`
- 结果：21 passed，1 个 PyPDF2 deprecation warning。
- `py_compile`：通过。

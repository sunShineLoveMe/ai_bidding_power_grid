# run_20260627_local_formal_asset_regression_gate — RAG 增量回归门禁

- 生成时间：2026-06-27T09:43:29.657351+00:00
- 门禁状态：FAIL
- 测试集：Base 30 + 泰昌专项 30

## 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 252 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 643 ms | 27 |
| 泰昌专项 | off | 50.0% | 63.3% | 0.500 | 3.3% | 0.0% | 358 ms | 0 |
| 泰昌专项 | qwen3-rerank | 53.3% | 63.3% | 0.533 | 0.0% | 0.0% | 634 ms | 19 |

## 阈值

```json
{
  "base_recall_min": 0.9667,
  "base_top1_min": 1.0,
  "base_cross_max": 0.0,
  "customer_qwen3_recall_min": 1.0,
  "customer_qwen3_top1_min": 1.0,
  "customer_qwen3_forbidden_max": 0.0,
  "customer_qwen3_cross_max": 0.0
}
```

## 结论

- Customer qwen3 Recall@5 below threshold: 0.5333
- Customer qwen3 top1 accuracy below threshold: 0.6333

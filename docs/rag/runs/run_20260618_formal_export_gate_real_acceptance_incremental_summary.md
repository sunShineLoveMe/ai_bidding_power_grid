# run_20260618_formal_export_gate_real_acceptance_incremental — RAG 增量回归门禁

- 生成时间：2026-06-18T07:52:42.854498+00:00
- 门禁状态：PASS
- 测试集：Base 30 + 泰昌专项 30

## 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 277 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 586 ms | 27 |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 339 ms | 0 |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 682 ms | 30 |

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

- 门禁通过，无召回、来源排序、禁用关键词或跨资料域串扰退化。

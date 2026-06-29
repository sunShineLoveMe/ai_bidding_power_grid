# run_20260629_taichang_legal_representative_fact_fix — RAG 增量回归门禁

- 生成时间：2026-06-29T03:43:39.758568+00:00
- 门禁状态：PASS
- 测试集：Base 30 + 泰昌专项 30

## 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 259 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 589 ms | 27 |
| 泰昌专项 | off | 93.3% | 100.0% | 0.900 | 3.3% | 0.0% | 338 ms | 0 |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.973 | 0.0% | 0.0% | 677 ms | 30 |

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

## 专项真实链路

- 触发问题：客户在知识库助手提问“这家公司的法人代表是谁？”时，历史链路曾被“宣传彩页”OCR 片段污染，输出错误姓名“王伟杰”。
- 根因定位：真实库存在 5 个泰昌 `enterprise_fact` chunk 含冲突工商字段，包括 `法定代表人：王伟杰`、`法人代表：刘志勇` 等；这些片段来源于“宣传彩页/OCR中间片段”，不应覆盖营业执照、企业信用报告等基础证照。
- 数据修复：执行 `scripts/rag/repair_taichang_legal_representative_facts.py --execute`，已将 5 个冲突 chunk 标记为 `exclude_from_rag=true`、`rag_visibility=internal_only`、`fact_source_allowed_for_enterprise=false`。
- 代码修复：新增泰昌企业工商基础信息结构化上下文，法人/法定代表人/统一社会信用代码/注册资本/成立日期/注册地址等问题强制走 `enterprise_basic_info` 范围，优先使用营业执照副本与企业信用报告。
- 真实 `/api/knowledge/search/stream`：问题 `这家公司的法人代表是谁？` 返回 `晁坤琳`，`answer_contains_chaokunlin=True`，`answer_contains_wangweijie=False`。
- 真实 `/api/knowledge/search`：问题 `这家公司的法定代表人是谁？` 返回 `晁坤琳`，`answer_contains_chaokunlin=True`，`answer_contains_wangweijie=False`。
- 定向单测：`tests/test_rag_retrieval.py tests/test_taichang_enterprise_facts.py tests/test_knowledge_enterprise_scope.py` 共 38 passed。

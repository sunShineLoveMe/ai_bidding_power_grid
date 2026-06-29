# run_20260629_taichang_enterprise_basic_fact_guard — RAG 增量回归门禁

- 生成时间：2026-06-29T03:56:39.247590+00:00
- 门禁状态：PASS
- 测试集：Base 30 + 泰昌专项 30

## 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 252 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 570 ms | 27 |
| 泰昌专项 | off | 93.3% | 100.0% | 0.917 | 3.3% | 0.0% | 335 ms | 0 |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.973 | 0.0% | 0.0% | 659 ms | 30 |

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

## 专项修复与真实验证

- 通用化修复：`scripts/rag/repair_taichang_legal_representative_facts.py` 已从固定错误姓名枚举改为“低可信来源字段抽取 + 核验事实包比对”，覆盖法定代表人、统一社会信用代码和注册资本等高置信工商基础字段。
- 数据隔离：本轮执行 `--execute` 后共隔离 6 个高置信冲突 chunk，包括宣传彩页中的错误法定代表人、错误注册资本，以及绿色/环保资料 OCR 中错误统一社会信用代码片段。
- 问答防护：企业基础工商事实问题统一进入 `enterprise_basic_info` 范围，不回退到宣传彩页、人员花名册、生产线合同、审计报告等低可信或无关片段。
- 来源展示：知识库助手参考资料来源后端合并结果限制为 Top 3，前端展示也限制为 Top 3；提示词同步要求参考依据最多引用前三条资料。
- 显示清洗：RAG 来源卡片新增空括号清理，`公司人员花名册（）` 显示为 `公司人员花名册`；`enterprise_profile` 显示为 `企业宣传资料`。
- 真实 `/api/knowledge/search/stream` 验证：
  - `这家公司的法人代表是谁？`：返回 `晁坤琳`，来源 3 条，无 `王伟杰`、无空括号、无 `enterprise_profile`。
  - `这家公司的统一社会信用代码是多少？`：返回 `91130607056539515C`，来源 3 条，无空括号、无内部枚举。
- 定向测试：`tests/test_rag_display_names.py tests/test_taichang_enterprise_facts.py tests/test_knowledge_enterprise_scope.py tests/test_rag_retrieval.py` 共 47 passed。
- 前端构建：`npm run build` PASS。

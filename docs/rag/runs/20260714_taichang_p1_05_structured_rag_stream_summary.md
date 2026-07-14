# 泰昌 P1-05 结构化事实基线真实流式验证

- 生成时间：2026-07-14T03:33:29.912696+00:00
- 状态：PASS
- 链路：真实 `/api/knowledge/search/stream`，真实 LLM，未使用 mock

## 结果

| 用例 | 完成 | 上下文 | 资产 |
| --- | --- | ---: | ---: |
| cross_product_guard | True | 1 | 0 |
| mpp_parameter | True | 3 | 0 |
| cpvc_parameter | True | 3 | 0 |

## 结论

- 架空绝缘导线问题仅命中范围守卫，未召回其他产品事实。
- MPP 环刚度和 CPVC 平均内径/壁厚均返回准确数值、报告编号和来源页。
- 结构化直查与父子分块向量召回可并行使用，未使用 mock。

# run_20260612_taichang_fact_grounded_real_stream — 泰昌补充资料 P1B 真实链路验证

- 生成时间：2026-06-12T22:48:19
- 批次：`customer_taichang_supplement_20260611`
- 状态：FAIL

## 数据库质量复核

| 指标 | 数量 |
| --- | ---: |
| 文档 | 24 |
| chunks | 1900 |
| 图片资产 | 297 |
| 异常资产 metadata | 0 |

## 真实 stream 验证

| 用例 | HTTP | 错误 | 资料/资产召回 | 结论 |
| --- | ---: | --- | --- | --- |
| `compound_contract_award` | 200 | False | 4/8 | 通过 |
| `logo_assets` | 200 | False | 5/8 | 通过 |
| `report_params` | 200 | False | 5/8 | 通过 |

## 结论

- compound answer missing award notice tender no 0322AB

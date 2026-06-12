# P1B-5 泰昌项目业绩结构化抽取执行记录

- 日期：2026-06-12
- 状态：PASS
- 批次：`customer_taichang_supplement_20260611`

## 原始证据

1. `TJ20220002363合同协议书（双方已签章）.pdf`，15 页。
2. `157-保护管（CPVC和MPP）_包2_电缆保护管MPP和CPVC_河北泰昌电力器材科技有限公司_中标通知书.pdf`，2 页。

## 结构化结果

| 字段 | 结果 |
| --- | --- |
| 项目名称 | 国网天津市电力公司2022年第二次配网物资协议库存招标采购 |
| 招标编号 | 0322AB |
| 分标/包号 | 157-保护管（CPVC和MPP）/ 包2 |
| 产品 | MPP、CPVC 电缆保护管 |
| 总数量 | 54,678 米 |
| 含税金额 | 6,372,409.05 元 |
| 买方/招标人 | 国网天津市电力公司 |
| 卖方/中标人 | 河北泰昌电力器材科技有限公司 |
| 中标日期 | 2022-11-21 |
| 合同签署日期 | 原件字段为空，未推断 |
| 买方合同编号 | SGTJWZ00HTMM2210273 |

中标通知书和合同各保留 9 行明细。两份证据的行顺序不同，抽取器按含税金额唯一匹配规格、数量和采购申请号，并校验总数量、总金额和双方主体一致。

## 输出

- `parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/taichang_project_performance_rows.json`
- `parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/taichang_project_performance_rows.csv`
- `parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/extract_taichang_project_performance_report.md`

## 测试与真实验证

- `PYTHONPATH=. .venv/bin/pytest tests/test_taichang_project_performance.py tests/test_taichang_product_parameter_query.py tests/test_rag_retrieval.py -q`
- 结果：`21 passed`，1 个既有 PyPDF2 deprecation warning。
- 真实 HTTP stream：`docs/rag/runs/run_20260612_taichang_project_performance_real_stream.json`。
- 回答已返回 54,678 米、6,372,409.05 元、合同日期缺失状态和来源页码。
- 增量回归：`docs/rag/runs/run_20260612_taichang_project_performance_p1b5_summary.md`，Gate PASS。

## 边界

- 本记录仅来自泰昌原始企业资料。
- 河北豪乾成功标书只提供编制结构参考，不参与业绩事实抽取。
- 合同正文未直接出现招标编号，`0322AB` 通过中标通知书与合同双方、产品范围、逐项金额和总价一致关联，并保留来源标记。

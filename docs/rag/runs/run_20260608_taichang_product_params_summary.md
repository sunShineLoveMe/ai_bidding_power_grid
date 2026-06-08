# Run 15：泰昌产品/检验报告参数抽取

> 日期：2026-06-08  
> Base filtered：`docs/rag/runs/run_20260608_taichang_product_params_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260608_taichang_product_params_customer_filtered.json`

## 背景

本轮根据业务边界调整：辽宁资料只代表辽宁省公司本批招标要求，可作为技术参数抽取后的 QA/异常校验参照，但不得自动推出“泰昌必须覆盖辽宁全部规格/全部需求”的结论。

## 处理内容

- 更新 `AGENTS.md`，明确辽宁资料不代表全国电网或其他省公司要求。
- 新增 `scripts/rag/extract_taichang_product_parameters.py`，从泰昌检验报告 MinerU `full.md` 中抽取企业事实参数。
- 新增 `tests/test_taichang_product_parameter_extraction.py`，覆盖 HTML 表格 `rowspan/colspan` 展开、报告 metadata 识别和 QA-only 范围标记。
- 输出泰昌产品参数：
  - `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/taichang_product_parameters/taichang_product_parameter_rows.json`
  - `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/taichang_product_parameters/taichang_product_parameter_rows.csv`
  - `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/taichang_product_parameters/taichang_product_parameter_summary.md`
  - `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/taichang_product_parameters/extract_taichang_product_parameters_report.json`

## 抽取结果

| 指标 | 数量 |
| --- | ---: |
| 泰昌检验报告 | 2 |
| 成功抽取文档 | 2 |
| 企业事实参数行 | 36 |
| CPVC 电缆保护管参数行 | 19 |
| MPP 电缆保护管参数行 | 17 |

| 产品 | 报告编号 | 规格型号 | 参数行 |
| --- | --- | --- | ---: |
| CPVC电缆保护管 | `2024100312005501713` | `DS 250×15×6000 SN16 PVC-C` | 19 |
| MPP电缆保护管 | `2024100312005501712` | `DF 250×22×9000 SN40 MPP` | 17 |

## 边界说明

- 本轮产物全部标为 `source_domain=enterprise_fact`，事实源为泰昌原始检验报告。
- `qa_reference.scope=qa_only_not_coverage_judgement`，辽宁技术参数只用于抽取 QA，不构成覆盖性结论。
- 后续如果某个省公司投标需要证明某规格可覆盖，应按该省公司需求、泰昌报告/产品资料和客户业务确认单独判断。

## 回归验证

- `.venv/bin/python -m pytest tests/test_taichang_product_parameter_extraction.py tests/test_technical_parameter_extraction.py tests/test_technical_deviation_report.py -q`
- 结果：9 passed。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

## 剩余风险

- 本轮只完成泰昌检验报告参数抽取，尚未新增结构化数据库表。
- 不再自动把泰昌报告值填入辽宁需求偏差判断；如需做具体投标偏差判断，必须先明确目标省公司/批次/规格和人工确认口径。

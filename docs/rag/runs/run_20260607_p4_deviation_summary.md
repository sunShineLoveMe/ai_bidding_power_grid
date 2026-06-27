# Run 14 — P4-4 技术偏差辅助判断

> 运行时间：2026-06-07
> Base filtered：`docs/rag/runs/run_20260607_p4_deviation_base_filtered.json`
> 泰昌专项 filtered：`docs/rag/runs/run_20260607_p4_deviation_customer_filtered.json`

## 背景

P4-2 已将辽宁/泰昌 39 份 CPVC/MPP 技术规范抽取为 `technical_parameter_rows.json`。P4-4 的第一步是基于这些结构化参数，自动判断“项目需求值/标准值”与“投标响应值/投标保证值”之间的偏差状态，为后续技术偏差表、漏项检查和检验报告覆盖性判断提供基础。

## 处理内容

- 新增 `scripts/rag/generate_technical_deviation_report.py`。
- 输入：
  - `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/technical_parameters/technical_parameter_rows.json`
- 输出：
  - `technical_deviation_rows.json`
  - `technical_deviation_rows.csv`
  - `technical_deviation_summary.md`
  - `technical_deviation_report.json`
- 支持的初版判断：
  - `pending_response`：有需求值/标准值，但投标响应值或保证值为空；
  - `no_deviation`：响应文本明确包含满足、响应、无偏差等表述，或数值等于要求；
  - `positive_deviation`：数值响应优于最低/最高限值要求；
  - `negative_deviation`：数值响应不满足最低/最高限值或范围要求；
  - `manual_review`：无法用规则自动判断，需要人工复核；
  - `informational`：未识别到明确需求值，仅作为参数信息保留。

## 产物结果

| 指标 | 数量 |
| --- | ---: |
| 参数行 | 928 |
| 需处理行 | 900 |
| `pending_response` | 900 |
| `informational` | 28 |
| `medium` 风险 | 900 |
| `low` 风险 | 28 |

本批大量参数被标为 `pending_response`，原因是招标技术规范里存在明确项目需求值或标准值，但 `投标人响应值`、`投标人保证值` 多为空白。该结果符合预期，后续需要接入泰昌产品参数、检验报告参数或人工确认值后再进行无偏差/正偏差/负偏差判断。

## 回归验证

- `./.venv/bin/python -m pytest tests/test_technical_deviation_report.py tests/test_technical_parameter_extraction.py tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
  - 33 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile scripts/rag/generate_technical_deviation_report.py scripts/rag/extract_customer_technical_parameters.py backend/rag/retrieval.py`
  - 通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

## 后续

- P4-4 初版已完成“项目需求值/标准值 vs 投标响应/保证值”的规则判断。
- 下一步应把泰昌检验报告、产品规格或人工确认值映射到 `bidder_response_value` / `bidder_guaranteed_value`，再生成正式技术偏差表。
- 如页面需要直接查询，可继续评估新增 `power_grid_technical_parameter_rows` 和 `power_grid_technical_deviation_rows` 数据库表。

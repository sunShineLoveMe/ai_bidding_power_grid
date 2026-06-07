# Run 13 — P4-2 技术参数表抽取

> 运行时间：2026-06-07
> Base filtered：`docs/rag/runs/run_20260607_p4_technical_parameters_base_filtered.json`
> 泰昌专项 filtered：`docs/rag/runs/run_20260607_p4_technical_parameters_customer_filtered.json`

## 背景

P4-2 目标是把技术规范书、技术补充文件和后续客户新增技术资料中的参数表抽成结构化数据，避免技术参数只以普通文本向量进入 RAG。该能力用于技术响应表、技术偏差表、检验报告覆盖性判断和按包号/规格/参数精确查询。

## 规则固化

- 已更新 `AGENTS.md`：
  - 客户后续新增的技术规范书、技术补充文件、技术响应参考稿、检验报告参数页、技术偏差/商务偏差表，只要包含“标准参数值、项目需求值、投标人保证值、保证值、偏差、备注、规格型号、检验项目、技术规范编码、物料编码”等字段，必须进入技术参数表抽取流程。
  - 技术参数表必须保留原始结构、检索摘要和行级记录，不得只做普通文本向量。

## 处理内容

- 新增 `scripts/rag/extract_customer_technical_parameters.py`。
- 从 `customer_liaoning_taichang_20260606_p0/staging/staging_manifest.json` 中筛选 `doc_role=technical_spec` 的 39 份辽宁 CPVC/MPP 技术规范。
- 读取原 `.docx` 或已由 LibreOffice 转换的 `.docx`，识别以下表类型：
  - `dimension_parameter_table`：公称内径、公称壁厚、最小壁厚、允许偏差等尺寸参数；
  - `performance_parameter_table`：密度、拉伸强度、断裂伸长率、环刚度、扁平试验等性能指标；
  - `bid_response_parameter_table`：技术参数名称、单位、项目需求值或表述、投标人响应值等投标响应表。
- 输出三类产物：
  - JSON：`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/technical_parameters/technical_parameter_rows.json`
  - CSV：`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/technical_parameters/technical_parameter_rows.csv`
  - summary chunk：`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/technical_parameters/technical_parameter_summary.md`

## 抽取结果

| 指标 | 数量 |
| --- | ---: |
| 技术规范文档 | 39 |
| 成功抽取文档 | 39 |
| 技术参数行 | 928 |
| CPVC 参数行 | 285 |
| MPP 参数行 | 643 |
| 尺寸参数行 | 349 |
| 性能参数行 | 369 |
| 投标响应参数行 | 210 |

字段覆盖：

- `parameter_name`：922 行；
- `standard_value`：341 行；
- `project_required_value`：210 行；
- `nominal_inner_diameter`：300 行；
- `minimum_wall_thickness`：68 行；
- `bidder_response_value` / `bidder_guaranteed_value`：本批招标技术规范中多为空白，已保留字段，供后续投标响应或客户保证值资料填充。

## 回归验证

- `./.venv/bin/python -m pytest tests/test_technical_parameter_extraction.py tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
  - 27 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile scripts/rag/extract_customer_technical_parameters.py backend/rag/retrieval.py`
  - 通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

## 后续

- 当前 P4-2 已完成首批 JSON/CSV/summary chunk 抽取，尚未新增数据库结构化表。
- 下一步 P4-4 技术偏差/商务偏差辅助可基于本批 `technical_parameter_rows.json` 判断“项目需求值”和“投标响应/保证值”的差异。
- 如后续要让页面或问答直接 SQL 查询技术参数，可参考 `power_grid_goods_list_rows` 新增 `power_grid_technical_parameter_rows` 表。

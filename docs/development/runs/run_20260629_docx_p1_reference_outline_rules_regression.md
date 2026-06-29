# DOCX P1-4 reference_outline 结构化规则回归记录

运行日期：2026-06-29

## 1. 验证目标

本次验证覆盖 `docs/development/docx-export-format-priority-todo.md` 中：

- `P1-4`：`reference_outline` 升级为结构化模板规则。

本轮只落地 `report_only` 阶段：

- 新增 `reference_outline_rules` 结构化 profile 元数据；
- `docx_template_report()` 输出结构化规则；
- 不接入 `backend/ai/chapter_planner.py`；
- 不改变真实项目章节生成数量、顺序和内容。

设计说明见：

```text
docs/development/docx-reference-outline-structured-rules-design.md
```

## 2. 代码口径

`technical_bid_standard` 和 `business_bid_standard` 均新增：

```text
reference_outline_rules.schema_version=1.0
reference_outline_rules.planner_integration=report_only
reference_outline_rules.numbering_style=sgcc_mixed
```

同时保留旧字段：

```text
reference_outline
```

以兼容历史报告和现有调用方。

本轮没有修改：

- `backend/ai/chapter_planner.py`
- `SUPPLY_ONLY_MAX_OUTLINE_NODES`
- `_supply_outline_reject_reason`
- 客户范本/规则版供货类大纲回退机制

## 3. 验证命令

```bash
.venv/bin/python -m py_compile backend/export/md_to_word.py tests/test_docx_export.py
.venv/bin/python -m pytest tests/test_docx_export.py -q
.venv/bin/python -m pytest tests/test_chapter_planner.py -q
.venv/bin/python -m pytest tests/test_celery_export_tasks.py -q
```

真实导出链路：

```text
build_project_bid_markdown
-> convert_md_to_word
-> refresh_docx_fields_with_soffice
```

验证项目：

```text
a1d853bc-ca4e-43b4-bbea-256f561c8a3d
```

## 4. 自动化测试结果

- `py_compile`：通过；
- `tests/test_docx_export.py`：`59 passed, 1 warning`；
- `tests/test_chapter_planner.py`：`12 passed`；
- `tests/test_celery_export_tasks.py`：`11 passed, 1 warning`。

新增/强化的单测断言：

- 技术标 profile 输出 `reference_outline_rules.schema_version=1.0`；
- 技术标 profile 输出 `scope=technical_bid_volume`；
- 商务标 profile 输出 `scope=business_bid_volume`；
- 两个 profile 均输出 `planner_integration=report_only`；
- 规则约束包含 `respect_supply_outline_guardrails=true`；
- 规则约束包含 `do_not_override_customer_confirmed_outline=true`；
- 结构化章节规则包含技术参数表、商务偏差表等稳定 ID。

## 5. 真实导出结果

技术标：

- DOCX：`outputs/a1d853bc/泰昌_2225AC_包1_技术投标文件_20260629_图文.docx`
- 模板：`technical_bid_standard`
- 旧 `reference_outline` 数量：`7`
- 新 `reference_outline_rules.sections` 数量：`6`
- `planner_integration`：`report_only`
- `selection_section_count`：`50`
- DOCX 标题数量：`52`
- P1-3 基线标题数量：`52`
- 标题数量是否与 P1-3 基线一致：`true`
- 字段刷新：`refreshed`
- 图片：选中 `9`，插入 `9`，失败 `0`

技术标结构化规则 ID：

```text
technical_deviation_table
technical_parameter_table
point_to_point_response
component_material_configuration
technical_evaluation_support
inspection_reports
```

商务标：

- DOCX：`outputs/a1d853bc/泰昌_2225AC_包1_商务投标文件_20260629_图文.docx`
- 模板：`business_bid_standard`
- 旧 `reference_outline` 数量：`7`
- 新 `reference_outline_rules.sections` 数量：`5`
- `planner_integration`：`report_only`
- `selection_section_count`：`52`
- DOCX 标题数量：`51`
- P1-3 基线标题数量：`51`
- 标题数量是否与 P1-3 基线一致：`true`
- 字段刷新：`refreshed`
- 图片：选中 `5`，插入 `5`，失败 `0`

商务标结构化规则 ID：

```text
business_deviation_table
legal_forms
enterprise_credit_query
financial_status
qualification_proofs
```

## 6. 审计结论

本轮满足 P1-4 report-only 阶段门禁：

- 结构化规则已进入导出报告；
- 旧 `reference_outline` 仍保留；
- 未修改 `chapter_planner.py`；
- `tests/test_chapter_planner.py` 全部通过；
- 真实技术标/商务标标题数量与 P1-3 基线一致；
- 没有出现章节数量膨胀；
- 没有绕过供货类大纲门禁；
- 没有复用参考稿企业事实。

## 7. 后续边界

若后续要让 `chapter_planner.py` 使用 `reference_outline_rules`，必须另开 P1-4C 子任务，并按以下优先级设计：

```text
招标文件明确要求
> 用户/客户已确认章节
> 当前供货类大纲门禁和章节数上限
> 客户范本/规则版回退
> reference_outline_rules 结构化提示
> AI 自由生成建议
```

不得在当前交付阶段直接把结构化规则接入生成层。

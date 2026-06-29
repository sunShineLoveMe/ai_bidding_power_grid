# P1-4C reference_outline_rules 生成层接入回归记录

日期：2026-06-29

## 1. 目标

验证 `reference_outline_rules` 从报告层进入 `chapter_planner.py` 生成层后，是否满足以下门禁：

- 只作为受控低优先级提示，不覆盖招标文件要求、客户确认章节、供货类大纲门禁；
- 不提高 `SUPPLY_ONLY_MAX_OUTLINE_NODES=140`；
- 不绕过 `_supply_outline_reject_reason()`；
- 不把参考稿企业事实、辽宁招标要求或河北豪乾事实写成泰昌事实；
- 真实项目改前/改后章节数和导出标题数可复核。

## 2. 本轮代码边界

- `backend/export/md_to_word.py`
  - `technical_bid_standard` / `business_bid_standard` 的 `reference_outline_rules.planner_integration` 从 `report_only` 升级为 `guarded_planner_hint`。
- `backend/ai/chapter_planner.py`
  - 仅供货类物资投标场景读取技术标/商务标 `reference_outline_rules`。
  - 规则进入 prompt 低优先级提示。
  - 命中的章节写入 `metadata.reference_outline_rule_id`、`reference_outline_section_type`、`reference_outline_requires_table` 等字段。
  - 供货类参考目录进入规则大纲前过滤施工类标题：`施工组织设计`、`施工部署`、`施工方案`、`工程概况`、`总体部署`。
  - 供货类识别补充 `物资协议库存`、`架空绝缘导线`、`绝缘导线`、`供货要求` 等电网物资项目口径。

## 3. 改前基线

命令：

```bash
set -a; source .env; set +a; .venv/bin/python <baseline script>
```

项目：

```text
a1d853bc-ca4e-43b4-bbea-256f561c8a3d
国网辽宁电力2025年第三次物资协议库存招标采购
```

结果：

- 快稿章节数：`64`
- 快稿分册：资格 `8`、商务 `10`、技术 `9`、报价 `2`、其他 `2`
- `reference_outline_rules` 未进入 prompt；
- `reference_outline_rules_integration` 不存在；
- 供货类门禁拒绝原因：包含 `施工组织设计`、`施工部署` 等施工类标题；
- 结论：真实物资协议库存项目被误判到通用施工类大纲路径，这是必须修正的事实问题。

## 4. 改后快稿验证

输出：

```text
output/docx-p1-4c-baseline-after.json
```

结果：

- `is_supply_only_bid=true`
- 快稿章节数：`102`
- 分册：商务 `50`、技术 `50`、报价 `1`、附件 `1`
- 章节数上限：`102 <= 140`
- `reject_reason=null`
- 禁用施工类标题命中：`0`
- prompt 包含 `结构化参考模板规则 reference_outline_rules`
- `reference_outline_rules_integration.mode=guarded_planner_hint`
- 规则集数量：`2`
- 结构化规则章节数：`11`
- 真实章节 metadata 命中规则数量：`13`

命中样本：

- `投标函及法定格式文件 -> legal_forms`
- `商务偏差表 -> business_deviation_table`
- `查询报告及截图 -> enterprise_credit_query`
- `技术评分支撑材料 -> technical_evaluation_support`
- `技术偏差表 -> technical_deviation_table`
- `技术特性参数表 -> technical_parameter_table`
- `货物组件材料配置表 -> component_material_configuration`

结论：

快稿章节数从 `64` 增加到 `102`，但这是从错误通用施工大纲切换到供货类参考结构，不是 AI 膨胀；改后仍低于门禁上限，且禁用施工类标题被清除。

## 5. 真实 AI 精修验证

命令：

```bash
set -a; source .env; set +a; .venv/bin/python <real ai refine script>
```

说明：调用 `_generate_outline_from_ai_or_rule(payload)`，只生成结果，不调用保存接口，不落库。

输出：

```text
output/docx-p1-4c-real-ai-after.json
```

结果：

- 模型：`deepseek-v4-pro`
- 返回版本：`ai-volume-v1`
- 精修章节数：`38`
- 分册：价格 `3`、商务 `16`、技术 `19`
- `preserve_reference_structure=true`
- `reject_reason=null`
- `fallback_reason=null`
- 禁用施工类标题命中：`0`

结论：

真实 AI 精修在 `reference_outline_rules` 提示下没有章节膨胀，也没有触发供货类门禁冲突。

## 6. 正式 DOCX 导出回归

命令链路：

```text
build_project_bid_markdown(volume_type, with_images=true)
-> convert_md_to_word(return_report=true, cover_fields=...)
-> refresh_docx_fields_with_soffice
```

输出：

```text
output/docx-p1-4c-export-regression/run_20260629_docx_p1_4c_export_regression.json
```

技术标：

- `template_id=technical_bid_standard`
- `planner_integration=guarded_planner_hint`
- 章节选择数：`50`
- Word 标题数：`52`
- 图片：选中 `9`，DOCX 插入 `9`，失败 `0`
- 字段刷新：`refreshed`
- 页眉可见文本字符：`0`
- 页脚：有 `PAGE`，无 `NUMPAGES`，无“第/共/页”

商务标：

- `template_id=business_bid_standard`
- `planner_integration=guarded_planner_hint`
- 章节选择数：`52`
- Word 标题数：`51`
- 图片：选中 `5`，DOCX 插入 `5`，失败 `0`
- 字段刷新：`refreshed`
- 页眉可见文本字符：`0`
- 页脚：有 `PAGE`，无 `NUMPAGES`，无“第/共/页”

结论：

P1-4C 生成层改动没有破坏技术标/商务标正式 DOCX 导出；导出标题数与 P1-3/P1-4B 基线一致。

## 7. 自动化测试

```bash
.venv/bin/python -m py_compile backend/ai/chapter_planner.py backend/export/md_to_word.py tests/test_chapter_planner.py tests/test_docx_export.py
.venv/bin/python -m pytest tests/test_chapter_planner.py tests/test_docx_export.py -q
```

结果：

```text
73 passed, 1 warning
```

补充回归：

```bash
.venv/bin/python -m pytest tests/test_celery_export_tasks.py -q
```

结果：

```text
11 passed, 1 warning
```

最终合并回归：

```bash
.venv/bin/python -m pytest tests/test_chapter_planner.py tests/test_docx_export.py tests/test_celery_export_tasks.py -q
```

结果：

```text
84 passed, 1 warning
```

## 8. 残余风险

- P1-4C 当前只将规则作为低优先级 planner hint 和 metadata，不生成附件级整页报告，也不生成逐规格技术参数表。
- 如后续要按规则强制补齐章节，必须另开任务，并重新比较快稿、AI 精修、落库章节和 DOCX 导出章节数。
- 当前正式配图数量仍是技术 `9`、商务 `5`，图片密度问题应通过 P2 附件级图片/报告插入和泰昌正式资产补充解决，不应放宽正式资产门禁。

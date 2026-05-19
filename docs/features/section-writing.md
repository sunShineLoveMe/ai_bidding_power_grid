# 章节写作计划

> 相关代码：`backend/ai/bid_writing_plan.py`、`backend/ai/section_writer.py`

## 章节写作计划

标书章节不会只按目录层级固定生成固定字数。系统会在章节大纲生成阶段为每个 `bid_sections` 章节写入 `metadata.writing_plan`，用于指导目录模式展示和章节正文生成。

### 写作计划字段

| 字段 | 说明 |
| --- | --- |
| `importance` | 章节重要性：`high` / `medium` / `low`，由评分项数量、风险项数量、章节类型综合计算 |
| `target_words` | 目标字数，用于指导正文生成篇幅；保存全文设置后由 `length_settings` 覆盖 |
| `min_words` / `max_words` | 建议字数区间，由章节类型和重要性决定 |
| `suggested_pages` | 建议页数区间，按标书常见排版估算 |
| `needs_table` | 是否建议插入表格 |
| `needs_image` | 是否建议插入图片、流程图或示意图 |
| `needs_qualification` | 是否需要资质、证书、营业执照等材料支撑 |
| `needs_case` | 是否需要类似项目业绩或案例支撑 |
| `generation_mode` | `single_pass` 或 `multi_pass`，长章节后续可分段续写 |
| `strategy` | 章节写作策略，参与正文生成 Prompt |
| `length_settings_source` | 字数来源标记；值为 `project_length_settings` 时表示由全文设置覆盖 |
| `allow_auto_expand` | 是否允许围绕评分点和可验证措施扩写；`false` 时资料不足只能占位 |

### 写作计划的生成时机

写作计划在以下三个时机生成或更新：

1. **章节大纲生成时**（`_normalize_outline_chapters()`）：为每个章节调用 `build_chapter_writing_plan()` 生成初始写作计划，基于章节标题、类型、层级、评分项、风险项和材料需求推导。

2. **保存全文篇幅设置时**（`apply_length_allocations_to_sections()`）：用用户设置的目标字数覆盖 `target_words` 和 `suggested_pages`，并写入 `length_settings_source: "project_length_settings"` 标记。

3. **历史数据兜底**：如果旧数据没有 `metadata.writing_plan`，前端和后端会根据章节标题、层级、评分项、风险项和材料要求临时推导一份计划，避免历史项目无法生成正文。

### 目录模式展示

- `目标 xxx字` 来自 `writing_plan.target_words`；保存全文设置后带有 `project_length_settings` 来源标记。
- `已完成 xxx字` 是当前章节正文去除 Markdown 语法后的实际估算字数。
- 核心章节、建议页数、需表格、需图文、需资质、需业绩等标签均来自写作计划。

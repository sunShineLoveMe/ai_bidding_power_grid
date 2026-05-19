# 全文篇幅设置与章节正文生成

> 相关代码：`backend/ai/length_settings.py`、`backend/ai/section_writer.py`

## 全文篇幅设置与章节正文生成

标书工作台中的"全文设置"不是把总页数或总字数直接塞进一个总 prompt，而是先转换为技术标、商务标的目标字数，再按章节权重分配到每个章节的 `metadata.writing_plan.target_words`。后续"一键编写全文"和单章重写都会读取该章节自己的写作计划，因此目标篇幅是按章节生效。

后端接口：

```text
POST /api/bidding/interpretations/{project_id}/length-settings
POST /api/bidding/interpretations/{project_id}/sections/stream
```

### 篇幅设置保存流程

1. `backend/ai/length_settings.py` 将页数按 `technical=700 字/页`、`business=550 字/页` 转换为目标字数。
2. 系统按章节重要性、评分项、要求条款、风险项和章节层级计算权重（`_chapter_weight()`）。
3. 技术标章节分配技术标目标字数；商务、资格、报价、附件统一归入商务标目标，但资格（上限 1800 字）、报价（上限 900 字）和附件（上限 900 字）会限制空泛扩写。
4. 分配结果写入每个章节的 `metadata.writing_plan`，包括 `target_words`、`suggested_pages`、`length_settings_source`（值为 `project_length_settings`）和 `allow_auto_expand`。

权重计算规则（`_chapter_weight()`）：

```python
weight = 1.0
weight += 1.2  # importance == "high"
weight += 0.5  # importance == "medium"
weight += min(scoring_count, 4) * 0.35   # 评分项数量
weight += min(requirement_count, 5) * 0.2  # 要求条款数量
weight += min(risk_count, 3) * 0.25      # 风险项数量
weight += 0.35  # level <= 2（一二级章节）
weight *= 0.55  # 资格/报价/附件分册（限制扩写）
```

### 章节正文生成流程

1. `backend/ai/section_writer.py` 的 `build_section_prompt()` 生成单章正文 Prompt 时注入：
   - 当前章节的目标字数（`writing_plan.target_words`）
   - 建议篇幅（`writing_plan.suggested_pages`）
   - 生成方式（`single_pass` / `multi_pass`）
   - 分册写作策略（技术标/商务标/资格/报价/附件各有不同约束）
   - 企业画像（7 字段）
   - 企业资产库候选（按分册类型过滤，最多 6 条）
   - 响应要点、关联评分项、风险提醒、所需资料

2. 首轮生成结束后，后端估算当前章节正文长度（`estimate_bid_content_words()`）；若低于章节目标字数的 **75%**，会针对该章节触发补写 Prompt（`build_section_supplement_prompt()`）。

3. 补写 Prompt 只允许输出可直接追加到章节末尾的内容，并明确告知：
   - 当前估算字数 vs 目标字数
   - 建议补写字数（`missing_words`）
   - 优先补充评分点、响应要求、风险控制、实施措施和可验证材料

4. 若用户选择"允许扩写"（`allow_auto_expand=true`），补写可以围绕评分点和可验证措施展开；否则只能补充有依据内容，资料不足时使用 `【待补充：...】` 占位。

5. 章节保存时会记录 `actual_words`、`target_words` 和 `length_completion_ratio`，用于后续判断是否仍低于目标。

### 前端展示口径

- `用户目标`：用户在全文生成设置中输入的技术标 / 商务标页数或字数。
- `章节计划`：系统实际分配到当前筛选范围内各章节的目标字数合计；由于资格、报价和附件会限制空泛扩写，该值可能小于用户目标。
- `已生成`：当前已生成正文的实际估算篇幅。
- 章节标签中的 `目标 xxxx 字` 来自章节写作计划；保存全文设置后，该目标会带有 `project_length_settings` 来源标记。

### 字数达成率说明

单章目标字数的可达性取决于章节数量。**章节越多，每章分配的目标字数越小，越容易达到**。建议在设置全文篇幅前先生成 AI 精细化大纲（章节数 40-60 个），再设置目标页数，避免单章目标超过 6000 字（模型单次输出上限约 4000-6000 字）。

| 目标页数 | 建议最少章节数 | 单章平均目标字数 |
| ---: | ---: | ---: |
| 80 页技术标 | 30 章 | ~1,900 字 |
| 120 页技术标 | 40 章 | ~2,100 字 |
| 150 页技术标 | 50 章 | ~2,100 字 |
| 200 页技术标 | 60 章 | ~2,300 字 |

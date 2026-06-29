# DOCX reference_outline 结构化模板规则设计说明

更新日期：2026-06-29

## 1. 背景

`P1-4` 的原始目标是把 `reference_outline` 从纯文本章节提示升级为结构化模板规则。经代码核查，目前事实如下：

- `reference_outline` 定义在 `backend/export/md_to_word.py` 的 `DOCX_TEMPLATE_PROFILES` 中；
- 当前 `reference_outline` 是技术标/商务标 profile 下的一组章节名称清单；
- 当前它主要通过 `docx_template_report()` 进入导出 metadata/report；
- 当前大纲生成主要在 `backend/ai/chapter_planner.py`，与 `reference_outline` 没有真正打通；
- `chapter_planner.py` 已有供货类大纲门禁，例如 `SUPPLY_ONLY_MAX_OUTLINE_NODES`、`_supply_outline_reject_reason()` 和客户范本/规则版回退；
- 前序 P0 到 P1-3 主要作用于导出层，P1-4 若直接接入大纲生成层，风险等级明显升高。

因此，`P1-4` 不能按“轻量导出版式改动”处理，必须先设计、再分阶段落地。

## 2. 任务定位

P1-4 的合理定位：

```text
把 reference_outline 从“章节名称提示词”升级为“可执行/可校验的模板规则元数据”。
```

它应服务于三类能力：

- 导出报告更明确：知道每个参考章节的类型、分册、编号层级、是否进目录、是否分页、是否偏表单/附件；
- 后续规则校验更稳定：可判断真实导出是否缺少关键章节、编号层级是否异常、是否错误复用参考稿事实；
- 为 P2 附件级图片/报告插入提供章节规则基础。

P1-4 不应立即做的事：

- 不直接替换 `chapter_planner.py` 已有大纲生成机制；
- 不直接绕过供货类大纲门禁；
- 不直接把新疆参考稿目录完整强塞进所有项目；
- 不直接增加章节数量上限；
- 不把参考稿企业事实、产品、证书、业绩或附件内容作为泰昌事实。

## 3. 分阶段方案

### P1-4A：设计与任务边界确认

只做文档和任务清单调整：

- 明确结构化规则的数据结构；
- 明确与 `chapter_planner.py` 的关系；
- 明确风险门禁；
- 明确验收标准；
- 不改生成逻辑。

### P1-4B：元数据与导出报告落地

在 `DOCX_TEMPLATE_PROFILES` 中新增结构化字段，例如：

```python
"reference_outline_rules": {
    "schema_version": "1.0",
    "scope": "technical_bid_volume",
    "numbering_style": "sgcc_mixed",
    "toc_max_level": 4,
    "planner_integration": "report_only",
    "sections": [
        {
            "id": "technical_deviation_table",
            "title": "技术偏差表",
            "aliases": ["技术偏离表"],
            "section_type": "deviation_table",
            "volume_type": "technical",
            "recommended_level": 2,
            "include_in_toc": True,
            "start_on_new_page": False,
            "heading_style": "reference_volume_heading",
            "requires_table": True,
            "preferred_asset_evidence_types": [],
            "generation_policy": "required_if_tender_requires",
        }
    ],
    "constraints": {
        "do_not_generate_enterprise_facts_from_reference": True,
        "respect_supply_outline_guardrails": True,
        "do_not_override_customer_confirmed_outline": True,
    },
}
```

本阶段只允许：

- `docx_template_report()` 输出结构化规则；
- 单元测试验证 schema 和 profile 范围；
- 真实导出 metadata 记录该规则；
- 不改变现有章节生成数量、顺序和内容。

### P1-4C：生成层接入评估与受控落地

只有在 P1-4B 稳定后，才评估是否让 `chapter_planner.py` 使用结构化规则。

若接入，优先级必须是：

```text
招标文件明确要求
> 用户/客户已确认章节
> 当前供货类大纲门禁和章节数上限
> 客户范本/规则版回退
> reference_outline_rules 结构化提示
> AI 自由生成建议
```

并且必须保留：

- `SUPPLY_ONLY_MAX_OUTLINE_NODES`；
- `_supply_outline_reject_reason()`；
- 客户范本/规则版回退；
- 后台精修章节数不得异常膨胀；
- 非电网/非供货类项目不得误套国网分册规则。

2026-06-29 已完成受控落地，实施边界如下：

- `reference_outline_rules.planner_integration` 从 `report_only` 升级为 `guarded_planner_hint`；
- `chapter_planner.py` 只在供货类物资投标场景读取技术标/商务标规则；
- 规则用于 prompt 低优先级提示、章节 metadata 标注、表格/结构化数据写作提示；
- 规则不直接强插章节，不提高 `SUPPLY_ONLY_MAX_OUTLINE_NODES`，不绕过 `_supply_outline_reject_reason()`；
- 供货类判断补充识别 `物资协议库存`、`架空绝缘导线`、`绝缘导线`、`供货要求` 等真实电网物资项目口径；
- 参考模板目录进入供货类规则大纲前过滤 `施工组织设计`、`施工部署`、`施工方案`、`工程概况`、`总体部署` 等施工类章节，避免客户参考目录污染物资供货标书。

## 4. 建议数据结构

### Profile 级字段

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 规则 schema 版本 |
| `scope` | 适用范围，例如 `technical_bid_volume`、`business_bid_volume` |
| `numbering_style` | 编号样式，例如 `sgcc_mixed` |
| `toc_max_level` | 最大目录层级 |
| `planner_integration` | 当前建议先用 `report_only` |
| `sections` | 结构化章节规则列表 |
| `constraints` | 与生成层、事实边界、门禁相关的约束 |

### Section 级字段

| 字段 | 含义 |
| --- | --- |
| `id` | 稳定规则 ID |
| `title` | 推荐章节标题 |
| `aliases` | 同义标题 |
| `section_type` | 章节类型，例如偏差表、技术参数表、点对点应答、附件证明 |
| `volume_type` | `technical` / `business` |
| `recommended_level` | 推荐层级 |
| `include_in_toc` | 是否进入目录 |
| `start_on_new_page` | 是否建议分页 |
| `heading_style` | 标题样式引用 |
| `requires_table` | 是否偏表格结构 |
| `preferred_asset_evidence_types` | 推荐证据类型 |
| `structured_data_required` | 是否依赖结构化表格/参数 |
| `generation_policy` | `required_if_tender_requires` / `optional` / `reference_only` |

## 5. 风险门禁

P1-4 相关改动必须满足：

- P1-4B 阶段不得改变真实项目章节数；
- 不得绕过 `chapter_planner.py` 供货类大纲门禁；
- 不得让大纲章节数超过 `SUPPLY_ONLY_MAX_OUTLINE_NODES`；
- 不得复用新疆参考稿企业事实；
- 不得复用河北豪乾参考稿事实；
- 不得将辽宁招标要求当作泰昌企业事实；
- 至少跑一个真实项目端到端导出，确认章节数没有失控；
- 必须跑 `tests/test_chapter_planner.py` 和 `tests/test_docx_export.py`；
- 若接入生成层，必须新增真实项目回归记录，并比较修改前后章节数量、目录样本和回退原因。

## 6. 本轮建议验收标准

P1-4B 可关闭的最低标准：

- `technical_bid_standard` 和 `business_bid_standard` 都有 `reference_outline_rules`；
- `docx_template_report()` 同时输出旧 `reference_outline` 和新 `reference_outline_rules`，兼容现有报告；
- 单元测试验证结构化规则 schema、scope、章节类型、编号样式和 `planner_integration=report_only`；
- 真实技术标/商务标导出 metadata 包含结构化规则；
- 真实项目章节数与 P1-3 基线一致，不出现章节膨胀；
- 文档记录说明：本轮暂不接入 `chapter_planner.py` 生成层。

P1-4C 若启动，需单独开子任务和真实项目回归门禁。

## 7. 当前结论

P1-4 方向合理，但必须按高风险生成层任务处理。P1-4A/P1-4B 已完成结构化规则和 `report_only` 验证；P1-4C 已完成受控生成层接入。

这样既能把模板规则结构化，为后续 P2 附件级能力和多模板扩展打基础，又不会在当前交付期引入章节膨胀、门禁冲突或事实混用风险。

P1-4C 验证结论：

- 真实项目改前快稿为通用大纲 `64` 节，并且供货类门禁会识别出施工类禁用标题；
- 改后真实项目被正确识别为供货类物资协议库存项目，快稿 `102` 节，低于 `140` 上限，禁用施工类标题为 `0`；
- `reference_outline_rules` 进入 prompt，`reference_outline_rules_integration.mode=guarded_planner_hint`，并有 `13` 个真实章节命中规则 metadata；
- 真实 AI 精修链路不落库返回 `38` 节，未触发拒绝原因，未出现施工类禁用标题；
- 技术标/商务标真实 DOCX 导出标题数仍为 `52/51`，图片插入 `9/9`、`5/5`，字段刷新 `refreshed`。

# P0 批量章节生成可靠性与 Prompt 分级瘦身技术方案

状态：评审稿  
日期：2026-06-25  
关联线上诊断：`docs/development/runs/run_20260625_aliyun_section_generation_timeout_diagnosis.md`

## 1. 背景与问题定义

客户在阿里云测试环境执行全文批量编写时，前半段章节生成速度较快，后半段大量章节长期停留在“正在编写/排队中”。线上任务诊断显示，任务并非进程死锁，也不是前端轮询失败，而是大量章节触发：

```text
MODEL_STREAM_WALL_TIMEOUT: 模型流式输出超过单章节最大时长 300 秒，已停止继续等待。
```

最新线上任务 `952fb458-25fa-49b6-bb40-e600d22da975` 的关键数据：

| 指标 | 数值 |
| --- | --- |
| 总叶子章节 | 144 |
| 已完成 | 76 |
| partial 草稿 | 59 |
| 正在编写 | 3 |
| 排队 | 6 |
| 完成章节平均字数 | 约 1138 |
| partial 章节平均字数 | 约 283 |
| 后半段共同错误 | `MODEL_STREAM_WALL_TIMEOUT` |

排查结论：

- 不支持“每次把前文全部塞进 DeepSeek 上下文导致越写越慢”的判断。批量任务没有拼接前面全部正文。
- 但每章 prompt 本身较重，固定包含企业画像、泰昌事实、用户确认变量、RAG、资料候选、评分项和风险项。
- 当前批量生成默认 3 路并发，持续进行长文本流式生成；当模型流式吞吐下降时，每个章节会占满 300 秒墙钟超时窗口，导致用户体感“卡死”。

本方案目标不是简单把并发降到 1，也不是单纯把超时调大，而是让批量写作变成可观测、可自适应、可恢复、对客户可解释的生产级流程。

## 2. 目标与非目标

### 2.1 目标

1. 保持批量编写整体速度，不因单个慢章节拖死整个任务。
2. 保持正文质量，核心章节仍能获得足够 RAG 和企业事实支撑。
3. 降低单章输入负担，大量重复小节不再携带过重上下文。
4. 让 partial 草稿成为可续写状态，而不是失败状态。
5. 前端能向客户明确展示真实进度、模型慢流、草稿续写和剩余工作。
6. 不引入庞大新架构，优先复用现有 Celery、`bid_generation_tasks`、`bid_generation_task_items`。

### 2.2 非目标

1. 不引入新的工作流引擎。
2. 不把批量生成改成复杂多 Agent。
3. 不把所有章节强行变成短内容；核心技术/资信章节仍应充分生成。
4. 不让普通用户面对大量底层参数配置。
5. 不为了绕过 DeepSeek 慢流而完全放弃模型质量控制。

## 3. 优先级总览

| 优先级 | 任务 | 目标 | 主要改动 |
| --- | --- | --- | --- |
| P0-A | 生成吞吐可观测 | 先知道慢在哪里、慢到什么程度 | item metadata 增加 prompt/首 token/吞吐/慢流原因 |
| P0-B | Prompt 分级瘦身 | 大幅降低简单/续写/表格章节输入负担 | 新增 prompt profile 和上下文预算策略 |
| P0-C | 慢流提前保护 | 不再每个慢章节硬等 300 秒 | 60-90 秒吞吐不足时进入 slow/partial/重试 |
| P0-D | 自适应并发调度 | 保持速度但避免持续压低模型吞吐 | 依据最近窗口成功率和吞吐动态调整并发 |
| P0-E | partial 草稿续写闭环 | 已保存草稿可自动/手动续写 | 短 prompt 续写、重试次数上限、状态清晰 |
| P0-F | 前端体验收口 | 客户不再看到“像卡死” | 状态文案、顶部统计、慢流提示、批量续写入口 |
| P0-G | 完成章节长度语义收口 | 客户不再把“篇幅偏长”理解成失败或必须重写 | 完成状态与长度质检分离；提供可选压缩而非默认重写 |
| P0-H | 目录结构编辑闭环 | 新增/改名/移动/删除不污染正式目录和分册 | 继承分册、显式确认、删除真实提示、操作后高亮和可撤销 |
| P1 | 模型路由与成本优化 | 简单章节走快路径，核心章节走稳路径 | 模型/模板/结构化生成分流 |

## 4. 设计原则

1. **章节不是同质任务**：编制依据、参数响应、资信证书、报价附件不应使用同一套 prompt。
2. **输入越多不等于质量越好**：上下文必须按章节目标选择，避免每章携带全量事实和资料候选。
3. **慢流比失败更危险**：失败会很快释放 worker，慢流会长期占用并发槽。
4. **partial 是生产状态**：模型写到一半时，系统应保存、标记、续写，而不是让用户以为任务坏了。
5. **调度策略集中化**：并发、慢流、重试、续写策略应集中在 policy 层，避免散落在前端和 worker 中。
6. **默认值服务演示稳定**：线上测试环境默认策略应偏稳，不以实验并发追求短期速度。

## 5. Prompt 分级瘦身方案

### 5.1 现状问题

当前 `backend/ai/section_writer.py` 的 `build_section_prompt()` 对多数章节都构造较重上下文，典型包含：

- 企业画像；
- 用户确认变量；
- 泰昌核验事实包；
- 当前命中的企业资料候选；
- 章节级 RAG 写作依据；
- 分册策略；
- 响应要点；
- 关联要求；
- 评分项；
- 风险提醒；
- 写作计划。

这对核心章节有必要，但对大量重复小节过重，例如：

- 编制依据；
- 工程概况；
- 总体部署；
- 组织机构；
- 实施方法；
- 进度安排；
- 附件索引；
- 价格/报价说明。

### 5.2 Prompt Profile

新增 `SectionPromptProfile`，由章节标题、分册、写作计划、是否需要表格/图片/资质/业绩、mapped requirements 等信息判定。

建议新增模块：

```text
backend/ai/section_prompt_policy.py
```

核心结构：

```python
@dataclass(frozen=True)
class SectionPromptProfile:
    name: str
    context_level: str
    max_prompt_chars: int
    rag_limit: int
    asset_limit: int
    fact_pack_mode: str
    allow_table: bool
    continuation_mode: bool = False
```

### 5.3 分级策略

| Profile | 适用章节 | 上下文策略 | 目标 |
| --- | --- | --- | --- |
| `simple_plan` | 编制依据、工程概况、总体部署、组织机构、实施方法、进度安排 | 项目变量 + 章节目标 + 轻量事实摘要 + 必要要求 | 快速生成稳定正文 |
| `fact_grounded` | 资质、业绩、企业能力、授权、承诺 | 用户确认变量 + 泰昌事实包 + 精选企业资料 | 保证企业事实准确 |
| `technical_parameter` | MPP/CPVC 技术参数响应、检验报告、偏差核对 | 结构化参数 + 技术 RAG + 关键检验报告事实 | 保证参数和报告编号正确 |
| `structured_table` | 响应表、偏差表、货物组件材料配置表 | 表格 schema + 关键值 + 少量说明 | 避免模型自由发挥长篇 |
| `attachment_index` | 附件、证明材料索引、页码索引 | 章节目的 + 占位规则 + 索引模板 | 快速生成可复核索引 |
| `price_sensitive` | 报价、单价分析、税率、保证金 | 不编造金额；只生成模板和人工确认项 | 防止错误金额进入正文 |
| `continuation_slim` | partial 草稿续写 | 草稿末尾 + 缺口 + 关键事实摘要 | 快速续写，不重复全文 |

### 5.4 上下文预算

建议默认预算：

| Profile | Prompt 字符预算 | RAG 条数 | 企业资料候选 | 泰昌事实包 |
| --- | ---: | ---: | ---: | --- |
| `simple_plan` | 3500-5000 | 0-2 | 0-2 | 轻量摘要 |
| `fact_grounded` | 7000-10000 | 2-4 | 3-5 | 完整相关事实 |
| `technical_parameter` | 8000-12000 | 3-5 | 2-4 | 产品/检验报告重点事实 |
| `structured_table` | 5000-8000 | 1-3 | 0-2 | 按字段摘取 |
| `attachment_index` | 2500-4000 | 0-1 | 0-1 | 不需要完整事实 |
| `price_sensitive` | 2500-4000 | 0-1 | 0 | 只保留不可编造约束 |
| `continuation_slim` | 2500-4500 | 默认 0 | 默认 0 | 关键事实摘要 |

### 5.5 轻量事实摘要

当前 `build_taichang_verified_fact_context()` 会把企业、证书、检验报告、业绩等都输出。建议拆成多个摘要函数：

```python
build_taichang_fact_digest(profile, chapter)
```

输出模式：

| 模式 | 内容 |
| --- | --- |
| `identity_only` | 投标人、统一社会信用代码、法人、项目名称 |
| `certifications` | 三体系证书、营业执照、资质相关事实 |
| `product_parameters` | CPVC/MPP 报告编号、规格、关键参数 |
| `performance` | 业绩项目、招标编号、数量、金额 |
| `minimal_constraints` | 不得编造金额、日期、签章、保证金等 |

### 5.6 章节分类示例

| 章节标题 | 推荐 Profile | 原因 |
| --- | --- | --- |
| `23.2.1 编制依据` | `simple_plan` | 不需要完整企业资料候选 |
| `23.2 电缆保护管CPVC技术参数响应表` | `technical_parameter` 或 `structured_table` | 需要参数事实和表格结构 |
| `24.3 偏差核对` | `structured_table` | 应输出偏差表，不应长篇扩写 |
| `24.4 证明材料索引` | `attachment_index` | 主要是索引和占位 |
| `单价分析表（如需要）` | `price_sensitive` | 金额不能编造 |
| partial 草稿续写 | `continuation_slim` | 不再携带完整 RAG 和资料候选 |

### 5.7 Prompt 构造流程

建议从当前单一 `build_section_prompt()` 演进为：

```text
classify_section_prompt_profile(chapter)
  -> build_section_context_budget(profile, chapter)
  -> build_profile_prompt(profile, context)
  -> validate_prompt_budget(prompt, profile)
```

伪代码：

```python
profile = classify_section_prompt_profile(chapter, continuation=bool(draft))
context = build_section_prompt_context(
    project_id=project_id,
    chapter=chapter,
    profile=profile,
    draft_content=draft,
)
prompt = render_section_prompt(profile, context)
prompt = enforce_prompt_budget(prompt, profile.max_prompt_chars)
```

### 5.8 与现有“自定义编写”能力的关系

当前编辑器已提供单章节“自定义编写”入口，用户可以在弹窗中输入本章补充要求。前端还会根据章节标题、用途、响应点、评分项、风险点和写作计划生成不同 placeholder，例如：

- 安全/应急类：提示补齐责任体系、危险源辨识、应急预案等；
- 质量/检验类：提示补齐质量保证体系、工序检验、第三方检测等；
- 进度/工期类：提示补齐节点工期、资源投入、偏差纠偏等；
- 资质/业绩类：提示补齐证书、业绩、附件索引，并提醒敏感编号和日期占位；
- 商务/报价类：提示不得编造金额、单价和工程量；
- 表格类：提示补齐表格字段、责任部门、完成时限和可量化承诺。

这部分能力应保留，并纳入 prompt 分级瘦身方案，而不是被新 profile 体系覆盖掉。

#### 5.8.1 当前实现风险

现有前端逻辑主要是：

```text
自定义编写弹窗 -> setChapters() 追加 writing_notes -> 用户点击生成本章正文
```

但当前单章后台生成已改为创建 Celery 任务：

```text
createSectionGenerationTask(items=[section_id, title, order_index, volume_type, target_words])
Celery worker -> list_bid_sections(project_id) -> 从数据库读取章节
```

如果自定义要求只停留在前端本地 `writing_notes`，且没有先保存到数据库或随 task item 一起提交，后台 worker 可能读不到用户刚输入的自定义要求。这会造成用户以为“加入写作要求”已生效，但模型实际没有使用。

这是本方案必须一起解决的 P0 兼容点。

#### 5.8.2 自定义要求在新体系中的定位

自定义编写要求不应成为独立的大 prompt，也不应绕过章节 profile。推荐定位为：

```text
Prompt Profile 决定上下文预算和事实来源
用户自定义要求决定本章补强方向和输出偏好
安全边界和事实边界始终优先于用户自定义要求
```

优先级顺序：

1. 系统安全边界：不得编造金额、证书编号、人员、日期、业绩、报价等。
2. 泰昌/辽宁/河北豪乾资料边界。
3. 已确认投标字段和正式检查约束。
4. Prompt profile 的上下文预算和生成方式。
5. 用户自定义写作要求。
6. 默认章节写作计划和 placeholder 示例。

如果用户自定义要求与事实边界冲突，例如“直接填一个报价”“编一个类似业绩”“补一个证书编号”，系统必须降级为：

```text
客户确认后填写 / 【待补充：...】
```

而不是照做。

#### 5.8.3 数据结构建议

将用户输入从普通 `writing_notes` 升级为结构化 metadata，便于任务传递、审计和导出前复核。

建议章节 metadata：

```json
{
  "generation_options": {
    "custom_instruction": "补齐组织机构职责、责任部门和证明材料索引。",
    "custom_instruction_source": "bid_editor_modal",
    "custom_instruction_created_at": "2026-06-25T14:30:00+08:00",
    "custom_instruction_profile_hint": "simple_plan",
    "custom_instruction_risk_level": "normal"
  }
}
```

批量任务 item metadata 可冗余保存一份快照：

```json
{
  "custom_instruction": "补齐组织机构职责、责任部门和证明材料索引。",
  "prompt_profile": "simple_plan"
}
```

这样即使章节在生成期间被编辑，当前任务仍能追溯当时使用的要求。

#### 5.8.4 传递路径要求

必须保证以下任一路径成立：

1. 用户点击“加入写作要求”后立即调用 `saveBidSection()` 持久化章节 metadata；
2. 或创建单章/批量任务时把 `custom_instruction` 放入 task item metadata；
3. 或两者都做：章节持久化作为长期状态，task item metadata 作为本次任务快照。

推荐第三种，原因：

- 用户刷新页面后还能看到自定义要求；
- 任务回放和问题排查能看到当次使用的要求；
- partial 续写时可以沿用或裁剪该要求；
- 后续正式检查可以识别用户要求是否引入人工确认字段。

#### 5.8.5 与 Prompt Profile 的组合规则

| 场景 | Profile | 自定义要求处理 |
| --- | --- | --- |
| 简单章节 + 自定义要求 | `simple_plan` | 保持轻量上下文，将用户要求放入“本章补强要求” |
| 技术参数章节 + 自定义要求 | `technical_parameter` | 保留结构化参数/RAG，用户要求只能补强表格字段和解释维度 |
| 表格章节 + 自定义要求 | `structured_table` | 将用户要求转成表格列、行、复核项，不让模型长篇自由发挥 |
| 报价章节 + 自定义要求 | `price_sensitive` | 只允许说明口径和人工复核，不允许生成金额 |
| partial 续写 + 自定义要求 | `continuation_slim` | 只带草稿末尾、用户要求摘要和关键事实，不带完整资料候选 |

#### 5.8.6 前后端提示词来源收敛

当前前端 placeholder 通过正则判断章节类型，后端也会通过章节信息判断 profile。长期看这会产生两套分类逻辑漂移。

建议演进为：

```text
后端 profile policy 是唯一分类来源
前端只展示后端返回的 profile label、默认建议和风险提示
```

短期可先保留前端 placeholder，但需要：

- 把明显偏“施工项目”的默认示例改成电缆保护管物资投标口径；
- 对商务/报价/授权/签章类 placeholder 明确“不得编造，需人工确认”；
- 在保存自定义要求时记录 `profile_hint`，后端最终分类仍以 `section_prompt_policy` 为准。

#### 5.8.7 验收口径

1. 单章“自定义编写”输入后，刷新页面仍可追溯该要求。
2. 单章后台生成任务能在 metadata 中看到本次使用的 `custom_instruction`。
3. 批量生成如果章节已有自定义要求，worker 必须使用该要求。
4. partial 续写时，自定义要求不丢失，但会被 slim prompt 摘要化。
5. 用户要求不得突破事实边界；报价、证书、人员、日期、业绩等未确认字段仍必须占位或提示人工确认。

## 6. 慢流保护与自适应调度

### 6.1 当前问题

当前流式请求行为：

- idle timeout：45 秒没有 token 才停；
- wall timeout：章节流式输出超过 300 秒才停；
- 如果已经产生少量 token，就不会重试，只保存 partial 草稿。

问题在于：当模型每几十秒吐少量 token 时，idle timeout 不触发，系统会一直等满 300 秒。

### 6.2 新增吞吐指标

每个 `bid_generation_task_items.metadata` 建议记录：

```json
{
  "prompt_profile": "simple_plan",
  "prompt_chars": 4200,
  "model_provider": "deepseek",
  "model": "deepseek-v4-flash",
  "first_token_latency_ms": 12000,
  "chars_at_60s": 220,
  "chars_at_90s": 360,
  "chars_per_minute": 240,
  "slow_stream": false,
  "slow_stream_reason": null,
  "timeout_code": null,
  "retry_policy": {
    "attempt": 1,
    "max_attempts": 2,
    "next_profile": null
  }
}
```

现有 `bid_generation_task_items` 已有 `metadata jsonb`，不需要新增表结构即可先落地。

### 6.3 慢流判定

建议阈值配置化，默认规则：

| 检查点 | 判定 |
| --- | --- |
| 首 token 超过 30 秒 | 标记 `first_token_slow` |
| 60 秒输出少于 120-180 字 | 标记 `slow_stream_candidate` |
| 90 秒输出少于 250-300 字 | 触发慢流保护 |
| 180 秒输出仍低于目标 30% | 触发 partial/续写策略 |
| 300 秒 | 兜底墙钟超时，不作为常规控制手段 |

注意：阈值不能一刀切。`structured_table` 和 `price_sensitive` 本来目标较短，应按 profile 调整。

### 6.4 慢流处理策略

当触发慢流：

1. 保存当前草稿。
2. 将 item 标为 `partial_generated` 或新增更明确的 `slow_partial`。
3. 如果草稿低于目标 30%，自动重新排队一次，使用 `continuation_slim`。
4. 当前任务全局连续慢流超过阈值时，调度器降低并发。
5. 两次仍慢的章节进入 `needs_review` 或 `partial_generated`，不无限重试。

### 6.5 自适应并发策略

新增调度策略函数：

```python
resolve_section_generation_concurrency(task) -> int
```

输入：

- 最近 N 个 item 的完成/慢流/超时状态；
- 当前活跃 item 吞吐；
- provider/model；
- 用户/环境配置的最大并发。

建议默认：

| 状态 | 并发 |
| --- | ---: |
| 初始 | 2 |
| 最近 5 个均正常完成 | 升到 3 |
| 最近 2 个慢流或超时 | 降到 1 |
| DeepSeek 连续慢流 | 保持 1，提示模型服务输出慢 |
| Qwen/其他模型稳定 | 可按配置升到 2-3 |

不要让前端决定并发。前端只显示当前调度状态。

### 6.6 调度状态

任务级 metadata 建议增加：

```json
{
  "scheduler_policy": "adaptive_v1",
  "current_concurrency": 1,
  "max_concurrency": 3,
  "slow_stream_count": 8,
  "timeout_count": 12,
  "last_policy_change": "reduce_concurrency",
  "policy_message": "模型输出变慢，已自动降为单路续写"
}
```

## 7. Partial 草稿续写闭环

### 7.1 状态语义

当前 `partial_generated` 容易被理解为失败。建议明确语义：

| 状态 | 用户文案 | 后续动作 |
| --- | --- | --- |
| `queued` | 排队中 | 等待调度 |
| `generating` | 正在编写 | 正常写作 |
| `slow_stream` 或 metadata 标记 | 模型输出较慢 | 系统准备降并发/续写 |
| `partial_generated` | 已保存草稿，待续写 | 可自动或手动续写 |
| `done` | 已完成 | 可编辑/导出 |
| `needs_review` | 需人工复核 | 人工确认或单章重写 |

如果暂不新增数据库状态，可先在 metadata 中区分：

```json
{
  "partial_reason": "slow_stream",
  "next_action": "auto_resume_with_slim_prompt"
}
```

### 7.2 续写 prompt

续写必须短，不再携带完整资料候选。

包含：

- 章节标题；
- 当前目标字数；
- 当前草稿估算字数；
- 草稿末尾 1000-1500 字；
- 关键事实摘要；
- 未完成小标题或缺口；
- “只追加，不重写标题，不重复已有内容”的硬约束。

不包含：

- 全量企业资料候选；
- 全量 RAG；
- 长篇企业画像；
- 全量评分项列表。

### 7.3 自动续写限制

| 条件 | 动作 |
| --- | --- |
| 草稿低于目标 30% 且 attempt < 2 | 自动续写一次 |
| 草稿达到目标 70% | 输出收束段，不继续长篇补写 |
| 连续两次 slow partial | 停止自动续写，转人工复核 |
| price/附件类章节 partial | 默认不自动长篇续写，只生成模板/占位 |

## 8. 前端体验方案

### 8.1 顶部批量进度

目录模式顶部建议显示：

```text
全部章节 185 | 需生成 144 | 已完成 76 | 正在写 3 | 排队 6 | 草稿待续写 59 | 模型慢流 12 | 当前并发 1
```

如调度器降并发，显示：

```text
模型输出变慢，系统已自动降并发并保存草稿，后续章节将用轻量续写策略继续。
```

### 8.2 行级状态

| 当前技术状态 | 推荐文案 |
| --- | --- |
| `generating` 且吞吐正常 | 正在编写 |
| `generating` 且慢流 | 模型输出较慢 |
| `partial_generated` | 草稿已保存，可续写 |
| `partial_reason=slow_stream` | 模型超时，已保存草稿 |
| `queued` 且调度器降并发 | 排队中，等待低并发续写 |

### 8.3 操作入口

建议增加：

- `续写本章`
- `批量续写草稿`
- `只导出已完成草稿`
- `停止并保存当前进度`
- `查看慢流原因`

这些按钮不需要一次全部做完，但“批量续写草稿”和“停止并保存当前进度”应进入 P0。

### 8.4 完成章节的“篇幅偏长”语义

当前线上页面中，“篇幅偏长 2003/1100字”来自前端 `chapterWordMeta()` 的规则：

```text
如果章节已生成，且实际字数 > 目标字数 * 1.35，则显示“篇幅偏长”
```

这不是失败状态，也不代表必须重写。但它现在和“已完成”占用同一个状态胶囊，客户会自然理解成：

```text
已经完成了，为什么还提示有问题？
是不是还要重写？
既然要重写，为什么不能一次写好？
```

这个体验判断是合理的，必须调整。

推荐改法：

| 当前表现 | 问题 | 推荐表现 |
| --- | --- | --- |
| `篇幅偏长 2003/1100字` 单独显示 | 像失败状态，暗示必须重写 | `已完成 · 偏长 2003/1100字` |
| 只有 `重写正文` | 容易让用户以为要推翻已有正文 | 增加 `压缩到目标`，保留 `重新生成` 为次级危险操作 |
| 目标字数只做事后提示 | 模型容易超出后再要求用户处理 | 生成 prompt 增加 hard max；完成后超阈值自动进入可选压缩 |
| 核心章节也简单按 1.35 判偏长 | 核心章节可能确实需要展开 | 按 profile 使用不同阈值，核心技术/资信章节可放宽 |

建议把状态拆成两层：

```text
生成状态：未生成 / 正在编写 / 草稿待续写 / 已完成 / 生成失败
质量提示：偏短 / 偏长 / 需表格 / 需图文 / 需业绩 / 需复核
```

完成章节的偏长处理不应默认“重写”，而应提供三种动作：

1. `接受当前篇幅`：核心章节或客户认可时不再强提示。
2. `压缩到目标`：基于现有正文做缩写，保留事实和小标题，不重新生成整章。
3. `重新生成`：明确提示会覆盖当前正文，并提供版本回退。

后端可复用现有 AI 编辑能力中的 `shorten` 动作，新增目标字数参数和事实保留约束：

```text
在不改变事实、不删除必要响应点、不编造新内容的前提下，将本章压缩到约 N 字。
```

验收口径：

1. 已完成章节即使偏长，也必须明确显示“已完成”。
2. 偏长不再默认引导“重写正文”，优先引导“压缩到目标”。
3. 生成时按 profile 设置目标字数和 hard max，减少事后大面积偏长。
4. 核心章节、结构表格章节、附件索引章节使用不同长度阈值。

### 8.5 目录“更多”菜单操作闭环

线上页面菜单项已经存在：

```text
自定义编写 / 新增子章节 / 修改标题 / 上移章节 / 下移章节 / 删除章节
```

但菜单存在不止“能不能点”的问题，更关键是点完后是否符合客户预期、是否污染正式目录。

本轮线上真实回归结论见第 15 节。这里先给出必须收口的产品与技术规则：

| 操作 | 当前风险 | 推荐规则 |
| --- | --- | --- |
| 自定义编写 | 目前前端只追加本地 `writing_notes`，后台 Celery 可能读不到 | 输入后立即保存到章节 metadata，并写入 task item metadata 快照 |
| 新增子章节 | 直接创建 `新增章节`，没有先输入标题；新增后可能不可见 | 先弹窗输入标题、分册、章节类型；保存后滚动并高亮 |
| 新增子章节 | 在技术筛选下新增，却没有继承父章节 `volume_type` | 默认继承父章节分册、重要性和基础 writing plan |
| 新增子章节 | 给叶子章节新增子节点后，父章节立即变成“结构容器” | 如果父章节已有正文或写作目标，必须二次确认如何处理原正文 |
| 修改标题 | 功能可用，但标题修改会同步改正文第一个 `##` 标题 | 应保留版本记录，避免误改正式标题无痕迹 |
| 上移/下移 | 只有一个兄弟节点时禁用是合理的，但缺少原因提示 | 禁用态加 tooltip；移动后必须保存并刷新顺序 |
| 删除章节 | 文案写“只影响当前页面草稿”，但已入库 UUID 会真实删除后端数据 | 文案必须改为“将从项目中删除”；提供撤销或回收站 |

新增章节不应默认为“商务”或 `None` 分册。建议 `createBlankChapter()` 和 `addChapter()` 至少继承：

```json
{
  "volume_type": "父章节 volume_type",
  "priority": "父章节 priority 或 medium",
  "metadata.writing_plan": "按父章节 profile 派生",
  "source": "manual_outline_edit"
}
```

对叶子章节新增子章节时，必须提示：

```text
当前章节已有正文/目标字数。新增子章节后，本章将变为结构容器，原正文可能不再作为叶子正文生成。
请选择：取消 / 保留本章正文作为概述 / 将本章正文迁移为第一个子章节。
```

## 9. 后端实施方案

### 9.1 新增模块

```text
backend/ai/section_prompt_policy.py
backend/services/section_generation_policy.py
```

职责：

- `section_prompt_policy.py`：章节分类、上下文预算、prompt profile。
- `section_generation_policy.py`：慢流判定、自适应并发、重试/续写策略。

### 9.2 改造点

| 文件 | 改造内容 |
| --- | --- |
| `backend/ai/section_writer.py` | 将 `build_section_prompt()` 拆成 profile-based prompt；续写 prompt 改为 slim 模式 |
| `backend/ai/qwen_client.py` | 流式调用增加吞吐检查 hook 或暴露进度回调 |
| `backend/services/section_generation.py` | 生成 summary 中返回 prompt profile、吞吐指标、partial reason |
| `backend/tasks/section_tasks.py` | flush progress 时记录 metadata；调度时调用自适应并发策略 |
| `backend/db/supabase_repo.py` | 保证 item metadata 可原子更新和同步到 snapshot |
| `frontend/src/pages/BidEditor/index.tsx` | 显示 partial/slow/concurrency 统计和续写入口 |

### 9.3 不建议的做法

1. 不建议简单把 wall timeout 从 300 秒改到 600 秒，会加重“卡死”感。
2. 不建议完全取消并发，会牺牲正常情况下的速度。
3. 不建议把所有章节 prompt 统一缩短，会伤害技术/资信核心章节质量。
4. 不建议在前端本地维护复杂状态机，应以后端任务状态为准。

## 10. 实施计划

### Phase 0：线上止血

目标：让客户测试不再持续触发 3 路慢流。

动作：

1. 线上临时设置 `SECTION_GEN_CONCURRENCY=1` 或 `2`。
2. 当前任务如已产生大量 partial，停止后重开，或只对 partial 分批续写。
3. 告知客户“草稿已保存，系统将续写”，避免误认为数据丢失。

验收：

- 新任务不再连续出现大面积 300 秒超时。
- 前端能看到任务继续推进。

### Phase 1：可观测与慢流保护

目标：不再盲等 300 秒。

动作：

1. item metadata 记录 prompt profile、prompt chars、首 token、60/90 秒输出、chars/min。
2. 增加慢流判定。
3. 触发慢流时保存草稿并释放并发槽。

验收：

- 任一 item 不应在 90 秒低吞吐情况下继续占满 300 秒。
- run 记录能说明慢流数量、原因和处理动作。

### Phase 2：Prompt 分级瘦身

目标：大量重复小节走轻量 prompt，核心章节保留事实/RAG。

动作：

1. 新增 prompt profile 分类。
2. 拆分泰昌事实摘要。
3. 不同 profile 使用不同 RAG/asset/fact budget。
4. continuation 使用 slim prompt。
5. 打通现有“自定义编写”入口：用户输入必须持久化到章节 metadata，并作为任务 item metadata 快照进入 Celery。
6. 前端默认 placeholder 与后端 prompt profile 收敛，避免前端一套分类、后端一套分类长期漂移。

验收：

- `simple_plan` prompt 字符显著低于当前通用 prompt。
- 技术参数章节仍能命中 CPVC/MPP 报告编号和关键参数。
- 续写章节不重复标题、不重写已有内容。
- 单章自定义要求能被后台生成任务实际使用；刷新页面后不丢失。

### Phase 3：自适应并发

目标：速度和稳定性兼得。

动作：

1. 默认并发从固定 3 改为 policy 输出。
2. 根据最近窗口慢流/成功动态升降。
3. 任务 metadata 展示 current concurrency 和 policy message。

验收：

- DeepSeek 慢时自动降并发。
- 连续正常后可恢复并发。
- 并发变更不需要前端参与。

### Phase 4：前端体验闭环

目标：客户清楚知道发生了什么。

动作：

1. 顶部进度增加 completed/running/queued/partial/slow/concurrency。
2. 行级文案区分“正在编写”“模型输出较慢”“草稿已保存，可续写”。
3. 增加批量续写草稿入口。
4. 下载前提示 partial 草稿仍只能作为草稿版。
5. 将“已完成”和“偏长/偏短”等质量提示拆开展示。
6. 增加“压缩到目标”动作，避免客户把偏长理解成必须重写。
7. 收口目录“更多”菜单：新增前确认标题和分册，删除前明确真实删除，移动后保存并高亮。

验收：

- 客户不再看到多个章节长时间只有“正在编写”。
- partial 章节有明确下一步。
- 已完成章节即使偏长，也显示为已完成，并给出可选压缩。
- 新增/改名/移动/删除章节后，页面刷新和接口查询结果一致。
- 技术视图下新增技术子章节后，该章节仍出现在技术视图，不会被归到商务或隐藏。

## 11. 验收标准

### 11.1 技术验收

1. 单元测试覆盖章节 profile 分类。
2. 单元测试覆盖慢流判定和自适应并发。
3. 真实 DeepSeek 链路至少跑 20 个混合章节。
4. 阿里云真实项目跑一次批量生成或 partial 续写回归。
5. 生成 run 记录写入 `docs/development/runs/`。
6. 单章自定义编写要求必须进入章节 metadata 和 task item metadata，后台 Celery 生成可追溯。
7. 自定义要求与报价、证书、人员、日期、业绩等事实边界冲突时，模型不得照做编造。

### 11.2 性能验收

| 指标 | 目标 |
| --- | --- |
| 慢流章节占用时间 | 不再硬等 300 秒，90-120 秒内进入保护 |
| 简单章节平均 prompt 字符 | 比当前通用 prompt 降低 40% 以上 |
| 批量任务可见进度 | 30 秒内能看到状态变化或明确慢流提示 |
| partial 续写重复率 | 不重复标题、不大段重复已有正文 |
| 核心技术事实准确性 | CPVC/MPP 报告编号、规格、关键参数不丢失 |
| 自定义要求生效性 | 单章自定义要求在后台任务中可见，并影响生成结果 |

### 11.3 客户体验验收

1. 客户能看到“已完成/正在写/排队/草稿待续写/模型慢流”。
2. 长时间慢流时有清晰解释，而不是像系统卡死。
3. 客户可以继续下载草稿，但正式检查仍能识别 partial/缺口。
4. 页面刷新后任务状态可恢复。
5. 完成章节的“偏长/偏短”是质量提示，不再表现为失败或必须重写。
6. 用户能选择“接受当前篇幅 / 压缩到目标 / 重新生成”，且重新生成前有覆盖提示。
7. 目录结构编辑不会静默改变分册、叶子/容器语义或真实后端数据。

## 12. 风险与控制

| 风险 | 影响 | 控制 |
| --- | --- | --- |
| prompt 过度瘦身导致质量下降 | 简单章节变空泛，核心事实缺失 | profile 分级；技术/资信章节保留 RAG 和事实 |
| 自动续写导致重复内容 | DOCX 观感变差 | 续写只带草稿末尾，明确只追加不重复 |
| 自适应并发误判 | 降速或频繁抖动 | 使用最近窗口和最小保持时间，避免每章都变更 |
| 状态过多增加理解成本 | 用户看不懂 | 前端文案用业务语言，技术原因放详情 |
| metadata 膨胀 | DB 记录过大 | 只记录指标，不记录完整 prompt |

## 13. 推荐默认配置

线上测试环境：

```text
SECTION_GEN_CONCURRENCY=1
CELERY_WORKER_CONCURRENCY=2
SECTION_STREAM_WALL_TIMEOUT_SECONDS=240
SECTION_STREAM_IDLE_TIMEOUT_SECONDS=45
SECTION_STREAM_SLOW_CHECK_SECONDS=90
SECTION_STREAM_MIN_CHARS_AT_SLOW_CHECK=250
```

生产稳定后可调整：

```text
SECTION_GEN_CONCURRENCY=2
CELERY_WORKER_CONCURRENCY=3
```

是否允许升到 3，应以真实 DeepSeek 回归数据为准，不作为默认演示配置。

## 14. 需要进入任务总账的 P0

任务名称：

```text
批量章节生成可靠性与 Prompt 分级瘦身
```

验收口径：

1. 批量章节生成不再因慢流长时间假死。
2. 简单章节、技术章节、资信章节、表格章节、partial 续写使用不同 prompt profile。
3. 系统能自动识别慢流并释放并发槽。
4. 前端清楚展示 partial、慢流和当前并发。
5. 阿里云真实项目完成一次回归记录。

## 15. 2026-06-25 线上目录操作真实回归

环境：

```text
阿里云测试环境
项目：d346ec62-8843-4cfd-b68c-e3fb1d215181
页面：/bid-editor?projectId=d346ec62-8843-4cfd-b68c-e3fb1d215181
```

### 15.1 实测步骤与结果

| 编号 | 操作 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| R1 | 打开 `23.1.4 组织机构` 行的“更多”菜单 | Chrome 真实页面 | 菜单存在，含自定义编写、新增子章节、修改标题、上移、下移、删除 |
| R2 | 在技术视图下点击“新增子章节” | Chrome 页面 + API 查询 | 真实创建成功，总章节 185 -> 186 |
| R3 | 查看新增章节可见性 | Chrome 页面 | 技术视图下新增章节不可见，切到“全部”后才显示为 `23.1.4.1 新增章节` |
| R4 | 查询新增章节 metadata | API 查询 | `volume_type=None`，未继承父章节技术分册 |
| R5 | 修改标题为 `测试临时章节-自动回归` | Chrome 页面 + API 查询 | 修改成功并持久化 |
| R6 | 再新增一个临时兄弟章节 | Chrome 页面 + API 查询 | 真实创建成功，总章节 186 -> 187 |
| R7 | 调换两个临时兄弟章节顺序 | API 调用同一 reorder 接口 | 顺序从 `[自动回归, 新增章节]` 变为 `[新增章节, 自动回归]` |
| R8 | 删除两个临时章节并清理 | API 删除 + API 查询 | 总章节恢复 185，临时章节 0，`组织机构` 下子节点 0 |

说明：

- R1-R6 通过 Chrome 真实页面完成。
- R7 使用同一线上 reorder 接口验证底层移动能力；Chrome 辅助树在第二次新增后短暂返回空，未继续用 UI 坐标冒险移动正式章节。
- R8 为避免污染客户测试项目，使用线上删除接口完成清理。

### 15.2 缺陷与任务优先级

| 优先级 | 编号 | 问题 | 影响 | 建议处理 |
| --- | --- | --- | --- | --- |
| P0 | SG-UX-001 | 完成章节显示 `篇幅偏长`，但未同时明确“已完成” | 客户误以为章节失败或必须重写 | 状态与质量提示拆分；显示 `已完成 · 偏长` |
| P0 | SG-UX-002 | 偏长后的主要动作是“重写正文”，缺少“压缩到目标” | 客户质疑为什么不能一次完成 | 增加基于现有正文的压缩动作；重新生成降为次级危险操作 |
| P0 | SG-DATA-001 | 技术视图下新增子章节未继承父章节 `volume_type`，API 显示 `None` | 新章节被统计到商务/全部，技术视图不可见 | 新增子章节默认继承父章节分册和当前筛选上下文 |
| P0 | SG-DATA-002 | 给叶子章节新增子章节后，父章节立即变成“结构容器” | 静默改变原章节正文生成和导出语义 | 新增前二次确认；提供保留概述/迁移正文/取消 |
| P0 | SG-DATA-003 | 删除弹窗文案称“只影响当前页面草稿”，但已入库 UUID 会真实删除后端数据 | 严重误导，可能造成客户误删正式目录 | 已完成：删除文案改为真实删除提示；后端删除章节子树；页面内提供最近一次删除撤销 |
| P0 | SG-AI-001 | 自定义编写只追加前端本地 `writing_notes`，后台任务可能读不到 | 用户以为要求生效，实际生成未采用 | 立即持久化到章节 metadata，并写入 task item metadata |
| P1 | SG-UX-003 | 新增子章节无标题输入，先创建通用 `新增章节` | 目录污染，客户需要再改名 | 新增前弹窗输入标题、分册、章节类型 |
| P1 | SG-UX-004 | 新增后没有明显高亮/滚动/筛选提示 | 用户以为点击无效 | 新增后自动切换到可见筛选、高亮 3 秒并显示 toast |
| P1 | SG-UX-005 | 上移/下移禁用时没有原因提示 | 用户不知道为什么不能移动 | 禁用态 tooltip 显示“当前没有同级章节可移动” |
| P1 | SG-REG-001 | 移动操作需要 UI 级回归补测 | 本轮只验证了同一后端 reorder 接口 | 修复新增分册继承后，用两个临时同级章节做完整 UI 移动回归 |
| P2 | SG-UX-006 | 菜单同时有“新增子章节”，但缺少“新增同级章节” | 用户容易把章节层级建错 | 增加“新增同级章节”，并清晰区分层级 |

### 15.3 对实施顺序的调整

这轮回归后，P0 不应只做生成吞吐。目录编辑和完成状态语义也必须进入同一轮，因为它们直接影响客户对“系统是否专业”的判断。

推荐 P0 顺序：

1. [x] 完成状态与长度质量提示拆分，新增“压缩到目标”。本地已实现并通过真实回归，见 15.4。
2. [x] 自定义编写持久化，确保用户单章要求进入后台任务。本地已实现并通过 API + 浏览器真实回归，见 15.5。
3. [x] 新增子章节继承父章节分册，并在当前筛选中可见。本地已实现并通过 API + 浏览器真实回归，见 15.6。
4. [x] 叶子章节转结构容器前增加确认和正文处理策略。本地已实现并通过 API + 浏览器真实回归，见 15.7。
5. [x] 删除真实提示与撤销/回收站兜底。本地已实现并通过 API + 浏览器真实回归，见 15.8。
6. Prompt profile、慢流保护、自适应并发按前文 Phase 1-3 实施。

### 15.4 2026-06-25 本地实施与回归：SG-UX-001/002

本轮已完成第一项 P0：

- `SG-UX-001`：完成章节主状态固定为 `已完成 N字`；`偏长/偏短` 改为独立质量提示，不再覆盖完成状态。
- `SG-UX-002`：偏长章节新增 `压缩到目标` 动作；原 `重写正文` 文案收口为 `重新生成`。
- 压缩动作复用已有 AI 编辑 `shorten`，保存仍走 `saveBidSection`，不新增一套章节生成后端任务，避免技术债。
- `shorten` 输入上限从 5000 字放宽到 12000 字；扩写、润色、正式化仍保持 5000 字，避免普通编辑输入成本失控。
- 压缩确认框改为受控 `<Modal>`，本次新增功能不触发 Ant Design 静态弹窗 warning。

真实回归记录：

```text
docs/development/runs/run_20260625_local_bid_editor_length_status_regression.md
output/playwright/local_bid_editor_length_status_final_20260625.png
```

关键验收结果：

| 验收项 | 结果 |
| --- | --- |
| 目录行状态 | `已完成 1672字` + `偏长 1672/1000字` 分开展示 |
| 偏短提示 | `已完成 608字` + `偏短 608/950字` 分开展示 |
| 偏长动作 | `重新生成`、`压缩到目标`、`预览`、`更多` 均存在 |
| 更多菜单 | 自定义编写、新增子章节、修改标题、上下移、删除仍存在 |
| 压缩弹窗 | 显示当前字数、目标字数，并说明不会重新生成整章 |
| 浏览器 console | 新会话 0 errors、0 warnings |
| 真实 API 压缩 | 6198 字临时章节通过 `shorten` 压缩并保存；临时章节已删除 |

### 15.5 2026-06-25 本地实施与回归：SG-AI-001

本轮已完成第二项 P0：

- `SG-AI-001`：单章“自定义编写”从静态 `Modal.confirm` 改为受控弹窗，用户输入不再只写入前端内存。
- 保存自定义要求时立即调用 `saveBidSection()`，把要求追加到章节 `writing_notes`，并写入 `metadata.custom_writing`。
- 单章生成和批量生成创建 task item 时，会携带 `writing_notes` 与 `custom_writing` 快照。
- 后端 `create_bid_generation_task()` 的 item 归一化与 `bid_generation_task_items` 行同步保留 `metadata`，避免任务明细丢失用户要求。
- 后端现有 `build_section_prompt()` 已读取章节 `writing_notes`，因此 Celery 从数据库读取章节时可拿到该要求。

真实回归记录：

```text
docs/development/runs/run_20260625_local_custom_writing_persistence_regression.md
```

关键验收结果：

| 验收项 | 结果 |
| --- | --- |
| API 持久化 | 临时章节写入 `writing_notes` 和 `metadata.custom_writing`，读取一致 |
| 任务快照 | `section-generation-tasks` 使用 `autoStart=false` 创建真实任务，item metadata 保留 `writing_notes/custom_writing` |
| 任务清理 | 回归任务已取消，临时章节已删除 |
| 浏览器流程 | 登录、搜索临时章节、打开“更多 -> 自定义编写”、输入并保存均跑通 |
| 页面菜单 | 编写章节、自定义编写、添加章节、上移章节、下移章节、修改标题、删除章节均存在 |
| 构建检查 | `npm run build` 通过；`python3 -m py_compile backend/db/supabase_repo.py` 通过 |
| 遗留告警 | 浏览器 console 出现 Ant Design 5 静态 `message.*` context warning，功能不阻断，建议后续统一改为 `App.useApp()` |

下一项 P0：

```text
SG-DATA-001：新增子章节继承父章节分册，并在当前筛选中可见。
```

### 15.6 2026-06-25 本地实施与回归：SG-DATA-001

本轮已完成第三项 P0：

- 前端新增章节时会根据父章节或当前分册筛选写入 `metadata.volume_type`、`volume_name`、`export_group` 和 `document_role`。
- 子章节默认继承父章节分册；如果没有父章节，则在技术/商务筛选下按当前筛选创建对应分册章节。
- 子章节继承父章节 `priority`，并在 metadata 中记录 `inherited_from_parent_id` 和 `created_from_active_volume`。
- 后端 `upsert_bid_section()` 增加兜底：客户端未传有效分册 metadata，且存在父章节时，从父章节 metadata 继承分册字段。
- 后端继承时会同步修正 `export_group`，避免出现 `volume_type=technical` 但 `export_group=其他文件` 的不一致状态。

真实回归记录：

```text
docs/development/runs/run_20260625_local_child_section_volume_inheritance_regression.md
```

关键验收结果：

| 验收项 | 结果 |
| --- | --- |
| 后端兜底 | 默认标题 `新增章节` 且不传 metadata 时，子章节从技术父章节继承 `volume_type=technical` |
| 派生字段 | 子章节 `volume_name=技术标`、`export_group=技术标文件`、`document_role=正文` |
| 浏览器流程 | 登录、进入标书编辑页、切换技术筛选、对临时技术父章节点击“添加章节”均跑通 |
| 当前筛选可见 | 新增后技术计数 `126 -> 127`，左侧技术视图显示 `29.1 新增章节` |
| 右侧标签 | 新增子章节详情区显示 `技术标 / 技术标` |
| 清理 | 临时父子章节均已删除，章节数恢复 206 |
| 构建检查 | `npm run build` 通过；`python3 -m py_compile backend/db/supabase_repo.py` 通过 |

下一项 P0：

```text
SG-DATA-002：叶子章节转结构容器前增加确认和正文处理策略。
```

### 15.7 2026-06-25 本地实施与回归：SG-DATA-002

本轮已完成第四项 P0：

- 对已有正文或明确目标字数的叶子章节点击“添加章节”时，先弹出“新增子章节前确认”，不再静默把原章节变成结构容器。
- 确认弹窗提供两种策略：保留本章正文作为父章节概述，或将本章正文迁移到新子章节；无有效正文时迁移选项自动禁用。
- 父章节转容器后写入 `metadata.section_role=container`、`leaf_generation=false`、`container_conversion_mode`、`container_content_policy` 和转换来源/时间。
- 迁移策略会把原正文改挂到首个新子章节，并记录 `migrated_from_parent_id`、`migrated_from_parent_title`、`migration_source` 和 `migrated_at`。
- 子章节继续继承父章节分册和写作计划，避免本轮修复破坏 SG-DATA-001 的分册可见性。

真实回归记录：

```text
docs/development/runs/run_20260625_local_leaf_to_container_confirmation_regression.md
```

关键验收结果：

| 验收项 | 结果 |
| --- | --- |
| 构建检查 | `npm run build` 通过；仅保留 Vite chunk size / 动态导入既有 warning |
| 保留概述路径 | 浏览器弹窗确认后，父章节写入 `container_conversion_mode=keep_parent_summary`，正文保留在父章节 |
| 保留路径子章节 | 新子章节从父章节继承 `volume_type=technical`、`volume_name=技术标`、`export_group=技术标文件` |
| 迁移正文路径 | 浏览器选择“将本章正文迁移到新子章节”后，父章节转为结构容器概述 |
| 迁移路径子章节 | 新子章节正文保留原父章节正文，并写入 `migrated_from_parent_id` 等迁移 metadata |
| 清理 | 4 个临时父子章节均已删除，`regression_case=leaf_to_container_confirmation` 剩余 0 |
| 浏览器 console | 本功能操作完成后 `console error` 为 0；登录成功提示仍会触发项目既有 Ant Design 静态 `message.*` context warning |

下一项 P0：

```text
SG-DATA-003：删除真实提示与撤销/回收站兜底。
```

### 15.8 2026-06-25 本地实施与回归：SG-DATA-003

本轮已完成第五项 P0：

- 删除章节确认弹窗不再提示“只影响当前页面草稿”，改为明确“从当前项目中删除”和“同步删除后端章节数据”。
- 删除父章节时，后端 `delete_bid_section()` 会基于项目章节树计算 descendant IDs，并一次性删除整棵章节子树，避免前端看似删除、数据库残留孤儿章节。
- 删除接口返回 `deleted_count`，用于真实链路验收删除数量。
- 前端删除成功后保留最近一次删除快照，在页面内显示“撤销删除”提示条。
- 撤销时按原 ID、父子关系和顺序恢复章节，并重新加载项目，保证 UI 与后端一致。
- 删除确认改为受控 `Modal`，避免本功能路径继续制造 Ant Design 静态 `Modal.confirm` warning。

真实回归记录：

```text
docs/development/runs/run_20260625_local_delete_subtree_undo_regression.md
```

关键验收结果：

| 验收项 | 结果 |
| --- | --- |
| 构建检查 | `npm run build` 通过；仅保留 Vite chunk size / 动态导入既有 warning |
| 后端语法 | `.venv/bin/python -m py_compile backend/db/supabase_repo.py backend/api/sections.py` 通过 |
| API 子树删除 | 创建临时父子章节后删除父章节，返回 `deleted_count=2`，父子 ID 剩余 0 |
| 浏览器确认文案 | 真实菜单点击删除后，弹窗显示真实项目删除、1 个子章节一并删除、后端同步删除和临时撤销说明 |
| 浏览器删除结果 | 页面章节数 `208 -> 206`，搜索结果 `1 / 208 -> 0 / 206` |
| 撤销恢复 | 点击“撤销删除”后页面章节数恢复 `208`，父子章节按原 ID 恢复 |
| 父子关系 | 撤销后子章节 `parent_id` 指向原父章节，`level=2` |
| 清理 | 回归临时父子章节已删除，章节数恢复 `206`，回归 metadata 剩余 0 |
| 浏览器 console | 受控删除/撤销路径完成后 `console error=0`；登录成功提示仍属于既有全局静态 `message.*` warning |

### 15.9 2026-06-25 本地实施与回归：SG-PROMPT-001

本轮已完成第六项 P0：

- 新增 `backend/ai/section_prompt_policy.py`，把章节生成拆分为 `simple_plan`、`fact_grounded`、`technical_parameter`、`structured_table`、`attachment_index`、`price_sensitive`、`continuation_slim` 七类 prompt profile。
- `build_section_prompt()`、补写 prompt 和 partial 续写 prompt 已按 profile 控制 RAG 条数、企业资料条数、事实包模式、列表输入上限和 prompt 字符预算。
- 续写 profile 不再加载章节级 RAG 与企业资料候选，仅保留草稿末尾、客户确认变量和最小事实边界，避免 partial 续写继续吃满大输入。
- `stream_bid_section()` 的首个 `start` 事件输出 `prompt_profile`、`prompt_chars`、`max_prompt_chars`、`rag_limit`、`asset_limit` 和 `fact_pack_mode`。
- Celery worker 接收 `start` 事件后写入 task item `metadata`，并同步到 legacy task JSON；PostgreSQL 原子更新函数已允许 `metadata` patch。

真实回归记录：

```text
docs/development/runs/run_20260625_sg_prompt_001_prompt_profile_budget.md
docs/rag/runs/run_20260625_sg_prompt_001_summary.md
docs/rag/runs/run_20260625_sg_prompt_001_incremental_summary.md
```

关键验收结果：

| 验收项 | 结果 |
| --- | --- |
| Prompt profile 单测 | `tests/test_section_prompt_policy.py` 5 passed |
| 章节生成相关回归 | `tests/test_section_prompt_policy.py tests/test_length_settings.py tests/test_section_generation_autoresume.py tests/test_postgres_schema_init.py` 21 passed |
| API/RAG 相关回归 | `tests/test_api_sections.py tests/test_section_prompt_policy.py tests/test_length_settings.py tests/test_section_generation_autoresume.py tests/test_rag_asset_scoring.py` 35 passed |
| DOCX/Celery 导出单测 | `tests/test_docx_export.py tests/test_celery_export_tasks.py` 48 passed |
| SQL 初始化 | `./scripts/init_postgres_schema.sh` 通过，`update_bid_generation_task_item_atomic` 已重建 |
| 真实单章生成 | 临时任务 `d2af70bd-2391-4303-ba99-cfebe019e557` completed，metadata 记录 `prompt_profile=simple_plan`、`prompt_chars=5000`、`rag_limit=1`、`asset_limit=1` |
| RAG 门禁 | Base + 泰昌专项增量回归 Gate PASS；泰昌专项 qwen3-rerank Recall@5/Top1/MRR 为 `100%/100%/1.000` |
| 完整 DOCX 链路 | 102/102 正文项目导出任务 `84af9199-f3cc-44ce-bf3f-9bb5c882cced` completed；正式门禁阻断项 0；图片 selected/inserted/failed 为 `23/23/0`；LibreOffice 字段刷新成功 |

下一项 P0：

```text
SG-SLOW-001：慢流提前保护与 partial 草稿释放并发槽。
```

### 15.10 2026-06-25 本地实施与回归：SG-SLOW-001

本轮已完成第七项 P0：

- `section_writer.stream_bid_section()` 增加 `_SectionStreamMonitor`，记录首 token 延迟、stream 字符数、chars/min、60/90 秒字符里程碑和慢流原因。
- 慢流保护支持 `SECTION_STREAM_SLOW_CHECK_SECONDS`、`SECTION_STREAM_MIN_CHARS_AT_SLOW_CHECK`、`SECTION_STREAM_FIRST_TOKEN_SLOW_SECONDS` 配置，并按 prompt profile 设置默认低吞吐阈值。
- 低吞吐章节抛出 `MODEL_STREAM_SLOW_TIMEOUT`，`generate_and_save_bid_section()` 透传 timeout metadata，Celery item 进入 `partial_generated` 并保存 partial 草稿。
- 生成任务 item metadata 已记录 `first_token_latency_ms`、`stream_elapsed_ms`、`stream_chars`、`chars_per_minute`、`slow_stream_reason`、`partial_chars` 和 `partial_words`，便于前端与任务列表解释卡顿原因。
- `backend/services/section_generation.py` 将图片 helper 改为函数内懒加载，修复服务层单测直接导入时的循环导入隐患。
- 本轮不做全局自适应并发降档；该项进入下一项 P0。

真实回归记录：

```text
docs/development/runs/run_20260625_sg_slow_001_slow_stream_protection.md
docs/rag/runs/run_20260625_sg_slow_001_summary.md
docs/rag/runs/run_20260625_sg_slow_001_incremental_summary.md
```

关键验收结果：

| 验收项 | 结果 |
| --- | --- |
| 后端编译检查 | `.venv/bin/python -m py_compile backend/ai/qwen_client.py backend/ai/section_writer.py backend/services/section_generation.py backend/tasks/section_tasks.py` 通过 |
| 慢流/续写单测 | `tests/test_section_generation_autoresume.py tests/test_section_prompt_policy.py` 13 passed |
| 章节/API 相关回归 | `tests/test_api_sections.py tests/test_section_generation_autoresume.py tests/test_section_prompt_policy.py tests/test_length_settings.py tests/test_postgres_schema_init.py` 30 passed |
| DOCX/Celery 导出单测 | `tests/test_docx_export.py tests/test_celery_export_tasks.py` 48 passed |
| 强制慢流真实任务 | 临时任务 `29c99120-38e9-4b3d-a67c-5eef6925dbd3` 进入 `partial_failed`，item 为 `partial_generated`，`timeout_code=MODEL_STREAM_SLOW_TIMEOUT`，partial 草稿已保存 |
| 正常阈值真实任务 | 临时任务 `41b912db-3d7a-4ca5-b8aa-1e64dbfcfe66` completed，`slow_stream=false`，`stream_chars=589` |
| 临时章节清理 | 两个回归临时章节均已通过 API 删除，`regression_case in ('sg_slow_001','sg_slow_001_normal')` 剩余 0 |
| RAG 门禁 | Base + 泰昌专项增量回归 Gate PASS；泰昌专项 qwen3-rerank Recall@5/Top1/MRR 为 `100%/100%/1.000` |
| 真实 stream 抽样 | `done=true`，contexts=5，assets=4，images=4 |

下一项 P0：

```text
SG-CONCURRENCY-001：自适应并发调度与任务级慢流窗口降档。
```

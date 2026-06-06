# 标书正文按章节生成生产整改待办清单

日期：2026-06-03

最近更新：2026-06-05，基于真实山西招标文件全流程下载验收，新增 DOCX 导出交付观感与格式模板整改 P0；此前基于真实“一键生成全文”复测结果补充 `partial_failed`、草稿不可见、自动续写中断、字数统计偏差、模型过度输出长期占用 worker、长任务轮询窗口过短、数据库迁移链缺口和历史僵尸任务清理问题。

范围：一键生成全文、按章节目录批量生成正文、Celery 章节子任务、DeepSeek 流式输出、章节正文落盘、前端任务进度展示、DOCX 导出格式与交付观感。

结论：当前问题不是单一模型慢、单一章节内容长或百炼 rerank 额度导致，而是正文生成链路缺少生产级任务系统能力。优先级应先处理任务状态、worker 租约、超时恢复、落盘边界，再处理 prompt、篇幅策略和前端体验。

## 优先级总览

| 优先级 | 待办 | 目标 | 建议负责人 |
| --- | --- | --- | --- |
| P0 | 重构章节任务状态模型 | 彻底解决 running 卡死、幽灵任务、并发槽位被占用 | 后端，基础版已完成 |
| P0 | 拆分任务 item 独立表 | 支持章节级 lease、重试、恢复、审计 | 后端 / 数据库，基础版已完成 |
| P0 | 建立 worker lease 与 heartbeat | worker 重启或断线后可自动回收任务 | 后端，基础版已完成 |
| P0 | 改造流式草稿保存与最终落盘边界 | 过程内容可恢复，最终正文必须有明确完成条件 | 后端，基础版已完成 |
| P0 | 加模型流墙钟超时和最后 token 超时 | 防止单章节无限占用 worker | 后端 / AI，基础版已完成 |
| P0 | 补齐取消、恢复、重试语义 | 取消后旧 worker 不得继续覆盖状态 | 后端，基础版已完成 |
| P0 | 正文生成粒度改为叶子小节级 | 章/节作为结构容器，最小小节独立生成 | AI / 后端 / 前端，基础版已完成 |
| P0 | partial_failed 自动续写与批量恢复闭环 | 草稿待续写不应让“一键生成全文”在中途停止 | 后端 / 前端，新增 |
| P0 | 草稿正文可见、续写、采纳闭环 | “草稿已保存”必须能被用户看到、续写或采纳 | 后端 / 前端，新增 |
| P0 | 目标字数硬约束与流式截流保存 | 避免章节持续超写并长期占用 worker | AI / 后端，基础版已完成 |
| P0 | 流式消费与任务状态持久化解耦 | 避免每 chunk 查库/写库拖慢 DeepSeek 流 | 后端，基础版已完成 |
| P0 | 前端轮询改成长任务友好模式 | 不再用固定 5 分钟/900 次判失败，支持刷新恢复后台任务 | 前端，基础版已完成 |
| P0 | 补齐 PostgreSQL 正式迁移链 | 将 `20260603` 章节任务 DDL 纳入新库初始化，避免新环境缺表/RPC | 后端 / 数据库，基础版已完成 |
| P0 | 协调任务异常失败回写 | `run_bid_section_generation()` 异常时写入业务终态，避免永久 `queued/running` | 后端，基础版已完成 |
| P0 | DOCX 导出交付观感与格式模板整改 | 按招标文件格式要求和投标文件惯例输出规整 Word，避免客户第一印象差和形式评审风险 | 后端 / 导出 / 产品，基础版已完成 |
| P1 | 增加任务 reconciler | 将超过 lease/心跳窗口的历史 `running/queued` 任务转为可恢复或失败态 | 后端，基础版已完成 |
| P1 | 补最小 E2E 长任务回归 | 覆盖上传、目录生成、30+ 章节全文生成、刷新恢复与导出 | 全栈，基础版已完成 |
| P1 | 可见字数统计口径与压缩改写 | 修正误导性统计，并对 too_long 内容提供压缩重写 | AI / 后端 / 前端 |
| P1 | 前端改为任务事件/状态面板 | 用户能判断是真在跑、慢、失败还是卡死 | 前端 |
| P1 | 增加可观测性与诊断日志 | 可定位每章耗时、首 token、末 token、保存点 | 后端 |
| P1 | 清理服务层循环依赖 | Celery、API、脚本启动路径一致 | 后端 |
| P1 | 隔离 RAG/rerank 降级策略 | rerank 额度耗尽不应影响正文任务可用性 | 后端 / AI |
| P2 | 优化 prompt 和篇幅补写策略 | 提升质量和稳定性，但不作为首要止血项 | AI |
| P2 | 完善演示模式与灰度开关 | 演示环境可控、可快速回退 | 全栈 |

## 2026-06-04 复盘新增 P0/P1

## 2026-06-05 真实 DOCX 下载验收新增 P0

### P0-新增 04 DOCX 导出交付观感与格式模板整改

#### 当前进展

2026-06-05 基础版已完成：

- 真实项目 `7dfcc318-c1f8-465d-abc3-d47ef0e355e7` 已跑通山西招标文件全流程并导出 DOCX。
- 导出文件：`outputs/Guo_Wang_Shan_Xi_Dian_Li_2026Nian_Di_Er_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Gong_Kai_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网山西电力2026年第二次物资协议库存公开招标采购招标文件.docx`。
- 服务端 LibreOffice 字段刷新成功，目录页码、页脚页码和总页数已刷新；问题不是页码字段未刷新，而是整体版式和模板交付观感不足。
- 原招标文件明确要求按第六章“投标文件格式”编写，并在形式评审中约束“未按招标文件规定的格式填写、内容不全或者关键字迹模糊无法辨认”风险。
- 当前主招标文件未发现明确写死“目录宋体几号、正文宋体几号”的条款，但格式仍需按招标文件格式和投标文件常用惯例默认规整。
- `backend/export/md_to_word.py` 默认模板调整为 `sgcc_power_grid`，正文改为宋体小四 `12pt`、固定 `28pt` 行距，表格改为宋体 `10.5pt`，并统一 docDefaults、Normal、列表和逐段 run 的中文字体。
- 页眉增加长度保护，避免长项目名溢出；页边距、页眉页脚距离改为环境变量可配置。
- `convert_md_to_word(..., return_report=True)` 返回 `template` 元数据；Celery 导出任务将 `docx_template` 写入 `bid_export_tasks.metadata`。
- 已用山西真实导出 Markdown 副本生成 DOCX 并结构化验证：正文宋体 `12pt`、A4、左右边距 `3.18cm`、页眉长度正常。
- 已重新生成当前山西项目下载 DOCX 并刷新页码字段。
- 回归测试：`PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_celery_export_tasks.py tests/test_smoke.py tests/test_api_sections.py -q`，41 passed。

#### 现象

用户下载生成 DOCX 后，标书文件和格式观感不规整。该问题属于客户第一印象和正式交付质量问题，不是普通 UI 美化。

当前 `backend/export/md_to_word.py` 的基础模板为：

- A4 页面；
- 正文仿宋小四 `12pt`，固定行距 `28pt`；
- 标题黑体，一级 `18pt`、二级 `16pt`、三级 `15pt`、四级 `12pt`；
- 页眉宋体 `9pt`，内容为“项目名投标文件”；
- 页脚宋体 `9pt`，内容为“第 X 页，共 Y 页”；
- 目录页由代码生成并通过 LibreOffice 刷新页码。

这些设置具备基础 Word 输出能力，但还不是面向客户正式提交的投标文件精排模板。尤其是封面、目录层级、正文宋体/仿宋选择、标题层级、表格样式、附件索引、页眉页脚内容、签章页和第六章格式表单保真度，都需要专项整改。

#### 整改要求

- 解析招标文件中的第六章“投标文件格式”和前附表/否决条款，提取格式约束、提交文件分类、目录要求、签章要求、平台工具要求。
- 没有明确字体字号要求时，按投标文件惯例提供默认模板，并允许配置覆盖。
- 默认模板建议：
  - 正文：宋体，小四 `12pt`，首行缩进 2 字符，固定 `28pt` 或 1.5 倍行距；
  - 一级标题：黑体，三号或小三，按分册/封面模板决定居中或居左；
  - 二级标题：黑体，小三或四号；
  - 三级及以下标题：黑体或宋体加粗，小四；
  - 目录：宋体小四，页码右对齐，点引导线，层级清晰；
  - 表格：表头加粗、正文五号或小五、边框清晰、宽度自适应页面；
  - 页眉：项目名称、文件类别或分册名称，不得过长溢出；
  - 页脚：居中连续页码，支持总页数；
  - 封面：项目名称、招标编号、分标/包号、投标人、日期等正式字段。
- 导出应支持至少三类模板模式：
  - `default_bid`：通用正式投标文件；
  - `sgcc_power_grid`：国网/电力投标文件默认；
  - `template_docx`：客户上传 Word 模板时按模板套打或继承样式。
- 对“第六章格式表单”类内容，不应被普通 Markdown 转表格破坏，应优先保留表格结构和签章/日期占位。
- DOCX 导出任务 metadata 应记录使用的模板、字体、字号、页边距、页眉页脚、字段刷新状态和格式告警。

#### 验收标准

- 山西真实项目导出后，封面、目录、正文、表格、页眉页脚、页码连续性均达到可给客户预览的规整程度。
- 对同一项目再次导出，目录页码、页脚页码和总页数刷新成功，页眉不溢出，正文不出现明显字体混乱。
- 目录和正文层级一致，不出现标题层级错乱、异常空页、目录页码缺失或点引导线缺失。
- 表格在 A4 页面内可读，不出现大面积越界、无边框或表头不可辨认。
- 若招标文件未明确字体字号，系统明确采用默认投标文件模板；若招标文件明确格式要求，系统优先按招标文件要求。
- 增加 DOCX 格式回归测试，至少覆盖字体、字号、页边距、页眉页脚、目录页码、表格样式和模板 metadata。

### P0-新增 01 前端轮询改成长任务友好模式

#### 当前进展

2026-06-04 基础版已完成：

- 前端轮询不再使用固定 `900` 次上限作为失败条件。
- 轮询等待窗口改为按任务章节数和目标字数动态计算，长任务超过当前等待窗口时返回后台执行状态，不抛失败。
- 单章生成、全文批量生成、章节重试均改为“后台继续执行，可刷新恢复”的用户提示。
- 终态仍以服务端 `completed`、`failed`、`partial_failed`、`cancelled` 为准。

验证记录见：`docs/development/runs/run_20260604_section_generation_p0_followup.md`。

#### 现象

真实任务 `3d7e3333-7414-4e36-aa3e-283c7d9dc18f` 一次生成 52 个叶子小节，后端实际在 `2026-06-04 16:39:18` 创建、`2026-06-04 16:45:15` 完成，耗时约 5 分 57 秒。前端当前固定 `900` 次、每次约 `300ms` 轮询，窗口约 5 分钟，导致后端仍在正常生成时，前端已经提示“章节正文后台任务仍在处理中”。

#### 整改要求

- 不得用固定 5 分钟或固定 900 次作为后台章节生成失败判断。
- 按 `total_count`、剩余 item 数、章节目标字数和最近进度动态调整等待窗口。
- 前端超出当前等待窗口时，不应把任务判为失败；应提示“后台继续生成，可稍后刷新恢复”。
- 页面刷新或重新进入项目时，必须自动恢复 latest task，并展示真实进度。
- `completed`、`partial_failed`、`failed`、`cancelled` 等终态由后端任务状态决定，前端只负责展示和恢复。

#### 验收标准

- 30+、50+、70+ 章节生成时，前端不会因为固定时间窗口提前报错。
- 关闭页面再打开，可恢复 latest task 的进度和终态。
- 后端完成后，前端能自动 reload 项目正文并清除“正在编写”视觉状态。

### P0-新增 02 补齐 PostgreSQL 正式迁移链

#### 当前进展

2026-06-04 基础版已完成：

- `scripts/init_postgres_schema.sh` 已纳入 `006`、`007` 和 `20260603` 章节任务 DDL。
- 初始化脚本已验证 `bid_generation_task_items`、`bid_generation_task_events` 和章节生成 RPC。
- 已在当前运行 PostgreSQL 上执行初始化脚本，确认幂等通过。

验证记录见：`docs/development/runs/run_20260604_section_generation_p0_followup.md`。

#### 现象

当前运行库已经存在 `bid_generation_task_items`、`bid_generation_task_events`、`lease_bid_generation_task_items`、`heartbeat_bid_generation_task_item`、`expire_bid_generation_task_items` 和 `update_bid_generation_task_item_atomic`，但 `scripts/init_postgres_schema.sh` 仍只执行 `001-005` 迁移。新库初始化时仍可能缺少 2026-06-03 章节任务 DDL。

#### 整改要求

- 将 `sql/20260603_create_bid_generation_task_items.sql`、`sql/20260603_add_bid_generation_task_item_lease.sql`、`sql/20260603_update_bid_generation_task_status_model.sql` 纳入正式迁移链。
- `migrations/postgres/006_rag_p0_filtered_recall.sql`、`migrations/postgres/007_atomic_section_task_item.sql` 和后续迁移必须被初始化脚本覆盖。
- `sql/` 目录继续作为历史/补丁参考时，不能承载新环境必需 DDL。

#### 验收标准

- 空库执行初始化脚本后，章节生成所需表和 RPC 全部存在。
- 不再依赖人工手动补跑 `sql/20260603_*`。
- 初始化脚本失败时应 fail fast，不允许静默缺迁移继续启动。

### P0-新增 03 协调任务异常失败回写

#### 当前进展

2026-06-04 基础版已完成：

- 新增 `fail_bid_generation_task()`，用于协调任务失败时把业务任务写入 `failed` 或 `partial_failed`。
- `run_bid_section_generation()` 已补外层异常捕获和业务失败回写。
- 已补单元测试覆盖 `_dispatch_next_sections()` 抛异常时的失败回写路径。

验证记录见：`docs/development/runs/run_20260604_section_generation_p0_followup.md`。

#### 现象

`run_bid_section_generation()` 调用 `_dispatch_next_sections()` 时没有外层异常回写。未来若数据库 RPC、Redis、Celery group 投递或任务读取异常，Celery 任务会失败，但业务表可能仍停留在 `queued` 或 `running`。

#### 整改要求

- `run_bid_section_generation()` 外层补 `try/except`。
- 捕获异常后，将任务或可影响 item 写入 `failed` / `partial_failed` 等业务终态。
- 错误信息写入任务 metadata 或 event 表，前端轮询必须能看到终态。
- 不能只依赖 Celery result backend 表达失败。

#### 验收标准

- 故意移除或禁用 RPC 时，前端能看到明确失败，而不是永久排队。
- Celery 投递失败时，业务任务表有终态和错误信息。

### P1-新增 01 增加任务 reconciler

#### 当前进展

2026-06-04 基础版已完成：

- 新增 `reconcile_stale_bid_generation_tasks()`，扫描长时间未推进的 `queued/running` 任务。
- 新式 item 表任务优先调用 lease 过期回收 RPC，保留可恢复语义。
- 无 item 明细的历史 JSON-only 任务转为业务失败态，避免继续污染 latest task 恢复逻辑。
- 新增 Celery 任务 `bid.sections.reconcile_stale_tasks`，并配置 beat schedule，默认 60 秒巡检一次；实际自动执行需要部署时启动 Celery beat 或等价 cron。
- 已在当前真实 PostgreSQL 上执行一次 reconciler，结果 `scanned=0`，未误伤数据。

验证记录见：`docs/development/runs/run_20260604_section_generation_p1_followup.md`。

#### 现象

历史库曾存在 19 条非终态垃圾任务：17 条 `running`、2 条 `queued`。2026-06-04 已手动清理 `bid_generation_tasks` 19 条、`bid_generation_task_events` 1 条，`bid_generation_task_items` 无关联旧 item。人工清理不能作为生产策略。

#### 整改要求

- 增加周期性 reconciler，扫描超过 lease/心跳窗口的 `queued`、`leased`、`generating`、`saving`、`running`。
- 对可恢复 item 自动重入队，对不可恢复任务写入 `failed` 或 `partial_failed`。
- 记录清理事件和原因，避免静默删除生产证据。

#### 验收标准

- 历史 `running/queued` 不会长期残留。
- worker 停止后，任务能自动恢复或进入明确终态。
- latest task 恢复逻辑不会被旧垃圾任务污染。

### P1-新增 02 补最小 E2E 长任务回归

#### 当前进展

2026-06-04 基础版已完成：

- `scripts/smoke_key_flow.py` 增加 `--section-count` 参数。
- 默认仍生成 1 个章节，保持原 smoke 成本和耗时不变。
- 显式传入 `--section-count 30` 或更大值时，可对真实后端执行 30+ 章节长任务回归。
- 脚本会优先选择叶子章节，创建一个批量章节任务并等待服务端终态。
- 2026-06-05 已完成真实 30 章节长任务压测：测试项目 `e3d516b7-c2e0-4349-8ede-efab6241076b`，任务 `88dc10b6-81dd-4896-b893-413a9eff10d0`，30/30 完成，失败 0，总耗时约 367 秒，正文全部落盘。

验证记录见：

- `docs/development/runs/run_20260604_section_generation_p1_followup.md`
- `docs/development/runs/run_20260605_091856_section_longtask_30_real.md`

#### 整改要求

- 覆盖上传招标文件、解析、目录生成、按章节批量生成正文、刷新恢复、导出。
- 至少包含 30+ 章节长任务场景，后续再扩到 50+、70+。
- fake LLM 场景覆盖慢流、断流、无 done、worker kill、重复投递、取消、重试。

#### 验收标准

- 新迁移缺失、前端固定轮询上限、业务失败不回写这三类问题能在合入前被测出。
- 长任务完成时间超过 5 分钟时，前端仍能正确恢复并展示终态。

## P0-01 重构章节任务状态模型

### 当前进展

2026-06-03 基础版已完成并通过真实 3 叶子小节验收：

- 批量任务和 item 已使用 `queued`、`leased`、`generating`、`saving`、`done`、`failed`、`stopped`、`cancelled`、`expired`、`partial_generated` 等明确状态。
- 协调任务不再把“已派发”和“真实生成”混在一个 `running` item 状态里；item 先进入 `leased`，worker 开始后进入 `generating`，保存时进入 `saving`，最终进入 `done`。
- 真实验收任务 `15449164-3a97-429c-a2e0-51b9565b180c` 中，3 个叶子小节状态链路完整：`queued -> leased -> generating -> saving -> done`，任务汇总最终为 `completed`。

P0 总体验收记录见：`docs/development/runs/run_20260603_p0_acceptance.md`。

### 现象

批量生成时多个章节长时间停留在“正在编写”或“排队中”，但实际 worker 可能已经退出、被重启、任务未真正执行，或旧任务仍在后台继续写。

### 代码依据

- `backend/tasks/section_tasks.py:91` 的 `_dispatch_next_sections` 使用当前 `running` 数量计算可派发槽位。
- `backend/tasks/section_tasks.py:115` 在 Celery 子任务真正开始前，就把 item 状态更新为 `running`。
- `backend/tasks/section_tasks.py:191` worker 开始后再次把 item 更新为 `running`。

### 生产风险

`running` 同时表示“已派发、等待 worker、真实生成中”，语义混乱。任何 Celery 投递失败、worker 重启、进程退出、旧任务覆盖，都可能造成幽灵 running。后续调度看到 running 数达到并发上限，就不会继续派发新章节，表现为“卡死”。

### 整改建议

新增明确状态：

- `queued`：等待调度。
- `leased`：已被调度器领取并投递 Celery，但 worker 未确认开始。
- `generating`：worker 已开始生成，并持续 heartbeat。
- `saving`：正在保存正文。
- `done`：完成。
- `failed`：失败。
- `cancelled`：被取消。
- `expired`：租约过期，等待重新入队或人工处理。

不要再用 `running` 同时承载多个阶段。

### 验收标准

- worker 被强杀后，章节 item 在租约过期后能自动回到 `queued` 或变为 `expired`。
- Celery 投递成功但 worker 未启动时，不会永久占用并发槽。
- 同一个章节不会被两个 worker 同时写入最终正文。
- 任务列表能清楚区分“排队、已派发、真实生成、保存中、失败、取消”。

## P0-02 拆分任务 item 独立表

### 当前进展

2026-06-03 基础版已完成并通过真实 3 叶子小节验收：

- 已落地 `bid_generation_task_items`，每个章节生成 item 独立记录 `attempt`、`attempt_id`、`worker_id`、`lease_expires_at`、`heartbeat_at`、`chars`、`final_saved_at`、`error` 等字段。
- 已落地 `bid_generation_task_events`，真实验收任务记录了 `task_created`、`item_dispatched`、`worker_started`、`heartbeat`、`progress_flushed`、`saving`、`final_saved`。
- 批量任务仍保留 JSON 快照作为前端兼容层，但生产执行证据和并发写入已落到 item/event 表。

P0 总体验收记录见：`docs/development/runs/run_20260603_p0_acceptance.md`。

### 现象

当前一个批量任务把所有章节 items 存在任务 JSON 中。每次更新一个章节状态，都需要读写整个任务结构。随着 69 个章节并发更新，容易出现覆盖、状态不一致和审计困难。

### 代码依据

- 前端类型 `frontend/src/api/bidProject.ts:217` 中 `SectionGenerationTask.items` 是任务对象里的数组。
- 后端 `backend/tasks/section_tasks.py:101`、`backend/tasks/section_tasks.py:162` 都从任务对象中读取 items。
- 后端多个 worker 都调用 `update_bid_generation_task_item` 对同一个任务 JSON 做局部更新。

### 生产风险

JSON 数组不适合作为生产级队列 item 存储。它无法自然支持行级锁、`FOR UPDATE SKIP LOCKED`、独立重试、独立租约、独立审计日志。并发写入时容易出现后写覆盖先写。

### 整改建议

新增表 `bid_generation_task_items`：

| 字段 | 说明 |
| --- | --- |
| `id` | item 主键 |
| `task_id` | 批量任务 ID |
| `project_id` | 项目 ID |
| `section_id` | 章节 ID |
| `status` | item 状态 |
| `attempt` | 重试次数 |
| `worker_id` | 当前 worker |
| `lease_expires_at` | 租约过期时间 |
| `heartbeat_at` | 最近心跳 |
| `progress_percent` | 进度 |
| `generated_content` | 当前生成缓冲 |
| `saved_section_id` | 已保存章节 |
| `error_message` | 错误 |
| `started_at` / `finished_at` | 生命周期时间 |

批量任务表只保留汇总字段，明细全部从 item 表聚合。

### 验收标准

- 任意章节 item 可独立查询、重试、取消。
- 批量任务汇总由 item 表聚合，不依赖 JSON 数组。
- 并发 worker 更新不同章节时不会互相覆盖。
- 能按 task_id 导出完整章节执行明细。

## P0-03 建立 worker lease、heartbeat 与过期回收

### 当前进展

2026-06-03 已完成基础版整改：

- 新增 `bid_generation_task_items` 行级领取 RPC：`FOR UPDATE SKIP LOCKED` 领取 `queued` item，写入 `attempt`、`attempt_id`、`worker_id`、`lease_expires_at`、`heartbeat_at`。
- Celery 调度器改为先领取 item，再投递单章任务，避免多个 worker 重复领取同一章节。
- worker 生成期间按 `BID_SECTION_HEARTBEAT_INTERVAL_SECONDS` 刷新 heartbeat，默认 10 秒。
- worker 在进度 flush、模型 chunk 回调、保存前、完成前均校验 lease owner，lease 失效后旧 worker 不再允许写入 `done` 或 `failed`。
- 调度器每次补位前会回收过期 item，默认重入队。
- 已写入 task event：`item_dispatched`、`heartbeat`、`lease_expired`、`final_saved` 等。

真实回归记录见：`docs/development/runs/run_20260603_worker_lease_heartbeat.md`。

### 现象

worker 重启、终端关闭、代码热重载后，前端仍可能看到章节“正在编写”。系统没有可靠机制判断该 worker 是否还活着。

### 代码依据

- `backend/tasks/section_tasks.py:122` 使用 Celery group 派发子任务。
- `backend/tasks/section_tasks.py:216` 仅在 flush 进度时检查取消状态，但没有 worker lease 和 heartbeat。
- `backend/tasks/section_tasks.py:321` 的协调任务只负责初次派发，不负责巡检过期 running。

### 生产风险

没有租约就无法区分“真的慢”和“已经死”。一旦 worker 异常退出，任务会长期停在 running，客户界面没有恢复能力。

### 整改建议

- 调度器领取 item 时写入 `worker_id` 和 `lease_expires_at`。
- worker 生成期间每 5-10 秒更新 `heartbeat_at`。
- 后台 reconciler 每 30-60 秒扫描过期 item。
- 过期 item 按策略重入队或标记失败。
- 保存正文时必须校验当前 worker 是否仍持有 lease。

### 验收标准

- 强杀 Celery worker 后，过期 item 能自动恢复。
- 旧 worker 在 lease 失效后不能继续写入 done。
- 同一任务可在 worker 重启后继续推进。

## P0-04 改造流式草稿保存与最终落盘边界

### 当前进展

2026-06-03 基础版已完成并通过真实验收：

- 正常完成路径：模型流收到完成信号后进入 `saving`，调用章节保存逻辑，item 写入 `final_saved_at`，章节表 `bid_sections.status` 写为 `generated`，`metadata.generation_status` / `metadata.writing_status` 写为 `generated`。
- 异常/超时路径：P0-05 已验证模型墙钟或 idle 超时后进入 `partial_generated`，保留 `generated_content` / `draft_content`，不把草稿误标成 `done`。
- 前端已能展示 `partial_generated` 为“草稿待续写”，并提供重试入口。
- 真实验收任务 `15449164-3a97-429c-a2e0-51b9565b180c` 中 3 个叶子小节全部完成最终落盘，正文表非空，AI 日志均成功。

仍需后续增强：

- 前端任务详情面板应进一步展示 `draft_saved_at`、`final_saved_at`、`attempt_id`、错误码和事件时间线。
- 可考虑把 `saved_from_task_id`、`attempt_id` 写入章节 metadata，便于从正文反查生成任务。

P0 总体验收记录见：`docs/development/runs/run_20260603_p0_acceptance.md`。

### 现象

截图中章节看似已有部分正文，但状态仍停在“正在编写”。用户看到正文页变化不稳定，任务面板也不结束。这里需要明确：不是“模型没输出完也直接当最终正文”，而是要把模型过程产物和正式章节正文分开管理。

### 代码依据

- `backend/services/section_generation.py:136` 从 `stream_bid_section` 读取流式事件。
- `backend/services/section_generation.py:148` 主要在收到 `done` 后进入保存流程。
- `backend/services/section_generation.py:158` 当前已有应急早保存逻辑，但这是补丁，不是完整事务设计。
- `backend/tasks/section_tasks.py:216` 的 `flush_progress` 中也加入了应急保存阈值，存在任务层和服务层职责混杂。

### 生产风险

如果模型持续输出但迟迟不结束，或者连接在最后阶段断开，系统会长时间占用 worker。生成内容可能只存在任务进度字段中，未稳定进入可恢复草稿；一旦任务异常退出，用户看到的内容和系统保存的内容不一致。

正式正文的可靠落盘仍然应该发生在模型正常结束、达到明确终止条件、并通过结构保存流程之后。中途内容只能作为草稿或部分生成结果保存，不能直接标记为 `done`。

### 整改建议

- 区分 `draft_content` 和 `final_content`。
- 流式输出每隔固定字符数或时间写入 `draft_content`。
- 到达最小可用阈值后允许保存为 `draft_generated`，但状态不能假装 `done`。
- 只有完成质量检查、补齐必要结构后再进入 `done`。
- 断流时保留草稿，并将 item 标记为 `needs_review` 或 `partial_generated`。
- 前端展示应区分“草稿已保存，正在继续生成”“草稿已保存，模型超时待续写”“最终正文已完成”。

### 验收标准

- 模型中途断开时，已生成内容不会丢。
- 前端能区分“草稿已保存”和“最终完成”。
- 不再通过环境变量早保存阈值来掩盖卡死。
- `draft_content` 不会被误展示为已完成的 `final_content`。

## P0-05 加模型流墙钟超时和最后 token 超时

### 当前进展

2026-06-03 已完成基础版整改：

- 对 `bid_section_*` 流式模型调用增加单章节墙钟上限，默认 `section_stream_wall_timeout_seconds=300` 秒；也可用环境变量 `BID_SECTION_STREAM_WALL_TIMEOUT_SECONDS` 覆盖。
- 对 `bid_section_*` 流式模型调用增加最后 token 空窗上限，默认 `section_stream_idle_timeout_seconds=45` 秒；也可用环境变量 `BID_SECTION_STREAM_IDLE_TIMEOUT_SECONDS` 覆盖。
- 超时错误写入 `ai_usage_logs.error_code`，当前支持：
  - `MODEL_STREAM_WALL_TIMEOUT`
  - `MODEL_STREAM_IDLE_TIMEOUT`
- 超时不再进入同步 fallback，避免“流式已超时，但 fallback 又继续占用 worker”。
- Celery item 超时后进入 `partial_generated`，批量任务汇总为 `partial_failed`，并保留 `generated_content` / `draft_content`。
- 章节表保留原正文，同时把 `metadata.generation_status`、`metadata.writing_status` 标记为 `partial_generated`，用于后续续写或人工复核。

真实回归记录见：`docs/development/runs/run_20260603_model_stream_timeout.md`。

### 现象

DeepSeek 流式调用出现过 10 分钟级延迟。只要连接持续有零星数据，底层 read timeout 不一定触发，章节就会持续占用 worker。

### 代码依据

- `backend/ai/section_writer.py:442` 调用 `stream_dashscope_api` 读取模型流。
- `backend/ai/qwen_client.py:588` requests 使用 `stream=True` 和 read timeout。
- `backend/ai/qwen_client.py:590` 持续迭代 `response.iter_lines`，没有章节级墙钟截止时间。
- `backend/ai/section_writer.py:492` 如果触发篇幅补写，还会再发起一次流式补写，进一步放大耗时。

### 生产风险

单章节可能长期占用一个 worker 槽位。并发数只有 3 时，三个章节都慢就会造成全文生成停滞。

### 整改建议

增加三类限制：

- 单章节最大墙钟时间，例如 180-300 秒。
- 最后 token 超时，例如 30-60 秒没有新内容就中断。
- 最大输出字符或 token 限制，达到后主动停止并保存草稿。

超时后不要直接失败，应保存已有内容并进入 `partial_generated` 或 `needs_review`。

### 验收标准

- 任一章节不会无限占用 worker。
- 超时任务有明确错误码，例如 `MODEL_STREAM_WALL_TIMEOUT`。
- 前端能展示“已保存草稿，模型超时，待重试/复核”。

## P0-06 补齐取消、恢复、重试语义

### 当前进展

2026-06-03 已完成基础版整改：

- 新增单章节 item 重试接口：`POST /api/bidding/interpretations/{project_id}/section-generation-tasks/{task_id}/items/{section_id}/retry`。
- 新增批量任务恢复接口：`POST /api/bidding/interpretations/{project_id}/section-generation-tasks/{task_id}/resume`。
- 重试时会把目标 item 重新置为 `queued`，清空旧 `attempt_id`、`worker_id`、`lease_expires_at`、`heartbeat_at`、保存时间与错误信息，从数据层使旧 worker/旧 attempt 失效。
- 恢复任务时默认只恢复 `failed`、`partial_generated`、`stopped`、`cancelled`、`expired` 等可重试状态。
- 前端目录行对 `failed`、`stopped`、`cancelled`、`expired`、`partial_generated` 增加“重试”入口；`partial_generated` 显示为“草稿待续写”，避免用户误判为已完成。
- 真实环境已验证：对真实 `partial_generated` item 调用重试接口后，Celery 启动新 attempt，并通过真实 DeepSeek 流式调用生成完成，最终 item 进入 `done`。

真实回归记录见：`docs/development/runs/run_20260603_retry_resume_cancel.md`。

仍需后续加强：

- Celery revoke 当前只做任务状态协议保护，尚未记录并强制撤销已投递的 Celery task id。
- 前端还需要任务详情抽屉展示 `attempt_id`、`worker_id`、lease、heartbeat 和事件时间线。

### 现象

取消任务后，如果旧 worker 还在流式输出，仍可能继续推进本地状态或尝试保存。当前取消更多是状态标记，不是严格的 worker 协议。

### 代码依据

- `frontend/src/pages/BidEditor/index.tsx:2434` 前端停止批量生成时先本地标记 stopped。
- `frontend/src/pages/BidEditor/index.tsx:2408` 再调用后端取消接口同步。
- `backend/tasks/section_tasks.py:224` flush 时检查任务是否 cancelled。
- `backend/tasks/section_tasks.py:262` chunk 到达时再次检查 cancelled。

### 生产风险

取消、旧 worker、重试 worker 之间没有统一 owner token。旧 worker 可能在取消后继续写状态，或与新任务竞争。

### 整改建议

- 每个 item 每次尝试生成时生成 `attempt_id`。
- 所有状态更新和正文保存都必须带 `attempt_id` 条件更新。
- 取消任务时同时 revoke Celery task，并把未完成 item 标记 `cancelled`。
- 旧 attempt 的任何更新都应被拒绝并记录。

### 验收标准

- 点击停止后，旧 worker 不会再把 item 改回 generating/done。
- 重试时只接受最新 attempt 的输出。
- 取消、重试、恢复路径都有自动化测试。

## P0-07 正文生成粒度改为叶子小节级

### 当前进展

2026-06-03 已完成基础版整改：

- 大纲规范化阶段会识别目标字数过大的叶子章节，前置拆成真实下级小节，而不是正文生成时临时隐藏拆分。
- 被拆分的原章节标记为结构容器：`metadata.section_role=container`、`metadata.leaf_generation=false`，`writing_plan.generation_mode=container`，不再直接进入模型生成队列。
- 新增下级小节标记为正文叶子：`metadata.section_role=leaf`、`metadata.leaf_generation=true`，目标字数控制在约 700-1400 字，`generation_mode=single_pass`。
- 批量正文生成只选择叶子小节；父级结构容器不计入生成进度、不进入 Celery item 队列。
- 单章生成如果点到父级容器，前端会自动切换到第一个叶子小节生成。
- 后端 `create_bid_generation_task` 增加兜底过滤，即使旧前端或脚本传入父级章节，也不会把父级容器投递给 Celery。

真实/本地回归记录见：`docs/development/runs/run_20260603_leaf_section_generation.md`。

### 现象

部分章节目标字数达到 6200、7700。一次模型流直接生成整章，稳定性和质量都不可控。参考成熟竞品，正文生成通常不是按“大章”一次性写完，而是在目录树下继续拆出多个叶子小节，每个叶子小节生成较短、明确、可控的正文。

### 代码依据

- `backend/ai/section_writer.py:432` 的 `stream_bid_section` 以章节为单位生成。
- `backend/ai/section_writer.py:492` 低于目标字数时继续补写。

### 生产风险

章节越大，模型越容易慢、断、偏题或重复。补写会让一次章节任务变成两次甚至更多模型调用，卡死概率翻倍。章级长流还会让用户长时间看不到明确进展，演示体验很差。

### 整改建议

- 正文生成粒度必须从章级改为叶子小节级。
- 章、节只作为结构容器和汇总展示，不直接承担大段正文生成任务。
- 以 `19.1.1`、`19.1.2`、`19.2.1` 这类叶子节点作为基本生成单位。
- 每个叶子小节控制在几百字到一千多字，必要时输出表格、清单或占位说明。
- 父级章节状态由子小节聚合得到，例如“3/5 已完成、1 个失败、1 个生成中”。
- 最终导出时按目录树合并叶子小节正文。

### 验收标准

- 单个模型调用目标控制在 800-1500 字。
- 大章节失败时只影响某个小节，不影响整章。
- 合并后的章节结构完整、标题层级正确。
- 前端目录能显示叶子小节的独立生成状态。
- 父级章节不再出现“一个大章卡住导致后续全停”的体验。

### 示例状态

```text
19 施工组织设计：汇总状态
  19.1 编制依据与工程概况：2/2 已完成
    19.1.1 编制依据：已完成
    19.1.2 工程概况：已完成
  19.2 总体施工部署：1/3 已完成
    19.2.1 施工组织机构：生成中
    19.2.2 施工任务划分：已完成
    19.2.3 施工准备：排队中
```

## P0-08 partial_failed 自动续写与批量恢复闭环

### 当前进展

2026-06-04 基础版已完成：

- 调度器 `_dispatch_next_sections` 在没有 queued/running item 且存在 `partial_generated` 时，会自动将未超过最大续写次数的 partial item 重新排队。
- 默认最大自动续写 attempt 为 3，可通过任务 metadata `maxAutoResumeAttempts` / `max_auto_resume_attempts` 或环境变量 `BID_SECTION_MAX_AUTO_RESUME_ATTEMPTS` 调整。
- 自动续写保留 `draft_content`，续写 worker 会把草稿作为初始正文，避免从头重写。
- 续写 prompt 已改为“只输出可追加到草稿末尾的内容”，要求模型承接草稿、补齐结构、不得重复已有段落。
- 已补充单元测试覆盖 partial 自动重排和 continuation prompt 选择。

仍需后续增强：

- 当前基础版没有新增 `resuming_partial` / `completed_with_drafts` 批量任务状态，仍沿用现有 `running` / `partial_failed` 状态模型，避免数据库枚举兼容风险。
- 真实 DeepSeek 全量任务的自动续写验收，需要在重启 Celery worker 后执行。旧 worker 不会加载本次代码修改。

### 生产复测现象

2026-06-04 真实“一键生成全文”复测中，最新批量任务进入 `partial_failed`：

- 批量任务总计 28 个小节。
- `done=8`，`partial_generated=20`。
- 多个 item 错误信息为“模型输出超时，已保存草稿，待续写或人工复核。”
- 任务已进入终态，不是仍在后台继续生成。
- 用户看到第五章后不再自动推进，实际原因是 partial item 没有自动进入第二轮续写队列。

### 根因判断

当前系统已经具备“单 item 重试”和“批量任务 resume”基础能力，但它仍然是人工触发能力，不是“一键生成全文”的自动续写闭环。

`partial_generated` 在生产语义上不应等同于失败终止。它表示“已有可用草稿，但模型未正常完成”，系统应根据策略自动续写，而不是直接让全文生成停在 `partial_failed`。

### 生产风险

- 用户点击“一键生成全文”后，任务会在部分小节超时后停止。
- 前端看起来像“第五章以后卡死”，但实际是任务已经终止。
- 客户无法理解为何有草稿、有进度，但系统不继续写。
- 演示时需要人工逐个点重试，体验不可接受。

### 整改建议

- 批量任务增加自动续写策略，例如 `auto_resume_partial=true`。
- 当一轮生成结束且存在 `partial_generated` item 时，自动创建下一轮 attempt。
- 对每个 item 设置最大续写次数，例如 2-3 次，避免无限循环。
- 续写 prompt 必须携带上一轮 `draft_content`，要求模型从断点继续或补齐结构，而不是重写全文。
- 批量任务状态增加更明确的中间态：
  - `resuming_partial`：正在自动续写 partial item。
  - `completed_with_drafts`：达到最大续写次数后仍有草稿，需人工复核。
  - `partial_failed`：只有在自动续写策略用尽后才进入。
- 前端“一键生成全文”应展示“第 2 轮续写中 / 剩余 12 个草稿待续写”，而不是直接显示失败或停止。

### 验收标准

- 真实模型超时产生 `partial_generated` 后，系统能自动发起下一轮续写。
- 一个全文任务中，单个小节超时不会导致后续小节永久停止。
- 达到最大续写次数后，任务能清楚显示哪些小节仍需人工复核。
- 自动续写不会覆盖已完成小节，也不会重复创建同一个 item 的并发 attempt。
- 续写内容能基于已有草稿继续补齐，而不是从头生成导致重复。

## P0-09 草稿正文可见、续写、采纳闭环

### 当前进展

2026-06-04 基础版已完成：

- 前端应用任务内容时优先读取 `draft_content`，没有时再读取 `generated_content`，确保 partial 草稿刷新后仍可见。
- `partial_generated` 章节在目录中继续显示“草稿待续写”，操作按钮文案由“重试”调整为“续写”。
- 章节更多菜单在 partial 状态下增加“采纳草稿为正文”。
- 采纳草稿会调用章节保存接口，把当前草稿保存为可编辑正文，并同步任务 item 为 `done`、message 为“已采纳草稿为正文”。
- 前端类型补齐 `draft_content`、`draft_saved_at`、`final_saved_at` 字段。

仍需后续增强：

- 当前采纳草稿保存为章节 `edited` 状态，尚未在章节 metadata 中写入 `generation_status=accepted_draft`，需要后端保存接口支持 metadata patch 后补齐审计口径。
- 章节详情抽屉和完整事件时间线仍属于 P1 可观测性任务。

### 生产复测现象

前端目录行显示“草稿已保存”或“草稿待续写”，但用户点击章节后，不一定能在正文编辑器看到对应草稿内容。

数据库层面也能看到该不一致：

- `partial_generated` item 存在 `generated_content` / `draft_content`。
- 对应 `bid_sections.content` 可能仍为空或保留旧正文。
- item 没有 `final_saved_at`，章节状态不是 `generated`。

这说明“草稿已保存”目前更多是任务 item 层保存，不等于最终章节正文已保存。

### 根因判断

当前链路把 `draft_content` 和 `final_content` 分开是正确的，但前端产品语义没有闭环。用户看到“草稿已保存”时，合理预期是：

- 可以看到草稿；
- 可以继续生成；
- 可以人工编辑；
- 可以采纳为正文；
- 可以重新生成。

目前这些动作没有完整串起来，所以用户会把“草稿已保存但正文区没有内容”理解成系统丢内容或卡死。

### 生产风险

- 模型已经消耗费用生成了内容，但用户无法直接利用。
- partial 状态越多，用户越难判断哪些内容可用。
- 后续续写如果没有明确草稿来源，容易重复写、覆盖写或丢失上下文。
- 演示时“草稿已保存”却看不到正文，会直接损害可信度。

### 整改建议

- 前端正文编辑器支持草稿视图：
  - `generated` 显示正式正文。
  - `partial_generated` 默认显示草稿预览，并用明显状态提示“草稿，未最终完成”。
- 增加草稿操作：
  - “继续续写”：用当前草稿作为上下文重新进入队列。
  - “采纳为正文”：用户确认后把草稿写入 `bid_sections.content`，但保留 `metadata.generation_status=accepted_draft`。
  - “重新生成”：废弃草稿并新建 attempt。
  - “查看生成详情”：打开 item/event 时间线。
- 后端保存结构应明确字段：
  - `draft_content`：模型阶段性产物。
  - `final_content` 或 `bid_sections.content`：正式正文。
  - `draft_saved_at`：草稿保存时间。
  - `final_saved_at`：最终正文保存时间。
- 文案调整：
  - “草稿已保存”只在草稿可见时使用。
  - 草稿不可直接进入正文时，应显示“草稿已缓存，待续写/采纳”。

### 验收标准

- 任一 `partial_generated` 小节，用户点击后能看到对应草稿。
- 用户可以对草稿执行续写、采纳、重写、查看详情。
- 采纳草稿不会伪装成模型完整完成，应有可审计状态。
- 草稿续写必须携带上一次草稿内容，避免重复从头写。
- 刷新页面后草稿仍可见，不依赖前端内存状态。

## P0-10 目标字数硬约束与流式截流保存

### 当前进展

2026-06-04 基础版已完成：

- `backend/ai/section_writer.py` 增加章节级硬性篇幅上限。
- 默认硬上限为 `max(target_words * 1.1, target_words + 120)`，可通过环境变量调整：
  - `BID_SECTION_HARD_LENGTH_CAP_ENABLED`
  - `BID_SECTION_HARD_LENGTH_CAP_RATIO`
  - `BID_SECTION_HARD_LENGTH_CAP_MIN_EXTRA_WORDS`
- 普通正文流、同步 fallback、篇幅补写流、补写 fallback 均会在达到硬上限后停止继续消费模型输出。
- prompt 中明确写入硬性篇幅上限，先给模型软约束，再由系统做硬截流。
- 达到硬上限时发出 `length_cap_reached` 事件，随后继续走现有 `done` / 保存链路。
- 已补充单元测试覆盖“超过硬上限后停止读取后续 chunk，仍正常发 done”。
- 已完成真实 DeepSeek 3 小节、10 小节、1 小节 smoke 验收，未再出现 300 秒级卡死。
- 3 小节任务 `7296e2ab-d877-4ab7-b1f1-cc2ee1730eab`：`completed`，3/3 done，约 17.5 秒。
- 10 小节任务 `c62a24ae-0dd2-457d-8a4e-bda25630a429`：`completed`，10/10 done，约 62.6 秒。
- 52 小节全量任务 `f29b298f-d939-4d6e-a83e-6ac0c0f109a9`：`completed`，52/52 done，0 failed，0 partial，约 4 分 51 秒。

真实代码生效前提：

- Celery worker 必须重启。已于 2026-06-04 15:55 重启，当前 worker 已加载本次修改。
- Gunicorn 若使用 `--reload` 可自动加载后端代码，但生产环境仍建议显式重启后统一验收。

### 生产复测现象

2026-06-04 真实“一键生成全文”复测中，任务 `e7d21c7a-4dd4-4914-a4b5-41546cdba0e1` 出现用户感知的“卡住”：

- 批量任务总计 52 个小节。
- 当时 `done=7`、`running=3`、`queued=42`、`failed=0`。
- 3 个 Celery 子任务均处于 active 状态，不是 worker 未启动。
- 数据库事件持续写入 `progress_flushed`，`last_token_at` 持续更新，说明 DeepSeek 不是完全无响应。
- `类似项目业绩 - 资料清单` 和 `类似项目业绩 - 有效性说明` 已达到 98%，实际字数约 1187 / 1206，仍继续流式输出。
- 已完成章节普遍超过目标 1000 字，例如 1430、1902、1655、1819 等。

### 根因判断

这次不是典型的“模型无响应卡死”。第一层问题是模型持续输出且不主动收束；第二层问题是 worker 每个流式 chunk 都同步查询任务状态并高频写库，导致对 DeepSeek SSE 消费产生反压。第二层问题已单独拆为 P0-11。

当并发数为 3 时，只要 3 个章节都进入慢速超写状态，后续 42 个排队章节就不会推进，前端表现为“卡住”。

上下文过大可能会放大模型延迟，但当前证据显示主要瓶颈不是首 token 前异常：

- `first_token_at` 已存在。
- `last_token_at` 持续刷新。
- `ai_usage_logs` 中已完成的 `bid_section_stream` 均为 DeepSeek `200` 成功。

2026-06-04 真实 DeepSeek API 测速显示：

- 简单 prompt 到 300 可见字约 4.05 秒。
- 生产章节 prompt 到 1200 可见字约 16.18 秒。
- 这明显快于 Celery worker 中 300 秒只生成约 1100-1500 字的表现。

因此根因不是 DeepSeek API 普遍慢，而是系统消费流的热路径把输出速度拖慢，再叠加缺少硬性篇幅截流。

### 生产风险

- 目标 1000 字的小节可能生成到 1500-2000 字以上，显著拉长单章耗时。
- 模型只要持续吐零星 token，就不会触发 idle timeout。
- worker 槽位被慢流章节占满，全文任务长期不推进。
- 用户看到 98% 进度条不结束，会误判为系统死锁。

### 整改建议

- 保留 prompt 目标字数作为软约束，但不能只依赖模型自觉结束。
- 流式消费侧必须根据可见正文估算字数做硬截流。
- 达到硬上限后关闭流并保存当前正文，状态进入 `done`，同时记录 `length_cap_reached` 事件供诊断。
- 篇幅补写只允许在低于下限时执行；一旦已达硬上限，不再触发补写。
- 对已完成但过长的历史章节，后续通过 P1 压缩改写处理，而不是阻塞本轮全文生成。

### 验收标准

- 目标 1000 字的小节，默认不应超过约 1120 字仍继续占用 worker。
- 达到硬上限后 item 能进入 `saving -> done`，后续 queued item 继续派发。
- `length_cap_reached` 事件可在任务事件中查询。
- 单元测试覆盖流式超写截流、fallback 超写截流、补写超写截流。
- 真实 DeepSeek 10 小节复测中，不再出现 3 个 worker 长时间停在 98% 的情况。

## P0-11 流式消费与任务状态持久化解耦

### 当前进展

2026-06-04 基础版已完成：

- `backend/tasks/section_tasks.py` 已移除每个 chunk 查询整任务的热路径。
- chunk 回调只做内存累加、chunk 计数和待 flush 缓冲，不再每个 token/chunk 做 DB 查询。
- 取消、终态、lease owner 校验移动到节流后的 progress flush、heartbeat、保存前和完成前。
- 进度落库默认节流为 `BID_SECTION_PROGRESS_FLUSH_INTERVAL_SECONDS=1.0` 秒，或 `BID_SECTION_PROGRESS_FLUSH_MIN_CHARS=160` 字符。
- `chunk_events` 默认只保留最近 `BID_SECTION_CHUNK_EVENT_LIMIT=200` 条，避免任务 item 反复写入不断膨胀的大数组。
- DeepSeek/DashScope 流被硬截流主动关闭时，仍写入 `ai_usage_logs`，metadata 标记 `stream_closed_by_consumer=true`。
- `lease_bid_generation_task_items` RPC 增加 task 级 `pg_advisory_xact_lock`，避免多个 worker 同时补位时重复领取同一 queued item。
- 已通过后端相关单元测试、语法检查和真实 DeepSeek 链路验收。

真实验收：

- 3 小节任务 `7296e2ab-d877-4ab7-b1f1-cc2ee1730eab`：`completed`，3/3 done，平均约 1133 字。
- 10 小节任务 `c62a24ae-0dd2-457d-8a4e-bda25630a429`：`completed`，10/10 done，平均约 1173 字，事件 `progress_flushed=119`。
- 1 小节 usage smoke `3717d44d-ca2a-4321-a35b-fa53a7393b7d`：`completed`，usage 记录存在，`usage_estimated=true`，`stream_closed_by_consumer=true`。
- 52 小节全量任务 `f29b298f-d939-4d6e-a83e-6ac0c0f109a9`：`completed`，52/52 done，0 failed，0 partial，AI error 0。
- 重复 lease 回归任务 `e851c185-1f89-456e-89f9-fe211364ac03`：`completed`，8/8 done，`item_dispatched=8`、`worker_started=8`、`final_saved=8`，duplicate dispatch 0。

### 生产复测现象

2026-06-04 真实 DeepSeek API 直连测速显示：

- 简单 prompt 到 300 可见字约 4.05 秒。
- 生产章节 prompt 到 1200 可见字约 16.18 秒。

但 Celery 任务中，DeepSeek `bid_section_stream` 出现 300 秒墙钟超时，期间只生成约 1100-1500 字。

这说明慢不在 DeepSeek 平台本身，而在本系统消费流式输出的路径中。

### 根因判断

原 worker 热路径存在严重反压：

- `generate_one_section.on_event` 在每一个流式 chunk 上调用 `get_bid_generation_task`。
- 真实 DB 实测中，单次 `get_bid_generation_task` 平均约 56ms。
- `stream_dashscope_api` / `_stream_deepseek_api` 是同步 generator；调用方处理 chunk 不返回，就不会继续消费下一条 SSE。
- 高频 progress flush 又会写入 `generated_content` 和不断增长的 `chunk_events`。

结果是 DeepSeek 本来可以快速输出，但 worker 被每 chunk 的 DB 操作拖住，最终触发 300 秒墙钟超时。

### 生产风险

- “一键生成全文”并发越高，数据库反压越明显。
- 前端为了看起来更实时，反而牺牲了模型消费速度和整体吞吐。
- worker 槽被慢消费占用，后续章节排队，用户误以为模型卡死。
- 如果继续逐 token/chunk 落库，换模型或提高并发都无法根治。

### 整改建议

- LLM 流式消费和任务状态持久化必须分层：
  - 流式消费：快速读取 SSE，内存累加。
  - 进度落库：按时间/字符数节流。
  - 控制检查：按 heartbeat / flush 节流检查取消、终态、lease。
  - 审计事件：只记录关键状态事件，不记录每个 token。
- 前端展示不追求逐 token 落库，以“最近 1 秒进度”作为生产默认。
- 完整正文以 `generated_content` / `draft_content` 为准，`chunk_events` 只作为短窗口诊断。
- 后续如果需要更实时，应使用内存队列/SSE 直推，而不是每个 chunk 写数据库。

### 验收标准

- 生产章节 prompt 真实 DeepSeek 流式输出不应因 worker DB 热路径被拖到 300 秒墙钟超时。
- 10 小节真实 DeepSeek 复测中，单小节到 1000-1200 字的耗时应接近直连测速量级，而不是 300 秒级。
- `progress_flushed` 事件频率可控，不再每秒写入大量 DB 事件。
- `chunk_events` 不再随生成时间无限增长。
- 取消、lease 失效、终态覆盖仍然能在 1-2 秒量级内被 worker 感知。

## P1-01 可见字数统计口径与压缩改写

### 生产复测现象

截图中多个小节显示“篇幅偏长 2736/1000字”“2698/1000字”等，但用户点击正文后感觉实际内容并没有那么长。

这个问题分两层：

- 部分小节确实超出目标很多，说明模型没有按目标字数收敛。
- 前端统计口径是 raw Markdown 非空白字符数，可能把标题、表格语法、标点、占位符、Markdown 符号都计入，和用户看到的可见正文长度不一致。

### 根因判断

当前 `target_words` 原先只是写作计划和 prompt 的软约束，不是系统硬约束。P0-10 已补齐流式截流，P1 剩余问题是前端统计口径、too_long 标记和压缩改写能力。

同时前端展示“字”但实际统计 raw content 长度，这会让用户误以为系统字数统计错误。更准确的产品口径应区分：

- 可见正文字符数；
- raw Markdown 字符数；
- 目标字数范围；
- 是否超出可接受阈值。

### 生产风险

- 历史小节或人工编辑后仍可能出现 1000 字目标却有 2500 字以上内容，需要能诊断和压缩。
- 生成内容过长会破坏投标文件结构节奏。
- 用户会质疑系统“目标字数”和“实际输出”不一致。
- 过长内容还会影响后续导出排版和人工审核效率。

### 整改建议

- 将目标字数从单点值改为范围，例如目标 1000 字对应可接受范围 800-1200 字。
- 根据目标字数进一步设置模型 `max_tokens`，减少无效输出成本。
- 生成后做长度审计：
  - 低于下限：标记 `too_short`，可选择补写。
  - 高于上限：标记 `too_long`，优先压缩改写，而不是直接标绿。
- 前端统计改为可见正文字符数，Markdown 表格可按单元格文本计数，不统计语法符号。
- UI 文案从“字数”调整为“正文约 X 字 / 目标 Y 字”，避免暗示精确 word count。

### 验收标准

- 目标 1000 字的小节，默认输出落在 800-1200 可见正文字符范围内。
- 超出 35% 以上时，系统能明确标记并提供“压缩正文”操作。
- 前端显示字数与用户肉眼可见正文长度基本一致。
- 表格、标题、Markdown 语法不会显著污染字数统计。
- 长度控制不依赖人工感觉，有可重复的测试用例。

## P1-02 前端任务进度改造

### 现象

用户只能看到“正在编写”进度条，无法判断是模型慢、worker 死、排队、保存、失败还是取消。

### 代码依据

- `frontend/src/pages/BidEditor/index.tsx:449` 每 300ms 轮询任务状态。
- `frontend/src/pages/BidEditor/index.tsx:434` 会自动选中第一个 running 章节，导致页面跳动。
- `frontend/src/pages/BidEditor/index.tsx:397` 用任务中的 `generated_content` 临时覆盖章节内容。

### 生产风险

高频轮询增加后端压力，但信息密度低。演示时客户看到“不动”，无法知道系统是否仍在工作。

### 整改建议

- 改为 SSE/WebSocket 或低频轮询加事件增量。
- 页面不要自动跳转到 running 章节，改为用户可点击查看。
- 增加“只看异常”“重试失败”“继续未完成”操作。
- 可观测指标分成客户可见和开发/运维可见两层，避免主界面堆满技术字段。

建议放置位置：

1. 右侧任务总览面板：展示总章节、已完成、生成中、排队中、失败、已保存草稿、当前并发、最近更新、运行时长。
2. 目录每一行轻量状态：展示状态、已生成字数/目标字数、最近输出时间、草稿保存状态。
3. 章节“生成详情”抽屉：从章节更多菜单进入，展示 worker、attempt、开始时间、首 token、最近 token、草稿保存时间、模型、RAG/rerank 状态、错误码和事件时间线。
4. 顶部生成健康提示：放在“一键生成全文”按钮附近，展示 Celery、Redis、DeepSeek、RAG 是否可用。

客户主界面只需要回答“有没有在动”；详情抽屉回答“卡在哪一层”。

### 验收标准

- 用户能在 5 秒内判断任务是否活跃。
- 后端轮询压力明显下降。
- 页面不会因多个章节并发生成而频繁跳动。
- 开发人员能从章节详情抽屉看到卡在排队、worker、模型、保存还是 RAG。
- 生成服务异常时，一键生成按钮旁能明确提示，而不是点击后才卡住。

## P1-03 增加可观测性与诊断日志

### 现象

后端日志主要能看到 HTTP 轮询完成，但不容易直接回答“卡在哪一章、卡在模型首 token 前还是结束前、是否保存成功”。

### 代码依据

- 当前 `ai_usage_logs` 能记录模型总耗时，但任务 item 级生命周期事件不足。
- `backend/tasks/section_tasks.py` 中关键状态变化缺少统一事件表。

### 生产风险

线上问题只能靠人工查 DB、翻日志和截图判断，无法快速止血。

### 整改建议

新增 `bid_generation_task_events`：

- `item_dispatched`
- `worker_started`
- `first_token`
- `progress_flushed`
- `draft_saved`
- `final_saved`
- `stream_timeout`
- `lease_expired`
- `retry_scheduled`
- `failed`
- `cancelled`

前端详情抽屉建议读取这些事件并按时间线展示：

```text
15:42:05 queued
15:42:07 leased
15:42:10 worker_started
15:42:18 first_token
15:42:35 draft_saved
15:43:02 progress_flushed
```

每个 item 至少应能展示：

- `worker_id`
- `attempt_id`
- `lease_expires_at`
- `first_token_at`
- `last_token_at`
- `draft_saved_at`
- `model`
- `rag_status`
- `error_code`

### 验收标准

- 任一任务可导出完整执行时间线。
- 管理后台可显示当前活跃 worker 和卡住 item。
- 出现卡死时 1 分钟内能定位阶段。

## P1-04 清理服务层循环依赖

### 现象

章节生成 service 直接依赖 API routes 中的图片辅助函数，导致 API、Celery、脚本启动路径容易互相影响。

### 代码依据

- `backend/services/section_generation.py:19` 从 `backend.api.routes` 导入 `_asset_allowed_for_bid`、`_asset_image_ref`、`_build_section_image_markdown`。

### 生产风险

Celery worker 启动、脚本导入、API 路由加载顺序不同，可能出现循环导入或部分初始化问题。

### 整改建议

- 把图片选择和 markdown 构建移动到 `backend/services/section_assets.py`。
- API routes 和 section_generation 都依赖 service，不允许 service 反向依赖 API。

### 验收标准

- `python -c "from backend.services.section_generation import generate_and_save_bid_section"` 可独立成功。
- Celery worker、Gunicorn、smoke 脚本均可独立启动。

## P1-05 隔离 RAG/rerank 降级策略

### 现象

正文写作使用 DeepSeek，但章节 prompt 生成会做章节级 RAG 检索。百炼 `qwen3-rerank` 免费额度耗尽不会直接导致 DeepSeek 写作卡死，但可能影响检索质量或召回耗时。

### 代码依据

- `backend/ai/section_writer.py:191` 中 `_compact_section_rag_context` 调用 `search_knowledge_base`。
- `backend/ai/section_writer.py:205` 检索异常时 fail-open，跳过 RAG。

### 生产风险

如果 rerank 降级不可见，用户会误以为正文模型卡死或内容质量突然下降。

### 整改建议

- RAG 检索和 rerank 设置明确超时，例如 5-10 秒。
- rerank 不可用时明确记录 `rerank_degraded=true`。
- 前端或任务详情显示“知识库召回降级，不影响正文生成继续执行”。

### 验收标准

- rerank API 额度耗尽时，正文生成仍可继续。
- 任务事件中能看到检索是否降级。
- 降级不会把章节 item 卡在 generating。

## P2-01 优化 prompt 和篇幅补写策略

### 现象

系统试图用目标字数驱动模型输出完整章节，并在不足时触发补写。这个策略容易造成重复、空泛和长耗时。

### 代码依据

- `backend/ai/section_writer.py:492` 判断不足后触发补写。
- `backend/ai/section_writer.py:501` 补写再次走流式模型调用。

### 生产风险

补写提升字数，但会牺牲稳定性。生产优先级应低于任务系统改造。

### 整改建议

- 先关闭自动补写作为默认路径。
- 改为小节级“计划 -> 初稿 -> 质量检查 -> 必要补写”。
- 补写只对失败小节或低质量小节执行。

### 验收标准

- 单次生成平均耗时下降。
- 重复段落减少。
- 章节完整度由结构检查保证，而不是单纯字数补齐。

## P2-02 演示模式与灰度开关

### 现象

客户演示中，一键生成全文是最长、最脆弱链路。没有演示保护机制时，任何外部模型波动都会直接暴露给客户。

### 整改建议

- 增加 `DEMO_MODE`，可使用固定短超时、固定并发、预置素材、可恢复任务。
- 增加“生成前健康检查”：DeepSeek、RAG、Redis、Celery、数据库。
- 一键生成前先跑 1 个章节探测，通过后再批量。

### 验收标准

- 演示前健康检查能明确给出是否可演示。
- 模型不可用时按钮禁用或降级，不进入半卡死状态。
- 演示模式不影响生产模式。

## 当前应急补丁处理建议

当前工作区存在为演示止血做的未提交修改，包括早保存、跳过补写、降低 prefetch、前端传入 `skipLengthSupplement` 等。这些补丁可以作为问题证据和短期保护，但不应作为最终生产方案。

建议处理方式：

1. 保留在单独分支或补丁记录中，标记为 emergency patch。
2. 主线整改以 item 表、lease、heartbeat、超时、事件日志为核心。
3. 在新架构完成前，不建议继续承诺“生产级一键生成全文”。

## 建议实施顺序

### 第 1 阶段：止血与可诊断

- 禁用或隐藏生产演示中的“一键生成全文”入口。
- 保留单章节生成，但加明确超时和失败提示。
- 增加任务事件日志，至少记录章节开始、首 token、最后 token、保存、失败。

### 第 2 阶段：任务系统重构

- 新增 `bid_generation_task_items`。
- 实现 lease、heartbeat、过期回收。
- 改造 Celery 子任务为按 item 独立执行。
- 实现 attempt_id 幂等写入。

### 第 3 阶段：生成策略重构

- 大章节拆成小节级生成。
- 保存草稿和最终正文分离。
- 补齐 partial_failed 自动续写策略，避免全文任务中途终止。
- 补齐草稿可见、续写、采纳闭环，避免“草稿已保存但用户看不到”。
- 关闭默认自动补写，改为质量检查后的定向补写。
- 建立目标字数范围、max_tokens、生成后长度审计和压缩改写策略。

### 第 4 阶段：前端体验重构

- 增加任务详情面板。
- 显示每章状态、耗时、最后更新时间、错误码。
- 支持重试失败、继续未完成、取消并清理。

### 第 5 阶段：回归测试与演示准入

- fake LLM 覆盖慢流、断流、无 done、重复投递、worker kill、取消、重试。
- 先用 fake LLM 跑通 69 章。
- 再用 DeepSeek 跑 3 章、10 章、全量 69 章压测。
- 只有全量任务可恢复、可取消、可诊断后，才恢复客户演示。

## 必须补齐的测试用例

| 用例 | 预期 |
| --- | --- |
| 模型一直不返回 done | 超时后保存草稿并标记 partial/needs_review |
| 模型首 token 前超时 | item 失败并释放 worker 槽 |
| 模型持续慢速输出 | 达到墙钟时间后中断并保存草稿 |
| worker 生成中被 kill | lease 过期后 item 自动恢复 |
| 同一 item 被重复投递 | 只有最新 attempt 能写入 |
| 用户点击取消 | 旧 worker 后续更新被拒绝 |
| rerank 额度耗尽 | RAG 降级，正文生成继续 |
| 批量任务出现 partial_generated | 自动进入下一轮续写，未达到最大次数前不终止全文任务 |
| partial_generated 小节点击预览 | 能看到草稿，并可续写、采纳或重写 |
| 目标 1000 字小节生成超长 | 被标记 too_long，并可触发压缩或重新生成 |
| Markdown 表格和标题计数 | 前端按可见正文统计，不把语法符号算作正文 |
| 69 章批量生成 | 任一章节失败不阻塞其它章节 |

## 评审建议

本次整改不要从“换模型”“调 prompt”“提高并发数”开始。提高并发只会放大当前状态模型的问题；换模型也无法解决 worker 死亡、无 lease、无恢复、无稳定落盘的问题。

团队评审时建议先确认两个架构决策：

1. 是否接受新增 `bid_generation_task_items` 和 `bid_generation_task_events` 两张表。
2. 是否接受大章节改为小节级生成，而不是单章节一次性长流生成。

这两个决策确认后，再拆具体开发任务。

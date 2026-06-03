# 标书正文按章节生成生产整改待办清单

日期：2026-06-03

范围：一键生成全文、按章节目录批量生成正文、Celery 章节子任务、DeepSeek 流式输出、章节正文落盘、前端任务进度展示。

结论：当前问题不是单一模型慢、单一章节内容长或百炼 rerank 额度导致，而是正文生成链路缺少生产级任务系统能力。优先级应先处理任务状态、worker 租约、超时恢复、落盘边界，再处理 prompt、篇幅策略和前端体验。

## 优先级总览

| 优先级 | 待办 | 目标 | 建议负责人 |
| --- | --- | --- | --- |
| P0 | 重构章节任务状态模型 | 彻底解决 running 卡死、幽灵任务、并发槽位被占用 | 后端 |
| P0 | 拆分任务 item 独立表 | 支持章节级 lease、重试、恢复、审计 | 后端 / 数据库 |
| P0 | 建立 worker lease 与 heartbeat | worker 重启或断线后可自动回收任务 | 后端，基础版已完成 |
| P0 | 改造流式草稿保存与最终落盘边界 | 过程内容可恢复，最终正文必须有明确完成条件 | 后端 |
| P0 | 加模型流墙钟超时和最后 token 超时 | 防止单章节无限占用 worker | 后端 / AI，基础版已完成 |
| P0 | 补齐取消、恢复、重试语义 | 取消后旧 worker 不得继续覆盖状态 | 后端 |
| P0 | 正文生成粒度改为叶子小节级 | 章/节作为结构容器，最小小节独立生成 | AI / 后端 / 前端 |
| P1 | 前端改为任务事件/状态面板 | 用户能判断是真在跑、慢、失败还是卡死 | 前端 |
| P1 | 增加可观测性与诊断日志 | 可定位每章耗时、首 token、末 token、保存点 | 后端 |
| P1 | 清理服务层循环依赖 | Celery、API、脚本启动路径一致 | 后端 |
| P1 | 隔离 RAG/rerank 降级策略 | rerank 额度耗尽不应影响正文任务可用性 | 后端 / AI |
| P2 | 优化 prompt 和篇幅补写策略 | 提升质量和稳定性，但不作为首要止血项 | AI |
| P2 | 完善演示模式与灰度开关 | 演示环境可控、可快速回退 | 全栈 |

## P0-01 重构章节任务状态模型

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
- 关闭默认自动补写，改为质量检查后的定向补写。

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
| 69 章批量生成 | 任一章节失败不阻塞其它章节 |

## 评审建议

本次整改不要从“换模型”“调 prompt”“提高并发数”开始。提高并发只会放大当前状态模型的问题；换模型也无法解决 worker 死亡、无 lease、无恢复、无稳定落盘的问题。

团队评审时建议先确认两个架构决策：

1. 是否接受新增 `bid_generation_task_items` 和 `bid_generation_task_events` 两张表。
2. 是否接受大章节改为小节级生成，而不是单章节一次性长流生成。

这两个决策确认后，再拆具体开发任务。

# P0-10 章节生成硬性篇幅截流整改记录

日期：2026-06-04

范围：

- “一键生成全文”过程中，目标 1000 字小节持续超写并长期占用 worker。
- DeepSeek 流式输出持续有 token，但不主动结束，前端表现为 98% 附近“卡住”。

## 现场复盘

真实复测任务：

- project_id：`50ae3a91-f725-4cc1-b0d3-d7c3a33a5211`
- task_id：`e7d21c7a-4dd4-4914-a4b5-41546cdba0e1`
- 任务规模：52 个叶子小节
- 现场汇总：`done=7`、`running=3`、`queued=42`、`failed=0`

现场判断：

- Celery worker 正常存在，并发数为 3。
- Celery inspect 显示 3 个 `bid.sections.generate_one` active。
- 数据库 `bid_generation_task_events` 持续写入 `progress_flushed`。
- 运行中 item 的 `first_token_at` 已存在，`last_token_at` 持续刷新。
- 因此这次不是“模型完全无响应”，而是“模型慢速持续输出且不结束”。

典型运行中 item：

- `类似项目业绩 - 资料清单`：目标 1000 字，已约 1187 字，仍在 `generating`，进度 98%。
- `类似项目业绩 - 有效性说明`：目标 1000 字，已约 1206 字，仍在 `generating`，进度 98%。
- `项目管理机构 - 编制依据`：目标 1000 字，仍在慢速输出。

已完成 item 也显示目标字数控制偏弱：

- `企业基本资格资料 - 响应要求`：约 1430 字。
- `企业基本资格资料 - 资料清单`：约 1902 字。
- `信誉与合规承诺 - 条款响应`：约 1819 字。

## 根因

`target_words` 之前主要是 prompt 软约束。模型可能为了“完整性”和“正式标书表达”持续展开，即使已经超过目标字数，系统也会继续消费流式输出，直到模型自然结束或墙钟超时。

在并发数为 3 的场景下，只要 3 个章节都进入慢速超写状态，后续章节就一直排队，前端表现为“卡住”。

上下文过大可能会增加延迟，但本次现场证据不支持“首 token 前异常”或“DeepSeek API 完全挂死”：

- 已有首 token。
- 末 token 持续更新。
- 最近完成的 `bid_section_stream` AI usage 记录为 DeepSeek 200 成功。

2026-06-04 进一步用真实 DeepSeek API 测速后，确认不能把问题简单归因于 DeepSeek 平台慢：

| 测试 | prompt 长度 | 截止条件 | 总耗时 | 首 token | 输出速率 |
| --- | ---: | --- | ---: | ---: | ---: |
| 简单 300 字 prompt | 44 字符 | 约 300 可见字 | 4.05s | 1.55s | 约 120 可见字/s |
| 生产章节 prompt | 3138 字符 | 约 1200 可见字 | 16.18s | 4.40s | 约 102 可见字/s |

这与 Celery 任务中 300 秒只生成约 1100-1500 字明显不一致。

进一步检查 worker 热路径后发现：

- `generate_one_section.on_event` 原先在每一个流式 chunk 上都调用 `get_bid_generation_task`。
- 本地真实 DB 测试中，单次 `get_bid_generation_task` 平均约 56ms。
- chunk 回调还会追加 `chunk_events`，并在高频 flush 时写回越来越大的数组。
- qwen_client 的流式 generator 是同步 yield；调用方 chunk 回调不返回，就不会继续消费下一条 SSE。

因此，生产慢流的更准确根因是“双重问题”：

1. 模型输出缺少硬性篇幅截流，超过目标后仍可能继续写。
2. worker 每个 chunk 做数据库查询/高频落库，导致对 DeepSeek SSE 消费产生反压，把本来十几秒的输出拖到数分钟。

## 本次改动

### 后端

- `backend/ai/section_writer.py`
  - 新增 `BID_SECTION_HARD_LENGTH_CAP_ENABLED`。
  - 新增 `BID_SECTION_HARD_LENGTH_CAP_RATIO`，默认 `1.1`。
  - 新增 `BID_SECTION_HARD_LENGTH_CAP_MIN_EXTRA_WORDS`，默认 `120`。
  - 新增硬上限计算：`max(target_words * ratio, target_words + min_extra_words)`。
  - 普通流式生成、同步 fallback、篇幅补写流、补写 fallback 均在达到硬上限后停止继续消费输出。
  - 达到硬上限时发出 `length_cap_reached` 事件。
  - prompt 中写入硬性篇幅上限，降低模型超写概率。

- `backend/tasks/section_tasks.py`
  - chunk 回调不再每个 chunk 查询整任务状态。
  - 取消/终态/lease owner 校验移动到节流后的 progress flush。
  - 进度落库默认节流为 `BID_SECTION_PROGRESS_FLUSH_INTERVAL_SECONDS=1.0` 秒和 `BID_SECTION_PROGRESS_FLUSH_MIN_CHARS=160` 字符。
  - `chunk_events` 默认只保留最近 200 条，避免每次写入不断膨胀。

- `backend/ai/qwen_client.py`
  - 当上层因硬截流主动关闭 DeepSeek/DashScope 流式 generator 时，仍记录 `ai_usage_logs`。
  - 记录 metadata：`stream_closed_by_consumer=true`、`partial_output=true`。
  - 如果 provider 未返回原生 usage，则基于输入/输出文本估算 token，避免成本和诊断记录断档。

### 文档

- `docs/section-generation-production-remediation-todo.md`
  - 将“目标字数硬约束与流式截流保存”提升为 P0-10。
  - 将“可见字数统计口径与压缩改写”保留为 P1。

## 验证

已执行：

```bash
.venv/bin/python -m unittest tests.test_section_generation_autoresume tests.test_deepseek_client tests.test_native_parse_ingestion
```

结果：

- 5 个测试通过。
- 新增测试覆盖：流式生成达到硬性篇幅上限后，不再消费后续 chunk，并正常发出 `done`。

后续追加执行：

```bash
.venv/bin/python -m unittest tests.test_section_generation_autoresume tests.test_api_sections tests.test_deepseek_client tests.test_native_parse_ingestion
```

结果：12 个测试通过。

2026-06-04 追加执行：

```bash
.venv/bin/python -m unittest tests.test_deepseek_client tests.test_section_generation_autoresume tests.test_api_sections tests.test_native_parse_ingestion
```

结果：13 个测试通过。

新增/修复测试：

- `tests/test_deepseek_client.py`
  - 验证 DeepSeek 流式 generator 被消费者主动关闭时仍会记录 usage。
- `tests/test_api_sections.py`
  - 修复测试隔离：强制关闭鉴权配置，避免受 `.env` 和测试执行顺序影响。

已执行：

```bash
.venv/bin/python -m py_compile backend/ai/section_writer.py backend/services/section_generation.py backend/tasks/section_tasks.py backend/parsing/document_parser.py
```

结果：通过。

## 真实生产链路验收

验收环境：

- 后端：本地 Gunicorn，真实 PostgreSQL/Supabase 兼容库。
- Celery：真实 Redis `redis://127.0.0.1:16379/0`，`--concurrency=3`。
- LLM：真实 DeepSeek `deepseek-v4-flash`。
- 项目：`50ae3a91-f725-4cc1-b0d3-d7c3a33a5211`。
- 任务创建：调用后端任务创建函数并派发 Celery，覆盖真实 DB、Redis、Celery worker、DeepSeek、落盘链路。

说明：HTTP API 创建任务被当前登录鉴权拦截，返回 401；因此本次验收跳过 HTTP 鉴权层，未使用 mock。

### 3 小节并发验收

- task_id：`7296e2ab-d877-4ab7-b1f1-cc2ee1730eab`
- 小节数：3
- 目标字数：1000
- 结果：`completed`
- 汇总：`done=3`、`failed=0`、`partial=0`
- 任务耗时：约 17.5 秒
- 生成字数：1133、1134、1134
- `chunk_events`：每个 item 最多保留 200 条

结论：3 路并发没有再出现 300 秒墙钟超时或 98% 长时间停住。

### 10 小节补位验收

- task_id：`c62a24ae-0dd2-457d-8a4e-bda25630a429`
- 小节数：10
- 目标字数：1050
- 结果：`completed`
- 汇总：`done=10`、`failed=0`、`partial=0`
- 任务耗时：约 62.6 秒
- 平均字数：约 1172.7
- 字数范围：1126-1182
- 事件汇总：
  - `item_dispatched=10`
  - `worker_started=10`
  - `final_saved=10`
  - `progress_flushed=119`
  - `heartbeat=21`

结论：3 路并发补位正常，后续 queued item 能持续推进，没有出现 worker 槽被慢流长期占满。

### usage 记录 smoke

- task_id：`3717d44d-ca2a-4321-a35b-fa53a7393b7d`
- 小节数：1
- 结果：`completed`
- 任务耗时：约 15 秒
- 生成字数：1180
- AI usage：
  - provider：`deepseek`
  - model：`deepseek-v4-flash`
  - stage：`bid_section_stream`
  - success：`true`
  - status_code：`200`
  - latency_ms：`12826`
  - usage_estimated：`true`
  - metadata：`stream_closed_by_consumer=true`、`partial_output=true`

结论：硬截流主动关闭流后，AI usage 不再断档。

### 52 小节全量验收

- task_id：`f29b298f-d939-4d6e-a83e-6ac0c0f109a9`
- 小节数：52
- 结果：`completed`
- 汇总：`done=52`、`failed=0`、`partial=0`
- 任务时间：2026-06-04 16:08:33 至 16:13:25，约 4 分 51 秒
- item 落盘：
  - `final_saved_at=52/52`
  - `saved_section_id=52/52`
  - 章节正文非空：52/52
- 字数范围：826-1771
- 平均字数：约 1192.5
- `chunk_events` 最大长度：200
- AI usage：
  - `bid_section_stream` success：53 条
  - error：0 条
  - `MODEL_STREAM_*`：0 条

结论：全量 52 个叶子小节真实 DeepSeek 验收通过，不再出现旧链路中的大面积 `partial_failed`、300 秒墙钟超时或 98% 长时间卡住。

### 全量验收中发现并修复的问题

全量验收期间发现一个新的 P0 边界问题：

- `联合体协议及分包说明` 被 `item_dispatched` 2 次、`worker_started` 2 次。
- 最终只有后一个 attempt 写入 `final_saved`，正文没有错，但已经产生重复 LLM 调用风险。
- 触发条件：多个 worker 在任务尾部几乎同时完成并调用 `_dispatch_next_sections`，最后少量 queued item 存在极窄重复 lease 竞争。

修复：

- `sql/20260603_add_bid_generation_task_item_lease.sql`
  - 在 `lease_bid_generation_task_items` RPC 中增加 `pg_advisory_xact_lock(hashtext(p_task_id::text))`。
  - 同一批量任务的补位领取在数据库事务内串行化，避免尾部 queued item 被重复领取。
- 已直接执行 SQL 更新当前本地数据库函数。

真实回归：

- task_id：`e851c185-1f89-456e-89f9-fe211364ac03`
- 小节数：8
- 结果：`completed`
- 汇总：`done=8`、`failed=0`、`partial=0`
- 事件：
  - `item_dispatched=8`
  - `worker_started=8`
  - `final_saved=8`
  - duplicate dispatch：0
- AI usage：`bid_section_stream` success 8 条，error 0 条。

结论：任务级 advisory lock 生效，重复派发边界已修复。

## 运行注意

本次修改需要重启 Celery worker 后才会对新任务生效。已于 2026-06-04 15:55 重启 worker，新进程已加载 P0-10/P0-11 和 usage 记录修复。

建议验证顺序：

1. 停止当前卡住的批量任务或重置生成状态。
2. 重启 Celery worker。
3. 先跑 3 个目标 1000 字小节，确认达到约 1120 字后能自动保存并释放 worker。
4. 再跑 10 个小节，确认 DeepSeek 流式输出不会被 worker 数据库热路径拖慢。
5. 最后再跑全量 52/69 小节。

## 剩余风险

- 当前硬截流解决的是“慢速超写占用 worker”，不是最终内容质量压缩。
- 已完成但过长的历史章节需要后续 P1 “压缩改写”处理。
- 前端显示字数仍需要统一为可见正文口径，避免 Markdown 语法污染统计。
- 本次 HTTP API 创建任务仍被登录鉴权拦截，真实验收从后端任务创建函数进入。后续前端一键按钮仍需做一次浏览器端操作验收。

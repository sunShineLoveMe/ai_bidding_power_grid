# 章节生成任务 item 独立表双写验证记录

日期：2026-06-03

目标：为 P0 “拆分任务 item 独立表”落地第一步。新增 `bid_generation_task_items` 与 `bid_generation_task_events`，在不破坏现有 `bid_generation_tasks.items` JSON API 的前提下，开始同步写入独立 item 行和事件日志。

## 执行的数据库迁移

已执行：

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/20260603_create_bid_generation_task_items.sql
```

新增表：

```text
public.bid_generation_task_items
public.bid_generation_task_events
```

同时重新幂等执行了状态模型函数迁移：

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/20260603_update_bid_generation_task_status_model.sql
```

确认数据库函数支持：

```text
leased = true
generating = true
saving = true
```

## 后端改造

改造文件：

```text
backend/db/supabase_repo.py
backend/db/postgres_compat.py
```

实现：

- `create_bid_generation_task(...)` 创建旧任务 JSON 后，同步 upsert 到 `bid_generation_task_items`。
- `update_bid_generation_task_item(...)` 更新旧 JSON 快照后，同步 upsert 到 `bid_generation_task_items`。
- 任务创建、item 更新、取消会写入 `bid_generation_task_events`。
- 本地 Postgres 兼容层新增 JSONB 列适配：
  - `bid_generation_task_items.chunk_events`
  - `bid_generation_task_items.metadata`
  - `bid_generation_task_events.payload`

当前仍保留旧 `bid_generation_tasks.items`，前端/API 不需要立刻改。

## 真实数据库验证

### Repository 直连验证

创建任务并模拟状态：

```text
queued -> leased -> generating -> done
```

验证结果：

```text
task_id: 3b4f9d47-eeed-49aa-be17-daed7ded6bc2
bid_generation_task_items.status = done
generated_len = 4
```

事件写入初次失败：

```text
psycopg.ProgrammingError: cannot adapt type 'dict'
```

根因：`backend/db/postgres_compat.py` 未把 `bid_generation_task_events.payload` 标记为 JSONB。

修复后再次触发事件写入，验证成功：

```text
event_type: final_saved
status: done
message: 双写测试：事件写入验证
payload: {"chars":120,"status":"done","message":"双写测试：事件写入验证","percent":100,...}
```

### 真实 API 验证

通过真实鉴权 API 创建 `autoStart=false` 任务，不触发 Celery/LLM：

```text
task_id: 96751892-d6df-46ee-ad13-860bdc3dbee1
created status: queued
cancelled status: cancelled
```

验证 item 表：

```text
section_id: 28d99271-daef-4530-8dc6-e1fbf486fbaa
status: stopped
message: 已停止
```

优化事件命名后再次验证：

```text
task_id: 6a2ab9cd-18b1-4929-a263-1b486c7c91b9
event_type: task_created
event_type: task_cancelled
```

## 自动化/静态验证

通过：

```bash
.venv/bin/python -m py_compile backend/db/supabase_repo.py backend/db/postgres_compat.py backend/tasks/section_tasks.py backend/services/section_generation.py
.venv/bin/python -m unittest tests.test_api_sections
```

结果：

```text
Ran 7 tests in 0.604s
OK
```

Celery 检查：

```text
active/reserved/scheduled: empty
1 node online
```

## 当前边界

本次完成的是兼容双写，不是完整切换。

尚未完成：

- 调度器直接从 `bid_generation_task_items` lease item。
- `FOR UPDATE SKIP LOCKED` 行级领取。
- worker heartbeat。
- lease 过期 reconciler。
- 前端从 event/item 表展示诊断详情。

下一步建议：实现 P0-03 worker lease 与 heartbeat，让 `bid_generation_task_items` 从“同步影子表”升级为真实调度依据。

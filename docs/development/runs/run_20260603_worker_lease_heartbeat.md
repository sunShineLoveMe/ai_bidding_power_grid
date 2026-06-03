# 2026-06-03 P0-03 Worker Lease / Heartbeat 真实回归记录

## 目标

验证批量章节生成不再只依赖内存中的 Celery 状态或任务 JSON。章节 item 必须支持行级领取、worker lease、heartbeat、过期回收、owner 校验和事件审计。

## 涉及改动

- `sql/20260603_add_bid_generation_task_item_lease.sql`
- `sql/20260603_update_bid_generation_task_status_model.sql`
- `backend/db/supabase_repo.py`
- `backend/db/postgres_compat.py`
- `backend/tasks/section_tasks.py`
- `docs/section-generation-production-remediation-todo.md`

## 已执行数据库脚本

```bash
set -a; source .env; set +a
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/20260603_update_bid_generation_task_status_model.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/20260603_add_bid_generation_task_item_lease.sql
```

执行结果：4 个 `CREATE FUNCTION` 均成功。

## 服务状态

后端：

```bash
set -a; source .env; set +a
.venv/bin/gunicorn -c gunicorn.conf.py --reload main:app
```

健康检查：

```text
GET http://127.0.0.1:8000/api/health
200
{"status": "ok"}
```

Celery：

```bash
set -a; source .env; set +a
.venv/bin/celery -A backend.tasks.celery_app.celery_app worker --loglevel=INFO --concurrency=3
```

worker 使用真实 Redis：

```text
transport: redis://127.0.0.1:16379/0
results: redis://127.0.0.1:16379/0
```

## 静态校验

```bash
.venv/bin/python -m py_compile backend/db/supabase_repo.py backend/db/postgres_compat.py backend/tasks/section_tasks.py
```

结果：通过。

## 真实数据库租约回收测试

测试方式：

1. 通过 repository 创建真实 `bid_generation_tasks` / `bid_generation_task_items` 任务。
2. 调用真实 RPC `lease_bid_generation_task_items` 领取 1 个 item。
3. 手工把该 item 的 `lease_expires_at` 设置为过去时间。
4. 调用真实 RPC `expire_bid_generation_task_items(..., requeue=True)`。
5. 查询任务 JSON 快照和事件表。

结果：

```json
{
  "task_id": "74025a7a-dff0-47d3-9178-d7baac1195d4",
  "section_id": "d78e6e9e-7a71-41b9-9149-8fc6f7759316",
  "leased_status": "leased",
  "leased_attempt": 1,
  "expired_count": 1,
  "expired_status": "queued",
  "latest_json_status": "queued",
  "latest_item_attempt": 1,
  "event_types": [
    "task_created",
    "item_dispatched",
    "lease_expired"
  ]
}
```

结论：过期 lease 可被回收，并能同步回任务 JSON 快照和事件表。

## 真实 API + 真实 LLM 单章节生成测试

测试对象：

- project_id: `70323ce8-f18e-46ca-8d22-33865525a7f7`
- section_id: `e36fee79-9acf-49e6-bd95-7442bfa7d015`
- title: `商务偏离表`
- task_id: `14ab4f89-83f9-48d2-8eda-1d9584c6de24`
- API: `POST /api/bidding/interpretations/<project_id>/section-generation-tasks`
- autoStart: `true`
- target_words: `800`

轮询结果摘要：

```text
poll 0: task=queued, item=queued, percent=0
poll 1: task=running, item=generating, percent=2, attempt=1, has_attempt_id=true, has_worker_id=true
poll 3: task=running, item=generating, percent=55, chars=443
poll 4: task=running, item=generating, percent=98, chars=838
poll 6: heartbeat_at 更新为 2026-06-03T17:42:26.016052+08:00
poll 14: heartbeat_at 更新为 2026-06-03T17:42:41.431655+08:00
poll 16: task=completed, item=done, percent=100, chars=1984
```

item 表最终状态：

```json
{
  "status": "done",
  "attempt": 1,
  "attempt_id": "a7c21895-4caf-43be-9d7e-773e5b4252a7",
  "worker_id": "celery:chrisdeMacBook-Pro.local:5637",
  "heartbeat_at": "2026-06-03T17:42:41.431655+08:00",
  "lease_expires_at": "2026-06-03T17:57:41.431655+08:00",
  "first_token_at": "2026-06-03T09:42:18.992427+08:00",
  "last_token_at": "2026-06-03T09:42:45.574889+08:00",
  "final_saved_at": "2026-06-03T09:42:45.574894+08:00",
  "chunk_seq": 1645
}
```

章节落盘结果：

```json
{
  "section_status": "generated",
  "section_content_chars": 2915,
  "section_writing_error": null
}
```

事件表摘要：

```text
task_created
item_dispatched
worker_started
heartbeat
progress_flushed
heartbeat
progress_flushed
heartbeat
saving
final_saved
```

本次单章节共产生 97 条事件。当前用于诊断是可接受的，后续 P1 可按前端展示需要对 `progress_flushed` 做节流或聚合。

AI usage 记录：

```json
[
  {
    "provider": "deepseek",
    "model": "deepseek-v4-flash",
    "operation_type": "text_generation",
    "stage": "bid_section_length_supplement",
    "success": true,
    "latency_ms": 17270,
    "total_tokens": 5007
  },
  {
    "provider": "deepseek",
    "model": "deepseek-v4-flash",
    "operation_type": "text_generation",
    "stage": "bid_section_stream",
    "success": true,
    "latency_ms": 10149,
    "total_tokens": 3860
  }
]
```

结论：真实 API、真实 Celery、真实 Redis、真实 PostgreSQL、真实 DeepSeek 调用均跑通。该任务没有使用 mock。

## Celery 队列收尾状态

```text
inspect active: empty
inspect reserved: empty
```

## 已验证能力

- 调度器按 item 表行级 lease 领取任务。
- worker 有明确 `worker_id`、`attempt_id`。
- worker 生成期间 heartbeat 正常刷新。
- 过期 lease 可回收并重入队。
- 旧 worker 在失去 owner 后不能继续写入最终状态的保护逻辑已实现；本轮通过过期回收和完整 LLM 成功链路验证了相关数据路径。
- 最终正文只在模型链路完成后保存为章节 `generated`。
- DeepSeek usage 成功记录到 `ai_usage_logs`。

## 剩余风险

- P0-05 尚未完成：模型流墙钟超时和最后 token 超时仍需要补齐，否则模型持续慢吐时仍可能长时间占用 worker。
- P0-06 尚未完成完整重试语义：当前已有 owner 校验，但还需要显式“重试某一小节/恢复未完成任务”的 API 与前端动作。
- P0-07 尚未完成：全文生成仍可能按较大章节生成，后续应切到叶子小节级生成，章/节只作为结构容器。
- P1 前端诊断面板尚未完成：事件表已有数据基础，但 UI 还没有把 lease、heartbeat、first token、last token、final save 展示给用户。
- 本轮未在真实 LLM 正在流式输出时强杀 worker。强杀恢复应在 P0-05 超时策略完成后追加回归，避免真实任务无限等待时缺少模型侧退出边界。

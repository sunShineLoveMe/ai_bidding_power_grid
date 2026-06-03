# 2026-06-03 P0-05 模型流超时真实回归记录

## 目标

防止单个章节在 DeepSeek/DashScope 流式输出阶段无限占用 Celery worker。章节生成必须有明确的墙钟上限和最后 token 空窗上限；触发超时后不能继续 fallback 长时间阻塞，应保存草稿并进入明确终态。

## 涉及改动

- `backend/ai/qwen_client.py`
- `backend/ai/section_writer.py`
- `backend/services/section_generation.py`
- `backend/tasks/section_tasks.py`
- `backend/db/supabase_repo.py`
- `frontend/src/api/bidProject.ts`
- `frontend/src/pages/BidEditor/index.tsx`
- `sql/20260603_update_bid_generation_task_status_model.sql`

## 配置

默认生产配置：

```text
section_stream_wall_timeout_seconds = 300
section_stream_idle_timeout_seconds = 45
```

可用环境变量覆盖：

```bash
BID_SECTION_STREAM_WALL_TIMEOUT_SECONDS=300
BID_SECTION_STREAM_IDLE_TIMEOUT_SECONDS=45
```

测试时使用短超时：

```bash
BID_SECTION_STREAM_WALL_TIMEOUT_SECONDS=5
BID_SECTION_STREAM_IDLE_TIMEOUT_SECONDS=20
```

## 静态校验

```bash
.venv/bin/python -m py_compile \
  backend/ai/qwen_client.py \
  backend/ai/section_writer.py \
  backend/services/section_generation.py \
  backend/tasks/section_tasks.py \
  backend/db/supabase_repo.py \
  backend/db/postgres_compat.py
```

结果：通过。

前端：

```bash
cd frontend
npm run build -- --mode development
```

结果：通过。仅保留既有 chunk size / dynamic import 警告。

数据库函数：

```bash
set -a; source .env; set +a
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/20260603_update_bid_generation_task_status_model.sql
```

结果：`CREATE FUNCTION`。

## 真实超时回归

测试服务：

- 后端：`gunicorn -c gunicorn.conf.py --reload main:app`
- Celery：真实 Redis `redis://127.0.0.1:16379/0`
- LLM：真实 DeepSeek `deepseek-v4-flash`
- 未使用 mock

测试任务：

- project_id: `70323ce8-f18e-46ca-8d22-33865525a7f7`
- section_id: `1513ef70-234a-4f66-a70a-54ab41a6f9b8`
- title: `分部分项工程量清单报价`
- task_id: `96e0d1f7-f8fc-463b-b30d-7152c34c7a85`
- 测试超时：墙钟 5 秒

轮询结果：

```text
poll 0: task=queued, item=queued
poll 1: task=running, item=generating
poll 4: task=partial_failed, item=partial_generated, chars=14
```

最终状态：

```json
{
  "final_status": "partial_failed",
  "final_item_status": "partial_generated",
  "chars": 14,
  "error": "MODEL_STREAM_WALL_TIMEOUT: 模型流式输出超过单章节最大时长 5 秒，已停止继续等待。"
}
```

AI usage：

```json
{
  "stage": "bid_section_stream",
  "success": false,
  "error_code": "MODEL_STREAM_WALL_TIMEOUT",
  "latency_ms": 5073,
  "total_tokens": 4400
}
```

事件尾部：

```text
task_created
item_dispatched
worker_started
heartbeat
partial_generated
```

章节状态：

```json
{
  "section_status": "partial_generated",
  "generation_status": "partial_generated",
  "writing_status": "partial_generated",
  "writing_error_code": "MODEL_STREAM_WALL_TIMEOUT",
  "draft_chars": 14
}
```

关键确认：本次 timeout 后没有新的 `bid_section_sync_fallback` 记录，说明模型流超时不会继续走同步 fallback 占用 worker。

## 默认配置正常生成回归

恢复默认 Celery worker：

```bash
set -a; source .env; set +a
.venv/bin/celery -A backend.tasks.celery_app.celery_app worker --loglevel=INFO --concurrency=3
```

测试任务：

- section_id: `333c13ac-1dbc-4d0a-bbe0-54533fb87f63`
- title: `措施项目清单报价`
- task_id: `2875711b-16c9-416b-b5d3-139829fb9449`

最终状态：

```json
{
  "final_status": "completed",
  "final_item_status": "done",
  "chars": 2824,
  "error": null
}
```

AI usage：

```json
{
  "stage": "bid_section_stream",
  "success": true,
  "error_code": null,
  "latency_ms": 33793,
  "total_tokens": 5934
}
```

item 表：

```json
{
  "status": "done",
  "chars": 2824,
  "first_token_at": "2026-06-03T21:02:15.453698+08:00",
  "last_token_at": "2026-06-03T21:02:39.054200+08:00",
  "final_saved_at": "2026-06-03T21:02:39.054205+08:00",
  "error": null
}
```

## 收尾状态

```text
GET /api/health => 200 {"status":"ok"}
celery inspect active => empty
celery inspect reserved => empty
```

## 结论

P0-05 基础版通过真实环境验证。模型流式输出现在有明确退出边界；超时后会保留草稿、写入错误码、结束 item 状态，并继续释放 worker 槽位。

## 剩余风险

- 当前 `partial_generated` 只是终态和草稿保存，尚未提供“从草稿续写”的专用 API。
- 前端已能识别 `partial_generated`，但还没有完整诊断面板展示墙钟、最后 token、错误码和草稿操作入口。
- 单章墙钟默认 300 秒是否合适，需要在 10 章、全文 69 章压测后再按客户演示体验调优。

# 2026-06-03 P0-06 取消、恢复、重试语义真实回归记录

## 范围

- 单章节 item 手动重试。
- 批量任务从 `partial_generated` 恢复。
- 恢复后取消，验证未完成 item 被停止。
- 前端目录行展示“草稿待续写”和“重试”入口。

## 环境

- 后端：`http://127.0.0.1:8000`，Gunicorn reload 模式。
- Redis：`redis://127.0.0.1:16379/0`。
- Celery：`backend.tasks.celery_app.celery_app`，`--concurrency=3`。
- 数据库：真实 Postgres/Supabase 兼容层。
- 模型：真实 DeepSeek 流式写作链路，未使用 mock。
- 项目：`70323ce8-f18e-46ca-8d22-33865525a7f7`。

## 代码变更

- `backend/db/supabase_repo.py`
  - 新增 `requeue_bid_generation_task_item`。
  - 新增 `resume_bid_generation_task`。
  - 重试时清空旧 `attempt_id`、`worker_id`、`lease_expires_at`、`heartbeat_at`、保存时间与错误信息。
- `backend/api/sections.py`
  - 新增单 item retry API。
  - 新增任务 resume API。
- `frontend/src/api/bidProject.ts`
  - 新增 `retrySectionGenerationTaskItem`。
  - 新增 `resumeSectionGenerationTask`。
- `frontend/src/pages/BidEditor/index.tsx`
  - `partial_generated` 显示为“草稿待续写”。
  - 对可重试状态展示“重试”按钮并调用真实 retry API。

## 静态回归

```bash
.venv/bin/python -m py_compile backend/api/sections.py backend/db/supabase_repo.py backend/tasks/section_tasks.py
cd frontend && npm run build -- --mode development
```

结果：

- Python 编译通过。
- 前端构建通过，仅保留既有 chunk size / dynamic import 警告。

## 真实重试验证

目标：

- `task_id=96e0d1f7-f8fc-463b-b30d-7152c34c7a85`
- `section_id=1513ef70-234a-4f66-a70a-54ab41a6f9b8`

操作：

```http
POST /api/bidding/interpretations/70323ce8-f18e-46ca-8d22-33865525a7f7/section-generation-tasks/96e0d1f7-f8fc-463b-b30d-7152c34c7a85/items/1513ef70-234a-4f66-a70a-54ab41a6f9b8/retry
```

请求：

```json
{
  "autoStart": true,
  "preserveDraft": true,
  "reason": "p006_real_retry"
}
```

结果：

- API 返回后 item 重新进入 `queued`。
- 旧 `attempt_id`、`worker_id` 被清空。
- Celery 启动新 attempt。
- 最终 item 状态为 `done`，`attempt=2`，`chars=1994`。
- 最新 AI 日志 `success=true`，`total_tokens=5208`，`error_code=null`。

数据库证据：

```text
status=done
attempt=2
attempt_id=6aeccb9b-12f3-4e98-8a6b-04b48e1463d5
worker_id=celery:chrisdeMacBook-Pro.local:21873
error=null
chars=1994
event_tail=progress_flushed -> saving -> final_saved
```

## 真实恢复与取消验证

目标：

- `task_id=21c26c56-aec5-44da-80cf-333921dd4927`
- 原 item 状态：`partial_generated`

恢复操作：

```http
POST /api/bidding/interpretations/70323ce8-f18e-46ca-8d22-33865525a7f7/section-generation-tasks/21c26c56-aec5-44da-80cf-333921dd4927/resume
```

请求：

```json
{
  "autoStart": false,
  "preserveDraft": true,
  "statuses": ["partial_generated"]
}
```

结果：

- item 重新进入 `queued`。
- 记录 `item_requeued` 和 `task_resumed` 事件。

随后调用任务取消接口，结果：

- task 状态为 `cancelled`。
- item 状态为 `stopped`。
- 记录 `task_cancelled` 事件。

数据库证据：

```text
item.status=stopped
item.attempt_id=null
item.worker_id=null
events=item_requeued -> task_resumed -> task_cancelled
```

## 结论

P0-06 基础版通过真实环境验证。当前版本已经具备单章节重试、批量恢复和取消后状态同步能力。旧 worker 覆盖风险主要通过 `attempt_id`、`worker_id`、lease owner 校验和重试时清空旧 lease 来控制。

后续仍需补齐：

- 记录 Celery task id 并支持 revoke 已投递任务。
- 在前端任务详情中展示事件时间线、worker、attempt、lease 和 heartbeat。

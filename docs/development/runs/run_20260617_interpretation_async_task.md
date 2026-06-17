# Run 20260617 - AI 深度解读后台任务化与进度轮询

## 背景

真实项目 `4390e1ff-2d62-4230-802a-b5dc829145f2` 的 AI 深度解读首跑包含 14 个 segment 和 1 个 merge。原实现把完整 DeepSeek 分段/融合流程放在同步 HTTP 请求中，耗时接近 5-6 分钟，容易造成前端长时间等待、超时或用户误判失败。

## 改动

### 后端

- 新增 PostgreSQL 表：`bid_interpretation_tasks`
  - 迁移文件：`migrations/postgres/008_bid_interpretation_tasks.sql`
  - 初始化脚本：`scripts/init_postgres_schema.sh`

- 新增仓储函数：
  - `create_bid_interpretation_task`
  - `get_bid_interpretation_task`
  - `update_bid_interpretation_task`

- 新增 Celery 任务：
  - `bid.interpretation.generate_report`
  - 文件：`backend/tasks/interpretation_tasks.py`

- 新增 API：
  - `POST /api/bidding/interpretations/<project_id>/ai-report-tasks`
  - `GET /api/bidding/interpretations/<project_id>/ai-report-tasks/<task_id>`

- `backend/ai/interpreter.py` 支持进度回调：
  - segmenting
  - merging
  - single
  - completed

### 前端

- `frontend/src/api/bidProject.ts`
  - `generateAIInterpretation` 改为创建任务并轮询任务状态。

- `frontend/src/components/workflow/BidWorkflow.tsx`
  - 上传自动流程展示 AI 解读后台任务进度。

- `frontend/src/pages/Interpretation/index.tsx`
  - 手动点击“生成 AI 解读”后展示任务状态、分段进度和失败信息。

## 真实环境处理

### PostgreSQL 迁移

```bash
set -a; source .env; set +a
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/postgres/008_bid_interpretation_tasks.sql
```

结果：

```text
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE TRIGGER
```

### Celery worker

重启 worker 后确认任务注册：

```text
bid.interpretation.generate_report
```

同一 worker 仍保留既有任务：

```text
bid.export.docx
bid.knowledge.sync_and_parse
bid.outline.refine
bid.parse.*
bid.sections.*
```

## 真实回归

### API 缓存命中

对真实项目 `4390e1ff-2d62-4230-802a-b5dc829145f2` 调用：

```bash
POST /api/bidding/interpretations/4390e1ff-2d62-4230-802a-b5dc829145f2/ai-report-tasks
GET  /api/bidding/interpretations/4390e1ff-2d62-4230-802a-b5dc829145f2/ai-report-tasks/9279d834-04b0-4c28-bbb4-20cccdae27d7
```

结果：

```text
HTTP 200
cached=true
status=completed
progress=100
```

说明已有 `project_meta.ai_report` 时不会重复消耗 DeepSeek。

### Redis/Celery 真实投递

手动创建真实任务并投递到 Celery worker：

```text
created_task_id=13927b81-b31f-425e-b1ef-c1daf8e6d361
celery_id=8d4b5f0a-de53-45c4-96d7-8604c8fa98b4
poll queued 0
poll completed 100
```

最终 metadata：

```text
stage=completed
segmented_interpretation.segment_count=14
segmented_interpretation.success_count=14
segmented_interpretation.failure_count=0
```

## 测试

```bash
.venv/bin/python -m pytest tests/test_celery_interpretation_tasks.py tests/test_segmented_interpreter.py tests/test_supabase_repo.py tests/test_postgres_schema_init.py
npm run build
```

结果：

```text
11 passed
npm run build PASS
```

## 结论

P1C-5 完成。AI 深度解读已从同步长 HTTP 等待迁移为后台任务 + 状态轮询。短期仍保留旧 `/ai-report` 同步接口作为兼容入口，但前端主流程已切换到 `/ai-report-tasks`，用户侧可看到任务进度，浏览器刷新或网络等待不再直接等同于任务失败。

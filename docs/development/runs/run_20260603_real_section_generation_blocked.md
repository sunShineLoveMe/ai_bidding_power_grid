# 真实生产链路章节生成测试记录：阻断

日期：2026-06-03

目标：不使用 mock，连接真实后端、真实 Redis/Celery、真实数据库和真实 LLM，模拟生产环境测试“按章节生成正文/一键生成全文”链路。

结论：本次没有触发真实 LLM 生成。原因是 Celery worker 未运行，且当前环境缺少 Celery 必需的 `REDIS_URL` 配置，Celery app 无法加载。按测试要求，发现关键服务未就绪后立即停止。

## 环境检查结果

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| 后端 Gunicorn | 通过 | `http://127.0.0.1:3012/api/health` 返回 `200 OK` |
| 前端 Vite | 通过 | 进程存在，端口 `5173` |
| Redis TCP 端口 | 通过 | `127.0.0.1:16379` 可连接 |
| Celery worker 进程 | 失败 | 进程列表未发现 Celery worker |
| Celery app 加载 | 失败 | 缺少 `REDIS_URL`，无法加载 Celery app |
| 数据库连接 | 未继续 | Celery 已阻断，未进入真实任务创建 |
| DeepSeek LLM | 未调用 | Celery 已阻断，未触发真实 LLM |

## 关键命令与证据

### 后端健康检查

```bash
curl -sS -m 5 -i http://127.0.0.1:3012/api/health
```

结果：

```text
HTTP/1.1 200 OK
{
  "status": "ok"
}
```

### Redis 端口检查

```bash
nc -vz 127.0.0.1 16379
```

结果：

```text
Connection to 127.0.0.1 port 16379 [tcp/*] succeeded!
```

### Celery worker 检查

进程列表中未发现 Celery worker，仅发现 Gunicorn 和 Vite。

### Celery app 加载检查

```bash
set -a; source .env 2>/dev/null || true; set +a
.venv/bin/celery -A backend.tasks.celery_app.celery_app inspect ping -d celery@$(hostname) --timeout=3
```

结果：

```text
REDIS_URL 未配置，Celery 无法连接消息代理（broker）。请在环境变量中配置 REDIS_URL。
RuntimeError: REDIS_URL is not configured; Celery broker cannot start
```

## 阻断原因

真实生产链路中，批量章节生成流程是：

```text
前端创建章节生成任务
  -> 后端写入 bid_generation_tasks
  -> 后端投递 Celery 任务
  -> Celery worker 调用真实 DeepSeek
  -> worker 回写任务状态和章节正文
  -> 前端轮询展示进度
```

当前 Celery app 因缺少 `REDIS_URL` 无法加载，worker 也没有运行。此时如果继续创建批量任务，会得到“任务已创建但无人消费”的假测试结果，不能代表真实生产环境。因此本次测试在 LLM 调用前停止。

## 需要先处理

1. 在 `.env` 中补齐 `REDIS_URL`，建议与当前 Redis 端口一致：

```env
REDIS_URL=redis://127.0.0.1:16379/0
```

2. 启动 Celery worker：

```bash
set -a; source .env; set +a
.venv/bin/celery -A backend.tasks.celery_app.celery_app worker --loglevel=INFO --concurrency=3
```

3. 再执行真实章节生成测试，至少覆盖：

- 创建真实 `section-generation-task`
- 确认 item 从 `queued -> leased -> generating -> saving -> done`
- 确认 `running_count` 对新状态计数正确
- 确认 DeepSeek `bid_section_stream` 出现在 `ai_usage_logs`
- 确认章节正文落入 `bid_sections.content`
- 确认失败时能看到明确错误而不是卡死

## 本次是否消耗 LLM 额度

没有。本次测试在 Celery 服务检查阶段停止，没有调用 DeepSeek 或百炼。

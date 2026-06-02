# HTTP 全链路冒烟报告

> 生成时间：2026-06-02T14:26:24.958047+00:00
> 结果：FAIL
> 后端：`http://127.0.0.1:3012`
> JSON：`docs/development/runs/run_20260602_222624_http_smoke_failed.json`

## 关键 ID

- project_id：`-`
- file_id：`-`
- supabase_file_id：`-`
- docx_task_id：`-`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |

## 错误

HTTPConnectionPool(host='127.0.0.1', port=3012): Max retries exceeded with url: /api/ready (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=3012): Failed to establish a new connection: [Errno 1] Operation not permitted"))

# HTTP 全链路冒烟报告

> 生成时间：2026-06-02T14:30:31.008349+00:00
> 结果：FAIL
> 后端：`http://127.0.0.1:3012`
> JSON：`docs/development/runs/run_20260602_223031_http_smoke_failed.json`

## 关键 ID

- project_id：`-`
- file_id：`-`
- supabase_file_id：`-`
- docx_task_id：`-`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |
| ok | `check_ready` | 2272 | status=ok checks=5 |
| ok | `identify_user` | 1 | fallback=smoke-user; status=401 |

## 错误

HTTP 401: {"error": "请先登录后再访问。"}

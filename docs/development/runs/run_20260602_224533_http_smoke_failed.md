# HTTP 全链路冒烟报告

> 生成时间：2026-06-02T14:45:33.635699+00:00
> 结果：FAIL
> 后端：`http://127.0.0.1:3012`
> JSON：`docs/development/runs/run_20260602_224533_http_smoke_failed.json`

## 关键 ID

- project_id：`49b9d507-5a39-4c84-b324-f13db2f263ce`
- file_id：`d6950bef-20f5-4e86-9430-576a47c5865c`
- supabase_file_id：`45299ba3-ffaf-49da-bc40-7faebef12446`
- docx_task_id：`-`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |
| ok | `check_ready` | 2163 | status=ok checks=5 |
| ok | `login` | 75 | user=smoke-20260602-2230 |
| ok | `wait_parse_completed` | 7 | parseStatus=indexed parser=native_text |
| ok | `query_interpretation` | 14 | hasAnalysis=False |

## 错误

HTTP 500: {"error": "服务器处理失败，请联系管理员查看后端日志。"}

# HTTP 全链路冒烟报告

> 生成时间：2026-06-03T02:37:22.425663+00:00
> 结果：FAIL
> 后端：`http://127.0.0.1:3012`
> JSON：`docs/development/runs/run_20260603_103722_http_smoke_failed.json`

## 关键 ID

- project_id：`6d54c1c3-b1c0-4f18-8fdd-6d8f9817500d`
- file_id：`01830221-d5ea-4411-91c2-051706257eec`
- supabase_file_id：`3cbd995e-21ba-4885-abe3-aade5c27ab46`
- docx_task_id：`-`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |
| ok | `check_ready` | 2288 | status=ok checks=5 |
| ok | `login` | 100 | user=smoke-20260602-2230 |
| ok | `identify_user` | 8 | userId=0d7aebef-cca1-4b23-86a1-46ed89336d48 |
| ok | `upload_tender` | 32 | projectId=6d54c1c3-b1c0-4f18-8fdd-6d8f9817500d fileId=01830221-d5ea-4411-91c2-051706257eec supabaseFileId=3cbd995e-21ba-4885-abe3-aade5c27ab46 |
| ok | `wait_parse_completed` | 10110 | parseStatus=indexed parser=mineru |
| ok | `query_interpretation` | 21 | hasAnalysis=True |
| ok | `generate_ai_report` | 53167 | ok |
| ok | `generate_outline` | 1328 | chapters=31 |
| ok | `list_sections` | 6 | sections=31 |

## 错误

HTTPConnectionPool(host='127.0.0.1', port=3012): Max retries exceeded with url: /api/bidding/interpretations/6d54c1c3-b1c0-4f18-8fdd-6d8f9817500d/section-generation-tasks/956328e3-d033-4eaf-8394-6a712ed0baac (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=3012): Failed to establish a new connection: [Errno 61] Connection refused"))

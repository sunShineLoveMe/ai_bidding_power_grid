# HTTP 全链路冒烟报告

> 生成时间：2026-06-03T02:30:34.489835+00:00
> 结果：FAIL
> 后端：`http://127.0.0.1:3012`
> JSON：`docs/development/runs/run_20260603_103034_http_smoke_failed.json`

## 关键 ID

- project_id：`61919c43-9a52-4afb-b054-749437c979df`
- file_id：`171ee504-d6f4-4e19-a7b0-51357bf6516c`
- supabase_file_id：`9dc3d35d-a1c7-438b-8842-cad01973807f`
- docx_task_id：`-`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |
| ok | `check_ready` | 2209 | status=ok checks=5 |
| ok | `login` | 98 | user=smoke-20260602-2230 |
| ok | `identify_user` | 6 | userId=e8800a37-d1c9-4d86-aaf0-82209ae71198 |
| ok | `upload_tender` | 33 | projectId=61919c43-9a52-4afb-b054-749437c979df fileId=171ee504-d6f4-4e19-a7b0-51357bf6516c supabaseFileId=9dc3d35d-a1c7-438b-8842-cad01973807f |

## 错误

解析已完成但未确认走 MinerU: {"downloadRetryCount": 0, "error": "Error -3 while decompressing data: invalid code lengths set", "errorType": "error", "failureStage": null, "fileId": "171ee504-d6f4-4e19-a7b0-51357bf6516c", "mineru": {"artifacts": {"content_list_path": "parsed_outputs/171ee504-d6f4-4e19-a7b0-51357bf6516c/extract/0476f7ff-100c-4f21-bd60-255266a78036_content_list.json", "download_info": {"downloaded_bytes": 0, "resume_enabled": true, "resumed_from_bytes": 0, "url_host": "cdn-mineru.openxlab.org.cn", "used_curl_f...

# HTTP 全链路冒烟报告

> 生成时间：2026-06-02T14:40:58.538912+00:00
> 结果：FAIL
> 后端：`http://127.0.0.1:3012`
> JSON：`docs/development/runs/run_20260602_224058_http_smoke_failed.json`

## 关键 ID

- project_id：`49b9d507-5a39-4c84-b324-f13db2f263ce`
- file_id：`d6950bef-20f5-4e86-9430-576a47c5865c`
- supabase_file_id：`45299ba3-ffaf-49da-bc40-7faebef12446`
- docx_task_id：`-`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |
| ok | `check_ready` | 2144 | status=ok checks=5 |
| ok | `login` | 95 | user=smoke-20260602-2230 |
| ok | `identify_user` | 8 | userId=5637d875-55ac-4156-9023-3680b6a9c09e |
| ok | `upload_tender` | 34 | projectId=49b9d507-5a39-4c84-b324-f13db2f263ce fileId=d6950bef-20f5-4e86-9430-576a47c5865c supabaseFileId=45299ba3-ffaf-49da-bc40-7faebef12446 |

## 错误

等待解析完成超时，最后状态: {"downloadRetryCount": 0, "error": null, "errorType": null, "failureStage": null, "fileId": "d6950bef-20f5-4e86-9430-576a47c5865c", "mineru": {"file_name": "power-grid-smoke-tender.md", "parse_recovery_started_at": "2026-06-02T14:39:01Z", "parse_status": "supabase_synced", "parser": "mineru", "project_id": "49b9d507-5a39-4c84-b324-f13db2f263ce", "retryable": true, "source_file": "uploads/1db67a4d-e0f7-4ae2-8ba5-3b00d78b7ab5-power-grid-smoke-tender.md", "supabase_file_id": "45299ba3-ffaf-49da-bc4...

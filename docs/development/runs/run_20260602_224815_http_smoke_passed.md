# HTTP 全链路冒烟报告

> 生成时间：2026-06-02T14:48:15.675003+00:00
> 结果：PASS
> 后端：`http://127.0.0.1:3012`
> JSON：`docs/development/runs/run_20260602_224815_http_smoke_passed.json`

## 关键 ID

- project_id：`e3d516b7-c2e0-4349-8ede-efab6241076b`
- file_id：`5e5bb8da-f064-4939-8d77-612956d4791c`
- supabase_file_id：`3540e2b3-44c2-4bb8-b1e5-6f8b5dc8f7b1`
- docx_task_id：`b52535e5-f729-4775-9ad3-fab904b68856`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |
| ok | `check_ready` | 2105 | status=ok checks=5 |
| ok | `login` | 81 | user=smoke-20260602-2230 |
| ok | `identify_user` | 9 | userId=8b817688-077f-4c87-bcab-44380518f9f5 |
| ok | `upload_tender` | 29 | projectId=e3d516b7-c2e0-4349-8ede-efab6241076b fileId=5e5bb8da-f064-4939-8d77-612956d4791c supabaseFileId=3540e2b3-44c2-4bb8-b1e5-6f8b5dc8f7b1 |
| ok | `wait_parse_completed` | 12115 | parseStatus=indexed parser=mineru |
| ok | `query_interpretation` | 25 | hasAnalysis=True |
| ok | `generate_ai_report` | 43405 | ok |
| ok | `generate_outline` | 1331 | chapters=31 |
| ok | `list_sections` | 6 | sections=31 |
| ok | `generate_one_section` | 24768 | sectionId=8f765a7e-3a53-4197-a234-c5d6b5ef8651 chunks=2299 |
| ok | `run_compliance_check` | 25 | rows=3 coverage=None |
| ok | `create_docx_export` | 9 | taskId=b52535e5-f729-4775-9ad3-fab904b68856 |
| ok | `wait_docx_export` | 6042 | status=completed path=outputs/03_Bi_Xu_Zhao_Biao_De_Gong_Cheng_Xiang_Mu_Gui_Ding__a8122eb9/03_必须招标的工程项目规定_a8122eb9.docx |

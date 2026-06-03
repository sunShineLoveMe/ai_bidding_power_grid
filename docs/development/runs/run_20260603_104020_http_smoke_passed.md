# HTTP 全链路冒烟报告

> 生成时间：2026-06-03T02:40:20.042110+00:00
> 结果：PASS
> 后端：`http://127.0.0.1:3012`
> JSON：`docs/development/runs/run_20260603_104020_http_smoke_passed.json`

## 关键 ID

- project_id：`a85a9c3e-0ad3-49c9-a702-661bc15fe775`
- file_id：`df326316-e84d-469b-8355-eccc6a223a1e`
- supabase_file_id：`410f46cd-306b-46f2-8897-7e1276da1f8a`
- docx_task_id：`18dc9798-412f-4f1b-99de-820b74d5bee8`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |
| ok | `check_ready` | 2171 | status=ok checks=5 |
| ok | `login` | 90 | user=smoke-20260602-2230 |
| ok | `identify_user` | 7 | userId=674bb5eb-ef67-4e31-8230-f7102f9e29b5 |
| ok | `upload_tender` | 35 | projectId=a85a9c3e-0ad3-49c9-a702-661bc15fe775 fileId=df326316-e84d-469b-8355-eccc6a223a1e supabaseFileId=410f46cd-306b-46f2-8897-7e1276da1f8a |
| ok | `wait_parse_completed` | 12091 | parseStatus=indexed parser=mineru |
| ok | `query_interpretation` | 32 | hasAnalysis=True |
| ok | `generate_ai_report` | 61590 | ok |
| ok | `generate_outline` | 1350 | chapters=31 |
| ok | `list_sections` | 8 | sections=31 |
| ok | `generate_one_section` | 48351 | sectionId=40ed4896-f7ff-4dc2-9568-b4226450bed8 taskId=87b1bb81-9034-46f5-9667-63d3f996a60a |
| ok | `run_compliance_check` | 39 | rows=3 coverage=None |
| ok | `create_docx_export` | 15 | taskId=18dc9798-412f-4f1b-99de-820b74d5bee8 |
| ok | `wait_docx_export` | 8055 | status=completed path=outputs/03_Bi_Xu_Zhao_Biao_De_Gong_Cheng_Xiang_Mu_Gui_Ding__a8122eb9/03_必须招标的工程项目规定_a8122eb9.docx |

# HTTP 全链路冒烟报告

> 生成时间：2026-06-25T13:34:16.151416+00:00
> 结果：PASS
> 后端：`http://127.0.0.1:3012`
> JSON：`docs/development/runs/run_20260625_contract_mvp_full_http_smoke.json`

## 关键 ID

- project_id：`5ea0b61e-4e1c-46b7-9749-0d86fe28c7fa`
- file_id：`dc11e66d-2d33-44c0-afcc-e04146f49b91`
- supabase_file_id：`fbc4e459-635a-43ef-9afc-8d7d3a1ce525`
- docx_task_id：`8c288ea9-4e24-4c59-9d89-84933e939527`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |
| ok | `check_ready` | 2102 | status=ok checks=5 |
| ok | `login` | 77 | user=contract_mvp_213205 |
| ok | `identify_user` | 6 | userId=7fdf256c-37d7-4d41-849f-f1cb859da5ca |
| ok | `upload_tender` | 24 | projectId=5ea0b61e-4e1c-46b7-9749-0d86fe28c7fa fileId=dc11e66d-2d33-44c0-afcc-e04146f49b91 supabaseFileId=fbc4e459-635a-43ef-9afc-8d7d3a1ce525 |
| ok | `wait_parse_completed` | 2027 | parseStatus=indexed parser=native_text |
| ok | `query_interpretation` | 46 | hasAnalysis=True |
| ok | `generate_ai_report` | 75367 | ok |
| ok | `generate_outline` | 5321 | chapters=102 |
| ok | `list_sections` | 14 | sections=102 |
| ok | `generate_sections` | 32311 | sections=1 done=1 taskId=d4e46ffa-6f9c-4351-9314-508b88dcd931 |
| ok | `run_compliance_check` | 57 | rows=5 coverage=None |
| ok | `create_docx_export` | 1017 | taskId=8c288ea9-4e24-4c59-9d89-84933e939527 |
| ok | `wait_docx_export` | 6051 | status=completed path=outputs/Guo_Wang_Pei_Dian_Zi_Dong_Hua_Zhong_Duan_Cai_Gou_Xiang_Mu/国网配电自动化终端采购项目投标文件-河北泰昌电力器材科技有限公司-图文.docx |

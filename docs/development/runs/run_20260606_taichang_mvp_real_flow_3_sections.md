# HTTP 全链路冒烟报告

> 生成时间：2026-06-06T10:50:38.165937+00:00
> 结果：PASS
> 后端：`http://127.0.0.1:8000`
> JSON：`docs/development/runs/run_20260606_taichang_mvp_real_flow_3_sections.json`

## 关键 ID

- project_id：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`
- file_id：`2a58243e-e7f6-4d49-bd82-f6f4608de49f`
- supabase_file_id：`3cda2559-159e-41ba-99fd-7e8cfdc5cc4e`
- docx_task_id：`1e49c5ac-7b94-476a-95da-beff0f72b77f`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |
| ok | `check_ready` | 2144 | status=ok checks=5 |
| ok | `login` | 100 | user=taichang-smoke-1780742625 |
| ok | `identify_user` | 6 | userId=d175d4d0-f7c3-44b2-923b-66971447c964 |
| ok | `upload_tender` | 31 | projectId=4bc3ee73-9ec5-4184-aafd-eaede9f90798 fileId=2a58243e-e7f6-4d49-bd82-f6f4608de49f supabaseFileId=3cda2559-159e-41ba-99fd-7e8cfdc5cc4e |
| ok | `wait_parse_completed` | 12142 | parseStatus=indexed parser=native_text |
| ok | `query_interpretation` | 72 | hasAnalysis=True |
| ok | `generate_ai_report` | 344604 | ok |
| ok | `generate_outline` | 3734 | chapters=74 |
| ok | `list_sections` | 16 | sections=74 |
| ok | `generate_sections` | 34460 | sections=3 done=3 taskId=7f1fade4-8dcc-4e85-aeb8-5e092ae19e7e |
| ok | `run_compliance_check` | 236 | rows=220 coverage=None |
| ok | `create_docx_export` | 13 | taskId=1e49c5ac-7b94-476a-95da-beff0f72b77f |
| ok | `wait_docx_export` | 4061 | status=completed path=outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购招标文件.docx |

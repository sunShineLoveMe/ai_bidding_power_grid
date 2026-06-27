# HTTP 全链路冒烟报告

> 生成时间：2026-06-06T11:00:24.242162+00:00
> 结果：PASS
> 后端：`http://127.0.0.1:8000`
> JSON：`docs/development/runs/run_20260606_taichang_mvp_real_flow_30_sections.json`

## 关键 ID

- project_id：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`
- file_id：`-`
- supabase_file_id：`-`
- docx_task_id：`5653a7b6-384b-4a06-9509-6321e8208888`

## 步骤

| 状态 | 步骤 | 耗时(ms) | 详情 |
| --- | --- | ---: | --- |
| ok | `check_ready` | 2255 | status=ok checks=5 |
| ok | `login` | 120 | user=taichang-smoke-1780742625 |
| ok | `query_interpretation` | 53 | hasAnalysis=True |
| ok | `generate_outline` | 4295 | chapters=74 |
| ok | `list_sections` | 18 | sections=74 |
| ok | `generate_sections` | 278151 | sections=30 done=30 taskId=b6d7da7c-d49b-4cfb-8a39-bdea9b79ef50 |
| ok | `run_compliance_check` | 385 | rows=220 coverage=None |
| ok | `create_docx_export` | 15 | taskId=5653a7b6-384b-4a06-9509-6321e8208888 |
| ok | `wait_docx_export` | 4036 | status=completed path=outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购招标文件.docx |

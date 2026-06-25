# run_20260624_p1c14_local_three_question_stream — P1C-14 本地真实三问复测

- 生成时间：2026-06-24T08:23:27.740900+00:00
- 测试环境：`http://127.0.0.1:3012`
- 测试方式：真实登录 + 真实 `/api/knowledge/search/stream`
- 总体状态：**PASS**

| 问题 | 状态 | 关键检查 | 产物 |
| --- | --- | --- | --- |
| 泰昌有哪些资质证书？ | PASS | ok=5; bad=error, has_internal_path, has_english_enum, mentions_liaoning_or_haoqian_as_fact | `docs/rag/runs/run_20260624_p1c14_local_three_question_stream_qualification.jsonl` |
| 泰昌 CPVC 电缆保护管有哪些检验报告？ | PASS | ok=5; bad=error, has_internal_path, has_english_enum, mentions_liaoning_or_haoqian_as_fact | `docs/rag/runs/run_20260624_p1c14_local_three_question_stream_cpvc_report.jsonl` |
| 泰昌有哪些企业证明材料？ | PASS | ok=6; bad=error, has_internal_path, has_english_enum, mentions_liaoning_or_haoqian_as_fact | `docs/rag/runs/run_20260624_p1c14_local_three_question_stream_enterprise_evidence.jsonl` |

## 来源摘要

### 泰昌有哪些资质证书？
- 状态：PASS
- 来源：-
- 图片/资产：泰昌1.质量管理体系认证证书第1页；泰昌1.质量管理体系认证证书第3页；泰昌1.质量管理体系认证证书第2页；质量管理体系认证证书；泰昌3.职业健康安全管理体系认证证书第1页

### 泰昌 CPVC 电缆保护管有哪些检验报告？
- 状态：PASS
- 来源：-
- 图片/资产：泰昌CPVC电缆保护管检验报告内径250_页面_4原图；泰昌CPVC电缆保护管检验报告内径250_页面_3原图；泰昌CPVC电缆保护管检验报告内径250_页面_2原图；泰昌CPVC电缆保护管检验报告内径250第4页；CPVC电缆保护管检验报告内径250

### 泰昌有哪些企业证明材料？
- 状态：PASS
- 来源：-
- 图片/资产：职业健康安全管理体系认证证书；环境管理体系认证证书；泰昌营业执照副本原图；质量管理体系认证证书；泰昌社保证明（第1页）

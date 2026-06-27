# run_20260626_taichang_enterprise_source_scope_final — 企业资料来源误解读专项收敛

- 生成时间：2026-06-26
- 门禁状态：PASS
- 适用范围：泰昌企业资信、绿色低碳、人员社保、检验报告、生产制造能力等知识库问答来源边界。

## 触发原因

阿里云 `f97b31a` 发布后，线上复查发现“泰昌有哪些资质证书？”仍可能受误标 `certification` 的 ESG、绿色发展、废水废气废固等资料污染。本轮按同类问题举一反三，检查本地真实库中是否存在其他资料被误解读或展示分类被覆盖。

## 数据审计与修复

- 只读审计发现：本地 `knowledge_assets` 中 221 条绿色/低碳相关资产，包含 ESG、绿色供应链、绿色发展规划、碳足迹、废水废气废固；其中 19 条绿色发展类资产曾被标为 `certification`，17 条碳足迹报告曾落在 `qualification_library`。
- `document_chunks` 中 1205 条绿色/低碳相关 chunk 已统一修正为 `evidence_type=green_low_carbon`。
- 执行脚本：`scripts/rag/repair_taichang_green_asset_metadata.py --execute`。
- 修复报告：
  - `docs/rag/runs/run_20260626_taichang_green_metadata_repair_dry_run.json`
  - `docs/rag/runs/run_20260626_taichang_green_metadata_repair_execute.json`
  - `docs/rag/runs/run_20260626_taichang_green_metadata_repair_execute_second_pass.json`
- 修复后校验：绿色/ESG/碳足迹/废水资料中 `certification_with_green_terms=0`，绿色低碳资料均保留为 `green_low_carbon`。

## 代码修复

- 企业知识库查询新增集中式证据类型收敛：资质证书、绿色低碳、人员社保、检验报告、生产制造能力、试验检测设备、营业执照。
- 同一收敛规则应用于文本上下文和图片资产，避免参考来源干净但答案正文仍被资产污染。
- 展示层 `sanitize_source_metadata` 不再用泛化“泰昌企业资料”覆盖具体分类；当 `category_label` 泛化且存在 `evidence_type` 时，显示具体证据类型。

## 真实 API 6 问审计

最终审计产物：`docs/rag/runs/run_20260626_taichang_enterprise_source_audit_final_summary.json`。

| 问题 | 结果 | 来源边界 |
| --- | --- | --- |
| 泰昌有哪些资质证书？ | PASS | 仅质量、环境、职业健康安全管理体系认证证书 |
| 泰昌有哪些企业证明材料？ | PASS | 三体系证书、营业执照、社保证明 |
| 泰昌有哪些绿色低碳资料？ | PASS | ESG、绿色供应链、碳足迹、绿色发展规划，均为绿色低碳资料 |
| 泰昌有哪些人员证书或社保证明？ | PASS | 仅人员证书、人员花名册、社保证明 |
| 泰昌 CPVC 电缆保护管有哪些检验报告？ | PASS | 仅 CPVC 内径250结构化参数和检验报告原始页 |
| 泰昌有哪些生产制造能力资料？ | PASS | 仅厂房、生产线、生产制造能力资料 |

所有非绿色低碳问题 `bad_terms=[]`，未混入 ESG、绿色发展、碳足迹、废水废气废固或绿色供应链资料。

## 标准门禁

自动门禁：`docs/rag/runs/run_20260626_taichang_enterprise_source_scope_final_summary.md`

| 步骤 | 状态 |
| --- | --- |
| api_ready | PASS |
| rag_unit_tests | PASS |
| incremental_regression_gate | PASS |
| stream_sample | PASS |

增量门禁：`docs/rag/runs/run_20260626_taichang_enterprise_source_scope_final_incremental_summary.md`

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% |

## 结论

本地真实服务已完成企业资料来源误解读专项收敛。未新增资料、未删除资料、未重建 embedding；仅修正绿色低碳资料 metadata、查询后处理证据类型收敛和展示分类清洗。下一步需提交并发布到阿里云，执行同一 metadata 修复脚本和线上 6 问复测。

# 2026-06-27 P0 新招标项目资料域隔离门禁摘要

## 结论

新疆 10kV 架空绝缘导线项目与泰昌现有 CPVC/MPP 电缆保护管企业事实不适配时，系统已形成预填、章节写作和正式检查三层门禁：

- 预填候选不再把辽宁 2025 2225AC CPVC/MPP 货物清单、技术参数和泰昌检验报告参数回填到新疆导线包。
- 技术章节 prompt 不再加载 CPVC/MPP 产品事实、企业资产候选和章节级 RAG 写作依据，只输出产品适配性风险与资料补充占位。
- 正式检查新增 `T-000` 阻断规则，产品不适配时不得作为正式投标文件导出。

## 验证

- 定向测试：`PYTHONPATH=. .venv/bin/pytest tests/test_bid_prefill.py tests/test_formal_bid_check.py tests/test_docx_export.py -q`
- 结果：`64 passed, 1 warning`
- 真实链路：`build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`
- 真实链路结果：短文件名 `泰昌_SL265A_包1_技术投标文件_20260627.docx` 生成成功，LibreOffice 字段刷新 `refreshed`，产品适配性 prompt 阻断生效。

详细记录见 `docs/development/runs/run_20260627_p0_product_compatibility_and_short_docx_names.md`。

## 未执行项说明

本轮没有新增客户资料入库、重建 embedding、调整 RAG RPC 或知识库索引；变更集中在投标预填、章节写作 prompt 和正式检查门禁。因此未执行 Base + 泰昌专项全量召回门禁。

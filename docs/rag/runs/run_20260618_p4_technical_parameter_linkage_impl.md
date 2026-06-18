# Run 20260618-P4-9 — 技术参数表联动章节占位与偏差表候选

- 时间：2026-06-18
- 范围：前导确认页 / 章节占位候选，不生成正文，不处理 DOCX/PDF 字体或乱码。
- 目标：把辽宁技术参数表、技术偏差辅助表和泰昌结构化检验报告参数做成可确认候选，服务后续技术响应、技术特性参数表和技术偏差表。

## 实现内容

- `backend/services/bid_prefill.py` 新增 3 个候选字段：
  - `technical_parameter_summary`：技术参数表候选摘要。
  - `technical_deviation_candidates`：技术偏差表候选。
  - `taichang_parameter_match_summary`：泰昌参数佐证摘要。
- 接入结构化文件：
  - `staging/technical_parameters/technical_parameter_rows.json`
  - `staging/technical_parameters/technical_deviations/technical_deviation_rows.json`
  - `staging/taichang_product_parameters/taichang_product_parameter_rows.json`
  - `goods_tables/goods_rows.json`
- 过滤策略沿用项目编号、包号、CPVC/MPP 物料上下文。
- 泰昌参数覆盖判断优先对比货物清单实际规格，避免把通用技术规范中的非本包规格误写为本次供货需求。
- 辽宁技术参数和偏差候选标记为 `sourceDomain=tender_requirement`、`factSourceAllowedForEnterprise=false`。
- 泰昌检验报告参数标记为 `sourceDomain=enterprise_fact`、`factSourceAllowedForEnterprise=true`，但边界提示明确：辽宁需求仅作 QA/异常校验，不构成覆盖辽宁全部规格结论。
- 确认应用链路未改变：只有客户确认后的值才会替换正文占位符，不自动生成正文，不自动写“无偏差”。

## 真实项目抽样

项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`

| 字段 | 状态 | 结果摘要 |
| --- | --- | --- |
| 技术参数表候选摘要 | 待人工确认 | 包1 共 300 行，CPVC/MPP，公称内径 50/70/90/100/125/150/175/200/225/250，待补投标响应/保证值 300 行 |
| 技术偏差表候选 | 待人工确认 | 包1 共 300 行，`pending_response` 284 行、`informational` 16 行；不自动写入无偏差 |
| 泰昌参数佐证摘要 | 待人工确认 | 泰昌结构化检验报告 36 行、报告 2 份；现有报告为内径 250；辽宁货物清单规格 50/100/150/200 未由现有泰昌结构化报告直接覆盖 |

## 验证命令

```bash
.venv/bin/python -m py_compile backend/services/bid_prefill.py
.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_taichang_product_parameter_query.py tests/test_technical_deviation_report.py -q
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_local_rag_gate.py --run-id run_20260618_p4_technical_parameter_linkage
```

## 验证结果

| 项 | 结果 |
| --- | --- |
| py_compile | PASS |
| 定向 pytest | 18 passed |
| 真实项目前导页抽样 | PASS |
| RAG 本地门禁 | PASS |
| api_ready | PASS |
| RAG 单测 | PASS |
| 增量回归门禁 | PASS |
| 真实 stream 抽样 | PASS，contexts=5，assets=8，images=8 |

增量回归指标见：

- `docs/rag/runs/run_20260618_p4_technical_parameter_linkage_summary.md`
- `docs/rag/runs/run_20260618_p4_technical_parameter_linkage_incremental_summary.md`

## 结论

- P4-9 完成。
- 技术参数表、偏差表和泰昌检验报告参数已进入前导页/章节占位候选层。
- 辽宁招标要求与泰昌企业事实边界保持隔离。
- 本次没有生成正文，也没有处理 DOCX/PDF 导出问题。

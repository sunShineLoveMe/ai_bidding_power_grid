# Run 20260617-P4-8 — 货物清单结构化联动前导页候选

- 时间：2026-06-17
- 范围：前导确认页候选字段，不生成正文，不处理 DOCX/PDF 导出格式。
- 目标：让包号、包名称、物料类别、货物清单摘要优先读取结构化货物清单行级记录，而不是只依赖正文正则。

## 实现内容

- `backend/services/bid_prefill.py` 接入 `goods_tables/goods_rows.json`。
- 按项目编号、包号、CPVC/MPP 物料关键词过滤结构化货物清单。
- 为以下字段生成待确认候选：
  - `package_no`
  - `package_name`
  - `material_category`
  - `goods_list_summary`
- 证据标记为 `sourceType=structured_tender_goods_rows`、`sourceDomain=tender_requirement`、`factSourceAllowedForEnterprise=false`，避免把辽宁招标清单误当泰昌企业事实。
- 确认应用链路未改变：只有用户确认后的值才会进入占位符替换，不自动生成或覆盖正文。

## 真实项目抽样

项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`

| 字段 | 状态 | 候选来源 | 结果摘要 |
| --- | --- | --- | --- |
| 包号 | 待人工确认 | 结构化货物清单 | `包1` |
| 包名称 | 待人工确认 | 结构化货物清单 | `电缆保护管CPVC、电缆保护管MPP（需按目标包确认）` |
| 物料类别 | 系统已识别 | 结构化货物清单 | `电缆保护管CPVC、电缆保护管MPP` |
| 货物清单摘要 | 待人工确认 | 结构化货物清单 | 共 38 行需求，包1 合计 102583 米，技术规范编码 10 个 |
| 产品规格型号 | 企业库带出 | 泰昌核验事实包 | CPVC/MPP 泰昌检验报告规格，未被辽宁清单覆盖 |

## 验证命令

```bash
.venv/bin/python -m py_compile backend/services/bid_prefill.py
.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_chapter_planner.py -q
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_local_rag_gate.py --run-id run_20260617_p4_structured_prefill_linkage
```

## 验证结果

| 项 | 结果 |
| --- | --- |
| py_compile | PASS |
| 定向 pytest | 17 passed |
| RAG 本地门禁 | PASS |
| api_ready | PASS |
| RAG 单测 | PASS |
| 增量回归门禁 | PASS |
| 真实 stream 抽样 | PASS，contexts=5，assets=8，images=8 |

增量回归指标见：

- `docs/rag/runs/run_20260617_p4_structured_prefill_linkage_summary.md`
- `docs/rag/runs/run_20260617_p4_structured_prefill_linkage_incremental_summary.md`

## 结论

- P4-8 完成。
- 前导页不再只能靠文本正则猜货物清单，已能读取结构化行级记录并给出可追溯候选。
- 辽宁招标要求与泰昌企业事实边界保持隔离。
- 本次不涉及正文生成、章节内容改写、DOCX/PDF 字体或乱码修复。

# Run 12 — 国网规则网页噪声重洗与回归

> 运行时间：2026-06-07
> Base filtered：`docs/rag/runs/run_20260607_sgcc_rule_clean_base_filtered.json`
> 泰昌专项 filtered：`docs/rag/runs/run_20260607_sgcc_rule_clean_customer_filtered.json`

## 背景

Run 11 后确认 `国家电网有限公司招标活动管理办法`、`国家电网有限公司供应商管理办法`、`国家电网有限公司物资采购标准` 三份种子资料的正文并非制度原文，而是中国政府网首页导航、新闻和政务入口内容。这类网页噪声会影响国网规则问答、合规召回和后续 P4 技术参数表抽取前的整体回归稳定性。

## 处理内容

- 新增 `scripts/rag/repair_sgcc_rule_seed_docs.py`，用于重洗三份异常种子资料并同步 `index.csv`、`index.jsonl` 的 `sha256` 和错误说明。
- 将三份异常 markdown 改为明确标注的“检索种子摘要”：
  - `02_policy_regulations/25_国家电网有限公司招标活动管理办法_f91d60bd.md`
  - `02_policy_regulations/26_国家电网有限公司供应商管理办法_fa9308a9.md`
  - `02_policy_regulations/27_国家电网有限公司物资采购标准_011cf2f8.md`
- 每份资料均明确：
  - 原始采集链接失效，误采为门户首页；
  - 当前不是官方制度全文；
  - `citation_policy=summary_only`，仅用于召回定位和摘要问答；
  - 后续拿到官方制度原文后必须替换并复跑入库评测。
- `search_knowledge_base()` 补充 `质量安全环保/质量目标/安全目标` 领域关键词，并将关键词补召回从固定 50000 条窗口改为分页扫描，避免小类资料在回归中被漏扫。

## 入库记录

- `./.venv/bin/python scripts/rag/repair_sgcc_rule_seed_docs.py`
- `./.venv/bin/python scripts/rag/ingest_power_grid_v2.py --dry-run --category 02_policy_regulations`
  - 11 文档，266 parent，2180 child。
- `./.venv/bin/python scripts/rag/ingest_power_grid_v2.py --category 02_policy_regulations`
  - 11 文档重新 indexed，三份国网规则旧 chunk 已按同一 `object_path` 删除后重建。
- `./.venv/bin/python scripts/rag/ingest_power_grid_v2.py --category 04_standard_phrases`
  - 6 文档，16 parent，22 child；用于恢复本次回归暴露的标准话术库不完整问题。

## 回归验证

- `./.venv/bin/python -m pytest tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
  - 26 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile backend/rag/retrieval.py scripts/rag/eval_recall.py scripts/rag/repair_sgcc_rule_seed_docs.py`
  - 通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

## 未命中与风险

- Base 仅剩 T04：top1 `policy_regulation` 正确，但测试关键词要求“无效”，当前命中内容为“否决所有投标”，属于既有评测关键词口径问题。
- 三份国网规则当前仍是检索种子摘要，不是官方制度全文。客户或公开渠道补到正式原文后，应替换 seed 文件、更新 hash、重新入库并复跑 Base + 泰昌专项评测。

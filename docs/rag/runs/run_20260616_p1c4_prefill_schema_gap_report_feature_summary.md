# Run 20260616 P1C-4 前导确认页变量 schema v1 与预填缺口报告

## 目标

在不影响章节正文编辑和 `sectionsSnapshot` DOCX 导出契约的前提下，完成投标前导确认页的第一版真实可用能力：

- 变量 schema v1；
- 预填字段来源规则；
- 客户确认缺口报告；
- 前端旁路只读确认页面。

## 实现范围

| 模块 | 变更 |
| --- | --- |
| 后端服务 | 新增 `backend/services/bid_prefill.py`，定义 32 个投标关键字段，按项目信息、包件/货物清单、投标主体、商务报价、保证金、投标承诺、授权签章、企业资信、检测报告、项目业绩、企业产品分组 |
| 后端接口 | 新增 `GET /api/bidding/projects/<project_id>/prefill-report`，实时读取项目解读、招标文本、知识资产生成只读报告 |
| 前端页面 | 新增 `/prefill` 投标信息确认页，默认读取最新项目，也支持 `?projectId=<id>` 指定项目 |
| 主导航 | 新增“投标确认”入口；招标项目页新增“投标信息确认”跳转 |
| 测试 | 新增 `tests/test_bid_prefill.py`，覆盖客户决策字段不得自动补全、企业资产只作为候选来源 |

## 字段状态口径

| 状态 | 含义 |
| --- | --- |
| 系统已识别 | 来自招标文件解析、项目结构化字段或规则识别 |
| 企业库带出 | 来自企业知识库、企业资信库、企业产品库资产候选 |
| 客户需填写 | 报价、保证金、授权签章等客户决策字段，禁止 AI 自动补 |
| 待人工确认 | 包号、货物清单、交货期、质保期等正式投标关键字段，需要人工确认候选值 |

## 真实接口回归

| 项 | 结果 |
| --- | --- |
| 服务健康 | `GET /api/ready` PASS，database、Redis、Celery、model_config、storage 均正常 |
| 真实项目 | `4bc3ee73-9ec5-4184-aafd-eaede9f90798` |
| 新接口 | `GET /api/bidding/projects/4bc3ee73-9ec5-4184-aafd-eaede9f90798/prefill-report` PASS |
| schemaVersion | `2026-06-16.v1` |
| 字段数 | 32 |
| 客户需填写 | 10 |
| 待人工确认 | 10 |
| 正式必填缺口 | 15 |
| 旁路只读 | `readonlyFirst=true` |
| 导出契约 | `affectsSectionsSnapshotExport=false` |

## 前端真实页面回归

| 项 | 结果 |
| --- | --- |
| 构建 | `npm run build` PASS |
| 页面 | `http://127.0.0.1:3012/prefill` |
| 登录态 | 使用本地真实账号登录后访问 |
| 页面检查 | 标题、只读说明、变量 schema v1、客户确认缺口报告、客户需填写、`sectionsSnapshot DOCX 导出契约` 文案均存在 |
| 截图 | `docs/development/runs/run_20260616_p1c4_prefill_page.png` |

## 自动化测试

```bash
.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_local_rag_gate.py
npm run build
set -a; source .env; set +a; .venv/bin/python scripts/rag/run_local_rag_gate.py --run-id run_20260616_p1c4_prefill_schema_gap_report
```

结果：

- `tests/test_bid_prefill.py tests/test_local_rag_gate.py`：4 passed；
- 前端构建：PASS；
- 本地 RAG 门禁：PASS。

## 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 279 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 614 ms |
| 泰昌专项 | off | 93.3% | 100.0% | 0.933 | 3.3% | 0.0% | 328 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 692 ms |

详见：

- `docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_summary.md`
- `docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_incremental_summary.md`
- `docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_stream.jsonl`

## 结论

- P1C-4 完成第一版真实可用闭环。
- 当前版本是旁路只读确认页，不替代章节正文编辑，不写入 `bid_sections`，不影响 `sectionsSnapshot` DOCX 导出契约。
- 后续任务可进入“变量确认后显式回填引擎”，但必须继续保持用户确认优先，报价、保证金、授权签章等客户决策字段不得自动补全。

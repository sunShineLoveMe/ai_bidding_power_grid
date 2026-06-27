# Run 20260618 P4-11 章节候选确认值批量应用与导出前门禁

- 时间：2026-06-18
- 范围：P4-11 章节候选确认值批量应用与导出前门禁
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 结论：PASS

## 背景

P4-10 已把 P4-8/P4-9 的结构化候选按章节归类展示。本轮继续收口确认闭环：客户可以按章节采纳候选到确认草稿，页面持续显示导出前门禁；后端应用确认值后返回章节级应用摘要和正式导出 gate，便于审计。

本轮仍不生成正文，不处理 PDF 字体或乱码问题。

## 改动内容

### 后端

- `backend/services/bid_prefill.py`
  - `apply_bid_prefill_confirmation()` 在应用明确占位符前构建章节候选摘要。
  - 应用结果新增：
    - `section_application_summary`
    - `export_gate`
  - `export_gate` 包含：
    - `ready`
    - `sectionCount`
    - `confirmedSectionCount`
    - `unresolvedPlaceholderCount`
    - `unresolvedPlaceholders`
    - `missingFormalRequiredFields`
  - 正式可导出判断继续以“存在真实章节、无未解析占位符、无正式必填缺口”为准。
  - 保持原有安全边界：只替换明确占位符，不覆盖普通正文，不把辽宁招标要求变成泰昌企业事实。

### 前端

- `frontend/src/pages/BidPrefill/index.tsx`
  - 新增“导出前门禁”面板。
  - 根据当前客户确认草稿动态展示：
    - 是否仍需收口；
    - 正式必填缺口数量；
    - 正文未解析占位符数量；
    - 最多 8 个优先缺口入口。
  - 每个章节候选卡新增“采纳本章候选”按钮，只把该章节候选字段写入本地确认草稿，不提交后端。
  - 点击缺口或章节字段可跳转到下方对应确认字段。
- `frontend/src/api/bidProject.ts`
  - 补充 `BidPrefillApplication` 的 `export_gate`、`section_application_summary`、`unresolved_placeholders` 类型。
- `frontend/src/index.css`
  - 新增门禁面板、缺口列表和通过状态样式。

### 测试

- `tests/test_bid_prefill.py`
  - 应用确认值后必须返回 `export_gate` 与 `section_application_summary`。
  - 正式必填字段不完整时 `ready_for_formal_export=false`。
  - 正式必填字段完整且无占位符时 `ready_for_formal_export=true`。

## 真实项目验证

后端真实报告：

| 指标 | 值 |
| --- | ---: |
| sectionCandidates | 22 |
| 当前草稿正式必填缺口 | 10 |
| summary.readyForFormalExport | false |
| unresolvedPlaceholderCount | 39 |

结论：真实项目当前仍不能作为正式导出状态，原因是存在客户决策字段缺口和正文明确占位符。

## 浏览器验证

验证命令：

```bash
cd frontend
VITE_API_PROXY_TARGET=http://127.0.0.1:3012 npm run dev -- --host 127.0.0.1 --port 5174
```

真实页面：

```text
http://127.0.0.1:5174/prefill?projectId=a1d853bc-ca4e-43b4-bbea-256f561c8a3d
```

验证结果：

- 页面显示“导出前门禁”。
- 页面显示“仍需收口”。
- 页面显示“正文占位 39”。
- 页面存在 22 个“采纳本章候选”按钮。
- 点击首个“采纳本章候选”后仅更新本地草稿，没有提交正式应用。
- 页面最多展示 8 个优先缺口入口。
- 控制台仅有既有 Ant Design `Drawer bodyStyle` 弃用提示，无 P4-11 新增功能错误。
- 截图：`output/playwright/run_20260618_p4_11_prefill_gate.png`

## 回归结果

| 命令 | 结果 |
| --- | --- |
| `set -a; source .env; set +a; .venv/bin/python -m py_compile backend/services/bid_prefill.py` | PASS |
| `set -a; source .env; set +a; .venv/bin/python -m pytest tests/test_bid_prefill.py -q` | PASS，9 passed |
| `cd frontend && npm run build` | PASS |
| `set -a; source .env; set +a; .venv/bin/python scripts/rag/run_local_rag_gate.py --run-id run_20260618_p4_11_prefill_gate_apply` | PASS |

RAG 本地门禁：

| 步骤 | 状态 | 结果 |
| --- | --- | --- |
| api_ready | PASS | HTTP 200，status=ok |
| rag_unit_tests | PASS | exit_code=0 |
| incremental_regression_gate | PASS | exit_code=0 |
| stream_sample | PASS | done=True，contexts=5，assets=8，images=8 |

增量召回指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 93.3% | 100.0% | 0.933 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% |

门禁结论：PASS。以 qwen3-rerank 为泰昌专项正式门禁口径，Recall@5、Top1 来源准确率、禁用关键词命中率和跨域串扰均达标。

## 边界

- “采纳本章候选”只写入页面本地草稿，不自动提交。
- “确认、应用并进入正文编辑”仍只替换明确占位符。
- 辽宁招标要求仍是 `tender_requirement`，不得作为泰昌企业事实。
- 技术偏差表候选仍需客户确认，不自动生成“无偏差”结论。

## 后续建议

下一步可进入 DOCX/PDF 导出观感修复，优先处理客户已指出的字体、格式和乱码问题；P4 结构化候选确认闭环本轮已可支撑后续正式导出前检查。

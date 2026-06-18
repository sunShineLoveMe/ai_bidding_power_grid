# Run 20260618 P4-10 章节级候选展示与缺口清单 UI 收口

- 时间：2026-06-18
- 范围：P4-10 章节级候选展示与缺口清单 UI 收口
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 结论：PASS

## 背景

P4-8 已把结构化货物清单接入前导确认页候选，P4-9 已把技术参数表、技术偏差表和泰昌检验报告参数佐证接入候选层。本轮不生成正文、不处理 PDF 字体/乱码问题，只解决客户确认前的可见性问题：把这些候选按标书章节归类展示，并暴露每章缺口、来源边界和人工确认风险。

## 改动内容

### 后端

- `backend/services/bid_prefill.py`
  - `build_bid_prefill_report()` 新增 `sectionCandidates`。
  - 根据真实 `bid_sections` 匹配章节；缺少章节时使用虚拟章节兜底。
  - 将字段按章节聚合，输出：
    - `fieldCount`
    - `gapCount`
    - `statusCounts`
    - `sourceDomains`
    - `boundaryWarnings`
    - 章节内字段预览
  - P4 重点字段映射：
    - `goods_list_summary` -> 报价文件及货物清单 / 货物清单 / 技术响应
    - `technical_parameter_summary` -> 技术特性参数表 / 技术响应文件 / 技术响应
    - `technical_deviation_candidates` -> 技术偏差表 / 技术响应文件 / 技术响应
    - `taichang_parameter_match_summary` -> 产品制造与质量控制 / 技术响应文件 / 检验报告 / 技术响应
  - 保留来源边界提示：辽宁招标参数是 `tender_requirement`，不得作为泰昌企业事实；偏差表候选不自动生成“无偏差”结论。

### 前端

- `frontend/src/api/bidProject.ts`
  - 增加 `BidPrefillSectionCandidate` 类型。
  - 前导页报告类型增加 `sectionCandidates`。
  - 字段证据增加 `sourceDomain` 和 `factSourceAllowedForEnterprise`。
- `frontend/src/pages/BidPrefill/index.tsx`
  - 新增“章节候选与缺口清单”区域。
  - 按章节展示候选字段、缺口数量、状态统计、来源域和边界告警。
  - 点击章节候选字段可跳转到下方对应字段卡片，便于客户逐项确认。
- `frontend/src/index.css`
  - 增加章节候选卡片、告警、字段按钮和窄屏布局样式。

### 测试

- `tests/test_bid_prefill.py`
  - 补充结构化技术参数、偏差表、泰昌参数佐证按章节归类的断言。
  - 验证 `技术特性参数表`、`技术偏差表`、`产品制造与质量控制` 都能拿到对应候选字段。
  - 验证招标要求来源和边界告警存在。

## 真实项目验证

后端真实项目报告输出：

| 指标 | 值 |
| --- | ---: |
| sectionCandidates | 22 |
| 技术响应文件 | 候选 10，缺口 6 |
| 技术偏差表 | 候选 2，缺口 2 |
| 技术特性参数表 | 候选 2，缺口 1 |
| 产品制造与质量控制 | 候选 3，缺口 1 |

关键候选已按章节出现：

- `技术参数表候选摘要` 出现在 `技术特性参数表` 和 `技术响应文件`。
- `技术偏差表候选` 出现在 `技术偏差表` 和 `技术响应文件`。
- `货物清单摘要` 出现在 `报价文件及货物清单`、`货物清单` 和 `技术响应文件`。
- `泰昌参数佐证摘要` 出现在 `产品制造与质量控制` 和 `技术响应文件`。

## 浏览器验证

验证方式：

```bash
cd frontend
VITE_API_PROXY_TARGET=http://127.0.0.1:3012 npm run dev -- --host 127.0.0.1 --port 5174
```

使用真实浏览器访问：

```text
http://127.0.0.1:5174/prefill?projectId=a1d853bc-ca4e-43b4-bbea-256f561c8a3d
```

验证结果：

- 页面显示“章节候选与缺口清单”。
- 页面显示 `章节 22`、`缺口 25`。
- 页面文本包含 `技术特性参数表`、`技术偏差表`、`报价文件及货物清单`、`产品制造与质量控制`。
- 控制台仅有 Ant Design `Drawer bodyStyle` 既有弃用警告，未出现本次功能错误。
- 截图：`docs/rag/runs/artifacts/run_20260618_p4_section_candidate_ui.png`

## 回归结果

| 命令 | 结果 |
| --- | --- |
| `set -a; source .env; set +a; .venv/bin/python -m py_compile backend/services/bid_prefill.py` | PASS |
| `set -a; source .env; set +a; .venv/bin/python -m pytest tests/test_bid_prefill.py -q` | PASS，8 passed |
| `cd frontend && npm run build` | PASS |
| `set -a; source .env; set +a; .venv/bin/python scripts/rag/run_local_rag_gate.py --run-id run_20260618_p4_section_candidate_ui` | PASS |

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
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% |

## 边界

- 本轮没有生成或改写正文。
- 本轮没有处理 PDF 导出、字体或乱码问题。
- 章节候选只做确认前展示，不自动把辽宁招标要求写成泰昌企业事实。
- 偏差表候选只提示待确认状态，不自动得出“无偏差”结论。

## 后续建议

下一步可进入 P4-11：章节候选的客户确认值批量应用与导出前门禁。目标是把客户在 P4-10 页面确认过的章节候选安全应用到明确占位符，并在导出前列出仍未确认的关键缺口。

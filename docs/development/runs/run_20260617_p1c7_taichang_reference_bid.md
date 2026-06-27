# run_20260617_p1c7_taichang_reference_bid — 泰昌参考模板标书成品度收口

- 日期：2026-06-17
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 项目名称：国网辽宁电力2025年第三次物资协议库存招标采购
- 投标主体：河北泰昌电力器材科技有限公司

## 背景

用户反馈当前生成的标书观感接近半成品，既不像标准投标文件，也没有贴近客户提供的河北豪乾参考标书结构。按项目边界，本轮只允许参考河北豪乾的目录、表式和写法，不得引用其企业事实；企业事实必须来自泰昌资料，辽宁资料只作为招标要求样本。

## 修复内容

- 前导确认页新增“确认并应用”后端链路：确认值持久化到 `project_meta.bid_prefill`，只替换正文中的显式占位符，不覆盖用户普通正文。
- 大纲规划器识别纯物资供货投标场景，改用 23 节的供货/商务/技术/报价/附件结构，避免生成施工组织设计、水利施工、BIM、建造师等不适用章节。
- 章节写作注入泰昌核验事实包，包含统一社会信用代码、法定代表人、CPVC/MPP 检验报告参数和真实项目业绩；河北豪乾只作为格式参考。
- 章节终审新增正式占位归并：重复的 `【待补充】` 不再铺满表格，合并为少量客户确认项；保存章节前也会执行同一归并。
- DOCX 导出新增正式 readiness metadata：记录模板、参考策略、空章节数、占位数和正式必填缺口；导出完成后前端优先提示未达正式标准的原因。
- 导出层不再把容器章节写成 `待补充章节正文。`，空章节统计排除容器节点，避免分册标题看起来像未写正文。
- 前导缺口报告接入泰昌核验事实包，统一社会信用代码、法定代表人、注册地址、产品型号、检验报告和资信附件不再误报为客户缺口。

## 真实项目处理

首轮用旧 worker 生成 19 个叶子章节后，审计发现占位 `916` 处，且 `施工组织` 命中 8 次、`安全生产许可证` 命中 2 次，判定不可交付。

修复后对真实项目重新生成并清理：

| 指标 | 结果 |
| --- | ---: |
| 章节节点 | 23 |
| 叶子章节 | 19 |
| 容器章节 | 4 |
| 有正文叶子章节 | 19 |
| 空叶子章节 | 0 |
| 正文占位 | 39 |
| 施工/水利/BIM/建造师/河北豪乾污染 | 0 |
| 泰昌提及 | 159 |

占位从 `916` 降至 `39`。剩余占位集中在招标人、包号/包名称、货物清单、报价税率、投标保证金、交货期、质保期、授权代表和签署日期等必须由招标文件或客户确认的字段，系统不得编造。

## 正式导出验收

真实链路：

```bash
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice -> LibreOffice PDF
```

产物：

- Markdown：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.md`
- DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`
- PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.pdf`
- JSON：`docs/development/runs/run_20260617_p1c7_taichang_reference_bid.json`

| 检查项 | 结果 |
| --- | --- |
| 模板 | `sgcc_taichang_bid` |
| 参考策略 | 招标格式 > 客户参考模板 > 系统默认 |
| 空叶子章节 | 0 |
| readiness 占位 | 39 |
| 正式必填缺口 | 15 |
| readiness | `false` |
| DOCX 段落 | 1799 |
| DOCX 标题 | 23 |
| DOCX 表格 | 36 |
| 图片 | selected 24，inserted 24，failed 0 |
| 目录标题 | PASS |
| 页眉泰昌投标文件 | PASS |
| `PAGE/NUMPAGES/PAGEREF` 字段 | PASS |
| LibreOffice 字段刷新 | `refreshed` |
| PDF 预览 | `generated` |
| 禁用主题 | 0 |

本轮产物已经从“空章节/施工模板污染/大量重复占位”的半成品状态，收敛为可评审的泰昌物资投标文件草稿。但 readiness 保持 `false`，因为正式投标前仍需补齐 15 个客户/招标文件确认字段。

## 回归

```bash
.venv/bin/python -m py_compile \
  backend/services/taichang_bid_context.py \
  backend/services/bid_prefill.py \
  backend/ai/section_writer.py \
  backend/services/section_generation.py

.venv/bin/python -m pytest \
  tests/test_bid_prefill.py \
  tests/test_section_writer_formal_quality.py \
  tests/test_chapter_planner.py \
  tests/test_length_settings.py \
  tests/test_section_generation_autoresume.py \
  tests/test_docx_export.py -q

cd frontend && npm run build

set -a; source .env; set +a
.venv/bin/python scripts/rag/run_local_rag_gate.py \
  --run-id run_20260617_p1c7_taichang_reference_bid
```

结果：

- 后端定向回归：`67 passed, 1 warning`
- 前端 build：PASS；仅保留既有 chunk size / dynamic import 警告
- RAG 本地门禁：PASS
- 增量回归：Base 30 + 泰昌专项 30 PASS
- 真实 stream：`done=true`，contexts=5，assets=8，images=8

增量回归核心指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 282 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 604 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 344 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 684 ms |

## 后续状态

P1C-7 可关闭为“工程链路和真实项目草稿收口完成”。下一步不是继续让模型猜字段，而是让客户/招标文件补齐正式必填字段，然后重新应用前导确认并导出 readiness 为 `true` 的最终版。

# 泰昌历史标书复用 P1-04 章节—事实—证据映射总结

> 日期：2026-07-14
> 企业：河北泰昌电力器材科技有限公司
> 范围：离线动态语义章节映射，不写数据库、不改 metadata、不复制资产

## 结果

P1-04 已完成。系统不再按历史标书固定章节号寻找资料，而是为当次 `project_bid_skeleton.json` 提供语义章节键和标题别名，并把命中章节定位到泰昌核验事实、结构化参数、业务台账、文件级证据包或知识资产 ID。

| 指标 | 结果 |
| --- | ---: |
| 技术标语义映射 | 12 |
| 商务标语义映射 | 7 |
| 已有资料 | 5 |
| 部分可用 | 10 |
| 缺原件 | 3 |
| 人工确认 | 1 |
| 唯一证据包引用 | 15 |
| 原始检验报告参数 | 36 行 |
| P1-03 安全台账投影 | 17 行 |
| 人员受限明细纳入 | 0 |
| 数据库写入 / 资产复制 | 0 / 0 |

## 关键边界

- CPVC、MPP 技术参数可定位结构化参数和对应完整检验报告证据包。
- N-HAP、UPVC 只有历史报告编号且缺原始报告，保持 `missing_evidence`，不得生成正式参数或覆盖结论。
- 设备、管理体系和审计材料按投标日、当前招标年度复核；过期职业健康安全证书未进入映射引用。
- 资格预审无独立原件；评审补充材料必须先解析当前评分项；授权委托和签章只生成模板占位与人工确认清单。
- P1-01 历史 Word 资产继续保持 `knowledge_only`，不能因映射被提升为正式附件或 DOCX 配图。
- 辽宁招标资料只确定本项目要求；河北豪乾只参考结构和写法；二者都不能生成泰昌企业事实。

## 交付物

- `scripts/rag/build_taichang_chapter_evidence_mapping.py`
- `docs/development/taichang-bid-v1-data/p1_04_chapter_evidence_mapping/taichang_bid_evidence_mapping.json`
- `docs/development/taichang-bid-v1-data/p1_04_chapter_evidence_mapping/泰昌资料—技术标章节映射表.md/csv`
- `docs/development/taichang-bid-v1-data/p1_04_chapter_evidence_mapping/泰昌资料—商务标章节映射表.md/csv`
- `tests/test_taichang_chapter_evidence_mapping.py`

## 验证

```bash
.venv/bin/python scripts/rag/build_taichang_chapter_evidence_mapping.py
.venv/bin/python -m pytest -q \
  tests/test_taichang_chapter_evidence_mapping.py \
  tests/test_taichang_evidence_bundles.py \
  tests/test_taichang_business_ledgers.py
.venv/bin/python -m pytest -q tests
```

- 专项：29 passed，1 个既有 PyPDF2 弃用告警。
- 后端全量：432 passed、2 subtests passed、11 个既有弃用告警。
- “已有资料”章节均能定位至少一个事实、证据包或知识资产 ID。
- 固定历史章节号、过期职业健康安全证书、人员受限证件号和未知证据包引用均由自动测试阻断。

## 门禁结论

本轮未新增或修改 RAG 语料、metadata、召回策略、API、数据库资产或 DOCX 选图/导出逻辑，因此不执行 Base+泰昌召回门禁、真实 `/api/knowledge/search/stream` 或 DOCX XML 审计。P1-05 接入 RAG 和生成链路后必须执行上述真实门禁。

下一步：P1-05 RAG 入库与回归门禁。

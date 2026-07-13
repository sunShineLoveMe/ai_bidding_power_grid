# 泰昌历史标书复用 P1-02 文件级证据包运行记录

> 日期：2026-07-13
> 范围：泰昌物资类投标试点
> 数据策略：只读，不写数据库，不接入 P0-06 尚未完成提取和入库的历史 Word 候选

## 1. 任务目标

在不等待 P0-06 业务审批、不绕过资产准入门禁的前提下，复用当前已入库且可追溯的泰昌企业事实资料，形成稳定的文件级证据包：一份业务证据只有一个 `evidence_bundle_id`，完整 PDF/原图保留原页序，重复 PDF 和关键页图片只作 rendition。

## 2. 真实输入核对

通过实时 PostgreSQL 只读快照复核当前基线，结果与 P0-02 冻结快照一致：

| 记录类型 | 数量 |
| --- | ---: |
| 知识文档 | 77 |
| 文档分块 | 6347 |
| 图片/附件资产 | 599 |
| 产品参数 | 36 |
| 项目业绩结构化证据 | 2 |
| 原始企业文件 | 116 |
| staging 候选 | 539 |

P0-06 v2 当前按策略自动接收 169 条低风险知识候选，但尚未完成 Word 媒体提取、质量校验和数据库入库；本轮包含历史标书候选仍为 0。

## 3. 产物

- `scripts/rag/build_taichang_evidence_bundles.py`
- `docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundles.json`
- `docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundles.csv`
- `docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundle_pages.csv`
- `docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundle_report.md`

## 4. 结果

| 类型 | 证据包数 |
| --- | ---: |
| CPVC/MPP 检验报告 | 2 |
| 主要试验设备及校准资料 | 6 |
| 管理体系认证证书 | 3 |
| 营业执照 | 1 |
| 2023/2024/2025 审计报告 | 3 |
| 合同 + 中标通知书项目业绩 | 1 |
| 合计 | 16 |

- 主证据页数：149 页。
- 页序完整：16/16；缺页 0；重页 0。
- 重复/参考 rendition：21 个，均不作为正式页源。
- 可沿用现有资产使用策略：4 个；受时效、年度或复核条件限制：12 个。
- CPVC 报告编号 `2024100312005501713`，关联 19 行结构化参数。
- MPP 报告编号 `2024100312005501712`，关联 17 行结构化参数。
- 项目业绩将 2 页中标通知书与 15 页供货合同合并为一个 17 页用户可见业务对象，数量 54,678 米、含税金额 6,372,409.05 元均来自既有结构化证据。

## 5. 安全门禁

- 职业健康安全管理体系证书已于 2026-06-18 到期，`blocked_expired`。
- 6 组设备及校准资料、质量/环境体系证书在有效期完成结构化前为 `review_required_validity`。
- 3 个审计年度为 `conditional_tender_year`，必须按当次招标文件选择。
- 未发现独立资格预审结果原件，记录为资料缺口；历史 Word 页面不得作为替代原件。
- 辽宁招标资料和河北豪乾参考稿不得作为泰昌企业事实，实际证据包命中 0。

## 6. 测试与回归

执行：

```bash
.venv/bin/python scripts/rag/build_taichang_evidence_bundles.py
.venv/bin/pytest -q tests/test_taichang_evidence_bundles.py \
  tests/test_taichang_historical_bid_asset_dedup.py \
  tests/test_taichang_p0_06_asset_review.py
PYTHONPATH=. .venv/bin/pytest -q
```

结果：

- 新增证据包测试：11 passed。
- P0-04/P0-06 联合专项：30 passed。
- 后端全量：400 passed，2 subtests passed，11 个既有弃用告警。
- 首次直接执行 `.venv/bin/pytest -q` 因项目根目录未进入模块搜索路径而在收集阶段失败；补充 `PYTHONPATH=.` 后全量通过。该环境型失败如实保留，不计为业务逻辑通过。

## 7. 回归门禁结论

本轮未新增客户资料、未写数据库、未修改 RAG 语料/metadata/召回策略、未改变页面接口或 DOCX 选图与导出逻辑，因此不重复执行 Base+泰昌召回门禁、真实 stream 和正式 DOCX 导出。后续 P1-01 一旦发生审批入库或 metadata 变更，必须执行标准增量门禁；P2-04 接入整包 DOCX 导出时必须走真实导出链路并审计 DOCX XML。

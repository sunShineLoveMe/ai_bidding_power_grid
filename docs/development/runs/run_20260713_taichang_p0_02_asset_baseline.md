# 泰昌专版 P0-02 数字资产基线运行记录

> 日期：2026-07-13
> 状态：PASS
> 执行策略：只读数据库 + 本地文件哈希与 staging 盘点

## 执行结果

| 步骤 | 结果 | 说明 |
| --- | --- | --- |
| PostgreSQL 连接与表结构检查 | PASS | 读取 `knowledge_documents/document_chunks/knowledge_assets`，无写操作 |
| 知识文档快照 | PASS | 77 条 |
| 文档分块快照 | PASS | 6,347 条，全部补算正文哈希 |
| 图片/附件资产快照 | PASS | 599 条 |
| 产品参数结构化快照 | PASS | 36 行 |
| 项目业绩结构化快照 | PASS | 2 条证据 |
| 原始资料文件哈希 | PASS | 116 份文件、91 个唯一哈希 |
| staging 候选盘点 | PASS | 539 条，全部保持隔离 |
| 正式资产审计 | PASS | 数据库资产/文档/分块问题 0；staging 中间产物问题 539 |
| 快照脚本单测 | PASS | 4 passed |
| JSON/CSV 一致性 | PASS | 两种格式均为 7,716 条，稳定业务键均非空 |
| 同源重跑确定性 | PASS | 两次记录集 SHA-256 均为 `b5f9859bf6de97d91f7317376a54afe4020be59f733ec1f04a75cb6a6295d66a` |

## 输出

- `docs/development/taichang-bid-v1-data/current_asset_baseline.json`
- `docs/development/taichang-bid-v1-data/current_asset_baseline.csv`
- `docs/development/taichang-current-asset-baseline-report-20260713.md`
- `docs/development/runs/run_20260713_taichang_p0_02_asset_baseline_audit.json`
- `docs/development/runs/run_20260713_taichang_p0_02_asset_baseline_audit.md`

## 未执行项说明

- 未新增客户资料、未修改 metadata、未调整召回策略，因此本轮不重复执行 Base 30 + 泰昌 30 增量召回门禁。
- 未运行 DOCX 导出，因为本任务没有改变资产选择、题注或导出逻辑。
- 未清理 2 个测试资产、6 条重复知识文档和 25 份重复原始文件；这些属于 P0-04/P0-05。

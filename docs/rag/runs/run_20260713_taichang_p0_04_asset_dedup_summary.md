# 泰昌历史标书复用 P0-04 四层去重运行记录

> 执行日期：2026-07-13
> 任务性质：只读审计，高风险候选隔离
> 试点范围：河北泰昌电力器材科技有限公司

## 1. 输入冻结

| 输入 | 数量/哈希 |
| --- | --- |
| 当前数字资产基线 | 7,716 条；`ac2e6428fb132f84978fc362e9cca8a21c8c9a871941d68ae53b4ff7582b957b` |
| 技术标候选 | 486 条；`b9d836843aab012c381659812136ea3d5c42f4f6560b6b678a338f207fde8b40` |
| 商务标候选 | 410 条；`076d540a7165bbd7d09db0989be885e0fdfd6bcf99d78649e3d72c53adbf26a3` |

执行后再次校验上述三个 SHA-256，全部未变化。

## 2. 安全边界

- 脚本不导入后端数据库模块，不连接数据库，不执行 INSERT/UPDATE/DELETE。
- 不修改现有 metadata、RAG 分块、embedding、召回策略或正式 DOCX 选图规则。
- 感知哈希只生成 `possible_visual_duplicate`，不自动删除、覆盖或合并。
- 空白/近空白页、小图及印章风险图增加保护标记，必须人工视觉复核。
- 所有输出为 `review_only / allowed_for_bid=false / promotion_eligible=false`。

## 3. 四层结果

| 去重状态 | 数量 | 处理结论 |
| --- | ---: | --- |
| `duplicate_exact` | 270 | 不进入增量入库，仅保留追溯 |
| `possible_visual_duplicate` | 142 | 禁止自动合并，逐图人工复核 |
| `possible_text_duplicate` | 5 | 补齐编号/原始证据后人工复核 |
| `same_evidence_new_rendition` | 2 | 归入既有报告证据包候选 |
| `fact_conflict` | 15 | 历史项目号/固化 ID 不得复用 |
| `new` | 462 | 仅可进入 P0-05 标签与质量审核 |

其中重新读取 staging 真实图片路径并建立视觉索引 543 个。staging 清单的 JSON `content_sha256` 未用于图片字节精确判定。

## 4. 关键业务校验

- 报告 `2024100312005501712`、`2024100312005501713` 均命中既有结构化参数记录，判为同一证据的不同载体。
- 报告 `2024400312005505333`、`2025200312005503479` 未误判为既有证据，保持新候选且禁止提升，等待客户原始资料。
- 15 个历史项目号/固化 ID 全部判为 `fact_conflict`，要求由当次招标文件覆盖。
- 134 个章节和 14 个表格虽取得去重状态，但明确属于结构/表单参考，不是资产入库对象。

## 5. 测试与重复执行

执行命令：

```bash
.venv/bin/python -m unittest \
  tests.test_taichang_historical_bid_asset_dedup \
  tests.test_taichang_historical_bid_inventory \
  tests.test_taichang_asset_baseline_snapshot -v
```

结果：18 项全部通过，覆盖候选全量状态、精确重复阻断、感知疑似人工复核、空白页保护、已知/缺失报告分离、项目专属事实冲突和冻结输入哈希。

第二次独立运行后，删除 `metadata.generated_at` 再比较 JSON，结果完全一致；说明结果具备确定性。

## 6. 回归门禁结论

本轮没有新增资料入库、修改 metadata、调整召回/rerank、改变正式图片准入或 DOCX 导出，因此没有重复执行 Base 30 + 泰昌专项 30 的真实召回门禁，也没有执行 DOCX 导出。P0-05 一旦发生审核入库、metadata 回填或正式资产状态变化，必须执行标准增量回归门禁和真实 stream 抽样。

## 7. 产物

- `scripts/rag/deduplicate_taichang_historical_bid_assets.py`
- `tests/test_taichang_historical_bid_asset_dedup.py`
- `docs/development/taichang-bid-v1-data/asset_dedup_matrix.json`
- `docs/development/taichang-bid-v1-data/asset_dedup_matrix.csv`
- `docs/development/taichang-historical-bid-asset-dedup-report-20260713.md`

结论：P0-04 完成，但没有任何候选在本任务中取得正式入库或正式标书使用授权。

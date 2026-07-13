# 泰昌历史标书复用 P0-05 标签、分类与质量分级验证记录

> 日期：2026-07-13
> 范围：河北泰昌电力器材科技有限公司两份历史标书候选
> 结论：PASS（只读分类完成，正式增量入库保持关闭）

## 一、任务边界

本轮承接 P0-04 四层去重结果，对 896 条候选统一补齐主体、来源域、目标库、证据类型、产品族、分册、章节、敏感级别、质量等级、审核状态、去重状态和中文展示字段。

本轮没有连接或写入数据库，没有修改正式 RAG 语料/metadata/召回，也没有修改 DOCX 选图或导出策略。P0-06 人工批准前，所有候选继续保持不可正式入库、不可自动进入标书的状态。

## 二、输入与可重复性

| 输入 | SHA-256 |
| --- | --- |
| `asset_dedup_matrix.json` | `0675054ee14d10714fffaf942c574a5832b73666c6f7d6218ea50c8f121ddfdb` |
| `taichang_technical_bid_candidate_inventory.json` | `b9d836843aab012c381659812136ea3d5c42f4f6560b6b678a338f207fde8b40` |
| `taichang_business_bid_candidate_inventory.json` | `076d540a7165bbd7d09db0989be885e0fdfd6bcf99d78649e3d72c53adbf26a3` |

第二次执行后，忽略 `generated_at` 字段，标签字典、分类矩阵、人工复核队列和入库候选四份 JSON 与首次输出完全一致；三份冻结输入哈希未变化。

## 三、分类结果

| 验证项 | 结果 |
| --- | --- |
| 候选全覆盖 | PASS，896/896 已分类 |
| 质量分级 | PASS，`review_only` 838、`restricted` 58 |
| 人工复核队列 | PASS，461 条 |
| 精确重复阻断 | PASS，270 条不进入复核队列和入库候选 |
| 事实冲突阻断 | PASS，15 条不进入复核队列和入库候选 |
| 产品边界 | PASS，产品事实缺少产品族时不得提升为正式可用 |
| 中文展示 | PASS，全部用户可见字段未命中内部枚举、路径、UUID、长哈希、`页面_`、`原图` 等禁用表达 |
| 显式批准门禁 | PASS，未提供 P0-06 批准 ID 时入库候选为 0 |
| 质量门禁 | PASS，仅提供批准 ID 也不能绕过质量等级和产品边界 |

## 四、测试与静态检查

执行：

```bash
.venv/bin/python -m unittest \
  tests.test_taichang_historical_bid_candidate_classification \
  tests.test_taichang_historical_bid_asset_dedup \
  tests.test_taichang_historical_bid_inventory \
  tests.test_taichang_asset_baseline_snapshot -v
```

结果：27 passed。

分类专项覆盖：必填 metadata、中文展示、重复/冲突阻断、全部 `possible_*` 人工复核、敏感资料受限、无审批不入库、批准 ID 不绕过质量门禁、产品事实必须有产品族。

## 五、RAG 与 DOCX 门禁结论

本轮只新增离线分类脚本、只读 JSON/CSV 和治理文档；没有新增或修改正式资料、数据库 metadata、召回策略、参考来源展示或 DOCX 资产选择。因此本轮不重复执行 Base 30 + 泰昌专项 30 增量召回门禁，也不执行正式 DOCX 导出。

P0-06 一旦批准并实际写入增量资产或修改 metadata，必须执行标准增量回归门禁、真实 `/api/knowledge/search/stream` 抽样，并在涉及配图时执行正式 DOCX 导出及 XML 审计。

## 六、结论与下一步

P0-05 完成。当前 `asset_ingestion_candidates` 为 0 是预期结果，不是缺失：它证明历史标书内容没有因“未发现重复”而被自动视为可用资产。

下一步进入 P0-06，按 461 条人工复核队列确认原始证据、产品/规格、有效期、敏感性和目标库；只有人工批准且质量等级提升后的候选，才允许进入增量入库批准清单。

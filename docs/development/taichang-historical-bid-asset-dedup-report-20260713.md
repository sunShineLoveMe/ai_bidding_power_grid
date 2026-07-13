# 泰昌历史标书候选资产四层去重报告

> 生成时间：2026-07-13T17:35:49.582336+08:00
> 结论性质：P0-04 只读审计，不代表候选已成为正式资产。

## 一、执行结论

- 冻结基线记录：7716 条。
- 历史标书候选：896 条，已全部给出去重状态。
- 可访问并重新计算真实图片哈希的基线视觉文件：543 个。
- 未连接数据库、未改 metadata、未执行自动合并、未生成任何正式入库记录。
- 所有候选继续保持 `review_only / allowed_for_bid=false / promotion_eligible=false`。

## 二、去重状态统计

| 状态 | 数量 | 安全处理 |
| --- | ---: | --- |
| `duplicate_exact` | 270 | 不进入增量入库，只保留来源追溯 |
| `fact_conflict` | 15 | 不得复用或覆盖，以当次招标文件/原始事实为准 |
| `new` | 462 | 仅进入 P0-05 标签和质量审核，不代表可入库 |
| `possible_text_duplicate` | 5 | 补业务编号/原始证据后人工复核 |
| `possible_visual_duplicate` | 142 | 人工逐图复核，禁止自动合并 |
| `same_evidence_new_rendition` | 2 | 归入同一证据包候选，不新建业务主记录 |

## 三、四层规则与风险控制

1. 文件层：仅 SHA-256 字节完全一致才判 `duplicate_exact`。
2. 视觉层：从 staging 的真实 `local_path` 重新计算图片哈希；dHash 距离不超过 4 也只判 `possible_visual_duplicate`。空白页、小图、印章/签章风险图禁止自动合并。
3. 文本层：名称相同但缺少报告号、证书号、设备编号等业务键时，只判 `possible_text_duplicate`。
4. 业务层：报告编号相同的 Word 载体与既有结构化参数记录归入同一 `evidence_bundle_id`，不建立第二个报告主记录。

## 四、明确未执行事项

- 未把 Word 内嵌图片导入产品库、资信库或知识库。
- 未把历史项目号、固化 ID、通用响应话术写入新项目。
- 未根据感知哈希删除、覆盖或合并任何文件。
- 未对证书/报告图片做 OCR，因此图片内部编号、有效期、签章和参数仍需原始文件或人工复核。

## 五、P0 门禁

- [x] `all_candidates_have_dedup_status`
- [x] `all_candidates_blocked_from_promotion`
- [x] `all_candidates_allowed_for_bid_false`
- [x] `possible_visual_duplicates_require_manual_review`
- [x] `exact_duplicates_blocked`

P0-05 只能消费本矩阵中通过后续标签、质量分级和人工审核的候选；本报告本身不授权入库。

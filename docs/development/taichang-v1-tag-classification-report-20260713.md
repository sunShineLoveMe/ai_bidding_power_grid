# 泰昌专版 V1 标签、分类与质量分级报告

> 生成时间：2026-07-13T17:54:38.522310+08:00
> 范围：河北泰昌电力器材科技有限公司历史标书候选

## 执行结论

- 已分类候选：896 条。
- P0-06 人工审核队列：461 条。
- 已批准候选 ID：0 条。
- 正式增量入库候选：0 条。
- 本轮未写数据库、未改变 RAG、未改变 DOCX 选图规则。

## 质量等级

| 质量等级 | 数量 | 处理 |
| --- | ---: | --- |
| `restricted` | 58 | 受限资料 |
| `review_only` | 838 | 仅限人工复核 |

## 审核状态

| 审核状态 | 数量 |
| --- | ---: |
| `needs_customer_confirmation` | 314 |
| `needs_manual_review` | 149 |
| `not_asset_reference` | 148 |
| `rejected_conflict` | 15 |
| `rejected_duplicate` | 270 |

## 关键安全结论

- `new` 只代表未发现重复，不代表已批准或可入库。
- 精确重复和事实冲突不进入 P0-06 审核队列。
- 视觉/文本疑似重复必须人工确认，不得自动合并。
- 历史 Word 图片、报告页和参数候选继续保持 `review_only`；敏感资料为 `restricted`。
- 正式入库清单只接受 P0-06 明确批准且通过产品、质量、敏感性门禁的候选。

## 门禁结果

- [x] `all_candidates_classified`
- [x] `all_required_metadata_present`
- [x] `all_visible_fields_clean`
- [x] `duplicates_excluded_from_review_queue`
- [x] `conflicts_excluded_from_review_queue`
- [x] `ingestion_requires_explicit_approval`
- [x] `no_unapproved_ingestion_candidate`
- [x] `product_fact_requires_product_family`

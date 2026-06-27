# 泰昌正式图片资产展示字段回填

> Run：`run_20260627_taichang_formal_asset_repair_uuid_visible_cleanup`
> dry_run：`False`

## 摘要

| 指标 | 数量 |
| --- | ---: |
| 扫描资产 | 599 |
| 更新资产 | 3 |
| 重写标题 | 3 |
| 剔除正式标书候选 | 0 |
| 抑制整页资料题注 | 1 |

## 样例

- `f4ad1957-e130-4f80-b93f-8ba00fd9ec96` 企业资料 -> 生产制造能力资料；题注策略：formal_material_caption；正式题注：资料：企业资料
- `d0584437-839b-4698-9691-00f0e299f3af` 企业资料 -> 生产制造能力资料；题注策略：formal_material_caption；正式题注：资料：企业资料
- `f31ca9d0-bcca-4970-900c-0b7dcec3bfd4` 企业资料 -> 财务资料资料；题注策略：suppressed_document_page_caption；正式题注：无

# 泰昌正式图片资产展示字段回填

> Run：`run_20260627_taichang_formal_asset_repair_specs_formal_title`
> dry_run：`False`

## 摘要

| 指标 | 数量 |
| --- | ---: |
| 扫描资产 | 599 |
| 更新资产 | 54 |
| 重写标题 | 0 |
| 剔除正式标书候选 | 0 |
| 抑制整页资料题注 | 52 |

## 样例

- `f4ad1957-e130-4f80-b93f-8ba00fd9ec96` 生产制造能力资料 -> 生产制造能力资料；题注策略：formal_material_caption；正式题注：资料：生产制造能力资料
- `d0584437-839b-4698-9691-00f0e299f3af` 生产制造能力资料 -> 生产制造能力资料；题注策略：formal_material_caption；正式题注：资料：生产制造能力资料
- `f31ca9d0-bcca-4970-900c-0b7dcec3bfd4` 财务资料 -> 财务资料；题注策略：suppressed_document_page_caption；正式题注：无
- `c3835978-c432-4d59-b79f-524ea67721ec` 投标 -> 投标；题注策略：suppressed_document_page_caption；正式题注：无
- `0cab5a2c-dd01-436c-bf4b-6e8b5d84f28a` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `e71a6d5a-9f73-4b2e-a67f-ee465695a518` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `2ea56ed1-8f56-45e0-9892-54a37d828f5a` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `4a18fbcc-16e1-42f7-87fb-a04df1c0a59a` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `25e13e0b-57ec-4a10-a523-48a040f5cc74` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `00ecddf9-82d9-4950-b271-183f0dbcc36a` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `6ce57cf5-3209-4bfc-bd0d-1f5095ad7fa9` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `3a143bff-8f19-44f7-b3a5-13bc30d1d785` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `a22692ef-8061-475e-8e1e-d336e3e04cd4` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `7a316acf-92c5-434e-97a8-0e6e993116bc` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `2c0e1a82-349e-4185-b17f-048f61ada603` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `fbb0d4b1-14b1-4eb7-bb94-98a38323dfcc` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `a510a59c-bbd4-42b9-9394-d580f0cdd44e` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `a161d1ae-b27d-4a5f-ae07-2aceec6cbdbd` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `a3ff26f7-bbd9-4178-bd77-d08207562e73` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `d4587511-67cb-45a8-a8bc-378439705981` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `848f6ab4-7713-44dc-84fa-62f117ad7c9d` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `3a5ba705-4523-4c18-948e-5cf152b2b081` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `0f7074d1-f619-432e-9eb1-5d8b9c31fb10` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `19434a03-4392-450e-8318-e6f5bc8dcef3` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `8b167e5b-8473-437d-bc3e-3da510a1f950` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `e70bccd6-3f2c-4151-9c47-42f28ad4ad1a` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `2288316a-1918-4d61-ba66-8f61ed2ccbc4` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `5b06311e-5057-4d26-8a0a-38fc7acd836b` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `ba0b71a0-8780-4bd2-87c9-0513b7a4baa9` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无
- `7d216e70-f659-47df-af19-a01405f776e5` 宣传彩页 -> 宣传彩页；题注策略：suppressed_document_page_caption；正式题注：无

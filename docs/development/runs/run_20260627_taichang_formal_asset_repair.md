# 泰昌正式图片资产展示字段回填

> Run：`run_20260627_taichang_formal_asset_repair`
> dry_run：`False`

## 摘要

| 指标 | 数量 |
| --- | ---: |
| 扫描资产 | 599 |
| 更新资产 | 599 |
| 重写标题 | 599 |
| 剔除正式标书候选 | 2 |
| 抑制整页资料题注 | 505 |

## 样例

- `ff3447bd-bede-493d-bb51-d7eb4d1b3acb` 泰昌2023年审计报告第1页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `5f0829f5-c64a-4b3b-b125-50a4ac46689a` 泰昌2023年审计报告第2页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `c08a6a60-9a9f-48c3-9b01-ca38bcc6661e` 泰昌2023年审计报告第3页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `39e276cc-5e58-463c-bf8e-a3f211c3b5ac` 泰昌2023年审计报告第4页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `495b6f71-53e1-4624-9f10-29d7590b93c4` 泰昌2023年审计报告第5页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `753cc122-2431-428c-a41f-8777d1344f7a` 泰昌2023年审计报告第6页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `a3c9cfb2-cd3b-4dd4-8cbb-c87d6f872759` 泰昌2023年审计报告第7页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `f5c8f472-83a9-4a29-8ee5-f91fc0120b74` 泰昌2023年审计报告第8页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `956112bc-65c3-441b-8d70-ac4d65d3b24f` 泰昌2023年审计报告第9页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `1f17aa09-4e6f-4b86-a6cd-2e98c55994fe` 泰昌2023年审计报告第10页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `f52d4793-a7db-4c48-ac97-0a40afc1205f` 泰昌2023年审计报告第11页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `1b93e8ce-5e09-4bf2-8ffe-5fece4049542` 泰昌2023年审计报告第12页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `c5d8c48a-290d-493a-a8a3-fc4832d4cf4f` 泰昌2023年审计报告第13页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `4db3fb31-0ae6-4c91-b241-999bd3342b05` 泰昌2023年审计报告第14页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `c6407b66-aa5f-4157-ab06-cb35732cc14a` 泰昌2023年审计报告第15页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `65c343a9-4e74-4ca9-af26-a2d4fab5e92a` 泰昌2023年审计报告第16页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `55e8a849-d27b-46fa-a169-40d626f8522c` 泰昌2023年审计报告第17页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `e8d4c3fd-b0ab-4b8a-8ad3-e6f443e9dcb0` 泰昌2023年审计报告第18页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `32c9bd0e-2f68-4a6d-aaff-4e6f864d0ddc` 泰昌2023年审计报告第19页 -> 2023年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `fb1840f1-7b52-42c6-97ae-09cd8f2bed4b` 泰昌2024年审计报告第1页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `79a5a9af-4191-4a93-8fdb-7afdb066024e` 泰昌2024年审计报告第2页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `eaaabad3-f539-4323-b900-55a6e93d6e16` 泰昌2024年审计报告第3页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `e761588e-d6bf-4327-a964-84cb3fcb6a13` 泰昌2024年审计报告第4页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `6b1d3d4d-2e64-4110-9384-06d8b6ebab13` 泰昌2024年审计报告第5页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `b038dfaf-b671-42d3-a396-31be98554fbc` 泰昌2024年审计报告第6页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `5ab77fae-3472-47bf-97d1-9f1ed8959ec1` 泰昌2024年审计报告第7页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `5cf50668-34a1-41e6-ba15-58232c55bf5d` 泰昌2024年审计报告第8页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `0b013587-6efe-4150-ba5c-037263fca5d0` 泰昌2024年审计报告第9页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `b6cdd3e4-f47e-4a50-8be5-574c74b88813` 泰昌2024年审计报告第10页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无
- `839df7ac-6e93-4a3b-b588-053db9cf148e` 泰昌2024年审计报告第11页 -> 2024年审计报告；题注策略：suppressed_document_page_caption；正式题注：无

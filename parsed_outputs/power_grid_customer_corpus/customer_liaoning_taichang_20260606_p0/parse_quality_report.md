# 泰昌 MVP 资料 Parse Quality Report

> 说明：本批资料用于泰昌 MVP 试点企业内部标书写作和智能问答。企业自有资料在泰昌租户内可用于 `knowledge_chat`、`bid_writing`、`asset_search`；不得跨企业、跨租户使用，也不得与河北豪乾参考稿混作泰昌事实。

## Summary

| 指标 | 数量 |
| --- | ---: |
| PDF 总数 | 42 |
| MinerU 完成 | 42 |
| 文本字符数 | 284019 |
| 图片资产 | 242 |
| 泰昌内部私有资产 | 78 |

## By Evidence Type

| evidence_type | 文件数 | 文本字符 | 图片资产 | 内部私有文件 |
| --- | ---: | ---: | ---: | ---: |
| `finance` | 3 | 91859 | 63 | 3 |
| `certification` | 6 | 24997 | 41 | 0 |
| `inspection_report` | 2 | 8825 | 2 | 0 |
| `production_capacity` | 15 | 33036 | 37 | 6 |
| `testing_capacity` | 12 | 60938 | 60 | 6 |
| `green_low_carbon` | 3 | 63806 | 38 | 0 |
| `business_license` | 1 | 558 | 1 | 1 |

## Ingestion Recommendation

| 建议 | 文件数 |
| --- | ---: |
| `ready_for_private_ingestion` | 24 |
| `ingest_with_spec_coverage_warning` | 2 |
| `ready_for_taichang_internal_ingestion` | 16 |

## Quality Flags

| 标记 | 数量 | 处理 |
| --- | ---: | --- |
| `spec_coverage_needs_business_confirmation` | 2 | CPVC/MPP 内径 250 检验报告需确认与辽宁清单规格覆盖关系 |
| `no_image_assets` | 3 | 可保留文本，不影响 OCR 完成状态 |
| `taichang_internal_private_allowed_for_tenant_use` | 16 | 泰昌租户内可直接用于问答/写作/资产检索；禁止跨租户和跨企业使用 |

## File Records

| 文件 | evidence_type | privacy_level | 页数 | 文本字符 | 图片资产 | 建议 | 质量标记 |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| `2023年审计报告.pdf` | `finance` | `taichang_internal_private` | 0 | 28797 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `2024年审计报告.pdf` | `finance` | `taichang_internal_private` | 0 | 33601 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `2025年审计报告.pdf` | `finance` | `taichang_internal_private` | 0 | 29461 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `1.质量管理体系认证证书.pdf` | `certification` | `private` | 0 | 6113 | 0 | `ready_for_private_ingestion` | - |
| `2.环境管理体系认证证书.pdf` | `certification` | `private` | 0 | 3274 | 0 | `ready_for_private_ingestion` | - |
| `3.职业健康安全管理体系认证证书.pdf` | `certification` | `private` | 0 | 4539 | 0 | `ready_for_private_ingestion` | - |
| `CPVC电缆保护管检验报告内径250.pdf` | `inspection_report` | `private` | 0 | 4462 | 0 | `ingest_with_spec_coverage_warning` | `spec_coverage_needs_business_confirmation` |
| `MPP电缆保护管检验报告内径250.pdf` | `inspection_report` | `private` | 0 | 4363 | 0 | `ingest_with_spec_coverage_warning` | `spec_coverage_needs_business_confirmation` |
| `1.陈仙瑞.pdf` | `production_capacity` | `taichang_internal_private` | 0 | 270 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `2.晁坤琳.pdf` | `production_capacity` | `taichang_internal_private` | 0 | 390 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `公司人员花名册.pdf` | `production_capacity` | `taichang_internal_private` | 0 | 7056 | 0 | `ready_for_taichang_internal_ingestion` | `no_image_assets`、`taichang_internal_private_allowed_for_tenant_use` |
| `1.陈仙瑞.pdf` | `production_capacity` | `taichang_internal_private` | 0 | 1415 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `2.晁坤琳.pdf` | `production_capacity` | `taichang_internal_private` | 0 | 1414 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `泰昌社保证明.pdf` | `production_capacity` | `taichang_internal_private` | 0 | 991 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `1.CPVC63三层复合管材挤出生产线.pdf` | `production_capacity` | `private` | 0 | 4713 | 0 | `ready_for_private_ingestion` | - |
| `2.CPVC110三层复合管材挤出生产线.pdf` | `production_capacity` | `private` | 0 | 4645 | 0 | `ready_for_private_ingestion` | - |
| `3.MPP生产线.pdf` | `production_capacity` | `private` | 0 | 5408 | 0 | `ready_for_private_ingestion` | - |
| `生产设备台账.pdf` | `production_capacity` | `private` | 0 | 514 | 0 | `ready_for_private_ingestion` | - |
| `1.土地租赁协议.pdf` | `production_capacity` | `private` | 0 | 1778 | 0 | `ready_for_private_ingestion` | - |
| `2.土地使用证明.pdf` | `production_capacity` | `private` | 0 | 358 | 0 | `ready_for_private_ingestion` | - |
| `3.厂房图片.pdf` | `production_capacity` | `private` | 0 | 1865 | 0 | `ready_for_private_ingestion` | - |
| `4.电费发票.pdf` | `production_capacity` | `private` | 0 | 1496 | 0 | `ready_for_private_ingestion` | `no_image_assets` |
| `微机控制电子万能试验机.pdf` | `testing_capacity` | `private` | 0 | 7631 | 0 | `ready_for_private_ingestion` | - |
| `热变型、维卡软化点温度测定仪.pdf` | `testing_capacity` | `private` | 0 | 14790 | 0 | `ready_for_private_ingestion` | - |
| `电子天平.pdf` | `testing_capacity` | `private` | 0 | 5235 | 0 | `ready_for_private_ingestion` | - |
| `锤击试验装置.pdf` | `testing_capacity` | `private` | 0 | 6662 | 0 | `ready_for_private_ingestion` | - |
| `溶体流动速率仪.pdf` | `testing_capacity` | `private` | 0 | 8591 | 0 | `ready_for_private_ingestion` | - |
| `电子拉力试验机.pdf` | `testing_capacity` | `private` | 0 | 6493 | 0 | `ready_for_private_ingestion` | - |
| `试验设备台账.pdf` | `production_capacity` | `private` | 0 | 723 | 0 | `ready_for_private_ingestion` | - |
| `1.陈仙瑞.pdf` | `testing_capacity` | `taichang_internal_private` | 0 | 270 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `2.晁坤琳.pdf` | `testing_capacity` | `taichang_internal_private` | 0 | 390 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `公司人员花名册.pdf` | `testing_capacity` | `taichang_internal_private` | 0 | 7056 | 0 | `ready_for_taichang_internal_ingestion` | `no_image_assets`、`taichang_internal_private_allowed_for_tenant_use` |
| `1.陈仙瑞.pdf` | `testing_capacity` | `taichang_internal_private` | 0 | 1415 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `2.晁坤琳.pdf` | `testing_capacity` | `taichang_internal_private` | 0 | 1414 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `泰昌社保证明.pdf` | `testing_capacity` | `taichang_internal_private` | 0 | 991 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |
| `绿色供应链认证证书.pdf` | `certification` | `private` | 0 | 1213 | 0 | `ready_for_private_ingestion` | - |
| `废水废气废固报告.pdf` | `green_low_carbon` | `private` | 0 | 24070 | 0 | `ready_for_private_ingestion` | - |
| `绿色发展规划报告.pdf` | `certification` | `private` | 0 | 8711 | 0 | `ready_for_private_ingestion` | - |
| `绿色电力认证证书.pdf` | `certification` | `private` | 0 | 1147 | 0 | `ready_for_private_ingestion` | - |
| `ESG环境社会公司治理报告.pdf` | `green_low_carbon` | `private` | 0 | 30395 | 0 | `ready_for_private_ingestion` | - |
| `碳足迹报告.pdf` | `green_low_carbon` | `private` | 0 | 9341 | 0 | `ready_for_private_ingestion` | - |
| `营业执照副本.pdf` | `business_license` | `taichang_internal_private` | 0 | 558 | 0 | `ready_for_taichang_internal_ingestion` | `taichang_internal_private_allowed_for_tenant_use` |

## Usage Policy

- 泰昌企业自有资料可在泰昌租户内用于 `knowledge_chat`、`bid_writing`、`asset_search`。
- `taichang_internal_private` 表示内部私有资料，不代表需要二次授权或脱敏；它的边界是租户隔离和企业事实隔离。
- 严禁将河北豪乾参考稿作为泰昌企业事实来源。
- 严禁将泰昌企业事实污染辽宁招标要求、技术规范或合同条款。

# 泰昌 MVP OCR 解析质量报告

> 批次：`customer_liaoning_taichang_20260606_p0`
> 生成时间：2026-06-06T03:43:22.357873+00:00

## 总览

| 指标 | 数量 |
| --- | ---: |
| PDF 总数 | 42 |
| MinerU 完成 | 42 |
| 文本字符数 | 284019 |
| 图片资产 | 242 |
| 受限图片资产 | 78 |

## 按资料类型

| 类型 | 文件数 | 文本字符 | 图片资产 | 受限文件 |
| --- | ---: | ---: | ---: | ---: |
| `finance` | 3 | 91859 | 63 | 3 |
| `certification` | 6 | 24997 | 41 | 0 |
| `inspection_report` | 2 | 8825 | 2 | 0 |
| `production_capacity` | 15 | 33036 | 37 | 6 |
| `testing_capacity` | 12 | 60938 | 60 | 6 |
| `green_low_carbon` | 3 | 63806 | 38 | 0 |
| `business_license` | 1 | 558 | 1 | 1 |

## 入库建议

| 建议 | 文件数 |
| --- | ---: |
| `ingest_only_after_authorization_or_redaction` | 16 |
| `ready_for_private_ingestion` | 24 |
| `ingest_with_spec_coverage_warning` | 2 |

## 质量标记

| 标记 | 数量 |
| --- | ---: |
| `restricted_private_requires_authorization` | 16 |
| `spec_coverage_needs_business_confirmation` | 2 |
| `no_image_assets` | 3 |

## 文件明细

| 文件 | 类型 | 隐私 | 页数 | 文本字符 | 图片 | 建议 | 标记 |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| `2023年审计报告.pdf` | `finance` | `restricted_private` | 19 | 28797 | 20 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `2024年审计报告.pdf` | `finance` | `restricted_private` | 29 | 33601 | 21 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `2025年审计报告.pdf` | `finance` | `restricted_private` | 19 | 29461 | 22 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `1.质量管理体系认证证书.pdf` | `certification` | `private` | 3 | 6113 | 9 | `ready_for_private_ingestion` | - |
| `2.环境管理体系认证证书.pdf` | `certification` | `private` | 2 | 3274 | 10 | `ready_for_private_ingestion` | - |
| `3.职业健康安全管理体系认证证书.pdf` | `certification` | `private` | 3 | 4539 | 7 | `ready_for_private_ingestion` | - |
| `CPVC电缆保护管检验报告内径250.pdf` | `inspection_report` | `private` | 5 | 4462 | 1 | `ingest_with_spec_coverage_warning` | `spec_coverage_needs_business_confirmation` |
| `MPP电缆保护管检验报告内径250.pdf` | `inspection_report` | `private` | 5 | 4363 | 1 | `ingest_with_spec_coverage_warning` | `spec_coverage_needs_business_confirmation` |
| `1.陈仙瑞.pdf` | `production_capacity` | `restricted_private` | 1 | 270 | 1 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `2.晁坤琳.pdf` | `production_capacity` | `restricted_private` | 1 | 390 | 2 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `公司人员花名册.pdf` | `production_capacity` | `restricted_private` | 2 | 7056 | 0 | `ingest_only_after_authorization_or_redaction` | `no_image_assets`、`restricted_private_requires_authorization` |
| `1.陈仙瑞.pdf` | `production_capacity` | `restricted_private` | 2 | 1415 | 1 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `2.晁坤琳.pdf` | `production_capacity` | `restricted_private` | 2 | 1414 | 1 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `泰昌社保证明.pdf` | `production_capacity` | `restricted_private` | 1 | 991 | 2 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `1.CPVC63三层复合管材挤出生产线.pdf` | `production_capacity` | `private` | 7 | 4713 | 5 | `ready_for_private_ingestion` | - |
| `2.CPVC110三层复合管材挤出生产线.pdf` | `production_capacity` | `private` | 7 | 4645 | 5 | `ready_for_private_ingestion` | - |
| `3.MPP生产线.pdf` | `production_capacity` | `private` | 8 | 5408 | 7 | `ready_for_private_ingestion` | - |
| `生产设备台账.pdf` | `production_capacity` | `private` | 1 | 514 | 1 | `ready_for_private_ingestion` | - |
| `1.土地租赁协议.pdf` | `production_capacity` | `private` | 4 | 1778 | 4 | `ready_for_private_ingestion` | - |
| `2.土地使用证明.pdf` | `production_capacity` | `private` | 1 | 358 | 1 | `ready_for_private_ingestion` | - |
| `3.厂房图片.pdf` | `production_capacity` | `private` | 6 | 1865 | 6 | `ready_for_private_ingestion` | - |
| `4.电费发票.pdf` | `production_capacity` | `private` | 3 | 1496 | 0 | `ready_for_private_ingestion` | `no_image_assets` |
| `微机控制电子万能试验机.pdf` | `testing_capacity` | `private` | 8 | 7631 | 7 | `ready_for_private_ingestion` | - |
| `热变型、维卡软化点温度测定仪.pdf` | `testing_capacity` | `private` | 9 | 14790 | 14 | `ready_for_private_ingestion` | - |
| `电子天平.pdf` | `testing_capacity` | `private` | 6 | 5235 | 7 | `ready_for_private_ingestion` | - |
| `锤击试验装置.pdf` | `testing_capacity` | `private` | 8 | 6662 | 9 | `ready_for_private_ingestion` | - |
| `溶体流动速率仪.pdf` | `testing_capacity` | `private` | 7 | 8591 | 8 | `ready_for_private_ingestion` | - |
| `电子拉力试验机.pdf` | `testing_capacity` | `private` | 8 | 6493 | 8 | `ready_for_private_ingestion` | - |
| `试验设备台账.pdf` | `production_capacity` | `private` | 1 | 723 | 1 | `ready_for_private_ingestion` | - |
| `1.陈仙瑞.pdf` | `testing_capacity` | `restricted_private` | 1 | 270 | 1 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `2.晁坤琳.pdf` | `testing_capacity` | `restricted_private` | 1 | 390 | 2 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `公司人员花名册.pdf` | `testing_capacity` | `restricted_private` | 2 | 7056 | 0 | `ingest_only_after_authorization_or_redaction` | `no_image_assets`、`restricted_private_requires_authorization` |
| `1.陈仙瑞.pdf` | `testing_capacity` | `restricted_private` | 2 | 1415 | 1 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `2.晁坤琳.pdf` | `testing_capacity` | `restricted_private` | 2 | 1414 | 1 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `泰昌社保证明.pdf` | `testing_capacity` | `restricted_private` | 1 | 991 | 2 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |
| `绿色供应链认证证书.pdf` | `certification` | `private` | 1 | 1213 | 5 | `ready_for_private_ingestion` | - |
| `废水废气废固报告.pdf` | `green_low_carbon` | `private` | 35 | 24070 | 14 | `ready_for_private_ingestion` | - |
| `绿色发展规划报告.pdf` | `certification` | `private` | 18 | 8711 | 5 | `ready_for_private_ingestion` | - |
| `绿色电力认证证书.pdf` | `certification` | `private` | 1 | 1147 | 5 | `ready_for_private_ingestion` | - |
| `ESG环境社会公司治理报告.pdf` | `green_low_carbon` | `private` | 39 | 30395 | 19 | `ready_for_private_ingestion` | - |
| `碳足迹报告.pdf` | `green_low_carbon` | `private` | 17 | 9341 | 5 | `ready_for_private_ingestion` | - |
| `营业执照副本.pdf` | `business_license` | `restricted_private` | 1 | 558 | 1 | `ingest_only_after_authorization_or_redaction` | `restricted_private_requires_authorization` |

## 结论

- 泰昌 42 份 PDF 已全部完成 MinerU 解析，缺失为 0。
- 图片资产 metadata 已覆盖知识库问答、标书正文插图、资产检索三个展示场景。
- `restricted_private` 资料必须先授权或脱敏，不能默认进入普通问答图片展示。
- CPVC/MPP 检验报告文件名显示内径 250，本批辽宁清单包含多个规格，正式写作前需要业务确认覆盖关系。

# 泰昌正式资料资产中文化与配图质量审计

> Run：`run_20260627_taichang_formal_asset_audit_after_visible_repair`
> 生成时间：2026-06-27T08:56:01.726367+00:00

## 结论

| 范围 | 扫描数 | 问题数 |
| --- | ---: | ---: |
| 真实图片资产 | 599 | 598 |
| 知识文档 | 77 | 24 |
| 文档分块 | 6347 | 2331 |
| staging 图片 payload | 539 | 538 |

## 图片资产问题分布

| 问题代码 | 数量 |
| --- | ---: |
| `display_trace_marker` | 595 |
| `suspected_local_cut_or_noise` | 300 |
| `file_name_non_chinese` | 5 |

## 典型样例

### display_trace_marker

- `ff3447bd-bede-493d-bb51-d7eb4d1b3acb` 2023年审计报告：2023年审计报告 财务资料 ["泰昌", "泰昌企业事实", "财务资料", "审计报告", "资信库"] ["资格审查资料", "财务资料"] 2023年审计报告 财务资料 财务资料 资信库资料 泰昌2023年审计报告第1页
- `5f0829f5-c64a-4b3b-b125-50a4ac46689a` 2023年审计报告：2023年审计报告 财务资料 ["泰昌", "泰昌企业事实", "财务资料", "审计报告", "资信库"] ["资格审查资料", "财务资料"] 2023年审计报告 财务资料 财务资料 资信库资料 泰昌2023年审计报告第2页
- `c08a6a60-9a9f-48c3-9b01-ca38bcc6661e` 2023年审计报告：2023年审计报告 财务资料 ["泰昌", "泰昌企业事实", "财务资料", "审计报告", "资信库"] ["资格审查资料", "财务资料"] 2023年审计报告 财务资料 财务资料 资信库资料 泰昌2023年审计报告第3页
- `39e276cc-5e58-463c-bf8e-a3f211c3b5ac` 2023年审计报告：2023年审计报告 财务资料 ["泰昌", "泰昌企业事实", "财务资料", "审计报告", "资信库"] ["资格审查资料", "财务资料"] 2023年审计报告 财务资料 财务资料 资信库资料 泰昌2023年审计报告第4页
- `495b6f71-53e1-4624-9f10-29d7590b93c4` 2023年审计报告：2023年审计报告 财务资料 ["泰昌", "泰昌企业事实", "财务资料", "审计报告", "资信库"] ["资格审查资料", "财务资料"] 2023年审计报告 财务资料 财务资料 资信库资料 泰昌2023年审计报告第5页

### suspected_local_cut_or_noise

- `ff3447bd-bede-493d-bb51-d7eb4d1b3acb` 2023年审计报告：2023年审计报告 河北泰昌电力器材科技有限公司财务资料，来源于客户已提供文件《2023年审计报告》。该图片为客户原始资料整页渲染件。 财务资料 qualification_image customer_pdf_full_page_render 2023年审计报告_第001页.jpg parsed_outputs/power_grid_customer_co
- `5f0829f5-c64a-4b3b-b125-50a4ac46689a` 2023年审计报告：2023年审计报告 河北泰昌电力器材科技有限公司财务资料，来源于客户已提供文件《2023年审计报告》。该图片为客户原始资料整页渲染件。 财务资料 qualification_image customer_pdf_full_page_render 2023年审计报告_第002页.jpg parsed_outputs/power_grid_customer_co
- `c08a6a60-9a9f-48c3-9b01-ca38bcc6661e` 2023年审计报告：2023年审计报告 河北泰昌电力器材科技有限公司财务资料，来源于客户已提供文件《2023年审计报告》。该图片为客户原始资料整页渲染件。 财务资料 qualification_image customer_pdf_full_page_render 2023年审计报告_第003页.jpg parsed_outputs/power_grid_customer_co
- `39e276cc-5e58-463c-bf8e-a3f211c3b5ac` 2023年审计报告：2023年审计报告 河北泰昌电力器材科技有限公司财务资料，来源于客户已提供文件《2023年审计报告》。该图片为客户原始资料整页渲染件。 财务资料 qualification_image customer_pdf_full_page_render 2023年审计报告_第004页.jpg parsed_outputs/power_grid_customer_co
- `495b6f71-53e1-4624-9f10-29d7590b93c4` 2023年审计报告：2023年审计报告 河北泰昌电力器材科技有限公司财务资料，来源于客户已提供文件《2023年审计报告》。该图片为客户原始资料整页渲染件。 财务资料 qualification_image customer_pdf_full_page_render 2023年审计报告_第005页.jpg parsed_outputs/power_grid_customer_co

### file_name_non_chinese

- `f4ad1957-e130-4f80-b93f-8ba00fd9ec96` 企业资料：aa787a1c-d48d-46f6-bcbd-4806003b8428.png
- `d0584437-839b-4698-9691-00f0e299f3af` 企业资料：d3e8f52a-a21b-4ecb-89b4-7ccccd80134e.png
- `f31ca9d0-bcca-4970-900c-0b7dcec3bfd4` 企业资料：2025-05-21.jpg
- `d1deec19-0b4a-4c41-8ce5-647dcc93312d` CPVC电缆保护管产品实物资料：codex-taichang-cpvc-test-product.png
- `17e53f70-649b-4a0c-8716-dfc5a502ed02` CPVC电缆保护管产品实物资料：codex-taichang-cpvc-test-product.png

## 后续处理要求

1. 先修复正式展示字段、RAG 选图 caption 和正式导出门禁，再批量回填数据。
2. 对 `bid_allowed_title_trace_marker`、`display_trace_marker`、`display_internal_token` 命中的资产优先处理。
3. 对疑似局部切图、二维码、印章、签名、页脚等资产设置 `allowed_for_bid=false` 或迁移为复核线索。
4. 修复后必须重跑 Base + 泰昌专项增量门禁、真实 `/api/knowledge/search/stream`、技术标/商务标真实 DOCX 导出和阿里云线上复验。

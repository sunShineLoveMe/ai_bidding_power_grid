# 泰昌正式资料资产中文化与配图质量审计

> Run：`run_20260627_local_formal_asset_regression_audit`
> 生成时间：2026-06-27T09:37:06.683975+00:00

## 结论

| 范围 | 扫描数 | 问题数 |
| --- | ---: | ---: |
| 真实图片资产 | 599 | 0 |
| 知识文档 | 77 | 0 |
| 文档分块 | 6347 | 0 |
| staging 图片 payload | 539 | 539 |

## 图片资产问题分布

| 问题代码 | 数量 |
| --- | ---: |

## 典型样例

## 后续处理要求

1. 先修复正式展示字段、RAG 选图 caption 和正式导出门禁，再批量回填数据。
2. 对 `bid_allowed_title_trace_marker`、`display_trace_marker`、`display_internal_token` 命中的资产优先处理。
3. 对疑似局部切图、二维码、印章、签名、页脚等资产设置 `allowed_for_bid=false` 或迁移为复核线索。
4. 修复后必须重跑 Base + 泰昌专项增量门禁、真实 `/api/knowledge/search/stream`、技术标/商务标真实 DOCX 导出和阿里云线上复验。

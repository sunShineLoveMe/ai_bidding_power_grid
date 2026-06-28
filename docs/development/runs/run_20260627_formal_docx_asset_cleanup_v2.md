# 泰昌正式图片题注治理 DOCX 真实复验

> Run：`run_20260627_formal_docx_asset_cleanup_v2`
> 日期：2026-06-27
> 项目：`4d632dbe-f6e6-4066-8fe2-929ecb54ba1d`

## 背景

真实导出的技术标中确认出现不适合正式投标文件的图片说明，例如“图示：泰昌CPVC电缆保护管检验报告内径250第1页”和“图示：泰昌试验设备台账原图”。这类表述把内部追溯名、页码、解析痕迹暴露到正文，不符合国内正式投标文件表达。

## 验证链路

```text
build_project_bid_markdown(volume_type=technical/business, with_images=true)
-> convert_md_to_word(return_report=true)
-> refresh_docx_fields_with_soffice
-> DOCX XML forbidden/caption audit
```

## 结果

| 分册 | 图片候选 | 选中图片 | 字段刷新 | 禁用表达命中 | 页码型题注命中 | 段落数 |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| 技术标 | 597 | 16 | refreshed | 0 | 0 | 2528 |
| 商务标 | 597 | 5 | refreshed | 0 | 0 | 1937 |

输出文件：

- `docs/development/runs/run_20260627_formal_docx_asset_cleanup_v2/technical_泰昌_2225AC_技术投标文件_20260627_图文.docx`
- `docs/development/runs/run_20260627_formal_docx_asset_cleanup_v2/business_泰昌_2225AC_商务投标文件_20260627_图文.docx`
- `docs/development/runs/run_20260627_formal_docx_asset_cleanup_v2/summary.json`

## 结论

本轮图片题注治理通过本地真实 DOCX 链路：正式文件正文未再命中 `图示：`、`原图`、`页面_`、API 路径、UUID 或“检验报告第几页”式追溯题注。

## 剩余风险

- 技术标仍有 59 处待补充/待确认和 11 个正式必填字段未确认。
- 商务标仍有 92 处待补充/待确认和 11 个正式必填字段未确认。
- 上述剩余项属于客户确认字段和正文完整性问题，不属于本轮图片题注问题；在客户补齐前，导出的文件仍应视为草稿版。
- 阿里云线上修复执行和真实浏览器导出复验尚未完成。

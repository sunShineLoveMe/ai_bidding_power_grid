# DOCX P0 格式整改真实导出回归记录

运行日期：2026-06-29

## 范围

本次回归覆盖 `docs/development/docx-export-format-priority-todo.md` 中以下任务：

- `P0-3` 技术标/商务标 profile 页眉留空；
- `P0-4` 技术标/商务标 profile 页脚改居中纯数字页码；
- `P0-5` 封面页码策略；
- `P0-6` 技术标/商务标 profile 正文和表格字体改宋体；
- `P1-5` 补充说明两层图片上限常量。

## 环境

- 分支：`codex/docx-export-p0-format-review`
- 服务健康检查：`GET http://127.0.0.1:3012/api/ready` 返回 `status=ok`
- Celery：`status=ok`，在线 worker `1`
- 数据库 / Redis / 模型配置：均为 `ok`
- LibreOffice：`/opt/homebrew/bin/soffice`

## 代码验证

```bash
.venv/bin/python -m py_compile backend/export/md_to_word.py tests/test_docx_export.py
.venv/bin/python -m pytest tests/test_docx_export.py -q
.venv/bin/python -m pytest tests/test_celery_export_tasks.py -q
```

结果：

| 命令 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| `tests/test_docx_export.py` | `57 passed, 1 warning` |
| `tests/test_celery_export_tasks.py` | `11 passed, 1 warning` |

警告均为 `PyPDF2` 废弃提醒，不影响本次 DOCX 格式整改结论。

## 真实导出链路

真实项目：

```text
project_id = a1d853bc-ca4e-43b4-bbea-256f561c8a3d
```

链路：

```text
build_project_bid_markdown(volume_type, with_images=true)
-> convert_md_to_word(return_report=true, cover_fields=image_selection_report.cover_fields)
-> refresh_docx_fields_with_soffice
-> ensure_docx_table_header_repeat
-> DOCX XML audit
-> LibreOffice PDF export
-> PDF first-page screenshot sampling
```

## 导出结果

| 分册 | DOCX | PDF | 页数 | 图片 | 表格 | 字段刷新 |
| --- | --- | --- | --- | --- | --- | --- |
| 技术标 | `outputs/a1d853bc/泰昌_2225AC_包1_技术投标文件_20260629_图文.docx` | `output/docx-p0-format-regression/泰昌_2225AC_包1_技术投标文件_20260629_图文.pdf` | 341 | found/inserted/skipped/failed = `9/9/0/0` | 110 | `refreshed` |
| 商务标 | `outputs/a1d853bc/泰昌_2225AC_包1_商务投标文件_20260629_图文.docx` | `output/docx-p0-format-regression/泰昌_2225AC_包1_商务投标文件_20260629_图文.pdf` | 189 | found/inserted/skipped/failed = `5/5/0/0` | 55 | `refreshed` |

PDF 抽样截图：

```text
output/docx-p0-format-regression/technical_page1.png
output/docx-p0-format-regression/business_page1.png
```

## DOCX XML 审计

| 检查项 | 技术标 | 商务标 |
| --- | --- | --- |
| `template_id` | `technical_bid_standard` | `business_bid_standard` |
| `template_family` | `formal_bid_xinjiang_sgcc_reference` | `formal_bid_xinjiang_sgcc_reference` |
| 页边距 | 上下 `2.54cm`，左右 `3.17cm` | 上下 `2.54cm`，左右 `3.17cm` |
| 页眉文本 | 空 | 空 |
| 页眉 XML 是否有文本 run | `false` | `false` |
| 页脚字段 | `PAGE` | `PAGE` |
| 是否含 `NUMPAGES` | `false` | `false` |
| 是否含“第/共/页”包装 | `false` | `false` |
| `different_first_page_header_footer` | `false` | `false` |
| `w:titlePg` | `false` | `false` |
| 封面页码 | 显示纯数字 `1` | 显示纯数字 `1` |
| 正文字体样本 | `宋体` | `宋体` |
| 表格字体样本 | `宋体` | `宋体` |
| 图片插入失败 | `0` | `0` |

## 说明与遗留项

- 本轮实现按参考稿口径采用“封面计入页码并显示纯数字 `1`”。如后续客户要求“封面计入但不显示页码”，需新增独立策略，不应回退本次页脚纯数字实现。
- 技术标仍提示 `16` 处待补充/待确认占位，商务标仍提示 `14` 处待补充/待确认占位；本次任务聚焦 DOCX 格式整改，不改变正文资料缺口状态。
- 本次回归使用辽宁 CPVC/MPP 真实项目验证技术/商务 profile；新疆两份参考稿仍只作为版式参考，不作为泰昌企业事实来源。

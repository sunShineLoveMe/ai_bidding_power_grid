# DOCX P0 表格正式化真实导出记录

运行 ID：`run_20260611_docx_quality_p0_table_real_export`

日期：2026-06-11

项目 ID：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`

## 背景

按照 `docs/development/docx-bid-export-quality-todo.md` 的 P0 优先级，本轮处理“表格正式化”。表格是正式标书中最容易暴露排版问题的区域，必须用真实导出链路验证，不以 mock 结果作为验收依据。

## 修复范围

- 表格宽度：导出为 100% 可用页宽，避免窄表或不稳定自适应。
- 表格布局：固定布局，减少 Word/LibreOffice/WPS 重新计算列宽造成的漂移。
- 表头：加粗、浅灰底，并设置跨页重复表头。
- 单元格：设置内边距，避免文字贴边；LibreOffice roundtrip 后会把 `left/right` 规范化为 `start/end`。
- 表格段落：表格内段落不首行缩进，使用 16pt 固定行距。
- 对齐：表头居中；序号、编号、单位、数量、响应情况等短字段居中，其余正文类单元格左对齐，提升长文本可读性。
- metadata：`docx_template` 记录 `table_line_spacing_pt` 和 `table_cell_margin_twips`。

## 自动化测试

命令：

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q
```

结果：

```text
49 passed, 5 warnings
```

## 真实链路

执行链路：

```text
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

输出文件：

- Markdown：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.md`
- DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`
- JSON 记录：`docs/development/runs/run_20260611_docx_quality_p0_table_real_export.json`

## 验收结果

模板与版式：

- 模板：`sgcc_taichang_bid`
- 页面：A4
- 页边距：上 2.0cm、下 2.0cm、左 3.18cm、右 3.18cm
- 正文：宋体 10.5pt，固定行距 20pt
- 表格：宋体 10.5pt，表格内固定行距 16pt，单元格边距 100 twips
- 页眉：`河北泰昌电力器材科技有限公司投标文件`
- 字段刷新：LibreOffice 自动刷新成功

表格结果：

- 表格数量：`60`
- 抽样表格：前 8 个表格
- 图片 found/inserted/skipped/failed：`24/24/0/0`
- Mermaid found/inserted/skipped：`1/0/1`

表格检查：

```json
{
  "table_count_gt_zero": true,
  "all_sample_tables_full_width": true,
  "all_sample_tables_fixed_layout": true,
  "all_sample_tables_repeat_header": true,
  "all_sample_tables_have_cell_margin": true,
  "all_sample_data_rows_no_first_line_indent": true,
  "all_sample_data_rows_line_spacing_16pt": true,
  "all_sample_data_rows_alignment_readable": true
}
```

兼容性说明：

- LibreOffice 刷新后会把表格边距 XML 中的 `left/right` 规范化为 `start/end`，真实验收按 roundtrip 后的 XML 口径读取。
- 当前环境未安装 `mmdc`，Mermaid 仍记录 skipped；正式 DOCX 中未出现 Mermaid 源码块。

清理检查：

```json
{
  "contains_mermaid_fence": false,
  "contains_internal_image_source": false
}
```

## 结论

本轮 P0“表格正式化”已通过自动化回归和真实 DOCX 导出链路验证。正文全篇格式统一仍作为独立 P0 待办继续处理，本轮只关闭表格相关的正式化问题。

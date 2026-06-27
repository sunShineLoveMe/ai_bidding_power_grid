# DOCX P0 正文格式统一真实导出记录

运行 ID：`run_20260611_docx_quality_p0_body_real_export`

日期：2026-06-11

项目 ID：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`

## 背景

按照 `docs/development/docx-bid-export-quality-todo.md` 的 P0 优先级，本轮处理“正文格式统一”。本轮目标是稳定正式投标文件正文观感，包括正文段落、标题、列表、空行和分页相关控制。验收必须使用真实导出链路，不以 mock 结果替代。

## 修复范围

- 正文段落：宋体 `10.5pt`、固定行距 `20pt`、首行缩进 `21pt`、段前段后 `0pt`。
- 正文段落控制：启用 `keep_together` 和 `widow_control`，降低孤行和段落被拆散的概率。
- 标题段落：不首行缩进，固定行距 `20pt`，段前段后稳定；启用 `keep_with_next` 和 `keep_together`，避免标题孤立在页尾。
- 列表段落：固定行距 `20pt`，左缩进 `21pt`，悬挂缩进 `10.5pt`。
- 模板 metadata：`docx_template` 增加 `body_first_line_indent_pt`、`list_left_indent_pt`、`list_hanging_indent_pt`、`heading_keep_with_next`。

## 自动化测试

命令：

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q
```

结果：

```text
50 passed, 5 warnings
```

## 真实链路

执行链路：

```text
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

输出文件：

- Markdown：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.md`
- DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`
- JSON 记录：`docs/development/runs/run_20260611_docx_quality_p0_body_real_export.json`

## 验收结果

模板与版式：

- 模板：`sgcc_taichang_bid`
- 页面：A4
- 页边距：上 2.0cm、下 2.0cm、左 3.18cm、右 3.18cm
- 正文：宋体 10.5pt，固定行距 20pt，首行缩进 21pt
- 列表：固定行距 20pt，左缩进 21pt，悬挂缩进 10.5pt
- 标题：固定行距 20pt，`keep_with_next=true`
- 页眉：`河北泰昌电力器材科技有限公司投标文件`
- 字段刷新：LibreOffice 自动刷新成功

正文检查：

```json
{
  "all_body_samples_line_spacing_20pt": true,
  "all_body_samples_first_line_indent_21pt": true,
  "all_body_samples_no_extra_spacing": true,
  "all_heading_samples_keep_with_next": true,
  "all_heading_samples_no_first_line_indent": true,
  "all_list_samples_line_spacing_20pt": true,
  "all_list_samples_left_or_start_indent_21pt": true,
  "all_list_samples_hanging_indent_10_5pt": true,
  "max_consecutive_empty_paragraphs_in_body": 1
}
```

表格回归：

```json
{
  "table_count_gt_zero": true,
  "all_sample_tables_full_width": true,
  "all_sample_tables_fixed_layout": true,
  "all_sample_tables_repeat_header": true,
  "all_sample_tables_have_cell_margin": true,
  "all_sample_data_rows_no_first_line_indent": true,
  "all_sample_data_rows_line_spacing_16pt": true
}
```

清理检查：

```json
{
  "contains_mermaid_fence": false,
  "contains_internal_image_source": false,
  "contains_repeated_parent_title_pattern": false
}
```

兼容性说明：

- LibreOffice 刷新后会把列表缩进 XML 中的 `left` 规范化为 `start`，真实验收按 roundtrip 后的 XML 口径读取。
- 当前环境未安装 `mmdc`，Mermaid 仍记录 skipped；正式 DOCX 中未出现 Mermaid 源码块。

## 结论

本轮 P0“正文格式统一”已通过自动化回归和真实 DOCX 导出链路验证。当前 P0 中仍待处理的主要项是“封面字段结构化来源补齐”“目录稳定性验收”和最终综合“真实导出验收记录”。

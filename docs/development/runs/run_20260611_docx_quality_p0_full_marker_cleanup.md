# DOCX P0 全文格式标记清理真实导出记录

运行 ID：`run_20260611_docx_quality_p0_full_marker_cleanup`

日期：2026-06-11

项目 ID：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`

## 背景

客户在目录页发现黑色小方块后，又指出正文中也存在同类问题。该黑色小方块是 Word/WPS 在开启“显示格式标记”时，对 `keep lines together`、`keep with next`、`page break before` 等段落分页控制的可视化提示。虽然通常不会打印，但正式交付物中不应出现这种容易被误判为格式异常的标记。

## 修复范围

- 正文、标题、列表、目录均不再写入 `keepLines/keepNext/pageBreakBefore`。
- DOCX 保存后执行 XML 清理，覆盖 `word/document.xml` 和 `word/styles.xml`。
- LibreOffice 字段刷新后再次执行 XML 清理，避免 LibreOffice roundtrip 把内置样式的 `keepNext` 写回。
- 保留正文正式格式：宋体 10.5pt、固定行距 20pt、首行缩进 21pt。
- 保留列表正式格式：固定行距 20pt、左缩进 21pt、悬挂缩进 10.5pt。
- 保留标题正式格式：固定行距 20pt、不首行缩进。

## 自动化测试

命令：

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q
```

结果：

```text
51 passed, 5 warnings
```

## 真实链路

执行链路：

```text
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

输出文件：

- Markdown：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.md`
- DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`
- JSON 记录：`docs/development/runs/run_20260611_docx_quality_p0_full_marker_cleanup.json`

## 验收结果

全文格式标记计数：

```json
{
  "document_keepLines": 0,
  "document_keepNext": 0,
  "document_pageBreakBefore": 0,
  "styles_keepLines": 0,
  "styles_keepNext": 0,
  "styles_pageBreakBefore": 0
}
```

正文/标题/列表格式检查：

```json
{
  "all_body_samples_line_spacing_20pt": true,
  "all_body_samples_first_line_indent_21pt": true,
  "all_heading_samples_no_first_line_indent": true,
  "all_list_samples_line_spacing_20pt": true,
  "all_list_samples_left_or_start_indent_21pt": true,
  "all_list_samples_hanging_indent_10_5pt": true,
  "max_consecutive_empty_paragraphs_in_body": 1
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

字段刷新：

- LibreOffice 自动刷新成功。
- 目录页码、页脚页码和总页数字段已重新保存。
- `field_refresh.marker_cleanup.counts_after.keepLines=0`
- `field_refresh.marker_cleanup.counts_after.keepNext=0`
- `field_refresh.marker_cleanup.counts_after.pageBreakBefore=0`

## 结论

全文黑色方块对应的分页控制标记已清理完成。最终 DOCX 的 `word/document.xml` 与 `word/styles.xml` 均不再包含 `keepLines/keepNext/pageBreakBefore`，同时正文、标题、列表和目录的基础格式保持稳定。

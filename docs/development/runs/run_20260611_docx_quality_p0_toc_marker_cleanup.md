# DOCX P0 目录格式标记修复真实导出记录

运行 ID：`run_20260611_docx_quality_p0_toc_marker_cleanup`

日期：2026-06-11

项目 ID：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`

## 背景

客户在 Word/WPS 中查看目录页时，发现目录左侧出现竖向黑色小方块。该现象发生在显示格式标记时，属于段落分页控制标记，不是目录页码刷新失败，也不是会打印到纸面上的正文字符。但在正式交付物中，这种观感容易被误认为格式异常，必须修复。

## 原因

上一轮“正文格式统一”中，为了避免正文段落孤行和段落被拆散，将 `keep lines together` 设到了 `Normal` 样式。目录条目也使用 `Normal` 样式，因此继承了该分页控制。Word/WPS 在显示格式标记时，会在这类段落左侧显示黑色方块。

## 修复范围

- 移除 `Normal` 样式上的全局 `keep_together / keepLines`。
- 正文段落继续通过直接段落格式设置 `keep_together` 和 `widow_control`。
- 标题段落继续通过直接段落格式设置 `keep_with_next` 和 `keep_together`。
- 目录条目继续保留点引导线、右对齐页码和 18pt 行距，但不继承正文分页控制。

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
- JSON 记录：`docs/development/runs/run_20260611_docx_quality_p0_toc_marker_cleanup.json`

## 验收结果

目录格式标记检查：

```json
{
  "toc_entry_count_gt_zero": true,
  "normal_style_has_no_keep_lines": true,
  "normal_style_has_no_keep_next": true,
  "all_toc_samples_have_no_direct_keep_lines": true,
  "all_toc_samples_have_no_direct_keep_next": true,
  "all_body_samples_still_keep_lines": true,
  "all_body_samples_line_spacing_20pt": true,
  "all_body_samples_first_line_indent_21pt": true
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

## 结论

目录左侧黑色小方块的来源已确认并修复。目录条目不再继承正文分页控制；正文段落和标题段落仍保留必要的分页控制，正式导出链路验证通过。

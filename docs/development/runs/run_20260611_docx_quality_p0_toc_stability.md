# DOCX P0 目录稳定性真实导出验收记录

运行时间：2026-06-11

Run ID：`run_20260611_docx_quality_p0_toc_stability`

项目 ID：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`

## 验收目标

本轮收尾验证 P0 目录稳定性，重点检查正式 DOCX 是否满足以下要求：

- 目录标题唯一，且位于正文标题之前；
- 目录条目存在，层级不超过 3-4 级；
- 目录页码右对齐，并使用点引导线；
- 目录页码使用字段，且经 LibreOffice 刷新后得到真实页码；
- 目录条目不首行缩进，不出现黑色方块格式标记；
- 目录和正文标题不重复父章节前缀；
- Mermaid 源码、内部图片来源/匹配依据、重复父标题前缀继续保持清理状态。

## 真实链路

执行真实项目导出链路：

```text
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

输出文件：

```text
outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx
```

结构化结果：

```text
docs/development/runs/run_20260611_docx_quality_p0_toc_stability.json
```

## 自动化回归

执行命令：

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q
```

结果：

```text
52 passed, 5 warnings
```

## 真实导出结果

- 模板：`sgcc_taichang_bid`
- 页眉：`河北泰昌电力器材科技有限公司投标文件`
- 页面：A4，页边距上/下 `2.0cm`，左/右 `3.18cm`
- 字段刷新：`field_refresh.status=refreshed`
- 目录标题位置：`toc_title_indexes=[12]`，首个正文标题索引 `first_heading_index=79`
- 目录条目数：`toc_entry_count=7`
- 目录层级：`toc_level_counts={"1": 7}`，最大层级 `toc_max_level=1`
- 目录页码范围：`4-73`
- 图片转换：`found/inserted/skipped/failed=24/24/0/0`
- Mermaid：`found/inserted/skipped=1/0/1`，当前环境缺少 `mmdc` 时跳过源码输出，正式 DOCX 不保留 Mermaid 源码块

## 验收项

| 检查项 | 结果 |
| --- | --- |
| 目录标题唯一 | 通过 |
| 目录标题位于正文标题之前 | 通过 |
| 目录条目存在 | 通过 |
| 目录最大层级不超过 4 级 | 通过 |
| 目录条目具备点引导线 | 通过 |
| 目录条目具备 PAGEREF 字段 | 通过 |
| 目录条目已刷新出真实页码 | 通过 |
| 目录条目固定行距 18pt | 通过 |
| 目录条目无首行缩进 | 通过 |
| 目录条目无黑色方块格式标记 | 通过 |
| 目录无重复父章节前缀 | 通过 |
| `word/document.xml` 无 `keepLines/keepNext/pageBreakBefore` | 通过 |
| `word/styles.xml` 无 `keepLines/keepNext/pageBreakBefore` | 通过 |
| LibreOffice 字段刷新成功 | 通过 |

补充说明：LibreOffice 刷新后未保留 `w:updateFields` 设置，因此结构化检查里 `update_fields_enabled=false`。这不作为阻断项，因为本轮验收以刷新后的真实页码和 `field_refresh.status=refreshed` 为准，目录条目已经包含 `PAGEREF` 字段和刷新后的页码。

## 清理项复核

- `contains_mermaid_fence=false`
- `contains_internal_image_source=false`
- `contains_repeated_parent_title_pattern=false`
- `document_keepLines=0`
- `document_keepNext=0`
- `document_pageBreakBefore=0`
- `styles_keepLines=0`
- `styles_keepNext=0`
- `styles_pageBreakBefore=0`

## 结论

P0 目录稳定性验收通过。目录页作为正式交付物的可读性、页码刷新、层级控制、点引导线、黑方块格式标记清理和标题去重均已完成真实链路验证。

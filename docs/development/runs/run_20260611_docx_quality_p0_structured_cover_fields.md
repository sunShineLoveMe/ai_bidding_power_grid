# DOCX P0 封面字段结构化来源真实导出验收记录

运行时间：2026-06-11

Run ID：`run_20260611_docx_quality_p0_structured_cover_fields`

项目 ID：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`

## 验收目标

本轮处理 `封面字段结构化来源补齐`，目标是让正式 DOCX 封面优先使用用户上传招标文件解析后的结构化字段，而不是从生成后的 Markdown 正文反向猜测。

## 实现范围

- 新增招标文件项目字段抽取模块：`backend/parsing/tender_metadata.py`。
- 上传解析入库阶段把抽取结果写入 `bid_analysis.project_meta.cover_fields`、`cover_field_sources`、`cover_field_missing`。
- 同步高置信字段到 `bid_projects` 基础列：`project_name`、`project_no`、`tender_unit`、`agency`。
- DOCX 导出阶段从 `project_meta.cover_fields` 传入 `convert_md_to_word`，并优先覆盖 Markdown 兜底字段。
- OnlyOffice 预览导出和 Celery 正式导出均接入同一结构化封面字段。
- 增加空字段/串联字段保护：当 `项目名称：` 后面紧跟 `招标编号：`、`分标编号：` 等字段名时，不把字段名误判为字段值。

## 自动化回归

执行命令：

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_native_parse_ingestion.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q
```

结果：

```text
57 passed, 5 warnings
```

新增覆盖：

- 招标文件文本抽取项目名称、招标编号、分标编号、分标名称、包号、包名称、招标人、招标代理机构；
- 原生解析链路把结构化封面字段写入 `project_meta`；
- 导出报告携带 `cover_fields` 和 `cover_field_sources`；
- DOCX 封面优先使用结构化字段覆盖 Markdown 兜底字段；
- 空值字段后接其他字段名时不误抽。

## 真实链路

执行真实项目导出链路：

```text
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

输出文件：

```text
outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx
```

结构化结果：

```text
docs/development/runs/run_20260611_docx_quality_p0_structured_cover_fields.json
```

## 真实导出结果

- 模板：`sgcc_taichang_bid`
- 字段刷新：`field_refresh.status=refreshed`
- 图片转换：`found/inserted/skipped/failed=24/24/0/0`
- Mermaid：`found/inserted/skipped=1/0/1`，当前环境缺少 `mmdc` 时跳过源码输出，正式 DOCX 不保留 Mermaid 源码块
- 封面字段来源：`uploaded_tender_structured_extract`
- 封面字段：
  - `项目名称=国网辽宁电力2025年第三次物资协议库存招标采购`
  - `文件类型=投标文件`
  - `招标编号=2225AC`
- 当前历史解析文本缺失可靠字段：
  - `分标编号`
  - `分标名称`
  - `包号`
  - `包名称`

## 验收项

| 检查项 | 结果 |
| --- | --- |
| 封面使用结构化招标编号 `2225AC` | 通过 |
| 封面使用结构化项目名称 | 通过 |
| 缺失分标/包字段被记录，不编造 | 通过 |
| DOCX 模板 metadata 记录 `cover_fields` | 通过 |
| LibreOffice 字段刷新成功 | 通过 |
| DOCX XML 无黑色方块格式标记 | 通过 |
| DOCX 不保留 Mermaid 源码块 | 通过 |

## 结论

`封面字段结构化来源补齐` 已完成。后续新上传招标文件时，解析链路会把可识别字段沉淀到项目结构化 metadata；正式 DOCX 封面优先读取该结构化字段，字段缺失时记录缺失并保留后续人工复核空间。

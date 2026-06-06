# 2026-06-05 DOCX 导出格式 P0 记录

## 背景

真实山西招标文件全流程跑通后，用户下载生成 DOCX，反馈标书文件与格式观感不规整。该问题直接影响客户第一印象，且可能触发投标文件形式评审风险，因此提升为 P0。

## 依据

- 原招标文件要求投标文件按第六章“投标文件格式”编写。
- 第六章说明电子商务平台投标文件制作格式以平台要求为准。
- 形式评审否决情形包含“投标文件未按招标文件规定的格式填写，内容不全或者关键字迹模糊无法辨认”。
- 本次主招标文件中暂未发现明确写死“目录宋体几号、正文宋体几号”的字体字号条款；没有明确要求时，应按投标文件惯例和国网/电力行业默认模板输出。

## 当前导出文件

- 项目 ID：`7dfcc318-c1f8-465d-abc3-d47ef0e355e7`
- 导出任务 ID：`baeaf101-3179-4ef5-ad9d-78fb0f1e9ac2`
- DOCX：`outputs/Guo_Wang_Shan_Xi_Dian_Li_2026Nian_Di_Er_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Gong_Kai_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网山西电力2026年第二次物资协议库存公开招标采购招标文件.docx`
- LibreOffice 字段刷新：成功，页码字段刷新不是本次主要问题。

## 当前模板观察

`backend/export/md_to_word.py` 当前默认：

- 正文：仿宋，小四 `12pt`，固定行距 `28pt`。
- 标题：黑体，一级 `18pt`、二级 `16pt`、三级 `15pt`、四级 `12pt`。
- 页眉：宋体 `9pt`，项目名 + “投标文件”。
- 页脚：宋体 `9pt`，“第 X 页，共 Y 页”。
- 目录：代码生成，LibreOffice 刷新页码。

这只是基础 Word 输出模板，不足以作为正式投标文件交付模板。

## 已同步任务状态

已在 `docs/section-generation-production-remediation-todo.md` 新增：

- `P0 | DOCX 导出交付观感与格式模板整改`

2026-06-05 后续已完成基础版整改：

- 默认模板 ID：`sgcc_power_grid`。
- 正文默认改为宋体小四 `12pt`、固定 `28pt` 行距。
- 表格默认改为宋体 `10.5pt`，表头加粗，表格居中并启用自适应。
- 页眉增加长度保护，避免长项目名称溢出。
- 页面参数、正文/表格字体字号、页边距、页眉页脚距离改为环境变量可配置。
- `convert_md_to_word(..., return_report=True)` 增加 `template` 元数据。
- Celery DOCX 导出任务将 `docx_template` 写入 `bid_export_tasks.metadata`。
- 已重新生成山西真实项目当前下载 DOCX 并刷新页码字段。

## 验证

命令：

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_celery_export_tasks.py tests/test_smoke.py tests/test_api_sections.py -q
PYTHONPATH=. .venv/bin/python -m py_compile backend/export/md_to_word.py backend/tasks/export_tasks.py
```

结果：

- 41 passed。
- `py_compile` 通过。
- 山西真实导出 Markdown 副本结构化检查通过：正文宋体 `12pt`、A4、左右边距 `3.18cm`、页眉长度正常。

## 后续验收重点

- 封面、目录、正文、表格、页眉页脚、页码连续性。
- 默认字体字号策略：没有招标方明确要求时，采用投标文件惯例。
- 招标文件第六章格式表单保真，避免 Markdown 转换破坏签章和表格。
- 导出 metadata 记录模板、字体、字号、页边距、刷新状态和格式告警。

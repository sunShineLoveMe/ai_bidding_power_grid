# 2026-06-09 标书文档导出质量 P0 第一阶段真实验证

## 背景

标书 DOCX/PDF 是客户最终交付物，本次按 P0 质量专项推进“封面正式字段补齐 + 真实导出链路验证”。验证使用泰昌 MVP 真实项目，不使用 mock。

## 改动范围

- 新增 `docs/development/docx-bid-export-quality-todo.md`，作为文档编写与正式导出质量专项待办清单。
- `AGENTS.md` 新增 DOCX 正式导出 SOP，要求后续改动走真实链路并同步验证记录。
- `backend/export/md_to_word.py` 新增封面字段提取：
  - `文件类型`
  - `招标编号`
  - `分标编号`
  - `分标名称`
  - `包号`
  - `包名称`
- `docx_template` metadata 新增 `cover_fields`，便于导出任务和验收报告追踪。

## 真实导出链路

项目：

```text
4bc3ee73-9ec5-4184-aafd-eaede9f90798
```

执行链路：

```text
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

输出文件：

```text
outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx
```

结构化验证报告：

```text
docs/development/runs/run_20260609_docx_quality_p0_real_export.json
```

## 验证结果

| 项 | 结果 |
| --- | --- |
| 模板 ID | `sgcc_taichang_bid` |
| 封面标题 | `国网辽宁电力2025年第三次物资协议库存招标采购投标文件` |
| 封面文件类型 | `投标文件` |
| 封面招标编号 | `2225AC` |
| 封面投标人 | `河北泰昌电力器材科技有限公司` |
| 目录标题 | `目  录` |
| 页面 | A4 |
| 页边距 | 上下 `2.0cm`，左右 `3.18cm` |
| 正文字体 | 宋体 `10.5pt` |
| 表格数量 | 60 |
| 图片候选 | 300 个泰昌资产 |
| 自动选图 | 24 个 |
| 图片插入 | found 24 / inserted 24 / skipped 0 / failed 0 |
| 字段刷新 | LibreOffice refreshed |
| 手动刷新要求 | false |

## 回归测试

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_celery_export_tasks.py -q
```

结果：

```text
30 passed, 5 warnings
```

## 剩余 P0 风险

- 当前真实项目 Markdown 可确定 `招标编号`，但 `分标编号`、`分标名称`、`包号/包名称` 未在生成 Markdown 的全局封面字段中稳定出现；后续应从项目解析 metadata 或招标文件结构化结果补齐，而不是从正文里猜。
- 表格已能生成并统计数量，但尚未做视觉级“是否越界/跨页表头重复”的自动预检。
- 图片题注仍沿用当前资产 caption 规则，后续需升级为正式 “图 N 资料名称” 格式。

# 2026-06-06 泰昌 MVP DOCX 模板与图文导出 P0 回归

## 背景

用户反馈此前下载的标书 DOCX 仍像“招标文件”，且目录、间距、页眉页脚、正文格式与客户提供参考模板不一致。该问题影响客户第一印象和正式投标文件交付观感。

## 本次整改

- 导出标题、文件名、封面、页眉默认改为泰昌投标人口径。
- 泰昌全称固定为 `河北泰昌电力器材科技有限公司`，可通过 `DOCX_BIDDER_FULL_NAME` 覆盖。
- `/download-docx` 未显式传参时默认 `withImages=true`，避免图文导出被静默降级。
- DOCX 模板 ID 改为 `sgcc_taichang_bid`。
- 页面参数按客户/国网参考文件抽取结果调整：
  - A4；
  - 上下边距 `2.0cm`；
  - 左右边距 `3.18cm`；
  - 正文宋体 `10.5pt`；
  - 正文固定行距 `20pt`；
  - 目录标题 `目  录`，黑体 `22pt`；
  - 目录正文宋体 `10.5pt`，右对齐页码和点引导线。
- 新增独立封面页，包含项目投标文件标题、投标人和日期。
- 修复真实大纲从二级开始时导出 `0.1` 的编号问题，改为栈式压平。
- 导出图片资产筛选收紧到泰昌企业事实资产，排除辽宁招标要求和河北豪乾参考稿。
- 自动插图整份上限统一为 24 张，且同一资产整份 DOCX 只插入一次。
- 导出阶段移除模型正文中未入库或不可解析的 Markdown 图片引用，避免假图片占位进入 Word。
- 修复 `list_knowledge_assets()` 未导入导致图文导出降级为无图的问题。

## 真实验证

项目：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`

输出文件：

```text
outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx
```

验证报告：

```text
docs/development/runs/run_20260606_taichang_docx_template_real_export.json
```

关键结果：

| 项 | 结果 |
| --- | --- |
| 文档标题 | `国网辽宁电力2025年第三次物资协议库存招标采购投标文件` |
| 封面投标人 | `河北泰昌电力器材科技有限公司` |
| 页眉 | `河北泰昌电力器材科技有限公司投标文件` |
| 目录首项 | `1. 投标函及投标函附录` |
| 页面 | A4 |
| 页边距 | 上下 `2.0cm`，左右 `3.18cm` |
| 正文字体 | 宋体 `10.5pt` |
| 图片候选 | 242 个泰昌资产 |
| 自动选图 | 24 个 |
| 唯一图片资产 | 24 个 |
| 图片插入 | found 24 / inserted 24 / skipped 0 / failed 0 |
| 目录/页码刷新 | LibreOffice refreshed |

## 回归命令

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_celery_export_tasks.py tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q
```

结果：

```text
44 passed, 5 warnings
```

## 剩余关注

- 当前仍是代码内置模板，不是直接套打客户 PDF 模板；后续若客户提供可编辑 Word 模板，应进入 `template_docx` 模式。
- 本次真实项目仍是此前 30 章节压测项目，不代表完整 74 章节全文标书已经全部重写完成。

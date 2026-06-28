# 2026-06-28 新疆参考分册 DOCX 格式稳定性修复

## 背景

客户反馈技术标/商务标导出观感不稳定，主要问题包括：

- 封面底部投标人、法定代表人/授权代表、日期区域与新疆参考投标文件不一致；
- 正文中出现旧模板编号，例如 `【5.1 概述】`、`【5.2 技术方案与产品性能响应】`；
- 正文小标题编号与目录章节编号不一致；
- 正式 DOCX 中残留 `【】`、编写要点、需准备资料、投标确认清单、插图建议等生成痕迹。

## 修复范围

- `backend/api/routes.py`
  - 导出 Markdown 组装阶段增加正式正文清洗：
    - 移除 `编写要点`、`需准备资料`、`风险与复核`、`投标确认清单` 等内部提示块；
    - 将历史正文中的旧编号标题按当前导出章节编号重排；
    - 将正文内部小标题写为非 TOC 内部标记，避免污染 Word 目录；
    - 移除正式可见文本中的 `【】`、`已确认/已完成` 状态标记和插图建议。
- `backend/export/md_to_word.py`
  - 技术标/商务标新疆参考 profile 下，封面改为 `投标文件 + 文件类别：技术/商务`；
  - 投标人行改为 `投标人：河北泰昌电力器材科技有限公司（盖单位章）`；
  - 签字行改为 `法定代表人（单位负责人）或其授权代表人：       （签字）`；
  - 技术/商务分册正文官方章节标题按新疆参考稿收敛为宋体 `12pt` 左对齐加粗；
  - 正文内部小标题按宋体 `12pt` 输出，不进入 Word 目录。
- `tests/test_docx_export.py`
  - 增加旧编号、`【】`、提示块清洗回归；
  - 更新新疆参考分册封面和标题样式断言。

## 真实链路验证

项目：`5d064d0a-29ba-41bb-ab07-9d51e6c9e084`

链路：

```bash
build_project_bid_markdown(volume_type=technical/business, with_images=false)
-> convert_md_to_word(return_report=true, cover_fields=report.cover_fields)
-> refresh_docx_fields_with_soffice
```

技术标输出：

- Markdown：`outputs/5d064d0a/泰昌_2225AC_包1_技术投标文件_20260628.md`
- DOCX：`outputs/5d064d0a/泰昌_2225AC_包1_技术投标文件_20260628.docx`
- 模板：`technical_bid_standard / formal_bid_xinjiang_sgcc_reference`
- 字段刷新：`refreshed`
- 检查结果：
  - `【5.1 概述】`：`0`
  - Markdown `【`：`0`
  - DOCX `【`：`0`
  - 编写提示/插图建议残留：`0`
  - `文件类别：技术`：`1`
  - `投标人：河北泰昌电力器材科技有限公司（盖单位章）`：`1`
  - `法定代表人（单位负责人）或其授权代表人：       （签字）`：`1`
  - 官方正文标题 `1. 技术评分支撑材料`：宋体 `12pt`
  - 正文小标题 `1.1 概述`：宋体 `12pt`

商务标输出：

- Markdown：`outputs/5d064d0a/泰昌_2225AC_包1_商务投标文件_20260628.md`
- DOCX：`outputs/5d064d0a/泰昌_2225AC_包1_商务投标文件_20260628.docx`
- 模板：`business_bid_standard / formal_bid_xinjiang_sgcc_reference`
- 字段刷新：`refreshed`
- 检查结果：
  - Markdown `【`：`0`
  - DOCX `【`：`0`
  - 编写提示/插图建议残留：`0`
  - `文件类别：商务`：`1`
  - `投标人：河北泰昌电力器材科技有限公司（盖单位章）`：`1`
  - `法定代表人（单位负责人）或其授权代表人：       （签字）`：`1`

## 自动化回归

```bash
.venv/bin/python -m py_compile backend/api/routes.py backend/export/md_to_word.py
.venv/bin/python -m pytest tests/test_docx_export.py -q
```

结果：`57 passed, 1 warning`。

## 结论

本次修复已将技术标/商务标导出收敛到新疆参考分册风格，并在导出层兜底清理历史正文脏标题和内部提示。后续若重新生成正文，仍建议同步优化正文生成 prompt，减少源数据中继续产生旧章节号和投标确认清单。

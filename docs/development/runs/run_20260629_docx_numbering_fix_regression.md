# 2026-06-29 商务标/完整投标文件正文编号错乱修复回归

## 背景

用户反馈本地 AI 标书完成后，分别导出技术标、商务标、完整投标文件：

- 技术标正文项目编号正常；
- 商务标正文中项目、章节编号错乱；
- 完整投标文件正文同商务标一样出现章节序号混乱。

本次定位结果：问题不是 Word 随机显示异常，而是导出前 Markdown 已经混入多套标题系统。商务标和完整投标文件同时存在正式章节树、模型正文标题、历史模板标题和 `BID_BODY_SUBHEADING` 注释型标题，导出器又把这些正文标题继续渲染进 Word，导致出现 `2.10.1.1.2 投标函`、`6.1.2.1.1.1.1 投标函` 等深层串号。

## 修复范围

- `backend/api/routes.py`
  - 新增 `BODY_SUBHEADING_COMMENT_RE` 和正文标题泛化过滤集。
  - `_normalize_body_outline_lines` 统一处理 Markdown 标题、加粗伪标题、旧模板编号和 `BID_BODY_SUBHEADING` 注释。
  - 正文内伪标题只作为当前正式章节下一级小标题，不再保留历史完整父级路径。
  - 完整投标文件同时包含商务与技术分册时，启用 `sgcc_mixed` 编号，使完整文件主标题与技术标/商务标分册编号策略一致。
- `backend/export/md_to_word.py`
  - 带显式数字编号的正文小标题不再因包含“投标函/承诺函/偏差表”等关键词被误判为居中正式表单标题。
- `tests/test_docx_export.py`
  - 增加旧 `BID_BODY_SUBHEADING` 重新编号与泛化分册标题移除用例。
  - 增加完整投标文件商务+技术同时存在时启用 `sgcc_mixed` 的用例。
  - 调整正文伪标题预期：正文小标题不再内部嵌套，正式目录层级仅来自 `bid_sections`。

## 验证命令

```bash
.venv/bin/python -m py_compile backend/api/routes.py backend/export/md_to_word.py tests/test_docx_export.py
.venv/bin/python -m pytest tests/test_docx_export.py -q
```

结果：

- `py_compile`：通过；
- `tests/test_docx_export.py`：`63 passed, 1 warning`。

## 真实导出回测

项目：

```text
ae6b7da5-a7b3-473f-a28f-13990ead304e
```

真实链路：

```text
build_project_bid_markdown(volume_type, with_images=true)
-> convert_md_to_word(return_report=true, cover_fields=...)
-> refresh_docx_fields_with_soffice
```

输出目录：

```text
output/docx-numbering-fix-regression/ae6b7da5/
```

详细 JSON：

```text
output/docx-numbering-fix-regression/run_20260629_docx_numbering_fix_regression.json
```

### 技术标

- Markdown：`output/docx-numbering-fix-regression/ae6b7da5/泰昌_2225AC_包1_技术投标文件_20260629_图文.md`
- DOCX：`output/docx-numbering-fix-regression/ae6b7da5/泰昌_2225AC_包1_技术投标文件_20260629_图文.docx`
- 模板：`technical_bid_standard`
- 编号策略：`sgcc_mixed`
- 字段刷新：`refreshed`
- 深层商务表单串号：`0`
- 泛化分册小标题：`0`
- `2.10.1.1.2 投标函`：`0`

标题样本：

```text
# （一）技术评分支撑材料
# （二）技术响应文件
## 1. 技术偏差表
## 2. 专项投标文件
## 3. 业绩文件
### 3.1 平台业绩汇总查询截图
```

### 商务标

- Markdown：`output/docx-numbering-fix-regression/ae6b7da5/泰昌_2225AC_包1_商务投标文件_20260629_图文.md`
- DOCX：`output/docx-numbering-fix-regression/ae6b7da5/泰昌_2225AC_包1_商务投标文件_20260629_图文.docx`
- 模板：`business_bid_standard`
- 编号策略：`sgcc_mixed`
- 字段刷新：`refreshed`
- 深层商务表单串号：`0`
- 泛化分册小标题：`0`
- `2.10.1.1.2 投标函`：`0`

标题样本：

```text
# （一）投标函及法定格式文件
## 1. 投标函及投标函附录
## 2. 法定代表人身份证明及授权委托书
## 3. 投标保证金及基本账户资料
# （二）商务响应文件
## 1. 商务偏差表
```

### 完整投标文件

- Markdown：`output/docx-numbering-fix-regression/ae6b7da5/泰昌_2225AC_包1_投标文件_20260629_图文.md`
- DOCX：`output/docx-numbering-fix-regression/ae6b7da5/泰昌_2225AC_包1_投标文件_20260629_图文.docx`
- 模板：`formal_bid_standard`
- 编号策略：`sgcc_mixed`
- 字段刷新：`refreshed`
- 深层商务表单串号：`0`
- 泛化分册小标题：`0`
- `2.10.1.1.2 投标函`：`0`

标题样本：

```text
# （一）投标函及法定格式文件
## 1. 投标函及投标函附录
## 2. 法定代表人身份证明及授权委托书
## 3. 投标保证金及基本账户资料
# （二）商务响应文件
## 1. 商务偏差表
```

## 结论

本轮修复后，技术标、商务标、完整投标文件三份真实 DOCX 均完成字段刷新，且导出前 Markdown 与导出后 DOCX 均未再检出用户截图中对应的深层错乱编号。无需重新生成正文即可在导出层稳定修正该类历史/模型脏标题；后续新生成正文也会被同一导出规则兜底治理。

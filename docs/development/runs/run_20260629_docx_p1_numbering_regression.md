# DOCX P1 国网混合编号整改真实回归记录

运行日期：2026-06-29

## 1. 验证目标

本次验证覆盖 `docs/development/docx-export-format-priority-todo.md` 中：

- `P1-3` 国网混合编号模板设计。

目标是让技术标/商务标分册目录和正文标题编号更接近国网正式投标文件常见结构，避免完全依赖模型自由生成编号：

- 一级：`（一）`
- 二级：`1.`
- 三级：`1.1`
- 四级：`1.1.1`
- 五级：`1）`

## 2. 代码口径

仅 `technical_bid_standard` 与 `business_bid_standard` 启用：

```text
section_numbering_style=sgcc_mixed
```

默认 `formal_bid_standard` 仍使用原有 `decimal_outline` 编号，避免影响完整/通用投标文件。

本次同时修正旧编号清理边界：

- 清理模型或来源标题中的 `（1）`、`(1)`、`1）` 等旧编号，避免叠加为 `10.3 （1）营业执照信息`；
- 保留 `9985-500143417-00001` 等物料编码/技术规范编码，不再误删开头数字。

## 3. 验证命令

```bash
.venv/bin/python -m py_compile backend/api/routes.py backend/export/md_to_word.py tests/test_docx_export.py
.venv/bin/python -m pytest tests/test_docx_export.py -q
.venv/bin/python -m pytest tests/test_celery_export_tasks.py -q
```

真实导出链路：

```text
build_project_bid_markdown
-> convert_md_to_word
-> refresh_docx_fields_with_soffice
-> ensure_docx_table_header_repeat
-> LibreOffice PDF export
-> pdftoppm 目录页截图
```

验证项目：

```text
a1d853bc-ca4e-43b4-bbea-256f561c8a3d
```

## 4. 自动化测试结果

- `py_compile`：通过；
- `tests/test_docx_export.py`：`59 passed, 1 warning`；
- `tests/test_celery_export_tasks.py`：`11 passed, 1 warning`。

新增/强化的单测断言：

- 默认 `decimal_outline` 编号保持不变；
- `sgcc_mixed` 支持一级 `（一）`、二级 `1.`、三级 `1.1`、四级 `1.1.1`、五级 `1）`；
- 正文内模型旧编号按当前导出章节编号重写；
- 不产生 `.0` 编号段；
- 不截断 `9985-...` 等物料/技术规范编码；
- 清理旧的 `(1)` / `（1）` 标题前缀。

## 5. 真实导出结果

技术标：

- DOCX：`outputs/a1d853bc/泰昌_2225AC_包1_技术投标文件_20260629_图文.docx`
- PDF：`output/docx-p1-numbering-regression/泰昌_2225AC_包1_技术投标文件_20260629_图文.pdf`
- 目录页截图：`output/docx-p1-numbering-regression/technical_toc.png`
- PDF 页数：`349`
- 字段刷新：`refreshed`
- 图片：选中 `9`，插入 `9`，失败 `0`

技术标目录样本：

```text
（一）技术评分支撑材料
（二）技术响应文件
1. 技术偏差表
2. 专项投标文件
3. 业绩文件
3.1 平台业绩汇总查询截图
3.2 资质业绩凭证单
3.3 新增业绩合同
3.3.1 产品购销合同
3.3.2 同类项目业绩证明材料
4. 技术特性参数表
4.1 技术特性参数明细（按物料编码）
```

商务标：

- DOCX：`outputs/a1d853bc/泰昌_2225AC_包1_商务投标文件_20260629_图文.docx`
- PDF：`output/docx-p1-numbering-regression/泰昌_2225AC_包1_商务投标文件_20260629_图文.pdf`
- 目录页截图：`output/docx-p1-numbering-regression/business_toc.png`
- PDF 页数：`193`
- 字段刷新：`refreshed`
- 图片：选中 `5`，插入 `5`，失败 `0`

商务标目录样本：

```text
（一）投标函及法定格式文件
1. 投标函及投标函附录
2. 法定代表人身份证明及授权委托书
3. 投标保证金及基本账户资料
（二）商务响应文件
1. 商务偏差表
2. 投标保证保险
3. 投标保证保险（电缆保护管 CPVC）
4. 投标保证保险（电缆保护管 MPP）
5. 补充文件
6. 投标保证金
6.1 保险购买凭证
```

## 6. 审计结论

技术标和商务标均满足：

- `section_numbering_style=sgcc_mixed`；
- 目录和正文标题均出现一级 `（一）/（二）`；
- 二级编号在每个一级章节下重新从 `1.` 开始；
- 三级/四级编号稳定为点号结构；
- 未出现 `.0` 编号段；
- 未出现旧 `(1)` / `（1）` 叠加编号；
- 未截断物料/技术规范编码；
- 目录页码字段刷新成功，PDF 目录页点引导线正常。

## 7. 图片数量说明

本轮真实导出图片数量仍为：

- 技术标：`9/9`；
- 商务标：`5/5`。

这表示自动选中的正式图片均成功插入，不是插入失败。数量偏少主要来自当前正式资产门禁和内容边界：

- 只允许泰昌企业事实资产自动进入正式 DOCX；
- 非 `formal_bid_ready`、解析中间图、辽宁招标资料图片、河北豪乾参考稿图片不会自动插入；
- 当前逻辑按章节证据类型、库类型、分册适配和去重保守选图；
- 检验报告整页、证书整页、合同/中标通知书附件级批量插入仍属于 P2/独立能力。

因此不建议仅通过调大 `DOCX_TOTAL_ASSET_IMAGE_LIMIT` 或 `DOCX_MAX_IMAGES` 解决观感问题。更合理的后续工作是补充/清洗泰昌正式图片资产、完善中文标签与适用章节，并在 P2 实现附件级整页插入策略。

## 8. 遗留说明

本次只收口编号模板，不处理以下问题：

- 技术标仍有 `16` 处待补充/待确认占位；
- 商务标仍有 `14` 处待补充/待确认占位；
- 附件级图片/报告插入策略仍在 P2；
- 更彻底的 `reference_outline` 结构化模板规则仍在 `P1-4`。

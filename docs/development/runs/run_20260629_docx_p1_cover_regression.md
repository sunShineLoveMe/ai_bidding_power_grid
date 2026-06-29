# DOCX P1 封面观感整改真实回归记录

运行日期：2026-06-29

## 1. 验证目标

本次验证覆盖 `docs/development/docx-export-format-priority-todo.md` 中：

- `P1-1` 技术标/商务标封面字号校准；
- `P1-2` 招标编号封面位置优化。

整改目标不是单纯放大字号，而是让技术标/商务标分册封面更接近客户提供的新疆正式中标参考稿观感：项目名称、招标编号、`投标文件` 主标题、分标/包号/文件类别、投标人、签字和日期应形成正式标书封面层级。

## 2. 代码口径

仅 `technical_bid_standard` 与 `business_bid_standard` 启用 `cover_layout.style=sgcc_reference_volume_cover`：

- 项目名：宋体 `18pt` 加粗；
- 招标编号：位于项目名下方、`投标文件` 上方，宋体 `18pt` 加粗；
- 主标题 `投标文件`：宋体 `36pt` 加粗；
- 分标编号、分标名称、`包    号`、包名称、文件类别：宋体 `14pt` 加粗；
- 投标人：宋体 `16pt` 加粗；
- 法定代表人/授权代表签字行：宋体 `15pt` 加粗；
- 日期：宋体 `16pt` 加粗；
- `formal_bid_standard` 通用模板不启用该封面布局，避免影响完整/通用投标文件口径。

## 3. 验证命令

```bash
.venv/bin/python -m py_compile backend/export/md_to_word.py tests/test_docx_export.py
.venv/bin/python -m pytest tests/test_docx_export.py -q
.venv/bin/python -m pytest tests/test_celery_export_tasks.py -q
curl -s http://127.0.0.1:3012/api/ready | python3 -m json.tool
```

真实导出链路：

```text
build_project_bid_markdown
-> convert_md_to_word
-> refresh_docx_fields_with_soffice
-> ensure_docx_table_header_repeat
-> LibreOffice PDF export
-> pdftoppm 首页截图
```

验证项目：

```text
a1d853bc-ca4e-43b4-bbea-256f561c8a3d
```

## 4. 自动化测试结果

- `py_compile`：通过；
- `tests/test_docx_export.py`：`57 passed, 1 warning`；
- `tests/test_celery_export_tasks.py`：`11 passed, 1 warning`；
- `/api/ready`：`status=ok`，数据库、Redis、模型配置、存储、Celery 均为 `ok`。

新增/强化的单测断言：

- 招标编号必须位于 `投标文件` 主标题之前；
- 技术/商务 profile 报告必须包含 `cover_layout.style=sgcc_reference_volume_cover`；
- 封面字段采用宋体，并校验 `18/36/14/16/15pt` 等关键字号；
- 封面关键字段加粗；
- `包号` 在参考分册封面中显示为 `包    号`；
- 仍禁止复用新疆参考稿企业名称、分标编号等事实内容。

## 5. 真实导出结果

技术标：

- DOCX：`outputs/a1d853bc/泰昌_2225AC_包1_技术投标文件_20260629_图文.docx`
- PDF：`output/docx-p1-cover-regression/泰昌_2225AC_包1_技术投标文件_20260629_图文.pdf`
- 首页截图：`output/docx-p1-cover-regression/technical_cover.png`
- PDF 页数：`349`
- 字段刷新：`refreshed`
- 图片：选中 `9`，插入 `9`，失败 `0`
- 表格：`110`

技术标封面顺序审计：

```text
国网辽宁电力2025年第三次物资协议
库存招标采购
招标编号：2225AC
投标文件
包    号：包1
包名称：包1：电缆保护管CPVC、电缆保护管MPP
文件类别：技术
投标人：河北泰昌电力器材科技有限公司（盖单位章）
法定代表人（单位负责人）或其授权代表人：       （签字）
2026年06月29日
```

商务标：

- DOCX：`outputs/a1d853bc/泰昌_2225AC_包1_商务投标文件_20260629_图文.docx`
- PDF：`output/docx-p1-cover-regression/泰昌_2225AC_包1_商务投标文件_20260629_图文.pdf`
- 首页截图：`output/docx-p1-cover-regression/business_cover.png`
- PDF 页数：`193`
- 字段刷新：`refreshed`
- 图片：选中 `5`，插入 `5`，失败 `0`
- 表格：`55`

商务标封面顺序审计：

```text
国网辽宁电力2025年第三次物资协议
库存招标采购
招标编号：2225AC
投标文件
分标编号：按招标文件、本投标文件及附件资料执行
包    号：包1
包名称：包1：电缆保护管CPVC、电缆保护管MPP
文件类别：商务
投标人：河北泰昌电力器材科技有限公司（盖单位章）
法定代表人（单位负责人）或其授权代表人：       （签字）
2026年06月29日
```

## 6. DOCX XML 审计结论

技术标和商务标均满足：

- 招标编号位于项目名称之后、`投标文件` 之前；
- 封面关键行居中；
- 封面字段加粗；
- 页眉文本为空；
- 页脚包含 `PAGE` 字段；
- 页脚不包含 `NUMPAGES`；
- `document.xml` 不包含 `w:titlePg`；
- 首页截图未发现字段重叠、溢出或明显排版失衡。

## 7. 遗留说明

本次只收口封面观感，不处理正文编号模板和附件体量问题。真实导出仍保留以下非本任务范围 warning：

- 技术标仍有 `16` 处待补充/待确认占位；
- 商务标仍有 `14` 处待补充/待确认占位；
- 商务标按本包物料范围过滤非本包物料章节 `2` 个。

这些问题应分别进入正文内容完备性、资料补齐或 P2 附件级能力任务，不作为 `P1-1/P1-2` 的关闭阻塞项。

# DOCX 导出与正式目录

本文档说明标书 Word 导出的关键技术逻辑，便于后续二开和交付排查。

## 目标

DOCX 导出面向正式投标文件，优先保证：

- 在线工作台目录结构与下载 Word 章节结构一致。
- 目录页使用正式 Word 目录样式：黑色正文、层级缩进、点线前导符、右侧页码。
- Word 左侧导航只展示系统章节，不把 AI 正文内部小标题误识别为正式目录章节。
- 正文标题具备稳定编号，避免出现 `18.0.1` 这类不规范编号。
- 图片、表格、页眉页脚、中文字体和正式文本清理在导出阶段统一处理。

## 导出链路

1. 前端标书工作台点击下载时，会把当前在线编辑器内存中的章节快照 `sectionsSnapshot` 一并提交给后端。
2. 后端 `build_project_bid_markdown` 优先使用 `sectionsSnapshot`，只有没有快照时才回退读取 Supabase `bid_sections`。
3. 后端将章节转换为 Markdown，并在导出阶段重新编号。
4. `backend/export/md_to_word.py` 将 Markdown 转成 DOCX：
   - 文档标题只作为封面/目录页文本，不进入 Word 大纲。
   - 系统章节标题写入 Word Heading 样式，并插入书签。
   - 目录页基于章节书签生成 `PAGEREF` 页码域。
   - 目录行使用右对齐制表位和 dot leader，形成正式目录点线。
5. `backend/api/export.py` 在异步导出任务最后调用 `refresh_docx_fields_with_soffice()`：
   - 用 LibreOffice headless 将生成的 DOCX 重新保存为 DOCX。
   - 刷新目录 `PAGEREF`、页脚 `PAGE` 和 `NUMPAGES` 字段。
   - 用户最终下载的仍是 `.docx`，不是 PDF。
   - 刷新失败时不阻断下载，导出任务 metadata 会记录 `field_refresh` 报告。

## 正式目录实现

当前目录不是普通超链接列表，而是“可刷新页码”的 Word 域：

- 每个正式章节标题都有唯一书签：`bid_heading_1`、`bid_heading_2` 等。
- 目录每一行由“章节标题 + 右对齐制表符 + `PAGEREF` 页码域”组成。
- 目录段落设置 `w:leader="dot"`，在 Word 中呈现为点线前导符。
- 文档设置 `w:updateFields=true`，提示 Word/LibreOffice 在打开时刷新目录页码、页脚页码和总页数。
- 目录 `PAGEREF`、页脚 `PAGE` 和 `NUMPAGES` 字段均标记 `w:dirty=true`，强制办公软件打开文档后重新计算字段结果，避免沿用导出阶段的占位页码 `1`。

注意：`python-docx` 本身不能计算真实页码，真实页码必须由 Word、LibreOffice 或 ONLYOFFICE 这类版面引擎刷新。当前后端导出任务已经内置 LibreOffice 刷新步骤，生产环境应安装 `soffice` 并配置路径。

## LibreOffice 服务端刷新

后端刷新逻辑位于 `backend/export/md_to_word.py`：

- `DOCX_REFRESH_FIELDS=true`：开启导出后字段刷新，默认开启。
- `SOFFICE_BIN=/opt/homebrew/bin/soffice`：指定 `soffice` 路径；未配置时会自动查找 PATH，并兜底检查 `/Applications/LibreOffice.app/Contents/MacOS/soffice`。
- `DOCX_REFRESH_TIMEOUT_SECONDS=180`：单次刷新超时秒数。

刷新命令使用独立临时用户目录：

```bash
soffice --headless --nologo --nofirststartwizard \
  -env:UserInstallation=file:///临时profile目录 \
  --convert-to docx \
  --outdir 临时输出目录 \
  输入文件.docx
```

这里使用 `-env:UserInstallation=...` 是为了隔离 LibreOffice 用户配置，避免多次并发导出互相锁定配置目录。不要用 `--env:UserInstallation`，部分 LibreOffice 版本会直接报 `Error in option`。

## 章节编号规则

导出前会按当前章节顺序重新生成正式编号：

- 一级：`1. 企业营业执照`
- 二级：`1.1 资料组成与响应关系`
- 三级：`1.1.1 附件索引`

如果上游章节层级异常，例如一级章节后直接出现三级章节，导出阶段会压平成相邻层级，避免 Word 目录出现 `1.0.1`、`18.0.1` 等非正式编号。

## 二开建议

- 如果客户要求国网/电力标书目录样式，可在现有目录生成逻辑上增加样式预设，例如一级使用 `（一）`、二级使用 `1、`、三级使用 `1.1、`。
- 如果客户要求目录只显示到二级或三级，可通过 `DOCX_TOC_MAX_LEVEL` 控制，默认显示到四级。
- 如果客户有固定 Word 模板，建议保留当前“章节快照 + 标题书签 + PAGEREF 目录”的数据逻辑，只替换样式、页眉页脚和段落格式。
- 如果客户要求下载后目录页码立即准确，必须在导出服务器安装 LibreOffice；否则只能依赖用户打开 Word 后自动刷新字段。

## 回归测试

相关测试位于 `tests/test_docx_export.py`，覆盖：

- 在线工作台章节快照优先于数据库旧章节。
- 正文内部 Markdown 小标题不会进入 Word 大纲。
- DOCX 目录包含 `PAGEREF` 页码域和 dot leader。
- 文档设置打开时刷新域。
- LibreOffice 刷新可被 mock 验证，确保刷新成功时会原地替换导出 DOCX，关闭开关时不改动原文件。
- 跳级章节编号会被压平，不产生 `1.0.1`。
- 正式文本清理、表格保留、图片上限与跳过报告。

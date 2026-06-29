# 2026-06-29 编制页父级目录与全文篇幅设置修复回归

## 背景

客户反馈编制页中父级目录标题仍可进入正文编辑态，正式 Word 中可能导出“编写要点、需准备资料、风险与复核”等内部提示内容。同时要求实事求是确认“全文生成设置”的目标页数/字数是否仍有用。

本轮结论：

- 全文生成设置有用，仍会影响章节目标字数、生成 prompt 和硬性篇幅上限。
- 但该设置只应分配到叶子正文小节，不应分配到父级目录容器。
- 父级容器只负责目录层级和下级章节汇总，不应进入正文编辑、生成、压缩、预览或分章下载。

## 修复范围

- `backend/ai/length_settings.py`
  - 新增容器识别：`section_role=container`、`leaf_generation=false`、存在子章节的节点均视为容器。
  - `evaluate_length_feasibility`、`allocate_chapter_length_targets` 仅统计叶子小节。
  - `apply_length_allocations_to_sections` 清除容器节点由项目篇幅设置写入的目标字数 metadata。
- `backend/api/routes.py`
  - `build_project_bid_markdown` 对容器节点只输出正式章节标题，不输出历史 `content`。
  - 禁止容器节点自动插图。
  - 增强导出清洗，支持清除 `<!-- BID_BODY_SUBHEADING: 1.1 编写要点 -->` 这类带编号的内部提示块。
- `frontend/src/pages/BidEditor/index.tsx`
  - 正文模式选中逻辑默认落到第一个叶子小节。
  - 父级节点点击只展开/收起，不切换到父级编辑器。
  - 父级节点隐藏生成、预览、压缩、下载本章等正文操作。
  - 目录统计拆分为“用户目标、叶子计划、已生成、预计成稿”。
- `tests/test_length_settings.py`
  - 新增容器节点不参与篇幅分配的回归用例。
- `tests/test_docx_export.py`
  - 新增带编号导出提示块清洗用例。
  - 新增父级容器内容不进入正式 Markdown 的用例。

## 真实项目复测

项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`

项目结构：

- 总章节数：`102`
- 容器节点：`27`
- 叶子小节：`75`

全文设置：

- 技术标目标：`80` 页，折算 `56,000` 字
- 商务标目标：`40` 页，折算 `22,000` 字
- 用户目标合计：`120` 页，`78,000` 字

修复后分配结果：

- allocations 总数：`75`
- 叶子 allocations：`75`
- 容器 allocations：`0`
- 容器中仍带 `project_length_settings` 来源 metadata：`0`
- 实际叶子计划合计：`77,300` 字

说明：`77,300` 字低于 `78,000` 字是预期结果。稳健模式下，资格文件、报价文件、附件材料等章节会受章节上限约束，系统不会为了凑满目标字数虚构资料或强行扩写。

## 真实浏览器复测

使用本地真实前端和后端服务，账号 `admin / 12345678` 登录。

结果：

- 正文模式默认选中 `1.1 投标函及投标函附录`，不是父级 `1. 投标函及法定格式文件`。
- 点击父级 `1. 投标函及法定格式文件` 后，右侧仍停留在 `当前章节：1.1 投标函及投标函附录`，父级不进入正文编辑态。
- 目录模式父级节点展示 `结构容器` 和 `目录汇总`，不展示目标页数、目标字数、图文/表格正文标签。
- 目录模式统计展示：
  - `用户目标：120 页 / 78,000 字`
  - `叶子计划：120 页 / 77,300 字`
  - `已生成：320 页 / 205,517 字`
  - `预计成稿：205,517 字（约294页）`

截图：

- `output/playwright/run_20260629_container_length_settings_fix/outline-mode-after-fix.png`

## 真实 DOCX 导出复测

链路：

```bash
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

输出：

- Markdown：`output/playwright/run_20260629_container_length_settings_fix/a1d853bc/泰昌_2225AC_包1_投标文件_20260629.md`
- DOCX：`output/playwright/run_20260629_container_length_settings_fix/a1d853bc/泰昌_2225AC_包1_投标文件_20260629.docx`
- 字段刷新：`refreshed`
- 模板：`formal_bid_standard`

内部提示词扫描结果：

| 关键词 | Markdown 命中 | DOCX XML 命中 |
| --- | ---: | ---: |
| 编写要点 | 0 | 0 |
| 需准备资料 | 0 | 0 |
| 风险与复核 | 0 | 0 |
| 目标字数 | 0 | 0 |
| 硬性篇幅上限 | 0 | 0 |
| 参考客户同类标书目录组织本节 | 0 | 0 |

导出告警：

- 正式资料缺口/占位仍有历史正文遗留，属于客户确认字段和资料补齐问题，不属于本轮父级容器导出污染问题。
- CPVC/MPP scope filter 过滤了 2 条候选，属于既有图片/资料边界门禁。

## 自动化验证

```bash
.venv/bin/python -m pytest tests/test_length_settings.py tests/test_docx_export.py -q
```

结果：`70 passed, 1 warning`

```bash
npm --prefix frontend run build
```

结果：通过。保留既有 Vite 警告：

- `bidProject.ts` 同时被动态和静态导入，不能单独拆 chunk。
- 主 bundle 超过 `500 kB`。

## 结论

本轮 P0 边界已关闭：

- 父级容器不再作为正文编辑节点。
- 父级容器内容不会进入正式 Markdown/DOCX。
- 全文篇幅设置仍有效，但只作用于叶子正文小节。
- 页面统计不再把实际已生成字数误标为计划目标。

剩余建议：

- 后续单独做历史数据治理，扫描并备份所有项目父级 `content`，必要时迁移到叶子小节或标记为 `container_note`。
- 将本轮人工执行的导出污染扫描接入导出任务 metadata，形成长期门禁。

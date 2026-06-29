# 编制页父级目录与全文篇幅设置治理任务清单

更新时间：2026-06-29

## 背景与结论

本清单针对客户反馈的两个问题合并跟踪：

1. 编制页目录树中的父级章节目前仍可被选中，右侧会出现编辑器、生成、下载等正文操作，容易把“目录结构节点”误当成“正式正文节点”。
2. 目录模式下“全文生成设置”的目标页数/字数功能仍然有用，但当前展示和后端分配边界不够严谨：它会影响章节写作计划、生成 prompt、补写策略和硬性篇幅上限，但现有分配逻辑没有显式排除父级容器节点。

验收边界：

- 父级容器只承担展开、收起、排序、目录结构展示和导出标题作用，不进入正文编辑态。
- 正式 DOCX 导出只输出父级标题，不输出父级内部写作提示、草稿说明或编辑器占位内容。
- 全文篇幅设置只分配到叶子正文小节；父级容器不得获得目标字数，也不得参与篇幅完成率计算。
- 页面必须明确区分“用户目标”“计划目标”“实际已生成”，避免用户误解目标页数等于最终 Word 页数。

## 任务清单

| 优先级 | 状态 | 任务 | 范围 | 验收标准 |
| --- | --- | --- | --- | --- |
| P0-1 | 已完成 | 父级容器节点禁止进入正文编辑态 | 前端 `BidEditor` | 点击父级标题只展开/收起或定位第一个叶子小节；右侧不展示 Tiptap 正文编辑器、保存章节、生成本章正文、下载本章等正文操作；父级只展示“结构容器”说明和下级章节汇总。 |
| P0-2 | 已完成 | DOCX 导出强制跳过父级容器内容 | 后端 `build_project_bid_markdown` / 导出清洗 | 父级容器只输出正式章节标题；即使数据库里已有父级 `content`，也不得进入 Markdown/DOCX 正文；新增回归用例覆盖父级含 `编写要点/需准备资料/风险与复核` 的场景。 |
| P0-3 | 已完成 | 全文篇幅设置只分配叶子章节 | 后端 `length_settings.py` | `allocate_chapter_length_targets` 排除 `section_role=container`、`leaf_generation=false` 和有子节点的章节；保存后 allocations 数量等于叶子章节数；容器 metadata 不写入 `target_words`。 |
| P0-4 | 已完成 | 目录统计口径修正 | 前端目录模式 | 分开显示“用户目标”“叶子章节计划”“实际已生成”；已生成内容超过目标时显示超出比例和说明，不再把实际字数标为“章节计划”。 |
| P1-1 | 已完成 | 清理/隔离历史父级内容 | 数据治理脚本/一次性修复 | 已新增可 dry-run/apply 的通用治理脚本；父级容器数量按具体项目目录树动态计算。本次辽宁项目实测为 27 个父级容器，其历史正文已备份、清空并写入 `container_content_policy=ignored_for_formal_export`；全部标记为 `migration_review_required=true`，后续如需复用只能人工迁移到叶子小节。 |
| P1-2 | 已完成 | 导出清洗增强 | 后端导出 | 对 `<!-- BID_BODY_SUBHEADING: 1.1 编写要点 -->` 这类带编号的内部提示也能清除；不得误删正式正文小标题。 |
| P1-3 | 已完成 | 全文设置文案与门禁说明 | 前端弹窗/帮助文案 | 明确“目标页数是生成规划估算，不保证最终 Word 页数”；说明图片、表格、附件、封面目录会改变最终页数；稳健模式不得为了凑页数虚构资料。 |
| P1-4 | 已完成 | 目录节点操作按钮分层 | 前端目录模式 | 父级仅保留展开/收起和结构类更多操作；叶子小节才显示生成、预览、压缩、下载本章等正文操作。 |
| P1-5 | 已完成基础门禁 | 正式导出污染扫描门禁 | 后端/测试 | 本轮真实导出后扫描 Markdown 与 DOCX XML，`编写要点`、`需准备资料`、`风险与复核`、`目标字数`、`硬性篇幅上限` 均为 0；后续可把该扫描正式接入导出任务 metadata。 |
| P2-1 | 待处理 | 父级正式概述例外机制 | 产品/后端 | 如确需父级概述，必须显式配置 `container_content_policy=formal_overview`，并通过正式正文白名单，不允许默认把编辑器草稿导出。 |

## 已完成复测

- 单元测试：`tests/test_length_settings.py` 和 `test_stream_bid_section_stops_when_hard_length_cap_is_reached` 通过，证明篇幅设置会进入写作计划和硬性篇幅上限。
- 真实项目数据：项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d` 当前 102 个章节，27 个容器、75 个叶子。按 80/40 页内存分配时，现有逻辑给 102 个章节全部分配目标字数，其中包含 27 个容器，需修复。
- 真实浏览器：本地 `admin / 12345678` 登录后进入编制页，目录模式显示“用户目标 120 页 / 78,000 字”，同时显示“已生成 320 页 / 205,517 字、章节计划 205,517 字”，展示口径存在误导。
- 真实导出前置链路：当前项目本次 Markdown 导出未命中 `编写要点/需准备资料/风险与复核/目标字数/硬性篇幅上限`，但合成父级草稿用例证明清洗函数对带编号的内部提示注释仍有缺口。
- 2026-06-29 修复后复测：项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d` 重算后仍为 102 个章节、27 个容器、75 个叶子；篇幅 allocations 为 75 个，容器 allocations 为 0，父级容器中 `project_length_settings` 来源 metadata 为 0。
- 2026-06-29 真实浏览器复测：正文模式默认选中 `1.1 投标函及投标函附录`；点击父级 `1. 投标函及法定格式文件` 后右侧仍停留叶子正文，不进入父级编辑器。目录模式显示 `用户目标 120 页 / 78,000 字`、`叶子计划 120 页 / 77,300 字`、`已生成 320 页 / 205,517 字`、`预计成稿 205,517 字（约294页）`。
- 2026-06-29 真实导出复测：完成 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`，输出 `output/playwright/run_20260629_container_length_settings_fix/a1d853bc/泰昌_2225AC_包1_投标文件_20260629.docx`，字段刷新 `refreshed`，内部提示词 Markdown/DOCX XML 命中均为 0。
- 2026-06-29 自动化回归：`.venv/bin/python -m pytest tests/test_length_settings.py tests/test_docx_export.py -q` 结果 `70 passed, 1 warning`；`npm --prefix frontend run build` 通过，仅保留既有动态导入和 chunk size 警告。
- 2026-06-29 P1-1 历史父级内容治理：新增 `scripts/rag/govern_bid_container_content.py`；脚本按项目章节树动态识别容器，不固定数量。本次辽宁项目 dry-run 发现 27 个父级容器均有历史正文，均为 `formal_overview_candidate`，无内部提示命中。正式执行 `--apply --clear-content` 后，27 个容器 `content` 全部清空，27 个容器 metadata 均写入 `container_content_policy=ignored_for_formal_export`，27 个标记 `migration_review_required=true`，75 个叶子正文保持不变。
- 2026-06-29 P1-1 真实导出复测：清理后重新执行 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`，输出 `output/playwright/run_20260629_bid_container_content_governance/a1d853bc/泰昌_2225AC_包1_投标文件_20260629.docx`，字段刷新 `refreshed`；`编写要点/需准备资料/风险与复核/目标字数/硬性篇幅上限/参考客户同类标书目录组织本节/历史父级正文已备份` 在 Markdown 与 DOCX XML 中命中均为 0。
- 2026-06-29 P1-1 自动化回归：`.venv/bin/python -m pytest tests/test_bid_container_content_governance.py tests/test_length_settings.py tests/test_docx_export.py -q` 结果 `74 passed, 1 warning`。

## 下一步建议

本轮 P0 与 P1-1 已完成并通过真实复测。下一步建议进入 P2-1 的“父级正式概述例外机制”设计：只有当用户明确需要父级概述正文时，才允许显式配置 `container_content_policy=formal_overview` 并走白名单审核，默认仍保持父级只作为目录结构。

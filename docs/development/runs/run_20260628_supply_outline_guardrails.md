# 2026-06-28 供货类标书大纲膨胀与正文标题污染修复记录

## 背景

辽宁 CPVC 包 1 真实投标流程中，标书编制页出现大纲膨胀到 `278` 个章节的问题，且正文中出现 `【5.1 概述】`、`【5.2 技术方案与产品性能响应】` 等模型生成的括号式编号标题，导致目录编号、正文编号和正式标书观感不一致。

## 根因判断

- 不是单纯脏数据问题，而是大纲生成策略缺少供货类硬门禁。
- 快速规则大纲已能使用客户参考结构，但后台 AI 精修路径可能返回远超参考结构的目录，并覆盖快速大纲。
- AI 大纲未强制 `preserve_reference_structure` 时，大叶子章节会被自动拆分，兜底拆分主题里包含施工类“编制依据、工程概况、总体部署”等章节。
- 章节正文生成时模型可能重复输出章节标题或自造 `【5.1】` 式小标题，保存层缺少统一清理。

## 修复内容

- `backend/ai/chapter_planner.py`
  - 供货类大纲新增总节点上限 `140`。
  - 供货类 AI 大纲强制 `preserve_reference_structure=true`，禁止进入大叶子自动拆分。
  - 后台精修增加相对快速大纲增长门禁，防止 `102 -> 278` 这类膨胀替换。
  - 供货类提示词从“章节不少于”调整为“章节控制在合理范围”，并禁止把附件/证明截图逐项扩成独立正文章节。

- `backend/ai/section_writer.py`
  - 保存前清理重复 Markdown 章节标题。
  - 将独立成行的 `【5.1 概述】` 等括号式编号标题规范为 `5.1 概述`。
  - 质量重写提示增加“不要输出章节标题、目录编号或括号式小标题”要求。

- `backend/services/section_generation.py`、`backend/tasks/section_tasks.py`
  - 章节保存和后台任务完成态均使用清理后的正文，避免任务缓存与章节正文不一致。

## 验证

- `.venv/bin/python -m pytest tests/test_chapter_planner.py tests/test_section_writer_formal_quality.py`
  - 结果：`15 passed`
- `.venv/bin/python -m py_compile backend/ai/chapter_planner.py backend/ai/section_writer.py backend/services/section_generation.py backend/tasks/section_tasks.py`
  - 结果：通过

## 后续建议

- 重新从辽宁 CPVC 包 1 上传/解析/确认/生成大纲开始跑一遍真实流程，确认章节数保持在供货类参考结构范围内。
- 已生成过的旧项目若已落库 278 节，需要重新生成大纲或清空旧章节后再生成正文。

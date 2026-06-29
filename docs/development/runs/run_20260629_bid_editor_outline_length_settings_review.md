# 2026-06-29 编制页父级目录与全文篇幅设置复测记录

## 复测对象

- 项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 页面：`/bid-editor?projectId=a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 场景：目录模式父级节点、全文生成设置、正式导出前置 Markdown

## 命令与结果

### 单元测试

```bash
.venv/bin/python -m pytest tests/test_length_settings.py tests/test_section_generation_autoresume.py::SectionGenerationAutoResumeTest::test_stream_bid_section_stops_when_hard_length_cap_is_reached -q
```

结果：`9 passed in 0.51s`。

结论：目标页数/字数会写入章节 `writing_plan.target_words`，并被写作 prompt、补写策略和硬性篇幅上限读取。该功能仍然有实际作用，不应直接删除。

### 真实项目内存分配复测

输入设置：

```json
{
  "mode": "pages",
  "technicalPages": 80,
  "businessPages": 40,
  "allowAutoExpand": false
}
```

结果：

- 章节总数：102
- 容器节点：27
- 叶子节点：75
- allocations 总数：102
- 叶子 allocations：75
- 容器 allocations：27

结论：当前后端篇幅分配没有排除父级容器节点。这会让父级章节也带上目标字数和写作计划，必须修复为只分配叶子正文小节。

### 真实浏览器复测

本地服务：

- 前端：`5173`
- 后端：`3012`
- 登录账号：`admin / 12345678`

观察结果：

- 正文模式下，选中父级“1. 投标函及法定格式文件”后，右侧仍显示正文编辑器、`保存章节`、`生成本章正文`、`下载本章`。
- 目录模式下，父级节点显示为“结构容器”，但标题按钮仍可点击，且行内仍存在多个操作按钮。
- 目录模式统计显示：
  - 用户目标：120 页 / 78,000 字
  - 已生成：320 页 / 205,517 字
  - 章节计划：205,517 字（约294页）
- 全文设置弹窗显示：
  - 技术标目标页数：80
  - 商务标目标页数：40
  - 合计：120 页 / 78,000 字
  - 策略：稳健生成

截图证据：

- `output/playwright/bid-editor-length-settings-20260629.png`

结论：全文设置可读取并展示项目设置，但目录统计口径把实际已生成字数混入“章节计划”，容易让用户误解设置无效。

### 正式导出前置链路复测

真实项目导出 Markdown：

```bash
build_project_bid_markdown(project_id, with_images=False)
```

结果：

- 输出标题：`国网辽宁电力2025年第三次物资协议库存招标采购投标文件`
- 关键字命中：
  - `编写要点`: 0
  - `需准备资料`: 0
  - `风险与复核`: 0
  - `目标字数`: 0
  - `硬性篇幅上限`: 0
- warnings：
  - 已按本包物料范围过滤非本包物料章节 2 个
  - 仍有 30 处待补充/待确认占位

补充复测：使用合成父级草稿内容验证导出清洗函数，发现 `### 编写要点` 被降级为 `<!-- BID_BODY_SUBHEADING: 1.1 编写要点 -->` 后，现有 `_strip_export_guidance_blocks` 未清除该编号形式。

结论：当前真实项目本次导出未复现内部提示泄露，但代码层仍存在门禁缺口；一旦父级或草稿内容进入导出，仍可能污染正式文件。

## 结论

1. 父级目录不可进入正文编辑态，这个优化合理且必要。
2. 全文生成设置仍有用，但必须限定为叶子章节写作计划，不应污染父级容器。
3. 目录模式统计需要区分“用户目标”“计划目标”“实际已生成”，否则会被客户理解为设置无效。
4. DOCX 导出必须增加父级容器内容跳过和内部提示词扫描门禁。

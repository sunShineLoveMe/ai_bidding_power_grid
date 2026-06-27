# Run 20260617 - 前导确认页接入主流程与可编辑 UI

## 背景

用户真实跑流程后发现两个问题：

1. “投标确认”作为左侧一级菜单出现，和前导确认页的产品定位不一致。
2. 前导确认页仍是只读报告，无法编辑客户需确认字段；同时表格布局导致项目名称、说明文案和字段内容横向溢出。

## 产品调整

前导确认页定位更新为“生成正文前的投标关键信息确认步骤”，不再作为全局一级业务菜单。

自动流程调整为：

```text
上传招标文件
-> 解析招标文件
-> 生成招标解读
-> 生成分册大纲
-> 投标信息确认
-> 进入标书编制
```

## 改动

### 导航

- `frontend/src/components/layout/AppLayout.tsx`
  - 左侧一级导航移除“投标确认”。
  - `/prefill` 路由继续保留，供流程跳转和招标解读页按钮进入。

### 上传自动流程

- `frontend/src/components/workflow/BidWorkflow.tsx`
  - 新增第 5 步“投标信息确认”。
  - 分册大纲生成完成后自动跳转 `/prefill?projectId=<id>&fromWorkflow=1`。
  - 右侧动作区新增“进入投标确认”，正文编辑入口在确认步骤前不作为主路径。

### 前导确认页

- `frontend/src/pages/BidPrefill/index.tsx`
  - 主视图从横向表格改为“字段分组 + 可编辑字段卡片”。
  - 每个字段展示系统候选值、客户确认值、状态、风险、来源规则、依据和映射。
  - 支持客户编辑确认值、恢复候选值、只看需确认字段。
  - 点击“确认并进入正文编辑”后，将确认值保存为本地草稿并进入正文编辑。

## 边界

- 当前确认值不直接写入 `bid_sections`。
- 当前确认值不影响 `sectionsSnapshot` DOCX 导出契约。
- 报价、保证金、授权签章、税率等客户决策字段仍要求人工填写/确认。
- 后续“变量确认后的显式回填引擎”完成后，再由用户明确触发变量替换。

## 测试

### 单元/构建

```bash
.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_celery_interpretation_tasks.py tests/test_segmented_interpreter.py
npm run build
```

结果：

```text
10 passed
npm run build PASS
```

### 真实页面回归

使用本地真实服务：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:3012`
- 项目：`4390e1ff-2d62-4230-802a-b5dc829145f2`

Playwright + 本机 Chrome 检查：

```text
左侧菜单项：
主页、招标项目、企业知识库、企业资信库、企业产品库、用量与成本、历史记录

前导页桌面 1440px：
textareaCount=33
cardCount=37
hasConfirmButton=true
bodyWidth=1440
viewportWidth=1440
overflow=false

前导页窄屏 390px：
textareaCount=33
hasConfirmButton=true
bodyWidth=390
viewportWidth=390
overflow=false

流程步骤：
上传招标文件、解析招标文件、生成招标解读、生成分册大纲、投标信息确认、进入标书编制
hasPrefillStep=true
hasConfirmAction=true
```

截图：

```text
/tmp/bid-prefill-regression.png
/tmp/bid-workflow-regression.png
/tmp/bid-prefill-regression-v2.png
/tmp/bid-prefill-mobile-regression-v2.png
```

## 结论

P1C-6 完成。前导确认页已从一级菜单独立入口调整为主流程中的生成前确认步骤，并支持客户编辑确认值；页面横向溢出问题已通过卡片化布局和换行约束修复。

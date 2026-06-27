# run_20260624_formal_check_v1_skeleton

生成时间：2026-06-24T10:02:46Z

## 目标

按 `docs/development/formal-check-todo.md` 的 P0 优先级，先完成“正式检查”本地最小闭环：

- 60 条正式检查规则 v1；
- 后端正式检查服务；
- 正式检查 API；
- 前端正式检查页面；
- 标书编制页入口；
- 规则来源核验初稿；
- 定向测试与前端构建验证。

## 本轮完成

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 60 条规则 JSON | 完成 | `rules/power_grid/formal_bid_check_rules.v1.json`，覆盖资格、商务、技术、报价、格式、资料边界、导出成品 |
| 后端服务 | 完成 | `backend/services/formal_bid_check.py`，实时汇总规则、投标确认、条款覆盖、资产和导出任务 metadata |
| API | 完成 | `GET /api/bidding/projects/{project_id}/formal-check` |
| 前端页面 | 完成 | `frontend/src/pages/FormalCheck/`，支持门禁状态、指标、筛选和明细展示 |
| 导航入口 | 完成 | 主导航新增“正式检查”；标书编制页下载按钮旁新增入口 |
| 来源核验文档 | 完成初稿 | `docs/development/formal-check-rules-source-review.md` |
| 草稿版策略 | 部分完成 | 页面和报告已显示“仅允许草稿版导出”；正式导出按钮强制降级/拦截尚未接入 |
| DOCX 导出后检查 | 部分完成 | 服务能读取导出任务 metadata；未传入导出任务时返回需导出后复验 |
| 散落检查项清理 | 部分完成 | 已新增统一入口；尚未删除/合并旧页面中的重复检查表达 |

## 验证命令

```bash
PYTHONPATH=. .venv/bin/python -m py_compile backend/services/formal_bid_check.py backend/api/formal_check.py
PYTHONPATH=. .venv/bin/pytest tests/test_formal_bid_check.py -q
npm run build
```

## 验证结果

| 命令 | 结果 |
| --- | --- |
| Python 编译 | PASS |
| `tests/test_formal_bid_check.py` | PASS，3 passed，1 个 PyPDF2 既有 warning |
| 前端 build | PASS，保留既有 Vite chunk size warning |
| Playwright 页面访问 | PASS，真实注册登录后访问 `/formal-check` |

## 当前限制

1. 正式导出按钮尚未强制调用正式检查结果；阻断项存在时的“只能导出草稿版”目前已在页面展示，但未在导出任务层完全 enforcement。
2. 规则来源核验是第一版初稿，后续应继续按目标省公司招标文件逐条补页码/条款。
3. DOCX 导出后成品项需要传入 `exportTaskId` 后才能基于真实导出 metadata 复验。
4. 已完成 Playwright 真实浏览器视觉评估；当前工具未暴露可调用的 Chrome 插件能力，后续如可用再补 Chrome 专项复核。
5. 散落在解读页、标书编制页、投标确认页的旧检查项仍需下一轮清理或合并。

## 浏览器验证

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:3012`
- 验证方式：Playwright wrapper，真实注册登录账号 `codex_formal_20260624` 后访问 `/formal-check`
- 结果：页面可访问，主导航“正式检查”可见，页面展示 60 条规则、7 个阻断项、草稿版提示、分类/状态/等级筛选和规则来源说明。
- 截图：`docs/development/runs/run_20260624_formal_check_page.png`
- 控制台：仅有 Ant Design 静态 `message` context 既有开发警告，未发现正式检查页面渲染异常。

## 下一步优先级

1. 将正式检查结果接入正式版导出按钮：阻断项存在时只能导出草稿版。
2. 用真实项目打开正式检查页，执行 Chrome/Playwright 本地浏览评估。
3. 清理重复检查项：将条款覆盖率、投标确认缺口、导出 metadata 统一说明为正式检查子指标。
4. 针对目标招标文件补充规则来源页码、条款原文和适用范围。

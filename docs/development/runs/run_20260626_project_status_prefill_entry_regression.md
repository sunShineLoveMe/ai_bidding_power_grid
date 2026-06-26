# 全流程项目状态与投标确认入口回归

时间：2026-06-26

范围：P1「全流程项目状态同步与投标确认入口收口」。

## 背景

真实浏览器全流程项目 `4d632dbe-f6e6-4066-8fe2-929ecb54ba1d` 已从上传招标文件推进到 75/75 个叶子章节正文完成，但首页/历史记录曾显示解析中或旧解析错误；工作流自动跳入投标确认页时也曾出现“当前项目暂无投标确认报告”的误导空态。

## 本轮修复

1. `/api/bidding/history` 统一派生项目生命周期：
   - `待投标确认`
   - `正文生成中`
   - `草稿待续写`
   - `正文初稿完成`
   - `next_step` / `next_action`
2. 历史接口接入最新批量正文生成任务，返回正文总数、完成数、partial 草稿数和复核数。
3. 已有 chunk/解读/章节的项目以结构化结果优先，不再被本地旧解析状态覆盖为解析失败/解析中，也不再展示旧错误和“重试解析”按钮。
4. 首页最近任务和历史记录按 `next_step` 跳转：
   - `prefill` -> 投标确认
   - `resume_partial` -> 带 `action=resume-partial` 的编辑器
   - `formal_check` -> 正式检查
5. 投标确认页从工作流进入时增加短轮询，等待大纲和确认字段同步完成，避免刚跳转时误显示空报告。
6. 编辑器支持 `action=resume-partial`，从历史/首页进入草稿待续写项目时自动触发一次批量续写。

## 自动化验证

| 命令 | 结果 |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_bid_history_status.py tests/test_project_latest_interpretation.py -q` | PASS，5 passed |
| `cd frontend && npm run build` | PASS，Vite 构建成功；仅保留既有 chunk size 警告 |

## 真实浏览器验证

环境：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:3012`
- 测试账号：本轮注册临时账号 `codex_status_1782459579844`

| 验证项 | 结果 |
| --- | --- |
| 首页最近任务 | 最新项目显示 `正文初稿完成`、`正文 75/75`，不再显示旧 `解析中` |
| 首页最近任务主按钮 | 点击后进入 `/formal-check?projectId=4d632dbe-f6e6-4066-8fe2-929ecb54ba1d` |
| 历史接口 | 最新项目返回 `stage=正文初稿完成`、`next_step=formal_check`、`parse_error=null`、`parse_retryable=false` |
| 历史页状态 | 最新项目不再显示旧解析错误，不再显示“重试解析”按钮 |
| 历史页正式检查按钮 | 点击第一行进入 `/formal-check?projectId=4d632dbe-f6e6-4066-8fe2-929ecb54ba1d` |
| 历史页投标确认按钮 | `待投标确认` 项目进入 `/prefill?projectId=fa4c8a41-5df2-49a9-984d-1c3ce0de57ea&fromHistory=1` |
| 投标确认报告加载 | 确认页加载 35 个字段，未出现“当前项目暂无投标确认报告” |

## 未触发项说明

历史记录中存在旧项目 `70323ce8-f18e-46ca-8d22-33865525a7f7`，状态为 `草稿待续写`，待续写草稿 20 个。点击会真实触发 20 章模型续写，成本和耗时不适合作为本轮状态回归的一部分；本轮已验证接口状态和目标路由 `/bid-editor?projectId=70323ce8-f18e-46ca-8d22-33865525a7f7&action=resume-partial` 正确。

## 结论

P1「全流程项目状态同步与投标确认入口收口」本轮通过验收。后续若客户继续从新项目上传开始全流程测试，应继续观察：

- 新项目从大纲生成后是否稳定进入投标确认；
- partial 草稿数量较少时是否可执行一次真实续写回归；
- Ant Design 全局 message context warning 仍属于 P2 工程质量项。

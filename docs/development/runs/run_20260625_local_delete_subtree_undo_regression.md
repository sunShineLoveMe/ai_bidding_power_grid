# 2026-06-25 本地回归：SG-DATA-003 删除真实提示与撤销兜底

## 范围

- P0：`SG-DATA-003`
- 页面：`/bid-editor?projectId=628ed517-0c31-44ea-a5cb-95b25db06fc2`
- 账号：`admin / 12345678`
- 目标：删除章节必须提示真实后端删除；删除父章节时同步删除子章节；删除后提供本页面内撤销恢复。

## 变更

- 后端 `delete_bid_section()` 改为按当前项目章节树计算 descendant IDs，并一次性删除章节子树。
- 删除接口返回 `deleted_count`，用于验证实际删除数量。
- 前端删除确认从静态 `Modal.confirm` 改为受控 `Modal`，文案明确“从当前项目删除”和“同步删除后端章节数据”。
- 前端删除成功后保留最近一次删除快照，页面内显示“撤销删除”提示条。
- 撤销时按原 ID、原父子关系和原顺序调用 `saveBidSection()` 恢复章节树，并重新加载项目。

## 验证

| 验收项 | 结果 |
| --- | --- |
| 前端构建 | `npm run build` 通过；仅保留 Vite chunk size / 动态导入既有 warning |
| 后端语法 | `.venv/bin/python -m py_compile backend/db/supabase_repo.py backend/api/sections.py` 通过 |
| API 子树删除 | 创建临时父子章节 2 个，删除父章节返回 `deleted_count=2`，查询剩余 0 |
| 浏览器删除提示 | 真实菜单点击“删除章节”后，确认弹窗显示真实删除、1 个子章节一并删除、后端同步删除和临时撤销说明 |
| 浏览器删除结果 | 页面章节数 `208 -> 206`，搜索结果 `1 / 208 -> 0 / 206` |
| 后端删除结果 | 删除后 API 查询父子 ID 均不存在 |
| 撤销恢复 | 点击“撤销删除”后页面章节数恢复 `208`，父章节与子章节按原 ID 恢复 |
| 父子关系 | 撤销后子章节 `parent_id` 指向原父章节 ID，`level=2` |
| 清理 | 回归临时父子章节已删除，章节数恢复 `206`，`regression_case=delete_subtree_undo_ui_controlled` 剩余 0 |
| 浏览器 console | 受控删除/撤销路径完成后 `console error=0`；登录成功提示仍属于既有全局静态 `message.*` warning |

## 临时数据

- API 子树删除验证：
  - parent: `a6b9a0fa-894f-419e-b920-d6391c91e434`
  - child: `c9c2d590-a087-4b7b-a975-3edd00b168ca`
- UI 删除/撤销最终验证：
  - parent: `c3754433-bcd6-4cfc-b078-3376f382d2b3`
  - child: `3e6a86c5-4c38-47ec-b95a-271760a6dfd4`

以上临时数据均已清理。

## 结论

`SG-DATA-003` 本地实现并通过真实 API + 真实浏览器回归。删除语义不再误导为“只影响页面草稿”，且误删后在当前页面内可以撤销恢复。

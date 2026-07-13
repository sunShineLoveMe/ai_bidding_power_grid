# 泰昌历史标书复用 P0-07 通用流程兼容性边界验证记录

> 日期：2026-07-13
> 状态：PASS
> 范围：项目模式、任务上下文、旧项目兼容、专版关闭回退和前端类型契约

## 一、实施结果

| 验证项 | 结果 |
| --- | --- |
| 项目模式字段 | PASS，新增 `bid_projects.project_mode`，默认 `general`，仅允许 `general/taichang_reuse` |
| 旧项目兼容 | PASS，缺失或旧异常值统一按 `general` 读取 |
| 默认流程 | PASS，前端与后端未显式传值时均创建 `general` |
| 显式专版 | PASS，仅显式 `projectMode=taichang_reuse` 创建泰昌专版 |
| 任务模式固化 | PASS，AI 解读、章节批量生成、DOCX 导出 metadata 均从服务器项目记录写入模式 |
| 客户端防篡改 | PASS，客户端 metadata 中同名模式字段被服务器权威字段覆盖 |
| 继续与重试 | PASS，历史解析重试从项目记录恢复模式；浏览器旧活动任务回退 `general` |
| 专版关闭 | PASS，`TAICHANG_REUSE_ENABLED=false` 只拒绝新建专版，不影响通用上传 |
| 迁移窗口回退 | PASS，旧表允许通用项目降级创建，专版禁止静默降级 |
| 本地 PostgreSQL 迁移 | PASS，48 个既有项目均为 `general`，字段默认值、非空约束和 CHECK 约束生效 |
| 真实数据只读抽样 | PASS，最近 3 个项目均返回 `general`；伪造 `taichang_reuse` metadata 后仍被服务器覆盖为 `general/general_v1` |
| 前端生产构建 | PASS，TypeScript 与 Vite 构建成功 |
| 后端全量回归 | PASS，389 passed、2 subtests passed |

## 二、代码与数据库变更

- 模式契约：`backend/core/project_modes.py`
- 任务上下文：`backend/services/project_mode_context.py`
- 项目创建/历史重试：`backend/api/projects.py`
- 解读/章节生成/导出任务：`backend/api/interpret.py`、`backend/api/sections.py`、`backend/api/export.py`
- 数据访问兼容：`backend/db/supabase_repo.py`
- 数据库迁移：`migrations/postgres/009_bid_project_modes.sql`
- 前端契约：`frontend/src/types/bid.ts`、`frontend/src/api/bidProject.ts`、`frontend/src/components/workflow/BidWorkflow.tsx`
- 边界说明：`docs/development/taichang-general-mode-compatibility-boundary-20260713.md`

## 三、测试记录

执行：

```text
.venv/bin/python -m pytest -q \
  tests/test_project_modes.py \
  tests/test_celery_parse_tasks.py \
  tests/test_api_sections.py \
  tests/test_celery_interpretation_tasks.py \
  tests/test_celery_export_tasks.py \
  tests/test_postgres_schema_init.py

npm --prefix frontend run build
```

定向结果：43 passed，4 个既有弃用告警；前端 build PASS，仅保留既有 bundle 大小和动态/静态 import 提示。

全量结果：389 passed、2 subtests passed、11 个既有弃用告警。全量首轮暴露健康检查旧测试仍要求纯 `status` 响应，而真实接口自 2026-06-27 起已包含版本信息；已按当前接口契约修正测试并复跑通过。

## 四、未触发门禁说明

本轮未新增或修改泰昌企业资料、RAG metadata、召回策略、正式图片资产、DOCX 排版或选图规则，因此不重复执行 Base + 泰昌专项召回门禁、真实知识问答 stream 或正式 DOCX 导出。P0-07 的导出变更仅为任务记录附加项目模式 metadata，已有导出路由与 Celery 回归纳入测试。

## 五、范围与后续

- P0-06 仍为业务审批待办，未批准任何候选资产。
- 本轮不实现泰昌专版首页入口；后续入口只能显式传入 `taichang_reuse`。
- 本轮不实现历史骨架差异对照或泰昌正文编排，继续由 P2 任务承接。
- 多企业、多行业历史模板平台不在泰昌 MVP 范围。

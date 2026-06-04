# 章节生成 P0 后续整改回归记录

日期：2026-06-04

范围：前端长任务轮询、PostgreSQL 初始化迁移链、章节生成协调任务失败回写。

## 改动摘要

- 前端 `pollSectionGenerationTask()` 改为长任务友好模式：按章节数和目标字数计算等待窗口，超过当前窗口时返回“后台继续执行”状态，不再把长任务误判为失败。
- `scripts/init_postgres_schema.sh` 纳入 `006`、`007` 和 `20260603` 章节任务 DDL，并验证章节生成所需表和 RPC。
- 后端新增 `fail_bid_generation_task()`，`run_bid_section_generation()` 外层捕获协调任务异常后写入业务终态。

## 生产环境证据

运行中的 PostgreSQL 已执行完整初始化脚本并验证通过：

- `bid_generation_tasks`
- `bid_generation_task_items`
- `bid_generation_task_events`
- `power_grid_goods_list_rows`
- `lease_bid_generation_task_items(uuid, uuid, integer, text, integer)`
- `heartbeat_bid_generation_task_item(uuid, uuid, uuid, uuid, text, integer)`
- `expire_bid_generation_task_items(uuid, uuid, boolean)`
- `update_bid_generation_task_item_atomic(uuid, uuid, text, jsonb)`
- `set_bid_generation_task_items_updated_at()`

历史垃圾任务已在整改前清理：

- `bid_generation_tasks` 删除 19 条历史 `queued/running`
- `bid_generation_task_events` 删除 1 条关联事件
- `bid_generation_task_items` 无关联旧 item

清理后：

- `bid_generation_tasks` 中 `queued/running = 0`
- `bid_generation_task_items` 中 `queued/leased/running/generating/saving = 0`
- 最新真实任务 `3d7e3333-7414-4e36-aa3e-283c7d9dc18f` 保留为 `completed`，52/52 章节完成

## 验证命令

```bash
bash -n scripts/init_postgres_schema.sh
git diff --check
npm run build
PYTHONPATH=. .venv/bin/pytest tests/test_section_generation_autoresume.py tests/test_postgres_schema_init.py
PYTHONPATH=. .venv/bin/pytest tests/test_api_sections.py tests/test_section_generation_autoresume.py tests/test_postgres_schema_init.py tests/test_celery_export_tasks.py
./scripts/init_postgres_schema.sh
```

## 验证结果

- 前端生产构建通过。
- 针对性后端测试：5 passed。
- API / Celery / 章节生成相关回归：19 passed。
- PostgreSQL 初始化脚本在当前运行库上幂等执行成功。
- 数据库对象和 RPC 校验通过。

## 仍需继续

- P1：实现周期性 task reconciler，把未来超过 lease/心跳窗口的任务转为可恢复或失败态。
- P1：补最小 E2E 长任务回归，覆盖上传、解析、目录生成、30+ 章节生成、刷新恢复和导出。
- 全量真实 LLM 30+ 章节压测应在成本和时间窗口确认后执行，避免无控制地重写客户正文。

# 章节生成 P1 Reconciler 与长任务 Smoke 回归记录

日期：2026-06-04

范围：任务 reconciler、长任务 HTTP smoke 入口。

## 改动摘要

- 新增 `reconcile_stale_bid_generation_tasks()`：
  - 扫描长时间停留在 `queued/running` 的章节生成任务。
  - 新式 item 表任务调用 `expire_bid_generation_task_items(..., requeue=True)` 回收过期 lease。
  - 历史 JSON-only 任务没有 item/lease 证据，直接写入业务失败态，避免污染 latest task 恢复。
- 新增 Celery 任务 `bid.sections.reconcile_stale_tasks`。
- Celery beat schedule 增加 `reconcile-stale-section-generation-tasks`，默认 60 秒触发一次。
- `scripts/smoke_key_flow.py` 新增 `--section-count` 参数，支持显式执行 30+ 章节长任务回归。

## 真实库验证

在当前运行 PostgreSQL 上执行 reconciler：

```bash
PYTHONPATH=. .venv/bin/python - <<'PY'
from backend.tasks.section_tasks import reconcile_stale_section_generation_tasks
print(reconcile_stale_section_generation_tasks.run(max_age_seconds=60, limit=20))
PY
```

结果：

```text
{'scanned': 0, 'expired_items': 0, 'failed_legacy_tasks': 0, 'skipped': 0, 'tasks': []}
```

当前库状态：

- `bid_generation_tasks` 中 `queued/running = 0`
- `bid_generation_task_items` 中 `queued/leased/running/generating/saving = 0`

## 长任务 Smoke 用法

默认 smoke 仍只生成 1 个章节：

```bash
PYTHONPATH=. .venv/bin/python scripts/smoke_key_flow.py --base-url http://127.0.0.1:8000
```

受控 30+ 章节长任务回归：

```bash
PYTHONPATH=. .venv/bin/python scripts/smoke_key_flow.py \
  --base-url http://127.0.0.1:8000 \
  --section-count 30 \
  --timeout 2400
```

2026-06-05 已补跑真实 30 章节长任务压测：

- 测试项目：`e3d516b7-c2e0-4349-8ede-efab6241076b`
- 覆盖范围：该测试项目 30 个叶子小节正文
- 任务：`88dc10b6-81dd-4896-b893-413a9eff10d0`
- 结果：`completed`
- 章节结果：30/30 完成，失败 0
- 总耗时：约 367 秒
- 正文落盘：30 个被选章节正文均非空
- 报告：`docs/development/runs/run_20260605_091856_section_longtask_30_real.md`

## 验证命令

```bash
python3 -m py_compile backend/db/supabase_repo.py backend/db/postgres_compat.py backend/tasks/celery_app.py backend/tasks/section_tasks.py scripts/smoke_key_flow.py
PYTHONPATH=. .venv/bin/pytest tests/test_section_generation_autoresume.py tests/test_smoke_key_flow_script.py tests/test_postgres_schema_init.py
PYTHONPATH=. .venv/bin/python scripts/smoke_key_flow.py --help
```

## 验证结果

- 针对性测试：17 passed。
- Python 编译检查通过。
- `smoke_key_flow.py --help` 已显示 `--section-count` 参数。
- 当前真实库 reconciler 执行无误伤。

## 部署注意

- 自动周期执行 reconciler 需要启动 Celery beat，或在部署平台配置等价 cron 调用 `bid.sections.reconcile_stale_tasks`。
- 默认阈值：
  - `SECTION_GEN_RECONCILE_INTERVAL_SECONDS=60`
  - `SECTION_GEN_RECONCILE_MAX_AGE_SECONDS=1800`
  - `SECTION_GEN_RECONCILE_LIMIT=100`

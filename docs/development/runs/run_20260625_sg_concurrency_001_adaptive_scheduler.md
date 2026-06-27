# 2026-06-25 本地回归：SG-CONCURRENCY-001 自适应并发调度与任务级慢流窗口降档

## 范围

- P0：`SG-CONCURRENCY-001`
- 目标：批量章节生成不再固定 3 路补位，而是根据任务最近窗口的成功、慢流和超时情况动态决定补位并发。
- 本轮不做前端可视化改造；前端可读取任务 metadata 中的调度状态。

## 变更

- 新增 `backend/services/section_generation_policy.py`：
  - `resolve_section_generation_concurrency(task, max_concurrency=...)` 统一计算调度窗口；
  - 默认最大并发仍由 `SECTION_GEN_CONCURRENCY` 控制，policy 初始窗口为 2；
  - 最近 2 个慢流或模型流超时降为 1；
  - 最近 5 个稳定完成恢复到最大并发；
  - 升并发受 `BID_SECTION_ADAPTIVE_INCREASE_HOLD_SECONDS` 保持期限制，避免频繁抖动；
  - 支持 `BID_SECTION_ADAPTIVE_CONCURRENCY_ENABLED=false` 或 task metadata `scheduler_policy=fixed` 关闭自适应。
- `backend/tasks/section_tasks.py` 的 `_dispatch_next_sections()` 改为先调用 policy，再按 `current_concurrency - running_count` 租约补位。
- 任务级 metadata 写入 `scheduler_policy`、`current_concurrency`、`max_concurrency`、`recent_slow_count`、`slow_stream_count`、`timeout_count`、`last_policy_change` 和 `policy_message`。
- `MODEL_STREAM_SLOW_TIMEOUT` 进入 partial 时补充 `partial_reason=slow_stream`、`next_action=auto_resume_with_slim_prompt` 和 `retry_policy`。
- `requeue_bid_generation_task_item()` 改为保留原 item metadata 后再追加 `retry_reason`，避免 partial 续写时丢失慢流历史。
- 新增 `patch_bid_generation_task_metadata()`，只 patch `bid_generation_tasks.metadata`，不改表结构。

## 验证

| 验收项 | 结果 |
| --- | --- |
| 编译检查 | `.venv/bin/python -m py_compile backend/services/section_generation_policy.py backend/tasks/section_tasks.py backend/db/supabase_repo.py` 通过 |
| 自适应 policy/调度单测 | `tests/test_section_generation_policy.py tests/test_section_generation_autoresume.py` 13 passed |
| 章节/API 回归 | `tests/test_api_sections.py tests/test_section_generation_policy.py tests/test_section_generation_autoresume.py tests/test_section_prompt_policy.py tests/test_length_settings.py tests/test_postgres_schema_init.py` 35 passed |
| DOCX/Celery 导出单测 | `tests/test_docx_export.py tests/test_celery_export_tasks.py` 48 passed |
| 本地 RAG 门禁 | `scripts/rag/run_local_rag_gate.py --run-id run_20260625_sg_concurrency_001` PASS |
| 服务 ready | `/api/ready` 返回 `status=ok`，Celery `workers=1` |
| 临时数据清理 | `regression_case=sg_concurrency_001` 的临时章节剩余 0；`metadata.regression_case like sg_concurrency_001%` 的测试任务行剩余 0 |

## 真实初始窗口回归

真实任务：

```text
project_id=628ed517-0c31-44ea-a5cb-95b25db06fc2
task_id=98ad8494-ba70-40c7-8856-f01c77db2cc9
```

结果：

| 字段 | 值 |
| --- | --- |
| task_status | `completed` |
| item_status | 4 个 item 均为 `done` |
| scheduler_policy | `adaptive_v1` |
| current_concurrency | `2` |
| max_concurrency | `3` |
| policy_message | `采用 2 路自适应初始并发，持续观察模型吞吐` |
| prompt_profile | 4 个 item 均为 `simple_plan` |
| slow_stream_count / timeout_count | `0 / 0` |

结论：最大并发为 3 时，初始补位窗口按 policy 控制为 2 路，并在任务 metadata 中可观测。

## 真实慢流降档回归

真实任务：

```text
project_id=628ed517-0c31-44ea-a5cb-95b25db06fc2
task_id=3881462f-e18f-4aa3-88d7-965d740f0b97
```

构造方式：

- 通过真实 API 创建 4 个 item 的批量任务，`autoStart=false`。
- 通过真实 PATCH 接口将前 2 个 item 标为 `partial_generated`，metadata 写入 `slow_stream=true`、`timeout_code=MODEL_STREAM_SLOW_TIMEOUT`。
- 投递真实 Celery 协调任务。

关键观测：

| 字段 | 值 |
| --- | --- |
| first_policy_current_concurrency | `1` |
| first_policy_change | `reduce_concurrency` |
| recent_slow_count | `2` |
| slow_stream_count / timeout_count | `2 / 2` |
| policy_message | `最近章节多次慢流或超时，已自动降为单路续写` |
| 初次补位结果 | 1 个 item `generating`，1 个 item 保持 `queued` |
| 自动续写 metadata | partial item 重新排队后仍保留 `timeout_code=MODEL_STREAM_SLOW_TIMEOUT` 与 `retry_reason=auto_resume_partial` |

结论：任务级连续慢流后，调度器会降为单路补位；partial 续写不再丢失慢流历史。

## RAG 门禁指标

产物：

```text
docs/rag/runs/run_20260625_sg_concurrency_001_summary.md
docs/rag/runs/run_20260625_sg_concurrency_001_incremental_summary.md
```

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 239 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 580 ms | 27 |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 340 ms | 0 |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 712 ms | 30 |

真实 stream 抽样：`done=true`，contexts=5，assets=4，images=4。

## 结论

`SG-CONCURRENCY-001` 本地实现并通过单测、真实初始窗口、真实慢流降档、DOCX/Celery 导出单测和 RAG 门禁。系统已能在模型输出变慢时自动收窄补位窗口，同时在稳定状态保留恢复并发的策略基础。

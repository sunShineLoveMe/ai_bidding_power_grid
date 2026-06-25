# 2026-06-25 本地回归：SG-SLOW-001 慢流提前保护与 partial 草稿释放并发槽

## 范围

- P0：`SG-SLOW-001`
- 目标：章节流式输出低吞吐时，不再等满 300 秒 wall timeout；提前保存 partial 草稿、记录慢流指标、释放当前生成槽。
- 本轮不做全局自适应并发降档；并发 policy 继续进入下一项 P0。

## 变更

- `section_writer.stream_bid_section()` 增加 `_SectionStreamMonitor`：
  - 记录首 token 延迟、stream 字符数、chars/min、60/90 秒字符里程碑；
  - 支持配置 `SECTION_STREAM_SLOW_CHECK_SECONDS`、`SECTION_STREAM_MIN_CHARS_AT_SLOW_CHECK`、`SECTION_STREAM_FIRST_TOKEN_SLOW_SECONDS`；
  - 按 profile 调整默认最小字符阈值：`simple_plan=180`、`structured_table=160`、`price_sensitive/attachment/continuation=120`、技术/事实类默认 `250`；
  - 低吞吐时抛出 `MODEL_STREAM_SLOW_TIMEOUT`。
- `LLMStreamTimeoutError` 增加可选 `metadata`，保留向后兼容。
- `generate_and_save_bid_section()` 透传 `stream_metric` 和 `timeout` metadata。
- Celery `generate_one_section()` 处理 `stream_metric/timeout` 事件，把慢流指标写入 item metadata；`MODEL_STREAM_SLOW_TIMEOUT` 进入 `partial_generated`，文案显示“模型输出较慢，已提前保存草稿”。
- `section_generation.py` 对 `backend.api.routes` 的图片 helper 改为函数内懒加载，修复直接导入 service 时的循环导入隐患。

## 验证

| 验收项 | 结果 |
| --- | --- |
| 编译检查 | `.venv/bin/python -m py_compile backend/ai/qwen_client.py backend/ai/section_writer.py backend/services/section_generation.py backend/tasks/section_tasks.py` 通过 |
| 慢流/续写单测 | `tests/test_section_generation_autoresume.py tests/test_section_prompt_policy.py` 13 passed |
| 章节/API 相关回归 | `tests/test_api_sections.py tests/test_section_generation_autoresume.py tests/test_section_prompt_policy.py tests/test_length_settings.py tests/test_postgres_schema_init.py` 30 passed |
| DOCX/Celery 导出单测 | `tests/test_docx_export.py tests/test_celery_export_tasks.py` 48 passed |
| 本地 RAG 门禁 | `scripts/rag/run_local_rag_gate.py --run-id run_20260625_sg_slow_001` PASS |
| 临时章节清理 | `regression_case in ('sg_slow_001','sg_slow_001_normal')` 剩余 0 |

## 真实慢流回归

临时 worker 配置：

```text
CELERY_WORKER_CONCURRENCY=1
SECTION_GEN_CONCURRENCY=1
SECTION_STREAM_SLOW_CHECK_SECONDS=1
SECTION_STREAM_MIN_CHARS_AT_SLOW_CHECK=999999
SECTION_STREAM_FIRST_TOKEN_SLOW_SECONDS=0.5
```

真实任务：

```text
project_id=628ed517-0c31-44ea-a5cb-95b25db06fc2
section_id=3fc49033-0090-4274-869b-12b74248e027
task_id=29c99120-38e9-4b3d-a67c-5eef6925dbd3
```

结果：

| 字段 | 值 |
| --- | --- |
| task_status | `partial_failed` |
| item_status | `partial_generated` |
| message | `模型输出较慢，已提前保存草稿，待续写或人工复核。` |
| timeout_code | `MODEL_STREAM_SLOW_TIMEOUT` |
| first_token_latency_ms | `10157` |
| stream_elapsed_ms | `10157` |
| stream_chars | `2` |
| chars_per_minute | `11.81` |
| partial_chars / partial_words | `27 / 11` |
| slow_stream_reason | `elapsed_10s_chars_2_below_999999` |

临时章节已通过 API 删除，`deleted_count=1`。

## 正常阈值回归

默认 worker 配置：

```text
CELERY_WORKER_CONCURRENCY=4
SECTION_GEN_CONCURRENCY=3
SECTION_STREAM_SLOW_CHECK_SECONDS=90
```

真实任务：

```text
project_id=628ed517-0c31-44ea-a5cb-95b25db06fc2
section_id=16d1622b-fa7a-427a-9f37-9c1664cab043
task_id=41b912db-3d7a-4ca5-b8aa-1e64dbfcfe66
```

结果：

| 字段 | 值 |
| --- | --- |
| task_status | `completed` |
| item_status | `done` |
| message | `已完成` |
| slow_stream | `false` |
| first_token_latency_ms | `2102` |
| stream_elapsed_ms | `6654` |
| stream_chars | `589` |
| chars_per_minute | `5310.62` |
| min_chars_at_slow_check | `180` |

临时章节已通过 API 删除，`deleted_count=1`。

## RAG 门禁指标

产物：

```text
docs/rag/runs/run_20260625_sg_slow_001_summary.md
docs/rag/runs/run_20260625_sg_slow_001_incremental_summary.md
```

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 242 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 594 ms | 27 |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 344 ms | 0 |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 706 ms | 30 |

真实 stream 抽样：`done=true`，contexts=5，assets=4，images=4。

## 结论

`SG-SLOW-001` 本地实现并通过单测、真实强制慢流、真实正常生成、DOCX/Celery 导出单测和 RAG 门禁。系统已能在低吞吐章节上提前保存草稿并释放生成槽，不再把这类章节常规性拖到 300 秒 wall timeout。下一项 P0 进入自适应并发调度。

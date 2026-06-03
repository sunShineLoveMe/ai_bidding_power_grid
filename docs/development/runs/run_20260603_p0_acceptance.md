# 2026-06-03 P0 正文生成链路总体验收记录

## 范围

本次验收覆盖 P0-01 到 P0-07 的基础版闭环：

- P0-01 任务状态模型。
- P0-02 item 独立表。
- P0-03 worker lease / heartbeat。
- P0-04 草稿与最终落盘边界。
- P0-05 模型流超时保护。
- P0-06 取消、恢复、重试。
- P0-07 叶子小节级正文生成。

## 环境

- 后端：`http://127.0.0.1:8000`。
- Redis：`redis://127.0.0.1:16379/0`。
- Celery：`backend.tasks.celery_app.celery_app`，`--concurrency=3`。
- 数据库：真实 Postgres/Supabase 兼容层。
- 模型：真实 DeepSeek 流式正文生成，未使用 mock。
- 项目：`70323ce8-f18e-46ca-8d22-33865525a7f7`。

验收前检查：

```text
/api/health -> {"status":"ok"}
celery active/reserved/scheduled -> empty
bid_sections total=74, containers=22, leaves=52
```

## 真实 3 叶子小节生成

任务：

```text
task_id=15449164-3a97-429c-a2e0-51b9565b180c
mode=p0_acceptance_3_leaf_sections
```

输入小节：

```text
97c1df09-2488-4d64-8f4d-22e1161f7a8a  投标函及投标函附录 - 编制依据  target=1000
34a951aa-c52d-4516-8d82-0a8bd30604a8  投标函及投标函附录 - 工程概况  target=1000
dac5cffc-d20c-4b28-9454-b6a41cdcc341  投标函及投标函附录 - 总体部署  target=1000
```

轮询过程：

```text
0.0s   queued=3 running=0 done=0
2.0s   queued=0 running=3 done=0
6.1s   3 个 item 均 generating，并开始产生 chars
16.2s  done=1 running=2
20.2s  done=2 running=1，最后一个 item 进入 saving
22.2s  task=completed, done=3, failed=0
```

最终任务汇总：

```text
status=completed
total_count=3
queued_count=0
running_count=0
done_count=3
failed_count=0
stopped_count=0
metadata.leaf_generation_only=true
requested_item_count=3
effective_item_count=3
```

## item 表验收

```text
投标函及投标函附录 - 编制依据
status=done, attempt=1, percent=100, chars=1259, error=null, final_saved_at=2026-06-03T22:13:28+08:00

投标函及投标函附录 - 工程概况
status=done, attempt=1, percent=100, chars=1714, error=null, final_saved_at=2026-06-03T22:13:32+08:00

投标函及投标函附录 - 总体部署
status=done, attempt=1, percent=100, chars=1423, error=null, final_saved_at=2026-06-03T22:13:33+08:00
```

每个 item 均写入 `attempt_id`、`worker_id`、`lease_expires_at`，证明 P0-01/P0-02/P0-03 的基础链路生效。

## 正文落库验收

```text
投标函及投标函附录 - 编制依据
bid_sections.status=generated, content_chars=1635, generation_status=generated, writing_status=generated

投标函及投标函附录 - 工程概况
bid_sections.status=generated, content_chars=2068, generation_status=generated, writing_status=generated

投标函及投标函附录 - 总体部署
bid_sections.status=generated, content_chars=1799, generation_status=generated, writing_status=generated
```

这证明 P0-04 的正常完成路径已经明确：只有完成模型流并进入保存阶段后，章节才标记为最终 `generated`。

## 事件链验收

事件计数：

```text
task_created=1
item_dispatched=3
worker_started=3
heartbeat=6
progress_flushed=220
saving=6
final_saved=3
```

事件链覆盖：

```text
task_created -> item_dispatched -> worker_started -> heartbeat -> progress_flushed -> saving -> final_saved
```

这证明 P0-01/P0-02/P0-03/P0-04 的关键状态可审计。

## AI 调用验收

```text
97c1df09... success=true, error_code=null, total_tokens=3336, total_cost=0.004616
34a951aa... success=true, error_code=null, total_tokens=3207, total_cost=0.004657
dac5cffc... success=true, error_code=null, total_tokens=3340, total_cost=0.004924
```

## P0-05/P0-06/P0-07 复用证据

- P0-05 模型流超时保护见：`docs/development/runs/run_20260603_model_stream_timeout.md`。
- P0-06 取消、恢复、重试见：`docs/development/runs/run_20260603_retry_resume_cancel.md`。
- P0-07 叶子小节级目录拆分与落库见：`docs/development/runs/run_20260603_leaf_section_generation.md`。

## 验收后检查

```text
celery active/reserved/scheduled -> empty
```

没有遗留正文生成任务。

## 结论

P0 基础版验收通过。当前链路已经具备：

- 叶子小节级任务输入。
- 明确任务状态。
- item 独立表。
- worker lease / heartbeat。
- 事件审计。
- 模型超时保护与 partial 草稿状态。
- 单 item 重试 / task 恢复 / 取消同步。
- 正常完成路径的最终正文可靠落库。

仍建议后续在 P1 完成：

- 前端任务详情/诊断面板。
- Celery task id 记录和 revoke 增强。
- RAG/rerank 降级状态可视化。
- 章节 metadata 反查 task_id / attempt_id。

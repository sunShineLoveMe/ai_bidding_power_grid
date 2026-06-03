# 真实生产链路章节生成测试记录：单章节

日期：2026-06-03

目标：不使用 mock，连接真实后端、真实 Redis/Celery、真实数据库和真实 LLM，模拟生产环境测试单章节正文生成链路。

测试范围：仅测试 1 个真实章节，避免直接触发 69 章全文生成。

## 结论

本次真实单章节任务完成，但暴露出两个必须整改的问题：

1. 任务状态显示 `completed/done`，正文内容也写入了 `bid_sections.content`，但章节主状态仍然是 `failed`，metadata 中 `generation_status/writing_status` 也仍为 `failed`。
2. 任务生成了新正文 chunk，但 `ai_usage_logs` 没有记录本次 DeepSeek `bid_section_stream` 写作调用；只记录了 embedding 和 qwen3-rerank。原因高度疑似早保存逻辑提前 `break` 流式 generator，导致 DeepSeek stream 的成功日志没有执行。

因此，这次测试不能判定“生产链路完全可用”。它证明了 Celery/Redis/DB/LLM 流式产出链路可以跑通单章节，但最终状态一致性和 AI 调用审计仍不合格。

## 环境状态

| 检查项 | 结果 |
| --- | --- |
| 后端 Gunicorn | 通过 |
| 前端 Vite | 通过 |
| Redis TCP | 通过 |
| Celery worker | 通过 |
| Celery 并发 | 3 |
| Celery broker/result | `redis://127.0.0.1:16379/0` |
| 登录鉴权 | 真实注册/登录获取 token |
| LLM mock | 未使用 |

## Celery 启动记录

启动命令：

```bash
set -a; source .env; set +a
.venv/bin/celery -A backend.tasks.celery_app.celery_app worker --loglevel=INFO --concurrency=3
```

启动结果：

```text
app: ai_bidding
transport: redis://127.0.0.1:16379/0
results: redis://127.0.0.1:16379/0
concurrency: 3 (prefork)
tasks:
  . bid.sections.generate_one
  . bid.sections.generate_task
celery@chrisdeMacBook-Pro.local ready.
```

注意：worker 启动后立刻收到了若干 Redis 中残留的历史 `bid.sections.generate_one` 消息。随后 `inspect active` 显示 active 为空，未继续占用 worker。

## 真实测试任务

项目：

```text
70323ce8-f18e-46ca-8d22-33865525a7f7
03_必须招标的工程项目规定_a8122eb9
```

章节：

```text
section_id: dd5df283-8267-43a6-89d4-ffc05b5cb37b
title: 单价分析表
target_words: 1600
```

创建任务结果：

```text
task_id: 4f528999-e504-4423-9801-3319767f108b
initial status: queued
total_count: 1
```

## 状态轮询结果

轮询输出：

```json
{"t":0,"task_status":"running","queued":0,"running":1,"done":0,"failed":0,"item_status":"generating","percent":88,"chars":1418,"message":"正在编写","error":null}
{"t":1,"task_status":"completed","queued":0,"running":0,"done":1,"failed":0,"item_status":"done","percent":100,"chars":1537,"message":"已完成","error":null}
```

最终任务表：

```text
id: 4f528999-e504-4423-9801-3319767f108b
status: completed
total_count: 1
queued_count: 0
running_count: 0
done_count: 1
failed_count: 0
stopped_count: 0
finished_at: 2026-06-03 17:07:50.288779+08
```

item 最终状态：

```text
item_status: done
message: 已完成
chars: 1537
saved_section_id: dd5df283-8267-43a6-89d4-ffc05b5cb37b
started_at: 2026-06-03T09:07:33.731819
finished_at: 2026-06-03T09:07:50.288779
```

## 正文落库检查

`bid_sections.content` 已写入新正文：

```text
content_len: 1567
content_preview:
## 单价分析表

### 单价分析表

#### 一、编制说明

本单价分析表依据招标文件、设计图纸、现行电力工程预算定额及费用定额，并结合本项目实际情况及企业自身施工管理水平进行编制...
```

但章节主状态仍异常：

```text
status: failed
generation_status: failed
writing_status: failed
actual_words: 916
target_words: 1600
```

这说明任务 item 和正文 content 写入成功，但章节级状态没有正确恢复为 generated。

## AI 调用日志检查

17:07 之后新增 AI 日志：

```text
17:07:34 local_openai_compatible qwen3-embedding success latency=1033ms
17:07:35 dashscope qwen3-rerank success latency=593ms
```

未发现 17:07 本次任务对应的 DeepSeek 写作日志：

```text
provider=deepseek
stage=bid_section_stream
section_id=dd5df283-8267-43a6-89d4-ffc05b5cb37b
```

结合任务 chunk_events 已产生大量 17:07 时间戳的正文 chunk，判断 DeepSeek 流式内容已经产出，但由于当前早保存逻辑提前中断 generator，`_stream_deepseek_api` 中流式成功后的 `record_ai_usage_log(...)` 没有机会执行。

## 发现的问题

### P0：任务完成与章节状态不一致

现象：

```text
bid_generation_tasks.status = completed
item.status = done
bid_sections.content 已更新
bid_sections.status = failed
metadata.generation_status = failed
metadata.writing_status = failed
```

影响：

- 前端可能仍把章节显示为失败。
- 合规检查、导出、目录状态可能误判。
- 用户看到“任务完成”但章节仍是失败，信任感很差。

建议：

- `save_generated_section` 必须确保章节主状态和 metadata 状态一起更新为 generated。
- 保存成功后增加断言或回读校验。
- 任务 item `done` 必须以章节状态同步成功为前提。

### P0：DeepSeek 流式调用缺少审计日志

现象：

- 真实生成过程中产生 chunk。
- 但 `ai_usage_logs` 没有记录本次 DeepSeek 写作调用。

影响：

- 无法准确统计成本。
- 无法证明模型是否调用成功。
- 出问题时无法定位模型耗时、token 和错误。

建议：

- 不要用 `break` 提前关闭 provider stream 作为早保存机制。
- 如果必须提前终止，应显式记录一条 `success=false/partial=true/early_stopped=true` 的 AI usage log。
- 更好的方案是草稿保存不打断模型流，最终由超时/完成条件决定终止。

### P1：历史 active 任务记录残留

测试前数据库中仍有旧任务处于 `queued/running`：

```text
active_items: 18
task_count: 18
```

影响：

- `latest` 接口和前端恢复状态可能被历史任务干扰。
- 用户可能看到旧任务仍在运行。

建议：

- 增加任务 reconciler，将长期无 heartbeat 的旧任务标记为 expired/cancelled。
- 前端恢复任务时过滤过期任务。

## 本次测试是否消耗 LLM/RAG 额度

消耗了真实 RAG 相关调用：

- qwen3-embedding
- qwen3-rerank

DeepSeek 写作是否计费需要在 DeepSeek 平台侧确认。应用本地 `ai_usage_logs` 未记录本次 DeepSeek 写作调用，这是本次发现的问题之一。

## 下一步建议

不要立即跑 69 章全文生成。先修复：

1. 保存成功后章节状态仍 failed 的问题。
2. 早保存中断 stream 导致 DeepSeek usage log 缺失的问题。
3. 历史 active 任务无 heartbeat 回收的问题。

修复后再按以下顺序压测：

1. 单叶子小节。
2. 3 个叶子小节并发。
3. 10 个叶子小节。
4. 全量目录叶子小节。

## 保存逻辑复查与修复记录

追加时间：2026-06-03 17:16

### 根因

保存状态不一致的直接根因是应急早保存逻辑：

```text
Celery on_event/flush_progress 达到早保存阈值
  -> 调用 save_generated_section 写入 content/generated
  -> 抛出 SectionGenerationSuperseded 作为控制流退出
  -> 异常穿过 generate_and_save_bid_section
  -> generate_and_save_bid_section 的 except Exception 将其当成失败
  -> mark_section_generation_failed 覆盖 bid_sections.status 和 metadata 为 failed
```

DeepSeek usage log 缺失的直接根因也是同一条路径：早保存提前 `break` / 关闭 provider stream，导致 `_stream_deepseek_api` 中流式成功后的 `record_ai_usage_log(...)` 没有执行。

### 修复

已调整：

- 移除 Celery flush 中“达到阈值即保存并标记 done”的应急路径。
- 移除 service 层 `generate_and_save_bid_section` 中早保存 `break` provider stream 的逻辑。
- service 层仅在模型正常结束并收到 `done` 后保存最终正文。
- 成功保存时将 `writing_error` 置空，避免旧失败原因残留。
- 如果已经成功保存，后续异常不会再把章节覆盖为 failed。

### 修复后真实复测 1

章节：

```text
section_id: 60f4be2c-5f58-4048-a652-4287ef537c38
title: 主要材料价格表
task_id: 7af0b351-1cc1-4ad8-9f50-ebad5f7d36ec
```

结果：

```text
bid_generation_tasks.status = completed
item.status = done
bid_sections.status = generated
metadata.generation_status = generated
metadata.writing_status = generated
DeepSeek bid_section_stream usage log = recorded
```

DeepSeek 日志：

```text
provider: deepseek
model: deepseek-v4-flash
stage: bid_section_stream
section_id: 60f4be2c-5f58-4048-a652-4287ef537c38
success: true
latency_ms: 22029
input_tokens: 2461
output_tokens: 2022
total_tokens: 4483
```

遗留发现：该轮修复前尚未清空旧 `writing_error`，随后已补充修复。

### 修复后真实复测 2

章节：

```text
section_id: 4f7d35e7-b908-49a1-a053-e3980aee8516
title: 其他项目清单报价
task_id: 56d5383f-d3af-40d1-b659-99aa51c09b61
```

结果：

```text
bid_generation_tasks.status = completed
item.status = done
bid_sections.status = generated
metadata.generation_status = generated
metadata.writing_status = generated
metadata.writing_error = null
content_len = 2713
actual_words = 1571
```

DeepSeek 日志：

```text
provider: deepseek
model: deepseek-v4-flash
stage: bid_section_stream
section_id: 4f7d35e7-b908-49a1-a053-e3980aee8516
success: true
latency_ms: 15858
input_tokens: 2819
output_tokens: 1701
total_tokens: 4520
```

### 当前判断

单章节最终保存链路已恢复一致：

```text
任务完成 -> item done -> 正文 content 写入 -> 章节 status generated -> metadata generated -> DeepSeek usage log 可审计
```

仍不建议直接跑 69 章全文。下一步应继续处理：

- 长章节拆叶子小节生成。
- worker heartbeat/lease 过期回收。
- 历史 queued/running 任务清理。
- 3 个叶子小节并发真实压测。

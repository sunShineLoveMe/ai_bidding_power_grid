# Run 20260617 - 招标 AI 解读报告写回修复

## 背景

真实项目 `4390e1ff-2d62-4230-802a-b5dc829145f2` 在生成“招标解读 / 资格 / 评分 / 风险”时，DeepSeek 分段解读和最终 merge 均已成功，但接口最终返回 500：

```text
生成 AI 深度解读报告失败: AI 解读报告写回 Supabase 失败
```

## 根因

失败不在模型调用阶段，而在 `backend/ai/interpreter.py` 最后的 `bid_analysis.project_meta` 写回阶段。

原逻辑直接按 `bid_analysis.id` 更新并要求 `updated.data` 非空：

```python
get_supabase_client().table("bid_analysis").update(...).eq("id", analysis["id"]).execute()
```

在 PostgreSQL/Supabase 兼容链路中，部分写回路径可能更新成功但返回空 representation。原代码把“返回体为空”直接当作写回失败，导致模型已经完成仍返回 500。

## 修复

- `backend/ai/interpreter.py`
  - AI 解读报告持久化改为统一调用 `update_bid_analysis_project_meta(project_id, project_meta)`。
  - 不再直接依赖 `analysis["id"]` 和单次 update 返回体。

- `backend/db/supabase_repo.py`
  - `update_bid_analysis_project_meta` 在 update 返回空 data 时，会 re-select 当前 `project_meta`。
  - 若读回内容与目标内容一致，则视为写回成功。

- `frontend/src/api/bidProject.ts`
  - `generateAIInterpretation` 超时从 360 秒调整到 900 秒。
  - 当前真实大文件首跑为 14 个 segment + 1 个 merge，耗时接近 5-6 分钟，360 秒过于贴边。

## 真实验证

### 单元测试

```bash
.venv/bin/python -m pytest tests/test_segmented_interpreter.py tests/test_supabase_repo.py tests/test_bid_prefill.py
```

结果：

```text
7 passed
```

### 真实数据库写回探针

对真实项目 `4390e1ff-2d62-4230-802a-b5dc829145f2` 执行可回滚写回探针：

- 临时写入 `project_meta._writeback_probe`
- 读回确认
- 恢复原始 `project_meta`

结果：

```text
probe_pass=true
restored=True
```

### 真实 AI 解读结果

本次真实接口触发后，后端最终完成并写入 `ai_report`：

```text
has_ai_report=True
generation={
  "mode": "segmented",
  "segment_count": 14,
  "document_chunk_count": 42,
  "segment_failure_count": 0,
  "segment_success_count": 14
}
```

最近一次真实模型调用记录：

| stage | model | success | latency_ms | total_tokens |
| --- | --- | --- | ---: | ---: |
| ai_interpretation_merge | deepseek-v4-pro | true | 99582 | 46356 |
| ai_interpretation_segment | deepseek-v4-flash | true | 3541-39780 | 12952-19640 |

## 结论

写回 500 已修复。当前首跑耗时仍然较长，这是同步接口架构问题，不是本次写回 bug。短期通过缓存和前端超时放宽降低失败概率；中期应把 AI 解读生成迁移为后台任务，复用现有 task/status 轮询模式，避免用户页面长时间等待。

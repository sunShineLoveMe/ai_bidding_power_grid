# P0-08 / P0-09 自动续写与草稿闭环整改记录

日期：2026-06-04

范围：

- P0-08 `partial_failed` 自动续写与批量恢复闭环。
- P0-09 草稿正文可见、续写、采纳闭环。

## 背景

真实“一键生成全文”复测中，批量任务出现 `partial_failed`：

- 部分 item 进入 `partial_generated`。
- item 中存在 `generated_content` / `draft_content`，但任务进入终态后不会自动续写。
- 前端显示“草稿已保存”，但用户对草稿的查看、续写、采纳路径不完整。

## 本次改动

### P0-08

- `backend/tasks/section_tasks.py`
  - `_dispatch_next_sections` 在没有 queued/running item 且存在 `partial_generated` 时，会自动 requeue 未超过最大续写次数的 partial item。
  - 默认最大自动续写 attempt 为 3。
  - 自动续写保留 draft，不清空 `draft_content` / `generated_content`。
  - worker 构造章节 metadata 时注入 `continuationDraft`。
  - worker 进度缓冲从已有草稿开始，续写 chunk 会追加到草稿后。

- `backend/ai/section_writer.py`
  - 新增 continuation prompt。
  - 当 `generation_options.continuationDraft` 存在时，不走普通章节 prompt，改为“只输出可追加到草稿末尾的续写内容”。

- `backend/services/section_generation.py`
  - 保存正文的 `full_content` 从 continuation draft 开始，避免最终正文只保存续写片段。

### P0-09

- `frontend/src/api/bidProject.ts`
  - 补齐 `draft_content`、`draft_saved_at`、`final_saved_at` 类型字段。

- `frontend/src/pages/BidEditor/index.tsx`
  - 应用任务内容时优先使用 `draft_content`，再 fallback 到 `generated_content`。
  - partial item 按钮文案显示为“续写”。
  - partial 章节更多菜单增加“采纳草稿为正文”。
  - 采纳草稿后调用章节保存接口，并同步任务 item 为 `done`。

## 验证

已执行：

```bash
.venv/bin/python -m unittest tests.test_section_generation_autoresume tests.test_api_sections
```

结果：通过，9 个测试 OK。

已执行：

```bash
cd frontend
npm run build
```

结果：通过。Vite 仅提示现有 chunk size warning。

新增测试：

- `tests/test_section_generation_autoresume.py`
  - 验证一轮结束后 `partial_generated` item 会被自动 requeue 并派发。
  - 验证存在 continuation draft 时，章节写作走 continuation prompt，而不是普通 prompt。

## 当前限制

- 本次未执行真实 DeepSeek 全量 69 章验收。原因是当前运行中的 Celery worker 需要重启后才能加载本次代码修改。
- 基础版没有新增 `resuming_partial` / `completed_with_drafts` 任务状态，避免数据库枚举兼容风险；当前仍通过 requeue 后的 `running` 状态表达自动续写中。
- “采纳草稿”当前保存章节为 `edited` 状态，尚未写入 `generation_status=accepted_draft` metadata。该审计增强需要后端保存接口支持 metadata patch。

## 后续真实验收建议

1. 重启 Celery worker 和前端 Vite。
2. 选择一个真实项目，使用较低 `BID_SECTION_STREAM_WALL_TIMEOUT_SECONDS` 触发 partial 场景，验证 partial item 自动进入下一轮续写。
3. 再恢复正常超时配置，跑 3 个叶子小节真实 DeepSeek 测试。
4. 最后执行完整“上传招标文件 -> 解析 -> 解读 -> 大纲 -> 一键生成全文”链路。

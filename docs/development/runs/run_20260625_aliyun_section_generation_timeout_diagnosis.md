# 2026-06-25 阿里云批量章节生成卡住诊断

## 背景

客户在阿里云测试环境执行全文批量编写，前几章 DeepSeek 写作速度较快，生成到后半段后页面长期显示“正在编写/排队中”，体感为任务卡死。

测试环境：

- 地址：`http://8.160.187.226:8080`
- 项目：`d346ec62-8843-4cfd-b68c-e3fb1d215181`
- 最新批量任务：`952fb458-25fa-49b6-bb40-e600d22da975`

## 线上任务快照

第一次快照：

```json
{
  "status": "running",
  "total_items": 144,
  "counts": {
    "done": 76,
    "partial_generated": 58,
    "generating": 3,
    "queued": 7
  },
  "metadata": {
    "mode": "batch_sections",
    "leaf_generation_only": true,
    "skipLengthSupplement": true,
    "requested_item_count": 144,
    "effective_item_count": 144
  }
}
```

15 秒后二次快照：

```json
{
  "status": "running",
  "counts": {
    "done": 76,
    "partial_generated": 59,
    "generating": 3,
    "queued": 6
  }
}
```

说明 worker 没有死锁，调度仍在推进；问题是每个后续章节都在极慢输出后触发超时，用户看到的是“每章卡 5 分钟再半成品”。

## 关键证据

大量后半段章节错误一致：

```text
MODEL_STREAM_WALL_TIMEOUT: 模型流式输出超过单章节最大时长 300 秒，已停止继续等待。
```

统计结果：

```json
{
  "done_count": 76,
  "done_avg_chars": 1138.0,
  "last_done_order": 105,
  "partial_count": 59,
  "partial_avg_chars": 283.0,
  "partial_minmax_chars": [173, 1603],
  "first_partial_order": 104
}
```

活跃章节示例：

```json
[
  {
    "order_index": 175,
    "title": "总体部署",
    "status": "generating",
    "percent": 10,
    "chars": 109,
    "message": "正在编写"
  },
  {
    "order_index": 176,
    "title": "组织机构",
    "status": "generating",
    "percent": 7,
    "chars": 81,
    "message": "正在编写"
  },
  {
    "order_index": 177,
    "title": "实施方法",
    "status": "generating",
    "percent": 3,
    "chars": 32,
    "message": "正在编写"
  }
]
```

这些章节仍有 token 输出，但输出吞吐极低。

## 对“上下文越来越大”的判断

本次排查不支持“每次把前面已生成全部正文都带给 DeepSeek，所以越到后面越慢”这个判断。

代码证据：

- 前端创建批量任务时，每个 item 只提交 `section_id/title/order_index/volume_type/target_words`。
- 后端 `build_section_prompt()` 没有拼接前面已生成章节正文。
- 批量任务 metadata 带 `skipLengthSupplement=true`，首轮批量生成不会额外调用篇幅补写。
- 首轮 fresh generation 的 `continuationDraft` 为空，不会带已有草稿；只有自动续写 partial 草稿时才会带草稿节选。

但用户的怀疑有一部分合理：单章 prompt 本身并不小，固定包含企业画像、泰昌核验事实、用户确认变量、企业资料候选、章节级 RAG 依据、响应要点、评分项和风险项。也就是说问题不是“全书上下文累积”，而是“每章固定重上下文 + 3 路长期连续流式生成 + DeepSeek 吞吐下降/服务端节流”共同触发。

## 初步根因

1. 线上批量生成默认 3 路并发，持续对 DeepSeek 发起长文本流式写作。
2. DeepSeek 在任务后半段未直接返回 429，但流式 token 吞吐明显下降。
3. 系统只有 45 秒 idle timeout 和 300 秒 wall timeout；只要持续有少量 token，idle timeout 不触发，worker 会一直等到 300 秒。
4. 一旦已经产生过 token，代码不会重试 DeepSeek，只会保存 partial 草稿。
5. 前端对 `partial_generated` 展示为“草稿待续写”，但客户在目录模式看到多个“正在编写/排队中”，体感像卡死。

## 当前结论

这不是单纯的前端展示问题，也不是单纯的 DeepSeek 硬 429 限速；更不是“前文全部塞进上下文”的线性膨胀。

更准确的定性：

> 批量章节生成对 DeepSeek 的长流式调用缺少吞吐自适应保护。持续并发后模型输出变慢，每个章节占满 300 秒超时窗口，导致后半段大量 partial 草稿和客户可见卡顿。

## 立即止血建议

线上测试环境先降低章节并发，避免继续压低 DeepSeek 流式吞吐：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
grep -q '^SECTION_GEN_CONCURRENCY=' .env \
  && sed -i 's/^SECTION_GEN_CONCURRENCY=.*/SECTION_GEN_CONCURRENCY=1/' .env \
  || echo 'SECTION_GEN_CONCURRENCY=1' >> .env

grep -q '^CELERY_WORKER_CONCURRENCY=' .env \
  && sed -i 's/^CELERY_WORKER_CONCURRENCY=.*/CELERY_WORKER_CONCURRENCY=2/' .env \
  || echo 'CELERY_WORKER_CONCURRENCY=2' >> .env

docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml up -d --force-recreate celery-worker
docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml ps celery-worker
```

当前这批任务已经产生大量 partial 草稿，不建议继续让客户等它自动续写。应先停止当前任务，部署修复后重启批量生成，或只对 partial 章节分批重试。

## 代码级修复建议

### P0：批量生成需要吞吐自适应

- 对章节流式输出增加 `min_chars_per_minute` 保护。
- 若 60-90 秒后输出字数低于阈值，提前转为 partial 或切换到低并发重试，而不是占满 300 秒。
- 对同一任务连续 N 个 `MODEL_STREAM_WALL_TIMEOUT` 后自动降并发或暂停调度，提示“模型服务输出过慢，请稍后续写”。

### P0：批量生成默认并发需按模型服务降级

- DeepSeek 线上默认 `SECTION_GEN_CONCURRENCY=1` 或 `2`。
- 只有在实测吞吐稳定时才提升到 3。

### P1：前端状态展示需要区分“正在编写”和“模型输出过慢”

- `partial_generated` 应清晰显示“模型超时，已保存草稿，可续写”，不要让客户误以为仍在写。
- 顶部进度应显示 partial 数量、超时数量和预计剩余时间。

### P1：增加诊断指标

任务 item 应落库：

- `prompt_chars`
- `first_token_latency_ms`
- `tokens_per_minute` 或 `chars_per_minute`
- `model`
- `provider`
- `timeout_code`

目前 `ai_usage_logs` 会记录 input/output，但前端任务页和普通 API 不便直接诊断。

### P1：重试策略需要区别慢流与硬失败

当前逻辑在已经产生 token 后不会重试，这是为了避免重复正文，但会导致大量 200 字 partial。建议：

- 首次慢流且草稿低于目标 30% 时，允许一次“短 prompt 续写重试”。
- 续写 prompt 不再携带完整企业资料候选和 RAG，只带标题、目标、已生成末尾、关键事实摘要。


# AI 用量与成本统计

> 相关代码：`backend/db/supabase_repo.py`（`record_ai_usage_log`）、`backend/api/usage.py`

## Token 用量与成本统计

系统已接入第一版 AI 用量与成本统计，用于评估单次招标解读、章节大纲生成、章节正文生成、知识库检索增强和智能客服问答等流程的大模型调用成本。

### 功能入口

在前端一级菜单进入「用量与成本」可以查看近 30 天统计，并支持按单个标书项目筛选：

- 调用次数
- 输入 Token
- 输出 Token
- 总 Token
- 人民币预估费用
- 模型类型拆分，包括文本模型、向量模型、重排模型和 OCR
- 标书项目成本汇总，按项目展示创建时间、最近调用时间、调用次数、总 Token、人民币成本和项目状态
- 单项目详情弹窗，点击项目行的「查看」后展示该标书项目的成本概览、阶段成本拆分和完整调用明细
- 完整调用明细，包括调用时间、业务阶段、模型、调用类型、Token、输入/输出费用、耗时、成功状态、章节 ID 和是否为估算值

后端接口：

```text
GET /api/bidding/ai-usage?days=30
GET /api/bidding/ai-usage?days=30&projectId=<project_id>
GET /api/bidding/settings/ai-usage?days=30
GET /api/bidding/settings/ai-usage?days=30&projectId=<project_id>
```

### 当前统计范围

| 调用类型 | 统计来源 | 成本口径 |
| --- | --- | --- |
| DeepSeek 文本生成 | OpenAI-compatible 返回的 `usage.prompt_tokens`、`usage.completion_tokens`、`usage.total_tokens` | `deepseek-v4-flash` 按人民币单价估算，当前按输入缓存未命中价保守计算 |
| DeepSeek 流式生成 | 优先读取 stream `usage`；缺失时按输入输出文本长度估算 | 估算记录会标记 `usage_estimated=true` |
| DashScope 文本生成 | 原生返回的 `usage.input_tokens`、`usage.output_tokens`、`usage.total_tokens` | 按 `ai_model_prices` 中的输入 / 输出人民币单价估算 |
| DashScope 流式生成 | 优先读取流式 payload 中的 `usage`；缺失时按输入输出文本长度估算 | 估算记录会标记 `usage_estimated=true` |
| OpenAI-compatible Embedding | `usage.prompt_tokens`、`usage.total_tokens` | 按 Embedding 模型人民币单价估算 |
| DashScope Rerank | 记录模型、文档数量、字符数和调用状态 | 当前按模型单价表估算，缺失 usage 时保留调用记录 |
| MinerU OCR | SQL 中预留 `mineru-ocr` 价格配置 | 暂未接入真实页数计费，默认 0 元占位 |

费用统计统一展示为人民币 CNY，用于业务核算和客户演示。若历史种子价格仍为 USD，后端会按 `AI_USAGE_USD_TO_CNY_RATE` 折算为 CNY 返回；最终账单仍以模型厂商和 OCR 服务商后台实际计费为准。

### 数据表与脚本

请在 Supabase SQL Editor 执行：

```sql
-- sql/20260507_create_ai_usage_tracking.sql
-- 若此前已执行过 USD 口径种子价，再执行：
-- sql/20260507_update_ai_usage_pricing_cny.sql
-- 若需要 DeepSeek V4 Flash 写作成本统计，再执行：
-- sql/20260510_seed_deepseek_v4_flash_pricing.sql
```

该脚本会创建：

| 对象 | 用途 |
| --- | --- |
| `ai_model_prices` | 维护模型输入、输出、Embedding、Rerank、OCR 等单价 |
| `ai_usage_logs` | 记录每一次 AI / OCR 调用的 Token、费用、阶段、项目、章节和原始 usage |
| `ai_usage_project_summary` | 按项目汇总调用次数、Token 和费用 |
| `ai_usage_project_stage_summary` | 按项目和业务阶段汇总成本 |
| `ai_usage_daily_summary` | 按日期汇总全局用量 |
| `get_ai_usage_project_cost(project_id)` | 项目级成本查询 RPC |

当前默认种子价格覆盖 `deepseek-v4-flash`、`qwen-turbo-latest`、`qwen-long-latest`、`text-embedding-v4`、`qwen3-rerank` 和 `mineru-ocr`。DeepSeek V4 Flash 价格按客户提供口径记录：输入缓存命中 0.02 元 / 百万 tokens、输入缓存未命中 1 元 / 百万 tokens、输出 2 元 / 百万 tokens；当前成本计算按缓存未命中输入价保守估算。如果模型厂商价格发生变化，应优先更新 `ai_model_prices`，历史日志中的 `total_cost` 不会自动重算。

### 多模型兼容

用量统计模块按通用模型调用字段设计，不绑定单一厂商。后续如果切换到 DeepSeek、智谱、Moonshot、百度千帆、火山方舟或其他国产模型，通常只需要完成两类适配：

- 在模型调用适配层继续调用 `record_ai_usage_log()`，写入 `provider`、`model`、`operation_type`、`stage`、`raw_usage`、输入输出文本和业务归属。
- 在 `ai_model_prices` 中维护对应模型的人民币单价，例如 `provider='deepseek'`、`model='deepseek-chat'`、`operation_type='text_generation'`。

当前 usage 归一化已兼容两类常见格式：

| 厂商返回字段 | 系统字段 |
| --- | --- |
| `input_tokens` / `output_tokens` / `total_tokens` | DashScope 原生接口 |
| `prompt_tokens` / `completion_tokens` / `total_tokens` | OpenAI-compatible 接口，包括多数国产模型兼容接口 |

如果厂商不返回 usage，系统会按输入 / 输出文本长度估算 Token，并在日志中标记 `usage_estimated=true`。如果厂商存在缓存命中、推理 Token、阶梯价、请求次数计费或特殊折扣，表结构已预留 `cached_tokens`、`reasoning_tokens`、`request_count`、`metadata` 等字段，但实际成本公式可能需要按厂商账单规则继续扩展。

-- DeepSeek V4 Flash 文本生成价格种子
-- 说明：
-- 1. 写作模型接入 deepseek-v4-flash，使用 OpenAI Compatible 协议。
-- 2. 当前成本计算按输入缓存未命中价保守估算，避免低估客户成本。
-- 3. 缓存命中价写入 metadata，后续如需精确区分 cached_tokens 可继续扩展成本公式。

insert into public.ai_model_prices (
  provider,
  region,
  model,
  operation_type,
  billing_unit,
  currency,
  input_price_per_million,
  output_price_per_million,
  pricing_note,
  source_url,
  metadata
) values
  (
    'deepseek',
    'global',
    'deepseek-v4-flash',
    'text_generation',
    'token_pair',
    'CNY',
    1,
    2,
    'DeepSeek V4 Flash：输入缓存命中 0.02 元/百万 tokens，输入缓存未命中 1 元/百万 tokens，输出 2 元/百万 tokens。系统按缓存未命中价保守估算。',
    'https://api-docs.deepseek.com/zh-cn/',
    '{"source_checked_at":"2026-05-10","input_cache_hit_price_per_million":0.02,"input_cache_miss_price_per_million":1,"output_price_per_million":2,"cost_policy":"cache_miss_conservative"}'::jsonb
  )
on conflict do nothing;

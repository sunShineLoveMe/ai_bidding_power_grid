-- DeepSeek V4 Pro 文本生成价格种子
-- 说明：
-- 1. 招标解读、分册大纲、LLM 语义合规复核默认使用 deepseek-v4-pro。
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
    'deepseek-v4-pro',
    'text_generation',
    'token_pair',
    'CNY',
    3,
    6,
    'DeepSeek V4 Pro：输入缓存命中 0.025 元/百万 tokens，输入缓存未命中 3 元/百万 tokens，输出 6 元/百万 tokens。系统按缓存未命中价保守估算。',
    'https://api-docs.deepseek.com/zh-cn/quick_start/pricing',
    '{"source_checked_at":"2026-05-10","input_cache_hit_price_per_million":0.025,"input_cache_miss_price_per_million":3,"output_price_per_million":6,"cost_policy":"cache_miss_conservative"}'::jsonb
  )
on conflict do nothing;

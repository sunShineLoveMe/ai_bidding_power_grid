-- =========================================================
-- AI 标书系统：AI 用量成本人民币口径修正
-- Date: 2026-05-07
--
-- 用途：
-- 1. 将已执行过的 USD 默认模型价格折算为人民币 CNY。
-- 2. 将历史 ai_usage_logs 中 USD 成本折算为人民币 CNY。
-- 3. 该脚本仅处理 currency='USD' 的记录，可重复执行，不会二次折算已转为 CNY 的数据。
--
-- 折算汇率：
-- 默认按 1 USD = 7.2 CNY。正式生产环境建议按企业财务确认的记账汇率维护。
-- =========================================================

do $$
declare
  v_usd_to_cny numeric := 7.2;
begin
  update public.ai_model_prices
  set
    currency = 'CNY',
    input_price_per_million = input_price_per_million * v_usd_to_cny,
    output_price_per_million = output_price_per_million * v_usd_to_cny,
    price_per_page = price_per_page * v_usd_to_cny,
    price_per_request = price_per_request * v_usd_to_cny,
    pricing_note = concat(coalesce(pricing_note, ''), '；已按 1 USD = 7.2 CNY 折算为人民币口径。'),
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'source_currency',
      'USD',
      'currency_rate',
      v_usd_to_cny,
      'converted_to_cny_at',
      now()
    )
  where currency = 'USD';

  update public.ai_usage_logs
  set
    currency = 'CNY',
    input_cost = input_cost * v_usd_to_cny,
    output_cost = output_cost * v_usd_to_cny,
    other_cost = other_cost * v_usd_to_cny,
    total_cost = total_cost * v_usd_to_cny,
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'source_currency',
      'USD',
      'currency_rate',
      v_usd_to_cny,
      'converted_to_cny_at',
      now()
    )
  where currency = 'USD';
end $$;

create or replace view public.ai_usage_daily_summary as
select
  date_trunc('day', created_at)::date as usage_date,
  provider,
  model,
  operation_type,
  count(*) as call_count,
  count(*) filter (where success) as success_count,
  count(*) filter (where not success) as failed_count,
  coalesce(sum(input_tokens), 0)::bigint as input_tokens,
  coalesce(sum(output_tokens), 0)::bigint as output_tokens,
  coalesce(sum(total_tokens), 0)::bigint as total_tokens,
  coalesce(sum(page_count), 0)::bigint as page_count,
  coalesce(sum(total_cost), 0)::numeric(18, 8) as total_cost
from public.ai_usage_logs
group by date_trunc('day', created_at)::date, provider, model, operation_type;

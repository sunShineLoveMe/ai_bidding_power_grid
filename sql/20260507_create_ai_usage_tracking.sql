-- =========================================================
-- AI 标书系统：AI/OCR Token 用量与成本追踪
-- Date: 2026-05-07
--
-- 用途：
-- 1. 记录单次模型/OCR调用的 token、耗时、成功失败和预估费用。
-- 2. 支持按项目、文件、章节、阶段、模型统计单份标书生成成本。
-- 3. 支持 DashScope 原生接口、OpenAI 兼容接口、Embedding、Rerank、MinerU/OCR 估算。
--
-- 执行位置：
-- Supabase Dashboard -> SQL Editor
--
-- 注意：
-- - 费用为“预估费用”，最终以模型厂商账单为准。
-- - 默认价格为 2026-05-07 调研时的公开文档口径，建议上线前在设置页允许人工维护。
-- - 为避免不同环境基础表结构不一致，本表对 project/file/section 只存 uuid，不强制外键。
-- =========================================================

create extension if not exists pgcrypto;

-- =========================================================
-- 1. 模型/OCR价格配置表
-- =========================================================

create table if not exists public.ai_model_prices (
  id uuid primary key default gen_random_uuid(),

  provider text not null default 'dashscope',
  region text not null default 'cn-beijing',
  model text not null,
  operation_type text not null,

  -- 计价口径：
  -- token_pair: 输入/输出 token 分别计价
  -- input_token: 只按输入 token 计价，如 embedding/rerank
  -- page: 按页计价，如 OCR 估算
  -- request: 按请求计价
  billing_unit text not null default 'token_pair',
  currency text not null default 'CNY',

  -- token 价格统一按“每 100 万 token”存储，便于和百炼官方文档一致。
  input_price_per_million numeric(18, 8) not null default 0,
  output_price_per_million numeric(18, 8) not null default 0,

  -- 非 token 类价格。
  price_per_page numeric(18, 8) not null default 0,
  price_per_request numeric(18, 8) not null default 0,

  -- 复杂价格说明，如 qwen-turbo thinking/non-thinking、阶梯价、OCR 按实际账单等。
  pricing_note text,
  source_url text,

  active boolean not null default true,
  effective_from date not null default current_date,
  effective_to date,

  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint ai_model_prices_billing_unit_check
    check (billing_unit in ('token_pair', 'input_token', 'output_token', 'page', 'request', 'custom')),
  constraint ai_model_prices_operation_type_check
    check (operation_type in ('chat_completion', 'text_generation', 'embedding', 'rerank', 'ocr', 'vision', 'other'))
);

create unique index if not exists ai_model_prices_active_uniq
  on public.ai_model_prices(provider, region, model, operation_type, billing_unit, effective_from)
  where active = true;

create index if not exists ai_model_prices_lookup_idx
  on public.ai_model_prices(provider, region, model, operation_type, active);

-- =========================================================
-- 2. AI/OCR调用明细表
-- =========================================================

create table if not exists public.ai_usage_logs (
  id uuid primary key default gen_random_uuid(),

  -- 业务归属
  project_id uuid,
  file_id uuid,
  section_id uuid,
  user_id text,

  -- 调用归属
  provider text not null default 'dashscope',
  region text default 'cn-beijing',
  api_protocol text not null default 'dashscope',
  endpoint text,
  model text,
  operation_type text not null,
  stage text not null,

  -- 用于串联一次完整标书生成任务。
  batch_id uuid,
  request_id text,
  trace_id text,

  -- 调用形态
  is_stream boolean not null default false,
  include_usage boolean not null default false,
  success boolean not null default true,
  status_code integer,
  latency_ms integer,

  -- token 用量。
  -- DashScope 原生接口通常返回 input_tokens/output_tokens/total_tokens。
  -- OpenAI 兼容接口通常返回 prompt_tokens/completion_tokens/total_tokens。
  input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  total_tokens integer not null default 0,

  prompt_tokens integer not null default 0,
  completion_tokens integer not null default 0,
  cached_tokens integer not null default 0,
  reasoning_tokens integer not null default 0,
  image_tokens integer not null default 0,
  video_tokens integer not null default 0,
  audio_tokens integer not null default 0,

  prompt_tokens_details jsonb not null default '{}'::jsonb,
  completion_tokens_details jsonb not null default '{}'::jsonb,
  raw_usage jsonb not null default '{}'::jsonb,

  -- 非 token 类用量。
  request_count integer not null default 1,
  page_count integer not null default 0,
  document_count integer not null default 0,
  character_count integer not null default 0,

  -- 费用估算。系统展示统一使用人民币 CNY。
  currency text not null default 'CNY',
  input_cost numeric(18, 8) not null default 0,
  output_cost numeric(18, 8) not null default 0,
  other_cost numeric(18, 8) not null default 0,
  total_cost numeric(18, 8) not null default 0,

  -- 没拿到厂商 usage 时可按字符估算，必须标记。
  usage_estimated boolean not null default false,
  cost_estimated boolean not null default true,

  -- 错误与审计
  error_code text,
  error_message text,
  request_payload_hash text,
  response_payload_hash text,

  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),

  constraint ai_usage_logs_api_protocol_check
    check (api_protocol in ('dashscope', 'openai_compatible', 'mineru', 'local', 'other')),
  constraint ai_usage_logs_operation_type_check
    check (operation_type in ('chat_completion', 'text_generation', 'embedding', 'rerank', 'ocr', 'vision', 'other')),
  constraint ai_usage_logs_non_negative_check
    check (
      input_tokens >= 0
      and output_tokens >= 0
      and total_tokens >= 0
      and prompt_tokens >= 0
      and completion_tokens >= 0
      and cached_tokens >= 0
      and reasoning_tokens >= 0
      and image_tokens >= 0
      and video_tokens >= 0
      and audio_tokens >= 0
      and request_count >= 0
      and page_count >= 0
      and document_count >= 0
      and character_count >= 0
      and input_cost >= 0
      and output_cost >= 0
      and other_cost >= 0
      and total_cost >= 0
    )
);

create index if not exists ai_usage_logs_project_created_idx
  on public.ai_usage_logs(project_id, created_at desc);

create index if not exists ai_usage_logs_file_created_idx
  on public.ai_usage_logs(file_id, created_at desc);

create index if not exists ai_usage_logs_section_created_idx
  on public.ai_usage_logs(section_id, created_at desc);

create index if not exists ai_usage_logs_batch_idx
  on public.ai_usage_logs(batch_id);

create index if not exists ai_usage_logs_stage_idx
  on public.ai_usage_logs(stage);

create index if not exists ai_usage_logs_model_idx
  on public.ai_usage_logs(provider, model, operation_type);

create index if not exists ai_usage_logs_created_idx
  on public.ai_usage_logs(created_at desc);

create index if not exists ai_usage_logs_metadata_idx
  on public.ai_usage_logs using gin(metadata);

-- =========================================================
-- 3. 更新时间触发器
-- =========================================================

create or replace function public.set_ai_model_prices_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_ai_model_prices_updated_at on public.ai_model_prices;

create trigger trg_ai_model_prices_updated_at
before update on public.ai_model_prices
for each row
execute function public.set_ai_model_prices_updated_at();

-- =========================================================
-- 4. 成本汇总视图
-- =========================================================

create or replace view public.ai_usage_project_summary as
select
  project_id,
  count(*) as call_count,
  count(*) filter (where success) as success_count,
  count(*) filter (where not success) as failed_count,
  coalesce(sum(input_tokens), 0)::bigint as input_tokens,
  coalesce(sum(output_tokens), 0)::bigint as output_tokens,
  coalesce(sum(total_tokens), 0)::bigint as total_tokens,
  coalesce(sum(cached_tokens), 0)::bigint as cached_tokens,
  coalesce(sum(reasoning_tokens), 0)::bigint as reasoning_tokens,
  coalesce(sum(image_tokens), 0)::bigint as image_tokens,
  coalesce(sum(request_count), 0)::bigint as request_count,
  coalesce(sum(page_count), 0)::bigint as page_count,
  coalesce(sum(document_count), 0)::bigint as document_count,
  coalesce(sum(input_cost), 0)::numeric(18, 8) as input_cost,
  coalesce(sum(output_cost), 0)::numeric(18, 8) as output_cost,
  coalesce(sum(other_cost), 0)::numeric(18, 8) as other_cost,
  coalesce(sum(total_cost), 0)::numeric(18, 8) as total_cost,
  min(created_at) as first_call_at,
  max(created_at) as last_call_at
from public.ai_usage_logs
group by project_id;

create or replace view public.ai_usage_project_stage_summary as
select
  project_id,
  stage,
  operation_type,
  provider,
  model,
  count(*) as call_count,
  count(*) filter (where success) as success_count,
  count(*) filter (where not success) as failed_count,
  coalesce(sum(input_tokens), 0)::bigint as input_tokens,
  coalesce(sum(output_tokens), 0)::bigint as output_tokens,
  coalesce(sum(total_tokens), 0)::bigint as total_tokens,
  coalesce(sum(page_count), 0)::bigint as page_count,
  coalesce(sum(total_cost), 0)::numeric(18, 8) as total_cost,
  max(created_at) as last_call_at
from public.ai_usage_logs
group by project_id, stage, operation_type, provider, model;

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

-- =========================================================
-- 5. 项目级统计 RPC：设置页和项目成本面板可直接调用
-- =========================================================

create or replace function public.get_ai_usage_project_cost(p_project_id uuid)
returns table (
  project_id uuid,
  call_count bigint,
  success_count bigint,
  failed_count bigint,
  input_tokens bigint,
  output_tokens bigint,
  total_tokens bigint,
  request_count bigint,
  page_count bigint,
  input_cost numeric,
  output_cost numeric,
  other_cost numeric,
  total_cost numeric,
  first_call_at timestamptz,
  last_call_at timestamptz
)
language sql
stable
as $$
  select
    s.project_id,
    s.call_count,
    s.success_count,
    s.failed_count,
    s.input_tokens,
    s.output_tokens,
    s.total_tokens,
    s.request_count,
    s.page_count,
    s.input_cost,
    s.output_cost,
    s.other_cost,
    s.total_cost,
    s.first_call_at,
    s.last_call_at
  from public.ai_usage_project_summary s
  where s.project_id = p_project_id;
$$;

-- =========================================================
-- 6. 默认价格种子
-- =========================================================

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
    'dashscope',
    'cn-beijing',
    'qwen-turbo-latest',
    'text_generation',
    'token_pair',
    'CNY',
    0.3168,
    0.6264,
    '中国大陆北京地域 qwen-turbo 非思考模式公开价格按 7.2 汇率折算为人民币；思考模式输出价格更高，需按调用参数另行配置。',
    'https://www.alibabacloud.com/help/en/model-studio/models',
    '{"source_checked_at":"2026-05-07","mode":"non-thinking"}'::jsonb
  ),
  (
    'dashscope',
    'cn-beijing',
    'qwen-long-latest',
    'text_generation',
    'token_pair',
    'CNY',
    0.5184,
    2.0664,
    '中国大陆北京地域 qwen-long-latest 公开价格按 7.2 汇率折算为人民币。',
    'https://www.alibabacloud.com/help/en/model-studio/models',
    '{"source_checked_at":"2026-05-07"}'::jsonb
  ),
  (
    'dashscope',
    'cn-beijing',
    'text-embedding-v4',
    'embedding',
    'input_token',
    'CNY',
    0.5184,
    0,
    '中国大陆北京地域 text-embedding-v4 每 100 万输入 token 公开价格按 7.2 汇率折算为人民币。',
    'https://www.alibabacloud.com/help/zh/model-studio/text-embedding-synchronous-api',
    '{"source_checked_at":"2026-05-07","dimensions_default":1024}'::jsonb
  ),
  (
    'dashscope',
    'cn-beijing',
    'qwen3-rerank',
    'rerank',
    'input_token',
    'CNY',
    0.72,
    0,
    'qwen3-rerank 按输入 token 计费，公开价格按 7.2 汇率折算为人民币；请求 token 计算公式为 Query Tokens × Document 数量 + Document Tokens 总和。',
    'https://www.alibabacloud.com/help/zh/doc-detail/2780056.html',
    '{"source_checked_at":"2026-05-07"}'::jsonb
  )
on conflict do nothing;

-- OCR/MinerU 的价格通常取决于实际购买的资源包、页数、模型和区域。
-- 这里先提供占位行，应用层或设置页应允许客户按实际账单维护。
insert into public.ai_model_prices (
  provider,
  region,
  model,
  operation_type,
  billing_unit,
  currency,
  price_per_page,
  pricing_note,
  metadata
) values (
  'mineru',
  'cn-beijing',
  'mineru-ocr',
  'ocr',
  'page',
  'CNY',
  0,
  'OCR 价格需按客户实际 MinerU/阿里云 OCR 合同或资源包维护；默认 0 表示只统计页数不估算费用。',
  '{"source_checked_at":"2026-05-07","requires_manual_pricing":true}'::jsonb
)
on conflict do nothing;

-- =========================================================
-- 7. 推荐查询
-- =========================================================

-- 单项目总成本：
-- select * from public.get_ai_usage_project_cost('项目UUID');
--
-- 单项目按阶段/模型拆分：
-- select * from public.ai_usage_project_stage_summary where project_id = '项目UUID' order by total_cost desc;
--
-- 最近 30 天每日成本：
-- select * from public.ai_usage_daily_summary where usage_date >= current_date - interval '30 days' order by usage_date desc;

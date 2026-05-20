create extension if not exists pgcrypto;
create extension if not exists vector;

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create table if not exists public.bid_projects (
  id uuid primary key default gen_random_uuid(),
  project_name text not null,
  tender_unit text,
  agency text,
  project_type text,
  project_no text,
  status text not null default 'uploaded',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_bid_projects_updated_at on public.bid_projects;
create trigger trg_bid_projects_updated_at
before update on public.bid_projects
for each row execute function public.set_updated_at();

create table if not exists public.bid_files (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  file_name text not null,
  file_type text,
  bucket text,
  object_path text,
  file_hash text,
  file_size bigint,
  parse_status text not null default 'pending',
  created_at timestamptz not null default now()
);

create index if not exists idx_bid_files_project_created
  on public.bid_files(project_id, created_at desc);

create table if not exists public.bid_analysis (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  project_meta jsonb not null default '{}'::jsonb,
  qualification_requirements jsonb not null default '[]'::jsonb,
  document_checklist jsonb not null default '[]'::jsonb,
  scoring_items jsonb not null default '[]'::jsonb,
  risk_items jsonb not null default '[]'::jsonb,
  chapter_suggestions jsonb not null default '[]'::jsonb,
  summary text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop index if exists public.idx_bid_analysis_project_unique;

create index if not exists idx_bid_analysis_project
  on public.bid_analysis(project_id);

drop trigger if exists trg_bid_analysis_updated_at on public.bid_analysis;
create trigger trg_bid_analysis_updated_at
before update on public.bid_analysis
for each row execute function public.set_updated_at();

create table if not exists public.bid_requirements (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  requirement_type text,
  title text,
  content text,
  priority text,
  source_section text,
  source_page integer,
  source_text text,
  created_at timestamptz not null default now()
);

create index if not exists idx_bid_requirements_project
  on public.bid_requirements(project_id);

create table if not exists public.bid_scoring_items (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  category text,
  item text,
  score numeric,
  requirement text,
  response_suggestion text,
  target_chapter text,
  source_section text,
  source_page integer,
  source_text text,
  created_at timestamptz not null default now()
);

create index if not exists idx_bid_scoring_items_project
  on public.bid_scoring_items(project_id);

create table if not exists public.bid_risks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  risk_level text,
  risk_type text,
  content text,
  action text,
  source_section text,
  source_page integer,
  source_text text,
  created_at timestamptz not null default now()
);

create index if not exists idx_bid_risks_project
  on public.bid_risks(project_id);

create table if not exists public.bid_chapter_suggestions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  chapter_title text,
  reason text,
  related_requirements jsonb not null default '[]'::jsonb,
  priority text,
  created_at timestamptz not null default now()
);

create index if not exists idx_bid_chapter_suggestions_project
  on public.bid_chapter_suggestions(project_id);

create table if not exists public.bid_sections (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  parent_id uuid,
  order_index integer not null default 0,
  level integer not null default 1,
  title text not null,
  status text not null default 'draft',
  purpose text,
  response_points jsonb not null default '[]'::jsonb,
  mapped_requirements jsonb not null default '[]'::jsonb,
  mapped_scoring_items jsonb not null default '[]'::jsonb,
  mapped_risks jsonb not null default '[]'::jsonb,
  required_materials jsonb not null default '[]'::jsonb,
  source_pages jsonb not null default '[]'::jsonb,
  writing_notes jsonb not null default '[]'::jsonb,
  content text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_bid_sections_project_order
  on public.bid_sections(project_id, order_index);

create index if not exists idx_bid_sections_parent
  on public.bid_sections(parent_id);

drop trigger if exists trg_bid_sections_updated_at on public.bid_sections;
create trigger trg_bid_sections_updated_at
before update on public.bid_sections
for each row execute function public.set_updated_at();

create table if not exists public.knowledge_documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  category text,
  bucket text,
  object_path text,
  source_type text,
  status text not null default 'processing',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_knowledge_documents_category
  on public.knowledge_documents(category);

create unique index if not exists idx_knowledge_documents_bucket_object_unique
  on public.knowledge_documents(bucket, object_path)
  where bucket is not null and object_path is not null;

create table if not exists public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references public.knowledge_documents(id) on delete cascade,
  project_id uuid references public.bid_projects(id) on delete cascade,
  chunk_index integer not null default 0,
  content text not null,
  source_page integer,
  source_section text,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(1024),
  created_at timestamptz not null default now()
);

create index if not exists idx_document_chunks_document
  on public.document_chunks(document_id, chunk_index);

create unique index if not exists idx_document_chunks_document_chunk_unique
  on public.document_chunks(document_id, chunk_index)
  where document_id is not null;

create index if not exists idx_document_chunks_embedding
  on public.document_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create table if not exists public.knowledge_assets (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  category text,
  asset_type text not null default 'image',
  file_name text,
  file_ext text,
  mime_type text,
  file_size bigint,
  local_path text,
  storage_bucket text,
  storage_path text,
  public_url text,
  width integer,
  height integer,
  source_type text default 'seed',
  source_url text,
  license text,
  attribution text,
  is_synthetic boolean default false,
  is_sensitive boolean default false,
  anonymized boolean default true,
  industry text default '电力行业',
  applicable_sections text[] default '{}',
  tags text[] default '{}',
  specs jsonb default '{}'::jsonb,
  ocr_text text,
  ai_caption text,
  searchable_text text,
  embedding vector(1024),
  knowledge_document_id uuid references public.knowledge_documents(id) on delete set null,
  status text not null default 'indexed',
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  applicable_volumes text[] default '{}'
);

create index if not exists knowledge_assets_category_idx
  on public.knowledge_assets(category);

create index if not exists knowledge_assets_asset_type_idx
  on public.knowledge_assets(asset_type);

create index if not exists knowledge_assets_status_idx
  on public.knowledge_assets(status);

create index if not exists knowledge_assets_tags_idx
  on public.knowledge_assets using gin(tags);

create index if not exists knowledge_assets_applicable_sections_idx
  on public.knowledge_assets using gin(applicable_sections);

create index if not exists knowledge_assets_applicable_volumes_idx
  on public.knowledge_assets using gin(applicable_volumes);

create index if not exists knowledge_assets_metadata_idx
  on public.knowledge_assets using gin(metadata);

create index if not exists knowledge_assets_embedding_idx
  on public.knowledge_assets
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create unique index if not exists idx_knowledge_assets_bucket_object_unique
  on public.knowledge_assets(storage_bucket, storage_path)
  where storage_bucket is not null and storage_path is not null;

drop trigger if exists trg_knowledge_assets_updated_at on public.knowledge_assets;
create trigger trg_knowledge_assets_updated_at
before update on public.knowledge_assets
for each row execute function public.set_updated_at();

create table if not exists public.app_users (
  id uuid primary key default gen_random_uuid(),
  fingerprint_id text unique not null,
  created_at timestamptz not null default now()
);

create table if not exists public.onlyoffice_documents (
  id uuid primary key default gen_random_uuid(),
  document_key text unique not null,
  project_id uuid references public.bid_projects(id) on delete cascade,
  title text not null,
  file_path text not null,
  download_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_onlyoffice_documents_project_id
  on public.onlyoffice_documents(project_id);

drop trigger if exists trg_onlyoffice_documents_updated_at on public.onlyoffice_documents;
create trigger trg_onlyoffice_documents_updated_at
before update on public.onlyoffice_documents
for each row execute function public.set_updated_at();

create table if not exists public.ai_model_prices (
  id uuid primary key default gen_random_uuid(),
  provider text not null default 'dashscope',
  region text not null default 'cn-beijing',
  model text not null,
  operation_type text not null,
  billing_unit text not null default 'token_pair',
  currency text not null default 'CNY',
  input_price_per_million numeric(18, 8) not null default 0,
  output_price_per_million numeric(18, 8) not null default 0,
  price_per_page numeric(18, 8) not null default 0,
  price_per_request numeric(18, 8) not null default 0,
  pricing_note text,
  source_url text,
  active boolean not null default true,
  effective_from date not null default current_date,
  effective_to date,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists ai_model_prices_active_uniq
  on public.ai_model_prices(provider, region, model, operation_type, billing_unit, effective_from)
  where active = true;

create index if not exists ai_model_prices_lookup_idx
  on public.ai_model_prices(provider, region, model, operation_type, active);

drop trigger if exists trg_ai_model_prices_updated_at on public.ai_model_prices;
create trigger trg_ai_model_prices_updated_at
before update on public.ai_model_prices
for each row execute function public.set_updated_at();

create table if not exists public.ai_usage_logs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid,
  file_id uuid,
  section_id uuid,
  user_id text,
  provider text not null default 'dashscope',
  region text default 'cn-beijing',
  api_protocol text not null default 'dashscope',
  endpoint text,
  model text,
  operation_type text not null,
  stage text not null,
  batch_id uuid,
  request_id text,
  trace_id text,
  is_stream boolean not null default false,
  include_usage boolean not null default false,
  success boolean not null default true,
  status_code integer,
  latency_ms integer,
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
  request_count integer not null default 1,
  page_count integer not null default 0,
  document_count integer not null default 0,
  character_count integer not null default 0,
  currency text not null default 'CNY',
  input_cost numeric(18, 8) not null default 0,
  output_cost numeric(18, 8) not null default 0,
  other_cost numeric(18, 8) not null default 0,
  total_cost numeric(18, 8) not null default 0,
  usage_estimated boolean not null default false,
  cost_estimated boolean not null default true,
  error_code text,
  error_message text,
  request_payload_hash text,
  response_payload_hash text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
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

create table if not exists public.bid_generation_tasks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  task_type text not null default 'batch_sections',
  volume_type text not null default 'all',
  with_images boolean not null default false,
  status text not null default 'queued',
  total_count integer not null default 0,
  queued_count integer not null default 0,
  running_count integer not null default 0,
  done_count integer not null default 0,
  failed_count integer not null default 0,
  stopped_count integer not null default 0,
  items jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_bid_generation_tasks_project_created
  on public.bid_generation_tasks(project_id, created_at desc);

create index if not exists idx_bid_generation_tasks_status
  on public.bid_generation_tasks(status);

create index if not exists idx_bid_generation_tasks_items
  on public.bid_generation_tasks using gin(items);

drop trigger if exists trg_bid_generation_tasks_updated_at on public.bid_generation_tasks;
create trigger trg_bid_generation_tasks_updated_at
before update on public.bid_generation_tasks
for each row execute function public.set_updated_at();

create table if not exists public.bid_export_tasks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  export_type text not null default 'docx',
  scope text not null default 'full',
  section_id uuid,
  volume_type text,
  with_images boolean not null default false,
  status text not null default 'queued',
  progress integer not null default 0,
  message text,
  project_name text,
  file_name text,
  file_path text,
  download_url text,
  error_message text,
  metadata jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_bid_export_tasks_project_created
  on public.bid_export_tasks(project_id, created_at desc);

create index if not exists idx_bid_export_tasks_status
  on public.bid_export_tasks(status);

drop trigger if exists trg_bid_export_tasks_updated_at on public.bid_export_tasks;
create trigger trg_bid_export_tasks_updated_at
before update on public.bid_export_tasks
for each row execute function public.set_updated_at();

create or replace view public.ai_usage_project_summary as
select
  project_id,
  count(*) as call_count,
  count(*) filter (where success) as success_count,
  count(*) filter (where not success) as failed_count,
  coalesce(sum(input_tokens), 0)::bigint as input_tokens,
  coalesce(sum(output_tokens), 0)::bigint as output_tokens,
  coalesce(sum(total_tokens), 0)::bigint as total_tokens,
  coalesce(sum(request_count), 0)::bigint as request_count,
  coalesce(sum(page_count), 0)::bigint as page_count,
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

create or replace function public.match_knowledge_chunks(
  query_embedding vector(1024),
  match_threshold float default 0.5,
  match_count int default 5
)
returns table (
  id uuid,
  document_id uuid,
  project_id uuid,
  content text,
  source_page integer,
  source_section text,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.project_id,
    dc.content,
    dc.source_page,
    dc.source_section,
    dc.metadata,
    1 - (dc.embedding <=> query_embedding) as similarity
  from public.document_chunks dc
  where dc.embedding is not null
    and 1 - (dc.embedding <=> query_embedding) >= match_threshold
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;

create or replace function public.match_knowledge_assets(
  query_embedding vector(1024),
  match_count int default 8,
  filter_category text default null,
  filter_asset_type text default null,
  filter_applicable_volume text default null
)
returns table (
  id uuid,
  title text,
  description text,
  category text,
  asset_type text,
  file_name text,
  file_ext text,
  mime_type text,
  file_size bigint,
  storage_bucket text,
  storage_path text,
  public_url text,
  width integer,
  height integer,
  source_type text,
  source_url text,
  license text,
  attribution text,
  is_synthetic boolean,
  is_sensitive boolean,
  anonymized boolean,
  industry text,
  applicable_sections text[],
  applicable_volumes text[],
  tags text[],
  specs jsonb,
  ocr_text text,
  ai_caption text,
  searchable_text text,
  knowledge_document_id uuid,
  status text,
  metadata jsonb,
  created_at timestamptz,
  updated_at timestamptz,
  similarity float
)
language sql
stable
as $$
  select
    ka.id,
    ka.title,
    ka.description,
    ka.category,
    ka.asset_type,
    ka.file_name,
    ka.file_ext,
    ka.mime_type,
    ka.file_size,
    ka.storage_bucket,
    ka.storage_path,
    ka.public_url,
    ka.width,
    ka.height,
    ka.source_type,
    ka.source_url,
    ka.license,
    ka.attribution,
    ka.is_synthetic,
    ka.is_sensitive,
    ka.anonymized,
    ka.industry,
    ka.applicable_sections,
    ka.applicable_volumes,
    ka.tags,
    ka.specs,
    ka.ocr_text,
    ka.ai_caption,
    ka.searchable_text,
    ka.knowledge_document_id,
    ka.status,
    ka.metadata,
    ka.created_at,
    ka.updated_at,
    1 - (ka.embedding <=> query_embedding) as similarity
  from public.knowledge_assets ka
  where ka.embedding is not null
    and ka.status = 'indexed'
    and (filter_category is null or ka.category = filter_category)
    and (filter_asset_type is null or ka.asset_type = filter_asset_type)
    and (
      filter_applicable_volume is null
      or coalesce(array_length(ka.applicable_volumes, 1), 0) = 0
      or filter_applicable_volume = any(ka.applicable_volumes)
    )
  order by ka.embedding <=> query_embedding
  limit match_count;
$$;

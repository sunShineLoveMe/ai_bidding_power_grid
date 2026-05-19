-- =========================================================
-- AI 标书系统：企业知识库图片/资质资产扩展
-- Date: 2026-04-28
--
-- 用途：
-- 1. 存储产品图、资质图、营业执照脱敏样张、工程案例图等图片资产。
-- 2. 为图片生成可检索文本与 embedding。
-- 3. 支持 RAG 企业问答返回相关图片来源。
--
-- 执行位置：
-- Supabase Dashboard -> SQL Editor
-- =========================================================

create extension if not exists vector;

create table if not exists public.knowledge_assets (
  id uuid primary key default gen_random_uuid(),

  -- 资产基础信息
  title text not null,
  description text,
  category text,
  asset_type text not null default 'image',

  -- 文件信息
  file_name text,
  file_ext text,
  mime_type text,
  file_size bigint,
  local_path text,
  storage_bucket text,
  storage_path text,
  public_url text,

  -- 图片尺寸
  width integer,
  height integer,

  -- 来源与合规信息
  source_type text default 'seed',
  source_url text,
  license text,
  attribution text,
  is_synthetic boolean default false,
  is_sensitive boolean default false,
  anonymized boolean default true,

  -- 业务标签
  industry text default '水利行业',
  applicable_sections text[] default '{}',
  applicable_volumes text[] default '{}',
  tags text[] default '{}',
  specs jsonb default '{}'::jsonb,

  -- OCR / AI 描述 / 可检索文本
  ocr_text text,
  ai_caption text,
  searchable_text text,

  -- 向量维度与 DashScope text-embedding-v3 当前项目配置保持一致。
  embedding vector(1024),

  -- 和现有知识库文档的弱关联，非强制。
  knowledge_document_id uuid references public.knowledge_documents(id) on delete set null,

  -- 状态
  status text not null default 'indexed',
  metadata jsonb default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
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

create or replace function public.set_knowledge_assets_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_knowledge_assets_updated_at on public.knowledge_assets;

create trigger trg_knowledge_assets_updated_at
before update on public.knowledge_assets
for each row
execute function public.set_knowledge_assets_updated_at();

-- =========================================================
-- 图片资产向量检索 RPC
-- =========================================================

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
  public_url text,
  storage_bucket text,
  storage_path text,
  source_url text,
  license text,
  attribution text,
  applicable_sections text[],
  applicable_volumes text[],
  tags text[],
  specs jsonb,
  searchable_text text,
  metadata jsonb,
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
    ka.public_url,
    ka.storage_bucket,
    ka.storage_path,
    ka.source_url,
    ka.license,
    ka.attribution,
    ka.applicable_sections,
    ka.applicable_volumes,
    ka.tags,
    ka.specs,
    ka.searchable_text,
    ka.metadata,
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
      or (filter_applicable_volume = 'qualification' and 'attachment' = any(ka.applicable_volumes))
      or (filter_applicable_volume = 'business' and ('qualification' = any(ka.applicable_volumes) or 'attachment' = any(ka.applicable_volumes)))
    )
  order by ka.embedding <=> query_embedding
  limit match_count;
$$;

-- =========================================================
-- Supabase Storage bucket
--
-- 当前 bucket 设置为 public，方便前端直接展示图片缩略图。
-- 如果后续存放真实企业证照，应改为 private bucket + signed URL。
-- =========================================================

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'knowledge-assets',
  'knowledge-assets',
  true,
  52428800,
  array[
    'image/jpeg',
    'image/png',
    'image/webp',
    'application/pdf'
  ]
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- =========================================================
-- Storage 访问策略
--
-- 当前是本地单机版/研发阶段：
-- - 允许公开读取。
-- - 允许上传、更新、删除 knowledge-assets bucket 文件。
--
-- 生产环境建议：
-- - 上传/更新/删除改为 authenticated 或 service_role 后端代理。
-- - 真实企业证照改为 private bucket。
-- =========================================================

drop policy if exists "knowledge assets public read" on storage.objects;
create policy "knowledge assets public read"
on storage.objects
for select
using (bucket_id = 'knowledge-assets');

drop policy if exists "knowledge assets anon insert" on storage.objects;
create policy "knowledge assets anon insert"
on storage.objects
for insert
with check (bucket_id = 'knowledge-assets');

drop policy if exists "knowledge assets anon update" on storage.objects;
create policy "knowledge assets anon update"
on storage.objects
for update
using (bucket_id = 'knowledge-assets')
with check (bucket_id = 'knowledge-assets');

drop policy if exists "knowledge assets anon delete" on storage.objects;
create policy "knowledge assets anon delete"
on storage.objects
for delete
using (bucket_id = 'knowledge-assets');

-- =========================================================
-- 执行后校验
-- =========================================================

select count(*) as knowledge_assets_count from public.knowledge_assets;
select id, name, public from storage.buckets where id = 'knowledge-assets';

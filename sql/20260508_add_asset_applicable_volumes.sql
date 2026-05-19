-- 企业资信库/产品库适用分册字段
-- 说明：
-- 1. 用于将知识资产明确限定到技术标、商务标、资格文件、报价文件或附件材料。
-- 2. 旧数据若未标注 applicable_volumes，代码仍会回退到适用章节、库类型、资产类型和标签推断。
-- 3. 新增字段后，RAG 和 DOCX 自动插图会优先遵守该字段，减少跨分册误召回。

alter table if exists public.knowledge_assets
  add column if not exists applicable_volumes text[] default '{}';

create index if not exists knowledge_assets_applicable_volumes_idx
  on public.knowledge_assets using gin(applicable_volumes);

-- 为已有产品库、资信库数据补默认分册，避免上线后出现空字段影响筛选解释。
update public.knowledge_assets
set applicable_volumes = array['technical']::text[]
where coalesce(array_length(applicable_volumes, 1), 0) = 0
  and (
    asset_type = 'product_image'
    or metadata->>'library_type' = 'product'
    or specs->>'library_type' = 'product'
  );

update public.knowledge_assets
set applicable_volumes = array['qualification', 'business', 'attachment']::text[]
where coalesce(array_length(applicable_volumes, 1), 0) = 0
  and (
    asset_type = 'qualification_image'
    or metadata->>'library_type' = 'qualification'
    or specs->>'library_type' = 'qualification'
  );

drop function if exists public.match_knowledge_assets(vector, int, text, text);

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

-- P0: 场景化召回支持（评审稿 §9、§10）
-- 1. 索引整改：ivfflat -> HNSW（小数据 recall 更好、增量友好）
-- 2. 新增带 metadata 过滤的召回 RPC：match_knowledge_chunks_filtered
-- 3. 为高频过滤字段建 jsonb 表达式索引

-- ---- 1. HNSW 索引 ----------------------------------------------------------
-- 删除旧 ivfflat 索引，改建 HNSW（cosine）。HNSW 不依赖数据量，适合持续增量。
drop index if exists idx_document_chunks_embedding;
create index if not exists idx_document_chunks_embedding_hnsw
  on public.document_chunks
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

drop index if exists knowledge_assets_embedding_idx;
create index if not exists knowledge_assets_embedding_hnsw
  on public.knowledge_assets
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- ---- 2. metadata 过滤字段的表达式索引（高基数过滤先行） --------------------
create index if not exists idx_chunks_meta_doc_role
  on public.document_chunks ((metadata->>'doc_role'));
create index if not exists idx_chunks_meta_chunk_layer
  on public.document_chunks ((metadata->>'chunk_layer'));
create index if not exists idx_chunks_meta_seed_corpus
  on public.document_chunks ((metadata->>'seed_corpus'));
create index if not exists idx_chunks_meta_province
  on public.document_chunks ((metadata->>'province'));
create index if not exists idx_chunks_meta_batch_no
  on public.document_chunks ((metadata->>'batch_no'));

-- ---- 3. 带 metadata 过滤的召回 RPC ----------------------------------------
-- 仅召回 child 层（embedding 非空）；通过 jsonb 包含匹配做定向过滤。
-- filter_metadata 形如：{"doc_role": "policy_regulation", "province": "山西"}
-- filter_project_id 不为空时，限定本标书私有资料（document_chunks.project_id）。
create or replace function public.match_knowledge_chunks_filtered(
  query_embedding vector(1024),
  match_threshold float default 0.3,
  match_count int default 8,
  filter_metadata jsonb default '{}'::jsonb,
  filter_project_id uuid default null
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
    and (filter_metadata = '{}'::jsonb or dc.metadata @> filter_metadata)
    and (filter_project_id is null or dc.project_id = filter_project_id)
    and 1 - (dc.embedding <=> query_embedding) >= match_threshold
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;

-- 父块回溯：按 document_id + chunk_index 取 parent，用于写作场景返回完整上下文。
create or replace function public.get_parent_chunk(
  p_document_id uuid,
  p_parent_index int
)
returns table (
  id uuid,
  document_id uuid,
  content text,
  source_section text,
  metadata jsonb
)
language sql
stable
as $$
  select dc.id, dc.document_id, dc.content, dc.source_section, dc.metadata
  from public.document_chunks dc
  where dc.document_id = p_document_id
    and dc.chunk_index = p_parent_index
  limit 1;
$$;

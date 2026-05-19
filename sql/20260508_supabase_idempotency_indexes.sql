-- P1.2 Supabase 写入幂等辅助索引
-- 说明：
-- 1. 代码层已先实现重复保存复用和写入重试；本脚本用于给数据库层补充防重能力。
-- 2. 若历史库中已经存在重复数据，创建 unique index 可能失败；请先备份并清理重复记录后再执行。

create unique index if not exists idx_knowledge_documents_bucket_object_unique
  on public.knowledge_documents(bucket, object_path)
  where bucket is not null and object_path is not null;

create unique index if not exists idx_document_chunks_document_chunk_unique
  on public.document_chunks(document_id, chunk_index)
  where document_id is not null and chunk_index is not null;

create unique index if not exists idx_knowledge_assets_bucket_object_unique
  on public.knowledge_assets(storage_bucket, storage_path)
  where storage_bucket is not null and storage_path is not null;

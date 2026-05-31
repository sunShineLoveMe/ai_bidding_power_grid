-- P1-1 第二批：招标文件解析状态从本地文件迁移到 PostgreSQL。
--
-- 背景：解析状态原本写在 parsed_outputs/{parse_id}/mineru_status.json，
-- 在多 worker / 多容器下 web 进程与 Celery worker 不共享该文件，导致状态不可见。
-- 本表把解析状态集中存到 DB，保证跨进程一致。
--
-- 说明：
-- - parse_id 是 text 而非 uuid：拆分大 PDF 时分片任务键形如 "{uuid}_part001"，并非合法 uuid。
-- - status_payload 保存与原 JSON 文件完全一致的整份状态，写入用 JSONB `||` 浅合并，
--   语义等价于原先的 read-modify-write，但是原子操作。
-- - supabase_file_id / parse_status 通过表达式索引支持历史列表和重试按文件查找。

create table if not exists public.bid_parse_tasks (
  parse_id text primary key,
  status_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_bid_parse_tasks_supabase_file
  on public.bid_parse_tasks ((status_payload->>'supabase_file_id'), updated_at desc);

create index if not exists idx_bid_parse_tasks_parse_status
  on public.bid_parse_tasks ((status_payload->>'parse_status'));

drop trigger if exists trg_bid_parse_tasks_updated_at on public.bid_parse_tasks;
create trigger trg_bid_parse_tasks_updated_at
before update on public.bid_parse_tasks
for each row execute function public.set_updated_at();

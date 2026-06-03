-- P0 章节生成任务 item 独立表与事件表
-- 先做 additive migration：保留 bid_generation_tasks.items JSON 作为兼容快照，
-- 新表用于后续 lease、heartbeat、重试、事件审计和行级并发控制。

create table if not exists public.bid_generation_task_items (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.bid_generation_tasks(id) on delete cascade,
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  section_id uuid not null references public.bid_sections(id) on delete cascade,
  title text,
  order_index integer,
  volume_type text,
  target_words integer not null default 0,
  status text not null default 'queued',
  percent integer not null default 0,
  chars integer not null default 0,
  message text,
  error text,
  attempt integer not null default 0,
  attempt_id uuid,
  worker_id text,
  lease_expires_at timestamptz,
  heartbeat_at timestamptz,
  first_token_at timestamptz,
  last_token_at timestamptz,
  draft_saved_at timestamptz,
  final_saved_at timestamptz,
  saved_section_id uuid,
  generated_content text not null default '',
  draft_content text not null default '',
  chunk_seq integer not null default 0,
  chunk_events jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(task_id, section_id)
);

create index if not exists idx_bid_generation_task_items_task
  on public.bid_generation_task_items(task_id, order_index, created_at);

create index if not exists idx_bid_generation_task_items_project_status
  on public.bid_generation_task_items(project_id, status, updated_at desc);

create index if not exists idx_bid_generation_task_items_lease
  on public.bid_generation_task_items(status, lease_expires_at)
  where status in ('leased', 'generating', 'saving', 'running');

create table if not exists public.bid_generation_task_events (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.bid_generation_tasks(id) on delete cascade,
  item_id uuid references public.bid_generation_task_items(id) on delete cascade,
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  section_id uuid references public.bid_sections(id) on delete set null,
  event_type text not null,
  status text,
  message text,
  worker_id text,
  attempt_id uuid,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_bid_generation_task_events_task_created
  on public.bid_generation_task_events(task_id, created_at);

create index if not exists idx_bid_generation_task_events_item_created
  on public.bid_generation_task_events(item_id, created_at);

create or replace function public.set_bid_generation_task_items_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_bid_generation_task_items_updated_at on public.bid_generation_task_items;
create trigger trg_bid_generation_task_items_updated_at
before update on public.bid_generation_task_items
for each row execute function public.set_bid_generation_task_items_updated_at();

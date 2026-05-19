-- P1.3 批量章节生成后端任务态
-- 用于记录“一键编写全文”的整批任务和每个章节的生成状态。

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

create or replace function public.set_bid_generation_tasks_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_bid_generation_tasks_updated_at on public.bid_generation_tasks;
create trigger trg_bid_generation_tasks_updated_at
before update on public.bid_generation_tasks
for each row execute function public.set_bid_generation_tasks_updated_at();

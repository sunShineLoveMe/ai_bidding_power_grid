create table if not exists public.bid_interpretation_tasks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  status text not null default 'queued',
  progress integer not null default 0,
  message text,
  error_message text,
  metadata jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_bid_interpretation_tasks_project_created
  on public.bid_interpretation_tasks(project_id, created_at desc);

create index if not exists idx_bid_interpretation_tasks_status
  on public.bid_interpretation_tasks(status);

drop trigger if exists trg_bid_interpretation_tasks_updated_at on public.bid_interpretation_tasks;
create trigger trg_bid_interpretation_tasks_updated_at
before update on public.bid_interpretation_tasks
for each row execute function public.set_updated_at();

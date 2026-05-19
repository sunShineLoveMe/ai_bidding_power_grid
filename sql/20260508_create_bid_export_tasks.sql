-- P1.5 DOCX 导出任务化
-- 用于记录全书、分册和单章 DOCX 导出任务，避免长文档导出阻塞 HTTP 请求。

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

create or replace function public.set_bid_export_tasks_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_bid_export_tasks_updated_at on public.bid_export_tasks;
create trigger trg_bid_export_tasks_updated_at
before update on public.bid_export_tasks
for each row execute function public.set_bid_export_tasks_updated_at();

create table if not exists public.bid_sections (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.bid_projects(id) on delete cascade,
  parent_id uuid references public.bid_sections(id) on delete cascade,
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

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_bid_sections_updated_at on public.bid_sections;
create trigger trg_bid_sections_updated_at
before update on public.bid_sections
for each row execute function public.set_updated_at();

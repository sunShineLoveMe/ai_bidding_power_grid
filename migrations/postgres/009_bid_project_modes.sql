-- P0-07：通用标书流程与泰昌历史标书复用流程的项目级隔离。
-- 旧项目统一回填为 general，避免升级后改变既有项目行为。

alter table public.bid_projects
  add column if not exists project_mode text not null default 'general';

update public.bid_projects
set project_mode = 'general'
where project_mode is null
   or project_mode not in ('general', 'taichang_reuse');

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'bid_projects_project_mode_check'
      and conrelid = 'public.bid_projects'::regclass
  ) then
    alter table public.bid_projects
      add constraint bid_projects_project_mode_check
      check (project_mode in ('general', 'taichang_reuse'));
  end if;
end
$$;

comment on column public.bid_projects.project_mode is
  '项目编排模式：general=现有通用流程，taichang_reuse=泰昌历史标书复用流程。创建后不可由客户端切换。';

-- P0 worker lease / heartbeat / expire for section generation task items.

create or replace function public.lease_bid_generation_task_items(
  p_project_id uuid,
  p_task_id uuid,
  p_limit integer,
  p_worker_id text,
  p_lease_seconds integer default 900
)
returns setof public.bid_generation_task_items
language plpgsql
as $$
begin
  -- Serialize lease top-up for the same task. Multiple workers can finish at
  -- nearly the same time and call the dispatcher concurrently; without a
  -- task-level transaction lock, the last queued item can be leased twice in
  -- a narrow race.
  perform pg_advisory_xact_lock(hashtext(p_task_id::text));

  return query
  with picked as (
    select id
    from public.bid_generation_task_items
    where project_id = p_project_id
      and task_id = p_task_id
      and status = 'queued'
    order by order_index nulls last, created_at
    limit greatest(p_limit, 0)
    for update skip locked
  )
  update public.bid_generation_task_items item
  set status = 'leased',
      percent = greatest(item.percent, 1),
      message = '已派发，等待 worker 开始编写',
      attempt = item.attempt + 1,
      attempt_id = gen_random_uuid(),
      worker_id = p_worker_id,
      lease_expires_at = now() + make_interval(secs => greatest(p_lease_seconds, 30)),
      heartbeat_at = now(),
      started_at = coalesce(item.started_at, now()),
      error = null
  from picked
  where item.id = picked.id
  returning item.*;
end;
$$;

create or replace function public.heartbeat_bid_generation_task_item(
  p_project_id uuid,
  p_task_id uuid,
  p_section_id uuid,
  p_attempt_id uuid,
  p_worker_id text,
  p_lease_seconds integer default 900
)
returns setof public.bid_generation_task_items
language plpgsql
as $$
begin
  return query
  update public.bid_generation_task_items item
  set heartbeat_at = now(),
      lease_expires_at = now() + make_interval(secs => greatest(p_lease_seconds, 30))
  where item.project_id = p_project_id
    and item.task_id = p_task_id
    and item.section_id = p_section_id
    and item.attempt_id = p_attempt_id
    and item.worker_id = p_worker_id
    and item.status in ('leased', 'generating', 'saving', 'running')
  returning item.*;
end;
$$;

create or replace function public.expire_bid_generation_task_items(
  p_project_id uuid,
  p_task_id uuid,
  p_requeue boolean default true
)
returns setof public.bid_generation_task_items
language plpgsql
as $$
begin
  return query
  update public.bid_generation_task_items item
  set status = case when p_requeue then 'queued' else 'expired' end,
      message = case when p_requeue then 'worker 心跳超时，已重新排队' else 'worker 心跳超时，已过期' end,
      percent = case when p_requeue then 0 else item.percent end,
      worker_id = null,
      lease_expires_at = null,
      heartbeat_at = null,
      attempt_id = case when p_requeue then null else item.attempt_id end,
      finished_at = case when p_requeue then null else now() end
  where item.project_id = p_project_id
    and item.task_id = p_task_id
    and item.status in ('leased', 'generating', 'saving', 'running')
    and item.lease_expires_at is not null
    and item.lease_expires_at < now()
  returning item.*;
end;
$$;

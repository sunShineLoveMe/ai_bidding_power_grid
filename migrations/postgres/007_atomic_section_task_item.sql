-- 并发安全的批量章节任务单项更新（对应"恢复多路并行编写"）。
--
-- 背景：章节正文改为多个 Celery 子任务并发编写后，多个子任务会同时更新同一行
-- bid_generation_tasks.items（jsonb 数组）。原 Python 实现是"读整行 → 改数组 → 写回"，
-- 并发下会丢更新（lost update）。
--
-- 方案：在数据库内用一条语句完成，并对该行加 FOR UPDATE 行锁，保证串行化：
--   1. 锁定目标任务行；
--   2. 在 items 数组中按 section_id 定位元素并就地合并补丁字段；
--   3. 重算 queued/running/done/failed/stopped 计数与总体 status；
--   4. 写回并返回最新行。
--
-- patch 为 jsonb，仅允许的字段会被合并；status 流转与 started_at/finished_at 由 SQL 维护。

create or replace function public.update_bid_generation_task_item_atomic(
  p_project_id uuid,
  p_task_id uuid,
  p_section_id text,
  p_patch jsonb
)
returns setof public.bid_generation_tasks
language plpgsql
as $$
declare
  v_items jsonb;
  v_new_items jsonb := '[]'::jsonb;
  v_elem jsonb;
  v_matched boolean := false;
  v_now text := to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.US');
  v_allowed text[] := array['section_id','status','percent','chars','message','error',
                            'target_words','saved_section_id','generated_content',
                            'chunk_seq','chunk_events','last_chunk','title','metadata'];
  v_key text;
  v_next_status text;
  v_prev_status text;
  v_queued int := 0; v_running int := 0; v_done int := 0; v_failed int := 0; v_stopped int := 0;
  v_status text;
  v_task_status text := p_patch->>'task_status';
begin
  -- 行锁：并发子任务在此串行化，消除 jsonb 数组的丢更新。
  select items into v_items from public.bid_generation_tasks
    where id = p_task_id and project_id = p_project_id
    for update;
  if v_items is null then
    raise exception '批量章节生成任务不存在: %', p_task_id;
  end if;

  for v_elem in select * from jsonb_array_elements(v_items)
  loop
    if (v_elem->>'section_id') = p_section_id then
      v_matched := true;
      v_prev_status := coalesce(v_elem->>'status', 'queued');
      v_next_status := coalesce(p_patch->>'status', v_prev_status);
      -- 合并允许的补丁字段
      foreach v_key in array v_allowed loop
        if p_patch ? v_key then
          v_elem := jsonb_set(v_elem, array[v_key], p_patch->v_key, true);
        end if;
      end loop;
      v_elem := jsonb_set(v_elem, '{status}', to_jsonb(v_next_status), true);
      if v_next_status = 'running' and (v_elem->>'started_at') is null then
        v_elem := jsonb_set(v_elem, '{started_at}', to_jsonb(v_now), true);
      end if;
      if v_next_status in ('done','failed','stopped') then
        v_elem := jsonb_set(v_elem, '{finished_at}', to_jsonb(v_now), true);
      end if;
    end if;
    v_new_items := v_new_items || v_elem;
  end loop;

  -- 未匹配到则追加一个新元素（与原 Python 行为一致）
  if not v_matched then
    v_new_items := v_new_items || jsonb_build_object(
      'section_id', p_section_id,
      'title', coalesce(p_patch->>'title', '未命名章节'),
      'status', coalesce(p_patch->>'status', 'queued'),
      'percent', coalesce((p_patch->>'percent')::int, 0),
      'chars', coalesce((p_patch->>'chars')::int, 0),
      'message', p_patch->>'message',
      'error', p_patch->>'error',
      'generated_content', coalesce(p_patch->>'generated_content', ''),
      'chunk_seq', coalesce((p_patch->>'chunk_seq')::int, 0),
      'chunk_events', coalesce(p_patch->'chunk_events', '[]'::jsonb),
      'metadata', coalesce(p_patch->'metadata', '{}'::jsonb)
    );
  end if;

  -- 重算计数
  for v_elem in select * from jsonb_array_elements(v_new_items) loop
    case coalesce(v_elem->>'status','queued')
      when 'running' then v_running := v_running + 1;
      when 'done' then v_done := v_done + 1;
      when 'failed' then v_failed := v_failed + 1;
      when 'stopped' then v_stopped := v_stopped + 1;
      else v_queued := v_queued + 1;
    end case;
  end loop;

  -- 总体状态：取消优先；全部终态后按是否有失败/停止判定
  if v_task_status = 'cancelled' then
    v_status := 'cancelled';
  elsif v_running > 0 or v_queued > 0 then
    v_status := 'running';
  elsif v_failed > 0 and v_done > 0 then
    v_status := 'partial_failed';
  elsif v_failed > 0 then
    v_status := 'failed';
  elsif v_stopped > 0 and v_done = 0 then
    v_status := 'cancelled';
  else
    v_status := 'completed';
  end if;

  return query
  update public.bid_generation_tasks
    set items = v_new_items,
        status = v_status,
        queued_count = v_queued,
        running_count = v_running,
        done_count = v_done,
        failed_count = v_failed,
        stopped_count = v_stopped,
        started_at = case when v_status = 'running' and started_at is null then now() else started_at end,
        finished_at = case when v_status in ('completed','failed','partial_failed','cancelled') then now() else finished_at end
    where id = p_task_id and project_id = p_project_id
    returning *;
end;
$$;

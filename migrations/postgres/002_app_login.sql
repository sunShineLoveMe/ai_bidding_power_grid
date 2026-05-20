alter table public.app_users
  alter column fingerprint_id drop not null,
  add column if not exists username text,
  add column if not exists password_hash text,
  add column if not exists display_name text,
  add column if not exists company_name text,
  add column if not exists role text not null default 'member',
  add column if not exists status text not null default 'active',
  add column if not exists last_login_at timestamptz,
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists idx_app_users_username_lower
  on public.app_users(lower(username))
  where username is not null;

drop trigger if exists trg_app_users_updated_at on public.app_users;
create trigger trg_app_users_updated_at
before update on public.app_users
for each row execute function public.set_updated_at();

-- App local runtime tables for replacing the early SQLite-only tables.
-- Execute this in Supabase SQL editor before disabling SQLite fallback.

create extension if not exists pgcrypto;

create table if not exists app_users (
  id uuid primary key default gen_random_uuid(),
  fingerprint_id text unique not null,
  created_at timestamptz not null default now()
);

comment on table app_users is '单机版本地操作人员识别表，用于替代早期 SQLite users 表。';
comment on column app_users.fingerprint_id is '浏览器本地生成的匿名指纹，仅用于单机版识别当前操作人员。';

create table if not exists onlyoffice_documents (
  id uuid primary key default gen_random_uuid(),
  document_key text unique not null,
  project_id uuid references bid_projects(id) on delete cascade,
  title text not null,
  file_path text not null,
  download_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table onlyoffice_documents is 'OnlyOffice 文档 key 与本地生成文件路径映射，用于保存回调定位目标文件。';

create index if not exists idx_onlyoffice_documents_project_id
  on onlyoffice_documents(project_id);

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_onlyoffice_documents_updated_at on onlyoffice_documents;
create trigger trg_onlyoffice_documents_updated_at
before update on onlyoffice_documents
for each row execute function set_updated_at();


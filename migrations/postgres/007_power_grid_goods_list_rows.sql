-- P1/P4: 客户货物清单结构化行表
-- 用途：在 document_chunks 的 table_summary/table_row 向量召回之外，保留可精确过滤的
-- package/material/spec/quantity 等字段，避免 `.xlsx` 清单只依赖语义检索。

create table if not exists public.power_grid_goods_list_rows (
  id uuid primary key default gen_random_uuid(),
  knowledge_document_id uuid references public.knowledge_documents(id) on delete cascade,
  ingestion_batch_id text not null,
  province text,
  batch_no text,
  package_no text,
  package_code text,
  material_category text,
  source_file text,
  sheet_name text,
  row_number int,
  bid_section_no text,
  package_name text,
  subpackage_no text,
  project_unit text,
  demand_unit text,
  project_name text,
  voltage_level text,
  item_name text,
  item_description text,
  unit text,
  quantity text,
  delivery_date_first text,
  delivery_date_last text,
  delivery_place text,
  delivery_method text,
  technical_spec_code text,
  material_code text,
  row_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (knowledge_document_id, sheet_name, row_number)
);

create index if not exists idx_power_grid_goods_rows_batch
  on public.power_grid_goods_list_rows (ingestion_batch_id);

create index if not exists idx_power_grid_goods_rows_package
  on public.power_grid_goods_list_rows (province, package_code);

create index if not exists idx_power_grid_goods_rows_material_code
  on public.power_grid_goods_list_rows (material_code);

create index if not exists idx_power_grid_goods_rows_spec_code
  on public.power_grid_goods_list_rows (technical_spec_code);

create index if not exists idx_power_grid_goods_rows_row_data
  on public.power_grid_goods_list_rows using gin (row_data);

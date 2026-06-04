#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_SERVICE="${DB_SERVICE:-postgres}"
DB_USER="${POSTGRES_USER:-bidding}"
DB_NAME="${POSTGRES_DB:-bidding}"

PSQL=(docker compose exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME")

run_sql_file() {
  local file="$1"
  if [[ ! -f "$ROOT_DIR/$file" ]]; then
    echo "missing SQL file: $file" >&2
    exit 1
  fi
  echo "applying $file"
  "${PSQL[@]}" < "$ROOT_DIR/$file"
}

echo "initializing PostgreSQL schema: service=$DB_SERVICE db=$DB_NAME user=$DB_USER"

run_sql_file "migrations/postgres/001_schema.sql"
run_sql_file "migrations/postgres/002_app_login.sql"
run_sql_file "migrations/postgres/003_seed_deepseek_v4_flash_pricing.sql"
run_sql_file "migrations/postgres/004_seed_deepseek_v4_pro_pricing.sql"
run_sql_file "migrations/postgres/005_bid_parse_tasks.sql"
run_sql_file "migrations/postgres/006_rag_p0_filtered_recall.sql"
run_sql_file "migrations/postgres/007_power_grid_goods_list_rows.sql"
run_sql_file "sql/20260603_create_bid_generation_task_items.sql"
run_sql_file "sql/20260603_add_bid_generation_task_item_lease.sql"
run_sql_file "migrations/postgres/007_atomic_section_task_item.sql"
run_sql_file "sql/20260603_update_bid_generation_task_status_model.sql"

echo "verifying core tables" 
"${PSQL[@]}" -At -c "
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'bid_projects',
    'bid_files',
    'bid_analysis',
    'bid_sections',
    'knowledge_documents',
    'document_chunks',
    'knowledge_assets',
    'app_users',
    'ai_usage_logs',
    'bid_generation_tasks',
    'bid_generation_task_items',
    'bid_generation_task_events',
    'bid_export_tasks',
    'bid_parse_tasks',
    'power_grid_goods_list_rows'
  )
order by table_name;
"

echo "verifying section generation RPC functions"
"${PSQL[@]}" -At -c "
select proname || '(' || oidvectortypes(proargtypes) || ')'
from pg_proc
where pronamespace = 'public'::regnamespace
  and proname in (
    'lease_bid_generation_task_items',
    'heartbeat_bid_generation_task_item',
    'expire_bid_generation_task_items',
    'update_bid_generation_task_item_atomic',
    'set_bid_generation_task_items_updated_at'
  )
order by proname;
"

echo "PostgreSQL schema initialization complete."

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_init_postgres_schema_includes_section_generation_migrations():
    script = (ROOT / "scripts" / "init_postgres_schema.sh").read_text()

    required_files = [
        "migrations/postgres/006_rag_p0_filtered_recall.sql",
        "migrations/postgres/007_power_grid_goods_list_rows.sql",
        "sql/20260603_create_bid_generation_task_items.sql",
        "sql/20260603_add_bid_generation_task_item_lease.sql",
        "migrations/postgres/007_atomic_section_task_item.sql",
        "migrations/postgres/008_bid_interpretation_tasks.sql",
        "migrations/postgres/009_bid_project_modes.sql",
        "sql/20260603_update_bid_generation_task_status_model.sql",
    ]
    for file_path in required_files:
        assert f'run_sql_file "{file_path}"' in script

    required_objects = [
        "bid_generation_task_items",
        "bid_generation_task_events",
        "lease_bid_generation_task_items",
        "heartbeat_bid_generation_task_item",
        "expire_bid_generation_task_items",
        "update_bid_generation_task_item_atomic",
        "bid_interpretation_tasks",
        "project_mode",
    ]
    for object_name in required_objects:
        assert object_name in script


def test_section_task_atomic_update_allows_item_metadata_patch():
    status_model_sql = (ROOT / "sql" / "20260603_update_bid_generation_task_status_model.sql").read_text()
    atomic_sql = (ROOT / "migrations" / "postgres" / "007_atomic_section_task_item.sql").read_text()

    assert "'metadata'" in status_model_sql
    assert "'metadata'" in atomic_sql


def test_bid_project_mode_migration_defaults_legacy_projects_to_general():
    migration = (ROOT / "migrations" / "postgres" / "009_bid_project_modes.sql").read_text()

    assert "add column if not exists project_mode" in migration
    assert "default 'general'" in migration
    assert "project_mode in ('general', 'taichang_reuse')" in migration
    assert "bid_projects_project_mode_check" in migration

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
    ]
    for object_name in required_objects:
        assert object_name in script

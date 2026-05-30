"""baseline postgres schema

Revision ID: 20260530_0001
Revises:
Create Date: 2026-05-30 00:00:00.000000
"""

from __future__ import annotations

from pathlib import Path

from alembic import op


revision = "20260530_0001"
down_revision = None
branch_labels = None
depends_on = None


SQL_FILES = (
    "001_schema.sql",
    "002_app_login.sql",
    "003_seed_deepseek_v4_flash_pricing.sql",
    "004_seed_deepseek_v4_pro_pricing.sql",
)


def _postgres_migration_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "postgres"


def upgrade() -> None:
    base_dir = _postgres_migration_dir()
    connection = op.get_bind()
    for filename in SQL_FILES:
        connection.exec_driver_sql((base_dir / filename).read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("Baseline PostgreSQL migration downgrade is not supported.")

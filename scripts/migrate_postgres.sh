#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -z "${DATABASE_URL:-}" ]]; then
  POSTGRES_USER="${POSTGRES_USER:-bidding}"
  POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-bidding_local_dev}"
  POSTGRES_DB="${POSTGRES_DB:-bidding}"
  POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
  POSTGRES_PORT="${POSTGRES_PORT:-15432}"
  export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
fi

ALEMBIC_BIN="${ALEMBIC_BIN:-venv/bin/alembic}"
if [[ ! -x "$ALEMBIC_BIN" ]]; then
  ALEMBIC_BIN="alembic"
fi

echo "running PostgreSQL migrations with Alembic"
"$ALEMBIC_BIN" upgrade head
"$ALEMBIC_BIN" current

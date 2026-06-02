#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

source .venv/bin/activate

export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:16379/0}"
export CELERY_WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-2}"

exec celery -A backend.tasks.celery_app:celery_app worker --loglevel=info --concurrency="${CELERY_WORKER_CONCURRENCY}"

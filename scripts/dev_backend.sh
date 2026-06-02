#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

source .venv/bin/activate

export PORT="${PORT:-3012}"
export WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:16379/0}"

exec gunicorn -c gunicorn.conf.py --reload main:app

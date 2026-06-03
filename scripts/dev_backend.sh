#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

source .venv/bin/activate

# 单一事实来源：显式加载 .env，保证 web 与 worker 环境一致。
# main.py 内也有 load_dotenv()，这里提前导出可让 gunicorn.conf.py 等
# 在 app import 前读取的变量也生效。
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export PORT="${PORT:-3012}"
export WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:16379/0}"

exec gunicorn -c gunicorn.conf.py --reload main:app

#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

source .venv/bin/activate

# 单一事实来源：显式加载 .env，保证 worker 与 web 环境一致。
# celery_app 在 import 期即读取 REDIS_URL 等变量，且 worker 任务需要
# DASHSCOPE/EMBEDDING/DATABASE 等配置，因此必须在启动前导出 .env。
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:16379/0}"
# worker 并发度：默认 4，配合章节并行编写。
export CELERY_WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"
# 全文编写时并行编写的章节数（恢复"多路 DeepSeek 同时编写"）。
export SECTION_GEN_CONCURRENCY="${SECTION_GEN_CONCURRENCY:-3}"

# Worker 池类型：默认 threads。
# 原因：默认的 prefork 池在 macOS + 新版 Python 上 fork() 已初始化线程/网络/
# Objective-C 运行时的父进程时会死锁——表现为"任务已 received 但永不执行"。
# 本项目任务以 IO 等待为主（LLM/HTTP/DB），threads 池无需 fork、且与线程安全的
# DB 连接池兼容，最稳妥。如需切回可设 CELERY_POOL=prefork。
export CELERY_POOL="${CELERY_POOL:-threads}"

exec celery -A backend.tasks.celery_app:celery_app worker \
  --loglevel=info \
  --pool="${CELERY_POOL}" \
  --concurrency="${CELERY_WORKER_CONCURRENCY}"

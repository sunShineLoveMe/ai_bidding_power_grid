import os
import time
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from flask import Blueprint, jsonify

from backend.db.supabase_client import get_bucket_name, get_supabase_client


bp = Blueprint("health", __name__)


def _check_database() -> dict:
    url = os.getenv("DATABASE_URL")
    if not url:
        return {"status": "fail", "message": "DATABASE_URL is not configured"}
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            row = conn.execute(
                """
                select
                  exists(select 1 from pg_extension where extname = 'vector') as vector_ok,
                  exists(select 1 from pg_proc where proname = 'match_knowledge_chunks') as chunks_rpc_ok,
                  exists(select 1 from pg_proc where proname = 'match_knowledge_assets') as assets_rpc_ok
                """
            ).fetchone()
        checks = {
            "vector": bool(row[0]),
            "match_knowledge_chunks": bool(row[1]),
            "match_knowledge_assets": bool(row[2]),
        }
        return {"status": "ok" if all(checks.values()) else "fail", "checks": checks}
    except Exception as exc:
        return {"status": "fail", "message": f"{type(exc).__name__}: {exc}"}


def _check_redis() -> dict:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return {"status": "warn", "message": "REDIS_URL is not configured"}
    parsed = urlparse(redis_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 6379
    try:
        import socket

        with socket.create_connection((host, port), timeout=2) as sock:
            sock.sendall(b"PING\r\n")
            response = sock.recv(16)
        if response.startswith(b"+PONG"):
            return {"status": "ok", "host": host, "port": port}
        return {"status": "fail", "message": f"unexpected response: {response!r}"}
    except Exception as exc:
        return {"status": "fail", "message": f"{type(exc).__name__}: {exc}"}


def _check_storage() -> dict:
    provider = (os.getenv("STORAGE_PROVIDER") or "local").lower()
    try:
        if provider == "oss":
            bucket = get_bucket_name("knowledge")
            client = get_supabase_client()
            # Build the bucket client to validate required OSS configuration without writing objects.
            client.storage.from_(bucket)
            return {"status": "ok", "provider": "oss", "bucket": bucket}

        root = Path(os.getenv("LOCAL_STORAGE_ROOT") or "storage")
        root.mkdir(parents=True, exist_ok=True)
        if not os.access(root, os.W_OK):
            return {"status": "fail", "provider": "local", "message": f"{root} is not writable"}
        return {"status": "ok", "provider": "local", "root": str(root)}
    except Exception as exc:
        return {"status": "fail", "provider": provider, "message": f"{type(exc).__name__}: {exc}"}


def _check_model_config() -> dict:
    required = {
        "deepseek_api_key": bool(os.getenv("DEEPSEEK_API_KEY")),
        "dashscope_api_key": bool(os.getenv("DASHSCOPE_API_KEY")),
    }
    optional = {
        "mineru_api_token": bool(os.getenv("MINERU_API_TOKEN") or os.getenv("MINERU_TOKEN")),
    }
    status = "ok" if all(required.values()) else "warn"
    return {"status": status, "required": required, "optional": optional}


@bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@bp.route("/ready")
def ready():
    started = time.time()
    checks = {
        "database": _check_database(),
        "redis": _check_redis(),
        "storage": _check_storage(),
        "model_config": _check_model_config(),
    }
    overall = "ok" if all(item["status"] in {"ok", "warn"} for item in checks.values()) and checks["database"]["status"] == "ok" and checks["storage"]["status"] == "ok" else "fail"
    status_code = 200 if overall == "ok" else 503
    return jsonify(
        {
            "status": overall,
            "checks": checks,
            "duration_ms": int((time.time() - started) * 1000),
        }
    ), status_code

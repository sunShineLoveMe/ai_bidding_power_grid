import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gevent")
workers = int(os.getenv("WEB_CONCURRENCY", os.getenv("GUNICORN_WORKERS", "4")))
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "1000"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

_access_log = os.getenv("GUNICORN_ACCESS_LOG", "none")
accesslog = None if _access_log.lower() == "none" else _access_log
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
capture_output = True

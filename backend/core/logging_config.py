from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator

from flask import g, request

from backend.core.security import sanitize_exception_message


_LOG_CONTEXT: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("log_context", default={})

STANDARD_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}

LOG_CONTEXT_KEYS = {
    "request_id",
    "app_module",
    "stage",
    "project_id",
    "file_id",
    "task_id",
    "section_id",
    "user_id",
    "celery_task_id",
    "celery_task_name",
}

SENSITIVE_HEADER_NAMES = {"authorization", "cookie", "x-app-auth-token", "set-cookie"}


def _json_default(value: Any) -> str:
    return str(value)


def _new_request_id() -> str:
    return f"req_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}"


def get_log_context() -> dict[str, Any]:
    return dict(_LOG_CONTEXT.get() or {})


def set_log_context(**values: Any) -> None:
    current = get_log_context()
    for key, value in values.items():
        if value is not None:
            current[key] = str(value)
    _LOG_CONTEXT.set(current)


def clear_log_context() -> None:
    _LOG_CONTEXT.set({})


@contextlib.contextmanager
def log_context(**values: Any) -> Iterator[None]:
    token = _LOG_CONTEXT.set({**get_log_context(), **{k: str(v) for k, v in values.items() if v is not None}})
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = get_log_context()
        for key in LOG_CONTEXT_KEYS:
            if not hasattr(record, key):
                setattr(record, key, context.get(key))
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = sanitize_exception_message(record.getMessage())
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": getattr(record, "app_module", None) or record.name,
            "stage": getattr(record, "stage", None),
            "request_id": getattr(record, "request_id", None),
            "message": message,
        }

        for key in ("project_id", "file_id", "task_id", "section_id", "user_id", "celery_task_id", "celery_task_name"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        for key, value in record.__dict__.items():
            if key in STANDARD_RECORD_ATTRS or key in LOG_CONTEXT_KEYS:
                continue
            if key.lower() in SENSITIVE_HEADER_NAMES:
                payload[key] = "***"
                continue
            if key.startswith("_"):
                continue
            payload[key] = sanitize_exception_message(value) if isinstance(value, str) else value

        if record.exc_info:
            payload["exception"] = sanitize_exception_message(self.formatException(record.exc_info))
        if record.stack_info:
            payload["stack"] = sanitize_exception_message(record.stack_info)

        return json.dumps({k: v for k, v in payload.items() if v is not None}, ensure_ascii=False, default=_json_default)


class SanitizingTextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return sanitize_exception_message(super().format(record))


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json").strip().lower()

    handler = logging.StreamHandler()
    handler.addFilter(ContextFilter())
    if log_format in {"text", "plain"}:
        handler.setFormatter(
            SanitizingTextFormatter("%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s")
        )
    else:
        handler.setFormatter(JsonLogFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for noisy_logger in ("werkzeug",):
        logging.getLogger(noisy_logger).setLevel(os.getenv("ACCESS_LOG_LEVEL", "WARNING").upper())


def register_request_logging(app) -> None:
    @app.before_request
    def _start_request_log_context():
        request_id = request.headers.get("X-Request-Id") or _new_request_id()
        g.request_id = request_id
        g.request_started_at = time.perf_counter()
        user_id = None
        current_user = getattr(g, "current_user", None)
        if isinstance(current_user, dict):
            user_id = current_user.get("sub") or current_user.get("id")
        set_log_context(
            request_id=request_id,
            app_module="http",
            stage="request",
            user_id=user_id,
        )

    @app.after_request
    def _finish_request_log_context(response):
        request_id = getattr(g, "request_id", None) or get_log_context().get("request_id") or _new_request_id()
        started_at = getattr(g, "request_started_at", None)
        duration_ms = int((time.perf_counter() - started_at) * 1000) if started_at else None
        user_id = None
        current_user = getattr(g, "current_user", None)
        if isinstance(current_user, dict):
            user_id = current_user.get("sub") or current_user.get("id")
        response.headers["X-Request-Id"] = request_id
        logging.info(
            "http_request_completed",
            extra={
                "app_module": "http",
                "stage": "request",
                "request_id": request_id,
                "user_id": user_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip(),
            },
        )
        return response

    @app.teardown_request
    def _clear_request_log_context(_exc):
        clear_log_context()

"""Lightweight PostgreSQL connection pooling for the local compat layer.

psycopg's official pool lives in a separate package, but this project currently
only depends on psycopg[binary]. This small pool keeps the deployment dependency
surface unchanged while avoiding a new TCP connection for every DB operation.
"""

from __future__ import annotations

import atexit
import os
import queue
import threading
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    return default


def _pool_max_size() -> int:
    return max(1, int(os.getenv("POSTGRES_POOL_MAX_SIZE", "10") or 10))


def _pool_timeout_seconds() -> float:
    return max(0.1, float(os.getenv("POSTGRES_POOL_TIMEOUT_SECONDS", "5") or 5))


class SimplePostgresPool:
    def __init__(self, url: str, *, row_factory: Any = dict_row, max_size: int = 10):
        self.url = url
        self.row_factory = row_factory
        self.max_size = max(1, int(max_size))
        self._idle: queue.LifoQueue = queue.LifoQueue()
        self._lock = threading.Lock()
        self._created = 0

    def _new_connection(self):
        return psycopg.connect(self.url, row_factory=self.row_factory)

    def acquire(self, timeout: float):
        try:
            return self._idle.get_nowait()
        except queue.Empty:
            pass

        with self._lock:
            if self._created < self.max_size:
                conn = self._new_connection()
                self._created += 1
                return conn

        return self._idle.get(timeout=timeout)

    def release(self, conn, *, commit: bool) -> None:
        if getattr(conn, "closed", False):
            with self._lock:
                self._created = max(0, self._created - 1)
            return
        try:
            if commit:
                # Match psycopg's connection context manager: commit on a clean
                # exit so callers that rely on `with psycopg.connect()` semantics
                # keep working when moved to the pool.
                conn.commit()
            else:
                conn.rollback()
        except Exception:
            try:
                conn.close()
            finally:
                with self._lock:
                    self._created = max(0, self._created - 1)
            return
        self._idle.put(conn)

    def close(self) -> None:
        while True:
            try:
                conn = self._idle.get_nowait()
            except queue.Empty:
                break
            try:
                conn.close()
            finally:
                with self._lock:
                    self._created = max(0, self._created - 1)


_POOLS: dict[tuple[str, int, int], SimplePostgresPool] = {}
_POOLS_LOCK = threading.Lock()


def _pool_key(url: str, row_factory: Any) -> tuple[str, int, int]:
    return (url, id(row_factory), _pool_max_size())


def _get_pool(url: str, row_factory: Any = dict_row) -> SimplePostgresPool:
    key = _pool_key(url, row_factory)
    with _POOLS_LOCK:
        pool = _POOLS.get(key)
        if pool is None:
            pool = SimplePostgresPool(url, row_factory=row_factory, max_size=key[2])
            _POOLS[key] = pool
        return pool


@contextmanager
def pooled_connection(url: str, *, row_factory: Any = dict_row) -> Iterator[Any]:
    """Return a psycopg connection, pooled unless POSTGRES_POOL_ENABLED=false."""
    if not _env_bool("POSTGRES_POOL_ENABLED", True):
        with psycopg.connect(url, row_factory=row_factory) as conn:
            yield conn
        return

    pool = _get_pool(url, row_factory)
    conn = pool.acquire(timeout=_pool_timeout_seconds())
    should_commit = False
    try:
        yield conn
        should_commit = True
    finally:
        pool.release(conn, commit=should_commit)


def reset_postgres_pools() -> None:
    """Close idle pooled connections. Intended for tests and process shutdown."""
    with _POOLS_LOCK:
        pools = list(_POOLS.values())
        _POOLS.clear()
    for pool in pools:
        pool.close()


atexit.register(reset_postgres_pools)

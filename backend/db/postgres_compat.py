import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.db.postgres_pool import pooled_connection


JSONB_COLUMNS = {
    ("bid_analysis", "project_meta"),
    ("bid_analysis", "qualification_requirements"),
    ("bid_analysis", "document_checklist"),
    ("bid_analysis", "scoring_items"),
    ("bid_analysis", "risk_items"),
    ("bid_analysis", "chapter_suggestions"),
    ("bid_chapter_suggestions", "related_requirements"),
    ("bid_sections", "response_points"),
    ("bid_sections", "mapped_requirements"),
    ("bid_sections", "mapped_scoring_items"),
    ("bid_sections", "mapped_risks"),
    ("bid_sections", "required_materials"),
    ("bid_sections", "source_pages"),
    ("bid_sections", "writing_notes"),
    ("bid_sections", "metadata"),
    ("knowledge_documents", "metadata"),
    ("document_chunks", "metadata"),
    ("power_grid_goods_list_rows", "row_data"),
    ("knowledge_assets", "specs"),
    ("knowledge_assets", "metadata"),
    ("ai_model_prices", "metadata"),
    ("ai_usage_logs", "prompt_tokens_details"),
    ("ai_usage_logs", "completion_tokens_details"),
    ("ai_usage_logs", "raw_usage"),
    ("ai_usage_logs", "metadata"),
    ("bid_generation_tasks", "items"),
    ("bid_generation_tasks", "metadata"),
    ("bid_export_tasks", "metadata"),
}

VECTOR_COLUMNS = {
    ("document_chunks", "embedding"),
    ("knowledge_assets", "embedding"),
}


@dataclass
class PostgresResponse:
    data: list[dict[str, Any]]
    count: int | None = None


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _adapt_value(table: str, column: str, value: Any) -> Any:
    if value is None:
        return None
    if (table, column) in JSONB_COLUMNS:
        return Jsonb(value)
    if (table, column) in VECTOR_COLUMNS and isinstance(value, list):
        return "[" + ",".join(str(item) for item in value) + "]"
    return value


def _selected_columns(select_expr: str | None) -> str:
    if not select_expr or select_expr.strip() == "*":
        return "*"
    columns = []
    for raw in select_expr.split(","):
        column = raw.strip()
        if not column:
            continue
        if column == "*":
            columns.append("*")
        elif "->" in column or "(" in column:
            columns.append(column)
        else:
            columns.append(f'"{column}"')
    return ", ".join(columns) or "*"


@lru_cache(maxsize=1)
def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required when DB_PROVIDER=postgres")
    return url


class PostgresTableQuery:
    def __init__(self, client: "PostgresCompatClient", table: str):
        self.client = client
        self.table = table
        self._action = "select"
        self._select = "*"
        self._count: str | None = None
        self._payload: Any = None
        self._filters: list[tuple[str, str, Any]] = []
        self._orders: list[tuple[str, bool]] = []
        self._limit: int | None = None
        self._range: tuple[int, int] | None = None
        self._on_conflict: str | None = None

    def select(self, columns: str = "*", count: str | None = None) -> "PostgresTableQuery":
        self._action = "select"
        self._select = columns
        self._count = count
        return self

    def insert(self, payload: Any) -> "PostgresTableQuery":
        self._action = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> "PostgresTableQuery":
        self._action = "update"
        self._payload = payload
        return self

    def upsert(self, payload: Any, on_conflict: str | None = None) -> "PostgresTableQuery":
        self._action = "upsert"
        self._payload = payload
        self._on_conflict = on_conflict
        return self

    def delete(self) -> "PostgresTableQuery":
        self._action = "delete"
        return self

    def eq(self, column: str, value: Any) -> "PostgresTableQuery":
        self._filters.append((column, "=", value))
        return self

    def gte(self, column: str, value: Any) -> "PostgresTableQuery":
        self._filters.append((column, ">=", value))
        return self

    def in_(self, column: str, values: list[Any]) -> "PostgresTableQuery":
        self._filters.append((column, "in", values))
        return self

    def order(self, column: str, desc: bool = False) -> "PostgresTableQuery":
        self._orders.append((column, desc))
        return self

    def limit(self, value: int) -> "PostgresTableQuery":
        self._limit = int(value)
        return self

    def range(self, start: int, end: int) -> "PostgresTableQuery":
        self._range = (int(start), int(end))
        return self

    def execute(self) -> PostgresResponse:
        if self._action == "select":
            return self._execute_select()
        if self._action == "insert":
            return self._execute_insert(self._payload)
        if self._action == "update":
            return self._execute_update()
        if self._action == "delete":
            return self._execute_delete()
        if self._action == "upsert":
            return self._execute_upsert()
        raise RuntimeError(f"Unsupported action: {self._action}")

    def _where_clause(self, params: list[Any]) -> str:
        clauses = []
        for column, op, value in self._filters:
            if op == "in":
                values = list(value or [])
                if not values:
                    clauses.append("false")
                else:
                    placeholders = ", ".join(["%s"] * len(values))
                    clauses.append(f'"{column}" in ({placeholders})')
                    params.extend(values)
            else:
                clauses.append(f'"{column}" {op} %s')
                params.append(value)
        return " where " + " and ".join(clauses) if clauses else ""

    def _execute_select(self) -> PostgresResponse:
        params: list[Any] = []
        columns = _selected_columns(self._select)
        sql = f'select {columns} from public."{self.table}"'
        sql += self._where_clause(params)
        if self._orders:
            order_sql = []
            for column, desc in self._orders:
                order_sql.append(f'"{column}" {"desc" if desc else "asc"}')
            sql += " order by " + ", ".join(order_sql)
        if self._range:
            start, end = self._range
            sql += " limit %s offset %s"
            params.extend([end - start + 1, start])
        elif self._limit is not None:
            sql += " limit %s"
            params.append(self._limit)

        count = None
        if self._count == "exact":
            count_params: list[Any] = []
            count_sql = f'select count(*) as count from public."{self.table}"'
            count_sql += self._where_clause(count_params)
            with self.client.connection() as conn:
                count = conn.execute(count_sql, count_params).fetchone()["count"]
                rows = conn.execute(sql, params).fetchall()
        else:
            with self.client.connection() as conn:
                rows = conn.execute(sql, params).fetchall()
        return PostgresResponse([_jsonable(dict(row)) for row in rows], count=count)

    def _execute_insert(self, payload: Any) -> PostgresResponse:
        rows = payload if isinstance(payload, list) else [payload]
        if not rows:
            return PostgresResponse([])
        columns = list(rows[0].keys())
        placeholders = "(" + ", ".join(["%s"] * len(columns)) + ")"
        values = []
        for row in rows:
            values.extend(_adapt_value(self.table, column, row.get(column)) for column in columns)
        sql = (
            f'insert into public."{self.table}" ('
            + ", ".join(f'"{column}"' for column in columns)
            + ") values "
            + ", ".join([placeholders] * len(rows))
            + " returning *"
        )
        with self.client.connection() as conn:
            result = conn.execute(sql, values).fetchall()
            conn.commit()
        return PostgresResponse([_jsonable(dict(row)) for row in result])

    def _execute_update(self) -> PostgresResponse:
        payload = self._payload or {}
        params = [_adapt_value(self.table, column, value) for column, value in payload.items()]
        sql = (
            f'update public."{self.table}" set '
            + ", ".join(f'"{column}" = %s' for column in payload.keys())
        )
        sql += self._where_clause(params)
        sql += " returning *"
        with self.client.connection() as conn:
            result = conn.execute(sql, params).fetchall()
            conn.commit()
        return PostgresResponse([_jsonable(dict(row)) for row in result])

    def _execute_delete(self) -> PostgresResponse:
        params: list[Any] = []
        sql = f'delete from public."{self.table}"'
        sql += self._where_clause(params)
        sql += " returning *"
        with self.client.connection() as conn:
            result = conn.execute(sql, params).fetchall()
            conn.commit()
        return PostgresResponse([_jsonable(dict(row)) for row in result])

    def _execute_upsert(self) -> PostgresResponse:
        rows = self._payload if isinstance(self._payload, list) else [self._payload]
        if not rows:
            return PostgresResponse([])
        columns = list(rows[0].keys())
        conflict = self._on_conflict
        if not conflict and all(row.get("id") for row in rows):
            conflict = "id"
        if not conflict:
            return self._execute_insert(rows)
        update_columns = [column for column in columns if column not in {part.strip() for part in conflict.split(",")}]
        placeholders = "(" + ", ".join(["%s"] * len(columns)) + ")"
        params = []
        for row in rows:
            params.extend(_adapt_value(self.table, column, row.get(column)) for column in columns)
        sql = (
            f'insert into public."{self.table}" ('
            + ", ".join(f'"{column}"' for column in columns)
            + ") values "
            + ", ".join([placeholders] * len(rows))
            + f" on conflict ({conflict}) "
        )
        if update_columns:
            sql += "do update set " + ", ".join(f'"{column}" = excluded."{column}"' for column in update_columns)
        else:
            sql += "do nothing"
        sql += " returning *"
        with self.client.connection() as conn:
            result = conn.execute(sql, params).fetchall()
            conn.commit()
        return PostgresResponse([_jsonable(dict(row)) for row in result])


class PostgresRpcQuery:
    def __init__(self, client: "PostgresCompatClient", name: str, params: dict[str, Any]):
        self.client = client
        self.name = name
        self.params = params or {}

    def execute(self) -> PostgresResponse:
        if self.name == "match_knowledge_chunks":
            sql = "select * from public.match_knowledge_chunks(%s::vector, %s, %s)"
            params = [
                self._vector(self.params.get("query_embedding")),
                self.params.get("match_threshold", 0.5),
                self.params.get("match_count", 5),
            ]
        elif self.name == "match_knowledge_chunks_filtered":
            sql = (
                "select * from public.match_knowledge_chunks_filtered("
                "%s::vector, %s, %s, %s, %s::uuid)"
            )
            params = [
                self._vector(self.params.get("query_embedding")),
                self.params.get("match_threshold", 0.3),
                self.params.get("match_count", 8),
                Jsonb(self.params.get("filter_metadata") or {}),
                self.params.get("filter_project_id"),
            ]
        elif self.name == "get_parent_chunk":
            sql = "select * from public.get_parent_chunk(%s::uuid, %s)"
            params = [
                self.params.get("p_document_id"),
                self.params.get("p_parent_index"),
            ]
        elif self.name == "update_bid_generation_task_item_atomic":
            sql = (
                "select * from public.update_bid_generation_task_item_atomic("
                "%s::uuid, %s::uuid, %s, %s)"
            )
            params = [
                self.params.get("p_project_id"),
                self.params.get("p_task_id"),
                self.params.get("p_section_id"),
                Jsonb(self.params.get("p_patch") or {}),
            ]
        elif self.name == "match_knowledge_assets":
            sql = "select * from public.match_knowledge_assets(%s::vector, %s, %s, %s, %s)"
            params = [
                self._vector(self.params.get("query_embedding")),
                self.params.get("match_count", 8),
                self.params.get("filter_category"),
                self.params.get("filter_asset_type"),
                self.params.get("filter_applicable_volume"),
            ]
        else:
            raise RuntimeError(f"Unsupported PostgreSQL RPC: {self.name}")
        with self.client.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return PostgresResponse([_jsonable(dict(row)) for row in rows])

    @staticmethod
    def _vector(value: Any) -> str:
        if isinstance(value, list):
            return "[" + ",".join(str(item) for item in value) + "]"
        return str(value or "[]")


class LocalStorageBucket:
    def __init__(self, root: Path, bucket: str):
        self.root = root
        self.bucket = bucket

    def _path(self, object_path: str) -> Path:
        return self.root / self.bucket / object_path

    def upload(self, path: str, file: bytes | bytearray | str | Path, file_options: dict[str, Any] | None = None) -> dict[str, Any]:
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(file, (str, Path)):
            shutil.copyfile(file, target)
        else:
            target.write_bytes(bytes(file))
        return {"path": path, "fullPath": f"{self.bucket}/{path}"}

    def download(self, path: str) -> bytes:
        return self._path(path).read_bytes()

    def get_public_url(self, path: str) -> str:
        return f"/local-storage/{self.bucket}/{path}"

    def create_signed_urls(self, paths: list[str], expires_in: int) -> list[dict[str, str]]:
        return [
            {"path": path, "signedURL": self.get_public_url(path)}
            for path in paths
            if self._path(path).exists()
        ]


class LocalStorageClient:
    def __init__(self, root: Path):
        self.root = root

    def from_(self, bucket: str) -> LocalStorageBucket:
        return LocalStorageBucket(self.root, bucket)


class OSSStorageBucket:
    def __init__(self, oss2_module: Any, bucket_name: str):
        endpoint = os.getenv("OSS_ENDPOINT")
        access_key_id = os.getenv("OSS_ACCESS_KEY_ID")
        access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET")
        if not endpoint or not access_key_id or not access_key_secret:
            raise RuntimeError("OSS_ENDPOINT, OSS_ACCESS_KEY_ID and OSS_ACCESS_KEY_SECRET are required when STORAGE_PROVIDER=oss")
        self.oss2 = oss2_module
        self.bucket_name = bucket_name
        self.endpoint = endpoint.rstrip("/")
        self.public_endpoint = (os.getenv("OSS_PUBLIC_ENDPOINT") or self.endpoint).rstrip("/")
        self.key_prefix = (os.getenv("OSS_KEY_PREFIX") or "").strip("/")
        auth = self.oss2.Auth(access_key_id, access_key_secret)
        self.bucket = self.oss2.Bucket(auth, self.endpoint, bucket_name)

    def _key(self, object_path: str) -> str:
        path = str(object_path or "").lstrip("/")
        return f"{self.key_prefix}/{path}" if self.key_prefix else path

    def upload(self, path: str, file: bytes | bytearray | str | Path, file_options: dict[str, Any] | None = None) -> dict[str, Any]:
        key = self._key(path)
        headers: dict[str, str] = {}
        content_type = (file_options or {}).get("content-type") or (file_options or {}).get("Content-Type")
        if content_type:
            headers["Content-Type"] = str(content_type)
        if isinstance(file, (str, Path)):
            self.bucket.put_object_from_file(key, str(file), headers=headers or None)
        else:
            self.bucket.put_object(key, bytes(file), headers=headers or None)
        return {"path": path, "fullPath": f"{self.bucket_name}/{key}"}

    def download(self, path: str) -> bytes:
        return self.bucket.get_object(self._key(path)).read()

    def get_public_url(self, path: str) -> str:
        key = self._key(path)
        if (os.getenv("OSS_PUBLIC_READ") or "").lower() in {"true", "1", "yes"}:
            endpoint = self.public_endpoint
            if endpoint.startswith(("http://", "https://")):
                return f"{endpoint}/{quote(key)}"
            return f"https://{self.bucket_name}.{endpoint}/{quote(key)}"
        return self.bucket.sign_url("GET", key, int(os.getenv("OSS_SIGNED_URL_EXPIRES", "3600")))

    def create_signed_urls(self, paths: list[str], expires_in: int) -> list[dict[str, str]]:
        signed: list[dict[str, str]] = []
        for path in paths:
            key = self._key(path)
            signed.append({"path": path, "signedURL": self.bucket.sign_url("GET", key, int(expires_in))})
        return signed


class OSSStorageClient:
    def __init__(self):
        try:
            import oss2
        except ImportError as exc:
            raise RuntimeError("oss2 package is required when STORAGE_PROVIDER=oss") from exc
        self.oss2 = oss2

    def from_(self, bucket: str) -> OSSStorageBucket:
        return OSSStorageBucket(self.oss2, bucket)


class PostgresCompatClient:
    def __init__(self):
        if (os.getenv("STORAGE_PROVIDER") or "local").lower() == "oss":
            self.storage = OSSStorageClient()
        else:
            self.storage = LocalStorageClient(Path(os.getenv("LOCAL_STORAGE_ROOT", "storage")))

    def connection(self):
        return pooled_connection(_database_url(), row_factory=dict_row)

    def table(self, table: str) -> PostgresTableQuery:
        return PostgresTableQuery(self, table)

    def rpc(self, name: str, params: dict[str, Any]) -> PostgresRpcQuery:
        return PostgresRpcQuery(self, name, params)

import os
import logging
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


class SupabaseConfigError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return a backend Supabase client.

    The service role key is preferred because this module runs only on the
    Flask backend and needs to write private Storage buckets and project tables.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise SupabaseConfigError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(url, key)


def reset_supabase_client() -> None:
    get_supabase_client.cache_clear()


def get_bucket_name(kind: str) -> str:
    env_key = {
        "tender": "SUPABASE_STORAGE_TENDER_BUCKET",
        "generated": "SUPABASE_STORAGE_GENERATED_BUCKET",
        "knowledge": "SUPABASE_STORAGE_KNOWLEDGE_BUCKET",
        "qualification": "SUPABASE_STORAGE_QUALIFICATION_BUCKET",
        "product": "SUPABASE_STORAGE_PRODUCT_BUCKET",
    }.get(kind)
    if not env_key:
        raise SupabaseConfigError(f"Unsupported storage bucket kind: {kind}")
    bucket = os.getenv(env_key)
    if not bucket:
        raise SupabaseConfigError(f"{env_key} is required")
    return bucket


def upload_file_to_storage(bucket: str, object_path: str, file_path: str | Path, content_type: str | None = None) -> Any:
    options: dict[str, str] = {"upsert": "true"}
    if content_type:
        options["content-type"] = content_type

    with open(file_path, "rb") as f:
        data = f.read()

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            client = get_supabase_client()
            return client.storage.from_(bucket).upload(
                path=object_path,
                file=data,
                file_options=options,
            )
        except Exception as exc:
            last_error = exc
            logging.warning(
                "Supabase Storage 上传失败，第 %s 次: bucket=%s object=%s error=%s",
                attempt,
                bucket,
                object_path,
                exc,
            )
            if attempt >= 3:
                break
            reset_supabase_client()
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Supabase Storage 上传失败，已重试 3 次: {last_error}") from last_error

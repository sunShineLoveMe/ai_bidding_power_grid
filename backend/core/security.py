import logging
import mimetypes
import os
from pathlib import Path
from typing import Iterable

from flask import Request, current_app, jsonify, request
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge


DEFAULT_ALLOWED_CORS_ORIGINS = {
    "http://127.0.0.1:3012",
    "http://localhost:3012",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
}

DEFAULT_TENDER_EXTENSIONS = {"pdf", "doc", "docx", "txt", "md"}
DEFAULT_KNOWLEDGE_EXTENSIONS = {"pdf", "doc", "docx", "txt", "md", "xls", "xlsx", "csv", "png", "jpg", "jpeg", "webp"}
DEFAULT_ASSET_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf", "doc", "docx"}
DEFAULT_ZIP_EXTENSIONS = {"zip"}

DEFAULT_MIME_PREFIXES = {
    "text/",
    "image/",
}

DEFAULT_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
    "application/x-zip-compressed",
    "text/csv",
}

PLACEHOLDER_VALUES = {
    "",
    "change_me",
    "replace_me",
    "your_deepseek_api_key",
    "your_dashscope_api_key",
    "your_supabase_anon_key",
    "your_supabase_service_role_key",
    "replace_with_a_strong_secret",
    "fsdftertrt34768586sfhjsdhfjhhjfsuhaiubue",
}


class UploadValidationError(ValueError):
    pass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_csv_env(name: str, default: Iterable[str] | None = None) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_cors_origins() -> list[str]:
    origins = parse_csv_env("APP_CORS_ORIGINS", DEFAULT_ALLOWED_CORS_ORIGINS)
    if "*" in origins and is_production_mode():
        raise RuntimeError("生产环境禁止 APP_CORS_ORIGINS 使用 *，请配置明确的前端域名白名单。")
    return origins


def is_production_mode() -> bool:
    return os.getenv("APP_ENV", "").strip().lower() in {"prod", "production"} or env_bool("REQUIRE_STRICT_CONFIG", False)


def validate_startup_security() -> None:
    if not is_production_mode():
        return

    missing = []
    provider = os.getenv("AI_PROVIDER", "deepseek").strip().lower()
    required_keys = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    if provider == "deepseek":
        required_keys.append("DEEPSEEK_API_KEY")
    else:
        required_keys.append("DASHSCOPE_API_KEY")
    # 当前知识库向量化和 Rerank 默认仍依赖 DashScope。
    required_keys.append("DASHSCOPE_API_KEY")

    for key in required_keys:
        value = os.getenv(key, "").strip()
        if value in PLACEHOLDER_VALUES:
            missing.append(key)

    onlyoffice_secret = os.getenv("ONLYOFFICE_JWT_SECRET", "").strip()
    if onlyoffice_secret in PLACEHOLDER_VALUES or len(onlyoffice_secret) < 24:
        missing.append("ONLYOFFICE_JWT_SECRET")

    if env_bool("APP_AUTH_ENABLED", False):
        token = os.getenv("APP_AUTH_TOKEN", "").strip()
        if token in PLACEHOLDER_VALUES or len(token) < 24:
            missing.append("APP_AUTH_TOKEN")

    if missing:
        raise RuntimeError(f"生产环境缺少或使用弱配置: {', '.join(sorted(set(missing)))}")


def _client_is_local(req: Request) -> bool:
    remote = req.headers.get("X-Forwarded-For", req.remote_addr or "").split(",")[0].strip()
    return remote in {"127.0.0.1", "::1", "localhost"} or remote.startswith("192.168.") or remote.startswith("10.")


def enforce_request_guard() -> tuple[object, int] | None:
    if request.method == "OPTIONS":
        return None
    if request.path.startswith("/assets/") or request.path.startswith("/api/health"):
        return None
    if env_bool("APP_LOCAL_ONLY", False) and not _client_is_local(request):
        return jsonify({"error": "当前服务仅允许本地或内网访问。"}), 403
    if not env_bool("APP_AUTH_ENABLED", False):
        return None

    expected = os.getenv("APP_AUTH_TOKEN", "").strip()
    supplied = request.headers.get("X-App-Auth-Token", "").strip()
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        supplied = auth[7:].strip()
    if not expected or supplied != expected:
        return jsonify({"error": "未授权访问，请检查访问令牌。"}), 401
    return None


def sanitize_exception_message(message: str) -> str:
    text = str(message or "")
    for key in ("DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY", "MINERU_API_TOKEN", "ONLYOFFICE_JWT_SECRET"):
        value = os.getenv(key)
        if value:
            text = text.replace(value, "***")
    if len(text) > 300:
        text = text[:300] + "..."
    return text


def should_expose_debug_errors() -> bool:
    return env_bool("APP_EXPOSE_DEBUG_ERRORS", False) and not is_production_mode()


def register_security_handlers(app) -> None:
    @app.before_request
    def _security_guard():
        return enforce_request_guard()

    @app.errorhandler(RequestEntityTooLarge)
    def _handle_upload_too_large(_exc):
        max_mb = int(os.getenv("MAX_UPLOAD_MB", "200") or 200)
        return jsonify({"error": f"上传文件超过大小限制，当前限制为 {max_mb} MB。"}), 413

    @app.after_request
    def _sanitize_500_json(response):
        if response.status_code < 500 or should_expose_debug_errors() or not response.is_json:
            return response
        payload = response.get_json(silent=True)
        if isinstance(payload, dict) and payload.get("error"):
            logging.warning("已脱敏 500 错误响应: %s", sanitize_exception_message(payload.get("error")))
            response.set_data(jsonify({"error": "服务器处理失败，请联系管理员查看后端日志。"}).get_data())
        return response


def _allowed_extensions_from_env(env_name: str, defaults: set[str]) -> set[str]:
    values = parse_csv_env(env_name)
    return {value.lower().lstrip(".") for value in values} if values else set(defaults)


def _is_allowed_mime(mime_type: str | None) -> bool:
    if not mime_type:
        return True
    lowered = mime_type.lower()
    return lowered in DEFAULT_MIME_TYPES or any(lowered.startswith(prefix) for prefix in DEFAULT_MIME_PREFIXES)


def validate_uploaded_file(file: FileStorage, *, kind: str) -> None:
    filename = (file.filename or "").strip()
    if not filename:
        raise UploadValidationError("未选择文件。")
    suffix = Path(filename).suffix.lower().lstrip(".")
    if kind == "tender":
        allowed = _allowed_extensions_from_env("ALLOWED_TENDER_EXTENSIONS", DEFAULT_TENDER_EXTENSIONS)
    elif kind == "knowledge":
        allowed = _allowed_extensions_from_env("ALLOWED_KNOWLEDGE_EXTENSIONS", DEFAULT_KNOWLEDGE_EXTENSIONS)
    elif kind == "asset":
        allowed = _allowed_extensions_from_env("ALLOWED_ASSET_EXTENSIONS", DEFAULT_ASSET_EXTENSIONS)
    elif kind == "mineru_zip":
        allowed = DEFAULT_ZIP_EXTENSIONS
    else:
        allowed = DEFAULT_KNOWLEDGE_EXTENSIONS

    if suffix not in allowed:
        raise UploadValidationError(f"文件类型 .{suffix or 'unknown'} 不在允许范围内。允许类型：{', '.join(sorted(allowed))}。")

    guessed_type = mimetypes.guess_type(filename)[0]
    content_type = (file.mimetype or guessed_type or "").lower()
    if content_type and not _is_allowed_mime(content_type):
        raise UploadValidationError(f"文件 MIME 类型 {content_type} 不在允许范围内。")


def safe_upload_filename(original_filename: str, fallback: str = "upload") -> str:
    from werkzeug.utils import secure_filename

    original = original_filename or ""
    suffix = Path(original).suffix.lower()
    safe = secure_filename(original)
    if safe and Path(safe).suffix:
        return safe

    stem = secure_filename(Path(original).stem) or fallback
    if suffix and suffix.isascii():
        return f"{stem}{suffix}"
    return stem

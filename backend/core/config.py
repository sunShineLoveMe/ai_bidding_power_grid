import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path("config")
CONFIG_FILE = CONFIG_DIR / "runtime_settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "ai_provider": "deepseek",
    "text_model": "deepseek-v4-flash",
    "interpretation_model": "deepseek-v4-pro",
    "interpretation_segment_model": "deepseek-v4-flash",
    "outline_model": "deepseek-v4-pro",
    "compliance_model": "deepseek-v4-pro",
    "section_writing_model": "deepseek-v4-flash",
    "section_supplement_model": "deepseek-v4-flash",
    "knowledge_model": "deepseek-v4-flash",
    "knowledge_followup_model": "deepseek-v4-flash",
    "deepseek_base_url": "https://api.deepseek.com",
    "embedding_model": "text-embedding-v4",
    "embedding_dimensions": 1024,
    "rerank_enabled": True,
    "rerank_model": "qwen3-rerank",
    "rerank_top_n": 6,
    "request_timeout_seconds": 120,
    "reasoning_request_timeout_seconds": 300,
    "interpretation_segment_max_chars": 24000,
    "interpretation_segment_max_groups": 24,
    "stream_connect_timeout_seconds": 15,
    "stream_read_timeout_seconds": 180,
    "max_retries": 2,
    "retry_base_delay_seconds": 1.5,
    "retry_max_delay_seconds": 12,
    "retry_status_codes": "429,500,502,503,504",
    "upload_dir": "uploads/",
    "output_dir": "outputs/",
    "vector_store": "supabase_pgvector",
    "chroma_dir": "chroma_db/",
    "sqlite_db": "bidding.db",
    "onlyoffice_url": "http://localhost:8080",
    "backend_public_url": "http://host.docker.internal:3012",
    "word_template": "templates/default_bid_template.docx",
    "online_editing_enabled": True,
    "auto_backup_enabled": True,
    "backup_frequency": "daily",
    "backup_dir": "backups/",
    "enterprise_name": "某水利工程建设企业",
    "enterprise_region": "华中地区",
    "enterprise_industry": "水利水电工程建设与工程配套服务",
    "enterprise_business_scope": "水利工程施工、金属结构件、机电设备配套、质量检验、交付保障和现场服务",
    "enterprise_advantages": "具备水利工程项目响应、质量安全管理、资料编制、供应链协同和现场履约能力",
    "enterprise_target_customers": "水利工程建设单位、总承包单位、监理单位和设备供应链配套单位",
    "enterprise_response_style": "专业、严谨、合规、可落地；不得编造证书编号、人员姓名、合同金额、具体日期和未提供的企业业绩",
}

ENV_MAPPING = {
    "ai_provider": "AI_PROVIDER",
    "text_model": "DASHSCOPE_MODEL",
    "interpretation_model": "INTERPRETATION_MODEL",
    "interpretation_segment_model": "INTERPRETATION_SEGMENT_MODEL",
    "outline_model": "OUTLINE_MODEL",
    "compliance_model": "COMPLIANCE_MODEL",
    "section_writing_model": "SECTION_WRITING_MODEL",
    "section_supplement_model": "SECTION_SUPPLEMENT_MODEL",
    "knowledge_model": "DASHSCOPE_KNOWLEDGE_MODEL",
    "knowledge_followup_model": "KNOWLEDGE_FOLLOWUP_MODEL",
    "deepseek_base_url": "DEEPSEEK_BASE_URL",
    "embedding_model": "DASHSCOPE_EMBEDDING_MODEL",
    "embedding_dimensions": "DASHSCOPE_EMBEDDING_DIMENSIONS",
    "rerank_enabled": "DASHSCOPE_RERANK_ENABLED",
    "rerank_model": "DASHSCOPE_RERANK_MODEL",
    "rerank_top_n": "DASHSCOPE_RERANK_TOP_N",
    "request_timeout_seconds": "DASHSCOPE_REQUEST_TIMEOUT_SECONDS",
    "reasoning_request_timeout_seconds": "REASONING_REQUEST_TIMEOUT_SECONDS",
    "interpretation_segment_max_chars": "INTERPRETATION_SEGMENT_MAX_CHARS",
    "interpretation_segment_max_groups": "INTERPRETATION_SEGMENT_MAX_GROUPS",
    "stream_connect_timeout_seconds": "DASHSCOPE_STREAM_CONNECT_TIMEOUT_SECONDS",
    "stream_read_timeout_seconds": "DASHSCOPE_STREAM_READ_TIMEOUT_SECONDS",
    "max_retries": "DASHSCOPE_MAX_RETRIES",
    "retry_base_delay_seconds": "DASHSCOPE_RETRY_BASE_DELAY_SECONDS",
    "retry_max_delay_seconds": "DASHSCOPE_RETRY_MAX_DELAY_SECONDS",
    "retry_status_codes": "DASHSCOPE_RETRY_STATUS_CODES",
    "upload_dir": "UPLOAD_DIR",
    "output_dir": "OUTPUT_DIR",
    "chroma_dir": "CHROMA_DIR",
    "sqlite_db": "SQLITE_DB_PATH",
    "onlyoffice_url": "ONLYOFFICE_DOCUMENT_SERVER_URL",
    "backend_public_url": "APP_PUBLIC_BASE_URL",
    "word_template": "WORD_TEMPLATE_PATH",
    "backup_dir": "BACKUP_DIR",
    "enterprise_name": "ENTERPRISE_NAME",
    "enterprise_region": "ENTERPRISE_REGION",
    "enterprise_industry": "ENTERPRISE_INDUSTRY",
    "enterprise_business_scope": "ENTERPRISE_BUSINESS_SCOPE",
    "enterprise_advantages": "ENTERPRISE_ADVANTAGES",
    "enterprise_target_customers": "ENTERPRISE_TARGET_CUSTOMERS",
    "enterprise_response_style": "ENTERPRISE_RESPONSE_STYLE",
}

INT_KEYS = {
    "request_timeout_seconds",
    "reasoning_request_timeout_seconds",
    "interpretation_segment_max_chars",
    "interpretation_segment_max_groups",
    "stream_connect_timeout_seconds",
    "stream_read_timeout_seconds",
    "embedding_dimensions",
    "rerank_top_n",
    "max_retries",
}

FLOAT_KEYS = {
    "retry_base_delay_seconds",
    "retry_max_delay_seconds",
}

BOOL_KEYS = {
    "online_editing_enabled",
    "auto_backup_enabled",
    "rerank_enabled",
}


def _coerce_value(key: str, value: Any) -> Any:
    if key in INT_KEYS:
        try:
            return int(value)
        except (TypeError, ValueError):
            return DEFAULT_SETTINGS[key]
    if key in BOOL_KEYS:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "on"}
    if key in FLOAT_KEYS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return DEFAULT_SETTINGS[key]
    return value


def load_runtime_settings() -> dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)

    # Environment variables provide deploy-time defaults for open-source users.
    for key, env_key in ENV_MAPPING.items():
        env_value = os.getenv(env_key)
        if env_value not in {None, ""}:
            settings[key] = env_value

    provider = str(settings.get("ai_provider") or "").lower()
    if provider == "deepseek":
        deepseek_model = os.getenv("DEEPSEEK_MODEL")
        deepseek_knowledge_model = os.getenv("DEEPSEEK_KNOWLEDGE_MODEL") or deepseek_model
        stage_envs = {
            "interpretation_model": "DEEPSEEK_INTERPRETATION_MODEL",
            "interpretation_segment_model": "DEEPSEEK_INTERPRETATION_SEGMENT_MODEL",
            "outline_model": "DEEPSEEK_OUTLINE_MODEL",
            "compliance_model": "DEEPSEEK_COMPLIANCE_MODEL",
            "section_writing_model": "DEEPSEEK_SECTION_WRITING_MODEL",
            "section_supplement_model": "DEEPSEEK_SECTION_SUPPLEMENT_MODEL",
            "knowledge_followup_model": "DEEPSEEK_KNOWLEDGE_FOLLOWUP_MODEL",
        }
        if deepseek_model:
            settings["text_model"] = deepseek_model
        else:
            settings["text_model"] = DEFAULT_SETTINGS["text_model"]
        if deepseek_knowledge_model:
            settings["knowledge_model"] = deepseek_knowledge_model
        else:
            settings["knowledge_model"] = DEFAULT_SETTINGS["knowledge_model"]
        for key, env_key in stage_envs.items():
            env_value = os.getenv(env_key)
            if env_value not in {None, ""}:
                settings[key] = env_value
            elif not settings.get(key):
                settings[key] = DEFAULT_SETTINGS[key]
        if os.getenv("DEEPSEEK_BASE_URL"):
            settings["deepseek_base_url"] = os.getenv("DEEPSEEK_BASE_URL")

    # Runtime UI settings intentionally override non-sensitive env defaults so
    # changes from the settings page take effect without editing .env.
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                settings.update({key: saved[key] for key in DEFAULT_SETTINGS.keys() & saved.keys()})
        except json.JSONDecodeError:
            pass

    return {key: _coerce_value(key, value) for key, value in settings.items()}


def save_runtime_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = load_runtime_settings()
    allowed = {key: payload[key] for key in DEFAULT_SETTINGS.keys() & payload.keys()}
    current.update({key: _coerce_value(key, value) for key, value in allowed.items()})
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_runtime_settings()


def get_setting(key: str, default: Any = None) -> Any:
    return load_runtime_settings().get(key, default)


def get_stage_model(stage: str, default: str | None = None) -> str:
    settings = load_runtime_settings()
    key_by_stage = {
        "interpretation": "interpretation_model",
        "interpretation_segment": "interpretation_segment_model",
        "outline": "outline_model",
        "compliance": "compliance_model",
        "section_writing": "section_writing_model",
        "section_supplement": "section_supplement_model",
        "knowledge": "knowledge_model",
        "knowledge_followup": "knowledge_followup_model",
    }
    key = key_by_stage.get(stage, "text_model")
    return str(settings.get(key) or default or settings.get("text_model") or DEFAULT_SETTINGS["text_model"])


def get_enterprise_profile() -> dict[str, str]:
    settings = load_runtime_settings()
    keys = [
        "enterprise_name",
        "enterprise_region",
        "enterprise_industry",
        "enterprise_business_scope",
        "enterprise_advantages",
        "enterprise_target_customers",
        "enterprise_response_style",
    ]
    return {key: str(settings.get(key) or DEFAULT_SETTINGS[key]).strip() for key in keys}


def build_enterprise_context() -> str:
    profile = get_enterprise_profile()
    return (
        f"服务对象：{profile['enterprise_name']}。\n"
        f"所属区域：{profile['enterprise_region']}。\n"
        f"行业定位：{profile['enterprise_industry']}。\n"
        f"业务范围：{profile['enterprise_business_scope']}。\n"
        f"核心能力：{profile['enterprise_advantages']}。\n"
        f"目标客户：{profile['enterprise_target_customers']}。\n"
        f"写作约束：{profile['enterprise_response_style']}。"
    )

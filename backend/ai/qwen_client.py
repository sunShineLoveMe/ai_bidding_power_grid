from flask import Blueprint, request, jsonify, current_app
import os
import sqlite3
import requests
from datetime import datetime
from unidecode import unidecode
from werkzeug.utils import secure_filename
import logging
import json
from backend.core.config import build_enterprise_context, get_setting
from backend.db.supabase_repo import record_ai_usage_log
import time

# 文本生成模型配置。函数名保留 call_dashscope_api/stream_dashscope_api，
# 兼容历史业务代码；内部按 ai_provider 路由到 DashScope 或 DeepSeek。
AI_PROVIDER = os.getenv('AI_PROVIDER', 'dashscope')


class DashScopeRetryableError(RuntimeError):
    def __init__(self, message, status_code=None, retry_after=None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class LLMRetryableError(RuntimeError):
    def __init__(self, message, status_code=None, retry_after=None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


def _active_provider() -> str:
    return str(get_setting("ai_provider", os.getenv("AI_PROVIDER", "dashscope")) or "dashscope").lower()


def _provider_label() -> str:
    provider = _active_provider()
    if provider == "deepseek":
        return "DeepSeek"
    if provider == "dashscope":
        return "DashScope"
    return provider


def _dashscope_api_key() -> str | None:
    return os.getenv("DASHSCOPE_API_KEY")


def _deepseek_api_key() -> str | None:
    return os.getenv("DEEPSEEK_API_KEY")


def _deepseek_base_url() -> str:
    return str(get_setting("deepseek_base_url", os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")) or "https://api.deepseek.com").rstrip("/")


def _deepseek_chat_url() -> str:
    return f"{_deepseek_base_url()}/chat/completions"


def _dashscope_timeout():
    return int(get_setting("request_timeout_seconds", 120))


def _llm_request_timeout(context: dict | None = None, model: str | None = None) -> int:
    stage = str((context or {}).get("stage") or "")
    model_name = str(model or "")
    reasoning_stages = {
        "ai_interpretation_report",
        "ai_interpretation_merge",
        "bid_outline_generation",
        "semantic_compliance_review",
        "compliance_supplement",
    }
    if stage in reasoning_stages or model_name.endswith("-pro"):
        return int(get_setting("reasoning_request_timeout_seconds", 300))
    return _dashscope_timeout()


def _stream_timeout():
    return (
        int(get_setting("stream_connect_timeout_seconds", 15)),
        int(get_setting("stream_read_timeout_seconds", 180)),
    )


def _max_attempts() -> int:
    retries = int(get_setting("max_retries", 2) or 0)
    return max(1, retries + 1)


def _retry_status_codes() -> set[int]:
    raw_value = str(get_setting("retry_status_codes", "429,500,502,503,504") or "")
    status_codes = set()
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            status_codes.add(int(item))
        except ValueError:
            logging.warning("忽略无效的 DashScope 重试状态码配置: %s", item)
    return status_codes or {429, 500, 502, 503, 504}


def _retry_delay_seconds(attempt: int, retry_after=None) -> float:
    if retry_after:
        try:
            return min(float(retry_after), float(get_setting("retry_max_delay_seconds", 12)))
        except (TypeError, ValueError):
            pass
    base_delay = float(get_setting("retry_base_delay_seconds", 1.5))
    max_delay = float(get_setting("retry_max_delay_seconds", 12))
    return min(max_delay, base_delay * (2 ** max(0, attempt - 1)))


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (DashScopeRetryableError, LLMRetryableError)):
        return True
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    response = getattr(exc, "response", None)
    return bool(response is not None and response.status_code in _retry_status_codes())


def _raise_for_dashscope_status(response):
    if response.status_code == 200:
        return

    message = f"DashScope API 调用失败，状态码: {response.status_code}"
    logging.warning(message)
    if response.status_code in _retry_status_codes():
        raise DashScopeRetryableError(
            message,
            status_code=response.status_code,
            retry_after=response.headers.get("Retry-After"),
        )
    response.raise_for_status()


def _raise_for_llm_status(response, provider_label: str):
    if response.status_code == 200:
        return

    message = f"{provider_label} API 调用失败，状态码: {response.status_code}"
    logging.warning("%s，响应片段: %s", message, response.text[:600])
    if response.status_code in _retry_status_codes():
        raise LLMRetryableError(
            message,
            status_code=response.status_code,
            retry_after=response.headers.get("Retry-After"),
        )
    response.raise_for_status()


def _public_error(exc: Exception) -> Exception:
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if response is not None:
        status_code = response.status_code
    if status_code == 429:
        return RuntimeError("模型服务限流，请稍后重试；如频繁出现，请降低并发或调整模型服务配额。")
    if _is_retryable_error(exc):
        return RuntimeError("模型服务临时不可用，已自动重试但仍失败，请稍后重新执行。")
    return exc


def _retry_metadata(context: dict, json_mode=None, attempt=1, success=False, retryable=False):
    metadata = dict(context.get("metadata") or {})
    if json_mode is not None:
        metadata["json_mode"] = json_mode
    metadata.update({
        "attempts": attempt,
        "retry_attempts": max(0, attempt - 1),
        "max_retries": _max_attempts() - 1,
        "retryable": retryable,
        "final_success": success,
    })
    return metadata


def _log_retry(exc: Exception, attempt: int, max_attempts: int):
    delay = _retry_delay_seconds(attempt, getattr(exc, "retry_after", None))
    logging.warning(
        "%s 调用临时失败，将在 %.1fs 后重试 (%s/%s): %s",
        _provider_label(),
        delay,
        attempt,
        max_attempts - 1,
        exc,
    )
    time.sleep(delay)


def _messages_text(messages) -> str:
    return "\n".join(str(message.get("content") or "") for message in (messages or []) if isinstance(message, dict))


def _response_content(payload: dict) -> str:
    try:
        return payload.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content") or ""
    except Exception:
        return ""


def _openai_response_content(payload: dict) -> str:
    try:
        return payload.get("choices", [{}])[0].get("message", {}).get("content") or ""
    except Exception:
        return ""


def _openai_to_dashscope_payload(payload: dict, model: str) -> dict:
    content = _openai_response_content(payload)
    return {
        "request_id": payload.get("id"),
        "model": payload.get("model") or model,
        "usage": payload.get("usage") or {},
        "output": {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": (payload.get("choices") or [{}])[0].get("finish_reason"),
                }
            ]
        },
        "raw_response": payload,
    }


def _call_deepseek_api(messages, model=None, json_mode=True, usage_context=None):
    api_key = _deepseek_api_key()
    if not api_key:
        raise Exception("DEEPSEEK_API_KEY is not set")

    url = _deepseek_chat_url()
    resolved_model = model or get_setting("text_model", "deepseek-v4-flash")
    context = usage_context or {}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": resolved_model,
        "messages": messages,
    }
    if json_mode:
        data["response_format"] = {"type": "json_object"}

    response = None
    started_at = time.time()
    attempts = _max_attempts()

    for attempt in range(1, attempts + 1):
        try:
            stage = context.get("stage") or ("json_generation" if json_mode else "text_generation")
            timeout_seconds = _llm_request_timeout(context, resolved_model)
            logging.info(
                "DeepSeek 调用开始: stage=%s model=%s json_mode=%s attempt=%s/%s timeout=%ss",
                stage,
                resolved_model,
                json_mode,
                attempt,
                attempts,
                timeout_seconds,
            )
            response = requests.post(url, headers=headers, json=data, timeout=timeout_seconds)
            _raise_for_llm_status(response, "DeepSeek")
            raw_payload = response.json()
            payload = _openai_to_dashscope_payload(raw_payload, resolved_model)
            latency_ms = int((time.time() - started_at) * 1000)
            logging.info(
                "DeepSeek 调用完成: stage=%s model=%s status=%s latency_ms=%s",
                stage,
                payload.get("model") or resolved_model,
                response.status_code,
                latency_ms,
            )
            record_ai_usage_log(
                provider="deepseek",
                region="global",
                api_protocol="openai_compatible",
                endpoint=url,
                model=payload.get("model") or resolved_model,
                operation_type=context.get("operation_type") or "text_generation",
                stage=context.get("stage") or ("json_generation" if json_mode else "text_generation"),
                project_id=context.get("project_id"),
                file_id=context.get("file_id"),
                section_id=context.get("section_id"),
                batch_id=context.get("batch_id"),
                request_id=payload.get("request_id"),
                status_code=response.status_code,
                latency_ms=latency_ms,
                raw_usage=payload.get("usage") or {},
                input_text=_messages_text(messages),
                output_text=_response_content(payload),
                metadata=_retry_metadata(
                    context,
                    json_mode=json_mode,
                    attempt=attempt,
                    success=True,
                ) | {"provider": "deepseek", "base_url": _deepseek_base_url()},
            )
            return payload
        except Exception as exc:
            retryable = _is_retryable_error(exc)
            if retryable and attempt < attempts:
                _log_retry(exc, attempt, attempts)
                continue
            logging.exception(
                "DeepSeek 调用失败: stage=%s model=%s attempt=%s/%s",
                context.get("stage") or ("json_generation" if json_mode else "text_generation"),
                resolved_model,
                attempt,
                attempts,
            )

            record_ai_usage_log(
                provider="deepseek",
                region="global",
                api_protocol="openai_compatible",
                endpoint=url,
                model=resolved_model,
                operation_type=context.get("operation_type") or "text_generation",
                stage=context.get("stage") or ("json_generation" if json_mode else "text_generation"),
                project_id=context.get("project_id"),
                file_id=context.get("file_id"),
                section_id=context.get("section_id"),
                batch_id=context.get("batch_id"),
                status_code=response.status_code if response is not None else getattr(exc, "status_code", None),
                latency_ms=int((time.time() - started_at) * 1000),
                raw_usage={},
                input_text=_messages_text(messages),
                success=False,
                error_message=str(exc),
                metadata=_retry_metadata(context, json_mode=json_mode, attempt=attempt, retryable=retryable)
                | {"provider": "deepseek", "base_url": _deepseek_base_url()},
            )
            raise _public_error(exc)


def _stream_deepseek_api(messages, model=None, usage_context=None):
    api_key = _deepseek_api_key()
    if not api_key:
        raise Exception("DEEPSEEK_API_KEY is not set")

    url = _deepseek_chat_url()
    resolved_model = model or get_setting("text_model", "deepseek-v4-flash")
    context = usage_context or {}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": resolved_model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    response = None
    output_parts = []
    last_usage = {}
    last_request_id = None
    started_at = time.time()
    attempts = _max_attempts()

    for attempt in range(1, attempts + 1):
        has_yielded = bool(output_parts)
        try:
            with requests.post(url, headers=headers, json=data, stream=True, timeout=_stream_timeout()) as response:
                _raise_for_llm_status(response, "DeepSeek")
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if not line or line == "[DONE]":
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    last_request_id = payload.get("id") or last_request_id
                    if payload.get("usage"):
                        last_usage = payload.get("usage") or {}
                    choice = (payload.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content:
                        output_parts.append(content)
                        has_yielded = True
                        yield content
            record_ai_usage_log(
                provider="deepseek",
                region="global",
                api_protocol="openai_compatible",
                endpoint=url,
                model=resolved_model,
                operation_type=context.get("operation_type") or "text_generation",
                stage=context.get("stage") or "stream_text_generation",
                project_id=context.get("project_id"),
                file_id=context.get("file_id"),
                section_id=context.get("section_id"),
                batch_id=context.get("batch_id"),
                request_id=last_request_id,
                is_stream=True,
                include_usage=bool(last_usage),
                status_code=response.status_code if response is not None else None,
                latency_ms=int((time.time() - started_at) * 1000),
                raw_usage=last_usage,
                input_text=_messages_text(messages),
                output_text="".join(output_parts),
                metadata=_retry_metadata(context, attempt=attempt, success=True)
                | {"provider": "deepseek", "base_url": _deepseek_base_url()},
            )
            return
        except Exception as exc:
            retryable = _is_retryable_error(exc)
            can_retry = retryable and not has_yielded and attempt < attempts
            if can_retry:
                _log_retry(exc, attempt, attempts)
                continue

            record_ai_usage_log(
                provider="deepseek",
                region="global",
                api_protocol="openai_compatible",
                endpoint=url,
                model=resolved_model,
                operation_type=context.get("operation_type") or "text_generation",
                stage=context.get("stage") or "stream_text_generation",
                project_id=context.get("project_id"),
                file_id=context.get("file_id"),
                section_id=context.get("section_id"),
                batch_id=context.get("batch_id"),
                is_stream=True,
                include_usage=bool(last_usage),
                status_code=response.status_code if response is not None else getattr(exc, "status_code", None),
                latency_ms=int((time.time() - started_at) * 1000),
                raw_usage=last_usage,
                input_text=_messages_text(messages),
                output_text="".join(output_parts),
                success=False,
                error_message=str(exc),
                metadata=_retry_metadata(context, attempt=attempt, retryable=retryable)
                | {"provider": "deepseek", "base_url": _deepseek_base_url()},
            )
            raise _public_error(exc)


def call_dashscope_api(messages, model=None, json_mode=True, usage_context=None):
    if _active_provider() == "deepseek":
        return _call_deepseek_api(messages, model=model, json_mode=json_mode, usage_context=usage_context)

    if not _dashscope_api_key():
        raise Exception("DASHSCOPE_API_KEY is not set")
    url = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation'
    resolved_model = model or get_setting("text_model", "qwen-turbo-latest")
    context = usage_context or {}
    headers = {
        'Authorization': f'Bearer {_dashscope_api_key()}',
        'Content-Type': 'application/json'
    }

    data = {
        'model': resolved_model,
        'input': {
            'messages': messages
        }
    }
    if json_mode:
        data['parameters'] = {'result_format': 'json_object'}
    else:
        data['parameters'] = {'result_format': 'message'}
    
    response = None
    started_at = time.time()
    attempts = _max_attempts()

    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=_dashscope_timeout())
            _raise_for_dashscope_status(response)
            payload = response.json()
            record_ai_usage_log(
                provider="dashscope",
                region="cn-beijing",
                api_protocol="dashscope",
                endpoint=url,
                model=payload.get("model") or resolved_model,
                operation_type=context.get("operation_type") or "text_generation",
                stage=context.get("stage") or ("json_generation" if json_mode else "text_generation"),
                project_id=context.get("project_id"),
                file_id=context.get("file_id"),
                section_id=context.get("section_id"),
                batch_id=context.get("batch_id"),
                request_id=payload.get("request_id"),
                status_code=response.status_code,
                latency_ms=int((time.time() - started_at) * 1000),
                raw_usage=payload.get("usage") or {},
                input_text=_messages_text(messages),
                output_text=_response_content(payload),
                metadata=_retry_metadata(context, json_mode=json_mode, attempt=attempt, success=True),
            )
            return payload
        except Exception as exc:
            retryable = _is_retryable_error(exc)
            if retryable and attempt < attempts:
                _log_retry(exc, attempt, attempts)
                continue

            record_ai_usage_log(
                provider="dashscope",
                region="cn-beijing",
                api_protocol="dashscope",
                endpoint=url,
                model=resolved_model,
                operation_type=context.get("operation_type") or "text_generation",
                stage=context.get("stage") or ("json_generation" if json_mode else "text_generation"),
                project_id=context.get("project_id"),
                file_id=context.get("file_id"),
                section_id=context.get("section_id"),
                batch_id=context.get("batch_id"),
                status_code=response.status_code if response is not None else getattr(exc, "status_code", None),
                latency_ms=int((time.time() - started_at) * 1000),
                raw_usage={},
                input_text=_messages_text(messages),
                success=False,
                error_message=str(exc),
                metadata=_retry_metadata(context, json_mode=json_mode, attempt=attempt, retryable=retryable),
            )
            raise _public_error(exc)


def stream_dashscope_api(messages, model=None, usage_context=None):
    """Stream DashScope text generation chunks.

    DashScope's SSE response usually emits lines prefixed with "data:".
    The parser is intentionally tolerant so local deployments can fall back
    cleanly if the provider response shape changes.
    """
    if _active_provider() == "deepseek":
        yield from _stream_deepseek_api(messages, model=model, usage_context=usage_context)
        return

    if not _dashscope_api_key():
        raise Exception("DASHSCOPE_API_KEY is not set")

    url = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation'
    resolved_model = model or get_setting("text_model", "qwen-turbo-latest")
    context = usage_context or {}
    headers = {
        'Authorization': f'Bearer {_dashscope_api_key()}',
        'Content-Type': 'application/json',
        'X-DashScope-SSE': 'enable',
    }
    data = {
        'model': resolved_model,
        'input': {
            'messages': messages
        },
        'parameters': {
            'result_format': 'message',
            'incremental_output': True,
        },
    }

    response = None
    output_parts = []
    last_usage = {}
    last_request_id = None
    started_at = time.time()
    attempts = _max_attempts()

    for attempt in range(1, attempts + 1):
        has_yielded = bool(output_parts)
        try:
            with requests.post(url, headers=headers, json=data, stream=True, timeout=_stream_timeout()) as response:
                _raise_for_dashscope_status(response)
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if not line or line == "[DONE]":
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if payload.get("usage"):
                        last_usage = payload.get("usage") or {}
                    last_request_id = payload.get("request_id") or last_request_id
                    message = (
                        payload.get("output", {})
                        .get("choices", [{}])[0]
                        .get("message", {})
                    )
                    content = message.get("content")
                    if content:
                        output_parts.append(content)
                        has_yielded = True
                        yield content
            record_ai_usage_log(
                provider="dashscope",
                region="cn-beijing",
                api_protocol="dashscope",
                endpoint=url,
                model=resolved_model,
                operation_type=context.get("operation_type") or "text_generation",
                stage=context.get("stage") or "stream_text_generation",
                project_id=context.get("project_id"),
                file_id=context.get("file_id"),
                section_id=context.get("section_id"),
                batch_id=context.get("batch_id"),
                request_id=last_request_id,
                is_stream=True,
                include_usage=bool(last_usage),
                status_code=response.status_code if response is not None else None,
                latency_ms=int((time.time() - started_at) * 1000),
                raw_usage=last_usage,
                input_text=_messages_text(messages),
                output_text="".join(output_parts),
                metadata=_retry_metadata(context, attempt=attempt, success=True),
            )
            return
        except Exception as exc:
            retryable = _is_retryable_error(exc)
            can_retry = retryable and not has_yielded and attempt < attempts
            if can_retry:
                _log_retry(exc, attempt, attempts)
                continue

            record_ai_usage_log(
                provider="dashscope",
                region="cn-beijing",
                api_protocol="dashscope",
                endpoint=url,
                model=resolved_model,
                operation_type=context.get("operation_type") or "text_generation",
                stage=context.get("stage") or "stream_text_generation",
                project_id=context.get("project_id"),
                file_id=context.get("file_id"),
                section_id=context.get("section_id"),
                batch_id=context.get("batch_id"),
                is_stream=True,
                include_usage=bool(last_usage),
                status_code=response.status_code if response is not None else getattr(exc, "status_code", None),
                latency_ms=int((time.time() - started_at) * 1000),
                raw_usage=last_usage,
                input_text=_messages_text(messages),
                output_text="".join(output_parts),
                success=False,
                error_message=str(exc),
                metadata=_retry_metadata(context, attempt=attempt, retryable=retryable),
            )
            raise _public_error(exc)

def generate_bid_section(section_title, section_content, tender_content):
    """按小节生成投标文件内容"""
    enterprise_context = build_enterprise_context()
    prompt = f'''
    你是专业投标书撰写专家，熟悉水利工程、设备配套、质量管理和供应链项目投标要求。
    企业画像：
    {enterprise_context}
    请结合企业能力、质量管理、内网资料库和招标文件要求，直接输出专业、严谨、可落地的正文内容。
    请根据以下小节标题、小节描述并参考招标书相关内容，生成投标书某一小节的完整内容。如果小节需要表格描述，请用Markdown格式生成表格。
    需要填写的表格内容请参考招标书原文中进行填写。
    仅输出小节正文内容，禁止包含任何自然语言解释或额外文。字数要求1000-1500字。
    小节标题: {section_title}
    小节描述: {section_content}
    招标书相关内容: {tender_content}
'''
    response = call_dashscope_api([
                {'role': 'user','content': prompt}
            ], json_mode=False)
    content = response['output']['choices'][0]['message']['content']
    return content

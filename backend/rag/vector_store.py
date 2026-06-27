import os
from openai import OpenAI
import requests
import time
from pathlib import Path
from backend.core.config import get_setting
from backend.db.supabase_repo import record_ai_usage_log

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DASHSCOPE_COMPAT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class EmptyDocumentContentError(Exception):
    """Raised when a document parser extracts no usable text.

    This is common for scanned/image-only PDFs and should be routed to OCR
    instead of treated as a fatal upload error.
    """


# 初始化 Embedding 客户端（OpenAI 兼容协议）
def init_ali_client():
    """初始化 Embedding 客户端。

    默认走阿里云百炼 OpenAI 兼容接口；可通过配置切换到本地 Ollama 或其它
    OpenAI 兼容服务（例如百炼额度用尽时本地跑 qwen3-embedding）。

    - base_url：`embedding_base_url`（环境变量 `EMBEDDING_BASE_URL`）。
      本地 Ollama 用 `http://localhost:11434/v1`；后端跑在容器内时用
      `http://host.docker.internal:11434/v1`。
    - api_key：`embedding_api_key`（环境变量 `EMBEDDING_API_KEY`）。
      百炼必填，回退到 `DASHSCOPE_API_KEY`；Ollama 不校验 key，留空时填占位符。
    """
    base_url = str(get_setting("embedding_base_url", DASHSCOPE_COMPAT_BASE_URL) or DASHSCOPE_COMPAT_BASE_URL).strip()
    api_key = str(get_setting("embedding_api_key", "") or "").strip() or DASHSCOPE_API_KEY
    is_dashscope = "dashscope.aliyuncs.com" in base_url
    # 本地 Ollama 等服务不校验 api_key，但 OpenAI SDK 要求非空，填占位符即可。
    if not api_key:
        api_key = DASHSCOPE_API_KEY if is_dashscope else "ollama"
    return OpenAI(api_key=api_key, base_url=base_url)

# 读取文件内容
def read_file_content(file_path):
    """读取文件内容，支持文本、docx、pdf。"""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".docx":
        import mammoth
        with open(file_path, "rb") as f:
            return mammoth.extract_raw_text(f).value
    if suffix == ".pdf":
        import PyPDF2
        text = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text.append(page.extract_text() or "")
        return "\n".join(text)

    # 编码尝试顺序：优先utf-8系列，再扩展中文字符集，最后兼容所有字节
    encodings = ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'latin-1']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue  # 尝试下一种编码
        except Exception as e:
            raise Exception(f"读取文件失败: {str(e)}")
    
    # 如果所有编码都尝试失败
    raise Exception(f"无法解析文件编码，已尝试编码: {encodings}")


# 文本分片处理（新增函数）
def split_text(text, max_length=8000):
    """
    将长文本分割成符合模型长度要求的分片
    max_length设置为8000，预留一定空间避免超出8192限制
    """
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + max_length
        # 避免在单词中间分割（简单处理）
        if end < text_length:
            # 找到最近的换行或空格
            split_pos = text.rfind('\n', start, end)
            if split_pos == -1:
                split_pos = text.rfind(' ', start, end)
            if split_pos != -1:
                end = split_pos
        
        chunk = text[start:end].strip()
        if chunk:  # 只添加非空分片
            chunks.append(chunk)
        
        start = end
    
    return chunks


def ensure_extractable_text(file_path) -> list[str]:
    """读取文件并分片，确认其中含可抽取文本。

    用于招标文件原生解析兜底路径：MinerU 不可用时，先确认文件不是扫描件。
    内容为空（典型扫描版 PDF）时抛 EmptyDocumentContentError，由调用方路由到 OCR。

    历史上这步借由 file_to_chroma 顺带完成（既检测又写 ChromaDB）。向量库统一到
    pgvector 后，ChromaDB 写入已移除，这里只保留“可抽取文本检测”这一真实职责；
    招标文件的语义入库统一走 bid_interpreter.ingest_mineru_artifacts_to_supabase。
    """
    content = read_file_content(file_path)
    chunks = split_text(content)
    if not chunks:
        raise EmptyDocumentContentError("文件内容为空或无法分割，可能是扫描版 PDF，需要 OCR/MinerU 解析")
    return chunks


def _openai_usage_to_dict(response):
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {
        "total_tokens": getattr(usage, "total_tokens", 0),
        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
    }


def _request_openai_compatible_embeddings(base_url, model, batch_texts, timeout=120):
    response = requests.post(
        f"{base_url.rstrip('/')}/embeddings",
        json={"model": model, "input": batch_texts},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or []
    return [item["embedding"] for item in data], payload


def get_embeddings(client, texts, batch_size=10, usage_context=None):
    """
    批量生成向量，处理分片后的文本
    支持自动分批，确保不超过模型的批量限制
    """
    all_embeddings = []
    context = usage_context or {}
    base_url = str(get_setting("embedding_base_url", DASHSCOPE_COMPAT_BASE_URL) or DASHSCOPE_COMPAT_BASE_URL).strip()
    is_dashscope = "dashscope.aliyuncs.com" in base_url
    provider = "dashscope" if is_dashscope else "local_openai_compatible"
    # 按批次处理
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i+batch_size]
        kwargs = {
            "model": get_setting("embedding_model", "text-embedding-v4"),
            "input": batch_texts,
        }
        dimensions = get_setting("embedding_dimensions", 1024)
        # 仅百炼支持 OpenAI 兼容的 dimensions 参数；本地 Ollama 等服务按模型默认维度输出，
        # 传该参数可能报错，因此只对 DashScope 下发。
        if dimensions and is_dashscope:
            kwargs["dimensions"] = int(dimensions)
        started_at = time.time()
        if is_dashscope:
            response = client.embeddings.create(**kwargs)
            # 提取当前批次的向量并添加到结果列表
            batch_embeddings = [item.embedding for item in response.data]
            model_name = getattr(response, "model", None) or kwargs["model"]
            raw_usage = _openai_usage_to_dict(response)
        else:
            # Ollama 的 OpenAI 兼容 embeddings 在部分版本下会对 OpenAI SDK/httpx
            # 返回 502，直接请求同一真实接口更稳定，且不影响 DashScope 生产链路。
            batch_embeddings, payload = _request_openai_compatible_embeddings(
                base_url,
                kwargs["model"],
                batch_texts,
                timeout=int(get_setting("request_timeout_seconds", 120) or 120),
            )
            model_name = payload.get("model") or kwargs["model"]
            raw_usage = payload.get("usage") or {}
        all_embeddings.extend(batch_embeddings)
        record_ai_usage_log(
            provider=provider,
            region="cn-beijing" if is_dashscope else "local",
            api_protocol="openai_compatible",
            endpoint=f"{base_url.rstrip('/')}/embeddings",
            model=model_name,
            operation_type="embedding",
            stage=context.get("stage") or "embedding",
            project_id=context.get("project_id"),
            file_id=context.get("file_id"),
            section_id=context.get("section_id"),
            batch_id=context.get("batch_id"),
            latency_ms=int((time.time() - started_at) * 1000),
            raw_usage=raw_usage,
            input_text="\n".join(str(item) for item in batch_texts),
            document_count=len(batch_texts),
            character_count=sum(len(str(item)) for item in batch_texts),
            metadata={"dimensions": dimensions, "batch_index": i // batch_size, **(context.get("metadata") or {})},
        )
    
    return all_embeddings

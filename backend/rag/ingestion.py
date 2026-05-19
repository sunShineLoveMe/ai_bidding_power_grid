import hashlib
import json
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, List, Dict

from backend.db.supabase_client import get_supabase_client, reset_supabase_client, upload_file_to_storage, get_bucket_name
from backend.rag.vector_store import init_ali_client, get_embeddings, split_text


def _file_sha256(file_path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def extract_image_contexts_and_text(markdown_path: str) -> tuple[List[str], List[Dict[str, Any]]]:
    """
    解析 Markdown 文件，分离出纯文本段落和带有上下文的图片节点。
    返回:
      texts: 纯文本段落列表
      images: 图片字典列表 [{"image_path": "images/xxx.jpg", "context": "...", "alt": "..."}]
    """
    with open(markdown_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 简单的基于正则的解析
    # 匹配 Markdown 图片格式 ![alt](url)
    image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    
    images = []
    
    # 找到所有的图片及其位置
    for match in image_pattern.finditer(content):
        alt = match.group(1)
        url = match.group(2)
        start_idx = match.start()
        end_idx = match.end()
        
        # 提取上下文 (向前向后各取500字符，并尽量保证句子完整)
        context_start = max(0, start_idx - 500)
        context_end = min(len(content), end_idx + 500)
        context_text = content[context_start:context_end].strip()
        
        images.append({
            "image_path": url,
            "alt": alt,
            "context": context_text
        })
        
    # 对于纯文本，我们直接移除图片标签，然后调用原本的 split_text
    clean_text = image_pattern.sub('', content)
    texts = split_text(clean_text)
    
    return texts, images

def create_knowledge_document(title: str, category: str, bucket: str, object_path: str, source_type: str) -> str:
    client = get_supabase_client()
    payload = {
        "title": title,
        "category": category,
        "bucket": bucket,
        "object_path": object_path,
        "source_type": source_type,
        "status": "processing"
    }
    existing = (
        client.table("knowledge_documents")
        .select("id")
        .eq("bucket", bucket)
        .eq("object_path", object_path)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        document_id = existing[0]["id"]
        client.table("knowledge_documents").update(payload).eq("id", document_id).execute()
        return document_id

    response = client.table("knowledge_documents").insert(payload).execute()
    if not response.data:
        raise RuntimeError("Failed to create knowledge document")
    return response.data[0]["id"]

def update_knowledge_document_status(document_id: str, status: str) -> None:
    client = get_supabase_client()
    client.table("knowledge_documents").update({"status": status}).eq("id", document_id).execute()


def _write_chunks_with_retry(client, rows: list[dict[str, Any]], batch_size: int = 50) -> int:
    inserted_count = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = client.table("document_chunks").insert(batch).execute()
                inserted_count += len(response.data) if response.data else 0
                break
            except Exception as exc:
                last_error = exc
                logging.warning("知识库 chunk 第 %s 批第 %s 次写入失败: %s", i // batch_size + 1, attempt, exc)
                reset_supabase_client()
                client = get_supabase_client()
                if attempt >= 3:
                    raise RuntimeError(f"知识库 chunk 写入失败，已重试 3 次: {last_error}") from last_error
    return inserted_count

def ingest_knowledge_document(
    document_id: str,
    original_filename: str,
    markdown_path: str,
    extract_dir: str
) -> dict[str, Any]:
    """
    将 MinerU 解析后的文档入库（轻量级打标图文检索方案）。
    """
    client = get_supabase_client()
    ali_client = init_ali_client()
    bucket = get_bucket_name("knowledge")
    
    # 1. 抽取纯文本和带有上下文的图片
    text_chunks, image_nodes = extract_image_contexts_and_text(markdown_path)
    
    documents_to_insert = []
    
    # 2. 处理图片：上传到 Supabase Storage，生成带有 Image URL 的 metadata
    for img_node in image_nodes:
        local_img_path = Path(extract_dir) / img_node["image_path"]
        if not local_img_path.exists():
            continue
            
        # 上传到 Supabase Storage
        safe_suffix = local_img_path.suffix.lower()
        object_path = f"{document_id}/{local_img_path.name}"
        content_type = mimetypes.guess_type(local_img_path.name)[0] or "application/octet-stream"
        
        upload_file_to_storage(bucket, object_path, local_img_path, content_type)
        public_url = client.storage.from_(bucket).get_public_url(object_path)
        
        # 组装图片上下文，这将被送去 Embedding
        semantic_tag = f"【图片元数据】\n文件名: {original_filename}\n图片描述: {img_node['alt']}\n所在段落上下文:\n{img_node['context']}"
        
        documents_to_insert.append({
            "content": semantic_tag,
            "metadata": {
                "type": "image",
                "image_url": public_url,
                "alt": img_node["alt"]
            }
        })

    # 3. 处理纯文本
    for text in text_chunks:
        documents_to_insert.append({
            "content": text,
            "metadata": {
                "type": "text"
            }
        })
        
    if not documents_to_insert:
        update_knowledge_document_status(document_id, "failed")
        return {"status": "error", "message": "无有效内容提取"}

    # 4. 批量生成 Embedding 并写入数据库
    # 分离 content 用于 embedding
    contents_for_embedding = [doc["content"] for doc in documents_to_insert]
    embeddings = get_embeddings(ali_client, contents_for_embedding)
    
    # 准备写入 Supabase document_chunks 表的数据
    rows_to_insert = []
    for i, doc in enumerate(documents_to_insert):
        rows_to_insert.append({
            "document_id": document_id,
            "chunk_index": i,
            "content": doc["content"],
            "embedding": embeddings[i],
            "metadata": doc["metadata"]
        })
        
    # 重入同一文档时先清理旧分片，避免刷新/重试导致检索结果重复。
    client.table("document_chunks").delete().eq("document_id", document_id).execute()
    inserted_count = _write_chunks_with_retry(client, rows_to_insert)
            
    update_knowledge_document_status(document_id, "indexed")
            
    return {
        "status": "success",
        "inserted_chunks": inserted_count,
        "images_processed": len(image_nodes)
    }

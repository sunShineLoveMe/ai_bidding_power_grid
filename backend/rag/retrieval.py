import os
import json
import re
from typing import Any, Iterator, List, Dict
from openai import OpenAI

from backend.db.supabase_client import get_supabase_client
from backend.rag.vector_store import init_ali_client, get_embeddings
from backend.ai.qwen_client import stream_dashscope_api
from backend.core.config import get_stage_model
from backend.ai.rerank_client import rerank_documents
from backend.core.bid_volumes import asset_applicable_volumes, asset_matches_volume, normalize_volume_type

def search_knowledge_base(query: str, match_threshold: float = 0.5, match_count: int = 5) -> List[Dict[str, Any]]:
    """
    通过 Supabase RPC 检索图文混排的知识库内容
    """
    ali_client = init_ali_client()
    client = get_supabase_client()
    
    # 1. 向量化查询
    query_embeddings = get_embeddings(ali_client, [query])
    if not query_embeddings:
        return []
    query_vector = query_embeddings[0]
    
    # 2. 调用 Supabase RPC
    response = client.rpc(
        "match_knowledge_chunks",
        {
            "query_embedding": query_vector,
            "match_threshold": match_threshold,
            "match_count": max(match_count * 3, match_count)
        }
    ).execute()
    
    rows = response.data or []
    return rerank_documents(query, rows, text_key="content", top_n=match_count)


def search_knowledge_assets(query: str, match_count: int = 8, volume_type: str | None = None) -> List[Dict[str, Any]]:
    """
    检索企业知识库中的图片/资质资产。
    图片本身不直接参与语义检索，检索的是 OCR、AI 描述、规格参数和适用章节组成的 searchable_text。
    """
    ali_client = init_ali_client()
    client = get_supabase_client()

    query_embeddings = get_embeddings(ali_client, [query])
    if not query_embeddings:
        return []

    target_volume = normalize_volume_type(volume_type) if volume_type else None
    rpc_payload = {
        "query_embedding": query_embeddings[0],
        "match_count": max(match_count * 3, match_count),
        "filter_category": None,
        "filter_asset_type": None,
    }
    if target_volume:
        rpc_payload["filter_applicable_volume"] = target_volume

    response = client.rpc(
        "match_knowledge_assets",
        rpc_payload,
    ).execute()

    rpc_rows = response.data or []
    if target_volume:
        rpc_rows = [asset for asset in rpc_rows if asset_matches_volume(asset, target_volume, allow_unscoped=True)]
    assets = rerank_documents(query, rpc_rows, text_key="searchable_text", top_n=match_count)
    # 过滤掉明显弱相关的资产，保留图片来源展示的准确性。
    strong_assets = [asset for asset in assets if float(asset.get("similarity") or 0) >= 0.28]
    if len(strong_assets) >= min(match_count, 3):
        return strong_assets[:match_count]

    fallback_assets = _keyword_search_knowledge_assets(query, match_count=match_count, volume_type=target_volume)
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for asset in [*strong_assets, *fallback_assets]:
        asset_id = str(asset.get("id") or asset.get("storage_path") or asset.get("title") or "")
        if asset_id and asset_id in seen:
            continue
        if asset_id:
            seen.add(asset_id)
        merged.append(asset)
        if len(merged) >= match_count:
            break
    return merged


def _keyword_search_knowledge_assets(query: str, match_count: int = 8, volume_type: str | None = None) -> list[dict[str, Any]]:
    """
    企业资信库/产品库里经常是短标题、短说明和图片附件，纯向量召回可能偏弱。
    这里补一层轻量关键词召回，确保“营业执照图片、社保缴纳证明、类似业绩证明”等私有资产问题不会被误拒。
    """
    client = get_supabase_client()
    response = (
        client.table("knowledge_assets")
        .select("*")
        .eq("status", "indexed")
        .limit(200)
        .execute()
    )
    rows = response.data or []
    query_tokens = _asset_query_tokens(query)
    if not query_tokens:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for asset in rows:
        if volume_type and not asset_matches_volume(asset, volume_type, allow_unscoped=True):
            continue
        text = _asset_search_text(asset)
        score = sum(1 for token in query_tokens if token and token in text)
        if volume_type and asset_matches_volume(asset, volume_type, allow_unscoped=False):
            score += 4
        if "图片" in query or "照片" in query or "附件" in query or "材料" in query:
            mime_type = str(asset.get("mime_type") or "")
            if mime_type.startswith("image/"):
                score += 2
        if any(token in query for token in ["资质", "资信", "证书", "执照", "许可", "社保", "人员"]):
            if str(asset.get("asset_type") or "") == "qualification_image":
                score += 3
        if any(token in query for token in ["产品", "设备", "材料", "闸门", "水泵", "水轮机", "叶片"]):
            if str(asset.get("asset_type") or "") == "product_image":
                score += 3
        if score > 0:
            enriched = {**asset, "similarity": max(float(asset.get("similarity") or 0), min(score / 10, 0.99))}
            scored.append((score, enriched))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [asset for _, asset in scored[:match_count]]


def _asset_search_text(asset: dict[str, Any]) -> str:
    parts = [
        asset.get("title"),
        asset.get("description"),
        asset.get("category"),
        asset.get("asset_type"),
        asset.get("searchable_text"),
        asset.get("ai_caption"),
        asset.get("file_name"),
        asset.get("attribution"),
    ]
    parts.extend(asset.get("tags") or [])
    parts.extend(asset.get("applicable_sections") or [])
    parts.extend(asset_applicable_volumes(asset))
    specs = asset.get("specs") or {}
    if isinstance(specs, dict):
        parts.extend(str(value) for value in specs.values() if value)
    return " ".join(str(part) for part in parts if part).lower()


def _asset_query_tokens(query: str) -> list[str]:
    synonym_tokens = {
        "业绩": ["业绩", "类似业绩", "合同", "中标", "验收", "证明材料"],
        "社保": ["社保", "缴纳", "参保", "人员", "证明"],
        "营业执照": ["营业执照", "执照", "基础证照", "企业证照"],
        "安全生产许可证": ["安全生产", "许可证", "安全生产许可", "资质证书"],
        "资质": ["资质", "证书", "资格", "资信", "许可"],
        "人员": ["人员", "项目经理", "技术负责人", "职称", "执业", "社保"],
        "产品": ["产品", "设备", "参数", "图册", "样张"],
        "图片": ["图片", "照片", "图", "附件", "材料", "样张"],
    }
    tokens = set(re.findall(r"[\u4e00-\u9fa5A-Za-z0-9_]+", query.lower()))
    for key, values in synonym_tokens.items():
        if key in query:
            tokens.update(value.lower() for value in values)
    return [token for token in tokens if token]

def generate_knowledge_answer(
    query: str,
    contexts: List[Dict[str, Any]],
    assets: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """
    组装包含图片链接的 Prompt，让大模型基于知识库生成最终回答
    """
    prompt, images = build_knowledge_prompt(query, contexts, assets)

    from backend.ai.qwen_client import call_dashscope_api

    response = call_dashscope_api(
        [
            {"role": "system", "content": "你是一个严谨的 RAG 知识库问答助手。"},
            {"role": "user", "content": prompt}
        ],
        model=get_stage_model("knowledge"),
        json_mode=False,
        usage_context={
            "stage": "knowledge_answer",
            "operation_type": "text_generation",
            "metadata": {
                "contexts_count": len(contexts),
                "assets_count": len(assets or []),
            },
        },
    )
    answer = response.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content") or ""
    
    return {
        "answer": answer,
        "images": images,
        "assets": assets or [],
        "raw_contexts": contexts
    }


def build_knowledge_prompt(
    query: str,
    contexts: List[Dict[str, Any]],
    assets: List[Dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    text_contexts = []
    images = []

    for index, ctx in enumerate(contexts, 1):
        content = ctx.get("content", "")
        meta = ctx.get("metadata", {}) or {}
        similarity = ctx.get("similarity", 0)
        source = meta.get("source_org") or meta.get("source_file") or "企业知识库"
        doc_type = meta.get("doc_type") or "知识片段"

        text_contexts.append(
            f"【资料{index}｜相关度 {similarity:.2f}｜来源 {source}｜类型 {doc_type}】\n{content}"
        )

        if meta.get("type") == "image" and meta.get("image_url"):
            images.append({
                "url": meta.get("image_url"),
                "alt": meta.get("alt", "未命名图片")
            })

    asset_contexts = []
    for index, asset in enumerate(assets or [], 1):
        title = asset.get("title") or "未命名图片"
        category = asset.get("category") or "图片资产"
        asset_type = asset.get("asset_type") or "image"
        similarity = float(asset.get("similarity") or 0)
        searchable_text = asset.get("searchable_text") or asset.get("description") or ""
        sections = "、".join(asset.get("applicable_sections") or [])
        public_url = f"/api/knowledge/assets/{asset.get('id')}/file" if asset.get("id") else (asset.get("public_url") or "")
        asset_contexts.append(
            f"【图片资产{index}｜相关度 {similarity:.2f}｜分类 {category}｜类型 {asset_type}】\n"
            f"名称：{title}\n适用章节：{sections}\n图片地址：{public_url}\n说明：{searchable_text}"
        )
        if public_url:
            images.append({
                "url": public_url,
                "alt": title,
            })

    context_str = "\n\n---\n\n".join(text_contexts)
    asset_context_str = "\n\n---\n\n".join(asset_contexts) or "无相关图片资产。"
    prompt = f"""你是一个专业的企业私有知识库与水利招投标 RAG 问答助手。
你可以同时依据“企业知识库检索片段”和“相关图片/资质资产”回答用户问题。用户询问企业资信库、产品库、业绩材料、人员证书、社保缴纳证明、营业执照、产品图片等私有资产时，应优先基于相关图片/资质资产回答。
不要编造未出现在资料中的证书编号、人员姓名、合同金额或具体日期。

【知识库检索片段】：
{context_str}

【相关图片/资质资产】：
{asset_context_str}

【用户问题】：
{query}

回答要求：
1. 先给出结论，再按要点展开。
2. 如果只有图片/资质资产命中、没有文本片段，也要基于资产标题、说明、标签和适用章节回答，并明确这些是“可参考/可插入的企业资料”。
3. 如果资料不足，请明确说明哪些信息需要继续补充。
4. 涉及投标材料、废标风险、施工组织设计等内容时，尽量给出可执行清单。
5. 如果相关图片/资质资产适合插入标书正文，请直接在对应说明段落后使用 Markdown 图片语法插入，不要在结尾集中罗列图片。格式必须是：![图片名称](图片地址)
6. 最多插入 3 张最相关图片。资质证书、营业执照、安全生产许可证、社保缴纳证明类图片如为脱敏样张，必须说明“仅作为脱敏示意图/排版占位图，不能替代正式法定文件”。
7. 不要输出 Markdown 表格，图片建议用自然段和项目符号描述，避免表格在聊天窗口中换行错乱。
8. 结尾列出“参考依据”，用“资料1、资料2...”和“图片资产1、图片资产2...”说明依据来自哪些检索片段或资产；图片资产只作为配图/材料建议，不要把它当成法规依据。
9. 语言专业、客观、准确，适合非技术标书人员阅读。
"""
    return prompt, images


def stream_knowledge_answer(
    query: str,
    contexts: List[Dict[str, Any]],
    assets: List[Dict[str, Any]] | None = None,
) -> Iterator[Dict[str, Any]]:
    prompt, images = build_knowledge_prompt(query, contexts, assets)
    yield {
        "type": "retrieved",
        "contexts_count": len(contexts),
        "assets_count": len(assets or []),
        "images": images,
        "raw_contexts": contexts,
        "assets": assets or [],
    }

    emitted = False
    try:
        for chunk in stream_dashscope_api(
            [
                {"role": "system", "content": "你是一个严谨的 RAG 知识库问答助手。"},
                {"role": "user", "content": prompt},
            ],
            model=get_stage_model("knowledge"),
            usage_context={
                "stage": "knowledge_answer_stream",
                "operation_type": "text_generation",
                "metadata": {
                    "contexts_count": len(contexts),
                    "assets_count": len(assets or []),
                },
            },
        ):
            emitted = True
            yield {
                "type": "chunk",
                "content": chunk,
            }
    except Exception:
        result = generate_knowledge_answer(query, contexts, assets)
        content = result.get("answer") or ""
        for start in range(0, len(content), 120):
            emitted = True
            yield {
                "type": "chunk",
                "content": content[start:start + 120],
            }

    if not emitted:
        yield {
            "type": "chunk",
            "content": "未能生成回答，请稍后重试或补充更多知识库资料。",
        }

    yield {
        "type": "done",
    }

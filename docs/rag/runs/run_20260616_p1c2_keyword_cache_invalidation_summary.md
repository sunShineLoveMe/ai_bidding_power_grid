# Run 32 - P1C-2 关键词兜底缓存失效机制（2026-06-16）

## 触发原因

客户后续会持续补充资料，且“企业知识库”页面支持用户上传资料。原实现中 `_keyword_search_knowledge_chunks` 使用进程级 `_CHUNK_KEYWORD_CACHE` 缓存 `document_chunks` 全量扫描结果；如果 Web 进程先生成缓存，随后 Celery 或入库脚本新增/重入库 `document_chunks`，旧 Web worker 可能继续读取旧快照。

## 实现内容

改动文件：

- `backend/rag/retrieval.py`
- `backend/rag/ingestion.py`
- `tests/test_rag_retrieval.py`

核心机制：

1. 在检索端增加 `document_chunks` 水位指纹：`count + 最新 created_at + 最新 id`。
2. 每次进入关键词兜底前，先读取轻量指纹；如果指纹变化，则自动重建 `_CHUNK_KEYWORD_CACHE`。
3. 保留 `invalidate_chunk_keyword_cache(reason)` 显式清理入口，便于入库流程和测试调用。
4. 在 `ingest_knowledge_document` 删除旧分片、写入新分片后调用显式清理，保证当前进程也立即失效。
5. 资产检索不改动：企业资信库/企业产品库上传走 `knowledge_assets`，不使用 `_CHUNK_KEYWORD_CACHE`。

## 单元测试

命令：

```bash
.venv/bin/python -m py_compile backend/rag/retrieval.py backend/rag/ingestion.py tests/test_rag_retrieval.py
.venv/bin/python -m pytest tests/test_rag_retrieval.py -q
```

结果：

- `py_compile` 通过。
- `tests/test_rag_retrieval.py`：16 passed，1 个 PyPDF2 deprecation warning。

新增覆盖：

- 显式调用 `invalidate_chunk_keyword_cache` 后，缓存行和指纹均被清空。
- 同一检索进程内 `document_chunks` 指纹变化后，关键词缓存自动重建，并返回新增 row。

## 真实 stream 验收

执行方式：

1. 对真实 `/api/knowledge/search/stream` 连续请求 4 次，预热旧关键词兜底缓存。
2. 向真实 PostgreSQL 插入一条测试 `knowledge_documents` 和一条测试 `document_chunks`。
3. 测试 chunk 使用完整泰昌企业事实 metadata：`enterprise=泰昌`、`source_domain=enterprise_fact`、`fact_source_allowed_for_enterprise=true`、`reference_only=false`。
4. 不重启 Web，再次请求真实 `/api/knowledge/search/stream`。
5. 验收后删除测试 chunk 和测试 document。

记录：

- before stream：`docs/rag/runs/run_20260616_p1c2_keyword_cache_invalidation_before_stream.jsonl`
- after stream：`docs/rag/runs/run_20260616_p1c2_keyword_cache_invalidation_after_stream.jsonl`
- JSON 摘要：`docs/rag/runs/run_20260616_p1c2_keyword_cache_invalidation_summary.json`

结果：

| 指标 | 结果 |
| --- | --- |
| before_contains_secret | false |
| after_contains_secret | true |
| after_done | true |
| 测试数据清理 | 已清理 |

说明：第一次真实样本失败是因为测试口令采用英文下划线，不适合当前中文关键词切分；第二次失败是因为测试 chunk 未带 `reference_only=false`，被泰昌试点 metadata 过滤正确排除。最终样本使用中文口令和完整泰昌企业事实 metadata 后通过。

## 增量回归门禁

命令：

```bash
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_incremental_regression_gate.py \
  --run-id run_20260616_p1c2_keyword_cache_invalidation_gate
```

结果记录：`docs/rag/runs/run_20260616_p1c2_keyword_cache_invalidation_gate_summary.md`

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨域串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 268 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 619 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 357 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 686 ms |

Gate：PASS。

## 结论

P1C-2 完成。新增客户知识文档或重入库 `document_chunks` 后，关键词兜底缓存不再依赖重启 Web 才能读取最新数据。下一任务顺延为 P1C-3：RAG 本地门禁自动化入口。

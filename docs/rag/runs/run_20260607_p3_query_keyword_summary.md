# P3 Query Rewrite / 关键词补召回 / Authority 排序回归记录

> 日期：2026-06-07  
> 范围：P3-1 Query Rewrite、P3-2 关键词补召回、P3-3 authority 排序  
> 本次未新增客户资料，未执行正式入库。

## 改动内容

- `backend/rag/retrieval.py` 增加轻量 Query Rewrite：
  - 提取标准号、包号、技术规范编码、物料编码、国网规则、供应商管理、不良行为、施工工艺等高精度关键词。
  - 将补充关键词拼入 embedding 查询文本，提升短词、编号和业务术语召回。
- 增加 `document_chunks` 关键词补召回：
  - 当向量召回不足，或高精度关键词未命中时触发。
  - 使用 `metadata_filter` 在应用层过滤，保持泰昌/辽宁/河北豪乾边界。
  - 对网页型国网规则分片补充“来源文件名、标签、类型、来源单位”前缀，避免只有网页导航噪声。
  - 同进程内缓存分片列表，降低批量评测重复拉取成本。
- 增加 authority/citation 排序：
  - `law_or_standard_citable`、`tender_requirement_citable`、`enterprise_fact_citable` 加权。
  - `reference_style_only` 降权，防止参考稿压过正式依据。
- `scripts/rag/eval_recall.py` 改为调用生产检索函数 `search_knowledge_base()`，确保 Base/专项回归覆盖 Query Rewrite、关键词补召回和排序逻辑。

## 单测

```bash
./.venv/bin/python -m pytest tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q
./.venv/bin/python -m py_compile backend/rag/retrieval.py scripts/rag/eval_recall.py
```

结果：25 passed，1 个 PyPDF2 deprecation warning；py_compile 通过。

## 召回回归

```bash
./.venv/bin/python scripts/rag/eval_recall.py --k 5 --save docs/rag/runs/run_20260607_p3_query_keyword_base_filtered.json
./.venv/bin/python scripts/rag/eval_recall.py --k 5 --testset tests/rag/customer_liaoning_taichang_testset.jsonl --save docs/rag/runs/run_20260607_p3_query_keyword_customer_filtered.json
```

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

与 P2 基线相比：

- Base Recall@5：86.7% -> 96.7%
- Base top1 来源准确率：93.3% -> 100.0%
- Base writing 场景 Recall@5：91% -> 100%
- 泰昌 MVP 专项保持 100%，禁用关键词命中率保持 0%。

## 未命中与后续

- Base 仅剩 T04 合规用例未命中关键词。top1 已命中 `policy_regulation`，但内容是“否决所有投标”，未覆盖测试关键词。
- 国网规则网页分片存在明显网页导航噪声。当前通过来源 metadata 前缀改善可召回性，但后续应重洗 `02_policy_regulations/25_国家电网有限公司招标活动管理办法_*` 和 `26_国家电网有限公司供应商管理办法_*`，提取正文条款后重新入库。
- 关键词补召回当前在应用层过滤，原因是本地 Supabase/Postgres 兼容层暂不支持 JSON metadata 过滤下推；后续可补数据库侧关键词索引或专用 RPC。


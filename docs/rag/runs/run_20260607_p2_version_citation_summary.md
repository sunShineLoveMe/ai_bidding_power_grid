# P2 版本去重与引用边界回归记录

> 日期：2026-06-07  
> 范围：P2-4 版本与去重策略、P2-5 模板可引用边界  
> 本次未新增客户资料，未执行正式入库。

## 改动内容

- 新增 `scripts/rag/customer_metadata_policy.py`，集中定义客户资料 metadata 门禁。
- `scripts/rag/ingest_customer_corpus.py` 在 dry-run 与正式入库前执行同一套 metadata 校验。
- 入库记录统一补齐/校验：
  - `source_domain`
  - `citation_policy`
  - `authority_level`
  - `source_sha256`
  - `doc_identity_key`
  - `doc_version`
  - `superseded_by`
- 正式入库时，同一 `doc_identity_key`、不同 `source_sha256` 且新版本不低于旧版本的既有文档会被置为 `superseded`，metadata 写入 `superseded_by=<新document_id>`。
- `enterprise_fact`、`tender_requirement`、`reference_template` 分别执行强边界校验，防止企业事实、招标要求和参考稿混用。

## dry-run

| manifest | documents | skipped | blocked_metadata | parent | child/table 检索块 | embedding |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/staging_manifest.json` | 124 | 0 | 0 | 2023 | 27660 | 27660 |
| `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/manifest.json` | 44 | 21 | 0 | 223 | 4015 | 4015 |

## 单测

```bash
./.venv/bin/python -m pytest tests/test_customer_metadata_policy.py tests/test_rag_retrieval.py -q
```

结果：14 passed，1 个 PyPDF2 deprecation warning。

## 召回回归

```bash
./.venv/bin/python scripts/rag/eval_recall.py --k 5 --save docs/rag/runs/run_20260607_p2_version_citation_base_filtered.json
./.venv/bin/python scripts/rag/eval_recall.py --k 5 --testset tests/rag/customer_liaoning_taichang_testset.jsonl --save docs/rag/runs/run_20260607_p2_version_citation_customer_filtered.json
```

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 86.7% | 93.3% | 86.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

## 剩余风险

- 旧版已入库文档如果历史 metadata 没有 `doc_identity_key`，本次新增规则无法反向识别其逻辑版本关系；后续新批次入库后会开始稳定生效。
- 如果客户后续提供“同一资料但文件名变化”的新版，manifest 应显式填写稳定 `doc_key` 或 `document_key`，否则默认会按来源路径生成身份键。


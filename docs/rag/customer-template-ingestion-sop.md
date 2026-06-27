# 客户资料入库 SOP

> 适用范围：客户新增招标文件包、企业资料、历史投标文件、参考稿、技术规范、货物清单、图片资产和解析产物入库。  
> 当前 MVP 口径：泰昌是试点企业和投标申请主体；辽宁资料只作为招标场景样本；河北豪乾资料只作为参考稿。

## 1. 不可混用边界

| 资料域 | 用途 | 必填 metadata | 禁止事项 |
| --- | --- | --- | --- |
| 泰昌企业事实 | 企业资质、生产、检测、财务、绿色低碳、图片资产、标书申请主体事实 | `mvp_enterprise=taichang`、`enterprise=泰昌`、`doc_owner=泰昌`、`source_domain=enterprise_fact`、`fact_source_allowed_for_enterprise=true`、`reference_only=false`、`tenant_visibility=taichang_only` | 不得被其他企业复用为企业事实 |
| 辽宁招标资料 | 招标要求、技术规范、货物清单、合同条款、评分与否决项 | `source_domain=tender_requirement`、`doc_owner=国网辽宁省电力有限公司`、`province=辽宁`、`fact_source_allowed_for_enterprise=false` | 不得写成泰昌企业能力或泰昌历史事实 |
| 河北豪乾参考稿 | 目录、格式、章节组织、表达风格参考 | `source_domain=reference_template`、`doc_owner=河北豪乾电气设备科技有限公司`、`reference_only=true`、`fact_source_allowed_for_enterprise=false`、`do_not_mix_with=["泰昌企业事实"]` | 不得作为泰昌资质、业绩、设备、人员、财务事实来源 |

AI 标书写作默认投标申请主体为泰昌。只有用户显式指定其他企业并切换资料域时，才允许改变主体。

## 2. 资料落位

1. 原始客户包保留在 `rag_seed/power_grid_resources/01_tender_documents/<批次目录>/` 或企业资料专用目录。
2. 企业私有资料建议落位到 `rag_seed/power_grid_resources/05_enterprise_documents/<企业>/<批次>/`。
3. 解析产物统一写入 `parsed_outputs/power_grid_customer_corpus/<ingestion_batch_id>/`。
4. 不修改原始文件名；如文件名乱码，新增规范化映射字段，不覆盖原文件。
5. `.zip/.rar/.sign/.zb` 先进入 manifest，默认不直接入 RAG。

## 3. 收件与 inventory

每批资料先做 inventory，再解析。至少记录：

- `ingestion_batch_id`
- `source_file`
- `sha256`
- `file_type`
- `source_domain`
- `doc_owner`
- `enterprise`
- `province`
- `batch_no`
- `package_no`
- `package_code`
- `material_category`
- `doc_role`
- `evidence_type`
- `reference_only`
- `fact_source_allowed_for_enterprise`
- `privacy_level`
- `tenant_visibility`
- `access_scope`
- `parse_status`
- `quality_status`

普通泰昌内部问答和标书写作不强制脱敏；但入库 metadata 必须保留 `tenant_visibility=taichang_only` 和 `access_scope=taichang_tenant_internal`，避免未来跨企业或跨租户串用。

## 4. 安全与授权检查

1. 客户原始包先进入隔离目录完成 inventory，不直接覆盖既有 seed 目录。
2. 记录压缩包、解压文件和解析文件的 `sha256`，便于后续去重、回滚和审计。
3. 可执行文件、脚本、未知二进制只进入归档清单，不进入 RAG。
4. 普通泰昌内部资料按客户口径可不脱敏；若未来进入跨企业演示、公开样例或第三方评测，必须另建脱敏批次。
5. 授权不作为普通泰昌内部问答阻断项，但必须在 manifest 中标注 `access_scope=taichang_tenant_internal`。

## 5. 解析策略

| 文件类型 | 默认策略 | 切换 MinerU/OCR 条件 |
| --- | --- | --- |
| `.docx` | 结构化解析标题、段落、表格 | 标题/表格明显缺失、正文为空、图片证据需要提取 |
| `.doc` | LibreOffice 转 `.docx` 后解析 | 转换失败、乱码、版式严重丢失 |
| `.pdf` | 原生文本快速检测后决定 | 扫描件、空文本、表格/图片证据重要、页码或章节错乱 |
| `.xlsx` | openpyxl 结构化解析 | 不适用普通 OCR；如是图片表格再走 OCR |
| 图片 | 作为资产入库并做 OCR/视觉说明 | 任何涉及营业执照、证书、设备、生产线、检测报告的图片都要生成资产 metadata |

解析失败不得静默跳过，必须标记 `parse_status=needs_review` 并写入质量报告。

## 6. 分块与结构化

1. 文本资料默认父子双层分块：child 召回，parent 写作回溯。
2. 货物清单、技术参数表、偏差表必须保留三形态：原始结构、检索摘要、行级记录。
3. 标书写作引用必须能回溯到 parent、页码或资产。
4. 泰昌企业图片资产要可被问答和标书图文并茂功能按 `evidence_type` 检索。

## 6.1 版本、去重与引用边界

客户资料入库必须执行 `scripts/rag/customer_metadata_policy.py` 中的 metadata 门禁。`scripts/rag/ingest_customer_corpus.py --dry-run` 和正式入库都会执行同一套规则。

### 版本与去重

- 每条可入库记录必须有 `doc_version` 和原始文件 `sha256`；入库时统一写入 `source_sha256`。
- 每条记录必须生成或显式提供 `doc_identity_key`。同一逻辑资料的新旧版本必须使用同一个 `doc_identity_key`。
- 若新资料与已有资料 `doc_identity_key` 相同、`source_sha256` 不同，且新 `doc_version` 不低于旧版本，正式入库后旧 `knowledge_documents.status` 与 metadata `status` 必须置为 `superseded`，并写入 `superseded_by=<新document_id>`。
- 同一内容重复入库（`source_sha256` 相同）不得触发 supersede。
- `blocked_metadata>0` 时不得正式入库；先修 manifest 或 metadata。

### citation_policy

| source_domain | citation_policy | 允许用途 | 禁止用途 |
| --- | --- | --- | --- |
| `enterprise_fact` | `enterprise_fact_citable` | 泰昌企业事实、资信、产品、生产/检测/财务等证明材料 | 不得跨企业复用 |
| `tender_requirement` | `tender_requirement_citable` | 招标要求、技术规范、货物清单、合同条款、评分/否决项 | 不得写成泰昌企业能力或历史事实 |
| `reference_template` | `reference_style_only` | 封面、目录、章节组织、表格结构、表达风格参考 | 不得作为泰昌事实、业绩、资质、设备、人员或财务来源 |
| `policy_regulation` | `law_or_standard_citable` | 法规、国网制度、标准规范依据 | 不得替代客户招标文件的项目级要求 |
| `base_seed` | `summary_only` | 通用背景、辅助检索、非正式说明 | 不得作为正式项目条款引用 |

边界强校验：

- `enterprise_fact` 必须 `enterprise`、`doc_owner` 非空，`reference_only=false`，`fact_source_allowed_for_enterprise=true`。
- `tender_requirement` 必须 `fact_source_allowed_for_enterprise=false`。
- `reference_template` 必须 `reference_only=true`，`fact_source_allowed_for_enterprise=false`，`citation_policy=reference_style_only`。

## 7. 图片资产 metadata

每个图片资产至少记录：

```json
{
  "asset_id": "uuid-or-stable-id",
  "enterprise": "泰昌",
  "doc_owner": "泰昌",
  "source_domain": "enterprise_fact",
  "evidence_type": "testing_capacity",
  "target_library": "enterprise_asset_library",
  "source_file": "原始 PDF 或图片路径",
  "page_no": 1,
  "bbox": null,
  "image_path": "解析输出图片路径",
  "ocr_text": "图片周边或图内可识别文字",
  "caption": "业务可读说明",
  "tenant_visibility": "taichang_only",
  "access_scope": "taichang_tenant_internal",
  "reference_only": false,
  "fact_source_allowed_for_enterprise": true,
  "display_contexts": ["knowledge_qa", "bid_writing_with_images"]
}
```

`evidence_type` 建议值包括 `business_license`、`certification`、`production_capacity`、`testing_capacity`、`green_low_carbon`、`inspection_report`、`financial_evidence`。

## 8. 入库前门禁

入库前必须满足：

1. manifest 覆盖所有原始文件和解析文件。
2. 解析质量报告没有未解释的 `fail`。
3. 泰昌、辽宁、河北豪乾三类资料 metadata 隔离正确。
4. 表格资料已结构化，不只作为普通文本。
5. 图片资产有 `evidence_type`、`source_file`、`page_no` 或可追溯路径。
6. dry-run 输出文档数、chunk 数、表格行数、资产数。
7. 可按 `ingestion_batch_id` 回滚。

## 9. 入库后回归

每次正式入库或召回策略调整后必须执行：

```bash
PYTHONPATH=. .venv/bin/python scripts/rag/eval_recall.py --k 5 --save docs/rag/runs/<run>_base_filtered.json
PYTHONPATH=. .venv/bin/python scripts/rag/eval_recall.py --k 5 --testset tests/rag/customer_liaoning_taichang_testset.jsonl --save docs/rag/runs/<run>_customer_filtered.json
```

若本批涉及图片资产，还要补充问答或写作链路验证，检查返回资产是否满足：

- `enterprise=泰昌`
- `source_domain=enterprise_fact`
- `reference_only=false`
- `evidence_type` 与问题或章节意图匹配
- 不命中河北豪乾主体事实

## 10. 完成定义

一批资料只有同时满足以下条件才算完成：

1. 原始包、解压文件、解析产物、manifest、质量报告均可追溯。
2. 入库 summary 写明文档、chunk、表格行、资产数量。
3. Base 回归不低于既有基线。
4. 专项评测无跨资料域串用。
5. `docs/rag/evaluation-records.md` 和 `docs/rag/todo.md` 已同步。
6. 未解决的客户确认项单独列出，不混入已完成结论。

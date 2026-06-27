# 客户资料批次 Manifest 模板

> 文件名建议：`parsed_outputs/power_grid_customer_corpus/<ingestion_batch_id>/manifest.json`。  
> 当前 MVP 默认：`mvp_enterprise=taichang`，投标申请主体为泰昌。

## JSON 模板

```json
{
  "schema_version": "2026-06-06",
  "ingestion_batch_id": "customer_liaoning_taichang_20260606_p0",
  "batch_name": "辽宁招标样本与泰昌 MVP 企业资料",
  "mvp_enterprise": "taichang",
  "applicant_enterprise": "泰昌",
  "created_at": "2026-06-06T00:00:00+08:00",
  "created_by": "manual_or_script_name",
  "source_roots": [
    "rag_seed/power_grid_resources/01_tender_documents/22_国网辽宁电力2025年第三次物资协议库存招标采购",
    "rag_seed/power_grid_resources/05_enterprise_documents/01_泰昌MVP试点企业资料"
  ],
  "batch_scope": {
    "province": "辽宁",
    "batch_no": "2025-03",
    "package_code": "2225AC",
    "material_category": "电缆保护管CPVC/MPP",
    "tenant_visibility": "taichang_only",
    "access_scope": "taichang_tenant_internal"
  },
  "source_domain_rules": [
    {
      "source_domain": "enterprise_fact",
      "doc_owner": "泰昌",
      "enterprise": "泰昌",
      "reference_only": false,
      "fact_source_allowed_for_enterprise": true
    },
    {
      "source_domain": "tender_requirement",
      "doc_owner": "国网辽宁省电力有限公司",
      "reference_only": false,
      "fact_source_allowed_for_enterprise": false
    },
    {
      "source_domain": "reference_template",
      "doc_owner": "河北豪乾电气设备科技有限公司",
      "reference_only": true,
      "fact_source_allowed_for_enterprise": false,
      "do_not_mix_with": ["泰昌企业事实"]
    }
  ],
  "files": [
    {
      "file_id": "stable-file-id",
      "source_file": "relative/original/file/path.pdf",
      "normalized_title": "营业执照",
      "sha256": "hex-sha256",
      "file_type": "pdf",
      "file_size_bytes": 123456,
      "source_domain": "enterprise_fact",
      "doc_owner": "泰昌",
      "enterprise": "泰昌",
      "province": null,
      "batch_no": null,
      "package_no": null,
      "package_code": null,
      "material_category": "电缆保护管CPVC/MPP",
      "doc_role": "enterprise_evidence",
      "evidence_type": "business_license",
      "target_library": "enterprise_asset_library",
      "qualification_mode": "enterprise_private",
      "parser_plan": "mineru_ocr",
      "parse_status": "parsed",
      "quality_status": "pass",
      "quality_score": 0.95,
      "text_length": 1800,
      "table_count": 0,
      "image_asset_count": 3,
      "page_count": 2,
      "privacy_level": "taichang_internal_private",
      "tenant_visibility": "taichang_only",
      "access_scope": "taichang_tenant_internal",
      "reference_only": false,
      "fact_source_allowed_for_enterprise": true,
      "citation_policy": "enterprise_fact_citable",
      "authority_level": "enterprise_evidence",
      "chunk_strategy": "parent_child",
      "table_strategy": "not_applicable",
      "asset_strategy": "extract_images_with_metadata",
      "content_sha256": "hex-content-sha256",
      "doc_version": "2026-06-06",
      "superseded_by": null,
      "status": "ready_for_ingestion",
      "do_not_mix_with": [],
      "review_notes": []
    }
  ],
  "quality_summary": {
    "total_files": 1,
    "ready_for_ingestion": 1,
    "needs_review": 0,
    "blocked": 0
  }
}
```

## 字段取值约束

| 字段 | 必填 | 建议值 |
| --- | --- | --- |
| `source_domain` | 是 | `enterprise_fact`、`tender_requirement`、`reference_template`、`policy_regulation`、`base_seed` |
| `doc_owner` | 是 | `泰昌`、`国网辽宁省电力有限公司`、`河北豪乾电气设备科技有限公司`、法规/标准发布单位 |
| `doc_role` | 是 | `main_tender_file`、`technical_spec`、`goods_list`、`enterprise_evidence`、`winning_bid_reference`、`technical_response_reference`、`policy_regulation` |
| `evidence_type` | 按需 | `business_license`、`certification`、`production_capacity`、`testing_capacity`、`green_low_carbon`、`inspection_report`、`financial_evidence` |
| `parser_plan` | 是 | `native_text`、`docx_structured`、`libreoffice_then_docx`、`mineru_ocr`、`openpyxl_structured`、`archive_only` |
| `parse_status` | 是 | `pending`、`parsed`、`needs_review`、`failed`、`archive_only` |
| `quality_status` | 是 | `pass`、`warn`、`fail` |
| `privacy_level` | 是 | `public`、`customer_internal`、`taichang_internal_private` |
| `tenant_visibility` | 是 | `taichang_only`、`public_base`、`admin_only` |
| `citation_policy` | 是 | `enterprise_fact_citable`、`tender_requirement_citable`、`reference_style_only`、`law_or_standard_citable` |
| `authority_level` | 是 | `law`、`sgcc_rule`、`tender_file`、`enterprise_evidence`、`reference_template` |
| `status` | 是 | `ready_for_ingestion`、`ingested`、`needs_review`、`blocked`、`superseded` |

## 泰昌 MVP 必填校验

泰昌资料必须满足：

- `source_domain=enterprise_fact`
- `enterprise=泰昌`
- `doc_owner=泰昌`
- `reference_only=false`
- `fact_source_allowed_for_enterprise=true`
- `tenant_visibility=taichang_only`
- `access_scope=taichang_tenant_internal`

辽宁招标资料必须满足：

- `source_domain=tender_requirement`
- `doc_owner=国网辽宁省电力有限公司`
- `fact_source_allowed_for_enterprise=false`
- `province=辽宁`
- 有明确 `batch_no`、`package_no` 或 `package_code`

河北豪乾参考稿必须满足：

- `source_domain=reference_template`
- `doc_owner=河北豪乾电气设备科技有限公司`
- `reference_only=true`
- `fact_source_allowed_for_enterprise=false`
- `citation_policy=reference_style_only`
- `do_not_mix_with` 包含 `泰昌企业事实`

## 入库前检查命令建议

```bash
PYTHONPATH=. .venv/bin/python scripts/rag/dry_run_customer_chunks.py --manifest parsed_outputs/power_grid_customer_corpus/<ingestion_batch_id>/manifest.json
PYTHONPATH=. .venv/bin/python scripts/rag/eval_parse_quality.py --manifest parsed_outputs/power_grid_customer_corpus/<ingestion_batch_id>/manifest.json
```

正式入库脚本应拒绝 `quality_status=fail`、缺少 `source_domain`、缺少 `doc_owner` 或泰昌/辽宁/河北豪乾边界不一致的文件。

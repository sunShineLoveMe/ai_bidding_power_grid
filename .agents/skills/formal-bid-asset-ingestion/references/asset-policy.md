# Formal Bid Asset Policy

## Quality Tiers

| Tier | Meaning | Allowed Use |
| --- | --- | --- |
| `formal_bid_ready` | Customer original or full-page rendered evidence with clean Chinese display fields and complete metadata | Product/qualification pages, RAG, automatic DOCX image selection |
| `knowledge_only` | Useful for Q&A or internal interpretation, but not suitable for official bid insertion | Knowledge-base answers and manual review |
| `review_only` | Parser clue, OCR artifact, local crop, low-confidence extraction, or incomplete evidence | Human review only; not displayed as a formal library asset |
| `restricted` | Sensitive, unrelated, cross-tenant, non-enterprise-fact, or unsafe material | Do not expose to user pages, RAG, or DOCX |

Default to `review_only` when ownership, source domain, visual type, or title quality is unclear.

## Source Domains

| Source | Required Metadata | Rule |
| --- | --- | --- |
| Taichang enterprise fact | `enterprise=泰昌`, `source_domain=enterprise_fact`, `fact_source_allowed_for_enterprise=true`, `tenant_visibility=taichang_only` | May support Taichang facts and formal bid assets |
| Tender requirement | `source_domain=tender_requirement`, `fact_source_allowed_for_enterprise=false` | Use for requirements, not enterprise facts |
| Reference template | `source_domain=reference_template`, `reference_only=true`, `citation_policy=reference_style_only` | Use writing style/structure only |
| Parser intermediate | `rag_visibility=internal_only` or equivalent | Do not display or auto-insert |

## File-Type Handling

| File Type | Strategy |
| --- | --- |
| PNG/JPG/WebP product photos | Preserve as original image asset when clear and customer-owned; assign product/production/testing/warehouse/green category |
| PDF certificate/report/contract | Render full pages for formal evidence; do not auto-crop logos, QR codes, seals, signatures, or table cells as standalone assets |
| DOC/DOCX | Parse text and tables; extract embedded images only when they are meaningful evidence and have clean metadata |
| XLS/XLSX/CSV | Parse structurally with rows/sheets; never only vectorize as plain text when values, quantities, models, or guarantee fields exist |
| ZIP/RAR | Inventory and extract; do not directly ingest as one asset |
| MinerU extract/images | Treat as intermediate unless explicitly promoted after human-quality checks |

## Evidence Types

Use these internal enums for filtering, and always provide Chinese labels for display.

| Enum | Chinese Label | Typical Library |
| --- | --- | --- |
| `business_license` | 基础证照 | 资信库 |
| `certification` | 资质证书 | 资信库 |
| `finance` | 财务资料 | 资信库 |
| `personnel_certificate` | 人员证书 | 资信库 |
| `project_performance` | 项目业绩 | 资信库 |
| `authorization` | 授权文件 | 资信库 |
| `inspection_report` | 检验报告 | 产品库 |
| `production_capacity` | 生产制造能力 | 产品库 |
| `testing_capacity` | 试验检测能力 | 产品库 |
| `green_low_carbon` | 绿色低碳资料 | 产品库或资信库 |
| `product_image` | 产品实物图片 | 产品库 |
| `enterprise_evidence` | 企业证明材料 | 资信库 |

## User-Facing Field Rules

Forbidden in user-visible fields:

- internal enums: `taichang_*`, `power_grid_*`, `production_capacity`, `testing_capacity`, `green_low_carbon`, `business_license`, `certification`, `product_image`, `technical`;
- parser traces: `页面_`, `原图`, UUIDs, hashes, `asset_path`, `parsed_outputs`, `rag_seed`, MinerU local paths;
- API URLs: `/api/knowledge/assets`, `/api/bidding/knowledge/assets`;
- retrieval/debug fields: score, similarity, source library, matching reason, vector details.

Allowed as metadata only:

- `evidence_type`, `target_library`, `source_file`, `storage_path`, `asset_id`, `page_no`, `page_index`, `source_sha256`, `ingestion_batch_id`.

Required Chinese display fields:

- `source_display_name`
- `source_document_name`
- `category_label`
- `evidence_type_label`
- `target_library_label`
- formal display `title`
- formal caption or `caption_policy`

## Formal Caption Rules

- Product/production/testing/green/photo assets may use `资料：<正式中文标题>`.
- Full-page certificates, licenses, inspection reports, contracts, bid notices, audit reports, personnel documents, and social-security documents usually suppress captions in DOCX unless a caption is explicitly useful.
- Never write “在 XX 报告第 X 页”“页面_X 原图”“图示：XX第X页” into formal bid正文.

## Promotion Checklist

Before promoting an asset to `formal_bid_ready`, confirm:

1. customer-owned or authorized source;
2. correct source domain and tenant visibility;
3. no cross-use of Taichang, Liaoning, or Haoqian facts;
4. clean Chinese title, category, tags, source display name, and caption policy;
5. complete traceability metadata;
6. image/document is visually meaningful and not a parser crop;
7. RAG retrieval and DOCX export rules can consume it without leaking internal fields.

---
name: formal-bid-asset-ingestion
description: Domestic Chinese formal bidding asset ingestion SOP for customer-uploaded images and documents. Use when handling product-library, qualification-library, enterprise knowledge-base, RAG, or DOCX bid-export assets from PNG/JPG/WebP/PDF/DOC/DOCX/XLS/XLSX/CSV files; when cleaning uploaded asset titles, captions, tags, categories, metadata, OCR/MinerU outputs, structured tables, or formal-bid image eligibility; when preventing internal names such as taichang_*, production_capacity, 页面_, 原图, UUIDs, parser paths, or API URLs from appearing in user-facing pages, RAG answers, or official bid documents.
---

# Formal Bid Asset Ingestion

## Core Rule

Treat every customer-uploaded file as a potential formal bidding evidence asset, not as a raw filename. Preserve traceability in metadata, but only expose Chinese, bid-safe names and descriptions to users, RAG answers, and DOCX exports.

Use this skill together with `power-grid-rag-ingestion` whenever the uploaded material also affects RAG ingestion, metadata filters, structured tables, recall evaluation, or `document_chunks`.

## Workflow

1. **Inventory first**  
   Record file owner, source domain, file type, target library, evidence type, visibility, and whether the file is a formal asset, knowledge-only material, review-only clue, or restricted material.

2. **Classify by source and file type**  
   Use `references/asset-policy.md` for file-type handling, evidence types, quality tiers, metadata, and forbidden display fields.

3. **Generate bid-safe display fields**  
   Ensure `title`, `category`, `tags`, `description`, `source_display_name`, `category_label`, `evidence_type_label`, `target_library_label`, and formal captions are Chinese and user-facing. Internal enums may remain in metadata only.

4. **Separate formal assets from parser intermediates**  
   MinerU local crops, QR codes, seals, signatures, footers, partial table cells, and parser-generated fragments are review clues only. Do not insert them into product/qualification display libraries or formal DOCX.

5. **Parse structured data correctly**  
   Excel/CSV tables, technical parameter tables, goods lists, deviation tables, contracts, bid notices, invoices, and inspection reports must keep structured rows when they contain numeric facts, models, quantities, amounts, dates, guarantee values, or report results.

6. **Apply library and bid eligibility rules**  
   Product library assets must be product facts or production/testing/inspection/green-low-carbon evidence. Qualification library assets must be certificates, licenses, finance, personnel, authorization, performance, or legal/qualification evidence. Only `formal_bid_ready` assets may be auto-selected for official bid DOCX.

7. **Validate through real links**  
   Use `references/validation-gates.md` for required API, stream, RAG, DOCX, and documentation checks. Do not rely on mock-only tests for customer-facing asset changes.

## Required Output

For each asset-ingestion or cleanup task, record:

- files or upload samples processed;
- final asset counts and quality-tier counts;
- metadata fields added or changed;
- whether parser intermediates were excluded;
- real API/stream/DOCX validation results;
- regression gate status;
- files updated under `docs/rag/runs/`, `docs/rag/evaluation-records.md`, and `docs/rag/todo.md`.

## Key Project Modules

- Upload/API payload: `backend/api/assets.py`
- User-facing source cleanup: `backend/rag/display_names.py`
- Formal captions: `backend/services/formal_asset_naming.py`
- Asset retrieval and public payloads: `backend/rag/retrieval.py`
- DOCX image insertion and caption fallback: `backend/api/routes.py`, `backend/export/md_to_word.py`
- Formal bid checks: `backend/services/formal_bid_check.py`, `rules/power_grid/formal_bid_check_rules.v1.json`
- Current quality tracker: `docs/development/taichang-formal-asset-cleanup-todo.md`

# Formal Bid Asset Validation Gates

## Minimum Validation Matrix

| Change Type | Required Validation |
| --- | --- |
| Upload payload, title, category, tags, metadata | Unit tests for payload builders and display sanitizers; real `POST /api/knowledge/assets/upload`; list/detail API check |
| User-facing RAG answer/source cleanup | Real `/api/knowledge/search/stream`; inspect SSE, answer text, images, assets, raw contexts |
| Retrieval or metadata filtering | Base 30 + Taichang/customer 30 incremental regression gate |
| DOCX image selection or captions | Real `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`; inspect DOCX XML |
| Structured Excel/CSV/DOCX/PDF data | Structured extraction tests plus real API/stream question covering exact values and sources |
| Cloud deployment readiness | Repeat the relevant real API/browser checks on Aliyun after deployment |

## Standard Commands

Run targeted unit tests first:

```bash
.venv/bin/python -m pytest \
  tests/test_knowledge_asset_upload_payload.py \
  tests/test_rag_display_names.py \
  tests/test_rag_retrieval.py \
  tests/test_rag_asset_scoring.py \
  tests/test_docx_export.py \
  -q
```

Run Python syntax checks:

```bash
python3 -m py_compile backend/api/assets.py backend/rag/display_names.py backend/services/formal_asset_naming.py
```

Run standard RAG gate after metadata, retrieval, source display, or asset eligibility changes:

```bash
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_incremental_regression_gate.py --run-id <run_id>
```

## Real Upload Smoke

Use an authenticated request. For local dev with login enabled:

```bash
curl -sS -c /tmp/ai_bid_cookie.txt \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"12345678"}' \
  http://127.0.0.1:3012/api/users/login
```

Upload a deliberately dirty sample name and confirm it is cleaned:

```bash
curl -sS -b /tmp/ai_bid_cookie.txt \
  -X POST http://127.0.0.1:3012/api/knowledge/assets/upload \
  -F 'file=@/tmp/泰昌MPP生产线_页面_9原图.png;type=image/png' \
  -F 'library_type=product' \
  -F 'title=泰昌MPP生产线_页面_9原图' \
  -F 'category=production_capacity' \
  -F 'tags=泰昌,taichang,production_capacity,technical' \
  -F 'applicable_sections=生产制造能力' \
  -F 'applicable_volumes=technical'
```

Required checks:

- title is Chinese and formal, for example `泰昌MPP生产线资料`;
- category and tags are Chinese;
- metadata includes `source_display_name`, `evidence_type_label`, `target_library_label`, `caption_policy`;
- visible fields and `searchable_text` contain none of `页面_`, `原图`, `taichang`, `production_capacity`, `technical`, `product_image`.

Delete synthetic smoke assets from the database after validation so they do not pollute formal libraries.

## Stream Smoke

Ask a real question that should retrieve the uploaded or repaired asset:

```bash
curl -sS -N \
  -H "Authorization: Bearer <token>" \
  -H 'Content-Type: application/json' \
  -d '{"query":"泰昌MPP生产线资料可以作为技术标生产制造能力配图吗？请说明可引用资料。"}' \
  http://127.0.0.1:3012/api/knowledge/search/stream
```

Inspect:

- `done=true`, no error event;
- `contexts_count` or `assets_count` > 0;
- answer text contains no forbidden internal fields;
- `assets[].asset_type` is Chinese if returned to the UI;
- image URLs may include `/api/knowledge/assets`, but the answer body must not expose API paths as prose.

## DOCX Gate

When formal export is affected, verify:

- cover, directory, headers, footers, and page fields refresh;
- selected/inserted/failed image counts;
- no Haoqian reference images or Liaoning tender images used as Taichang facts;
- DOCX `word/*.xml` contains none of `图示：`, `原图`, `页面_`, `parsed_outputs`, `taichang_`, internal enums, or API asset URLs in body text.

## Documentation Updates

After each real task, update the relevant records:

- `docs/rag/runs/<run_id>.md` and JSON when useful;
- `docs/rag/evaluation-records.md`;
- `docs/rag/todo.md`;
- `docs/development/taichang-formal-asset-cleanup-todo.md` for formal asset work;
- `docs/development/docx-bid-export-quality-todo.md` for DOCX output changes.

If any gate fails, record it as failed with concrete causes and next actions. Do not silently omit failed checks.

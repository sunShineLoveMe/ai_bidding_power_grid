# Run 20260627 — 产品库/资信库上传表单资料规范产品化

## 背景

客户后续会持续自行上传图片、PDF、Word、Excel、CSV 等资料。若上传入口只提供自由分类和普通附件选择，二维码、印章、局部截图、表格截图、内部文件名等低质量资产容易进入知识库和正式标书候选，影响正式投标文件质量。

本轮目标是把正式投标资产 SOP 产品化到产品库和资信库上传表单，不依赖开发人员后续逐批人工修补。

## 改动范围

- 前端产品库上传表单新增中文资料类型：产品实物图片、生产制造能力、试验检测设备、检验报告、绿色低碳资料、厂房仓储资料、产品参数表、技术响应资料。
- 前端资信库上传表单新增中文资料类型：基础证照、资质证书、财务资料、人员证书、社保证明、项目业绩、合同证明、中标通知书、授权文件、企业证明材料。
- 上传文件支持范围扩展到 Excel/CSV：`.xls/.xlsx/.csv`。
- 选择资料类型后展示推荐文件格式和正式投标使用提示。
- 选择文件后即时做质量预检，显示“可用于正式标书 / 仅用于知识库 / 需人工复核 / 禁止使用”。
- 后端入库统一写入 `quality_tier`、`quality_tier_label`、`quality_notes`、`user_requested_bid_usage`。
- DOCX 自动配图只允许 `quality_tier=formal_bid_ready` 的资产；表格、DOCX、低清小图、二维码/印章/签名/局部截图默认不会自动进入正式标书。
- 资产 API 返回层移除 `embedding`，并压平内部 `searchable_text` 换行，避免前端/脚本暴露或解析内部检索字段。

## 真实验证

### 单元与构建

```bash
python3 -m py_compile backend/api/assets.py backend/core/security.py backend/rag/display_names.py backend/api/routes.py
.venv/bin/python -m pytest tests/test_knowledge_asset_upload_payload.py -q
npm run build
.venv/bin/python -m pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py tests/test_rag_display_names.py -q
```

结果：

- 上传 payload 测试：`5 passed, 2 subtests passed`
- DOCX/RAG/display 定向回归：`95 passed, 1 warning`
- 前端 TypeScript/Vite 构建：PASS

### 真实 API

用真实登录会话调用：

```text
POST /api/knowledge/assets/upload
```

上传测试文件：`泰昌上传表单回归产品参数表.csv`

验证结果：

```json
{
  "title": "泰昌上传表单回归产品参数表",
  "category": "产品参数表",
  "quality_tier": "knowledge_only",
  "allowed_for_bid": false,
  "evidence_type_label": "产品参数表",
  "has_embedding": false,
  "searchable_text_has_newline": false
}
```

测试资产已从 `knowledge_assets` 删除，避免污染客户真实资料库。

### 真实浏览器

浏览器：Chrome headless，访问本地 `http://127.0.0.1:5173`。

覆盖：

- 登录 `admin`
- 企业产品库打开上传弹窗，选择“产品参数表”，上传 CSV，页面出现“资料预检：仅用于知识库”
- 企业资信库打开上传弹窗，选择“基础证照”，上传 1x1 局部截图样张，页面出现“资料预检：需人工复核”

截图：

- `docs/development/runs/screenshots/run_20260627_asset_upload_product_form.png`
- `docs/development/runs/screenshots/run_20260627_asset_upload_qualification_form.png`

### RAG 增量门禁

```bash
set -a; source .env; set +a; .venv/bin/python scripts/rag/run_incremental_regression_gate.py --run-id run_20260627_asset_upload_form_productization_gate
```

结果：PASS

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.973 | 0.0% | 0.0% |

## 结论

P2-4 完成。产品库/资信库上传入口已经从“自由上传附件”升级为正式投标资料准入表单：用户看到的是中文资料类型、推荐格式、质量预检和正式使用范围；后端同步执行质量门禁，避免低质量资料直接进入正式 DOCX 自动配图。

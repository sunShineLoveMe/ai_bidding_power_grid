# 水利行业 RAG 种子知识库

本目录用于给企业知识库提供第一批水利招投标基础资料。资料分为公开来源下载和项目自建模板两类。

## 目录

- `01_tender_documents/`：公开招标公告、招标文件 PDF、招标文件公示页面。
- `02_policy_regulations/`：招投标、水利建设、质量、安全、验收、信用等政策法规。
- `03_standards_specs/`：公开示范文本、标准目录和规范引用资料。
- `04_standard_phrases/`：自建水利投标标准话术、检查清单、施工组织设计模板。
- `index.csv` / `index.jsonl`：RAG 入库元数据索引。

## 本次采集数量

- `01_tender_documents`：12 条
- `02_policy_regulations`：8 条
- `03_standards_specs`：2 条
- `04_standard_phrases`：7 条

## 入库建议

1. 优先导入 `04_standard_phrases`，这些是可直接用于生成投标文件的自有知识。
2. 再导入 `02_policy_regulations`，用于法规依据、资格条件、质量安全、验收和信用合规问答。
3. 最后导入 `01_tender_documents` 和 `03_standards_specs`，用于学习招标文件结构、评标办法、投标文件格式和技术条款表达。
4. PDF 建议先走 MinerU/OCR，保留页码、表格、章节层级；HTML/Markdown 可以直接按标题层级切片。

## 版权和使用边界

本目录优先采集政府网站、公共资源交易平台或政府附件公开资料。标准规范全文通常存在版权边界，后续不要混入来源不明或付费平台搬运的全文资料；可通过标准名称、适用场景、条文引用位置和企业自有理解形成可检索的二级知识。

## 重新下载

```bash
python rag_seed/water_resources/_scripts/download_water_rag_seed.py
```

## 入库结果

已执行企业知识库入库脚本：

```bash
python rag_seed/water_resources/_scripts/ingest_water_rag_seed.py
```

本次入库范围排除了下载失败的 `.url.md` 占位文件，仅处理 `index.csv` 中 `status=downloaded/generated` 的有效资料。

- 有效资料：26 份
- 新入库资料：26 份
- 新增向量分片：558 条
- 入库目标：Supabase `knowledge_documents` / `document_chunks`
- 对象存储：`SUPABASE_STORAGE_KNOWLEDGE_BUCKET` 对应 bucket
- 入库分类：
  - `water_tender_documents`
  - `water_policy_regulations`
  - `water_standards_specs`
  - `water_standard_phrases`

入库报告：

- `ingestion_report.md`
- `ingestion_report.json`

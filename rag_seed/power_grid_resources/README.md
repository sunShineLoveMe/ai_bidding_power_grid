# 国网电力行业 RAG 种子知识库

本目录用于给企业知识库提供第一批国网电力招投标基础资料。资料分为公开来源下载和项目自建模板两类，重点支撑国家电网、输变电工程、配网工程、电力设施安装调试等投标场景。

## 目录

- `01_tender_documents/`：国网公开采购公告、输变电工程公开报告和招投标流程样例。
- `02_policy_regulations/`：招标投标、电力法、能源法、电力建设安全、质量监督和备案等政策法规。
- `03_standards_specs/`：电力建设标准目录、常用标准引用说明和国网企业技术体系引用边界。
- `04_standard_phrases/`：自建国网投标标准话术、章节库、资格/商务/技术/质量安全环保模板、检查清单。
- `index.csv` / `index.jsonl`：RAG 入库元数据索引。

## 本次采集数量

- `01_tender_documents`：7 条
- `02_policy_regulations`：19 条
- `03_standards_specs`：23 条
- `04_standard_phrases`：6 条
- 下载成功：34 条
- 自建生成：7 条
- 下载失败但保留 URL：14 条

## 入库建议

1. 优先导入 `04_standard_phrases`，这些是可直接用于生成投标文件的自有知识。
2. 再导入 `02_policy_regulations`，用于法规依据、资格条件、质量安全、必须招标范围、质量监督和备案要求问答。
3. 最后导入 `01_tender_documents` 和 `03_standards_specs`，用于学习国网采购公告结构、ECP/ETP 平台流程、评标/应答风险、电力工程标准引用和输变电项目场景词汇。
4. PDF 建议先走 MinerU/OCR，保留页码、表格和章节层级；HTML/Markdown 使用 v2 父子分块脚本按 `doc_role` 切分，不再走统一定长切片。

## 版权和使用边界

本目录优先采集政府网站、国家能源局、国家电网公开页面或公开 PDF。国家标准、行业标准、国网企业标准全文通常存在版权边界，后续不要混入来源不明或付费平台搬运的全文资料；可通过标准名称、标准编号、适用场景、条文引用位置和企业自有理解形成可检索的二级知识。

## 重新下载

```bash
python rag_seed/power_grid_resources/_scripts/download_power_grid_rag_seed.py
```

## 入库脚本

```bash
python scripts/rag/ingest_power_grid_v2.py
```

脚本默认读取 `index.csv` 中 `status=downloaded/generated` 的 Markdown/网页型资料和自建标准话术，跳过 PDF。入库时先清洗网页导航噪声，再按 `doc_role` 生成 parent/child 两层 chunk；仅 child 写入 embedding，parent 作为写作回溯上下文。

PDF 资料需要先确认抽取质量、摘要边界和版权边界，经过 MinerU/OCR 转换并复核后，再显式纳入本索引。

常用参数：

```bash
python scripts/rag/ingest_power_grid_v2.py --dry-run
python scripts/rag/ingest_power_grid_v2.py --category 04_standard_phrases
```

本地验证结果见：

- `docs/rag/evaluation-records.md`
- `docs/rag/_run_filtered.json`
- `docs/rag/_run_nofilter.json`

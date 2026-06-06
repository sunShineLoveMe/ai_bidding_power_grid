# 泰昌 MVP 试点资料 P0 启动记录

> 日期：2026-06-06
> 批次 ID：`customer_liaoning_taichang_20260606_p0`
> 范围：泰昌 MVP 试点企业资料、辽宁电缆保护管招标资料、河北豪乾中标参考稿。

## 目标

本轮目标不是直接全量入库，而是先补齐 P0 级边界与解析前置条件：

1. 完成 RAG P0 中旧部署/历史文档的迁移参考标注，避免误用旧脚本。
2. 为泰昌 MVP 批次建立强隔离 manifest，防止“泰昌事实”和“河北豪乾参考稿”混用。
3. 验证 MinerU/OCR 对泰昌扫描件的可用性。
4. 为 MinerU 解析出的图片资源生成后续知识库、产品库、资信库批量入库所需 metadata。

## P0 基座状态

`docs/rag/todo.md` 中 P0 已全部完成。最后一项“旧部署/历史文档标注迁移参考”已在以下文档补充边界：

- `docs/deployment/supabase-setup.md`
- `docs/deployment/supabase-to-postgres-migration.md`
- `docs/deployment/local-postgres-docker.md`
- `docs/deployment/gitee-ai-bid-runbook.md`

新环境入口统一指向：

- PostgreSQL 正式迁移链：`migrations/postgres/`
- 电网 RAG v2 入库：`scripts/rag/ingest_power_grid_v2.py`
- 客户批次入库与评测：`scripts/rag/ingest_customer_corpus.py`、`scripts/rag/eval_recall.py`

## 批次 Manifest

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/manifest.json`

摘要：

| 指标 | 数量 |
| --- | ---: |
| 文件总数 | 230 |
| 泰昌企业事实文件 | 44 |
| 辽宁招标要求文件 | 184 |
| 河北豪乾参考稿文件 | 2 |
| 敏感私有文件 | 17 |
| MinerU/OCR 候选 | 45 |
| 图片抽取候选 | 145 |

强边界：

| source_domain | doc_owner | 允许用途 | 禁止用途 |
| --- | --- | --- | --- |
| `enterprise_fact` | 泰昌 | 泰昌企业资质、产品、生产、检测、绿色低碳等事实 | 河北豪乾事实 |
| `tender_requirement` | 国网辽宁省电力有限公司 | 招标要求、货物清单、合同、技术规范 | 任一投标人企业事实 |
| `reference_template` | 河北豪乾电气设备科技有限公司 | 标书目录、格式、章节组织、写法参考 | 泰昌企业事实或泰昌业绩 |

## MinerU/OCR Smoke

样本：

- `rag_seed/power_grid_resources/05_enterprise_documents/01_泰昌MVP试点企业资料/extracted/泰昌资料/营业执照副本.pdf`

原因：

- 单页；
- 属于泰昌企业事实；
- 原生 PDF 文本抽取为空，能验证扫描件 OCR 价值。

结果：

| 项 | 结果 |
| --- | --- |
| MinerU token | 已配置 |
| DashScope / DeepSeek key | 已配置 |
| MinerU 状态 | `mineru_done` |
| 页数 | 1 |
| Markdown | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/extract/full.md` |
| Content list | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/extract/bb1e2413-db49-49b8-b777-7ac42e77d30a_content_list.json` |
| Layout / model | 已产出 `layout.json`、`*_model.json` |
| 图片资产 | 1 个 |
| 下载方式 | requests 失败后使用 curl fallback，zip 完整 |

OCR 抽取到的关键字段包括：

- 统一社会信用代码；
- 企业名称：河北泰昌电力器材科技有限公司；
- 法定代表人；
- 经营范围，包含电缆保护管研发、制造、加工；
- 注册资本；
- 成立日期、营业期限、住所。

## 图片资产 Metadata

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/asset_manifest.json`

当前样本产出 1 个图片资产，metadata 已包含：

- `source_domain=enterprise_fact`
- `doc_owner=泰昌`
- `enterprise=泰昌`
- `evidence_type=business_license`
- `target_library=qualification_library`
- `privacy_level=restricted_private`
- `reference_only=false`
- `fact_source_allowed_for_enterprise=true`
- `page_idx/page_no/bbox`
- `asset_sha256`
- `usage_policy=enterprise_fact_evidence`
- `do_not_mix_with=河北豪乾参考稿`

这个结构可扩展到后续资信库、产品库、知识库批量入库。

## 后续 P0 队列

1. 全量泰昌扫描 PDF MinerU/OCR：按 `manifest.json` 中 `parse_plan` 执行，敏感件标 `restricted_private`，先产物化，不直接入库。
2. 辽宁货物清单结构化：兼容 `dimension ref=A1` 但 worksheet XML 实际多行多列的异常，输出 87 条去重需求行。
3. 河北豪乾参考稿格式抽取：只抽封面、目录、章节组织、页眉页脚、表格和签章位，metadata 固定 `reference_only=true`。
4. 泰昌事实与参考稿隔离评测：新增专项测试集，验证问泰昌事实不召回河北豪乾事实，问格式参考可召回河北豪乾但不改写主体。
5. 全量 OCR 后生成 parse quality report，再决定哪些资料进入知识库、产品库、资信库。

## 2026-06-06 后续推进

### 辽宁货物清单结构化

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/goods_tables/goods_rows.json`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/goods_tables/goods_summary.json`

结果：

- 解析文件数：6 个 `.xlsx`
- 去重需求行：87 条
- 解析器：`xlsx_worksheet_xml`
- 说明：本批 Excel 的 workbook dimension 标记为 `A1`，普通 openpyxl 读取会误判为空表；本轮直接解析 worksheet XML，保留分标编号、包名称、需求单位、物资名称、物资描述、数量、交货日期、技术规范编码等字段。

### 河北豪乾参考稿基础模板数据

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/reference_templates/haoqian_reference_templates.json`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/reference_templates/haoqian_reference_templates.md`

抽取范围：

- 封面字段；
- 招标编号、分标名称、包号；
- 目录结构；
- 章节粒度；
- 可作为格式/目录/写法参考的材料清单。

硬边界：

- `source_domain=reference_template`
- `doc_owner=河北豪乾电气设备科技有限公司`
- `reference_only=true`
- `fact_source_allowed_for_enterprise=false`

禁止用途：

- 泰昌资质事实；
- 泰昌业绩事实；
- 泰昌生产/检测/财务事实；
- 自动填充泰昌企业能力证明。

### 泰昌 OCR 优先级计划

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/ocr_plan/taichang_ocr_plan.json`

摘要：

| evidence_type | 文件数 | 页数 | 空文本/低文本 |
| --- | ---: | ---: | ---: |
| `finance` | 3 | 67 | 3 |
| `certification` | 6 | 28 | 3 |
| `inspection_report` | 2 | 10 | 0 |
| `production_capacity` | 15 | 47 | 14 |
| `testing_capacity` | 12 | 55 | 12 |
| `green_low_carbon` | 3 | 91 | 0 |
| `business_license` | 1 | 1 | 1 |

### 泰昌首批 MinerU OCR

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_batch/`

已完成文件：

| 文件 | evidence_type | 状态 | 图片资产 |
| --- | --- | --- | ---: |
| `营业执照副本.pdf` | `business_license` | `mineru_done` | 1 |
| `2.环境管理体系认证证书.pdf` | `certification` | `mineru_done` | 10 |
| `1.质量管理体系认证证书.pdf` | `certification` | `mineru_done` | 9 |
| `3.职业健康安全管理体系认证证书.pdf` | `certification` | `mineru_done` | 7 |
| `生产设备台账.pdf` | `production_capacity` | `mineru_done` | 1 |

累计：

- OCR 文件：5 份
- 图片资产 metadata：28 个

每个图片资产 metadata 均包含：

- `source_domain=enterprise_fact`
- `doc_owner=泰昌`
- `enterprise=泰昌`
- `evidence_type`
- `target_library`
- `privacy_level`
- `reference_only=false`
- `fact_source_allowed_for_enterprise=true`
- `page_idx/page_no/bbox`
- `asset_sha256`
- `do_not_mix_with=河北豪乾参考稿`

## 回归验证

命令：

```bash
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/manifest.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/asset_manifest.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_smoke/business_license/status.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/goods_tables/goods_rows.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/goods_tables/goods_summary.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/reference_templates/haoqian_reference_templates.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/ocr_plan/taichang_ocr_plan.json
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_batch/batch_summary.json
PYTHONPATH=. .venv/bin/pytest tests/test_mineru_status.py -q
```

结果：

- JSON 产物校验通过。
- 语义检查通过：辽宁货物清单 87 条；河北豪乾 2 份参考稿均为 `reference_only=true` 且 `fact_source_allowed_for_enterprise=false`；首批 MinerU batch 全部 `mineru_done`。
- `docs/rag/todo.md` P0 核查通过，P0 行全部为 `[x]`。
- `tests/test_mineru_status.py`：5 passed。
- 单测有 PyPDF2 / `datetime.utcnow()` deprecation warnings，不影响本轮 P0 资料处理结论。

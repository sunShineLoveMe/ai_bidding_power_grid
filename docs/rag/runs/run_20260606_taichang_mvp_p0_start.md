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

### 泰昌第二批 MinerU OCR

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_batch_02/`

本批目标是补齐生产制造能力、厂房与试验检测设备材料，支撑后续技术标图文插入和知识库问答中的图片展示。

已完成文件：

| 文件 | evidence_type | 页数 | 状态 | 图片资产 |
| --- | --- | ---: | --- | ---: |
| `2.土地使用证明.pdf` | `production_capacity` | 1 | `mineru_done` | 1 |
| `4.电费发票.pdf` | `production_capacity` | 3 | `mineru_done` | 0 |
| `1.土地租赁协议.pdf` | `production_capacity` | 4 | `mineru_done` | 4 |
| `3.厂房图片.pdf` | `production_capacity` | 6 | `mineru_done` | 6 |
| `电子天平.pdf` | `testing_capacity` | 6 | `mineru_done` | 7 |
| `1.CPVC63三层复合管材挤出生产线.pdf` | `production_capacity` | 7 | `mineru_done` | 5 |
| `2.CPVC110三层复合管材挤出生产线.pdf` | `production_capacity` | 7 | `mineru_done` | 5 |
| `溶体流动速率仪.pdf` | `testing_capacity` | 7 | `mineru_done` | 8 |
| `3.MPP生产线.pdf` | `production_capacity` | 8 | `mineru_done` | 7 |
| `微机控制电子万能试验机.pdf` | `testing_capacity` | 8 | `mineru_done` | 7 |

本批新增：

- OCR 文件：10 份
- 图片资产 metadata：50 个

累计：

- OCR 文件：15 份
- 图片资产 metadata：78 个

### 统一图片资产索引

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/asset_index.json`

摘要：

| target_library | 图片资产数 |
| --- | ---: |
| `qualification_library` | 27 |
| `product_library` | 51 |

| evidence_type | 图片资产数 |
| --- | ---: |
| `business_license` | 1 |
| `certification` | 26 |
| `production_capacity` | 29 |
| `testing_capacity` | 22 |

统一索引中每个资产均要求包含：

- 图片显示：`asset_path`、`asset_sha256`、`page_no`、`bbox`
- 问答召回：`retrieval_text`、`caption_candidate`、`ocr_context`
- 入库边界：`source_domain=enterprise_fact`、`doc_owner=泰昌`、`enterprise=泰昌`
- 目标库：`target_library=qualification_library/product_library`
- 展示场景：`display_contexts=[bid_writing, knowledge_chat, asset_search]`
- 防串用：`reference_only=false`、`fact_source_allowed_for_enterprise=true`、`do_not_mix_with=河北豪乾参考稿`

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
- 统一图片资产索引语义检查通过：78 个资产全部为泰昌企业事实，均有 `asset_path/asset_sha256/page_no/bbox`，且全部禁止混用河北豪乾参考稿。
- `docs/rag/todo.md` P0 核查通过，P0 行全部为 `[x]`。
- `tests/test_mineru_status.py`：5 passed。
- 单测有 PyPDF2 / `datetime.utcnow()` deprecation warnings，不影响本轮 P0 资料处理结论。

## 2026-06-06 第三批 OCR

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_batch_03/`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/asset_index.json`

本批目标：

- 补齐试验检测设备图片资料；
- 解析人员证书、社保证明、花名册等受限私有资料；
- 验证 `restricted_private` 图片资产必须带授权展示 metadata。

已完成文件：

| 文件 | evidence_type | 页数 | privacy_level | 状态 | 图片资产 |
| --- | --- | ---: | --- | --- | ---: |
| `锤击试验装置.pdf` | `testing_capacity` | 8 | `private` | `mineru_done` | 9 |
| `电子拉力试验机.pdf` | `testing_capacity` | 8 | `private` | `mineru_done` | 8 |
| `热变型、维卡软化点温度测定仪.pdf` | `testing_capacity` | 9 | `private` | `mineru_done` | 14 |
| `1.陈仙瑞.pdf` | `production_capacity` | 1 | `restricted_private` | `mineru_done` | 1 |
| `2.晁坤琳.pdf` | `production_capacity` | 1 | `restricted_private` | `mineru_done` | 2 |
| `泰昌社保证明.pdf` | `production_capacity` | 1 | `restricted_private` | `mineru_done` | 2 |
| `1.陈仙瑞.pdf` | `testing_capacity` | 1 | `restricted_private` | `mineru_done` | 1 |
| `2.晁坤琳.pdf` | `testing_capacity` | 1 | `restricted_private` | `mineru_done` | 2 |
| `泰昌社保证明.pdf` | `testing_capacity` | 1 | `restricted_private` | `mineru_done` | 2 |
| `公司人员花名册.pdf` | `production_capacity` | 2 | `restricted_private` | `mineru_done` | 0 |

本批新增：

- OCR 文件：10 份
- 图片资产 metadata：41 个

累计：

- OCR 文件：25 份
- 图片资产 metadata：119 个

统一图片资产索引刷新后：

| 维度 | 数量 |
| --- | ---: |
| 全部图片资产 | 119 |
| `qualification_library` | 27 |
| `product_library` | 92 |
| `private` | 108 |
| `restricted_private` | 11 |

按 evidence_type：

| evidence_type | 图片资产数 |
| --- | ---: |
| `business_license` | 1 |
| `certification` | 26 |
| `production_capacity` | 34 |
| `testing_capacity` | 58 |

受限资产规则：

- `restricted_private` 资产必须包含 `requires_authorization=true`；
- 展示场景限制为 `restricted_review` / `authorized_bid_writing`；
- metadata 中写入 `sensitive_handling=redact_or_authorize_before_display`；
- 不进入普通知识库问答图片自动展示，除非后续授权策略明确允许。

第三批回归：

```bash
find parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0 -name '*.json' -maxdepth 5 -print0 | xargs -0 -I{} .venv/bin/python -m json.tool {} >/dev/null
PYTHONPATH=. .venv/bin/pytest tests/test_mineru_status.py -q
```

结果：

- JSON 全量校验：`all_json_ok`
- 图片资产语义检查：`asset_semantic_checks_ok`
- MinerU 状态单测：5 passed

## 2026-06-06 全量 OCR 补齐

用户确认 OCR 额度充足后，本轮将剩余 17 份 PDF 全部走 MinerU，包括原生文本可抽取但需要版式/图片资产的检验报告、绿色低碳材料和审计报告。

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/mineru_batch_04/`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/asset_index.json`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/ocr_coverage_report.json`

第四批完成文件：

| evidence_type | 文件数 | 图片资产 |
| --- | ---: | ---: |
| `certification` | 3 | 15 |
| `production_capacity` | 3 | 3 |
| `testing_capacity` | 3 | 2 |
| `inspection_report` | 2 | 2 |
| `green_low_carbon` | 3 | 38 |
| `finance` | 3 | 63 |

最终 OCR 覆盖：

| 指标 | 数量 |
| --- | ---: |
| 泰昌 PDF 总数 | 42 |
| MinerU 完成 | 42 |
| 缺失 | 0 |
| 图片资产 | 242 |
| 资产 manifest | 42 |

按目标库：

| target_library | 图片资产数 |
| --- | ---: |
| `qualification_library` | 105 |
| `product_library` | 137 |

按 evidence_type：

| evidence_type | 图片资产数 |
| --- | ---: |
| `business_license` | 1 |
| `certification` | 41 |
| `finance` | 63 |
| `green_low_carbon` | 38 |
| `inspection_report` | 2 |
| `production_capacity` | 37 |
| `testing_capacity` | 60 |

按敏感级别：

| privacy_level | 图片资产数 |
| --- | ---: |
| `private` | 164 |
| `restricted_private` | 78 |

受限资产规则继续保持：

- `restricted_private` 资产全部包含 `requires_authorization=true`；
- 展示场景限制为 `restricted_review` / `authorized_bid_writing`；
- metadata 中写入 `sensitive_handling=redact_or_authorize_before_display`；
- 默认不进入普通问答图片自动展示。

全量补齐回归：

```bash
find parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0 -name '*.json' -maxdepth 5 -print0 | xargs -0 -I{} .venv/bin/python -m json.tool {} >/dev/null
PYTHONPATH=. .venv/bin/pytest tests/test_mineru_status.py -q
```

结果：

- JSON 全量校验：`all_json_ok`
- 覆盖率和图片资产语义检查：`coverage_and_asset_semantic_checks_ok`
- MinerU 状态单测：5 passed

## 2026-06-06 Parse Quality 与专项测试集

### Parse Quality Report

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/parse_quality_report.json`
- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/parse_quality_report.md`

摘要：

| 指标 | 数量 |
| --- | ---: |
| PDF 总数 | 42 |
| MinerU 完成 | 42 |
| 文本字符数 | 284019 |
| 图片资产 | 242 |
| 受限图片资产 | 78 |

按资料类型：

| evidence_type | 文件数 | 文本字符 | 图片资产 | 受限文件 |
| --- | ---: | ---: | ---: | ---: |
| `finance` | 3 | 91859 | 63 | 3 |
| `certification` | 6 | 24997 | 41 | 0 |
| `inspection_report` | 2 | 8825 | 2 | 0 |
| `production_capacity` | 15 | 33036 | 37 | 6 |
| `testing_capacity` | 12 | 60938 | 60 | 6 |
| `green_low_carbon` | 3 | 63806 | 38 | 0 |
| `business_license` | 1 | 558 | 1 | 1 |

入库建议：

| 建议 | 文件数 |
| --- | ---: |
| `ready_for_private_ingestion` | 24 |
| `ingest_only_after_authorization_or_redaction` | 16 |
| `ingest_with_spec_coverage_warning` | 2 |

质量标记：

| 标记 | 数量 | 处理 |
| --- | ---: | --- |
| `restricted_private_requires_authorization` | 16 | 授权/脱敏后再展示或入普通问答 |
| `spec_coverage_needs_business_confirmation` | 2 | CPVC/MPP 内径 250 检验报告需确认与辽宁清单规格覆盖关系 |
| `no_image_assets` | 3 | 可保留文本，不影响 OCR 完成状态 |

### 辽宁/泰昌专项评测集

产物：

- `tests/rag/customer_liaoning_taichang_testset.jsonl`

用例数：17 条。

覆盖场景：

- 辽宁 `2225AC` CPVC/MPP 货物清单；
- 辽宁技术规范和合同条款；
- 泰昌营业执照、三体系认证、生产制造能力、试验检测能力、绿色低碳、检验报告；
- 图片资产召回和展示 metadata；
- 河北豪乾商务/技术参考稿仅作为格式模板；
- 负样本：禁止河北豪乾参考稿变成泰昌事实，禁止泰昌企业事实污染辽宁招标要求，禁止受限私有图片在普通问答中自动展示。

说明：

- 当前测试集是正式入库后的召回门禁，尚未跑 `eval_recall.py`，因为本批资料还未写入 pgvector。
- 正式入库后必须运行 Base + `customer_liaoning_taichang_testset.jsonl`，并追加 `docs/rag/evaluation-records.md`。

验证：

```bash
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/parse_quality_report.json >/dev/null
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/ocr_coverage_report.json >/dev/null
.venv/bin/python -m json.tool parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/asset_index.json >/dev/null
PYTHONPATH=. .venv/bin/pytest tests/test_mineru_status.py -q
```

结果：

- JSON / JSONL 校验：`all_json_and_jsonl_ok`
- 专项测试集语义校验：`testset_semantic_checks_ok`
- Parse quality 语义校验：`parse_quality_semantic_checks_ok`
- MinerU 状态单测：5 passed

# Run 20260611 — 泰昌资质补充包与 Logo 入库完整记录

> 批次 ID：`customer_taichang_supplement_20260611`  
> 原始资料：`泰昌资质文件(补充).zip`、`assets/icons/taichang.png`  
> MVP 主体：河北泰昌电力器材科技有限公司  
> 运行时间：2026-06-11

## 处理范围

本次按泰昌企业事实资料处理，metadata 统一使用：

- `enterprise=泰昌`
- `doc_owner=河北泰昌电力器材科技有限公司`
- `source_domain=enterprise_fact`
- `fact_source_allowed_for_enterprise=true`
- `reference_only=false`
- `tenant_visibility=taichang_only`
- `access_scope=taichang_tenant_internal`

原始压缩包已落位到：

```text
rag_seed/power_grid_resources/05_enterprise_documents/02_泰昌资质文件补充_20260611/泰昌资质文件(补充).zip
```

官方 Logo 已落位到：

```text
rag_seed/power_grid_resources/05_enterprise_documents/01_泰昌MVP试点企业资料/00_brand_assets/泰昌官方Logo.png
```

## Inventory

| 项 | 数量 |
| --- | ---: |
| 总文件 | 70 |
| `.pdf` | 24 |
| `.jpg` | 34 |
| `.png` | 12 |
| 可文本入库 manifest | 13 |
| 图片资产 payload | 297 |

按证据类型统计：

| evidence_type | 数量 |
| --- | ---: |
| `inspection_report` | 8 |
| `enterprise_evidence` | 7 |
| `production_capacity` | 6 |
| `business_license` | 8 |
| `testing_capacity` | 16 |
| `finance` | 10 |
| `project_performance` | 2 |
| `green_low_carbon` | 5 |
| `signature_seal` | 3 |
| `enterprise_profile` | 1 |
| `certification` | 3 |
| `brand_logo` | 1 |

以下签章/签名文件仅归档，不自动进入正式标书配图或企业事实问答：

- `46公章法人章签名图片/晁坤琳.png`
- `46公章法人章签名图片/晁坤琳手章.jpg`
- `46公章法人章签名图片/透明公章.png`

## 解析与入库

新增 staging 脚本：

```text
scripts/rag/stage_taichang_supplement_20260611.py
```

脚本完成：

- 解压后 inventory；
- 文本型 PDF 抽取；
- PDF 整页渲染正式图片资产；
- 客户原始 JPG/PNG 作为正式原图资产；
- 官方 Logo 作为 `brand_logo` 资产；
- 清洗文本中的 NUL/control 字符，避免 PostgreSQL text 写入失败；
- 签章/签名文件限制为 `allowed_for_bid=false`。

文本资料真实入库结果：

| 指标 | 数量 |
| --- | ---: |
| documents | 13 |
| indexed | 13 |
| parent chunks | 33 |
| child chunks | 331 |
| embeddings | 331 |
| blocked metadata | 0 |

图片资产真实入库结果：

| 指标 | 数量 |
| --- | ---: |
| payloads | 297 |
| imported | 297 |
| failed | 0 |
| deleted existing | 0 |

## 产品参数

本批补充包中的 CPVC/MPP 内径 250 检验报告与既有结构化参数层报告编号一致：

| 产品 | 报告编号 | 关键值 |
| --- | --- | --- |
| MPP 电缆保护管 | `2024100312005501712` | 平均内径 `250.0~250.2 mm`，环刚度 `66.40 kN/m²` |
| CPVC 电缆保护管 | `2024100312005501713` | 平均内径 `250.2~250.4 mm`，80°C 环刚度 `21.63 kN/m²` |

本次未重复新增结构化参数行；补充资料作为新的可追溯文本来源与整页图片佐证进入知识库和图片资产库。

## 回归结果

增量回归门禁：

```bash
set -a; source .env; set +a; .venv/bin/python scripts/rag/run_incremental_regression_gate.py --run-id run_20260611_taichang_supplement_ingestion
```

门禁状态：PASS。

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% |

专项单测：

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_taichang_product_parameter_query.py tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py tests/test_incremental_regression_gate.py -q
```

结果：`26 passed`，仅有既有 PyPDF2 deprecation warning。

## 真实 stream 验证

真实页面同源接口：`/api/bidding/knowledge/search/stream`。本次未使用 mock；鉴权在测试环境中通过 `APP_AUTH_ENABLED=false APP_LOGIN_ENABLED=false` 关闭，检索和 embedding 仍走真实链路。

| 用例 | 结果 |
| --- | --- |
| CPVC/MPP 检验报告参数 | 正确返回报告编号、平均内径、环刚度，并引用结构化参数与报告图片来源 |
| Logo 与生产线/产品配图 | 正确召回官方 Logo、MPP 生产线和宣传彩页资产 |
| 中标通知书专项查询 | 正确返回国网天津市电力公司 2022 年第二次配网物资协议库存招标采购、招标编号 `0322AB`、包号 `157-保护管（CPVC和MPP） 包2_电缆保护管MPP和CPVC` |
| 合同或中标通知书复合查询 | 真实检索召回合同资产，但生成回答漏提已入库的中标通知书，记录为生成侧复合问题完整性待优化 |

## 剩余风险

1. 部分扫描 PDF 无可抽取文本，本次已作为正式整页图片资产入库，后续如需要全文问答应补 OCR。
2. 签名、手章、公章图片已做限制，不应自动插入正式标书；如项目需要签章页，应走人工确认和授权流程。
3. 复合问题“合同或中标通知书”的生成回答存在漏答，检索层能命中中标通知书；后续应优化回答合成阶段的多意图来源覆盖检查。

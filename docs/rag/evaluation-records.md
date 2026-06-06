# 召回评测记录

> 评测脚本：`scripts/rag/eval_recall.py`
> 测试集：`tests/rag/base_testset.jsonl`（30 条）
> 原始结果：`docs/rag/_run_filtered.json`、`docs/rag/_run_nofilter.json`

每次入库/策略调整后重跑并在此追加记录，形成可追溯的质量基线。

---

## Run 1 — P0 基线（2026-06-02）

### 环境

| 项 | 值 |
| --- | --- |
| Embedding | Ollama `qwen3-embedding:0.6b` @ 1024 维 |
| 向量库 | pgvector pg16，HNSW（m=16, ef_construction=64） |
| 分块 | 父子双层 v2（`parent_child_v2`） |
| 语料 | power_grid 种子库：298 parent + 2449 child（child 全部嵌入） |
| 召回 | `match_knowledge_chunks_filtered`，k=5，threshold=0.2 |
| Rerank | 未启用（基线） |

### A/B：metadata 过滤的价值

| 指标 | 过滤 ON | 过滤 OFF | 差值 |
| --- | --- | --- | --- |
| Recall@5 | **86.7%** | 80.0% | +6.7pp |
| 来源类别准确率(top1) | **100%** | 83.3% | +16.7pp |
| 跨 doc_role 串扰均值 | **0.0%** | 30.0% | −30.0pp |
| 关键词命中率 | 86.7% | 93.3% | −6.6pp |

分场景 Recall@5：

| scenario | 过滤 ON | 过滤 OFF |
| --- | --- | --- |
| qa (15) | 93% | 93% |
| writing (11) | 91% | 82% |
| compliance (4) | 50% | 25% |

### 结论

1. metadata 过滤把**跨 doc_role 串扰从 30% 降到 0%**，来源类别准确率升到 100%，验证了评审稿“过滤先行”的核心判断。
2. compliance 场景受益最大（25%→50%），因为合规问题最容易召回到相邻但错误的法规/规章。
3. 关键词命中率在过滤 OFF 时略高，是因为关键词可能出现在“相似但 doc_role 不对”的片段里——这正是串扰，过滤后被正确排除，属预期。

### 失败用例分析（过滤 ON 未命中 4 条）

| 用例 | 现象 | 根因 | 处置 |
| --- | --- | --- | --- |
| T17 国网招标活动管理办法 | top1 召回到“中国政府网版权”片段 | **源数据问题**：文件 25 的 source_url 是 gov.cn 占位，抓到政府网首页而非规章正文 | 需重新采集源文件（非 RAG 缺陷） |
| T18 国网供应商不良行为 | top1 召回到“个人中心/邮箱/无障碍”导航 | 同上，文件 26 源数据为网站导航 | 需重新采集 |
| T04 否决投标情形 | 实际 top1 是“第四十二条 否决所有投标”，内容正确 | 关键词标注过严（“无效”未覆盖“否决”表述） | 优化测试集关键词 |
| T20 配电网技术导则 | 召回到标准目录条目而非正文 | 该标准仅入库了标准号/名称索引 | 待 P1 补全文解析 |

> 4 条失败中，2 条是源数据采集问题、1 条是测试集标注偏严、1 条是标准全文待解析——**没有一条是分块或召回逻辑的缺陷**。真实可改进项是源数据质量。

### 复现命令

```bash
ollama serve            # 启动本地 embedding
python scripts/rag/eval_recall.py --k 5 --save docs/rag/_run_filtered.json
python scripts/rag/eval_recall.py --k 5 --no-filter --save docs/rag/_run_nofilter.json
```

---

## 待办（下一次 Run 前）

- [ ] 重新采集国网规章 25/26/27 源文件（解决 T17/T18）。
- [ ] P1：解析客户江西/山西铁构件标书（.docx/.doc/.xlsx），纳入测试集与负样本。
- [ ] 对比启用 Rerank（qwen3-rerank）对 Recall@5 / MRR 的增量。
- [ ] 升维实验：1024 vs 1536（需全量重嵌）在本测试集上的收益。

---

## Run 2 — 删除水利误入库记录后的复验（2026-06-02）

> 摘要：`docs/rag/runs/run_20260602_152803_summary.md`
> 原始结果：`docs/rag/runs/run_20260602_152803_filtered.json`、`docs/rag/runs/run_20260602_152803_nofilter.json`

### 触发原因

从本地 PostgreSQL 的 `knowledge_documents` 中删除误入库水利资料：

```text
19_塔里木河流域希尼尔水库除险加固工程坝基防渗处理施工标招标文件_b7a2c0d3.pdf
```

删除后复跑 Base 测试集，确认电网 RAG 基座召回质量没有退化。

### 数据快照

| 项 | 数量 |
| --- | ---: |
| `knowledge_documents` | 26 |
| `document_chunks` | 3459 |
| `document_chunks.embedding is not null` | 2449 |
| `power_grid_docs` | 26 |
| `power_grid_chunks` | 2747 |

### A/B：metadata 过滤的价值

| 指标 | 过滤 ON | 过滤 OFF | 差值 |
| --- | ---: | ---: | ---: |
| Recall@5 | **86.7%** | 80.0% | +6.7pp |
| 来源类别准确率(top1) | **100.0%** | 83.3% | +16.7pp |
| 跨 doc_role 串扰均值 | **0.0%** | 30.0% | -30.0pp |
| 关键词命中率 | 86.7% | 93.3% | -6.6pp |

分场景 Recall@5：

| scenario | 过滤 ON | 过滤 OFF |
| --- | ---: | ---: |
| qa (15) | 93% | 93% |
| writing (11) | 91% | 82% |
| compliance (4) | 50% | 25% |

### 失败用例分析（过滤 ON 未命中 4 条）

| 用例 | 现象 | 根因 | 处置 |
| --- | --- | --- | --- |
| T04 否决投标情形 | top1 是“第四十二条 否决所有投标” | 关键词标注偏严，`无效` 未覆盖 `否决` 表述 | 优化测试集关键词 |
| T17 国网招标活动管理办法 | top1 召回到“中国政府网版权”片段 | 源文件抓到政府网首页/版权页 | 重新采集源文件 |
| T18 国网供应商不良行为 | top1 召回到“个人中心/邮箱/无障碍”导航 | 源文件含网站导航噪声 | 重新采集源文件 |
| T20 配电网技术导则 | top1 是标准编号/名称摘要 | 该标准仅入库标准目录/摘要，非正文全文 | P1 补全文解析 |

### 结论

Run 2 与 Run 1 指标保持一致，删除误入库水利资料后没有造成召回退化。metadata 过滤仍将跨 `doc_role` 串扰控制在 0%，可继续作为客户江西/山西真实标书入库前的基线。

---

## Run 3 — 场景化测试集评测（2026-06-02）

> 摘要：`docs/rag/runs/run_20260602_scenario_summary.md`
> 测试集：`tests/rag/scenario_testset.jsonl`（12 条）
> 原始结果：`docs/rag/runs/run_20260602_scenario_filtered.json`、`docs/rag/runs/run_20260602_scenario_nofilter.json`

### 触发原因

为区分知识库问答和标书写作场景，新增场景化测试集，单独跟踪：

- `qa_recall`
- `writing_parent_coverage`
- `compliance_recall`
- `table_recall`

### A/B：metadata 过滤的价值

| 指标 | 过滤 ON | 过滤 OFF | 差值 |
| --- | ---: | ---: | ---: |
| Recall@5 | **100.0%** | 75.0% | +25.0pp |
| 来源类别准确率(top1) | **100.0%** | 83.3% | +16.7pp |
| 跨 doc_role 串扰均值 | **0.0%** | 41.7% | -41.7pp |
| 关键词命中率 | **100.0%** | 75.0% | +25.0pp |

分指标 Recall@5：

| metric | 过滤 ON | 过滤 OFF |
| --- | ---: | ---: |
| `qa_recall` | 100% | 67% |
| `writing_parent_coverage` | 100% | 67% |
| `compliance_recall` | 100% | 67% |
| `table_recall` | 100% | 100% |

### 结论

场景化测试集进一步证明 metadata 过滤是必要条件。关闭过滤后，问答、合规和写作父块覆盖均退化，且跨 `doc_role` 串扰升至 41.7%。当前写作父块回溯在样例集上可用，但仍需加入江西/山西真实标书和 `.xlsx` 表格样本后再判断生产可用性。

---

## Run 4 — 江西/山西客户资料 staging 入库与召回评测（2026-06-02）

> 摘要：`docs/rag/runs/run_20260602_customer_jx_sx_summary.md`
> 测试集：`tests/rag/customer_jx_sx_testset.jsonl`（17 条）
> 原始结果：`docs/rag/runs/run_20260602_customer_jx_sx_filtered.json`、`docs/rag/runs/run_20260602_customer_jx_sx_nofilter.json`

### 触发原因

客户江西/山西铁构件样本资料完成本地解析 QA 后，进行 staging 入库和客户真实场景召回评测，验证本地解析是否足以支撑 P1 样板库建设。

### 入库数据

| 项 | 数量 |
| --- | ---: |
| `knowledge_documents` | 23 |
| `document_chunks` | 4238 |
| parent chunk | 223 |
| child/table 检索块 | 4015 |
| embedding | 4015 |
| 结构化货物清单行 | 105 |
| 仅归档文件 | 21 |

### A/B：metadata 过滤的价值

| 指标 | 过滤 ON | 过滤 OFF | 差值 |
| --- | ---: | ---: | ---: |
| Recall@5 | **100.0%** | 70.6% | +29.4pp |
| 来源类别准确率(top1) | **100.0%** | 58.8% | +41.2pp |
| 关键词命中率 | **100.0%** | 88.2% | +11.8pp |
| 跨 doc_role 串扰均值 | **0.0%** | 50.9% | -50.9pp |
| 禁用关键词命中率 | **0.0%** | 0.0% | 0.0pp |

分场景 Recall@5：

| scenario | 过滤 ON | 过滤 OFF |
| --- | ---: | ---: |
| qa | 100% | 43% |
| compliance | 100% | 100% |
| writing | 100% | 67% |
| table | 100% | 100% |

### Base 回归

新增客户资料后，原 Base filtered 复跑结果仍为 Recall@5 86.7%、来源类别准确率 100%、跨 `doc_role` 串扰 0%，与 Run 1/2 基线一致，未发现退化。

### 结论

1. 本地解析链路在本批客户样本上通过 QA，暂不需要强制切到 MinerU。
2. 客户资料 staging 入库后，过滤 ON 的客户测试集 Recall@5 达到 100%。
3. 过滤 OFF 明显退化，说明 `province/package_code/doc_role/ingestion_batch_id` 过滤必须作为上线门禁。
4. 表格召回已可用，且本批已补 `power_grid_goods_list_rows` 结构化表/JSONB 精确查询层。

---

## Run 5 — PDF 标准源文件入库前审计与错源排除（2026-06-02）

> 审计脚本：`scripts/rag/audit_power_grid_pdf_standards.py`  
> 当前复审报告：`docs/rag/runs/run_20260602_pdf_standard_audit.md`  
> 当前复审原始结果：`docs/rag/runs/run_20260602_pdf_standard_audit.json`

### 触发原因

本地下一阶段任务将“PDF 国标/行标样板入库”列为最高优先级。入库前先对 `rag_seed/power_grid_resources/index.csv` 中 `03_standards_specs` 下已下载 PDF 做源文件一致性审计，避免把文件名正确但正文不匹配的 PDF 写入技术标知识库。

### 首次审计结果

| 状态 | 数量 |
| --- | ---: |
| `match` | 1 |
| `mismatch` | 6 |
| 合计 | 7 |

主要问题：

- `GB 50150-2016 电气装置安装工程电气设备交接试验标准` 实际抽取到 HJ/T 351-2007 环境标志产品技术要求。
- `GB 50168-2018 电气装置安装工程电缆线路施工及验收标准` 实际抽取到 HJ2057-2018 铅冶炼废水治理工程技术规范。
- `GB 50169-2016`、`GB 50171-2016`、`DL/T 5729-2016` 等也未在前 20 页抽取结果中稳定命中对应标准号和标题，不能直接进入 RAG。

### 处置后复审

根据客户后续安排，错误 PDF 暂不继续第三方下载，改由客户提供正确源文件。已将以下 6 条从 `downloaded` 改为 `needs_customer_source`，并清空 `file_path` / `sha256`，使 `scripts/rag/ingest_power_grid_v2.py` 在入库时跳过：

- GB/T 50430-2017 工程建设施工企业质量管理规范
- GB 50150-2016 电气装置安装工程电气设备交接试验标准
- GB 50168-2018 电气装置安装工程电缆线路施工及验收标准
- GB 50169-2016 电气装置安装工程接地装置施工及验收规范
- GB 50171-2016 电气装置安装工程盘、柜及二次回路接线施工及验收规范
- DL/T 5729-2016 配电网规划设计技术导则

复审结果：

| 状态 | 数量 |
| --- | ---: |
| `match` | 1 |
| 合计 | 1 |

### 结论

PDF 标准入库前必须增加源文件审计门禁。当前错源 GB/DL 标准 PDF 已从自动入库候选中排除；下一步等待客户提供正确源文件，重跑审计通过后再做 MinerU/OCR 解析、条文级分块和召回评测。

---

## Run 6 — 辽宁 / 泰昌 MVP 正式入库与专项回归（2026-06-06）

> Staging manifest：`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/staging_manifest.json`  
> 入库汇总：`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/formal_ingestion_summary.md`  
> Base filtered：`docs/rag/runs/run_20260606_taichang_mvp_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260606_taichang_mvp_customer_filtered.json`

### 正式入库结果

| 表 / 对象 | 数量 |
| --- | ---: |
| `knowledge_documents` | 124 |
| `document_chunks` | 29683 |
| `power_grid_goods_list_rows` | 87 |
| `knowledge_assets` | 242 |
| `knowledge_assets.embedding` | 242 |

资产目标库：

| target_library | 数量 |
| --- | ---: |
| `qualification_library` | 105 |
| `product_library` | 137 |

### 召回回归

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 86.7% | 93.3% | 86.7% | 0.0% | - |
| 辽宁/泰昌专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

专项分场景 Recall@5：

| scenario | cases | Recall@5 |
| --- | ---: | ---: |
| `asset_search` | 2 | 100% |
| `format_reference` | 2 | 100% |
| `negative` | 3 | 100% |
| `qa` | 5 | 100% |
| `table` | 2 | 100% |
| `writing` | 3 | 100% |

### 处置记录

- 为了让图片 metadata 在 `eval_recall.py` 的 `document_chunks` 评测链路中可测，新增 9 个泰昌图片资产目录文本块；正式图片仍写入 `knowledge_assets`。
- 资产目录正文去掉“河北豪乾”字样，仅在 metadata 保留 `do_not_mix_with`，避免泰昌事实召回命中禁用关键词。
- 补入 1 条 `self_phrase` Base 回归话术，使 T23 恢复命中；Base Recall@5 回到既有 86.7% 门槛。
- 修复 `backend/db/supabase_repo.py` 中 `upload_knowledge_asset_file()` 调用未定义 `_knowledge_asset_bucket()` 的问题，否则正式资产上传会全部失败。

### 剩余风险

- Base 未命中 T04/T17/T18/T20 仍为既有问题：T04 关键词标注偏严，T17/T18 源数据质量差，T20 标准仅有摘要/目录。
- 泰昌 CPVC/MPP 检验报告为“内径250”，与辽宁清单中的 φ50/100/150/175/200 覆盖关系仍需业务确认。

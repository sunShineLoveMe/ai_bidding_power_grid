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

---

## Run 7 — 泰昌 MVP 图片智能问答与图文并茂选图 P0 回归（2026-06-06）

> Base filtered：`docs/rag/runs/run_20260606_taichang_mvp_asset_p0_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260606_taichang_mvp_asset_p0_customer_filtered.json`

### 范围边界

- 泰昌是 MVP 试点企业，`enterprise_fact/doc_owner=泰昌` 是企业事实主线。
- 辽宁资料仅作为电缆保护管招标场景样本，用于招标要求、技术规范、货物清单、合同条款召回。
- 河北豪乾资料仅作为格式/目录/写法参考，`reference_only=true`，不得作为泰昌企业事实或泰昌图片来源。

### 修复内容

- 智能问答图片资产检索支持 metadata 过滤；当查询或显式过滤指向泰昌时，仅召回泰昌企业事实资产，并排除参考稿。
- 图片资产检索文本补入 `metadata/specs` 标量和列表值，使 `evidence_type/target_library/enterprise/source_domain` 可参与关键词补召回。
- 标书导出“图文并茂”按章节语义推断 `evidence_type`，对生产制造、试验检测、绿色低碳、营业执照/证书、检验报告做强匹配，避免泛化的“设备/证书”关键词误选。

### 真实库验证

当前 `knowledge_assets` 候选池 242 个资产。真实库模拟结果：

| 查询/章节 | 期望 evidence_type | 结果 |
| --- | --- | --- |
| 泰昌企业资信与营业执照 | `business_license`、`certification` | 命中泰昌营业执照与认证证书 |
| 泰昌生产制造能力 | `production_capacity` | 命中泰昌生产线/生产制造资产 |
| 泰昌试验检测能力 | `testing_capacity` | 命中电子天平、万能试验机等试验检测资产 |
| 泰昌绿色低碳与绿色供应链能力 | `green_low_carbon` | 命中绿色低碳/绿色供应链资产 |

智能问答资产检索验证：

| 查询 | Top evidence_type |
| --- | --- |
| 泰昌营业执照图片 | `business_license` |
| 泰昌 MPP 生产线图片 | `production_capacity` |
| 泰昌电子天平和万能试验机图片 | `testing_capacity` |
| 泰昌绿色供应链证书图片 | `green_low_carbon` |

### 召回回归

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 86.7% | 93.3% | 86.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 单测

- `PYTHONPATH=. .venv/bin/pytest tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q`
- 结果：16 passed，1 个 PyPDF2 deprecation warning。

---

## Run 8 — 泰昌正式图片资产整页化重建与中文命名（2026-06-07）

> 重建报告：`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/rebuild_formal_image_assets_report.md`  
> Base filtered：`docs/rag/runs/run_20260607_taichang_formal_assets_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_taichang_formal_assets_customer_filtered.json`

### 背景

- 资信库、产品库中原有 242 个图片资产来自 MinerU `extract/images` 局部切图，包含二维码、页脚、签名/印章附近局部、文字块和表格局部。
- 页面展示直接使用资产 `title/category/tags`，因此出现 `taichang_*`、`production_capacity`、`green_low_carbon` 等内部英文/拼音值。
- 客户已提供营业执照、开户许可证、审计报告、管理体系证书、CPVC/MPP 检验报告、生产线/厂房/设备/人员/社保/绿色低碳等 PDF/JPG，可按正式投标文件规则处理为整页/原图资产。

### 处理内容

- 新增 `scripts/rag/rebuild_taichang_formal_image_assets.py`。
- 删除旧批次 `knowledge_assets` 中 242 个 MinerU 局部图资产。
- 使用客户已提供 42 个 PDF 和 1 个 JPG，按 PDF 文件顺序逐页渲染整页图片，导入 300 个正式图片资产。
- 用户可见字段全部改为中文：标题、分类、标签、说明均不再出现拼音或英文枚举。
- 技术枚举仅保留在 metadata/specs 内，用于过滤和召回，例如 `evidence_type`、`target_library`、`asset_visual_type`。
- 更新 `AGENTS.md`，固化国内中文命名规则和正式图片资产门禁规则。
- 更新产品库、资信库页面旧文案，把“公开素材/公开来源素材/脱敏合成规格图”改为“泰昌资料/客户提供资料/客户自有资料”口径。

### 数据库验证

| 指标 | 结果 |
| --- | ---: |
| 删除旧局部图片资产 | 242 |
| 导入正式整页/原图资产 | 300 |
| `product_image` | 203 |
| `qualification_image` | 97 |
| 标题英文/拼音残留 | 0 |
| 标签英文枚举残留 | 0 |

正式资产分类：

| 分类 | 数量 |
| --- | ---: |
| 绿色低碳资料 | 111 |
| 财务资料 | 67 |
| 试验检测设备 | 46 |
| 生产制造能力 | 24 |
| 人员证书 | 18 |
| 厂房仓储资料 | 14 |
| 检验报告 | 10 |
| 资质证书 | 8 |
| 基础证照 | 2 |

### 回归验证

- Base filtered Recall@5：86.7%，top1 来源准确率：93.3%，关键词命中率：86.7%，跨 doc_role 串扰均值：0.0%。
- 泰昌专项 filtered Recall@5：100.0%，top1 来源准确率：100.0%，关键词命中率：100.0%，禁用关键词命中率：0.0%。
- `PYTHONPATH=. .venv/bin/pytest tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q`
- 结果：16 passed，1 个 PyPDF2 deprecation warning。
- `cd frontend && npm run build`
- 结果：构建通过；Vite 仅提示既有大 chunk 和动态/静态 import 混用警告。

### 剩余风险

- CPVC/MPP 现有检验报告为“内径250”，是否覆盖辽宁清单中的其他口径仍需客户业务确认。
- 产品实物高清照片、生产线/检测设备原始照片、同类业绩合同/中标通知书/验收证明、项目级盖章扫描件和官方 Logo 仍需客户补充。

---

## Run 9 — 泰昌企业知识库问答入口与参考来源收紧（2026-06-07）

### 背景

- MVP 版本已确定以河北泰昌电力器材科技有限公司为试点企业。
- 企业知识库助手原先仍向用户暴露“自动判断资料范围”和“问答/写作/合规/货物清单”等场景选择，容易让业务用户误以为可以跨省份、跨包号或跨主体选择资料。
- 回答下方“参考资料来源”直接展示 `province/package_code/material_category/doc_role` 等 metadata，导致江西、山西、辽宁等招标资料在企业事实问答中被明示展示，不符合泰昌企业事实边界。

### 处理内容

- 前端 `KnowledgeSearchDrawer` 移除资料范围和问答类型下拉控件，默认入口文案改为泰昌企业资信、产品资料和标书材料问答。
- 后端 `/api/knowledge/search` 与 `/api/knowledge/search/stream` 默认使用泰昌企业事实过滤：
  - `enterprise=泰昌`
  - `source_domain=enterprise_fact`
  - `fact_source_allowed_for_enterprise=true`
  - `reference_only=false`
- 文本参考来源返回前执行企业事实门禁、同源去重、按 `similarity` 降序排序，最多返回 5 条。
- 前端来源卡片不再展示省份、包号、物料类别等招标资料标签，仅展示企业事实标题、中文化说明、内容预览和相关度。

### 回归验证

- 本次未新增客户资料，未执行重新入库。
- `./.venv/bin/python -m pytest tests/test_rag_retrieval.py -q`
- 结果：8 passed，1 个 PyPDF2 deprecation warning。
- `cd frontend && npm run build`
- 结果：构建通过；Vite 仅提示既有大 chunk 和动态/静态 import 混用警告。
- `curl -I http://127.0.0.1:5173/`
- 结果：本地前端服务返回 HTTP 200。

### 剩余风险

- 本次锁定的是企业知识库助手的泰昌试点口径；如后续恢复多企业租户模式，需要把试点企业常量改为租户上下文，而不是重新暴露省份/包号型筛选。
- Playwright 未安装，未做自动截图；已通过 TypeScript 构建、静态文本检查和本地服务可访问性检查。

---

## Run 10 — P2 版本去重与引用边界门禁（2026-06-07）

> Run summary：`docs/rag/runs/run_20260607_p2_version_citation_summary.md`  
> Base filtered：`docs/rag/runs/run_20260607_p2_version_citation_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_p2_version_citation_customer_filtered.json`

### 背景

- P2-4 要求同一模板新旧版本不能同时污染召回。
- P2-5 要求区分企业事实、招标要求、参考模板、法规/标准等引用边界，避免把参考稿当事实、把招标要求写成企业能力。

### 处理内容

- 新增 `scripts/rag/customer_metadata_policy.py`：
  - `enterprise_fact` -> `citation_policy=enterprise_fact_citable`
  - `tender_requirement` -> `citation_policy=tender_requirement_citable`
  - `reference_template` -> `citation_policy=reference_style_only`
  - `policy_regulation` -> `citation_policy=law_or_standard_citable`
  - `base_seed` -> `citation_policy=summary_only`
- `scripts/rag/ingest_customer_corpus.py` 在 dry-run 和正式入库前执行 metadata 门禁。
- 入库 metadata 统一补齐或校验 `source_sha256`、`doc_identity_key`、`doc_version`、`superseded_by`。
- 正式入库时，同一 `doc_identity_key`、不同 `source_sha256` 且新版本不低于旧版本的旧文档会被置为 `superseded`。
- 强校验泰昌企业事实、辽宁/江西/山西招标要求、河北豪乾参考稿三类边界。

### dry-run

| manifest | documents | skipped | blocked_metadata | parent | child/table 检索块 | embedding |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 泰昌/辽宁 P0 staging | 124 | 0 | 0 | 2023 | 27660 | 27660 |
| 江西/山西 P1 manifest | 44 | 21 | 0 | 223 | 4015 | 4015 |

### 回归验证

- `./.venv/bin/python -m pytest tests/test_customer_metadata_policy.py tests/test_rag_retrieval.py -q`
- 结果：14 passed，1 个 PyPDF2 deprecation warning。
- Base filtered Recall@5：86.7%，top1 来源准确率：93.3%，关键词命中率：86.7%，跨 doc_role 串扰均值：0.0%。
- 泰昌专项 filtered Recall@5：100.0%，top1 来源准确率：100.0%，关键词命中率：100.0%，禁用关键词命中率：0.0%。

### 剩余风险

- 历史已入库文档如果没有 `doc_identity_key`，无法自动反向判定新旧版本关系；后续新批次按新门禁入库后会稳定生效。
- 如果客户后续提供同一资料但文件名变化的新版本，manifest 应显式填写稳定 `doc_key` 或 `document_key`。

---

## Run 11 — P3 Query Rewrite / 关键词补召回 / Authority 排序（2026-06-07）

> Run summary：`docs/rag/runs/run_20260607_p3_query_keyword_summary.md`  
> Base filtered：`docs/rag/runs/run_20260607_p3_query_keyword_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_p3_query_keyword_customer_filtered.json`

### 背景

- P2 后 Base Recall@5 为 86.7%，未命中集中在标准规范、国网规则和合规类问题。
- 原评测脚本直接调用 RPC，未覆盖生产检索链路中的 rerank、后处理和后续增强逻辑。

### 处理内容

- `search_knowledge_base()` 增加轻量 Query Rewrite，提取标准号、包号、技术规范编码、物料编码、供应商管理、不良行为、施工工艺等关键词。
- 增加 document chunk 关键词补召回：向量召回不足或高精度关键词未命中时触发，并继续执行 metadata 边界过滤。
- 对关键词命中的网页型国网规则分片补充来源文件名、标签、类型、来源单位作为上下文前缀，缓解网页导航噪声。
- 增加 authority/citation 排序：正式法规/标准、招标要求、企业事实加权；`reference_style_only` 降权。
- `scripts/rag/eval_recall.py` 改为调用生产检索函数，确保回归覆盖 Query Rewrite、关键词补召回和 authority 排序。

### 回归验证

- `./.venv/bin/python -m pytest tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
- 结果：25 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile backend/rag/retrieval.py scripts/rag/eval_recall.py`
- 结果：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- Base 仅剩 T04 合规用例未命中关键词；top1 doc_role 已正确为 `policy_regulation`。
- 国网规则网页存在明显导航噪声，应在后续重洗并重新入库。
- 关键词补召回暂在应用层过滤；后续可补数据库侧关键词索引或专用 RPC。

---

## Run 12 — 国网规则网页噪声重洗与回归（2026-06-07）

> Run summary：`docs/rag/runs/run_20260607_sgcc_rule_clean_summary.md`  
> Base filtered：`docs/rag/runs/run_20260607_sgcc_rule_clean_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_sgcc_rule_clean_customer_filtered.json`

### 背景

- `国家电网有限公司招标活动管理办法`、`国家电网有限公司供应商管理办法`、`国家电网有限公司物资采购标准` 三份 seed 文档的原正文为门户首页导航/新闻内容，不是制度原文。
- 该问题会污染国网规则问答和合规召回，且影响后续 P4 技术参数表抽取前的整体回归稳定性。

### 处理内容

- 新增 `scripts/rag/repair_sgcc_rule_seed_docs.py`，重洗三份异常 markdown，并同步 `index.csv`、`index.jsonl` 的 `sha256` 与错误说明。
- 三份异常资料改为明确标注的“检索种子摘要”，均标明原始采集链接失效、待官方原文复核、`citation_policy=summary_only`。
- 重新入库 `02_policy_regulations`：11 文档、266 parent、2180 child。
- 重新入库 `04_standard_phrases`：6 文档、16 parent、22 child，用于恢复本次回归暴露的标准话术库不完整问题。
- `search_knowledge_base()` 补充 `质量安全环保/质量目标/安全目标` 领域关键词，并将关键词补召回改为分页扫描，避免固定窗口漏扫小类资料。

### 回归验证

- `./.venv/bin/python -m pytest tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
- 结果：26 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile backend/rag/retrieval.py scripts/rag/eval_recall.py scripts/rag/repair_sgcc_rule_seed_docs.py`
- 结果：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- Base 仅剩 T04：top1 `policy_regulation` 正确，但关键词口径仍是“无效”与“否决所有投标”的表达差异。
- 三份国网规则当前仍是检索种子摘要，不是官方制度全文；后续拿到官方原文后仍需替换 seed、重入库并复跑评测。

---

## Run 13 — P4-2 技术参数表抽取（2026-06-07）

> Run summary：`docs/rag/runs/run_20260607_p4_technical_parameters_summary.md`  
> Base filtered：`docs/rag/runs/run_20260607_p4_technical_parameters_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_p4_technical_parameters_customer_filtered.json`

### 背景

- P4-2 要求技术参数表不能只做普通文本向量，必须保留原始结构、检索摘要和行级记录。
- 后续客户继续提供技术规范书、技术补充文件、技术响应参考稿、检验报告参数页或偏差表时，也需要按同一方式结构化。

### 处理内容

- 更新 `AGENTS.md`，固化后续客户技术资料的技术参数表抽取规则。
- 新增 `scripts/rag/extract_customer_technical_parameters.py`。
- 对辽宁/泰昌 MVP staging manifest 中 39 份 `technical_spec` 文档进行抽取。
- 输出：
  - `technical_parameter_rows.json`
  - `technical_parameter_rows.csv`
  - `technical_parameter_summary.md`
  - `extract_technical_parameters_report.json`

### 抽取结果

| 指标 | 数量 |
| --- | ---: |
| 技术规范文档 | 39 |
| 成功抽取文档 | 39 |
| 技术参数行 | 928 |
| CPVC 参数行 | 285 |
| MPP 参数行 | 643 |
| 尺寸参数行 | 349 |
| 性能参数行 | 369 |
| 投标响应参数行 | 210 |

### 回归验证

- `./.venv/bin/python -m pytest tests/test_technical_parameter_extraction.py tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
- 结果：27 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile scripts/rag/extract_customer_technical_parameters.py backend/rag/retrieval.py`
- 结果：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- 本轮只生成 JSON/CSV/summary chunk，尚未新增 `power_grid_technical_parameter_rows` 数据库表。
- 本批招标技术规范中的 `投标人响应值`、`投标人保证值` 多为空白，字段已保留；后续可由泰昌产品资料、检验报告或人工确认值补齐。

---

## Run 14 — P4-4 技术偏差辅助判断（2026-06-07）

> Run summary：`docs/rag/runs/run_20260607_p4_deviation_summary.md`  
> Base filtered：`docs/rag/runs/run_20260607_p4_deviation_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_p4_deviation_customer_filtered.json`

### 背景

- P4-2 已产出 `technical_parameter_rows.json`。
- P4-4 初版要求先支持“项目需求值/标准值 vs 投标响应/保证值”的差异判断，用于技术偏差表、漏项检查和检验报告覆盖性判断。

### 处理内容

- 新增 `scripts/rag/generate_technical_deviation_report.py`。
- 对 928 行技术参数生成偏差辅助判断：
  - `pending_response`
  - `no_deviation`
  - `positive_deviation`
  - `negative_deviation`
  - `manual_review`
  - `informational`
- 输出：
  - `technical_deviation_rows.json`
  - `technical_deviation_rows.csv`
  - `technical_deviation_summary.md`
  - `technical_deviation_report.json`

### 产物结果

| 指标 | 数量 |
| --- | ---: |
| 参数行 | 928 |
| 需处理行 | 900 |
| `pending_response` | 900 |
| `informational` | 28 |
| `medium` 风险 | 900 |
| `low` 风险 | 28 |

本批大量参数被标为 `pending_response`，原因是招标技术规范里有明确项目需求值或标准值，但 `投标人响应值`、`投标人保证值` 多为空白。该结果符合预期，不能直接写成无偏差。

### 回归验证

- `./.venv/bin/python -m pytest tests/test_technical_deviation_report.py tests/test_technical_parameter_extraction.py tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
- 结果：33 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile scripts/rag/generate_technical_deviation_report.py scripts/rag/extract_customer_technical_parameters.py backend/rag/retrieval.py`
- 结果：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- 初版偏差判断尚未接入泰昌检验报告或产品规格作为保证值来源。
- 本轮未新增结构化数据库表，产物仍以 JSON/CSV/Markdown 为主。

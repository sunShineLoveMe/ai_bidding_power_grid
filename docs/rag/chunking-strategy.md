# 父子双层分块策略（实现）

> 实现：`backend/rag/chunking.py`
> 入库：`scripts/rag/ingest_power_grid_v2.py`
> 方案依据：`feishu/docs/国家电网物资协议库存标书RAG技术路线评审稿.md` §6

## 1. 为什么父子双层

三个消费场景对 chunk 的诉求冲突：

| 场景 | 优化目标 | 理想 chunk |
| --- | --- | --- |
| 智能问答 | precision | 子块：条/款级，小而准 |
| 写作依据 | coverage + 连贯上下文 | 父块：章/节级 |
| 合规检查 | recall | 规则项，逐条 |

一份资料切一次，产出两层：

- **child（子块）**：参与向量召回、问答、合规。`embedding` 非空。
- **parent（父块）**：完整章/节上下文，写作回溯用。`embedding` 为空，**不参与向量召回**（召回 RPC 过滤 `embedding is not null`），因此不污染检索。
- child 通过 `metadata.parent_index` 指向同文档内的 parent（同 `document_id` + `chunk_index`）。

## 2. 按 doc_role 的切分规则

| doc_role | parent | child | block_type |
| --- | --- | --- | --- |
| `policy_regulation` / `sgcc_rule` / `contract_*` | 第X章 | **第X条** | clause |
| `standard_spec` | 章节 | 条文 | clause |
| `tender_notice` / `main_tender_file` | 全文/段标题 | 编号业务段（1. / （一） / 一、） | clause |
| `bid_instructions` | 全文 | 每条风险 | rule |
| `self_phrase` / 其它 | markdown 小标题段 | 段落 | paragraph |

切分硬约束：

- 不用统一固定长度作主策略；定长仅作兜底，且按句子边界（`。；！？` 换行）回退，**绝不从字中间截断**。
- 子块目标 ≤600 字，父块 ≤4000 字（可调）。
- 单条超长时按句子兜底切，并在后续片段补回条号前缀，保证可溯源。

## 3. 清洗（入库前强制）

`clean_text()` 处理：

- 删除采集脚本写入的元信息整行（`- 来源：` / `- 原始链接：` / `- 采集时间：`）。
- 删除网页导航噪声（“您当前位置/正文”“首页 | 登录/注册”“Languages English…”“大 中 小”“发布时间：”“更多>>”等）。
- 折叠多余空白与空行。

## 4. 写入的 metadata（评审稿 §7 落地子集）

每个 chunk 写入：

```text
chunk_layer        child | parent
parent_index       child 指向 parent 的 chunk_index
block_type         clause | rule | section | paragraph
doc_role           policy_regulation | sgcc_rule | tender_notice | standard_spec | self_phrase ...
authority_level    law > regulation > national_standard > industry_standard > sgcc_rule > tender_file > template
citation_policy    summary_only | internal_reference_only | direct_quote_allowed
source_category    01_tender_documents ...
source_org / source_file / tags
content_sha256     去重/幂等用
seed_corpus        power_grid_resources
chunker            parent_child_v2
```

`authority_level` 与 `citation_policy` 的映射见 `ingest_power_grid_v2.py` 的 `AUTHORITY_BY_DOC_TYPE` / `CITATION_BY_AUTHORITY`，用于写作场景的权威排序与引用边界控制。

## 5. 实测分块产出（power_grid 种子库）

| 指标 | v1（旧，统一 1800 字） | v2（父子分块） |
| --- | --- | --- |
| child chunk 数 | 279 | 2449 |
| parent chunk 数 | 0 | 298 |
| 法规条文是否按“条”切 | 否（盲切，条文被截断） | 是 |
| 网页导航噪声 | 入库 | 已清洗 |

法规示例（招标投标法）：v2 切出 18 个 parent（章）+ 210 个 child（条），child 平均 113 字、每条自洽可独立回答。

2026-06-02 客户资料解析准备后，分块器补充了长文档 parent 拆分逻辑，避免一份大招标文件只产生一个 parent。当前代码 dry-run：

| 语料 | parent | child | 说明 |
| --- | ---: | ---: | --- |
| power_grid 种子库 dry-run | 323 | 2444 | 仅 dry-run，数据库仍保持 Run 1/2 评测时的 298 parent / 2449 child，待正式重入库后再更新召回基线 |
| 江西/山西客户资料 dry-run | 233 | 3942 | 21 个文本文件，另有 2 个 `.xlsx` 表格文件 107 行走结构化 |

## 6. 已知数据问题（非分块缺陷）

部分国网规章源文件（`25/26/27`，source_url 为 `gov.cn` 占位）实际抓取到的是政府网首页新闻，而非规章正文。分块器已尽量清洗，但**源数据本身需要重新采集**。已在评测中作为失败用例暴露（T17/T18），见 `evaluation-records.md`。

## 7. 复跑

```bash
# 干跑（只统计父子数与 doc_role 分类）
python scripts/rag/ingest_power_grid_v2.py --dry-run

# 入库（需 Ollama 或百炼可用）
python scripts/rag/ingest_power_grid_v2.py
```

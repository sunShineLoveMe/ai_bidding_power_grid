# 本地下一阶段任务清单（云环境到位前）

> 制定日期：2026-06-02  
> 修订日期：2026-06-03  
> 适用前提：**阿里云测试环境账号未到位；客户完整/正式私有资料未到位，但已有江西/山西样本资料完成本地 staging 解析、入库与召回评测。**  
> 目标：在不依赖云资源的前提下，优先补齐技术标知识库、正文生成可靠性和回归保护，让后续客户资料与云资源到位后能高质量接入。  
> 依据：`docs/development/maturity-assessment.md`、`docs/rag/customer-corpus-parse-runs.md`、`docs/rag/evaluation-records.md`、当前代码实际。

---

## 0. 排序原则

1. 先补成熟度报告中最高的本地可控风险：关键 PDF 标准缺口、章节正文未异步化、全链路回归不足。
2. 数据质量优先于检索算法：先修复缺失/污染语料，再做混合检索和 rerank 增益量化。
3. 已有能力先产品化/通用化，不重复按“从零开发”排期。例如 `.doc/.xlsx` 解析脚本已跑通，下一步是接入正式知识库流程。
4. 工程债穿插处理，不抢占影响客户测试质量和演示稳定性的任务。
5. 云上联调、HTTPS/SLS 真实采集、客户完整私有资料入库等依赖外部条件的任务显式排除。

---

## 1. 当前本地可做任务池

| 优先级 | 任务 | 为什么现在做 | 主要验收 |
| --- | --- | --- | --- |
| P0 | PDF 国标/行标样板入库与批量方案 | 技术标知识库最大内容缺口，直接影响生成质量 | 客户提供正确标准 PDF 后，至少 3-5 份样板可召回正文条文；有 token 时批量完成 |
| P0 | 全链路 HTTP 冒烟补全 | 为正文 Celery 化和后续改造建立回归护栏 | 一条命令覆盖上传、解析、解读、大纲、正文、合规、导出；支持 mock LLM/MinerU |
| P0 | 章节正文生成迁入 Celery | 已完成首版迁移，后续维护任务状态恢复和批量体验 | 关闭浏览器后任务继续执行，重连/轮询可拿到结果，失败保稿不回归 |
| P1 | 重采污染的国网规章种子文件 | Base 评测 T17/T18 暴露源文件抓到网站导航/首页 | T17/T18 召回规章正文而非 gov.cn 导航页 |
| P1 | `.doc/.xlsx` 解析链路通用化 | 客户样本脚本已跑通，但尚未成为通用上传/入库能力 | 新批次 `.doc/.xlsx` 可通过统一入口生成 manifest、文本/表格产物和结构化行 |
| P1 | Base 测试集扩充 + 负样本 + MRR | 混合检索和 rerank 需要稳定评估基线 | 40-50 条测试集，含 `must_not_include`，输出 MRR/串扰率 |
| P1 | 混合检索 BM25/关键词 + 向量 | 标准号、包号、条号等精确符号仅靠向量可能漏召回 | 标准号/包号查询相对纯向量 Recall/MRR 有量化提升 |
| P2 | Rerank 增益量化 | 当前已接入 rerank，但缺少 A/B 数据 | `evaluation-records.md` 追加有/无 rerank 的 Recall/MRR/延迟 |
| P2 | 父子分块器健壮性补强 | 当前主链路可用，但合同阿拉伯条号、表格隔离仍可增强 | 新增 chunking 单测，合同 `1.1/1.1.1` 层级不被截断 |
| P2 | Alembic 增量迁移能力 | 当前只有 baseline，后续改表仍偏手工 | 能生成并回滚一个示例 revision |
| P2 | 前端测试框架/拆包/组件化 | 工程治理必要，但不阻塞近期客户测试质量 | `npm test` 可跑；主 chunk 下降；巨型组件逐步拆分 |

---

## A. RAG 基座数据工程

### A1. PDF 国标/行标入库（最高优先）🔴

- **现状**：15 份 GB/DL 标准 PDF 被跳过；GB 50150、GB 50168、GB 50169、DL/T 5729 等正是技术标标准响应的关键依据。当前 Base 评测中 T20 等用例只能召回标准目录/摘要，无法召回正文条文。
- **2026-06-02 本地门禁**：已新增 `scripts/rag/audit_power_grid_pdf_standards.py` 并生成 `docs/rag/runs/run_20260602_pdf_standard_audit.md`。审计结果显示 7 份标准类 PDF 中 1 份目录 PDF可用、6 份标准 PDF 与标题不匹配或抽取内容不可信，不得直接入库。已将 6 条索引状态改为 `needs_customer_source`，后续入库脚本会跳过。
- **客户需提供/确认的 PDF 清单**：
  - GB/T 50430-2017 工程建设施工企业质量管理规范
  - GB 50150-2016 电气装置安装工程电气设备交接试验标准
  - GB 50168-2018 电气装置安装工程电缆线路施工及验收标准
  - GB 50169-2016 电气装置安装工程接地装置施工及验收规范
  - GB 50171-2016 电气装置安装工程盘、柜及二次回路接线施工及验收规范（年份需客户确认）
  - DL/T 5729-2016 配电网规划设计技术导则
- **任务**：
  - 确认 `MINERU_API_TOKEN` 是否可用。
  - 客户提供正确 PDF 后，替换或新增到 `03_standards_specs`，并重新跑 PDF 审计。
  - 有 token：优先批量解析 GB 50150/50168/50169/DL/T 5729 等标准，按条文/章节粒度入库。
  - 无 token：先挑 3-5 份关键标准做本地 OCR/人工摘要样板，产出可复用的条文级分块规范，其余标记为待 token。
  - 对标准全文、摘要、引用边界做 metadata 标注，避免后续生成时误把标准目录当正文依据。
- **验收**：PDF 审计先通过；技术类 Base 用例能召回到标准正文条文；`docs/rag/evaluation-records.md` 追加本轮评测记录。
- **依赖**：MinerU token 可提升效率；无 token 时仍可先做样板。

### A2. 重采污染的国网规章种子文件 🟡

- **现状**：`25/26/27` 国网规章源 URL 为 `gov.cn` 占位，实际抓到政府网首页/导航，而非规章正文。Base 评测 T17/T18 已暴露。
- **任务**：重新采集《国网招标活动管理办法》《供应商管理办法》《物资采购标准》等正文，清理旧污染内容，重跑 v2 入库。
- **验收**：T17/T18 在 Base 评测中召回到规章正文而非网站导航。

### A3. `.doc/.xlsx` 解析链路通用化 🟡

- **现状**：`backend/rag/vector_store.py:read_file_content` 仍只支持 `.docx`/`.pdf`/文本；但客户江西/山西样本已通过 `scripts/rag/prepare_customer_corpus.py` 完成 `.doc` LibreOffice 转 `.docx`、`.xlsx` openpyxl 结构化解析，`power_grid_goods_list_rows` 已有结构化行表。该能力已在脚本侧跑通，但还不是通用知识库上传/入库主流程。
- **任务**：
  - 把 `prepare_customer_corpus.py` 中 `.doc`/`.xlsx` 解析能力沉淀成可复用模块或正式导入命令。
  - `.doc`：继续采用 LibreOffice headless 转 `.docx` 后 mammoth 抽取。
  - `.xlsx`：保留原始结构、检索摘要、行级记录三形态；结构化行写 `power_grid_goods_list_rows`，不简单压成长文本向量化。
  - 为新批次资料输出 manifest、QA 报告、入库报告，保留失败文件 `needs_review` 状态。
- **验收**：任意新批次 `.doc/.xlsx` 可通过统一入口完成解析、QA、入库和结构化表写入；不再只依赖江西/山西专用脚本。

### A4. Base 测试集扩充 + 负样本 + MRR 🟡

- **现状**：Base 测试集 30 条，正向样本为主；客户测试集已有 `must_not_include`，但 Base 还缺少跨批次/跨省份串扰负样本。
- **任务**：
  - Base 扩到 40-50 条，覆盖问答、写作、合规、表格、标准号、包号、条号等场景。
  - 引入 `must_not_include`，单独统计 doc_role/省份/批次串扰率。
  - `eval_recall.py` 增加 MRR 指标。
- **验收**：评测输出含 Recall@5、MRR、关键词命中率、串扰率；负样本用例可复现。

### A5. 父子分块器健壮性补强 🟢

- **任务**：
  - 给 `chunking.py` 补单元测试：条文切分、表格隔离、噪声清洗、兜底定长。
  - 补合同条款 `1.1/1.1.1` 层级切分。
  - 明确表格 chunk 三形态与普通文本 chunk 的边界。
- **验收**：新增 chunking 单测全绿；合同类文件切分不再被截断。

---

## B. 可靠性与回归保护

### B1. 全链路 HTTP 冒烟补全 🔴

- **现状**：`scripts/smoke_key_flow.py` 已有最小冒烟，但尚未覆盖合规检查，也缺少适合本地 mock LLM/MinerU 的稳定回归模式。
- **2026-06-02 进展**：已把规则合规检查接入 `scripts/smoke_key_flow.py`，主链路现在覆盖上传 → 解析 → 解读 → 大纲 → 正文 → 合规 → DOCX 导出；新增 `--skip-compliance` 跳过开关和脚本单测。脚本已增加 `/api/ready` 前置探测、实时阶段输出、Markdown/JSON 报告落盘、`--require-mineru` PDF 解析强校验开关。
- **2026-06-02 真实冒烟状态**：首次真实脚本因未登录被 401 拦截；注册本地 smoke 账号后重跑，因未启动 Celery worker 卡在 `wait_parse_completed`。已补充 README 启动说明并启动 worker，`/api/ready` 显示 DB/Redis/模型/存储/Celery 全部 ok。随后使用 PDF 样例 + `--require-mineru` 完成真实全链路冒烟：上传 → MinerU 解析/落库 → 解读 → AI 报告 → 大纲 → 章节正文 → 合规 → DOCX 导出全部通过。报告：`docs/development/runs/run_20260602_224815_http_smoke_passed.md`。
- **2026-06-03 真实冒烟状态**：B2 迁移后，使用 PDF 样例 + `--require-mineru` 再次完成真实全链路冒烟；章节正文阶段已改为创建后端任务并由 Celery worker 执行，状态从 `queued` → `running` → `completed`，最终合规检查和 DOCX 导出通过。报告：`docs/development/runs/run_20260603_104020_http_smoke_passed.md`。
- **任务**：
  - 扩展/维护上传 → 解析 → 解读 → 大纲 → 正文 → 合规 → DOCX 导出的完整 HTTP 级回归。
  - 真实全链路优先：后端、前端、Celery worker、LLM、MinerU 可用时直接跑真实冒烟；mock 模式仅作为 CI/无外部依赖时的后备。
  - 输出清晰的阶段耗时、失败阶段和关键 ID。
- **验收**：一条命令跑通主链路，后续可挂 CI 或云上部署后直接复验。

### B2. 章节正文生成迁入 Celery ✅

- **2026-06-03 进展**：
  - 新增 `backend.tasks.section_tasks.run_bid_section_generation`，任务名 `bid.sections.generate_task`，复用 `bid_generation_tasks` 记录章节任务状态。
  - 新增 `backend/services/section_generation.py`，统一正文生成、图片拼接、落库和失败保稿逻辑，避免 HTTP 与 Celery 两套实现分叉。
  - `POST /api/bidding/interpretations/<project_id>/section-generation-tasks` 默认自动投递 Celery；新增任务详情查询接口，前端单章/批量生成改为“创建任务 + 轮询状态 + 完成后刷新章节”。
  - `scripts/smoke_key_flow.py` 的正文阶段已改为走章节任务接口，不再依赖浏览器 SSE 长连接。
- **2026-06-03 实时体验修正**：
  - 客户要求保留原先前端“生成中实时展示正文”的成交体验。当前方案调整为 Celery worker 在生成过程中按微批 chunk 回写 `generated_content`、`chunk_seq`、`chunk_events` 到 `bid_generation_tasks.items`。
  - 前端轮询任务时不只更新状态，还会把 `generated_content` 实时写回当前章节编辑器；页面刷新或网络重连后，可通过 latest task 恢复中间已生成正文。
  - 单章生成增加“停止生成”入口；取消任务会写入 `cancelled/stopped` 状态，worker 在 chunk/微批边界检查取消信号并停止后续生成，已生成内容保留在编辑器中。
  - 当前采用 600ms HTTP 轮询 + 约 400ms/120 字符微批持久化，先满足可靠 catch-up 和实时可见；后续若要求逐字级体验，可在同一持久化基础上叠加 WebSocket/Redis PubSub 增量通道。
- **验收结果**：
  - 后端单测：`tests.test_api_sections` 已覆盖创建章节任务自动投递 Celery、任务详情查询。
  - 全量后端测试：`python -m unittest discover -s tests -v`，109 条通过、2 条跳过。
  - 前端构建：`npm run build` 通过。
  - 真实 HTTP 冒烟：`docs/development/runs/run_20260603_104020_http_smoke_passed.md` 通过，章节正文任务 `87b1bb81-9034-46f5-9667-63d3f996a60a` 完成。
  - 实时体验修正后已通过 `py_compile`、`tests.test_api_sections tests.test_smoke_key_flow_script` 和 `npm run build`；真实 LLM 联调需重启后端与 Celery worker 后补跑。
- **后续维护**：当前首版采用轮询降低复杂度；如后续需要更细粒度 token 级进度，可在此基础上增加 Redis pub/sub 或任务事件流。

---

## C. 召回质量增强

### C1. 混合检索（关键词/BM25 + 向量）🟡

- **现状**：当前主链路为 pgvector 向量召回 + metadata 过滤 + Rerank；缺少关键词通道。标准号、包号、条号、物料编码等精确符号可能漏召回。
- **任务**：
  - 优先实现轻量关键词补召回：标准号/包号/物料编码/技术规范编码的精确或 trigram 匹配。
  - 再评估 PostgreSQL 全文检索或 `pg_trgm` 与向量结果融合。
  - 与向量结果去重合并后进入 rerank。
- **验收**：标准号/包号查询相对纯向量 Recall@5/MRR 有量化提升；不会引入跨 doc_role/批次串扰。

### C2. Rerank 增益量化 🟢

- **任务**：`eval_recall.py` 增加有/无 rerank A/B，记录 Recall@5、MRR 与延迟。
- **验收**：`docs/rag/evaluation-records.md` 追加 rerank A/B 数据。

### C3. 升维实验（可选）🟢

- **任务**：1024 vs 1536 维向量对比。该任务需要全量重嵌和 `vector(N)` schema 调整，只在混合检索和数据质量修复后再做。
- **验收**：给出是否值得升维的成本/收益结论。

---

## D. 工程债与可回归性

### D1. Alembic 真实增量迁移能力 🟢

- **现状**：仅 1 个 baseline，`downgrade()` 抛 `NotImplementedError`。后续改表仍依赖手写 SQL。
- **任务**：建立“改表 → revision → upgrade/downgrade 可逆”的工作流，把后续 schema 变更纳入 Alembic 管理。
- **验收**：能生成并回滚一个示例 revision。

### D2. 前端测试框架落地 🟢

- **现状**：`frontend/package.json` 无 vitest/jest/playwright。
- **任务**：先引入 vitest，覆盖核心纯函数、状态转换和 API 适配；Playwright E2E 留到云上或前端测试基础完成后。
- **验收**：`npm test` 可跑。

### D3. `routes.py` 拆分 🟢

- **现状**：855 行，仍保留部分历史公共 helper 和导出逻辑。
- **任务**：继续按业务域拆到 `backend/api/*`，控制单文件复杂度。
- **验收**：主路由文件显著瘦身，现有 unittest 不回归。

### D4. `pages/BidEditor/index.tsx` 组件化 🟢

- **现状**：2,849 行巨型组件。
- **任务**：拆分编辑器、工具栏、章节树、批量生成、状态面板等组件/hooks。
- **验收**：主文件显著瘦身，前端构建通过。

### D5. 前端主 chunk 拆包 🟢

- **任务**：按路由懒加载，降低首屏体积。
- **验收**：主 chunk 体积下降，构建无超大包警告。

---

## E. 文档与对外沉淀

### E1. RAG 工程文档随实现更新 🟢

- 每次召回策略、分块策略、入库策略调整后，同步更新 `docs/rag/`，保留评测记录和原始结果路径。

### E2. 飞书同步 🟢

- 按 `AGENTS.md` 链路，把需要对外沉淀的 Markdown 文档同步到飞书 Docx 云文档；导入成功后由用户手动移入知识库。

---

## 显式排除（资源/完整资料到位后再做）

| 任务 | 阻塞原因 |
| --- | --- |
| 阿里云 ECS/RDS/OSS/Redis 全栈联调（P0-1/5/6/7/11） | 无云账号 |
| HTTPS + 域名 + SLS 日志采集联调 | 无云资源 |
| 客户完整私有资料入库与清洗（P2-1） | 完整资料未到位；当前只有样本批次 |
| 国网目录编号体系适配（P2-2）、分册模板精校（P1-6） | 需客户正式样例和模板偏好 |
| 真实阿里云 RDS/OSS/Redis 压测与容量调参 | 无云资源 |

---

## 建议两周冲刺顺序

| 周 | 重点 | 任务 |
| --- | --- | --- |
| 第 1 周 | 知识库缺口 + 回归护栏 | A1(PDF 标准样板/批量)、B1(全链路冒烟)、A2(重采规章) |
| 第 2 周 | 正文可靠性 + 召回评估 | B2(正文 Celery 化)、A4(测试集扩充+MRR)、C1(混合检索一期) |

> A3（`.doc/.xlsx` 通用化）可和 A4/C1 并行推进；D 类工程债作为穿插任务处理，不抢占 P0/P1。

---

## 验收总目标

云环境和客户完整资料到位时，应能做到：

1. 标准规范、规章、客户样本语料可稳定入库，技术标生成有标准正文支撑；
2. 新批次 `.docx/.doc/.xlsx` 资料可通过统一流程解析、QA、入库；
3. 正文生成关浏览器不丢，失败不覆盖有效稿；
4. 召回质量有 Base/客户测试集、负样本、MRR、串扰率护航；
5. 一条命令跑通主链路冒烟，改动有回归保护。

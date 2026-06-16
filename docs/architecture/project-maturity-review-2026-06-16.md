# 电力 AI 标书系统 — 项目成熟度与专业性评审报告

> **评审日期**：2026-06-16
> **评审方式**：源码直接审查 + 本地真实测试环境核验（gunicorn / Celery / PostgreSQL+pgvector / Redis / DeepSeek / DashScope / MinerU 已配置）
> **评审分支**：`feat/aliyun-test-readiness`
> **评审范围**：后端 ~19,900 行 Python（63 文件）、前端 ~10,400 行 TS/TSX（42 文件）、34 个测试文件、154 篇 docs、scripts/rag 工程脚本
> **评审口径**：定性为主，所有结论附 `文件路径:行号` 证据，不使用 mock 替代真实链路判断

---

## 0. 一句话结论

这是一套**面向单一垂类（电网物资协议库存标书）、工程化程度显著高于一般 LLM 应用 demo 的"测试版底座 + 单企业试点"系统**。主链路真实贯通、可演示、可试用，**不是 PPT 工程**。

> **评审口径声明**：本期真实交付目标 = **泰昌单企业试点**（非多企业 SaaS）。因此本评审**不以多企业扩展性苛求**——用 JSON 存一家企业参数、进程级缓存、薄状态层等对单企业都是合理工程取舍，不计入本期短板。真正计入的阻塞项聚焦在"能否把泰昌这一家跑通、跑稳、交付客户试用"：云上联调、图文召回可靠性、长章节生成稳定性、质量基线保护。多租户隔离/参数规模化建表等列为未来路线图（P2）。

| 维度 | 成熟度 | 判据摘要 |
|:---|:---:|:---|
| 后端架构与工程质量 | **中上** | Celery 编排 + lease/断点续传 + 结构化日志 + 生产启动强校验；上帝 repo、自研连接池、分层违例是债 |
| RAG 检索工程 | **强** | metadata 过滤先行（A/B 数据支撑）+ 增量回归门禁（28 Run 全绿）+ 三类数据边界代码级隔离 |
| AI 写作与合规链路 | **中上** | 章节数动态算法、分册策略、双轨合规、篇幅补写均落地；DOCX 1771 行能力扎实 |
| 前端工程 | **中** | 技术栈现代、SSE 流式 + 断线恢复；但 `BidEditor` 3171 行超大组件、零测试、零 E2E |
| 测试 | **弱–中** | 34 个后端 unittest 扎实但全 mock；无 CI、无前端测试、真实链路靠手动脚本 |
| 文档 | **强** | 154 篇 md、自评不护短、RAG 评测可复现、AGENTS.md 极详尽 |
| 数据边界治理 | **强** | 规则→策略→测试→真实抽样→run summary 全闭环，业内罕见 |
| 部署 / DevOps | **中** | Compose + healthcheck 到位；backend 非多阶段、依赖未锁、MinerU 未编排、云上零联调 |
| **综合** | **中等偏上（~70%）** | 适合内部测试 / 泰昌单企业试点，尚不满足生产交付标准 |

> 综合判断与项目自评 `docs/development/maturity-assessment-2026-06-07.md` 基本一致，本评审予以客观支持。

---

## 1. 后端架构与工程质量（中上）

### 1.1 启动与生产配置 — 成熟

- 生产入口走 gunicorn + gevent（`Dockerfile.backend:33`），配置全部可环境变量覆盖：worker_class 默认 `gevent`、workers=4、worker_connections=1000、timeout=300s、graceful_timeout=30s（`gunicorn.conf.py:4-16`）。
- **生产启动强校验护栏**（`backend/core/security.py:85-136`）：生产模式下校验 `DATABASE_URL`/`DEEPSEEK_API_KEY`/`DASHSCOPE_API_KEY`/`ONLYOFFICE_JWT_SECRET` 不得为占位值（`PLACEHOLDER_VALUES` 黑名单），密钥长度≥24，且必须开访问控制，否则启动即 raise。这是很硬的安全护栏。
- CORS 生产模式禁止 `*`（`security.py:74-78`），密钥脱敏覆盖日志/异常/响应（`security.py:217-240`），上传做扩展名+MIME 双重白名单（`security.py:280-318`）。

### 1.2 异步任务编排 — 工程化程度最高的部分

- **Celery 配置专业**（`backend/tasks/celery_app.py:79-104`）：`task_acks_late=True` + `task_reject_on_worker_lost=True`（worker 被杀后任务重投递）、`worker_max_tasks_per_child=100`（防内存泄漏）、prefetch=1（避免长任务饥饿）、beat 每 60s 兜底回收 1800s 未完成任务（`:94-103`）。
- **章节生成的 lease/heartbeat/微批 chunk/断点续传**（`section_tasks.py:157-537`）是整个后端工程化程度最高的部分：
  - 并发 lease（默认 3）+ `heartbeat()` 每 10s 续租 + owner 校验防双写（`:287-294,365-382`）；
  - 微批 chunk 按字符阈值（160）+ 时间间隔（1s）节流写回 DB（`:384-419`）；
  - 超时分支保留已生成内容为 `draft_content` + `partial_generated`，支持 `auto_resume_partial` 自动续写，最多重试 6 次（`:485-515`）；
  - 幂等：重投递先判终态 + owner（`:282-294`）。
- 这套设计是**专门为 LLM 长时流式生成做的工程化**，在同类项目中少见。

### 1.3 主要问题与风险

1. **`backend/db/supabase_repo.py` 是 2632 行上帝模块**（102 函数，全部表 CRUD 挤在一起，docstring 仅 16 处）——可维护性和 review 难度的最大单点风险。
2. **分层违例**：`tasks` 层反向 import `api` 层业务函数（`export_tasks.py:43`、`parse_tasks.py:31,98`），`ai` 层 7 个模块直连 `db` 层，缺 service/repository 中间层。
3. **自研 PG 连接池**（`postgres_pool.py:42-100`）无连接健康检查/自动重连/Idle 回收，仅靠 `conn.closed` 判定；建议换 psycopg-pool 或 SQLAlchemy。
4. **请求校验与错误处理不规范**：无 schema 校验框架（无 pydantic/marshmallow），全部手写判空；无全局 `errorhandler(Exception)`，4xx 路径不脱敏。
5. **认证链薄弱**：JWT secret 回退到 `ONLYOFFICE_JWT_SECRET`/`APP_AUTH_TOKEN`（`security.py:144-149`），未见独立密码哈希、登录限流、CSRF；`alembic.ini:7` 明文写死 dev 弱口令连接串。

---

## 2. RAG 检索工程（强）— 本项目最强项

### 2.1 metadata 过滤先行的检索范式 — 有硬数据支撑

- **A/B 实验证明价值**（`docs/rag/evaluation-records.md:24-31`）：metadata 定向过滤把跨 doc_role 串扰从 **30% → 0%**，Top1 准确率 **83.3% → 100%**。这是很多 RAG 项目缺失的工程纪律。
- 检索链路四路融合（`backend/rag/retrieval.py:439-516`）：Query Rewrite（标准号/物料码领域词扩展）→ metadata 定向 + 向量召回（不足时自动放宽 doc_role fallback，`:479-491`）→ 关键词兜底 → 父块回溯 → Rerank（`qwen3-rerank`，fail-open 降级，`rerank_client.py:60-61`）。
- **Authority 排序把"参考稿不能当事实"硬编码进排序**（`retrieval.py:15-23,226-237`）：法规/标准 +0.18、企业事实 +0.14、参考模板 **-0.08**、`superseded` 状态 **-0.4**。

### 2.2 父子双层分块 — 设计成熟

- `backend/rag/chunking.py:92-100`：parent/child 双层，父块 embedding 为空不污染检索，仅写作场景回溯（符合 Small-to-Big 最佳实践）。
- 按 doc_role 分化切分（`:153-176`）：法规/标准/合同 → 条款切分；招标公告 → 段标题切分；其它 → 通用切分。
- ⚠️ 单位是字符而非 token（`:108`），且无 overlap 滑窗——对中文法规可接受，对无结构长文本可能丢上下文。

### 2.3 增量回归门禁 — 准生产级质量纪律

- 指标齐全（`scripts/rag/eval_recall.py:114-133`）：Recall@5、Top1 来源准确率、MRR、跨 doc_role 串扰、禁用关键词命中、平均耗时、rerank 打分用例数。
- **四象限对照**（`run_incremental_regression_gate.py:139-164`）：Base×{rerank off, qwen3} + 泰昌专项×{rerank off, qwen3}，硬阈值（泰昌专项 Recall@5=1.0、串扰=0、禁用关键词=0）。
- **连续 28 个 Run 全绿**，失败用例逐条归类根因（无一条归因于分块/召回缺陷），最新门禁 2026-06-12 PASS（`docs/rag/runs/run_20260612_..._regression_summary.md`）。

### 2.4 数据边界治理 — 规则/实现/测试/抽样四闭环

- 三类数据边界定义在 `AGENTS.md:56-88`：泰昌=企业事实、辽宁=招标要求、河北豪乾=参考模板（`reference_only=true`、`do_not_mix_with=["泰昌企业事实"]`）。
- **代码级强制校验**（`scripts/rag/customer_metadata_policy.py:96-171`）：入库前对三类域做互斥强校验，`enterprise_fact` 必须满足 `reference_only=false` + `fact_source_allowed=true`，任一不符报错。
- 测试覆盖（`tests/test_customer_metadata_policy.py`）、真实链路抽样（MPP 环刚度 `66.40`、CPVC 内径 `250.2~250.4`）、门禁硬阈值全到位。

### 2.5 主要问题与风险

1. **关键词兜底是应用层全量扫描 + 进程级全局缓存**（`retrieval.py:25-27,329-343`）：缓存 `_CHUNK_KEYWORD_CACHE` 无失效机制，入库后可能读到旧数据；万级 chunk 下是性能瓶颈。应迁移到数据库侧 FTS。**（本期泰昌试点直接相关）**：泰昌资料后续会持续补充，若不补缓存失效，客户重抽参数/重入库后问答可能读到旧结果。
2. ~~结构化参数存储在 staging JSON 文件而非数据库表~~ **（已按单企业口径重新评级）**：`product_parameters.py:12-16` 的 staging JSON 对泰昌单企业是**合理的工程取舍**——数据量小、查询简单、可接受每次读盘。不作为本期短板，列为多企业阶段的 P2 路线图项（AGENTS.md:49 自己也定义了此演进触发条件）。
3. **match_threshold 阈值散落 4 处不统一**（RPC 默认 0.3、主链路 0.5、评测 0.2、知识库 API 0.3），易导致评测与生产表现脱节。
4. **图片资产评分为规则启发式**（`retrieval.py:653-670`），仅靠 evidence_type 标签匹配，不验证图片实际内容是否与标签一致。

---

## 3. AI 写作与合规链路（中上）

### 3.1 章节规划与篇幅控制 — 算法落地

- **章节数动态算法**（`backend/ai/chapter_planner.py:730-731`）：`min_chapters_hint = max(25, scoring_count * 2, requirement_count // 3)`，封顶 80，确保每个评分项有对应章节响应。
- **篇幅动态分配**（`:322,348-349`）：按章节重要性/评分项/风险项算 `target_words`，单章 `min_words = target*0.7`、`max_words = target*1.25`；首轮不足 75% 自动触发补写（`section_writer.py:114` `_needs_length_supplement(threshold=0.75)`）。

### 3.2 分册写作策略 — 贴合行业

- `backend/core/bid_volumes.py`（284 行）定义技术标/商务标/资格/报价/附件五类分册的生成策略；`section_writer.py:290-318` 按分册注入企业画像（7 字段）和写作约束。
- 资产配图按分册评分（`section_writer.py:150-180`）：technical/business/qualification/price/attachment 各有不同权重。

### 3.3 双轨合规检查

- **规则版**（`compliance_checker.py`，395 行）三维度分类：要求条款（`:296`）、评分项（`:322`）、风险项（`:345`），实时算覆盖率。
- **LLM 语义复核**（`semantic_compliance.py`，212 行）输出证据摘录和补强建议，`scopeNote` 明确声明"不等同于最终 Word 合规结论"（`compliance_checker.py:389`）——反过度承诺设计。

### 3.4 LLM 客户端与成本透明

- 多厂商路由（`qwen_client.py:38-64`）：按 `ai_provider` 切换 DashScope/DeepSeek，函数名保留 `call_dashscope_api` 兼容历史代码。
- **每次调用记录 token + 费用**（`qwen_client.py:10,371` `record_ai_usage_log`），实测 DB 中有 7,053 条用量日志。
- 流式输出有 idle timeout 看门狗（`:137-164`），超时主动停止。

### 3.5 DOCX 导出 — 1771 行能力扎实

- 三步链路真实贯通（`export_tasks.py:84-135`）：`build_project_bid_markdown` → `convert_md_to_word` → `refresh_docx_fields_with_soffice`（LibreOffice headless 刷新目录页码/页脚/总页数）。
- 实现层 `backend/export/md_to_word.py`（1771 行）：封面字段结构化提取（`:334-381`）、目录点引导线、页眉"泰昌投标文件"、宋体 10.5pt、表格表头重复（`ensure_docx_table_header_repeat`）、Mermaid 转图失败兜底清理、图片 caption 去内部来源信息。
- P0 质量项**全部已完成**并有真实导出验收记录（`docs/development/docx-bid-export-quality-todo.md`）：图片 24/24 插入成功、字段刷新成功、无 Mermaid 源码泄露。

### 3.6 主要问题与风险

1. **单章正文仍走请求内 SSE 实时生成**（`sections/stream`，`BidEditor/index.tsx:2222`），未任务化——长时生成受 HTTP 连接/网关超时影响，是生产稳定性风险（自评 P1-1 待办）。
2. `chapter_planner.py` 1081 行、`qwen_client.py` 840 行偏大，函数职责可进一步拆分。
3. 篇幅控制依赖 LLM 自觉遵循字数指令，缺乏生成后硬性截断/补写闭环的自动化验收。

---

## 4. 前端工程（中）

### 4.1 技术栈现代、流式体验完整

- 技术栈：React 18 + TypeScript 5.7 + Vite 6 + Ant Design 5 + Tiptap 2 + Zustand 5 + React Query 5（`frontend/package.json`），选型合理。
- **SSE 流式渲染 + 断线恢复**（`BidEditor/index.tsx:668` 用 EventSource 接收大纲流，`:485` 轮询任务状态回填，`:2347-2348` 关闭页面提示"可刷新恢复进度"）——LLM 生成的前端体验完整。
- 路由清晰（`App.tsx:26-52`），鉴权路由 `RequireAuth` 包裹编辑器页面。

### 4.2 主要问题与风险

1. **`BidEditor/index.tsx` 是 3171 行超大组件**（全文件最大），承载大纲/正文/合规/篇幅/下载/分册切换等几乎所有编辑器逻辑，42 个 useState/useEffect 集中在一个组件——可维护性和测试难度极高，是前端首要技术债。
2. **零前端测试**：无 vitest/jest/playwright，无 `*.test.*` 文件，`package.json` 无 test 脚本。SSE 渲染、DOCX 导出观感、编辑器交互完全没有自动化保护。
3. **无懒加载**（`App.tsx` 全部静态 import 页面），首屏 bundle 偏大。
4. stores 较薄（`bidProjectStore` 仅管理 recentTasks 列表），大量状态散落在 `BidEditor` 组件内，状态管理一致性依赖组件内部协调。

---

## 5. 测试（弱–中）

### 5.1 现状

- 34 个后端测试文件，基于 `unittest`（非 pytest），**无 pytest 配置**（无 pytest.ini/conftest.py/pyproject.toml）。
- 最新实测 **138 个用例全绿**（`docs/development/maturity-assessment-2026-06-07.md:19`）。
- 测试性质：**单元 + HTTP 路由级 mock 为主**，重型外部依赖全 mock（`test_celery_parse_tasks.py:10-14` 明确说明 Supabase/MinerU/入库全 mock）。
- 真实链路验证放在 `scripts/`（`smoke_key_flow.py`、`run_taichang_product_parameter_refresh.py`、`run_incremental_regression_gate.py`），靠**手动跑 + 写 run summary**。

### 5.2 主要问题与风险

1. **无 CI/CD**：无 `.github/workflows/`、无 GitLab CI，回归全靠开发者本地手跑，退化风险高，PR 无自动门禁。
2. **无前端测试、无浏览器 E2E**：编辑器/SSE/DOCX 观感零自动化保护。
3. 真实链路脚本依赖真实服务+真实 LLM+`source .env`，无法纳入 CI 或夜跑，难以持续回归。

---

## 6. 文档（强）— 体系化、可追溯、自评诚实

- **154 篇 markdown**，分层清晰：research / development / features / rag / architecture / deployment / debugging。
- `README.md`（467 行）含架构图、7 大亮点、技术路径 sequence 图。
- `AGENTS.md`（253 行）极详尽：RAG SOP、泰昌 MVP 规则、metadata 边界、图片资产规则、DOCX 导出 SOP、回归同步规则。
- **RAG 评测体系专业**：`evaluation-records.md` 多 Run 追加式记录含 A/B 对比和失败根因；`runs/` 有 171 个文件（含 summary + 原始 JSON）。
- **自评不护短**（`maturity-assessment-2026-06-07.md`）：主动修正"历史稿写 101 测试，实际 138"、主动暴露"300 图片资产 0 个有 embedding"、把"已完成但有水分"项单独列出——可信度高。

### 问题
- 根目录与 docs/ 文档职责重叠（多个评估/选型 md 散落根目录）；`runs/` 同日多版本缺归档策略。

---

## 7. 部署 / DevOps（中）

### 7.1 已就绪
- `docker-compose.yml` 编排 5 服务（postgres+pgvector / redis / backend-gunicorn / celery-worker / frontend-nginx），**全部带 healthcheck + `depends_on: condition: service_healthy`**，工程质量较高。
- `Dockerfile.frontend` 是真正的多阶段构建（node:22 build → nginx run）。
- `.env.example`（179 行）配置项覆盖完整，每个块有中文注释。
- 部署文档齐全：quickstart / security / aliyun-target-architecture / aliyun-sls / gitee-ai-bid-runbook（1201 行）。

### 7.2 主要问题与风险

1. **`Dockerfile.backend` 单阶段、非多阶段**（直接 `python:3.12-slim` + `apt-get install libreoffice`），镜像偏大，无 builder/runner 分离。
2. **依赖未锁定**：`requirements.txt` 仅锁直接依赖（22 行 `==`），无 `requirements.lock`/`uv.lock`/`poetry.lock`，传递依赖未冻结。
3. **docker-compose 无 MinerU 服务**：OCR 链路在容器化部署里仍是外部依赖，与"全栈编排"宣称不符。
4. **云上零联调是硬阻塞**（`阿里云测试环境准备任务清单.md:91`）：本地 Docker 通过 ≠ RDS pgvector/OSS Endpoint/Redis broker/网络策略都通；P0-1 阿里云账号仍未到位。

---

## 8. 阿里云测试就绪度（中，偏弱）

- 准备清单 `阿里云测试环境准备任务清单.md`（1739 行）极其细致，P0(14)/P1(12)/P2(8) + 外部依赖矩阵。
- 代码/本地验证就绪：Docker 编排、gunicorn、PostgreSQL、OSS 双 provider、SQLite 下线、生产鉴权强制、pgvector 统一。
- **未完成的关键项**：
  - P0-1 阿里云账号未到位（⏳ 等外部条件，硬阻塞）；
  - P0-9 关键国标 PDF 未入库（15 份被跳过，含 GB 50150/GB 50168）；
  - P0-14 300 个图片资产 0 个有 embedding（图文语义召回不可靠）；
  - P1-1 单章 SSE 未任务化；P1-10/11/12 单章收敛/DOCX 复验/Alembic 增量迁移未补齐。
- **结论**：代码与文档准备充分，但真实云资源零联调，是当前最大阻塞。

---

## 9. 项目整洁度（中）

- `.gitignore` 设计周到（`*.db`/`*.pdf`/`*.zip`/`storage/`/`uploads/`/`.env` 均忽略），敏感大文件未进 git 历史。
- **问题**：
  - `_debug_project_state.py`（硬编码 project_id 的一次性调试脚本）、`task_plan.md`、`notes.md` 被提交进仓库，应清理或归档。
  - **350MB+ 客户敏感资料**（5 个 pdf/zip）躺在仓库根目录，虽不入 git 但存在泄露/误打包风险，建议移到仓库外。
  - 根目录评估/选型 md 与 `docs/research`、`docs/development` 职责重叠。

---

## 10. 综合评价与改进建议

### 10.1 项目定位（客观）

**中等偏上成熟度（~70%）的"测试版底座 + 电网/泰昌单企业适配"系统。** 核心主链路（上传 → 解析 → 解读 → 大纲 → 正文 → 合规 → DOCX）每一环都有真实实现并真实贯通，RAG 工程和数据边界治理达到了准生产级工程纪律，文档体系专业且自评诚实。**以本期"泰昌单企业试点"为口径，系统已具备交付客户试用的基础；剩余阻塞集中在云上联调、图文召回可靠性、长章节稳定性三项，均非架构性返工，属可收敛的工程项。**

### 10.2 最值得肯定的 5 个亮点

1. **RAG 增量回归门禁体系**（四象限对照 + 硬阈值 + 28 Run 全绿 + 失败根因归类）——达到准生产级质量纪律，同类项目罕见。
2. **数据边界治理四闭环**（AGENTS.md 规则 → customer_metadata_policy 机器校验 → unittest 断言 → 真实链路抽样 → run summary）——把"企业事实/招标/参考稿不得混用"做成了可量化、可追溯的工程实践。
3. **章节生成的 lease/heartbeat/微批/断点续传/幂等**——专门为 LLM 长时流式生成做的工程化设计。
4. **结构化参数层优先于向量回答具体数值**（MPP 环刚度/CPVC 内径从检验报告结构化抽取），反幻觉设计到位（含合同日期空白不代填）。
5. **文档自评不护短**——主动修正过时数据、暴露"已完成但有水分"项，可信度高。

### 10.3 最需要优先解决的 5 个问题

| 优先级 | 问题 | 影响 | 建议 |
|:---:|:---|:---|:---|
| **P0** | 无 CI/CD | 回归无保护，PR 无门禁，退化风险高（泰昌资料会持续补充，每次补充都改了 RAG，没门禁很容易把已通过的召回指标改坏） | 接 GitHub Actions：后端 unittest + RAG 门禁 + lint，PR 必须绿 |
| **P0** | 阿里云零联调 + 图片资产 0 向量 | 无法验证云上真实可用性；图文召回当前不可靠（300 资产 0 embedding） | 账号到位后优先联调 RDS/OSS/Redis/网络策略；补图片资产 embedding（P0-14） |
| **P1** | 关键词兜底缓存无失效 | 泰昌资料持续补充，重入库后问答可能读到旧数据 | 入库流程末尾清 `_CHUNK_KEYWORD_CACHE`，或迁移 DB 侧 FTS |
| **P1** | 单章正文仍走请求内 SSE | 长章节生成受 HTTP/网关超时影响，是泰昌试点交付稳定性风险 | 改为 Celery 任务 + 轮询（自评 P1-1） |
| **P1** | 前端零测试 + BidEditor 3171 行 | 编辑器/SSE/DOCX 观感无保护，客户试用遇回归难定位 | 至少补 vitest 关键交互 + 拆分 BidEditor 组件 |

> **说明**：多租户隔离、结构化参数规模化建表、自研连接池替换等"多企业 SaaS 才需要"的项，已按单企业口径移出本期优先级，列入下方 P2 路线图。

### 10.4 其他建议（按本期/路线图分组）

**本期泰昌试点范围内（值得做）：**
- **图片资产补 embedding**（P0-14）：300 个资产 0 向量，图文语义召回当前不可靠——直接影响泰昌标书图文并茂质量。
- **单章正文任务化**（P1-1）：把请求内 SSE 改为 Celery 任务 + 轮询，解除 HTTP/网关超时依赖。
- **关键词缓存失效**：泰昌资料持续补充，入库流程末尾清 `_CHUNK_KEYWORD_CACHE`，防止问答读到旧结果。
- **项目整洁度**：清理 `_debug_project_state.py`/`task_plan.md`/`notes.md`；350MB 客户资料移出仓库根目录（防误打包/泄露）。

**未来路线图（多企业阶段再做，本期不苛求）：**
- 结构化参数落地 `power_grid_product_parameter_rows` 等数据库表（触发条件：参数规模变大或多批次查询变复杂，见 AGENTS.md:49）。
- `supabase_repo.py`（2632 行）按业务域拆分多个 repository；引入 ORM 或 pydantic schema 校验。
- 自研连接池换 psycopg-pool。
- backend Dockerfile 改多阶段构建；锁定传递依赖（pip-compile/uv lock）。
- 关键词兜底迁移 DB 侧 FTS（pgvector hybrid / tsvector）。

---

## 附：评审依据关键文件清单

| 维度 | 关键文件 |
|:---|:---|
| 后端启动/安全 | `main.py`、`gunicorn.conf.py`、`backend/core/security.py`、`backend/core/config.py`、`backend/core/logging_config.py` |
| 任务编排 | `backend/tasks/celery_app.py`、`backend/tasks/section_tasks.py`、`backend/tasks/export_tasks.py` |
| 数据层 | `backend/db/supabase_repo.py`、`backend/db/postgres_pool.py`、`migrations/alembic/`、`sql/` |
| RAG | `backend/rag/chunking.py`、`backend/rag/retrieval.py`、`backend/rag/vector_store.py`、`migrations/postgres/006_rag_p0_filtered_recall.sql`、`scripts/rag/customer_metadata_policy.py` |
| AI 写作 | `backend/ai/chapter_planner.py`、`backend/ai/section_writer.py`、`backend/ai/compliance_checker.py`、`backend/ai/qwen_client.py`、`backend/core/bid_volumes.py` |
| DOCX 导出 | `backend/export/md_to_word.py`、`backend/tasks/export_tasks.py` |
| 前端 | `frontend/src/pages/BidEditor/index.tsx`、`frontend/src/App.tsx`、`frontend/src/components/editor/TiptapBidEditor.tsx` |
| 测试/评测 | `tests/`、`scripts/rag/eval_recall.py`、`scripts/rag/run_incremental_regression_gate.py`、`docs/rag/evaluation-records.md` |
| 部署/治理 | `docker-compose.yml`、`Dockerfile.backend`、`.env.example`、`AGENTS.md`、`阿里云测试环境准备任务清单.md` |

---

*本报告基于 2026-06-16 代码快照与本地真实测试环境核验生成。所有结论附文件路径:行号证据，可与项目自评 `docs/development/maturity-assessment-2026-06-07.md` 对照。*

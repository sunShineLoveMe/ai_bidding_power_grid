# Requirements Document

## Introduction

电网 AI 标书系统当前所有后台异步任务都运行在裸 `threading.Thread(daemon=True)` 线程上。线程随 Web 进程生命周期存活，一旦进程重启（部署、OOM、崩溃、gunicorn reload），进行中的任务会无痕丢失：任务状态既不会转为失败，也无法重试，前端则持续轮询、界面一直转圈。系统已确定使用 PostgreSQL（含 pgvector）作为数据库，生产以 gunicorn + gevent worker（默认 4 worker）启动。`requirements.txt` 已包含 gunicorn/gevent，但尚无 redis、celery 依赖；Redis 目前仅被 `/ready` 健康检查用 socket PING 探测，没有 broker/worker 代码。

本特性引入 Celery + Redis，把核心后台异步任务从裸线程迁移到任务队列，使任务在进程重启后不再无痕丢失（具备失败状态或可重试能力），同时保持前端轮询 API 契约不变。当前阶段为单企业、小团队的阿里云测试/演示版本，因此本特性强调“可靠、可观测、可分批落地、可本地联调”，而非高吞吐或多租户能力。

经代码审阅确认，真正运行在裸线程上的后台任务共有四类，均纳入迁移范围：

1. **DOCX 异步导出**（`backend/api/export.py` 的 `_run_bid_docx_export_task`）——任务状态写 PostgreSQL 表 `bid_export_tasks`。
2. **MinerU 招标文件解析/入库**（`backend/api/projects.py`、`backend/api/mineru.py`、`backend/parsing/document_parser.py`）——任务状态写**本地文件** `parsed_outputs/{id}/mineru_status.json`，不在数据库。
3. **知识库文件入库**（`backend/api/knowledge.py` 的 `sync_and_parse_knowledge_in_background`）——同样用本地文件记录解析状态。
4. **大纲后台精炼**（`backend/ai/chapter_planner.py` 的 `_refine_bid_outline_in_background`）——完成后写回数据库。

明确排除在迁移范围之外的两类工作：

- **批量章节生成**不是后端线程任务。它由前端循环逐章调用 SSE（`backend/api/sections.py` 的 `sections/stream`），后端仅通过 `section-generation-tasks` 系列接口记录任务状态，没有后台线程，因此不迁移到 Celery。
- **SSE 流式接口**（大纲流式、章节正文流式、知识库问答流式）是 HTTP 长连接内的实时生成器，依赖即时推送返回给浏览器，不能改造为 Celery 异步执行，必须排除在迁移范围外。

本特性最大的工程风险是缺乏集成/E2E 测试保护网：现有约 78 个测试几乎全是 mock 单元测试，在零回归保护下重构异步主干风险高。因此本文档把“为被迁移任务补 HTTP 路由级集成 smoke 测试”列为强制需求。此外，MinerU/知识库解析状态目前存于本地文件，在多 worker/多容器下 Web 进程与 Celery worker 不共享该文件就读不到状态，因此迁移这两类任务时必须将状态从本地文件迁移到 PostgreSQL（或 Redis），保证跨进程可见。

## Glossary

- **Task_Queue_System（任务队列系统）**：本特性引入的 Celery + Redis 整体能力，负责接收、排队、执行后台异步任务并记录其状态。
- **Celery_App（Celery 应用）**：在后端代码中初始化的 Celery 实例，注册任务、绑定 broker 与 result backend，并被 Web 进程与 Worker 进程共享导入。
- **Celery_Worker（Celery 工作进程）**：独立于 gunicorn Web 进程运行、从 Redis_Broker 拉取并执行任务的进程。
- **Redis_Broker（Redis 消息代理）**：Celery 使用的消息代理，承载任务投递队列；测试版可用本地 `redis:7-alpine`，生产可切换为阿里云 Redis。
- **Task_Status_Store（任务状态存储）**：记录任务状态（pending/running/completed/failed 等）、进度与错误信息的持久化位置；对 DOCX 导出为 PostgreSQL 表 `bid_export_tasks`，对解析类任务迁移后为 PostgreSQL（或 Redis），要求跨进程可见。
- **DOCX_Export_Task（DOCX 导出任务）**：将项目标书 Markdown 转换为 Word 文档的后台任务，状态写入 `bid_export_tasks`。
- **Tender_Parse_Task（招标文件解析任务）**：MinerU 招标文件解析与入库的后台任务。
- **Knowledge_Ingest_Task（知识库入库任务）**：知识库文件解析与入库的后台任务。
- **Outline_Refine_Task（大纲精炼任务）**：大纲后台精炼任务，完成后写回数据库。
- **Migrated_Task（被迁移任务）**：上述四类后台任务的统称，即 DOCX_Export_Task、Tender_Parse_Task、Knowledge_Ingest_Task、Outline_Refine_Task。
- **Polling_API（轮询接口）**：前端用于查询任务进度的 HTTP 接口集合，包括 `export-tasks`、`parse-status`、`section-generation-tasks` 等现有接口。
- **API_Contract（接口契约）**：Polling_API 的请求路径、请求方法、请求参数、响应字段结构与字段语义的集合。
- **Readiness_Probe（就绪探针）**：后端 `/ready` 健康检查端点，用于反映依赖组件可用性。
- **Health_Probe（存活探针）**：后端 `/health` 健康检查端点。
- **SSE_Endpoint（流式接口）**：大纲流式、章节正文流式、知识库问答流式等基于 Server-Sent Events 的 HTTP 长连接接口。
- **Section_Generation_Tracking（批量章节生成跟踪）**：`section-generation-tasks` 系列接口承载的、由前端逐章 SSE 调用驱动的任务状态记录。
- **Integration_Smoke_Test（集成冒烟测试）**：针对被迁移任务的 HTTP 路由级集成测试，验证“创建任务 → 查询状态”链路在不依赖真实外部服务（MinerU/LLM/对象存储）时可端到端跑通。
- **Compose_Stack（容器编排栈）**：项目 `docker-compose.yml` 定义的服务集合，当前包含 postgres、redis、backend、frontend。
- **DB_Client（数据库访问客户端）**：当前的 `PostgresCompatClient`，每次操作新建数据库连接、无连接池。

## Requirements

### Requirement 1: 引入 Celery + Redis 基础设施

**User Story:** 作为后端开发者，我希望系统具备可用的 Celery + Redis 任务队列基础设施，以便后续把后台任务从裸线程迁移到队列执行。

#### Acceptance Criteria
1. THE Task_Queue_System SHALL 在 `requirements.txt` 中声明固定版本的 `celery` 与 `redis` 依赖。
2. THE Celery_App SHALL 从环境变量 `REDIS_URL` 读取 Redis_Broker 连接地址。
3. IF 环境变量 `REDIS_URL` 未配置，THEN THE Celery_App SHALL 在启动时记录一条错误日志并以非零退出码终止 Celery_Worker 启动。
4. THE Celery_App SHALL 被 gunicorn Web 进程与 Celery_Worker 进程以同一模块路径导入，且任务注册结果在两类进程中一致。
5. WHEN 一个任务被提交到 Task_Queue_System，THE Redis_Broker SHALL 持久化该任务消息直到任意 Celery_Worker 确认完成或失败。
6. THE Celery_Worker SHALL 在任务执行成功或失败后向 Redis_Broker 发送确认（late acknowledgement），且启用 late acknowledgement 即自动使未完成的任务在 Celery_Worker 进程重启后被重新投递。

### Requirement 2: 任务在进程重启后不再无痕丢失

**User Story:** 作为系统运维者，我希望进程重启时进行中的后台任务不再无痕丢失，以便前端能看到失败状态或任务被重试，而不是一直转圈。

#### Acceptance Criteria
1. WHEN 一个 Migrated_Task 开始执行，THE Task_Queue_System SHALL 将该任务在 Task_Status_Store 中的状态置为 `running`。
2. IF 一个 Migrated_Task 在执行中抛出异常，THEN THE Task_Queue_System SHALL 将该任务在 Task_Status_Store 中的状态置为 `failed` 并记录错误摘要。
3. WHEN 一个正在执行 Migrated_Task 的 Celery_Worker 进程被终止，THE Task_Queue_System SHALL 在剩余的 Celery_Worker 上重新投递该任务，或将该任务在 Task_Status_Store 中标记为 `failed`。
4. THE Task_Status_Store SHALL 为每个 Migrated_Task 持久化记录 `pending`、`running`、`completed`、`failed` 四种状态之一。
5. WHILE 一个 Migrated_Task 处于 `running` 状态，THE Task_Status_Store SHALL 保留该任务的进度字段供 Polling_API 读取。

### Requirement 3: 迁移 DOCX 异步导出任务（第一批）

**User Story:** 作为后端开发者，我希望先把状态已在数据库的 DOCX 导出任务迁移到 Celery，以便用低风险任务立住 Celery + Redis 基础设施。

#### Acceptance Criteria
1. WHEN 客户端调用 `POST /api/bidding/interpretations/<project_id>/download-docx`，THE DOCX_Export_Task SHALL 作为 Celery 任务提交到 Task_Queue_System，而不在裸线程中执行。
2. WHEN DOCX_Export_Task 提交成功，THE 导出接口 SHALL 返回与迁移前一致的响应字段（包含 `task`、`taskId`、`projectId`）与 HTTP 201 状态码。
3. WHILE DOCX_Export_Task 执行，THE DOCX_Export_Task SHALL 将状态与进度写入 PostgreSQL 表 `bid_export_tasks`。
4. WHEN 客户端调用 `GET /api/bidding/interpretations/<project_id>/export-tasks/<task_id>`，THE Polling_API SHALL 从 `bid_export_tasks` 返回该任务的当前状态，且响应字段结构与迁移前一致。
5. IF DOCX_Export_Task 执行失败，THEN THE DOCX_Export_Task SHALL 在 `bid_export_tasks` 中写入 `failed` 状态与错误摘要。

### Requirement 4: 迁移 MinerU 招标文件解析任务并将状态迁移到数据库（第二批）

**User Story:** 作为后端开发者，我希望把 MinerU 招标文件解析任务迁移到 Celery，并将其状态从本地文件迁移到数据库，以便 Web 进程与 Celery_Worker 在多进程/多容器下都能读到一致的解析状态。

#### Acceptance Criteria
1. WHEN 招标文件上传或重试解析触发解析，THE Tender_Parse_Task SHALL 作为 Celery 任务提交到 Task_Queue_System，而不在裸线程中执行。
2. THE Tender_Parse_Task SHALL 将解析状态写入跨进程可见的 Task_Status_Store（PostgreSQL 或 Redis），而不是仅写本地文件 `parsed_outputs/{id}/mineru_status.json`。
3. WHEN Celery_Worker 与 Web 进程运行在不同进程或不同容器中，THE `GET /api/bidding/parse-status/<file_id>` SHALL 返回由 Celery_Worker 写入的最新解析状态。
4. THE `parse-status` 系列接口的 API_Contract SHALL 与迁移前保持一致，包括请求路径、请求方法与响应字段结构。
5. IF Tender_Parse_Task 在解析或入库阶段失败，THEN THE Tender_Parse_Task SHALL 在 Task_Status_Store 中记录失败状态、失败阶段与是否可重试标识。
6. WHERE 原解析逻辑包含可重试的下载或导入步骤，THE Tender_Parse_Task SHALL 保留对应的重试入口，使失败任务可被再次触发。

### Requirement 5: 迁移知识库文件入库任务并将状态迁移到数据库

**User Story:** 作为后端开发者，我希望把知识库文件入库任务迁移到 Celery 并将状态迁移到数据库，以便客户资料入库在进程重启后不丢失且状态跨进程可见。

#### Acceptance Criteria
1. WHEN 客户端调用 `POST /api/knowledge/upload`（或其等价路由），THE Knowledge_Ingest_Task SHALL 作为 Celery 任务提交到 Task_Queue_System，而不在裸线程中执行。
2. THE Knowledge_Ingest_Task SHALL 将入库状态写入跨进程可见的 Task_Status_Store（PostgreSQL 或 Redis），而不是仅写本地文件。
3. IF Knowledge_Ingest_Task 执行失败，THEN THE Knowledge_Ingest_Task SHALL 将对应知识文档状态更新为 `failed` 并记录错误摘要。
4. THE 知识库文档查询接口（`GET /api/knowledge/documents` 与 `GET /api/knowledge/documents/<id>`）的 API_Contract SHALL 与迁移前保持一致。

### Requirement 6: 迁移大纲后台精炼任务

**User Story:** 作为后端开发者，我希望把大纲后台精炼任务迁移到 Celery，以便大纲精炼在进程重启后不无痕丢失。

#### Acceptance Criteria
1. WHEN 大纲精炼被触发，THE Outline_Refine_Task SHALL 作为 Celery 任务提交到 Task_Queue_System，而不在裸线程中执行。
2. WHEN Outline_Refine_Task 执行成功，THE Outline_Refine_Task SHALL 将精炼结果写回 PostgreSQL，行为与迁移前一致。
3. IF Outline_Refine_Task 执行失败，THEN THE Outline_Refine_Task SHALL 记录失败状态与错误摘要供后续查询。

### Requirement 7: 保持前端轮询接口契约不变

**User Story:** 作为前端开发者，我希望任务迁移到 Celery 后前端轮询接口契约不变，以便前端无需修改即可继续获取任务进度。

#### Acceptance Criteria
1. THE Polling_API SHALL 在迁移后保留 `export-tasks`、`parse-status`、`section-generation-tasks` 系列接口的请求路径与请求方法。
2. WHEN 前端轮询任一 Polling_API 接口，THE Polling_API SHALL 返回与迁移前字段名称与字段语义一致的响应结构。
3. THE Polling_API SHALL 在迁移后保留与迁移前一致的 HTTP 状态码取值（包括成功、未找到与参数错误对应的状态码）。

### Requirement 8: 明确并约束迁移范围的排除项

**User Story:** 作为技术负责人，我希望明确哪些工作不纳入 Celery 迁移，以便避免错误地改造 SSE 实时链路或前端驱动的章节生成跟踪。

#### Acceptance Criteria
1. THE Task_Queue_System SHALL NOT 承载 SSE_Endpoint 的实时生成逻辑（大纲流式、章节正文流式、知识库问答流式）。
2. THE SSE_Endpoint SHALL 在本特性实施后保持 HTTP 长连接实时推送的执行方式不变。
3. THE Section_Generation_Tracking SHALL 在本特性实施后保持由前端逐章 SSE 调用驱动、后端仅记录状态的方式不变，不迁移到 Celery。

### Requirement 9: 为被迁移任务补充集成冒烟测试

**User Story:** 作为开发者，我希望为被迁移任务补充 HTTP 路由级集成冒烟测试，以便在缺乏 E2E 保护网的情况下重构异步主干时具备回归保护。

#### Acceptance Criteria
1. THE Integration_Smoke_Test SHALL 覆盖每一类 Migrated_Task 的“创建任务”与“查询任务状态”两个 HTTP 路由。
2. WHEN Integration_Smoke_Test 在禁用真实外部服务（MinerU、LLM、对象存储）的条件下执行，THE Integration_Smoke_Test SHALL 验证任务创建接口返回成功状态码且任务状态可被查询接口读取。
3. WHEN Integration_Smoke_Test 模拟 Migrated_Task 执行失败，THE Integration_Smoke_Test SHALL 验证 Task_Status_Store 中记录为 `failed` 状态。
4. THE Integration_Smoke_Test SHALL 以 Celery eager 模式或等价的同步执行模式运行，使测试不依赖独立运行的 Celery_Worker 进程。

### Requirement 10: 支持分批迁移与分批验收

**User Story:** 作为技术负责人，我希望迁移能分批推进并分批验收，以便先用低风险的 DOCX 导出立住基础设施，再推进高风险的解析状态模型改造。

#### Acceptance Criteria
1. THE Task_Queue_System SHALL 在仅迁移 DOCX_Export_Task 的状态下可独立部署并通过验收，无需同时迁移其余 Migrated_Task。
2. WHILE 一部分 Migrated_Task 已迁移到 Celery 而其余仍未迁移，THE 系统 SHALL 保持所有 Polling_API 接口对前端可用。
3. THE 系统 SHALL 在每一批迁移完成后支持以下验收：终止执行该批任务的 Celery_Worker 后，对应任务在 Task_Status_Store 中具有 `failed` 状态或被重新投递，而不是无痕消失。

### Requirement 11: 在容器编排中补充 Celery worker 服务

**User Story:** 作为 DevOps，我希望在 Docker Compose 中补充 Celery worker 服务，以便本地与测试环境能完整运行任务队列。

#### Acceptance Criteria
1. THE Compose_Stack SHALL 新增一个 Celery_Worker 服务，与 backend 服务使用同一镜像并以 Celery worker 命令启动。
2. THE Compose_Stack 中的 Celery_Worker 服务 SHALL 依赖 redis 与 postgres 服务，并从同一环境配置读取 `REDIS_URL` 与 `DATABASE_URL`。
3. THE Compose_Stack SHALL 支持使用本地 `redis:7-alpine` 作为 Redis_Broker 进行开发联调。
4. WHEN 执行 `docker compose up`，THE Compose_Stack SHALL 启动 backend、frontend、postgres、redis 与 Celery_Worker 全部服务。

### Requirement 12: 健康/就绪探针反映 worker 与 broker 可用性

**User Story:** 作为系统运维者，我希望就绪探针能反映 Celery worker 与 Redis broker 的可用性，以便部署时判断任务队列是否真正就绪。

#### Acceptance Criteria
1. WHEN 客户端请求 Readiness_Probe（`/ready`），THE Readiness_Probe SHALL 返回 Redis_Broker 的连通性检查结果。
2. WHEN 客户端请求 Readiness_Probe（`/ready`），THE Readiness_Probe SHALL 返回至少一个 Celery_Worker 是否可达的检查结果。
3. IF Redis_Broker 不可连通，THEN THE Readiness_Probe SHALL 在响应中将 Redis 检查项标记为 `fail`。
4. IF 没有任何 Celery_Worker 可达，THEN THE Readiness_Probe SHALL 在响应中将 Celery_Worker 检查项标记为 `fail` 或 `warn`。
5. THE Health_Probe（`/health`）SHALL 保持仅返回进程存活状态，不引入对 Redis_Broker 或 Celery_Worker 的强依赖。

### Requirement 13: 本地 Redis 开发联调能力

**User Story:** 作为后端开发者，我希望在本地用 redis:7-alpine 即可联调任务队列，以便在阿里云 Redis 资源到位前推进开发。

#### Acceptance Criteria
1. WHERE 环境变量 `REDIS_URL` 指向本地 `redis:7-alpine` 实例，THE Task_Queue_System SHALL 完成任务的提交、执行与状态写入。
2. THE Task_Queue_System SHALL 仅通过 `REDIS_URL` 环境变量切换本地 Redis 与阿里云 Redis，无需修改应用代码。

### Requirement 14: 数据库连接来源增多的连接管理风险约束

**User Story:** 作为后端开发者，我希望在新增 Celery worker 后控制数据库连接来源的增长，以便避免打满 RDS 连接数。

#### Acceptance Criteria
1. WHEN Celery_Worker 与 gunicorn Web 进程同时访问 PostgreSQL，THE 系统 SHALL 通过可配置的上限约束并发数据库连接来源（worker 并发数与 Web worker 数）。
2. THE Celery_Worker 并发度 SHALL 可通过环境变量配置，以便按 RDS 最大连接数设置上限。
3. WHERE DB_Client 当前每次操作新建连接且无连接池，THE 设计文档 SHALL 记录连接池改造为关联风险项，供后续任务跟踪。

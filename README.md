# 电力 AI 标书系统（国家电网配网物资投标 MVP）

> 面向国家电网及省公司配网物资类招投标场景的 AI 标书编制工作台，支持本地开发、私有化部署和阿里云交付。

招标文件上传 → OCR 解析 → 结构化解读 → 分册大纲 → 章节正文 → 合规检查 → DOCX 导出，全流程 AI 辅助，企业知识库驱动，数据本地可控。

> **交付前重要说明**：本项目不是通用行业、通用采购、通用标书系统。当前 MVP 聚焦国家电网/省公司物资协议库存、配网物资、技术规范书、货物清单、商务/技术/资格响应等电力器材投标场景；默认试点投标主体为 **河北泰昌电力器材科技有限公司**。招标文件只能提供“招标方要求”，不能替代投标企业自己的资质、业绩、产品参数、检验报告和图片资产。

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![React](https://img.shields.io/badge/React-18-blue)](https://react.dev)
[![Use](https://img.shields.io/badge/Use-Internal-lightgrey)](#使用范围)

---

## 项目定位与适用场景

### 当前最适合的投标场景

本系统当前最适合用于以下类型的投标辅助：

- 国家电网、国网省公司、区域联合采购中的物资类公开招标、协议库存招标、配网物资招标。
- 电力器材、配网材料、电缆保护管、电力电缆、架空绝缘导线等“有明确技术规范书、货物清单、资格条件、商务条款、技术响应表”的标书。
- 单一投标企业私有化使用：围绕一个企业建立企业知识库、资信库、产品库和历史投标资料库，再针对具体招标包生成技术标、商务标、资格文件和 DOCX 初稿。
- 客户验收和演示场景：用真实招标文件包测试“招标要求解析、关键条款提取、大纲生成、企业资料召回、章节正文生成、合规检查、正式 DOCX 导出”这条链路。

### 当前默认试点主体

当前 MVP 默认投标主体为：

```text
河北泰昌电力器材科技有限公司
```

因此，系统生成的企业事实、资质引用、产品参数、检验报告、业绩证明、图片资产和 DOCX 配图，必须来自泰昌自己的真实资料。辽宁、江西、山西、西北/西藏等招标资料只能作为招标要求样本；河北豪乾等第三方标书只能作为格式和写法参考，不能作为泰昌企业事实。

### 不应误用的场景

以下场景不应直接承诺为当前 MVP 能力：

- 只上传招标文件，不提供投标企业资料，就直接生成完整、可盖章的正式投标文件。
- 把非泰昌企业资料、其他企业历史标书、招标方文件中的描述当作泰昌资质、业绩或产品能力。
- 跨行业通用投标，例如软件服务、工程总承包、政府服务采购、医疗设备、建筑施工等非电网物资标书。
- 未提供对应产品资质和检测报告时，强行响应某类产品包。例如使用 1kV/10kV 架空绝缘导线招标包测试时，若泰昌未提供架空绝缘导线相关资质、型式试验报告、产品参数和供货业绩，系统只能解析招标要求，不能生成“泰昌已满足”的事实性响应。
- 替代人工报价、签字盖章、商务决策、法务审查和最终投标责任确认。

### 测试资料准备说明

如需使用根目录 `assets/template_words/` 下的“国家电网有限公司2026年西北、西藏区域第一次联合采购10kV电力电缆、架空绝缘导线协议库存公开招标采购”资料进行客户测试，请先阅读根目录文档：

→ [西北西藏架空绝缘导线招标文件测试资料准备说明](西北西藏架空绝缘导线招标文件测试资料准备说明.md)

该文档明确说明：这些文件属于招标要求测试样本；若要生成泰昌口径投标文件，还需要泰昌额外提供哪些企业资料、产品资料、产品图片、资质证书、检验报告和业绩证明。

---

## 核心亮点

### 1. 两阶段 AI 章节大纲生成
规则版骨架秒级展示，AI 精细化版通过 Celery 后台任务异步刷新。大纲生成前自动检索企业知识库，根据评分项数量动态计算最小章节数（`max(25, 评分项×2)`），确保每个评分项都有对应章节响应。

→ [详细说明](docs/features/outline-generation.md)

### 2. 企业知识库驱动的正文生成
章节正文生成时自动从企业资信库、产品库、历史标书中召回相关资料，注入企业画像（7 字段）和分册写作策略（技术标/商务标/资格/报价/附件各有不同约束），生成内容贴合企业实际。
章节正文由 Celery worker 后台生成，并把微批 chunk 持久化到任务状态；前端轮询时实时回填编辑器，断线或刷新后可恢复中间已生成正文，取消生成时保留已展示内容。

→ [章节写作计划](docs/features/section-writing.md) · [分册设计](docs/features/volume-design.md)

### 3. 全文篇幅精细控制
用户设置目标页数后，系统按章节重要性、评分项数量、风险项数量动态分配每章目标字数。首轮生成不足 75% 时自动触发补写。

→ [详细说明](docs/features/length-settings.md)

### 4. 规则 + LLM 双轨合规检查
三维度覆盖率（要求条款/评分项/风险项）实时仪表盘，下载前拦截高风险缺失项，支持 LLM 语义复核输出证据摘录和补强建议。

→ [详细说明](docs/features/compliance.md)

### 5. 企业私有 RAG 知识库（父子分块 + 场景化召回）
pgvector（HNSW 索引）向量检索 + 父子双层分块 + metadata 定向过滤 + 关键词兜底，支持图片资产内联、来源引用和模型追问建议。按文件角色（法规/标准/招标公告/合同/话术）分化切分，子块服务问答与合规、父块服务正文写作；召回前先按 doc_role / 省份 / 批次过滤，避免跨类别、跨批次串扰。Embedding 默认百炼 `text-embedding-v4`，可切换本地 Ollama 开源模型。

→ [RAG 工程实现与评测](docs/rag/README.md) · [检索链路](docs/features/rag-knowledge-base.md)

### 6. AI 用量与成本透明
每次 LLM / Embedding / Rerank / OCR 调用均记录 Token 和人民币费用，按项目/阶段/模型汇总，支持多模型厂商适配。

→ [详细说明](docs/features/cost-tracking.md)

### 7. 正式 DOCX 标书导出
下载 Word 时优先使用在线工作台当前章节快照，避免数据库旧章节导致目录和正文不一致。导出目录采用正式 Word 目录样式，包含层级缩进、点线前导符和右侧页码。后端支持在导出最后一步调用 LibreOffice headless 重新保存 DOCX，自动刷新目录页码、页脚页码和总页数，用户下载的仍然是 `.docx` 文件。

→ [详细说明](docs/features/docx-export.md)

---

## 系统架构

```mermaid
flowchart LR
    U[用户浏览器] --> FE[Vite React 前端]
    FE --> API[Flask / Gunicorn API]

    API --> Storage[本地 Storage / 阿里云 OSS]
    API --> DB[(PostgreSQL / 阿里云 RDS)]
    DB --> Vec[(pgvector HNSW)]

    API --> Redis[(Redis / Celery Broker)]
    Redis --> Worker[Celery Worker]

    Worker --> Parser[文档解析与落库]
    Parser --> Native[原生文本抽取]
    Parser --> MinerU[MinerU OCR/版面解析]
    Parser --> DB
    Parser --> Vec
    Storage --> Parser

    API --> LLM[DeepSeek / DashScope LLM]
    Vec --> API
    Worker --> Docx[python-docx 生成 DOCX]
    Docx --> LO[LibreOffice 刷新目录页码]
    Worker --> DB
    LLM --> API

    FE --> Tiptap[Tiptap AI 章节编辑器]
    FE --> Office[ONLYOFFICE / 终稿编辑，可选]
```

**技术栈**：Flask/Gunicorn · Celery · Redis · React 18 · TypeScript · Ant Design 5 · Tiptap · PostgreSQL + pgvector（HNSW）· 本地 Storage / 阿里云 OSS · DeepSeek（写作）/ DashScope · Ollama（可选本地 Embedding）· MinerU

### 当前技术路径

```mermaid
sequenceDiagram
    participant FE as 前端工作台
    participant API as Flask/Gunicorn API
    participant Q as Redis 队列
    participant W as Celery Worker
    participant M as MinerU / 原生解析
    participant DB as PostgreSQL + pgvector
    participant LLM as DeepSeek / DashScope
    participant DOCX as DOCX 导出

    FE->>API: 上传招标文件
    API->>DB: 创建项目、文件和解析任务状态
    API->>Q: 投递解析任务
    API-->>FE: 返回 project_id / file_id
    W->>Q: 消费解析任务
    W->>M: PDF 走 MinerU，文本文件走原生抽取
    M-->>W: Markdown / 结构块 / 页码与版面信息
    W->>DB: 写入 bid_analysis / document_chunks / embedding
    FE->>API: 轮询 parse-status
    API-->>FE: indexed / hasAnalysis=true
    FE->>API: 生成 AI 报告、大纲、章节正文、合规检查
    API->>LLM: 解读 / 大纲 / 正文 / 语义复核
    API->>DB: 保存章节、大纲、合规结果
    FE->>API: 创建 DOCX 导出任务
    API->>Q: 投递导出任务
    W->>DOCX: 生成 Word 并刷新目录页码
    W->>DB: 写回导出任务 completed
    FE->>API: 轮询导出任务并下载 DOCX
```

生产与本地真实联调采用同一条主链路：**API 只负责接请求、校验、创建任务和查询状态；Celery worker 负责解析、MinerU 产物落库、大纲精炼、章节正文生成和 DOCX 导出等长任务**。因此 `/api/ready` 中 `checks.celery.status=ok` 是真实全链路冒烟的前置条件。

→ [文档中心](docs/README.md) · [完整架构说明](docs/architecture/overview.md)

---

## 快速开始

> 当前默认路线：本地 Docker PostgreSQL + pgvector，后续生产平移到阿里云 RDS PostgreSQL + OSS。Supabase 文档仅作为历史环境和迁移参考。

```bash
# 1. 创建并激活项目专属虚拟环境（不要复用 marker/MinerU 等其他环境，避免依赖冲突）
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装后端依赖
pip install -r requirements.txt

# 3. 安装并构建前端
cd frontend && npm install && npm run build && cd ..

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 DEEPSEEK_API_KEY、DASHSCOPE_API_KEY，并确认 DATABASE_URL
# 如需下载 DOCX 后目录页码直接准确，安装 LibreOffice 并确认 SOFFICE_BIN 路径

# 5. 启动本地 PostgreSQL 和 Redis
docker compose up -d postgres redis

# 6. 启动后端 Web（gunicorn，端口 3012；脚本会自动 source .env）
./scripts/dev_backend.sh

# 7. 另开一个终端启动 Celery worker（脚本会自动 source .env；默认并发 4、章节并行 3）
./scripts/dev_worker.sh

# 8. 另开一个终端启动前端开发服务（dev 代理已指向 127.0.0.1:3012）
cd frontend && npm run dev
```

> 三端缺一不可：只启 Web + 前端时 HTTP 能响应，但解析、章节正文生成、DOCX 导出等后台任务不会推进——它们都跑在 Celery worker 里。详见下方「本地三端启动」。

→ [完整部署文档](docs/deployment/quickstart.md) · [安全配置](docs/deployment/security.md) · [本地 Docker PostgreSQL](docs/deployment/local-postgres-docker.md) · [阿里云单 ECS 部署清单](docs/deployment/aliyun-ubuntu-single-ecs-deploy-checklist-20260622.md) · [阿里云运维交接手册](docs/deployment/aliyun-single-ecs-developer-operations-guide.md)

### 阿里云测试环境部署

阿里云单企业测试环境采用 Ubuntu 22.04 + Docker Compose + 单 ECS 形态，当前约定代码来源为 Gitee `feat/aliyun-test-readiness` 分支，公网入口为 `http://8.160.187.226`（80 端口）。开发人员或运维人员接手部署时，优先阅读：

- [阿里云 Ubuntu 单 ECS 测试部署操作清单](docs/deployment/aliyun-ubuntu-single-ecs-deploy-checklist-20260622.md)：从 ECS 初始化、Git 拉取、`.env`、Docker Compose、数据库初始化到真实验收的逐步执行清单。
- [阿里云单 ECS 部署与运维交接手册](docs/deployment/aliyun-single-ecs-developer-operations-guide.md)：面向日常发布、客户验收前强制干净发布、版本校验、缓存排障、备份和回滚。

客户验收或前端缓存异常时，必须按交接手册中的“强制干净发布”流程执行，确认 Git HEAD、`/api/health` 的后端 commit、`/build-info.json` 的前端 commit 三者一致。任何场景都不要执行 `docker compose down -v` 或删除业务数据 volume。

### 后端启动方式（团队统一规范）

> 本项目为多人协作开发。为保证本地、测试、生产环境行为一致，**统一使用 gunicorn 启动后端**，不再推荐 `python main.py`（Flask 开发服务器）。
> 原因：系统大量使用 SSE 流式响应（招标解读、大纲、正文、知识库问答都是长连接），Flask 自带的开发服务器是单进程、同步模型，多个流式连接会互相阻塞，且明确标注“不可用于生产”。gunicorn 的 gevent worker 才是和生产一致的运行模型。
>
> 重要：上传解析、MinerU 产物落库、大纲精炼、章节正文生成和 DOCX 导出依赖 Celery worker。只启动后端和前端时，HTTP 可以响应，但解析、正文生成、导出等后台任务不会推进。真实全链路冒烟或本地联调必须同时启动 Redis 和 Celery worker。

#### 本地三端启动（推荐，最佳实践）

本地开发需要三个常驻进程，各开一个终端，均在项目根目录执行。两个脚本都会自动 `source .env`，保证 Web 与 worker 环境一致（单一事实来源）。

```bash
# 前置：本地 PostgreSQL + Redis
docker compose up -d postgres redis

# 终端 1 —— 后端 Web（gunicorn + gevent，端口 3012，带 --reload）
./scripts/dev_backend.sh

# 终端 2 —— Celery worker（默认 CELERY_WORKER_CONCURRENCY=4、SECTION_GEN_CONCURRENCY=3）
./scripts/dev_worker.sh

# 终端 3 —— 前端开发服务（Vite，端口 5173，/api 代理到 127.0.0.1:3012）
cd frontend && npm run dev
```

要点与最佳实践：

| 维度 | 说明 |
| --- | --- |
| 环境一致性 | `dev_backend.sh` / `dev_worker.sh` 均 `set -a; source .env; set +a`，避免 Web 与 worker 环境变量分叉。`celery_app.py` 也做了防御性 `load_dotenv`，直接 `celery -A ...` 启动也能读到 .env。 |
| 改代码后是否需重启 | Web 带 `--reload`，改后端代码自动重载；**worker 无热重载，改 `backend/tasks/*` 或任务依赖的代码后必须重启 `dev_worker.sh`**。 |
| 并发度 | worker 并行编写章节数 = min(`SECTION_GEN_CONCURRENCY`, `CELERY_WORKER_CONCURRENCY`)。提速可调高，但受 DeepSeek 并发配额限制（429）。 |
| Worker 池（重要） | 默认 `CELERY_POOL=threads`。**不要在 macOS / 新版 Python 上用默认 prefork**：fork 已初始化线程的父进程会死锁，表现为"任务已 received 但永不执行、章节一直排队中"。任务以 IO 等待为主，threads 池最稳妥。 |
| 避免双 worker | 重启 worker 前确认旧进程已退出，否则两个 worker 抢同一 Redis 队列，旧代码可能接走任务。 |
| 验证 worker 代码已加载 | `.venv/bin/celery -A backend.tasks.celery_app:celery_app inspect registered \| grep generate_one`，看到 `bid.sections.generate_one` 即为最新代码。 |
| 健康检查 | `curl http://127.0.0.1:3012/api/ready`，确认 `checks.celery.status=ok`（worker 在线）。 |
| 故障排查：一直"排队中" | worker 日志只有 `Task ... received` 却无任务执行日志 = prefork fork 死锁。改用 threads 池（`dev_worker.sh` 已默认）后重启即可。 |

#### 1. 标准启动（推荐，所有人默认用这个）

```bash
source .venv/bin/activate
gunicorn -c gunicorn.conf.py main:app
```

- 配置文件：`gunicorn.conf.py`
- 默认监听：`http://0.0.0.0:8000`（本机访问用 `http://127.0.0.1:8000`）
- 默认 worker：4 个 `gevent` worker，单请求超时 300 秒（适配长章节生成）
- 启动成功会看到日志：`Starting gunicorn`、`Using worker: gevent`、`Booting worker ...`
- 健康检查：`curl http://127.0.0.1:8000/api/health` 返回 `{"status": "ok"}`

> 注意端口差异：gunicorn 默认走 **8000** 端口；旧的 `python main.py` 走的是 3012。改用 gunicorn 后，本地访问地址是 `http://127.0.0.1:8000`。如果前端 dev server 或调试脚本里写死了 3012，请同步改成 8000，或用下面的环境变量把 gunicorn 端口调成 3012。

#### 1.1 本地异步任务 worker（真实联调必开）

```bash
docker compose up -d redis
./scripts/dev_worker.sh
```

启动后检查：

```bash
curl http://127.0.0.1:3012/api/ready
```

`checks.celery.status` 应为 `ok`，并显示在线 worker 数量。若为 `warn: no Celery worker responded to ping`，上传后的解析状态会一直轮询，DOCX 导出任务也不会完成。

#### 1.2 真实全链路冒烟

真实冒烟应使用 PDF 样例并开启 MinerU 校验，确保覆盖“上传 → MinerU 解析/落库 → 结构化解读 → AI 报告 → 大纲 → 章节正文 → 合规检查 → DOCX 导出”完整链路。默认 Markdown 样例只适合脚本连通性检查，不足以验证 MinerU 和结构化解读落库。

```bash
.venv/bin/python scripts/smoke_key_flow.py \
  --base-url http://127.0.0.1:3012 \
  --timeout 900 \
  --username <本地测试账号> \
  --password <本地测试密码> \
  --sample-file "rag_seed/power_grid_resources/02_policy_regulations/03_必须招标的工程项目规定_a8122eb9.pdf" \
  --require-mineru \
  --report docs/development/runs
```

最近一次通过记录：`docs/development/runs/run_20260602_224815_http_smoke_passed.md`。该记录显示 Celery worker 在线、PDF 通过 MinerU 解析并落库、AI 报告/大纲/正文/合规/DOCX 导出全部完成。

#### 2. 本地调试：开启热重载

开发时希望改完代码自动重启，加 `--reload`：

```bash
source .venv/bin/activate
gunicorn -c gunicorn.conf.py --reload main:app
```

`--reload` 仅用于本地开发，生产环境不要开启。

#### 3. 通过环境变量调整启动参数

`gunicorn.conf.py` 的关键参数都支持环境变量覆盖，无需改代码：

| 环境变量 | 作用 | 默认值 |
| --- | --- | --- |
| `PORT` | 监听端口 | `8000` |
| `WEB_CONCURRENCY` / `GUNICORN_WORKERS` | worker 数量 | `4` |
| `GUNICORN_WORKER_CLASS` | worker 类型 | `gevent` |
| `GUNICORN_TIMEOUT` | 单请求超时（秒） | `300` |
| `GUNICORN_GRACEFUL_TIMEOUT` | 优雅退出超时（秒） | `30` |
| `LOG_LEVEL` | 日志级别 | `info` |

例如，想让本地 gunicorn 仍然监听 3012、只起 2 个 worker：

```bash
PORT=3012 WEB_CONCURRENCY=2 gunicorn -c gunicorn.conf.py main:app
```

#### 4. 容器 / 生产环境

Docker 镜像（`Dockerfile.backend`）已默认用 gunicorn 启动，无需手动操作：

```dockerfile
CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:app"]
```

容器内监听 8000，由 `docker-compose.yml` 映射到宿主机 `3012`（直连后端）或经 Nginx（当前阿里云入口为 80 端口）反代。生产环境必须启用一种访问控制（登录 / 静态令牌 / 仅本地），否则后端会拒绝启动，详见 [安全配置](docs/deployment/security.md)。

#### 关于 `python main.py`

`main.py` 末尾仍保留 `app.run(...)`，仅用于个别需要 Flask 原生调试器的临时场景；**团队协作和提交代码时一律以 gunicorn 为准**。两种方式加载的是同一个 `main:app` 对象，业务逻辑完全一致，区别只是启动器和默认端口（dev server 3012 / gunicorn 8000）。

#### 常见报错

- `ModuleNotFoundError: No module named 'psycopg'`（或其他包）：说明当前 Python 环境没装本项目依赖，通常是误用了其它虚拟环境（如 marker/MinerU 环境）。请激活项目的 `.venv` 后重新 `pip install -r requirements.txt`。

### 本地 Docker PostgreSQL

国内企业交付路线建议先在本机用 Docker PostgreSQL + pgvector 开发验证，后续平移到阿里云 RDS PostgreSQL + OSS。

```bash
docker compose up -d postgres
```

默认连接串：

```env
DATABASE_URL=postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding
```

### DeepSeek 写作模型

标书系统按业务阶段使用 DeepSeek 模型，通过 OpenAI-compatible 协议访问 `https://api.deepseek.com/chat/completions`。招标解读、分册大纲和 LLM 语义合规复核默认使用 `deepseek-v4-pro`，用于结构判断、风险识别和复杂推理；章节正文、章节补写、知识库问答和追问建议默认使用 `deepseek-v4-flash`，用于降低批量生成成本和提升响应速度。知识库向量化和 Rerank 默认仍使用 DashScope，因此本地和生产环境需要同时配置：

```env
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_INTERPRETATION_MODEL=deepseek-v4-pro
DEEPSEEK_INTERPRETATION_SEGMENT_MODEL=deepseek-v4-flash
DEEPSEEK_OUTLINE_MODEL=deepseek-v4-pro
DEEPSEEK_COMPLIANCE_MODEL=deepseek-v4-pro
DEEPSEEK_SECTION_WRITING_MODEL=deepseek-v4-flash
DEEPSEEK_SECTION_SUPPLEMENT_MODEL=deepseek-v4-flash
DEEPSEEK_KNOWLEDGE_MODEL=deepseek-v4-flash
DEEPSEEK_KNOWLEDGE_FOLLOWUP_MODEL=deepseek-v4-flash
REASONING_REQUEST_TIMEOUT_SECONDS=300
INTERPRETATION_SEGMENT_MAX_CHARS=24000
INTERPRETATION_SEGMENT_MAX_GROUPS=24
DASHSCOPE_API_KEY=your_dashscope_api_key
```

系统设置 - 模型配置中会展示每个业务模块当前使用的模型；解读、大纲和语义复核等 Pro 推理阶段默认允许 300 秒服务端超时，前端对应请求允许 360 秒，避免大文件解读时前端先报 `timeout of 120000ms exceeded`。招标文件正文分片数量较多或正文超过约 8 万字时，系统会自动启用“大文件分段解读”：先用 `DEEPSEEK_INTERPRETATION_SEGMENT_MODEL` 对文档分段抽取资格、评分、风险和材料要点，再用 `DEEPSEEK_INTERPRETATION_MODEL` 做最终融合去重；分段大小和最大段数由 `INTERPRETATION_SEGMENT_MAX_CHARS`、`INTERPRETATION_SEGMENT_MAX_GROUPS` 控制。用量与成本中心会按 `provider`、`model`、`stage` 记录历史调用。DeepSeek V4 Flash 成本种子脚本按客户提供的价格口径写入：输入缓存命中 0.02 元 / 百万 tokens、输入缓存未命中 1 元 / 百万 tokens、输出 2 元 / 百万 tokens；DeepSeek V4 Pro 按输入缓存命中 0.025 元 / 百万 tokens、输入缓存未命中 3 元 / 百万 tokens、输出 6 元 / 百万 tokens 写入。当前系统按缓存未命中输入价保守估算，最终仍以 DeepSeek 账单为准。

分册大纲落库采用“同项目串行锁 + 预生成章节 UUID + 批量写入 + 写入重试”的可靠性策略。规则版大纲、AI 精修大纲和前端重复流式请求都必须通过 `replace_bid_sections_from_outline()` 统一替换 `bid_sections`，避免网络抖动或并发 SSE 连接造成章节目录写入一半、被二次删除或 Word 导出目录错乱。当前实现仍处于从 Supabase SDK 向标准 PostgreSQL 数据访问层迁移的过程中，详细机制见 [章节大纲生成](docs/features/outline-generation.md)。

### Embedding 向量化服务（支持本地 Ollama 与百炼切换）

> ⚠️ **环境差异提醒（开发人员必读）**：知识库向量化（Embedding）的服务地址现已可配置。**本地开发机**与**阿里云测试/生产环境**的 Embedding 后端可能不同，切换时务必同步配置并按需重嵌，否则会出现召回失真。

Embedding 走 OpenAI 兼容协议，由 `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` 控制后端，默认仍是百炼，不影响既有部署：

| 场景 | `EMBEDDING_BASE_URL` | `DASHSCOPE_EMBEDDING_MODEL` | 说明 |
| --- | --- | --- | --- |
| 百炼（默认） | 留空 或 `https://dashscope.aliyuncs.com/compatible-mode/v1` | `text-embedding-v4` | 需 `DASHSCOPE_API_KEY`，按 token 计费 |
| 本地 Ollama（开发省额度） | `http://localhost:11434/v1` | `qwen3-embedding:0.6b` | 无需联网/付费，输出 1024 维，与 pgvector schema 对齐 |
| 容器内后端连宿主机 Ollama | `http://host.docker.internal:11434/v1` | `qwen3-embedding:0.6b` | Docker 内访问宿主机 Ollama |

本地 Ollama 启用步骤：

```bash
# 1. 启动 Ollama 并拉取 embedding 模型（与百炼 v4 同源，输出 1024 维）
ollama serve
ollama pull qwen3-embedding:0.6b

# 2. 在 .env 中切换 Embedding 后端
EMBEDDING_BASE_URL=http://localhost:11434/v1
EMBEDDING_API_KEY=                       # Ollama 不校验，可留空
DASHSCOPE_EMBEDDING_MODEL=qwen3-embedding:0.6b
DASHSCOPE_EMBEDDING_DIMENSIONS=1024

# 3. 验证返回维度为 1024
curl -s http://localhost:11434/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-embedding:0.6b","input":"测试"}' \
  | python3 -c "import sys,json;print('dim=',len(json.load(sys.stdin)['data'][0]['embedding']))"
```

关键约束：

- **换模型或换维度必须全量重嵌**。百炼 `text-embedding-v4` 与 Ollama `qwen3-embedding` 生成的向量不在同一空间，混用会导致召回失真。切换后需重跑入库（种子库父子分块 v2：`python scripts/rag/ingest_power_grid_v2.py`），把存量 chunk 用新模型重嵌，并重跑 `python scripts/rag/eval_recall.py` 确认召回未退化。
- **维度必须保持 1024**，与 `document_chunks.embedding vector(1024)` / `knowledge_assets.embedding vector(1024)` 一致；如要改维度需同步迁移向量列。
- `dimensions` 参数仅对百炼下发；Ollama 按模型默认维度输出（`qwen3-embedding:0.6b` 即 1024），系统已自动处理，无需手动区分。
- **生产/阿里云环境**默认仍用百炼（测试环境无开发机的 Ollama）。如需在阿里云上私有化向量化，应在 ECS 上用 vLLM/Ollama 自托管同款模型，并保证与开发期模型一致，避免再次重嵌。
- Rerank（`qwen3-rerank`）仍走百炼；它是 fail-open 增强项，额度问题不影响主召回链路。

### RAG 基座数据工程（分块 / 召回 / 评测）

知识库的召回质量不取决于“是否已向量化”，而取决于分块是否保留语义、召回是否定向过滤、是否有测试集持续验证。本项目据此落地了一套可复跑、可回归、可对外分享的 RAG 工程实践，完整记录见 [docs/rag/](docs/rag/README.md)。

#### 父子双层分块（Small-to-Big）

一份资料切一次，产出两层，解决“问答要小块、写作要大块”的矛盾：

- 子块（child）：按 doc_role 切到条/款/业务段级，小而自洽，参与向量召回、问答、合规判定；
- 父块（parent）：章/节级完整上下文，写作正文回溯用，`embedding` 置空、不参与召回因此不污染检索；
- 子块通过 `metadata.parent_index` 回溯父块。

切分按文件角色分化（法规/合同按“条”、标准按条文、招标公告按业务段、投标注意事项按风险条、话术按段落），不使用统一固定长度作主策略；入库前强制清洗网页导航噪声与采集元信息。实现见 `backend/rag/chunking.py`。

#### 场景化召回（metadata 过滤先行）

召回 RPC `match_knowledge_chunks_filtered` 支持 jsonb metadata 过滤 + `project_id` 隔离，按消费场景（问答 / 写作 / 合规）使用不同过滤条件与 top-k；向量索引为 HNSW（`m=16, ef_construction=64`），高频过滤字段建表达式索引。每个 chunk 携带 `doc_role / authority_level / citation_policy / chunk_layer / content_sha256` 等 metadata，支撑权威排序、引用边界控制与增量幂等。

#### Base 测试集与回归

`tests/rag/base_testset.jsonl` 按 qa / writing / compliance 三场景标注；`scripts/rag/eval_recall.py` 计算 Recall@k、来源类别准确率、关键词命中率与跨 doc_role 串扰，并支持有/无过滤 A/B 对比。**新批次资料入库后必须重跑回归，指标退化则阻断上线**，避免“越加资料、召回越差”。

第一版基线（power_grid 种子库，298 父块 + 2449 子块，Ollama `qwen3-embedding:0.6b`）：

| 指标 | 过滤 ON | 过滤 OFF |
| --- | --- | --- |
| Recall@5 | 86.7% | 80.0% |
| 来源类别准确率(top1) | 100% | 83.3% |
| 跨 doc_role 串扰均值 | 0% | 30% |

metadata 过滤把跨类别串扰从 30% 降到 0%、来源准确率升到 100%，验证了“过滤先行”的核心判断。详细评测与失败用例分析见 [评测记录](docs/rag/evaluation-records.md)。

> 切换 embedding 模型或维度后需用对应入库脚本全量重嵌（种子库 v2：`python scripts/rag/ingest_power_grid_v2.py`），再重跑 `eval_recall.py` 刷新基线。

### DOCX 目录页码刷新

`python-docx` 只能写入 Word 字段，不能计算真实页码。系统导出流程已集成 LibreOffice headless：`Markdown -> python-docx DOCX -> soffice DOCX 重新保存 -> 返回 DOCX`。开启后，目录 `PAGEREF`、页脚 `PAGE/NUMPAGES` 会在服务端刷新，避免下载后目录页码全部显示为 `1`。

```env
DOCX_REFRESH_FIELDS=true
SOFFICE_BIN=/opt/homebrew/bin/soffice
DOCX_REFRESH_TIMEOUT_SECONDS=180
```

Mac M1/M2 使用 Homebrew 安装通常是 `/opt/homebrew/bin/soffice`；Linux 服务器通常是 `/usr/bin/soffice`。如果服务器未安装 LibreOffice 或刷新失败，导出任务不会阻断，系统会保留 `w:updateFields=true` 和 `w:dirty=true`，由用户打开 Word 时刷新字段，同时在导出任务 metadata 中记录 `field_refresh` 报告。

---

## 文档导航

| 分类 | 文档 | 说明 |
| --- | --- | --- |
| 入口 | [文档中心](docs/README.md) | 新成员阅读顺序、文档分层、维护要求 |
| 架构 | [系统架构总览](docs/architecture/overview.md) | 技术栈、架构图、业务流程 |
| 架构 | [数据模型](docs/architecture/data-model.md) | 核心表、ER 图、对象存储目录/Bucket |
| 功能 | [章节大纲生成](docs/features/outline-generation.md) | 两阶段流式、知识库注入、章节数量规则 |
| 功能 | [全文篇幅设置](docs/features/length-settings.md) | 字数分配、权重计算、补写机制 |
| 功能 | [章节写作计划](docs/features/section-writing.md) | writing_plan 字段、生成时机 |
| 功能 | [合规检查](docs/features/compliance.md) | 规则覆盖率、LLM 语义复核 |
| 功能 | [RAG 知识库](docs/features/rag-knowledge-base.md) | 检索链路、分片策略、种子库 |
| 功能 | [RAG 工程实现与评测](docs/rag/README.md) | 父子分块、场景化召回、Base 测试集、评测记录 |
| 功能 | [分册设计](docs/features/volume-design.md) | 分册类型、正文生成策略 |
| 功能 | [成本统计](docs/features/cost-tracking.md) | Token 用量、多模型兼容 |
| 功能 | [DOCX 导出](docs/features/docx-export.md) | 正式目录、页码域、章节快照、Word 标题层级 |
| 交付 | [西北西藏架空绝缘导线招标文件测试资料准备说明](西北西藏架空绝缘导线招标文件测试资料准备说明.md) | 使用西北/西藏 1kV、10kV 架空绝缘导线招标包测试时，泰昌需补充的企业资料、产品资料、图片资产和资质文件 |
| 部署 | [快速开始](docs/deployment/quickstart.md) | 安装、配置、启动 |
| 部署 | [本地 Docker PostgreSQL](docs/deployment/local-postgres-docker.md) | 本地数据库、pgvector、Docker 资源建议 |
| 部署 | [阿里云单 ECS 测试部署操作清单](docs/deployment/aliyun-ubuntu-single-ecs-deploy-checklist-20260622.md) | ECS 初始化、代码拉取、Docker Compose 构建、清缓存发布、验收记录 |
| 部署 | [阿里云单 ECS 部署与运维交接手册](docs/deployment/aliyun-single-ecs-developer-operations-guide.md) | 开发/运维交接、强制干净发布、版本校验、备份与回滚 |
| 部署 | [Supabase 到 PostgreSQL 迁移](docs/deployment/supabase-to-postgres-migration.md) | 真实迁移流程、校验脚本、迁移记录 |
| 部署 | [阿里云目标架构](docs/deployment/aliyun-target-architecture.md) | RDS PostgreSQL + OSS 生产部署路线 |
| 部署 | [安全配置](docs/deployment/security.md) | CORS、认证、生产部署 |
| 部署 | [Supabase 初始化](docs/deployment/supabase-setup.md) | 历史环境和迁移参考 |
| 开发 | [API 接口参考](docs/development/api-reference.md) | 主要接口列表 |
| 开发 | [项目目录结构](docs/development/project-structure.md) | 代码组织说明 |
| 开发 | [文档制度](docs/development/documentation-standards.md) | 文档分层、维护时机、提交检查 |
| 开发 | [路线图](docs/development/roadmap.md) | P0-P5 规划、已完成任务 |

---

## 当前限制

- PDF 解析质量取决于文件类型，扫描版建议走 MinerU/OCR；客户标书的 `.doc`（老二进制）和 `.xlsx`（货物清单）结构化解析尚在补齐（见 [RAG 工程待办](docs/rag/todo.md)）。
- 电力/电网知识库应持续以国网招采文件、政策法规、技术规范、供应商资料和客户真实标书样本建设；新批次入库后需重跑 `scripts/rag/eval_recall.py` 做召回回归。
- 部分公开法规/规章种子文件存在来源页噪声或采集为占位页，需复核与重采，不应直接作为权威依据。
- 企业资质、人员、业绩、产品、设备、试验报告、运维案例等私有资料需投标企业自行提供并入库。招标文件包只代表招标方要求，不代表投标企业已具备相应能力。
- 不同物料包不能自动复用企业事实。以 1kV/10kV 架空绝缘导线测试包为例，若泰昌只提供电缆保护管资料，则系统不能据此生成泰昌已具备架空绝缘导线生产、检测、供货能力的正式响应。
- 数据访问层正在从 Supabase SDK 迁移到标准 PostgreSQL + 本地/OSS 存储抽象（通过 `DB_PROVIDER` / `STORAGE_PROVIDER` 切换）。
- 当前定位为单企业私有化 MVP。阿里云单 ECS 可用于测试和客户试用；正式公网生产需继续补齐 HTTPS、域名、备份演练、监控告警和权限审计。

---

## 使用范围

本项目为企业内部和单企业私有化交付项目，暂不按开源项目发布，也不提供公开商用许可证。对外交付、客户试用、源码分发或第三方部署前，应先确认授权范围、客户数据边界、密钥脱敏要求和投标主体资料边界。

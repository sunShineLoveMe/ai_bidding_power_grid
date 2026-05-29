# Gitee ai-bid 项目启动操作说明

> 适用场景：合作伙伴从 Gitee 仓库 `ai-bid` 拉取代码后，在本地或内网服务器快速搭建并跑通项目。
>
> 当前推荐路线：Docker PostgreSQL + pgvector + 本地文件存储 + DeepSeek 写作模型 + DashScope Embedding/Rerank。
>
> 注意：`sql/` 目录里有部分 Supabase 历史脚本，不要直接整目录执行。新环境初始化优先使用 `migrations/postgres/` 下的 PostgreSQL schema。

## 1. 环境要求

### 1.1 必装软件

| 软件 | 建议版本 | 用途 |
| --- | --- | --- |
| Git | 2.30+ | 拉取 Gitee 代码 |
| Python | 3.9+ | 运行 Flask 后端和入库脚本 |
| Node.js | 18+ | 构建 React 前端 |
| npm | 9+ | 安装前端依赖 |
| Docker Desktop / Docker Engine | 最新稳定版 | 启动 PostgreSQL + pgvector |
| LibreOffice | 可选，建议安装 | 服务端刷新 DOCX 目录页码 |

### 1.2 Docker 资源建议

本地开发或演示：

```text
CPU: 4-6 核
Memory: 12-16 GB
Swap: 4 GB
Disk: 100-200 GB
```

大量导入知识库、图片资产、历史标书时，建议临时提高到：

```text
CPU: 8 核
Memory: 24 GB
Disk: 200 GB+
```

### 1.3 必备外部服务密钥

至少准备：

| 密钥 | 是否必需 | 用途 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 必需 | 招标解读、大纲、正文生成、合规复核、知识库问答 |
| `DASHSCOPE_API_KEY` | 必需 | 知识库向量化、图片资产向量化、Rerank |
| `MINERU_API_TOKEN` | 可选 | 扫描版 PDF / 复杂 PDF OCR 解析 |
| `ONLYOFFICE_JWT_SECRET` | 可选 | 使用 OnlyOffice 终稿编辑时需要 |

没有 `DASHSCOPE_API_KEY` 时，后端可以启动，但水利基础知识库入库和向量检索会失败。

## 2. 拉取代码

将下面地址替换为实际 Gitee 仓库地址：

```bash
git clone https://gitee.com/<owner>/ai-bid.git
cd ai-bid
```

确认当前分支：

```bash
git status --short --branch
```

建议首次部署固定使用 `main`：

```bash
git checkout main
```

## 3. 后端环境安装

### macOS / Linux

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

验证 Python 依赖：

```bash
python -m py_compile main.py
```

## 4. 前端环境安装与构建

```bash
cd frontend
npm install
npm run build
cd ..
```

构建成功后会生成 `frontend/dist/`。该目录是本地构建产物，不需要提交到 Git。

## 5. 配置环境变量

复制示例配置：

```bash
cp .env.example .env
```

打开 `.env`，至少确认以下配置。

### 5.1 本地开发 / 演示推荐配置

```ini
APP_ENV=development
APP_HOST=127.0.0.1:3012
APP_PUBLIC_BASE_URL=http://127.0.0.1:3012
APP_CORS_ORIGINS=http://127.0.0.1:3012,http://localhost:3012,http://127.0.0.1:5173,http://localhost:5173
APP_LOCAL_ONLY=false
APP_LOGIN_ENABLED=true
APP_SESSION_SECRET=replace_with_a_random_session_secret_at_least_24_chars
APP_COOKIE_SECURE=false
APP_AUTH_ENABLED=false
APP_EXPOSE_DEBUG_ERRORS=false
REQUIRE_STRICT_CONFIG=false
PORT=3012
FLASK_DEBUG=false
```

### 5.2 模型配置

```ini
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=填写真实 DeepSeek Key
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

DASHSCOPE_API_KEY=填写真实 DashScope Key
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
DASHSCOPE_EMBEDDING_DIMENSIONS=1024
DASHSCOPE_RERANK_ENABLED=true
DASHSCOPE_RERANK_MODEL=qwen3-rerank
DASHSCOPE_RERANK_TOP_N=6
DASHSCOPE_REQUEST_TIMEOUT_SECONDS=120
DASHSCOPE_STREAM_CONNECT_TIMEOUT_SECONDS=15
DASHSCOPE_STREAM_READ_TIMEOUT_SECONDS=180
DASHSCOPE_MAX_RETRIES=2
DASHSCOPE_RETRY_BASE_DELAY_SECONDS=1.5
DASHSCOPE_RETRY_MAX_DELAY_SECONDS=12
DASHSCOPE_RETRY_STATUS_CODES=429,500,502,503,504
REASONING_REQUEST_TIMEOUT_SECONDS=300
INTERPRETATION_SEGMENT_MAX_CHARS=24000
INTERPRETATION_SEGMENT_MAX_GROUPS=24
AI_USAGE_USD_TO_CNY_RATE=7.2
```

### 5.3 PostgreSQL / 本地存储配置

```ini
DB_PROVIDER=postgres
DATABASE_URL=postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding
STORAGE_PROVIDER=local
LOCAL_STORAGE_ROOT=storage
```

本地文件会写入 `storage/`、`uploads/`、`outputs/`、`parsed_outputs/` 等目录，这些目录已被 `.gitignore` 忽略。

### 5.4 水利演示企业画像

如果本次要演示水利行业，建议把 `.env` 里的企业画像从电力示例改为水利示例：

```ini
ENTERPRISE_NAME=某水利工程建设企业
ENTERPRISE_REGION=华中地区
ENTERPRISE_INDUSTRY=水利水电工程施工、检测、信息化建设与运行维护
ENTERPRISE_BUSINESS_SCOPE=水库除险加固、河道治理、泵站水闸工程、灌区节水改造、水利信息化、施工检测、运行维护和资料交付
ENTERPRISE_ADVANTAGES=具备水利工程施工组织、质量安全管理、设备与材料供应、试验检测、现场协调、缺陷责任期服务和资料归档能力
ENTERPRISE_TARGET_CUSTOMERS=水利厅局、水务局、流域管理机构、地方水利建设单位、公共资源交易项目招标人
ENTERPRISE_RESPONSE_STYLE=专业、严谨、合规、可落地；不得编造资质证书编号、人员姓名、业绩合同金额、具体日期和未提供的企业证明材料
```

后续也可以在系统设置页面维护企业画像。

### 5.5 MinerU OCR 可选配置

如果需要处理扫描版 PDF 或复杂版式 PDF：

```ini
MINERU_API_TOKEN=填写真实 MinerU Token
MINERU_API_BASE_URL=https://mineru.net
MINERU_PARSE_PDF_FIRST=true
MINERU_DOWNLOAD_AUTO_RETRIES=6
MINERU_DOWNLOAD_USE_CURL_FALLBACK=true
MINERU_DOWNLOAD_DOH_RESOLVE=true
```

没有 MinerU 时，普通文本型 PDF / DOCX 仍可走本地解析能力，但扫描件质量会受影响。

### 5.6 LibreOffice 可选配置

用于导出 DOCX 后刷新目录页码、页脚页码和总页数。

macOS Apple Silicon 常见路径：

```ini
DOCX_REFRESH_FIELDS=true
SOFFICE_BIN=/opt/homebrew/bin/soffice
DOCX_REFRESH_TIMEOUT_SECONDS=180
```

Linux 常见路径：

```ini
DOCX_REFRESH_FIELDS=true
SOFFICE_BIN=/usr/bin/soffice
DOCX_REFRESH_TIMEOUT_SECONDS=180
```

未安装 LibreOffice 时，DOCX 导出不会被阻断，但目录页码可能需要用户打开 Word 后手动刷新。

## 6. 启动 PostgreSQL

启动容器：

```bash
docker compose up -d postgres
```

查看状态：

```bash
docker compose ps postgres
```

健康状态应为 `healthy`。如果不是，查看日志：

```bash
docker compose logs postgres
```

验证扩展：

```bash
docker compose exec postgres psql -U bidding -d bidding -c "select extname from pg_extension where extname in ('pgcrypto','vector') order by extname;"
```

期望输出包含：

```text
pgcrypto
vector
```

## 7. 初始化 PostgreSQL 业务表

> 重要：`docker compose up -d postgres` 只会创建数据库和扩展，不会自动创建全部业务表。

推荐直接执行初始化脚本，脚本会按固定顺序执行主 schema、登录表扩展和 DeepSeek 成本价格种子，并在最后验证核心表：

```bash
scripts/init_postgres_schema.sh
```

如果需要手工排障，等价执行顺序如下：

```bash
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/001_schema.sql
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/002_app_login.sql
docker compose exec -T postgres psql -U bidding -d bidding < sql/20260510_seed_deepseek_v4_flash_pricing.sql
docker compose exec -T postgres psql -U bidding -d bidding < sql/20260510_seed_deepseek_v4_pro_pricing.sql
```

验证核心表是否存在：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select table_name from information_schema.tables where table_schema='public' and table_name in ('bid_projects','bid_files','bid_analysis','bid_sections','knowledge_documents','document_chunks','knowledge_assets','app_users','ai_usage_logs','bid_generation_tasks','bid_export_tasks') order by table_name;"
```

期望至少看到：

```text
ai_usage_logs
app_users
bid_analysis
bid_export_tasks
bid_files
bid_generation_tasks
bid_projects
bid_sections
document_chunks
knowledge_assets
knowledge_documents
```

如果表不存在，先不要启动后端，回到本节重新执行 schema。

## 8. 导入水利基础数据

水利基础数据分三类：

| 数据目录 | 内容 | 导入目标 |
| --- | --- | --- |
| `rag_seed/water_resources/` | 水利招投标公开资料、法规、标准话术 | `knowledge_documents` / `document_chunks` |
| `rag_seed/water_enterprise_mock/` | 脱敏企业画像、资信、产品服务、能力说明 | `knowledge_documents` / `document_chunks` |
| `rag_seed/water_asset_images/` | 水利产品图、资信样张、工程示意图 | `knowledge_assets` + 本地 `storage/` |

导入前确认 `.env` 中：

```ini
DB_PROVIDER=postgres
STORAGE_PROVIDER=local
DATABASE_URL=postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding
LOCAL_STORAGE_ROOT=storage
DASHSCOPE_API_KEY=真实 DashScope Key
```

激活 Python 虚拟环境：

```bash
source venv/bin/activate
```

Windows PowerShell：

```powershell
venv\Scripts\activate
```

### 8.1 导入水利 RAG 基础知识库

```bash
python rag_seed/water_resources/_scripts/ingest_water_rag_seed.py
```

成功后会生成或更新：

```text
rag_seed/water_resources/ingestion_report.md
rag_seed/water_resources/ingestion_report.json
```

参考历史规模：

```text
有效资料：26 份
向量分片：约 558 条
```

### 8.2 导入水利脱敏企业资料

```bash
python rag_seed/water_enterprise_mock/_scripts/ingest_enterprise_mock_seed.py
```

成功后会生成或更新：

```text
rag_seed/water_enterprise_mock/ingestion_report.md
rag_seed/water_enterprise_mock/ingestion_report.json
```

### 8.3 导入水利图片资产库

```bash
python rag_seed/water_asset_images/_scripts/ingest_knowledge_assets.py
```

成功后会生成或更新：

```text
rag_seed/water_asset_images/ingestion_report.json
```

图片文件会复制到本地：

```text
storage/knowledge-assets/
```

### 8.4 验证入库结果

查看知识文档、分片、图片资产数量：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select 'knowledge_documents=' || count(*) from public.knowledge_documents union all select 'document_chunks=' || count(*) from public.document_chunks union all select 'knowledge_assets=' || count(*) from public.knowledge_assets;"
```

查看水利数据分类：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -c "select category, count(*) from public.knowledge_documents group by category order by category;"
```

查看向量是否生成：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select 'chunk_embeddings=' || count(*) from public.document_chunks where embedding is not null union all select 'asset_embeddings=' || count(*) from public.knowledge_assets where embedding is not null;"
```

如果 `embedding` 数量为 0，优先检查 `DASHSCOPE_API_KEY` 是否正确。

## 9. 启动后端

确保虚拟环境已激活：

```bash
source venv/bin/activate
```

启动：

```bash
python main.py
```

默认访问：

```text
http://127.0.0.1:3012
```

后端启动成功时，终端会显示 Flask 服务监听地址。

如果端口被占用，可以在 `.env` 中修改：

```ini
PORT=3013
APP_HOST=127.0.0.1:3013
APP_PUBLIC_BASE_URL=http://127.0.0.1:3013
APP_CORS_ORIGINS=http://127.0.0.1:3013,http://localhost:3013,http://127.0.0.1:5173,http://localhost:5173
```

然后重新启动：

```bash
python main.py
```

## 10. 前端开发模式可选

如果只需要使用后端托管的构建产物，完成 `npm run build` 后直接访问 `http://127.0.0.1:3012` 即可。

如果需要前端热更新开发：

```bash
cd frontend
npm run dev
```

默认 Vite 地址通常是：

```text
http://127.0.0.1:5173
```

此时后端仍需要单独运行：

```bash
python main.py
```

## 11. 登录与账号

当前 `.env.example` 默认：

```ini
APP_LOGIN_ENABLED=true
```

首次进入页面时按前端页面提示注册或登录。账号信息会写入 PostgreSQL：

```text
public.app_users
```

如果登录相关表报错，确认已执行：

```bash
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/002_app_login.sql
```

## 12. 跑通验收流程

### 12.1 基础健康检查

访问：

```text
http://127.0.0.1:3012
```

确认页面正常打开，无 500 报错。

### 12.2 数据库检查

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select 'bid_projects=' || count(*) from public.bid_projects union all select 'knowledge_documents=' || count(*) from public.knowledge_documents union all select 'document_chunks=' || count(*) from public.document_chunks union all select 'knowledge_assets=' || count(*) from public.knowledge_assets;"
```

初始项目数可以为 0，但水利种子导入后 `knowledge_documents`、`document_chunks`、`knowledge_assets` 应大于 0。

### 12.3 上传招标文件测试

可使用测试样本：

```text
test_samples/water_tender_docs/
```

建议测试顺序：

1. 上传较小或结构清晰的 PDF / DOCX，验证解析和项目创建。
2. 进入招标解读，验证 DeepSeek 调用。
3. 生成分册大纲，验证章节落库。
4. 生成单个章节正文，验证 RAG 检索和写作模型。
5. 运行合规检查，验证规则覆盖率和 LLM 语义复核。
6. 导出 Word，验证 DOCX 下载。

### 12.4 知识库问答测试

进入知识库问答或相关入口，提问：

```text
水库除险加固工程投标文件通常需要哪些资格审查材料？
```

如果水利 RAG 已入库，回答应能引用水利投标、法规或标准话术相关内容。

## 13. 常用维护命令

### 查看 PostgreSQL 状态

```bash
docker compose ps postgres
docker compose logs postgres
```

### 进入数据库

```bash
docker compose exec postgres psql -U bidding -d bidding
```

### 停止数据库

```bash
docker compose stop postgres
```

### 重新启动数据库

```bash
docker compose start postgres
```

### 查看本地数据目录大小

```bash
du -sh storage uploads outputs parsed_outputs logs 2>/dev/null
```

### 后端测试

```bash
python -m unittest discover -s tests
```

### 后端语法检查

```bash
python -m py_compile main.py backend/api/routes.py backend/parsing/document_parser.py backend/export/md_to_word.py
```

## 14. 重新初始化空库

> 危险操作：会删除 PostgreSQL 容器 volume 中的全部数据。只适合本地测试环境。

停止并删除数据库 volume：

```bash
docker compose down -v
```

重新启动：

```bash
docker compose up -d postgres
```

然后重新执行：

```bash
scripts/init_postgres_schema.sh
python rag_seed/water_resources/_scripts/ingest_water_rag_seed.py
python rag_seed/water_enterprise_mock/_scripts/ingest_enterprise_mock_seed.py
python rag_seed/water_asset_images/_scripts/ingest_knowledge_assets.py
```

## 15. 推送到 Gitee 的注意事项

不要提交以下内容：

```text
.env
venv/
frontend/node_modules/
frontend/dist/
storage/
uploads/
outputs/
parsed_outputs/
logs/
chroma_db/
bidding.db
migration_reports/
config/runtime_settings.json
```

这些已经在 `.gitignore` 中，但推送前仍建议检查：

```bash
git status --short --ignored
```

确认没有真实密钥：

```bash
git grep -n "DEEPSEEK_API_KEY\\|DASHSCOPE_API_KEY\\|SUPABASE_SERVICE_ROLE_KEY\\|MINERU_API_TOKEN\\|ONLYOFFICE_JWT_SECRET"
```

只应看到 `.env.example` 或文档中的占位示例，不应出现真实 key。

添加 Gitee 远程仓库：

```bash
git remote add gitee https://gitee.com/<owner>/ai-bid.git
```

推送：

```bash
git push -u gitee main
```

如果已经存在 `gitee` remote：

```bash
git remote -v
git push gitee main
```

## 16. 常见问题

### 16.1 `connection refused` 或连不上 `127.0.0.1:15432`

原因：PostgreSQL 容器未启动或端口被占用。

处理：

```bash
docker compose ps postgres
docker compose logs postgres
docker compose up -d postgres
```

### 16.2 `extension "vector" is not available`

原因：没有使用 `pgvector/pgvector:pg16` 镜像，或数据库初始化异常。

处理：

```bash
docker compose ps postgres
docker compose logs postgres
```

确认 `docker-compose.yml` 中镜像为：

```yaml
image: pgvector/pgvector:pg16
```

### 16.3 业务表不存在

现象：后端报 `relation "bid_projects" does not exist`、`relation "knowledge_documents" does not exist` 等。

处理：

```bash
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/001_schema.sql
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/002_app_login.sql
```

### 16.4 水利知识库为空

原因：只初始化了表，没有跑种子入库脚本。

处理：

```bash
python rag_seed/water_resources/_scripts/ingest_water_rag_seed.py
python rag_seed/water_enterprise_mock/_scripts/ingest_enterprise_mock_seed.py
python rag_seed/water_asset_images/_scripts/ingest_knowledge_assets.py
```

### 16.5 入库脚本提示 DashScope 相关错误

原因：`DASHSCOPE_API_KEY` 未配置、无权限、余额不足或网络无法访问 DashScope。

处理：

1. 检查 `.env` 中 `DASHSCOPE_API_KEY`。
2. 确认当前终端在项目根目录执行脚本。
3. 确认虚拟环境已激活。
4. 重新执行入库脚本。

### 16.6 DeepSeek 生成失败

原因：`DEEPSEEK_API_KEY` 未配置、模型名错误、余额不足、网络异常或请求超时。

处理：

1. 检查 `.env` 中 `DEEPSEEK_API_KEY`。
2. 确认 `DEEPSEEK_BASE_URL=https://api.deepseek.com`。
3. 确认模型名仍可用。
4. 大文件解读时可适当调大 `REASONING_REQUEST_TIMEOUT_SECONDS`。

### 16.7 DOCX 导出成功但目录页码不正确

原因：服务器未安装 LibreOffice，或 `SOFFICE_BIN` 路径错误。

处理：

```bash
soffice --version
```

macOS 可检查：

```bash
/opt/homebrew/bin/soffice --version
```

Linux 可检查：

```bash
/usr/bin/soffice --version
```

然后修正 `.env`：

```ini
DOCX_REFRESH_FIELDS=true
SOFFICE_BIN=/实际/soffice/路径
DOCX_REFRESH_TIMEOUT_SECONDS=180
```

### 16.8 前端跨域失败

原因：前端访问地址没有加入 `APP_CORS_ORIGINS`。

处理：

```ini
APP_CORS_ORIGINS=http://127.0.0.1:3012,http://localhost:3012,http://127.0.0.1:5173,http://localhost:5173
```

如果部署到内网服务器，例如 `192.168.1.20`：

```ini
APP_CORS_ORIGINS=http://192.168.1.20:3012,http://192.168.1.20:5173
APP_PUBLIC_BASE_URL=http://192.168.1.20:3012
```

修改 `.env` 后重启后端。

## 17. 首次交付检查清单

交付前逐项确认：

- [ ] Gitee 仓库已推送 `main` 分支。
- [ ] `.env` 未提交到仓库。
- [ ] 合作伙伴已拿到单独发送的 `.env` 配置或密钥填写说明。
- [ ] Docker PostgreSQL 启动正常。
- [ ] `pgcrypto` 和 `vector` 扩展存在。
- [ ] `migrations/postgres/001_schema.sql` 已执行。
- [ ] `migrations/postgres/002_app_login.sql` 已执行。
- [ ] DeepSeek 价格种子 SQL 已执行。
- [ ] 水利 RAG 文档已导入。
- [ ] 水利脱敏企业资料已导入。
- [ ] 水利图片资产已导入。
- [ ] `knowledge_documents`、`document_chunks`、`knowledge_assets` 数量大于 0。
- [ ] 后端 `python main.py` 可启动。
- [ ] 前端页面可访问。
- [ ] 可注册/登录。
- [ ] 可上传招标文件。
- [ ] 可执行招标解读。
- [ ] 可生成分册大纲。
- [ ] 可生成章节正文。
- [ ] 可导出 DOCX。

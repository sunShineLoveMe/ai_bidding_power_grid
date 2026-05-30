# 快速开始

> 安全配置详见 [security.md](./security.md)，本地数据库详见 [local-postgres-docker.md](./local-postgres-docker.md)，阿里云目标架构详见 [aliyun-target-architecture.md](./aliyun-target-architecture.md)。

当前项目默认面向电力/电网侧改造与国内企业交付。本地开发使用 Docker PostgreSQL + pgvector + 本地文件存储；生产目标为阿里云 RDS PostgreSQL + OSS。Supabase 相关文档仅作为历史环境和迁移参考。

## 前置检查清单

在跑起来之前务必完成这 4 件事：

1. **安装 Docker Desktop**，并按团队建议分配 6 CPU / 16 GB Memory / 4 GB Swap / 200 GB Disk。
2. **启动本地 PostgreSQL**：执行 `docker compose up -d postgres`。
3. **配置 `.env`**：至少确认 `DATABASE_URL`、`DB_PROVIDER`、`STORAGE_PROVIDER`、`LOCAL_STORAGE_ROOT`。
4. **配置模型密钥**：填写 `DEEPSEEK_API_KEY` 和 `DASHSCOPE_API_KEY`。

常见症状速查：

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `connection refused` 或连不上 `127.0.0.1:15432` | PostgreSQL 容器未启动 | `docker compose up -d postgres` |
| Docker Desktop 容器列表为空 | Docker 重启后容器未恢复或数据被清理 | 在项目根目录重新执行 `docker compose up -d postgres` |
| `extension "vector" is not available` | 没有使用 pgvector 镜像或初始化失败 | 确认镜像为 `pgvector/pgvector:pg16` |
| 模型调用失败 | 未配置模型 API Key | 检查 `DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY` |
| DOCX 目录页码不刷新 | 未配置 LibreOffice | 检查 `DOCX_REFRESH_FIELDS` 和 `SOFFICE_BIN` |

## 快速开始

### 1. 安装后端依赖

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 安装并构建前端

```bash
cd frontend
npm install
npm run build
cd ..
```

### 2.1 启动本地 PostgreSQL

```bash
docker compose up -d postgres
docker compose ps postgres
```

默认连接串：

```env
DATABASE_URL=postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding
```

验证扩展：

```bash
docker compose exec postgres psql -U bidding -d bidding -c "select extname from pg_extension where extname in ('pgcrypto','vector') order by extname;"
```

前端开发模式：

```bash
cd frontend
npm run dev
```

### 2.2 运行后端 MVP 测试

项目已提供第一版后端 MVP 测试，覆盖健康检查、上传文件类型拦截、MinerU 解析失败状态透出、MinerU zip 导入、DOCX 导出格式回归、章节 API 参数校验和合规覆盖基础口径。测试不依赖真实 DashScope、MinerU 或 Supabase 调用，适合开发、实施和交付前快速检查主链路是否被破坏。

```bash
python -m unittest discover -s tests
```

建议每次修改后端核心链路后至少执行：

```bash
python -m py_compile backend/api/routes.py backend/parsing/document_parser.py backend/parsing/mineru_client.py backend/export/md_to_word.py
python -m unittest discover -s tests
```

当前测试文件：

| 文件 | 覆盖内容 |
| --- | --- |
| `tests/test_smoke.py` | Flask 健康检查、非法招标文件上传拦截、MinerU 下载失败状态字段、DOCX 失效图片降级 |
| `tests/test_docx_export.py` | DOCX 正式文本清理、表格保留、图片插入上限和跳过报告 |
| `tests/test_api_sections.py` | 章节 API 参数校验、保存、排序、导出任务非法参数 |
| `tests/test_mineru_status.py` | MinerU 手动导入失败状态、断点续传 Range、有效 zip 产物识别 |
| `tests/test_compliance.py` | 正文命中后覆盖率提升、高风险缺失项识别、内部分册统计和商务包兼容口径 |
| `tests/test_rag_retrieval.py` | RAG 文本召回、图片资产向量召回、关键词兜底、来源和图片 Prompt 组装 |
| `tests/test_rag_asset_scoring.py` | 技术标/资格文件/商务文件的企业产品库、资信库和图片资产匹配策略 |

### 3. 配置环境变量

复制示例文件：

```bash
cp .env.example .env
```

当前 `.env.example` 已覆盖模型、PostgreSQL、对象存储迁移目标、MinerU、OnlyOffice、上传限制、安全开关、存储路径、企业画像和 Token 成本汇率。生产或客户环境至少需要重点确认以下配置：

```ini
# App / Security
APP_ENV=development
APP_CORS_ORIGINS=http://127.0.0.1:3012,http://localhost:3012,http://127.0.0.1:5173,http://localhost:5173
APP_LOCAL_ONLY=false
APP_LOGIN_ENABLED=true
APP_SESSION_SECRET=replace_with_a_random_session_secret_at_least_24_chars
APP_SESSION_EXPIRES_HOURS=72
APP_COOKIE_SECURE=false
APP_AUTH_ENABLED=false
APP_AUTH_TOKEN=replace_with_a_random_token_at_least_24_chars
APP_EXPOSE_DEBUG_ERRORS=false
REQUIRE_STRICT_CONFIG=false
LOG_LEVEL=INFO
MAX_UPLOAD_MB=200
ALLOWED_TENDER_EXTENSIONS=pdf,doc,docx,txt,md
ALLOWED_KNOWLEDGE_EXTENSIONS=pdf,doc,docx,txt,md,xls,xlsx,csv,png,jpg,jpeg,webp
ALLOWED_ASSET_EXTENSIONS=png,jpg,jpeg,webp,pdf,doc,docx

# LLM / Embedding / Rerank
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_KNOWLEDGE_MODEL=deepseek-v4-flash
DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_MODEL=qwen-turbo-latest
DASHSCOPE_KNOWLEDGE_MODEL=qwen-long
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
AI_USAGE_USD_TO_CNY_RATE=7.2

# PostgreSQL / Object Storage
DB_PROVIDER=postgres
DATABASE_URL=postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding
STORAGE_PROVIDER=local
LOCAL_STORAGE_ROOT=storage

# MinerU，可选
MINERU_API_TOKEN=your_mineru_api_token
MINERU_API_BASE_URL=https://mineru.net
MINERU_PARSE_PDF_FIRST=true
MINERU_DOWNLOAD_AUTO_RETRIES=6
MINERU_DOWNLOAD_USE_CURL_FALLBACK=true
MINERU_DOWNLOAD_DOH_RESOLVE=true

# App
APP_HOST=127.0.0.1:3012
APP_PUBLIC_BASE_URL=http://127.0.0.1:3012
UPLOAD_DIR=uploads/
OUTPUT_DIR=outputs/
BACKUP_DIR=backups/
WORD_TEMPLATE_PATH=templates/default_bid_template.docx

# DOCX 导出页码刷新，可选但生产建议配置
DOCX_REFRESH_FIELDS=true
SOFFICE_BIN=/opt/homebrew/bin/soffice
DOCX_REFRESH_TIMEOUT_SECONDS=180

# 企业画像，可选；也可在系统设置页面维护
ENTERPRISE_NAME=某电力工程服务企业
ENTERPRISE_REGION=华北地区
ENTERPRISE_INDUSTRY=电力工程建设、设备供货、运维检修与技术服务
ENTERPRISE_BUSINESS_SCOPE=输变电工程、配网工程、电力设备供货、安装调试、试验检测、运维检修、技术服务和项目交付保障
ENTERPRISE_ADVANTAGES=具备电力项目响应、质量安全管理、设备供应链协同、现场施工组织、调试试验、运维服务和资料交付能力
ENTERPRISE_TARGET_CUSTOMERS=国家电网、南方电网、发电集团、电力建设单位、工业园区和能源类企业
ENTERPRISE_RESPONSE_STYLE=专业、严谨、合规、可落地；不得编造资质证书编号、人员姓名、业绩合同金额、具体日期和未提供的企业证明材料

# ONLYOFFICE，可选
ONLYOFFICE_DOCS_API_URL=http://127.0.0.1:8080/web-apps/apps/api/documents/api.js
ONLYOFFICE_JWT_SECRET=replace_with_a_strong_secret
BACKEND_URL_FOR_DOCKER=host.docker.internal:3012
```

模型、Embedding、超时时间、OnlyOffice 地址、存储目录和企业画像等非敏感配置也可以在「系统设置」页面调整。页面保存后会写入本地 `config/runtime_settings.json`，后端在下一次模型请求时读取该配置；该文件已加入 `.gitignore`，开源时只保留 `config/runtime_settings.example.json`。API Key、数据库连接串、对象存储密钥等敏感项仍必须通过 `.env` 配置，不会保存在前端。

DeepSeek 写作模型通过 OpenAI-compatible 协议调用 `https://api.deepseek.com/chat/completions`，默认模型为 `deepseek-v4-flash`。知识库向量化和 Rerank 默认仍使用 DashScope，因此切换写作模型时不要删除 `DASHSCOPE_API_KEY`。DeepSeek/DashScope 文本调用共用基础重试与退避策略：普通文本生成和流式生成默认最多重试 2 次，遇到 `429,500,502,503,504`、连接异常或超时会按指数退避等待后重试；流式接口如果已经向前端输出了部分正文，则不会自动重试，避免重复拼接正文。相关参数可通过 `DASHSCOPE_MAX_RETRIES`、`DASHSCOPE_RETRY_BASE_DELAY_SECONDS`、`DASHSCOPE_RETRY_MAX_DELAY_SECONDS`、`DASHSCOPE_RETRY_STATUS_CODES` 和各类 timeout 配置调整。重试次数、是否最终成功、是否属于可重试错误会写入 AI 用量日志的 `metadata`，便于后续在「用量与成本」中审计单次标书生成的稳定性。

### 3.1 安装 LibreOffice 用于 DOCX 目录页码刷新

系统下载标书时最终仍返回 `.docx`。由于 `python-docx` 无法计算真实页码，后端会在生成 DOCX 后调用 LibreOffice headless 重新保存一次 DOCX，用来刷新目录页码、页脚页码和总页数。

Mac M1/M2：

```bash
brew install --cask libreoffice
which soffice
```

常见路径：

```text
/opt/homebrew/bin/soffice
```

Linux 服务器：

```bash
sudo apt-get update
sudo apt-get install -y libreoffice
which soffice
```

常见路径：

```text
/usr/bin/soffice
```

`.env` 推荐配置：

```ini
DOCX_REFRESH_FIELDS=true
SOFFICE_BIN=/opt/homebrew/bin/soffice
DOCX_REFRESH_TIMEOUT_SECONDS=180
```

验证命令：

```bash
soffice --version
```

如果 `SOFFICE_BIN` 未配置，后端会优先从 PATH 查找 `soffice`，再兜底检查 `/Applications/LibreOffice.app/Contents/MacOS/soffice`。如果服务器没有安装 LibreOffice，导出不会失败，但目录页码可能需要用户打开 Word 后手动刷新。

### 4. 启动后端

```bash
python main.py
```

默认访问：

```text
http://127.0.0.1:3012
```

## 在线编辑器

### 主编辑器：Tiptap（默认）

标书编制工作台默认使用 Tiptap / ProseMirror 作为 AI 章节编辑器。

特点：
- 纯前端方案，无需 Docker 部署
- 内容保存仍采用 Markdown，便于 AI 生成、RAG 引用和 Word 导出
- AI 生成内容流式实时渲染，无延迟
- 支持标题、列表、表格、加粗、斜体、下划线等常用标书编辑能力
- 后续可扩展选中文字润色、续写、改写、资质图片插入和合规提示块

### 终稿编辑：ONLYOFFICE（可选）

如需 Word 格式终稿编辑，可本地启动 ONLYOFFICE Document Server：

```bash
docker run -d \
  -p 8080:80 \
  --restart=always \
  -e JWT_SECRET=replace_with_a_strong_secret \
  onlyoffice/documentserver
```

注意：

- `JWT_SECRET` 必须与 `.env` 中 `ONLYOFFICE_JWT_SECRET` 一致。
- `APP_PUBLIC_BASE_URL` 必须是 ONLYOFFICE 容器能够访问到的后端地址。
- 如果仅使用 Tiptap 编辑 + Word 下载，可以不部署 ONLYOFFICE。

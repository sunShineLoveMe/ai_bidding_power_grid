# 快速开始

> 安全配置详见 [security.md](./security.md)，Supabase 初始化详见 [supabase-setup.md](./supabase-setup.md)

## 前置检查清单

在跑起来之前务必完成这 3 件事，否则首次启动必定报错：

1. **准备好 Supabase 项目**（自建或 supabase.com 托管都可以），拿到 `SUPABASE_URL` 和 `SUPABASE_SERVICE_ROLE_KEY`。
2. **执行必需的 SQL 脚本**（共 9 个），详见 [supabase-setup.md](./supabase-setup.md#必须执行否则功能异常)。跳过任何一个都会在对应功能触发时报错。
3. **创建 5 个 Storage Buckets**，详见 [supabase-setup.md](./supabase-setup.md#storage-buckets)。

常见症状速查：

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 日志反复打印 `Could not find the table 'public.app_users'` | 未执行 `20260429_app_users_and_onlyoffice_documents.sql` | 执行该 SQL 并 Reload schema |
| 章节大纲保存 500 | 未执行 `20260426_create_bid_sections.sql` | 执行该 SQL |
| 用量成本中心为空 | 未执行 `20260507_create_ai_usage_tracking.sql` | 执行该 SQL |
| 上传招标文件 500，日志提示 Bucket 不存在 | Storage bucket 未创建 | 按 [supabase-setup.md](./supabase-setup.md#storage-buckets) 创建 |

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

前端开发模式：

```bash
cd frontend
npm run dev
```

### 2.1 运行后端 MVP 测试

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

当前 `.env.example` 已覆盖模型、Supabase、MinerU、OnlyOffice、上传限制、安全开关、存储路径、企业画像和 Token 成本汇率。生产或客户环境至少需要重点确认以下配置：

```ini
# App / Security
APP_ENV=development
APP_CORS_ORIGINS=http://127.0.0.1:3012,http://localhost:3012,http://127.0.0.1:5173,http://localhost:5173
APP_LOCAL_ONLY=false
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

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

SUPABASE_STORAGE_TENDER_BUCKET=tender-files
SUPABASE_STORAGE_GENERATED_BUCKET=generated-docx
SUPABASE_STORAGE_KNOWLEDGE_BUCKET=knowledge-files
SUPABASE_STORAGE_QUALIFICATION_BUCKET=qualification-files
SUPABASE_STORAGE_PRODUCT_BUCKET=product-files

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
CHROMA_DIR=chroma_db/
SQLITE_DB_PATH=bidding.db
BACKUP_DIR=backups/
WORD_TEMPLATE_PATH=templates/default_bid_template.docx

# DOCX 导出页码刷新，可选但生产建议配置
DOCX_REFRESH_FIELDS=true
SOFFICE_BIN=/opt/homebrew/bin/soffice
DOCX_REFRESH_TIMEOUT_SECONDS=180

# 企业画像，可选；也可在系统设置页面维护
ENTERPRISE_NAME=某水利工程建设企业
ENTERPRISE_REGION=华中地区
ENTERPRISE_INDUSTRY=水利水电工程建设与工程配套服务
ENTERPRISE_BUSINESS_SCOPE=水利工程施工、金属结构件、机电设备配套、质量检验、交付保障和现场服务
ENTERPRISE_ADVANTAGES=水利工程项目响应、质量安全管理、资料编制、供应链协同和现场履约能力
ENTERPRISE_TARGET_CUSTOMERS=水利工程建设单位、总承包单位、监理单位和设备供应链配套单位
ENTERPRISE_RESPONSE_STYLE=专业、严谨、合规、可落地；不得编造证书编号、人员姓名、合同金额、具体日期和未提供的企业业绩

# ONLYOFFICE，可选
ONLYOFFICE_DOCS_API_URL=http://127.0.0.1:8080/web-apps/apps/api/documents/api.js
ONLYOFFICE_JWT_SECRET=replace_with_a_strong_secret
BACKEND_URL_FOR_DOCKER=host.docker.internal:3012
```

模型、Embedding、超时时间、OnlyOffice 地址、存储目录和企业画像等非敏感配置也可以在「系统设置」页面调整。页面保存后会写入本地 `config/runtime_settings.json`，后端在下一次模型请求时读取该配置；该文件已加入 `.gitignore`，开源时只保留 `config/runtime_settings.example.json`。API Key、Supabase service role 等敏感项仍必须通过 `.env` 配置，不会保存在前端。

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

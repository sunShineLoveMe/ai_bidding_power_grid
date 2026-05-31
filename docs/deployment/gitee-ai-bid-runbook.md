# Gitee ai-bid 项目启动操作说明

> 适用场景：合作伙伴从 Gitee 仓库 `ai-bid` 拉取代码后，在本地或内网服务器快速搭建并跑通项目。
>
> 当前推荐路线：Docker Compose 一键启动 PostgreSQL + pgvector + Redis + gunicorn 后端 + Nginx 前端，本地文件存储 + DeepSeek 写作模型 + DashScope Embedding/Rerank。
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
| Docker Desktop / Docker Engine | 最新稳定版 | 启动 PostgreSQL + pgvector、Redis、后端和前端 |
| LibreOffice | 本地可选，backend 容器已内置 | 服务端刷新 DOCX 目录页码 |

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

没有 `DASHSCOPE_API_KEY` 时，后端可以启动，但行业基础知识库入库、向量检索和 Rerank 会失败。

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

构建时会自动生成 `frontend/public/build-info.json` 并复制到 `frontend/dist/build-info.json`。该文件记录 `buildId`、git commit、branch 和构建时间，用于部署后排查“页面是否还是旧版本”。`frontend/public/build-info.json` 是构建临时产物，不需要提交到 Git。

本地查看构建版本：

```bash
cat frontend/dist/build-info.json
```

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

### 5.4 OSS 存储配置（阿里云测试环境）

本地开发保持 `STORAGE_PROVIDER=local`。阿里云测试环境拿到 OSS Bucket 和 RAM AccessKey 后，再切换。

实施前先确认以下信息：

| 项目 | 要求 |
| --- | --- |
| Bucket 地域 | 建议与 ECS 同地域，便于使用内网 Endpoint |
| Bucket ACL | `private`，不要开启公共读或公共读写 |
| Endpoint | ECS 与 OSS 同地域时优先用内网 Endpoint；本地电脑或跨地域调试用外网 Endpoint |
| RAM 凭证 | 使用测试环境专用 RAM 用户或 RAM 角色，不使用主账号 AccessKey |
| 对象前缀 | 建议 `ai-bid/test`，便于测试环境隔离和后续清理 |

阿里云官方参考：

- OSS 访问域名与网络连接：<https://help.aliyun.com/zh/oss/user-guide/access-and-network-overview>
- OSS 地域和 Endpoint：<https://help.aliyun.com/zh/oss/user-guide/regions-and-endpoints>
- Bucket ACL：<https://help.aliyun.com/zh/oss/user-guide/oss-bucket-acl>
- OSS Python SDK：<https://gosspublic.alicdn.com/sdks/python/apidocs/latest/zh-cn/index.html>

```ini
STORAGE_PROVIDER=oss
OSS_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
OSS_PUBLIC_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
OSS_ACCESS_KEY_ID=真实 AccessKey ID
OSS_ACCESS_KEY_SECRET=真实 AccessKey Secret
OSS_BUCKET=测试环境私有 Bucket
OSS_KEY_PREFIX=ai-bid/test
OSS_SIGNED_URL_EXPIRES=3600
```

建议 OSS Bucket 使用私有读写，不开启公共读。系统会通过签名 URL 访问图片资产和下载对象。

也可以按用途拆分 Bucket：

```ini
OSS_TENDER_BUCKET=...
OSS_GENERATED_BUCKET=...
OSS_KNOWLEDGE_BUCKET=...
OSS_QUALIFICATION_BUCKET=...
OSS_PRODUCT_BUCKET=...
```

未配置分用途 Bucket 时，统一回退到 `OSS_BUCKET`。

#### 5.4.1 Endpoint 选择

如果后端部署在阿里云 ECS，并且 ECS 与 OSS Bucket 在同一地域，`OSS_ENDPOINT` 建议填写内网 Endpoint，例如：

```ini
OSS_ENDPOINT=https://oss-cn-hangzhou-internal.aliyuncs.com
OSS_PUBLIC_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
```

如果在本地电脑调试，或者 ECS 与 OSS 不在同一地域，使用外网 Endpoint：

```ini
OSS_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
OSS_PUBLIC_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
```

不要跨地域使用内网 Endpoint，否则可能出现连接失败。

#### 5.4.2 RAM 权限建议

测试环境最小权限建议只授权指定 Bucket 和指定前缀。将下面的 `YOUR_BUCKET`、`ai-bid/test` 替换为实际值：

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "oss:PutObject",
        "oss:GetObject",
        "oss:DeleteObject",
        "oss:ListObjects"
      ],
      "Resource": [
        "acs:oss:*:*:YOUR_BUCKET",
        "acs:oss:*:*:YOUR_BUCKET/ai-bid/test/*"
      ]
    }
  ]
}
```

说明：

- `oss:PutObject`：上传招标文件、知识库文件、资信/产品图片、导出文件。
- `oss:GetObject`：下载、预览、签名 URL 访问对象。
- `oss:DeleteObject`：测试环境清理文件时使用；如客户安全要求更严格，可先不授予。
- `oss:ListObjects`：联调排查时查看前缀下对象；如客户安全要求更严格，可先不授予。

#### 5.4.3 本地联调步骤

1. 安装后端依赖：

```bash
source venv/bin/activate
pip install -r requirements.txt
```

2. 在 `.env` 或 `.env.production` 中切换 OSS：

```ini
STORAGE_PROVIDER=oss
OSS_ENDPOINT=https://实际地域 Endpoint
OSS_PUBLIC_ENDPOINT=https://实际地域外网 Endpoint
OSS_ACCESS_KEY_ID=客户提供
OSS_ACCESS_KEY_SECRET=客户提供
OSS_BUCKET=客户提供
OSS_KEY_PREFIX=ai-bid/test
OSS_SIGNED_URL_EXPIRES=3600
```

3. 重启后端容器：

```bash
docker compose up -d --build backend
docker compose logs -f backend
```

4. 执行 OSS smoke test：

```bash
python - <<'PY'
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")

from backend.db.supabase_client import get_bucket_name, get_supabase_client, upload_file_to_storage

bucket = get_bucket_name("knowledge")
object_path = "smoke/oss-health-check.txt"
local_file = Path("/tmp/oss-health-check.txt")
local_file.write_text("oss ok", encoding="utf-8")

upload_file_to_storage(bucket, object_path, local_file, "text/plain")
client = get_supabase_client()
data = client.storage.from_(bucket).download(object_path)
url = client.storage.from_(bucket).create_signed_urls([object_path], 300)[0]["signedURL"]

assert (data.decode("utf-8") if isinstance(data, bytes) else data.read().decode("utf-8")) == "oss ok"
assert url.startswith("http")
print("OSS smoke ok")
print("bucket=", bucket)
print("object=", object_path)
print("signed_url_prefix=", url.split("?")[0])
PY
```

5. 业务链路验证：

- 上传 1 个小型 PDF/DOCX 招标文件，确认上传接口成功。
- 上传 1 个知识库 Markdown 或图片资产，确认数据库中保存了 `bucket/object_path`。
- 打开知识库图片预览或下载接口，确认返回文件。
- 导出 1 个 DOCX，确认可下载。

#### 5.4.4 回滚到本地存储

如果 OSS AccessKey、Endpoint、Bucket 权限尚未准备好，先回滚到本地存储，保证测试演示不中断：

```ini
STORAGE_PROVIDER=local
LOCAL_STORAGE_ROOT=storage
```

然后重启后端：

```bash
docker compose up -d --build backend
```

注意：回滚只影响新上传和新生成文件；已写入 OSS 的旧文件仍保留在 OSS，数据库中的旧记录仍指向原 Bucket/Object Path。

#### 5.4.5 常见错误

| 现象 | 常见原因 | 处理 |
| --- | --- | --- |
| `AccessDenied` / 403 | RAM 权限不足、Bucket Policy 限制、签名过期 | 检查 RAM Policy 是否覆盖 Bucket 和前缀，重新生成签名 URL |
| `NoSuchBucket` | Bucket 名称或地域错误 | 核对 `OSS_BUCKET` 和 `OSS_ENDPOINT` 是否属于同一地域 |
| `InvalidAccessKeyId` | AccessKey ID 错误或被禁用 | 让客户重新确认 RAM 用户状态和 AccessKey |
| `SignatureDoesNotMatch` | AccessKey Secret 错误、系统时间偏差、Endpoint 不匹配 | 核对 Secret，校准服务器时间，确认 Endpoint |
| 连接超时 | 本地网络不可达、ECS 跨地域使用内网 Endpoint | 本地调试改外网 Endpoint；ECS 与 OSS 同地域时再用内网 Endpoint |
| 预览 403 | Bucket 私有且未使用签名 URL，或签名过期 | 确认后端返回的是 signed URL，适当调大 `OSS_SIGNED_URL_EXPIRES` |

### 5.5 电网测试企业画像

当前测试版本默认面向电网/电力项目，建议 `.env` 使用脱敏电力企业画像：

```ini
ENTERPRISE_NAME=某电力工程服务企业
ENTERPRISE_REGION=华北地区
ENTERPRISE_INDUSTRY=电力工程建设、设备供货、运维检修与技术服务
ENTERPRISE_BUSINESS_SCOPE=输变电工程、配网工程、设备供货、安装调试、试验检测、运维检修和资料交付
ENTERPRISE_ADVANTAGES=具备电力工程项目响应、质量安全管理、资料编制、供应链协同、现场履约和售后运维能力
ENTERPRISE_TARGET_CUSTOMERS=国家电网、南方电网、地方电力公司、电力设计院、总承包单位和设备供应链客户
ENTERPRISE_RESPONSE_STYLE=专业、严谨、合规、可落地；不得编造资质证书编号、人员姓名、业绩合同金额、具体日期和未提供的企业证明材料
```

后续也可以在系统设置页面维护企业画像。

### 5.6 MinerU OCR 可选配置

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

### 5.7 LibreOffice / DOCX 页码刷新配置

用于导出 DOCX 后刷新目录页码、页脚页码和总页数。

Docker 测试环境中，backend 镜像已安装 LibreOffice Writer。镜像构建时使用阿里云 Debian 镜像源并配置 apt 重试，推荐保持以下运行配置：

```ini
DOCX_REFRESH_FIELDS=true
CONTAINER_SOFFICE_BIN=/usr/bin/soffice
DOCX_REFRESH_TIMEOUT_SECONDS=180
```

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

注意：`SOFFICE_BIN` 是本机或直接运行后端时使用的路径；Docker Compose 中 backend 容器会读取 `CONTAINER_SOFFICE_BIN` 并映射为容器内的 `SOFFICE_BIN`，默认值是 `/usr/bin/soffice`。这样可以避免 macOS 的 `/opt/homebrew/bin/soffice` 覆盖容器路径。

验证命令：

```bash
docker compose exec -T backend soffice --version
```

未安装 LibreOffice 或路径错误时，DOCX 导出不会被阻断。导出任务的 `metadata.field_refresh` 会记录 `status`、`reason`、`soffice_bin` 和 `user_message`，前端会提示用户在 Word/WPS 中手动刷新域。

## 6. Docker Compose 一键启动

当前项目已支持通过 Docker Compose 启动测试版基础栈：

| 服务 | 容器 | 对外端口 | 说明 |
| --- | --- | --- | --- |
| `postgres` | `ai-bidding-postgres` | `15432 -> 5432` | PostgreSQL 16 + pgvector |
| `redis` | `ai-bidding-redis` | `16379 -> 6379` | 为后续 Celery/API 限流准备 |
| `backend` | `ai-bidding-backend` | `3012 -> 8000` | gunicorn + gevent 运行 Flask |
| `frontend` | `ai-bidding-frontend` | `8080 -> 80` | Nginx 运行前端构建产物，并反代 `/api/` |

启动前先确认 `.env` 已配置好模型 Key 和本地安全配置，然后执行：

```bash
docker compose build backend
scripts/build_frontend_image.sh
docker compose up -d postgres redis backend frontend
docker compose ps
```

验证后端直连：

```bash
curl -i http://127.0.0.1:3012/api/health
curl -i http://127.0.0.1:3012/api/ready
```

验证前端 Nginx 入口和 API 反代：

```bash
curl -I http://127.0.0.1:8080/
curl -I http://127.0.0.1:8080/build-info.json
curl -s http://127.0.0.1:8080/build-info.json | python3 -m json.tool
curl -i http://127.0.0.1:8080/api/health
curl -i http://127.0.0.1:8080/api/ready
```

说明：

- `/api/health` 是轻量存活检查，只确认后端进程可响应，适合 Docker `HEALTHCHECK`。
- `/api/ready` 是启动就绪检查，会检查 PostgreSQL/pgvector/知识库匹配函数、Redis、存储 provider 和模型 Key 配置，适合部署完成后的接流量验收。
- `/api/ready` 不需要登录态；即使 `APP_LOGIN_ENABLED=true`，Nginx、部署脚本和阿里云测试环境探针也可以直接调用。
- 如果 `/api/ready` 返回 503，先看返回 JSON 中 `checks` 的失败项，再排查对应依赖。
- `index.html` 返回 `Cache-Control: no-cache, no-store, must-revalidate`，避免发版后浏览器继续使用旧入口。
- `/assets/` 下的 Vite hash JS/CSS 返回 1 年 immutable 缓存。
- `/build-info.json` 返回 `Cache-Control: no-store`，可用于确认当前前端镜像版本；浏览器控制台也会输出同一份版本信息。

浏览器访问：

```text
http://127.0.0.1:8080
```

查看日志：

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

停止服务：

```bash
docker compose down
```

如需删除本地数据库、上传文件、导出文件等 Docker volume 数据，再执行：

```bash
docker compose down -v
```

注意：`docker compose down -v` 会删除本地 PostgreSQL 数据和文件卷，只能在确认不需要保留测试数据时使用。

## 7. 单独启动 PostgreSQL

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

## 8. 初始化 PostgreSQL 业务表

> 重要：`docker compose up -d postgres` 只会创建数据库和扩展，不会自动创建全部业务表。

推荐执行 Alembic 迁移入口。该命令会读取 `DATABASE_URL`，本地未配置时默认连接 `127.0.0.1:15432` 的 Docker PostgreSQL：

```bash
scripts/migrate_postgres.sh
```

当前 Alembic baseline revision 为 `20260530_0001`，会按固定顺序执行主 schema、登录表扩展和 DeepSeek 成本价格种子，并写入 `alembic_version`。

验证 Alembic 当前版本：

```bash
DATABASE_URL=postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding venv/bin/alembic current
```

期望看到：

```text
20260530_0001 (head)
```

当前本地验证状态：2026-05-30 已在本地 PostgreSQL + pgvector Docker 库中执行 `scripts/migrate_postgres.sh`，Alembic 当前版本为 `20260530_0001 (head)`。已确认核心表、`pgcrypto` / `vector` 扩展、`match_knowledge_chunks` / `match_knowledge_assets` RPC、DeepSeek v4 flash/pro 价格种子可用。阿里云 RDS 测试库需等账号到位后复验。

如果只需要手工排障，也可以执行旧初始化脚本，脚本会按固定顺序执行主 schema、登录表扩展和 DeepSeek 成本价格种子，并在最后验证核心表：

```bash
scripts/init_postgres_schema.sh
```

如果需要手工排障，等价执行顺序如下：

```bash
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/001_schema.sql
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/002_app_login.sql
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/003_seed_deepseek_v4_flash_pricing.sql
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/004_seed_deepseek_v4_pro_pricing.sql
```

验证核心表是否存在：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select table_name from information_schema.tables where table_schema='public' and table_name in ('bid_projects','bid_files','bid_analysis','bid_sections','knowledge_documents','document_chunks','knowledge_assets','app_users','ai_usage_logs','bid_generation_tasks','bid_export_tasks') order by table_name;"
```

验证 pgvector 扩展和 RPC：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select extname from pg_extension where extname in ('pgcrypto','vector') order by extname;"
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select proname from pg_proc where proname in ('match_knowledge_chunks','match_knowledge_assets') order by proname;"
```

验证 DeepSeek 价格种子：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select provider || ':' || model || ':' || operation_type || ':' || currency from public.ai_model_prices where provider='deepseek' order by model;"
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

## 9. 导入行业基础数据

当前项目默认面向电网/电力场景。历史 `rag_seed/water_*` 目录只作为迁移参考，不作为当前测试环境默认数据；电网 RAG 种子库入库脚本会在 P0-9 补齐。

当前基础数据分三类：

| 数据目录 | 内容 | 导入目标 |
| --- | --- | --- |
| `rag_seed/power_grid_resources/` | 电网/电力招投标公开资料、技术规范书响应、政策法规、标准话术 | `knowledge_documents` / `document_chunks` |
| 待补：电网脱敏企业资料 | 脱敏企业画像、资信、产品服务、能力说明 | `knowledge_documents` / `document_chunks` |
| 待补：电网图片资产库 | 电力产品图、资信样张、工程/服务示意图 | `knowledge_assets` + 本地 `storage/` |

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

### 9.1 电网 RAG 基础知识库

执行电网种子库入库：

```bash
python rag_seed/power_grid_resources/_scripts/ingest_power_grid_rag_seed.py
```

脚本默认只导入 Markdown/网页型资料和自建标准话术，PDF 会跳过。原因是标准、法规、蓝皮书等 PDF 直接粗切会带来噪声和版权边界问题；如需补充 PDF，请先用 MinerU/OCR 抽取、人工确认摘要和引用边界，再显式执行：

```bash
python rag_seed/power_grid_resources/_scripts/ingest_power_grid_rag_seed.py --include-pdf --category 02_policy_regulations
```

常用参数：

```bash
# 只检查分片，不写库、不消耗 embedding
python rag_seed/power_grid_resources/_scripts/ingest_power_grid_rag_seed.py --dry-run

# 只导入自建标准话术
python rag_seed/power_grid_resources/_scripts/ingest_power_grid_rag_seed.py --category 04_standard_phrases

# 已入库资料需要重建分片时使用
python rag_seed/power_grid_resources/_scripts/ingest_power_grid_rag_seed.py --refresh
```

本地已验证结果：

```text
候选资料：41 条
已入库或已存在文档：26 条
向量分片：279 条
PDF 默认跳过：15 条
分类：power_grid_policy_regulations、power_grid_standard_phrases、power_grid_standards_specs、power_grid_tender_documents
```

### 9.2 历史水利种子库（仅迁移参考）

如果需要回归旧水利演示链路，可在独立测试库执行历史脚本：

```bash
python rag_seed/water_resources/_scripts/ingest_water_rag_seed.py
python rag_seed/water_enterprise_mock/_scripts/ingest_enterprise_mock_seed.py
python rag_seed/water_asset_images/_scripts/ingest_knowledge_assets.py
```

历史脚本成功后会生成或更新各自目录下的入库报告，例如：

```text
rag_seed/water_resources/ingestion_report.md
rag_seed/water_resources/ingestion_report.json
rag_seed/water_enterprise_mock/ingestion_report.md
rag_seed/water_enterprise_mock/ingestion_report.json
rag_seed/water_asset_images/ingestion_report.json
```

图片文件会复制到本地：

```text
storage/knowledge-assets/
```

### 9.3 验证入库结果

查看知识文档、分片、图片资产数量：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select 'knowledge_documents=' || count(*) from public.knowledge_documents union all select 'document_chunks=' || count(*) from public.document_chunks union all select 'knowledge_assets=' || count(*) from public.knowledge_assets;"
```

查看数据分类：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -c "select category, count(*) from public.knowledge_documents group by category order by category;"
```

查看向量是否生成：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select 'chunk_embeddings=' || count(*) from public.document_chunks where embedding is not null union all select 'asset_embeddings=' || count(*) from public.knowledge_assets where embedding is not null;"
```

如果 `embedding` 数量为 0，优先检查 `DASHSCOPE_API_KEY` 是否正确。

查看电网种子库入库结果：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select 'power_grid_docs=' || count(*) from public.knowledge_documents where metadata->>'seed_corpus'='power_grid_resources' union all select 'power_grid_chunks=' || count(*) from public.document_chunks where metadata->>'seed_corpus'='power_grid_resources' union all select 'power_grid_embeddings=' || count(*) from public.document_chunks where metadata->>'seed_corpus'='power_grid_resources' and embedding is not null;"
```

查看电网资料分类：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -c "select category, count(*) from public.knowledge_documents where metadata->>'seed_corpus'='power_grid_resources' group by category order by category;"
```

## 10. 启动后端

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

## 11. 前端开发模式可选

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

## 12. 登录与账号

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

## 13. 跑通验收流程

### 13.1 基础健康检查

访问：

```text
http://127.0.0.1:3012
```

确认页面正常打开，无 500 报错。

后端存活检查：

```bash
curl -fsS http://127.0.0.1:3012/api/health
```

后端就绪检查：

```bash
curl -fsS http://127.0.0.1:3012/api/ready | python3 -m json.tool
```

`/api/ready` 返回 200 表示 PostgreSQL、Redis、存储 provider 等关键依赖已达到可接流量状态；返回 503 时按 `checks` 中的失败项处理。

### 13.2 数据库检查

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c "select 'bid_projects=' || count(*) from public.bid_projects union all select 'knowledge_documents=' || count(*) from public.knowledge_documents union all select 'document_chunks=' || count(*) from public.document_chunks union all select 'knowledge_assets=' || count(*) from public.knowledge_assets;"
```

初始项目数可以为 0；电网种子库入库后 `knowledge_documents`、`document_chunks`、`knowledge_assets` 应大于 0。

### 13.3 上传招标文件测试

可使用测试样本：

```text
test_samples/
```

建议测试顺序：

1. 上传较小或结构清晰的 PDF / DOCX，验证解析和项目创建。
2. 进入招标解读，验证 DeepSeek 调用。
3. 生成分册大纲，验证章节落库。
4. 生成单个章节正文，验证 RAG 检索和写作模型。
5. 运行合规检查，验证规则覆盖率和 LLM 语义复核。
6. 导出 Word，验证 DOCX 下载。

### 13.4 知识库问答测试

进入知识库问答或相关入口，提问：

```text
电网设备采购项目投标文件通常需要哪些资格审查材料？
```

如果电网 RAG 已入库，回答应能引用电网招投标、技术规范书响应、政策法规或标准话术相关内容。

## 14. 常用维护命令

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

### OSS 依赖检查

```bash
python - <<'PY'
import oss2
print("oss2", oss2.__version__)
PY
```

### 后端测试

```bash
python -m unittest discover -s tests
```

### 后端语法检查

```bash
python -m py_compile main.py backend/api/routes.py backend/parsing/document_parser.py backend/export/md_to_word.py
```

## 15. 重新初始化空库

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
scripts/migrate_postgres.sh
python rag_seed/power_grid_resources/_scripts/ingest_power_grid_rag_seed.py
```

## 16. 推送到 Gitee 的注意事项

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

## 17. 常见问题

### 17.1 `connection refused` 或连不上 `127.0.0.1:15432`

原因：PostgreSQL 容器未启动或端口被占用。

处理：

```bash
docker compose ps postgres
docker compose logs postgres
docker compose up -d postgres
```

### 17.2 `extension "vector" is not available`

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

### 17.3 业务表不存在

现象：后端报 `relation "bid_projects" does not exist`、`relation "knowledge_documents" does not exist` 等。

处理：

```bash
scripts/migrate_postgres.sh
```

### 17.4 行业知识库为空

原因：只初始化了表，没有跑种子入库脚本。

处理：

```bash
python rag_seed/power_grid_resources/_scripts/ingest_power_grid_rag_seed.py
```

### 17.5 入库脚本提示 DashScope 相关错误

原因：`DASHSCOPE_API_KEY` 未配置、无权限、余额不足或网络无法访问 DashScope。

处理：

1. 检查 `.env` 中 `DASHSCOPE_API_KEY`。
2. 确认当前终端在项目根目录执行脚本。
3. 确认虚拟环境已激活。
4. 重新执行入库脚本。

### 17.6 DeepSeek 生成失败

原因：`DEEPSEEK_API_KEY` 未配置、模型名错误、余额不足、网络异常或请求超时。

处理：

1. 检查 `.env` 中 `DEEPSEEK_API_KEY`。
2. 确认 `DEEPSEEK_BASE_URL=https://api.deepseek.com`。
3. 确认模型名仍可用。
4. 大文件解读时可适当调大 `REASONING_REQUEST_TIMEOUT_SECONDS`。

### 17.7 DOCX 导出成功但目录页码不正确

原因：服务器未安装 LibreOffice、`SOFFICE_BIN` 路径错误，或 LibreOffice 执行超时。

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

Docker 测试环境优先检查 backend 容器：

```bash
docker compose exec -T backend soffice --version
docker compose exec -T backend printenv SOFFICE_BIN
```

如果容器内没有 `soffice`，重新构建 backend 镜像：

```bash
docker compose build backend
docker compose up -d backend
```

排查导出任务时，查看任务返回的 `metadata.field_refresh`：

| 字段 | 说明 |
| --- | --- |
| `status` | `refreshed` 成功；`failed` 失败但不阻断下载；`skipped` 配置关闭 |
| `manual_refresh_required` | `true` 表示用户需要打开 Word/WPS 后手动刷新域 |
| `user_message` | 前端展示给用户的提示 |
| `reason` | 具体失败原因 |

### 17.8 前端跨域失败

原因：前端访问地址没有加入 `APP_CORS_ORIGINS`。

处理：

```ini
APP_CORS_ORIGINS=http://127.0.0.1:3012,http://localhost:3012,http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8080,http://localhost:8080
```

如果部署到内网服务器，例如 `192.168.1.20`：

```ini
APP_CORS_ORIGINS=http://192.168.1.20:3012,http://192.168.1.20:5173
APP_PUBLIC_BASE_URL=http://192.168.1.20:3012
```

修改 `.env` 后重启后端。

## 18. 首次交付检查清单

交付前逐项确认：

- [ ] Gitee 仓库已推送 `main` 分支。
- [ ] `.env` 未提交到仓库。
- [ ] 合作伙伴已拿到单独发送的 `.env` 配置或密钥填写说明。
- [ ] Docker Compose 可启动 PostgreSQL、Redis、backend、frontend。
- [ ] backend 容器使用 gunicorn + gevent 启动。
- [ ] frontend Nginx 可访问 `http://127.0.0.1:8080` 并正常反代 `/api/health`、`/api/ready`。
- [ ] `pgcrypto` 和 `vector` 扩展存在。
- [ ] `scripts/migrate_postgres.sh` 已执行，`alembic current` 为 `20260530_0001 (head)`。
- [ ] DeepSeek 价格种子已存在。
- [ ] 电网 RAG 文档已导入。
- [ ] 电网脱敏企业资料已导入。
- [ ] 电网图片资产已导入。
- [ ] `knowledge_documents`、`document_chunks`、`knowledge_assets` 数量大于 0。
- [ ] 后端 `python main.py` 可启动。
- [ ] 前端页面可访问。
- [ ] 可注册/登录。
- [ ] 可上传招标文件。
- [ ] 可执行招标解读。
- [ ] 可生成分册大纲。
- [ ] 可生成章节正文。
- [ ] 可导出 DOCX。

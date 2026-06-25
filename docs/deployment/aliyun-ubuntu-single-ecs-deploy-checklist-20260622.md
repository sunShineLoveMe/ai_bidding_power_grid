# 阿里云 Ubuntu 单 ECS 测试部署操作清单

更新日期：2026-06-25  
适用环境：阿里云 ECS 单企业测试环境  
当前实例：`launch-advisor-20260604`  
公网 IP：`8.160.187.226`  
系统：`Ubuntu 22.04 64位`  
规格：`8 vCPU / 16 GiB / 200 GiB ESSD Entry / 5 Mbps`
代码来源：Gitee `git@gitee.com:mainiutech/ai-bid.git`  
部署分支：`feat/aliyun-test-readiness`

## 目标

在客户提供的阿里云 ECS 上部署国家电网单企业 AI 标书系统测试环境，先采用单机 Docker Compose 方式运行：

- PostgreSQL + pgvector
- Redis
- Backend Flask/Gunicorn
- Celery Worker
- Frontend Nginx
- LibreOffice headless DOCX 字段刷新

本清单用于逐步执行和交接。每完成一项，在状态栏改为 `[x]`，并在“执行记录”里写明时间、执行人和异常。

## 重要边界

1. 测试期先走单 ECS Docker 部署，不先拆 RDS/OSS/云 Redis。
2. 不公网暴露 PostgreSQL `5432`、Redis `6379`、backend 内部端口和 Celery。
3. 正式访问入口优先走前端 Nginx，后续再接域名和 HTTPS。
4. 所有 API Key、数据库密码、登录密钥只写服务器 `.env`，不得提交 Git。
5. DOCX/PDF 正式验收必须后续单独跑导出链路和字段刷新检查。

## 0. 阿里云控制台准备

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | 确认 ECS 已重装为 Ubuntu 22.04 64 位 | 控制台显示 `Ubuntu 22.04 64位` | 已从 Windows Server 改为 Ubuntu；SSH 实测为 Ubuntu 22.04.5 LTS |
| [x] | 确认 EIP 已绑定 ECS | 可看到公网 IP `8.160.187.226`，SSH 可连通 | SSH 已连通 |
| [ ] | 确认 RAM 权限范围 | RAM 账号可进入 ECS 控制台并对实例执行重置密码/密钥绑定等操作 | RAM 控制台账号不是服务器 SSH 账号 |
| [x] | 设置 ECS 登录凭据 | 已通过控制台重置 root 密码，或绑定 SSH 密钥对 | 已可用 root SSH 登录 |
| [ ] | 安全组开放 SSH | TCP `22` 仅允许运维办公 IP 或临时白名单 | 不建议长期 `0.0.0.0/0` |
| [ ] | 安全组开放 HTTP | TCP `80` 允许 `0.0.0.0/0` | 测试期访问入口 |
| [ ] | 安全组开放 HTTPS | TCP `443` 允许 `0.0.0.0/0` | 后续域名证书使用 |
| [ ] | 确认不开放数据库端口 | `5432`、`6379` 不对公网开放 | 只走 Docker 内网 |
| [x] | 记录登录方式 | root 密码或 SSH key 已安全保存 | 使用 root 密码登录；不写入本文档明文 |

### 0.1 RAM 账号与 ECS SSH 登录的区别

客户提供的 RAM 账号用于登录阿里云控制台，例如查看 ECS、改安全组、重置实例密码、绑定密钥对。它不是 Ubuntu 服务器里的 Linux 用户，不能直接作为 SSH 账号使用。

SSH 登录需要以下二选一：

1. 控制台为 ECS 重置 `root` 密码，然后使用 `ssh root@8.160.187.226` 登录。
2. 控制台为 ECS 绑定 SSH 密钥对，然后使用 `ssh -i <key.pem> root@8.160.187.226` 登录。

如果执行 `ssh root@8.160.187.226` 后提示 `Permission denied`，通常说明：

- 输入的是 RAM 控制台密码，而不是 ECS 的 `root` 密码；
- ECS 尚未设置或重置 `root` 密码；
- ECS 禁止密码登录，只允许密钥登录；
- 安全组或实例防火墙未放通 `22`。

## 1. 首次 SSH 登录与系统信息确认

在本机终端执行：

```bash
ssh-keygen -R 8.160.187.226
ssh root@8.160.187.226
```

如使用密钥：

```bash
chmod 600 /path/to/key.pem
ssh -i /path/to/key.pem root@8.160.187.226
```

服务器上执行：

```bash
whoami
uname -a
lsb_release -a
df -h
free -h
ip addr | grep -E "inet "
```

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | SSH 登录成功 | 能进入服务器 shell | 用户为 `root` |
| [x] | 确认系统版本 | `Ubuntu 22.04` | 实测 `Ubuntu 22.04.5 LTS`，内核 `5.15.0-181-generic` |
| [x] | 确认磁盘空间 | 系统盘约 200 GiB 可用 | `/dev/vda3` 197G，已用 2.9G，可用 186G |
| [x] | 确认内存 | 约 16 GiB | 实测 14Gi total，14Gi available |
| [x] | 确认内网/公网网络 | 有 `172.30.78.66` 等私网 IP | 实测 `172.30.78.66/20`，公网通过 EIP 访问 |

## 2. Ubuntu 基础初始化

服务器上执行：

```bash
apt update
apt upgrade -y
timedatectl set-timezone Asia/Shanghai

apt install -y \
  curl wget git vim htop unzip zip ca-certificates gnupg lsb-release \
  build-essential software-properties-common ufw

date
```

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | 更新 apt 索引 | `apt update` 成功 | 已使用阿里云 Ubuntu 源 |
| [x] | 升级系统包 | `apt upgrade -y` 成功 | 输出显示内核已是最新，无服务需重启 |
| [x] | 设置时区 | `date` 显示 CST/北京时间 | 实测 `Mon Jun 22 04:07:24 PM CST 2026` |
| [x] | 安装基础工具 | curl/git/vim/htop/unzip 等可用 | unzip/zip 已安装，其他基础包已完成 |

## 3. 安装 Docker 与 Docker Compose

服务器上执行：

```bash
install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

chmod a+r /etc/apt/keyrings/docker.gpg

echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
> /etc/apt/sources.list.d/docker.list

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker
systemctl start docker
```

验证：

```bash
docker --version
docker compose version
systemctl is-active docker
```

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | 添加 Docker 阿里云源 | `/etc/apt/sources.list.d/docker.list` 存在 | 国内下载更稳定 |
| [x] | 安装 Docker Engine | `docker --version` 正常 | 实测 Docker `29.0.0` |
| [x] | 安装 compose 插件 | `docker compose version` 正常 | 实测 Docker Compose `v5.1.4` |
| [x] | Docker 服务启动 | `systemctl is-active docker` 输出 `active` | 已启动 |
| [x] | Docker 设置开机启动 | `systemctl is-enabled docker` 输出 `enabled` | 已启用 |

## 4. 创建部署目录与拉取代码

建议部署目录：

```bash
mkdir -p /opt/ai-bidding
cd /opt/ai-bidding
```

代码获取方式二选一：

### 方式 A：Git 拉取

```bash
git clone -b feat/aliyun-test-readiness --single-branch git@gitee.com:mainiutech/ai-bid.git ai_bidding_power_grid
cd ai_bidding_power_grid
git status
```

### 方式 B：打包上传

本地打包后上传：

```bash
tar --exclude='.git' --exclude='.venv' --exclude='venv' --exclude='node_modules' \
  --exclude='frontend/node_modules' --exclude='uploads' --exclude='outputs' \
  --exclude='storage' --exclude='parsed_outputs' \
  -czf ai_bidding_power_grid.tar.gz ai_bidding_power_grid

scp ai_bidding_power_grid.tar.gz root@8.160.187.226:/opt/ai-bidding/
```

服务器解压：

```bash
cd /opt/ai-bidding
tar -xzf ai_bidding_power_grid.tar.gz
cd ai_bidding_power_grid
```

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | 创建部署目录 | `/opt/ai-bidding` 存在 | 已创建并进入部署目录 |
| [x] | 配置 Gitee SSH 访问 | `ssh -T git@gitee.com` 认证成功 | 实测 `successfully authenticated` |
| [x] | 代码上传或拉取完成 | 项目根目录存在 `docker-compose.yml` | 已拉取 `feat/aliyun-test-readiness`，工作区 clean |
| [x] | 确认关键文件 | `Dockerfile.backend`、`Dockerfile.frontend`、`.env.example` 存在 | 已确认 |

### 4.1 代码发布到阿里云测试环境 SOP

本环境代码来源统一以 Gitee 为准，测试部署分支为：

```text
feat/aliyun-test-readiness
```

除非只是紧急排障且已在执行记录中注明，否则不要只把本地单个文件 `scp` 到服务器后长期运行。正确流程是：本地提交代码 -> 推送 Gitee 测试分支 -> 服务器拉取指定 commit -> 构建对应镜像 -> 冒烟验证。

#### 4.1.1 开发人员本地提交与推送

本地确认当前分支：

```bash
cd /Users/chris/Documents/项目/AI标书项目/ai_bidding_power_grid
git branch --show-current
```

如不在测试分支，先切换：

```bash
git checkout feat/aliyun-test-readiness
git pull --rebase origin feat/aliyun-test-readiness
```

提交前检查：

```bash
git status --short
git diff
```

只提交本次相关文件，不要把 `.env`、客户密钥、临时压缩包、`node_modules`、`.venv`、大体积解析中间产物误提交：

```bash
git add <本次修改文件>
git commit -m "<简短说明>"
git push origin feat/aliyun-test-readiness
```

推送后记录本地 commit：

```bash
git rev-parse --short HEAD
git log -1 --oneline
```

#### 4.1.2 服务器拉取并确认代码版本

服务器执行：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid

git status --short
git branch --show-current
git fetch origin feat/aliyun-test-readiness
git pull --ff-only origin feat/aliyun-test-readiness
git log -1 --oneline
```

验收口径：

- `git branch --show-current` 必须是 `feat/aliyun-test-readiness`；
- `git log -1 --oneline` 必须等于或晚于本地刚推送的 commit；
- 如果服务器有未提交改动，先判断是否为 `.env`、数据文件或临时热修复。不要直接 `git reset --hard`，避免覆盖线上排障痕迹和客户资料。

#### 4.1.3 前端改动发布

适用范围：`frontend/` 下页面、组件、样式、接口调用、构建配置等变更。

服务器执行：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid

git log -1 --oneline
docker compose build frontend
docker compose up -d --force-recreate frontend
docker compose ps
```

如果怀疑 Docker 构建缓存导致旧前端仍被打包，执行无缓存构建：

```bash
docker compose build --no-cache frontend
docker compose up -d --force-recreate frontend
```

如果仍怀疑旧镜像残留，可只删除前端镜像，禁止删除数据库 volume：

```bash
docker compose down frontend
docker image rm -f ai-bidding-frontend:local
docker builder prune -f
docker compose build --no-cache frontend
docker compose up -d frontend
```

注意：

- `docker compose down frontend` 只会移除前端容器；提示 `Network ... Resource is still in use` 属于正常，因为 backend/postgres/redis 仍在使用网络；
- 不要执行 `docker compose down -v`，会删除 volume，存在清空数据库或存储数据风险；
- 不要删除 `postgres_data`、`redis`、`storage` 等数据 volume。

前端发布后验证静态包：

```bash
docker compose exec frontend sh -lc 'ls -lh /usr/share/nginx/html/assets | head'
docker compose exec frontend sh -lc 'grep -R "<关键字符串>" -n /usr/share/nginx/html/assets | head'
```

浏览器验证：

- 优先使用无痕窗口；
- 或打开 DevTools -> Network -> 勾选 Disable cache -> 强制刷新；
- 对前端功能问题，除页面显示外，还应检查 Network 中对应接口 Response。

#### 4.1.4 后端改动发布

适用范围：`backend/`、`scripts/`、Python 依赖、数据库访问、RAG 检索、导出逻辑等变更。

如果只是 `backend/`、`scripts/`、`main.py` 或 `gunicorn.conf.py` 的代码改动，且没有修改 `requirements.txt`、`Dockerfile.backend` 或系统依赖，阿里云测试环境可用源码挂载方式快速发布，避免每次重新 `pip install`：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid

git fetch origin feat/aliyun-test-readiness
git pull --ff-only origin feat/aliyun-test-readiness
git log -1 --oneline

docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml restart backend celery-worker
docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml ps backend celery-worker
```

验证容器内代码确实来自最新源码：

```bash
docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml exec backend sh -lc \
  'grep -n "只回答已命中的资质证书" /app/backend/rag/retrieval.py || true'
docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml exec backend sh -lc \
  'grep -n "_request_openai_compatible_embeddings" /app/backend/rag/vector_store.py || true'
```

如果修改了依赖、Dockerfile 或需要验证完整镜像，则执行完整镜像发布。

服务器执行：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid

git log -1 --oneline
docker compose build backend
docker compose up -d --force-recreate backend celery-worker
docker compose ps
```

后端发布后验证：

```bash
curl -fsS http://127.0.0.1:3012/api/health
curl -fsS http://127.0.0.1:8080/api/health
docker compose logs --tail=100 backend
docker compose logs --tail=100 celery-worker
```

如果只是临时验证一个 Python 文件，可短期使用 `docker cp` 覆盖容器内文件，但必须满足：

- 同步把代码提交并推送到 Gitee；
- 在执行记录中注明临时覆盖了哪个文件；
- 后续正式发布必须重新 `git pull + docker compose build backend`，避免容器内文件和 Git 代码不一致。

#### 4.1.5 前后端同时改动发布

服务器执行：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid

git fetch origin feat/aliyun-test-readiness
git pull --ff-only origin feat/aliyun-test-readiness
git log -1 --oneline

docker compose build backend frontend
docker compose up -d --force-recreate backend celery-worker frontend
docker compose ps
```

基础验证：

```bash
curl -fsS http://127.0.0.1:3012/api/health
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS -I http://127.0.0.1:8080/
```

#### 4.1.6 发布前后必查清单

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [ ] | 本地代码已提交 | `git status --short` 无应提交源码改动 | `.env` 和客户密钥不得提交 |
| [ ] | 已推送 Gitee 测试分支 | `git push origin feat/aliyun-test-readiness` 成功 | 不使用 GitHub |
| [ ] | 服务器已拉取目标 commit | 服务器 `git log -1 --oneline` 与本地一致 | 构建前必须确认 |
| [ ] | 按改动范围构建镜像 | 前端改动构建 frontend；后端改动构建 backend | 不盲目全量重建 |
| [ ] | 容器已重建或重启 | `docker compose ps` 显示目标服务 healthy/running | frontend 可能只显示 Started |
| [ ] | 本机健康检查通过 | `/api/health` 返回 `{"status":"ok"}` | 同时检查 `3012` 和 `8080` |
| [ ] | 浏览器无痕验证通过 | 页面显示和核心操作符合预期 | 前端问题必须验证真实页面 |
| [ ] | 执行记录已更新 | 写明 commit、构建服务、验证结果 | 便于交接追踪 |

## 5. 配置生产测试 `.env`

在服务器项目根目录执行：

```bash
cp .env.example .env
vim .env
```

也可以在本地编辑 `.env` 后直接上传覆盖服务器文件，更适合变量较多的首次部署：

```bash
scp .env root@8.160.187.226:/opt/ai-bidding/ai_bidding_power_grid/.env
```

上传后服务器执行脱敏检查，不要截图或转发完整 `.env`：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
grep -E '^(APP_ENV|APP_PUBLIC_BASE_URL|APP_HOST|APP_LOGIN_ENABLED|DB_PROVIDER|POSTGRES_DB|POSTGRES_USER|STORAGE_PROVIDER|DOCX_REFRESH_FIELDS|CONTAINER_SOFFICE_BIN|AI_PROVIDER|DEEPSEEK_BASE_URL|DASHSCOPE_EMBEDDING_MODEL|DASHSCOPE_RERANK_ENABLED|MINERU_API_BASE_URL)=' .env
```

测试期单机 Docker 推荐先配置以下关键项：

```ini
APP_ENV=production
APP_PUBLIC_BASE_URL=http://8.160.187.226
APP_HOST=8.160.187.226
APP_CORS_ORIGINS=http://8.160.187.226,http://localhost,http://127.0.0.1
APP_LOCAL_ONLY=false

APP_LOGIN_ENABLED=true
APP_SESSION_SECRET=<生成一个至少32位随机字符串>
APP_SESSION_EXPIRES_HOURS=72
APP_COOKIE_SECURE=false

APP_AUTH_ENABLED=false
APP_AUTH_TOKEN=<生成一个至少32位随机字符串>
REQUIRE_STRICT_CONFIG=false
APP_EXPOSE_DEBUG_ERRORS=false
LOG_LEVEL=INFO
LOG_FORMAT=json

DB_PROVIDER=postgres
POSTGRES_DB=bidding
POSTGRES_USER=bidding
POSTGRES_PASSWORD=<生成一个强密码>
POSTGRES_POOL_ENABLED=true
POSTGRES_POOL_MAX_SIZE=10
POSTGRES_POOL_TIMEOUT_SECONDS=5

STORAGE_PROVIDER=local
LOCAL_STORAGE_ROOT=storage

AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=<客户提供>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_KNOWLEDGE_MODEL=deepseek-v4-flash

DASHSCOPE_API_KEY=<客户提供>
DASHSCOPE_MODEL=qwen-turbo-latest
DASHSCOPE_KNOWLEDGE_MODEL=qwen-long
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
DASHSCOPE_EMBEDDING_DIMENSIONS=1024
DASHSCOPE_RERANK_ENABLED=true
DASHSCOPE_RERANK_MODEL=qwen3-rerank

MINERU_API_TOKEN=<客户提供，可后补>
MINERU_API_BASE_URL=https://mineru.net
MINERU_PARSE_PDF_FIRST=true

DOCX_REFRESH_FIELDS=true
CONTAINER_SOFFICE_BIN=/usr/bin/soffice
DOCX_REFRESH_TIMEOUT_SECONDS=180
DOCX_TEMPLATE_ID=formal_bid_standard

MAX_UPLOAD_MB=200
ALLOWED_TENDER_EXTENSIONS=pdf,doc,docx,txt,md
ALLOWED_KNOWLEDGE_EXTENSIONS=pdf,doc,docx,txt,md,xls,xlsx,csv,png,jpg,jpeg,webp
ALLOWED_ASSET_EXTENSIONS=png,jpg,jpeg,webp,pdf,doc,docx
```

生成随机密钥示例：

```bash
openssl rand -hex 32
```

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [ ] | 复制 `.env.example` | `.env` 存在 | |
| [ ] | 设置生产测试基础项 | `APP_ENV=production` | 测试也按生产启动约束 |
| [ ] | 配置公网访问地址 | `APP_PUBLIC_BASE_URL=http://8.160.187.226` | 后续有域名再改 |
| [ ] | 配置数据库密码 | `POSTGRES_PASSWORD` 非默认弱口令 | 不提交 Git |
| [ ] | 配置登录/会话密钥 | `APP_SESSION_SECRET` 已生成随机值 | |
| [x] | 配置 DeepSeek Key | 模型调用可用 | 本地使用云上 `.env.aliyun.local` 验证 `chat/completions` 返回正常 |
| [x] | 配置 DashScope Key | embedding/rerank 可用 | 本地验证百炼 embedding 返回向量；云上容器烟测输出 `1 1024` |
| [ ] | 配置 MinerU Token | OCR/MinerU 可用 | 可后补 |
| [ ] | 配置 DOCX 字段刷新 | `CONTAINER_SOFFICE_BIN=/usr/bin/soffice` | 容器内路径 |
| [ ] | 配置 DOCX 中文字体 | 容器内 `fc-match` 能匹配仿宋/黑体/楷体替代字体 | 保障 `formal_bid_standard` 线上 DOCX/PDF 预览不被异常替换 |

## 6. 构建并启动容器

在服务器项目根目录执行：

```bash
docker compose config
docker compose build backend frontend
docker compose up -d postgres redis
docker compose ps
```

确认数据库和 Redis healthy 后：

```bash
docker compose up -d backend celery-worker frontend
docker compose ps
```

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | Compose 配置校验 | `docker compose config` 无错误 | 已进入后续 build/up 流程，Compose 配置可解析 |
| [x] | 后端镜像构建 | `ai-bidding-backend:local` 构建成功 | 首次构建约 2271.5s，后续应走缓存 |
| [x] | 前端镜像构建 | `ai-bidding-frontend:local` 构建成功 | 首次构建约 2271.5s，后续应走缓存 |
| [x] | PostgreSQL 启动 | `postgres` 状态 healthy | pgvector 镜像；端口映射 `15432->5432` |
| [x] | Redis 启动 | `redis` 状态 healthy | 端口映射 `16379->6379` |
| [x] | Backend 启动 | `backend` 状态 healthy | 端口映射 `3012->8000` |
| [x] | Celery Worker 启动 | `celery-worker` 状态 healthy | 已启动并 healthy |
| [x] | Frontend 启动 | `frontend` 状态 healthy | 本机 `8080` 首页返回 200；`compose ps` 截图时仍在 health starting，需后续复查一次 |

## 7. 基础健康检查

服务器上执行：

```bash
curl -fsS http://127.0.0.1:3012/api/health
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS -I http://127.0.0.1:8080/
```

外部本机浏览器访问：

```text
http://8.160.187.226
```

如果前端当前只映射 `8080:80`，公网直接访问 80 还不可用，需要后续调整为 `80:80` 或增加宿主机 Nginx。测试期可临时访问：

```text
http://8.160.187.226:8080
```

但若使用 `8080`，必须临时开放安全组 `8080`。正式建议改 compose 前端端口为 `80:80`。

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | 后端本机健康检查 | `/api/health` 返回 200 | `127.0.0.1:3012` 返回 `{"status":"ok"}` |
| [x] | 前端反代健康检查 | `/api/health` 返回 200 | `127.0.0.1:8080` 返回 `{"status":"ok"}` |
| [x] | 前端首页本机访问 | `curl -I` 返回 200 | `HTTP/1.1 200 OK`，Nginx `1.27.5` |
| [x] | 公网浏览器访问 | 能打开登录页/首页 | `http://8.160.187.226:8080` 已能打开登录页；当前仍是测试端口 |

## 8. 数据库扩展与初始化检查

服务器上执行：

```bash
docker compose exec postgres psql -U bidding -d bidding -c \
"select extname from pg_extension where extname in ('pgcrypto','vector') order by extname;"
```

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | pgcrypto 扩展可用 | 查询结果包含 `pgcrypto` | 已验证 |
| [x] | vector 扩展可用 | 查询结果包含 `vector` | RAG 必需，已验证 |
| [ ] | 初始化 SQL 已执行 | 关键业务表存在 | 由 `docker/postgres/init` 执行 |

### 8.1 业务库表初始化

当前 PostgreSQL 容器已启动且扩展可用，但业务表、登录表、RAG RPC、任务表和价格表仍需执行迁移脚本初始化。

服务器项目根目录执行：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
bash scripts/init_postgres_schema.sh
docker compose restart backend celery-worker frontend
```

验证：

```bash
# 核心表抽查：只会显示 IN 列表中的表，不代表数据库全量表数量。
docker compose exec postgres psql -U bidding -d bidding -c "
select table_name
from information_schema.tables
where table_schema='public'
  and table_name in (
    'app_users',
    'knowledge_documents',
    'document_chunks',
    'knowledge_assets',
    'bid_projects',
    'bid_files',
    'bid_sections',
    'bid_interpretation_tasks',
    'bid_generation_tasks',
    'bid_generation_task_items',
    'bid_export_tasks',
    'power_grid_goods_list_rows'
  )
order by table_name;"

# 全量业务表清单：用于和本地库表列表对齐。
docker compose exec postgres psql -U bidding -d bidding -c "
select table_name
from information_schema.tables
where table_schema='public'
  and table_type='BASE TABLE'
order by table_name;"

# 全量视图清单：AI 用量汇总等是 view，不在 BASE TABLE 里。
docker compose exec postgres psql -U bidding -d bidding -c "
select table_name
from information_schema.views
where table_schema='public'
order by table_name;"
```

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [ ] | 执行业务库表初始化脚本 | `scripts/init_postgres_schema.sh` 完成且无报错 | 登录失败时优先检查此项 |
| [ ] | 验证核心表存在 | 核心表抽查返回登录、RAG、项目、任务、导出相关表 | 至少包含 `app_users`、`knowledge_documents`、`document_chunks` |
| [ ] | 导出全量表/视图清单 | 全量表包含业务主表；视图包含 AI 用量汇总 | `alembic_version` 是本地迁移工具表，云上 SQL 初始化链路不强制要求 |
| [ ] | 重启应用容器 | backend/celery/frontend 重启后 healthy | 让新 schema 生效 |

## 9. RAG 种子库与客户资料入库

测试期先使用服务器本地项目目录和 Docker volume，不需要先把 `rag_seed` 上传到 OSS。

`rag_seed/power_grid_resources/` 是原始资料源，入库后系统主要依赖：

- PostgreSQL：`knowledge_documents`、`document_chunks`、`knowledge_assets`、`power_grid_goods_list_rows` 等表；
- 本地存储：`.env` 中 `STORAGE_PROVIDER=local`、`LOCAL_STORAGE_ROOT=storage` 对应的 Docker volume；
- OSS：仅正式多机部署、长期对象存储或客户明确要求云存储时再切换。

基础电网种子库入库命令：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
docker compose exec backend python scripts/rag/ingest_power_grid_v2.py --dry-run
docker compose exec backend python scripts/rag/ingest_power_grid_v2.py
```

入库后验证：

```bash
docker compose exec postgres psql -U bidding -d bidding -c "
select
  (select count(*) from public.knowledge_documents) as documents,
  (select count(*) from public.document_chunks) as chunks,
  (select count(*) from public.document_chunks where embedding is not null) as embedded_chunks;"
```

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [ ] | 确认 `rag_seed` 在服务器存在 | `rag_seed/power_grid_resources/index.csv` 存在 | Git 拉取或包上传后应已存在 |
| [ ] | RAG 种子库 dry-run | 输出 docs/parents/children 统计，无异常 | 不写数据库 |
| [ ] | RAG 种子库正式入库 | `knowledge_documents`、`document_chunks` 数量增加 | 需要 DashScope Embedding Key 可用 |
| [ ] | RAG 基础问答验证 | 企业知识库问答接口可返回内容和来源 | 2026-06-24 云上真实页面 3 条问答：1 条基本通过、2 条 FAIL；本地 P1C-14 已修复并通过三问真实 stream 复测，待推送部署后按同口径云上复测 |
| [ ] | 泰昌/辽宁客户资料专项入库 | 企业资信库、产品库、图片资产可见 | 需按专项脚本和 metadata 边界执行，不与基础种子库混跑 |

### 9.0 泰昌/辽宁企业知识库文档入库

企业知识库页面读取 `knowledge_documents` 和 `document_chunks`，与资信库/产品库读取的 `knowledge_assets` 是两条链路。资产入库完成后，企业知识库仍为 0 是正常现象，必须继续导入文本语料。

首批泰昌/辽宁文本语料不要使用原始 inventory manifest：

```text
parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/manifest.json
```

该文件包含原始清单记录，缺少 `parse_status=parsed` 和 `output_file`，`ingest_customer_corpus.py --dry-run` 会表现为 `documents=230 indexed=0 skipped=230 parents=0 children=0`。

应使用已解析 staging manifest：

```text
parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/staging_manifest.json
```

泰昌补充包文本语料使用：

```text
parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/manifest.json
```

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | 首批文本语料 dry-run | `skipped=0`、`blocked_metadata=0`、`parents/children/embedding_count > 0` | dry-run 下 `indexed=0` 属于正常 |
| [x] | 首批文本语料正式入库 | `knowledge_documents` 和 `document_chunks` 数量增加 | 已入库 `124` 个文档 |
| [x] | 补充包文本语料 dry-run | `skipped=0`、`blocked_metadata=0`、`parents/children/embedding_count > 0` | 使用补充包 manifest |
| [x] | 补充包文本语料正式入库 | 文档和 chunk 数继续增加 | 两批文本均已入库，文档总数约 `148` |
| [x] | 企业知识库页面验证 | 页面资料总数、已索引文件不再为 0 | 已可见企业知识库文件 |
| [x] | 企业知识库分类展示优化 | 左侧按 `doc_role/category_label/source_category` 展示中文细分类 | 根因是阿里云服务器前端源码未同步；同步 `frontend/src/pages/KnowledgeBase/index.tsx` 并重建 frontend 后恢复 |

### 9.1 泰昌企业资信库 / 产品库资产入库

产品库、资信库页面读取的是 `knowledge_assets` 表和本地存储文件，不是只读取 `knowledge_documents` / `document_chunks` 文本分块。新测试环境首次部署后这两个库为空是正常现象，需导入泰昌企业事实资产。

本阶段优先导入两个已整理批次：

- 首批泰昌 MVP 资产：`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/asset_staging_payloads.json`
- 泰昌补充资质资产：`parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/asset_staging_payloads.json`

如果服务器项目目录没有 `parsed_outputs`，需先从本地打包上传对应资产和图片目录，再复制进 backend 容器的 `/app/parsed_outputs` Docker volume。

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | 确认服务器存在资产 payload | 两个 `asset_staging_payloads.json` 均存在 | 首批 `960K`，补充批 `1.1M` |
| [x] | 确认 backend 容器可见资产文件 | 容器内 `/app/parsed_outputs/...` 可读 | 已 `docker cp parsed_outputs/.` 到 backend volume |
| [x] | 泰昌首批资产 dry-run | `missing_file=0`、`failed=0` | `total=242`，`failed=0` |
| [x] | 泰昌补充资产 dry-run | `missing_file=0`、`failed=0` | `total=297`，`failed=0` |
| [x] | 云上百炼 embedding 烟测 | backend 容器输出 `1 1024` | 已切到百炼在线 `text-embedding-v4` |
| [x] | 正式导入泰昌首批资产 | `knowledge_assets` 增加到 `242` | 资信 `105`、产品 `137`、embedding `242` |
| [x] | 正式导入泰昌补充资产 | `knowledge_assets` 总数增加到约 `539` | 实测总数 `538`，资信 `215`、产品 `323`、embedding `538` |
| [ ] | 页面验证产品库/资信库 | 页面可见泰昌产品、证照、资质、检验报告等资料 | 不得展示内部英文枚举 |
| [ ] | 记录资产入库报告 | 生成并保留 `aliyun_*assets_report.md/json` | 便于交接和回滚 |

## 10. 应用级冒烟测试

先做最小人工冒烟：

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [x] | 打开系统 | 浏览器能访问首页/登录页 | 已打开登录页；登录失败另查 |
| [x] | 登录或初始化用户 | 能进入工作台 | 已可正常注册、登录 |
| [ ] | 上传一个小 PDF/DOCX | 文件上传成功 | 先用小文件 |
| [ ] | 解析文件 | 解析状态变为完成或明确失败 | 若 MinerU token 未配，扫描 PDF 会失败 |
| [ ] | 生成解读 | 项目概况/要求/风险/评分可见 | |
| [ ] | 生成大纲 | 章节树生成成功 | |
| [ ] | 进入投标确认页 | 候选字段/缺口可见 | |
| [ ] | 生成一节正文 | SSE/任务状态正常，正文保存 | |
| [ ] | 运行合规检查 | 能输出覆盖/缺口/风险 | |
| [ ] | 企业知识库问答 | `/api/knowledge/search/stream` 正常返回且来源正确 | 2026-06-24 本地修复后通过：资质证书、CPVC 检验报告、企业证明材料三问 3/3 PASS；阿里云部署后必须复测同三问，通过前暂不进入最小标书主流程 |
| [ ] | 导出 DOCX | 能下载 Word 文件 | |
| [ ] | DOCX 字段刷新 | metadata 或日志显示刷新成功 | LibreOffice |

## 11. 后续专项验证

| 状态 | 任务 | 验收口径 | 备注 |
| --- | --- | --- | --- |
| [ ] | 跑 HTTP 冒烟脚本 | 上传 -> 解析 -> 解读 -> 大纲 -> 正文 -> 导出通过 | 脚本路径需按当前环境确认 |
| [ ] | 跑 RAG 本地门禁 | Base + 泰昌专项回归通过 | 需要已入库数据和模型 key |
| [ ] | 跑 DOCX 正式导出门禁 | 封面/目录/页眉页脚/表格/图片/字段刷新通过 | 正式演示前必跑 |
| [ ] | 人工打开 DOCX/PDF | 封面、目录、报价页、授权页、图片页观感可接受 | 客户最容易看到 |
| [ ] | 记录云上运行报告 | 写入 `docs/development/runs/` 或部署记录 | 便于交接 |

## 常用排障命令

### 前端重建后页面仍然是旧逻辑

典型症状：

- 已执行 `docker compose build --no-cache frontend` 和 `docker compose up -d --force-recreate frontend`；
- 无痕窗口访问后页面仍显示旧文案、旧分类或旧交互；
- 数据库和接口 Response 已确认是正确的。

优先判断顺序：

1. 先确认服务器源码是否是最新；
2. 再确认构建产物是否包含关键字符串；
3. 最后才考虑浏览器缓存或 Nginx 静态文件缓存。

服务器检查源码：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid

git branch --show-current
git log -1 --oneline
git status --short

# 用本次改动的关键函数/字段做确认，例如企业知识库分类展示：
grep -n "displayDocumentCategory" frontend/src/pages/KnowledgeBase/index.tsx
grep -n "category_label" frontend/src/pages/KnowledgeBase/index.tsx
```

如果 `grep` 没有输出，说明服务器源码不是最新。此时重建 Docker 没有意义，因为 Docker 只会把旧源码重新打包。

正确处理：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
git fetch origin feat/aliyun-test-readiness
git pull --ff-only origin feat/aliyun-test-readiness
git log -1 --oneline
```

如果只是临时从本地同步单文件，应立即记录，并在后续补 Git 提交：

```bash
scp frontend/src/pages/KnowledgeBase/index.tsx \
root@8.160.187.226:/opt/ai-bidding/ai_bidding_power_grid/frontend/src/pages/KnowledgeBase/index.tsx
```

重新构建前端：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
docker compose build --no-cache frontend
docker compose up -d --force-recreate frontend
```

验证容器静态包：

```bash
docker compose exec frontend sh -lc \
'grep -R "category_label" -n /usr/share/nginx/html/assets | head'
```

如果源码有、静态包没有，说明构建上下文或 Dockerfile 没吃到最新文件，需要删除前端镜像后重建：

```bash
docker compose down frontend
docker image rm -f ai-bidding-frontend:local
docker builder prune -f
docker compose build --no-cache frontend
docker compose up -d frontend
```

如果源码有、静态包也有，但页面仍旧：

- 使用无痕窗口重新打开；
- 或 DevTools -> Network -> 勾选 Disable cache -> 强制刷新；
- 在 Network 中打开接口，例如 `/api/knowledge/documents`，确认 Response 是否含新字段；
- 前端页面问题不要先改数据库或后端接口兜底，除非确认 API 合同本身缺字段。

本次企业知识库分类问题根因：

- 数据库 `knowledge_documents.metadata` 已有 `category_label`、`doc_role`、`source_category`；
- 本地前端已有 `displayDocumentCategory()`；
- 但阿里云服务器 `frontend/src/pages/KnowledgeBase/index.tsx` 没有该函数和 `category_label` 字符串；
- 因此之前多次重建 Docker 都是在重建旧源码；
- 同步最新前端文件并重建 frontend 后，左侧分类和表格分类恢复正常。

### Docker Hub 拉取超时

症状：

```text
failed to resolve source metadata for docker.io/library/nginx:1.27-alpine
dial tcp ...:443: i/o timeout
```

处理：

```bash
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.m.daocloud.io",
    "https://mirror.ccs.tencentyun.com"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  }
}
EOF

systemctl daemon-reload
systemctl restart docker
docker info | grep -A 10 "Registry Mirrors"
docker pull nginx:1.27-alpine
docker pull node:22-alpine
docker pull python:3.12-slim
```

镜像能拉取后，回到项目目录重新执行：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
docker compose build backend frontend
```

查看容器状态：

```bash
docker compose ps
```

查看后端日志：

```bash
docker compose logs --tail=200 backend
```

查看 worker 日志：

```bash
docker compose logs --tail=200 celery-worker
```

查看前端/Nginx 日志：

```bash
docker compose logs --tail=200 frontend
```

重启服务：

```bash
docker compose restart backend celery-worker frontend
```

重新构建并启动：

```bash
docker compose build backend frontend
docker compose up -d
```

进入后端容器：

```bash
docker compose exec backend bash
```

检查 LibreOffice：

```bash
docker compose exec backend soffice --version
```

检查正式 DOCX 中文字体匹配：

```bash
docker compose exec backend bash -lc 'fc-match FangSong_GB2312 && fc-match SimHei && fc-match KaiTi_GB2312'
```

若返回 DejaVu、Noto Sans CJK 之外的异常空值，需在镜像或宿主机安装中文字体包并执行 `fc-cache -fv` 后重启 backend/celery。

检查数据库：

```bash
docker compose exec postgres psql -U bidding -d bidding
```

## 执行记录

| 时间 | 执行人 | 操作 | 结果 | 备注 |
| --- | --- | --- | --- | --- |
| 2026-06-22 | Codex | 创建部署 checklist | 完成 |  |
| 2026-06-22 | chris | 完成首次 SSH 登录与系统信息确认 | 通过 | root 登录成功；Ubuntu 22.04.5；磁盘/内存/私网 IP 正常 |
| 2026-06-22 | chris | 完成 Ubuntu 基础初始化 | 通过 | apt 更新、系统升级、时区、基础工具安装完成；无服务需重启 |
| 2026-06-22 | chris | 完成 Docker 与 Docker Compose 安装 | 通过 | Docker 29.0.0；Compose v5.1.4；docker active/enabled |
| 2026-06-22 | chris | 完成 Gitee SSH key 配置 | 通过 | `ssh -T git@gitee.com` 返回 successfully authenticated |
| 2026-06-22 | chris | 拉取 Gitee 指定部署分支 | 通过 | `feat/aliyun-test-readiness`；关键 Docker 文件和 `.env.example` 存在 |
| 2026-06-22 | chris | 完成 backend/frontend 镜像构建 | 通过 | `ai-bidding-backend:local`、`ai-bidding-frontend:local` Built；首次构建耗时约 38 分钟 |
| 2026-06-22 | chris | 启动 PostgreSQL/Redis 并验证扩展 | 通过 | postgres/redis healthy；`pgcrypto` 和 `vector` 扩展存在 |
| 2026-06-22 | chris | 启动 backend/celery/frontend 并完成本机健康检查 | 通过 | backend API、frontend 反代 API、frontend 首页均返回 200 |
| 2026-06-22 | chris | 完成公网 8080 访问验证 | 部分通过 | 登录页可访问；账号登录报服务器处理失败，待查后端日志/用户表 |
| 2026-06-23 | chris | 完成 DeepSeek 与百炼 Key 连通性验证 | 通过 | DeepSeek `chat/completions` 返回 `ok`；百炼 embedding 本地返回向量 |
| 2026-06-23 | chris | 上传云上 `.env` 并重启 backend/celery | 通过 | backend/celery running；百炼 embedding 容器烟测输出 `1 1024` |
| 2026-06-23 | chris | 完成泰昌资产 payload 准备和 dry-run | 通过 | 首批 `242`、补充批 `297`；两批 dry-run 均 `failed=0` |
| 2026-06-23 | chris/Codex | 首批资产正式入库触发百炼 batch size 限制 | 待重试 | 百炼 embedding 报 `batch_size ... should not be larger than 10`；已将 `scripts/rag/ingest_taichang_assets.py` 的 `batch_size` 从 `20` 调整为 `10` |
| 2026-06-23 | chris | 修复首批资产文件缺失并正式导入 | 通过 | 重新上传/复制完整 `customer_liaoning_taichang_20260606_p0`；入库 `242`，embedding `242` |
| 2026-06-23 | chris | 修复泰昌补充批 `rag_seed` 文件缺失并重跑 dry-run | 通过 | 复制 `02_泰昌资质文件补充_20260611` 到 backend 容器；首条文件存在；补充批 dry-run `total=297 failed=0` |
| 2026-06-23 | chris | 正式导入泰昌补充批资产 | 通过 | `knowledge_assets` 总数 `538`；资信 `215`、产品 `323`、embedding `538` |
| 2026-06-23 | chris | 企业知识库文档入库 dry-run 使用原始 manifest | 未通过 | `knowledge_documents=0`、`document_chunks=0`；原始 `manifest.json` dry-run 为 `documents=230 skipped=230`，下一步改用 `staging/staging_manifest.json` |
| 2026-06-23 | chris | 完成两批企业知识库文本语料入库 | 通过 | 首批 `124` 文档，补充包约 `24` 文档；企业知识库页面已有数据 |
| 2026-06-23 | Codex | 修复企业知识库分类展示逻辑 | 已部署 | 前端改为优先按 `metadata.category_label/doc_role/source_category` 展示中文细分类 |
| 2026-06-23 | chris/Codex | 排查企业知识库分类仍显示单一“电网招标文件” | 通过 | 根因不是数据库、浏览器缓存或 Docker 缓存，而是阿里云服务器前端源码未同步；服务器 `grep displayDocumentCategory/category_label` 无输出，导致重建的是旧源码 |
| 2026-06-23 | chris | 同步最新 `KnowledgeBase/index.tsx` 并重建 frontend | 通过 | 无痕窗口验证企业知识库分类已正常显示 |
| 2026-06-23 | Codex | 补充阿里云测试环境代码发布 SOP 与排障说明 | 完成 | 新增 Gitee 分支提交流程、服务器拉取 commit、前后端镜像构建、缓存排查和执行记录要求 |
| 2026-06-24 | Codex | 阿里云企业知识库 3 条真实问答冒烟 | 部分通过 | 环境 ready；CPVC 检验报告基本正确，资质证书和企业证明材料问答失败；发现正式证书未优先、基础证照误判缺失、社保证明错误归类及内部枚举/路径暴露，详见 `docs/rag/runs/run_20260624_aliyun_enterprise_knowledge_qa_smoke.md` |
| 2026-06-24 | Codex | P1C-14 本地修复与真实回归 | 本地通过 | 修复企业知识库事实来源优先级、中文展示清洗、社保证明归类和 Ollama embedding 兼容；本地 RAG 门禁 PASS，三问真实 stream 3/3 PASS，详见 `docs/rag/runs/run_20260624_p1c14_local_final_three_question_stream_summary.md` |

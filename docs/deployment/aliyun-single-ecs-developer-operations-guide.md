# 阿里云单 ECS 部署与运维交接手册

**适用对象：** 开发人员、发布人员、运维人员

**适用环境：** 国家电网 AI 标书系统单企业 MVP 测试环境

**部署形态：** Ubuntu 22.04 + Docker Compose + 单 ECS

**维护团队：** AI 标书项目研发与运维团队

**最后复核：** 2026-06-27

**上游实施记录：** [阿里云 Ubuntu 单 ECS 测试部署操作清单](aliyun-ubuntu-single-ecs-deploy-checklist-20260622.md)

## 1. 文档目标

本文是可直接执行的部署与运维手册，用于完成以下工作：

- 新接手人员快速理解云上架构、代码来源、数据位置和安全边界；
- 完成首次部署、日常前端发布、后端发布和全栈发布；
- 完成客户验收前的强制干净发布，排除旧容器、旧镜像和浏览器缓存影响；
- 在不覆盖客户数据的前提下处理服务器本地改动和 Git 拉取失败；
- 完成数据库初始化、健康检查、日志排查、备份和版本回滚；
- 按统一格式记录发布结果，减少“服务器代码、Git 提交、容器镜像不一致”的问题。

本文不替代以下专项文档：

- RAG 数据入库与评测：参见 [RAG 文档索引](../rag/README.md)；
- DOCX 正式导出质量：参见 [DOCX 投标文件导出质量清单](../development/docx-bid-export-quality-todo.md)；
- 阿里云生产目标架构：参见 [阿里云目标架构](aliyun-target-architecture.md)；
- 详细安全配置：参见 [安全配置说明](security.md)。

## 2. 当前环境基线

### 2.1 服务器信息

| 项目 | 当前值 |
| --- | --- |
| 公网 IP | `8.160.187.226` |
| 操作系统 | Ubuntu 22.04 64 位 |
| ECS 规格 | 8 vCPU / 16 GiB / 200 GiB |
| 部署目录 | `/opt/ai-bidding/ai_bidding_power_grid` |
| Git 来源 | `git@gitee.com:mainiutech/ai-bid.git` |
| 测试分支 | `feat/aliyun-test-readiness` |
| 测试入口 | `http://8.160.187.226:8080` |
| 正式演示入口 | 设置 `FRONTEND_HTTP_PORT=80` 后使用 `http://8.160.187.226` |
| 时区 | `Asia/Shanghai` |

> 公网 IP、分支和端口是当前测试环境基线。环境迁移后，应先更新本节，再执行本文命令。

### 2.2 服务拓扑

```text
外部浏览器
    |
    | TCP 8080（测试）/ TCP 80（正式演示）
    v
Frontend / Nginx
    |
    | /api/* 反向代理
    v
Backend / Gunicorn ------ PostgreSQL 16 + pgvector
    |                              |
    | Redis Queue                  | 业务数据、RAG 数据、任务状态
    v                              |
Celery Worker ---------------------+
    |
    +-- 本地 Docker volumes
        uploads / outputs / storage / backups / parsed_outputs
```

### 2.3 Compose 服务

| 服务 | 容器名称 | 宿主机端口 | 作用 | 是否保存业务数据 |
| --- | --- | --- | --- | --- |
| `postgres` | `ai-bidding-postgres` | `15432 -> 5432` | PostgreSQL、pgvector、业务库 | 是 |
| `redis` | `ai-bidding-redis` | `16379 -> 6379` | Celery 队列和运行态 | 部分 |
| `backend` | `ai-bidding-backend` | `3012 -> 8000` | API、解析、检索、导出 | 否 |
| `celery-worker` | `ai-bidding-celery-worker` | 无公网端口 | 异步解析、生成任务 | 否 |
| `frontend` | `ai-bidding-frontend` | `${FRONTEND_HTTP_PORT:-8080} -> 80` | Web 静态文件和 API 反代 | 否 |

持久化数据位于 Docker volumes：

```text
postgres_data
app_uploads
app_outputs
app_storage
app_backups
app_parsed_outputs
```

容器可以重建，volume 不得随意删除。

## 3. 角色与职责

### 3.1 开发人员

- 在本地完成功能开发、构建和必要测试；
- 只提交本次功能相关文件，不提交 `.env`、密钥和客户临时资料；
- 推送到约定的 Gitee 分支；
- 向发布人员提供目标 commit、改动范围、迁移要求和验收路径；
- 对业务功能、RAG 边界和 DOCX 结果负责。

### 3.2 发布或运维人员

- 发布前检查服务器状态、磁盘、Git 工作区和数据备份；
- 确认服务器拉取到开发人员指定的 commit；
- 根据改动范围重建对应镜像，不做无必要的全量重启；
- 执行健康检查、日志检查和浏览器冒烟；
- 记录发布时间、commit、构建服务、验证结果和异常；
- 发现数据丢失风险时停止操作并升级处理。

### 3.3 共同责任

- 不在聊天、截图、Git 或部署文档中暴露 `.env` 完整内容；
- 不使用辽宁招标资料或河北豪乾参考稿生成泰昌企业事实；
- 不把服务器手工改动当成长期发布方式；
- 不在未备份、未确认影响范围时执行数据库清理或 volume 删除。

## 4. 访问权限与前置条件

执行部署前确认：

- [ ] 可以通过 SSH 登录 ECS；
- [ ] Gitee SSH key 已配置，`ssh -T git@gitee.com` 成功；
- [ ] 当前账号可以执行 Docker 命令；
- [ ] 项目根目录存在 `.env`，且权限不对普通用户开放；
- [ ] 已获得本次发布的目标分支和目标 commit；
- [ ] 已明确本次改动属于前端、后端、数据库、RAG 数据或组合改动；
- [ ] 数据库或数据处理改动已准备备份和回滚方案。

连接服务器：

```bash
ssh root@8.160.187.226
cd /opt/ai-bidding/ai_bidding_power_grid
```

基础环境检查：

```bash
whoami
date
df -h
free -h
docker --version
docker compose version
systemctl is-active docker
```

健康标准：

- 根分区剩余空间建议不少于 `20 GiB`；
- Docker 状态为 `active`；
- 系统时间为北京时间；
- 不存在持续重启或 unhealthy 的核心容器。

## 5. 安全边界

### 5.1 网络

- 公网只开放业务入口和受控 SSH；
- `15432`、`16379`、`3012` 不得通过阿里云安全组对公网开放；
- 测试期入口为 `8080`，正式环境应迁移到域名、HTTPS 和 `80/443`；
- SSH `22` 应限制为办公出口 IP 或临时白名单。

### 5.2 密钥与配置

服务器 `.env` 至少应满足：

```text
APP_ENV=production
REQUIRE_STRICT_CONFIG=true
APP_LOCAL_ONLY=false
APP_AUTH_ENABLED=true
APP_LOGIN_ENABLED=true
APP_COOKIE_SECURE=false
DB_PROVIDER=postgres
STORAGE_PROVIDER=local
CONTAINER_SOFFICE_BIN=/usr/bin/soffice
```

当前使用 HTTP 测试入口，因此 `APP_COOKIE_SECURE=false`。启用 HTTPS 后应改为：

```text
APP_COOKIE_SECURE=true
```

生成高强度会话密钥：

```bash
openssl rand -hex 32
```

检查 `.env` 权限：

```bash
chmod 600 .env
ls -l .env
```

禁止执行：

```bash
cat .env
git add .env
docker compose config
```

`docker compose config` 可能展开环境变量并将敏感值输出到终端记录。需要校验 Compose 时使用：

```bash
docker compose config --quiet
```

## 6. 开发人员发布准备

### 6.1 本地检查

```bash
cd /Users/chris/Documents/项目/AI标书项目/ai_bidding_power_grid
git branch --show-current
git status --short
git diff
```

目标分支为：

```text
feat/aliyun-test-readiness
```

只暂存本次改动：

```bash
git add <文件1> <文件2>
git diff --cached
git commit -m "<type>: <简短说明>"
git push gitee feat/aliyun-test-readiness
```

记录目标版本：

```bash
git rev-parse HEAD
git log -1 --oneline
```

### 6.2 发布信息

开发人员交给运维人员的信息必须包含：

| 字段 | 示例 |
| --- | --- |
| 分支 | `feat/aliyun-test-readiness` |
| commit | `68ad2a8` |
| 改动范围 | `frontend` |
| 是否包含数据库迁移 | 否 |
| 是否需要 RAG 入库 | 否 |
| 构建服务 | `frontend` |
| 验收路径 | 首页、企业资信库、企业产品库 |
| 回滚 commit | 发布前服务器 commit |

## 7. 标准发布流程

### 7.1 发布前检查

服务器执行：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid

git branch --show-current
git log -1 --oneline
git status --short
docker compose ps
df -h
curl -fsS http://127.0.0.1:8080/api/health
```

记录发布前 commit：

```bash
git rev-parse HEAD | tee /tmp/ai-bidding-before-release.commit
```

如果 `git status --short` 显示已修改源码，不要直接 pull。按第 8 节处理。

### 7.2 拉取目标版本

```bash
git remote -v
GIT_REMOTE=origin
git fetch "${GIT_REMOTE}" feat/aliyun-test-readiness
git checkout feat/aliyun-test-readiness
git pull --ff-only "${GIT_REMOTE}" feat/aliyun-test-readiness
git log -1 --oneline
git rev-parse --short=12 HEAD
```

当前服务器克隆仓库使用 `origin` 指向 Gitee。若后续环境的 remote 名不同，先用以下命令确认并替换 `GIT_REMOTE`：

```bash
git remote -v
```

构建前必须确认 `git log -1 --oneline` 和 `git rev-parse --short=12 HEAD` 与开发人员提供的 commit 一致。若有人误把本地开发机的 remote 名 `gitee` 复制到服务器，而服务器只有 `origin`，会出现 `fatal: 'gitee' does not appear to be a git repository`，此时应改用 `origin`，不要重新 clone。

### 7.3 前端发布

适用于 `frontend/` 下页面、组件、样式、接口调用或构建配置变更。

```bash
unset BUILD_ID BUILD_COMMIT BUILD_BRANCH BUILD_TIME
export BUILD_COMMIT="$(git rev-parse --short=12 HEAD)"
export BUILD_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
export BUILD_TIME="$(date -Iseconds)"
export BUILD_ID="$(date +%Y%m%d%H%M%S)-${BUILD_COMMIT}"
echo "${BUILD_ID}"

docker compose build frontend
docker compose up -d --force-recreate frontend
docker compose ps frontend
```

前端构建版本说明：

- Docker 构建上下文排除了 `.git/`，构建容器内不能直接读取 Git commit；
- 每次前端发布都必须显式注入 `BUILD_ID`、`BUILD_COMMIT`、`BUILD_BRANCH`、`BUILD_TIME`；
- 不要在 `.env` 长期写死 `BUILD_*`，否则后续发布可能出现“代码已更新，但 `/build-info.json` 仍是旧 commit”。

验证：

```bash
curl -fsS -I http://127.0.0.1:8080/
curl -fsS http://127.0.0.1:8080/build-info.json
docker compose exec frontend sh -lc 'cat /usr/share/nginx/html/build-info.json'
docker compose logs --tail=100 frontend
```

验收口径：`curl` 和容器内 `build-info.json` 的 `commit` 必须等于 `git rev-parse --short=12 HEAD`。

常规发布不要默认使用 `--no-cache`。`--no-cache` 会重新执行 `npm ci`，阿里云 ECS 到 npm 源网络不稳定时可能出现 `ECONNRESET`。只有在依赖变更或明确怀疑依赖层损坏时再使用无缓存构建。需要无缓存构建前，建议先配置临时国内 npm 镜像：

```bash
cat > frontend/.npmrc <<'EOF'
registry=https://registry.npmmirror.com
fetch-retries=5
fetch-retry-mintimeout=20000
fetch-retry-maxtimeout=120000
EOF

unset BUILD_ID BUILD_COMMIT BUILD_BRANCH BUILD_TIME
export BUILD_COMMIT="$(git rev-parse --short=12 HEAD)"
export BUILD_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
export BUILD_TIME="$(date -Iseconds)"
export BUILD_ID="$(date +%Y%m%d%H%M%S)-${BUILD_COMMIT}"

docker compose build --no-cache frontend
docker compose up -d --force-recreate frontend
```

如果 Git 已是目标版本但构建结果仍显示旧 commit，先检查当前 shell 或 Compose 配置中是否残留旧构建变量：

```bash
env | grep '^BUILD_' || true
docker compose config | sed -n '/frontend:/,/healthcheck:/p' | grep BUILD -n || true
```

浏览器使用无痕窗口验证，或在 DevTools 中禁用缓存后强制刷新。

如果属于客户验收前发布、线上空表/旧页面排障或前后端 commit 不一致，直接使用第 7.6 节“强制干净发布”，不要只重启 frontend。

### 7.4 后端发布

适用于 `backend/`、`scripts/`、Python 依赖、RAG 检索、解析、导出或任务逻辑变更。

#### 7.4.1 测试环境快速后端代码发布

阿里云单 ECS 测试环境允许使用 `docker-compose.aliyun-dev.yml` 将后端源码以只读 bind mount 挂入容器。这样在 **未修改 Python 依赖、系统依赖或 Dockerfile** 时，后端代码改动不需要重新构建 backend 镜像，只需要拉取代码并重启 `backend` 与 `celery-worker`。

适用范围：

- `backend/` 下 Python 业务代码；
- `scripts/` 下运行脚本；
- `main.py`、`gunicorn.conf.py`。

不适用范围：

- 修改 `requirements.txt`；
- 修改 `Dockerfile.backend`；
- 修改 apt/LibreOffice/字体等系统依赖；
- 修改前端代码；
- 需要验证“完整镜像可独立运行”的正式发布。

首次启用或确认 override 生效：

```bash
docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml up -d --force-recreate backend celery-worker
```

之后纯后端代码发布：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
git fetch origin feat/aliyun-test-readiness
git pull --ff-only origin feat/aliyun-test-readiness
git log -1 --oneline

docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml restart backend celery-worker
docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml ps backend celery-worker
```

验证容器看到的是服务器源码：

```bash
docker compose -f docker-compose.yml -f docker-compose.aliyun-dev.yml exec backend sh -lc \
  'grep -n "只回答已命中的资质证书" /app/backend/rag/retrieval.py || true'
```

注意：该方式是测试环境提速手段。正式生产环境仍应优先使用完整镜像构建发布，避免运行代码与镜像内容不一致。

#### 7.4.2 完整后端镜像发布

```bash
docker compose build backend
docker compose up -d --force-recreate backend celery-worker
docker compose ps backend celery-worker
```

验证：

```bash
curl -fsS http://127.0.0.1:3012/api/health
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS http://127.0.0.1:8080/api/ready
docker compose logs --tail=100 backend
docker compose logs --tail=100 celery-worker
```

`/api/health` 只验证进程存活。`/api/ready` 会检查 PostgreSQL、pgvector、Redis、存储和模型配置，发布验收应以后者为准。

### 7.5 前后端联合发布

```bash
unset BUILD_ID BUILD_COMMIT BUILD_BRANCH BUILD_TIME
export BUILD_COMMIT="$(git rev-parse --short=12 HEAD)"
export BUILD_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
export BUILD_TIME="$(date -Iseconds)"
export BUILD_ID="$(date +%Y%m%d%H%M%S)-${BUILD_COMMIT}"

docker compose build backend frontend
docker compose up -d --force-recreate backend celery-worker frontend
docker compose ps
```

验证：

```bash
curl -fsS http://127.0.0.1:3012/api/health
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS http://127.0.0.1:8080/api/ready
curl -fsS http://127.0.0.1:8080/build-info.json
curl -fsS -I http://127.0.0.1:8080/
```

### 7.6 客户验收前强制干净发布

该流程用于客户验收、缓存排障、线上页面疑似运行旧包、`/build-info.json` 与 `/api/health` commit 不一致等场景。它会删除并重建 `frontend/backend/celery-worker` 容器，清理 Docker build cache，并使用 `--no-cache` 重新构建镜像。

该流程不会删除 PostgreSQL、Redis 或业务数据 volume。禁止把它改成 `docker compose down -v`。

1. 确认目标代码版本：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
git remote -v
GIT_REMOTE=origin
git fetch "${GIT_REMOTE}" feat/aliyun-test-readiness
git checkout feat/aliyun-test-readiness
git pull --ff-only "${GIT_REMOTE}" feat/aliyun-test-readiness
git status --short
git rev-parse --short=12 HEAD
git log -1 --oneline
```

2. 设置前端构建版本变量：

```bash
unset BUILD_ID BUILD_COMMIT BUILD_BRANCH BUILD_TIME
export BUILD_COMMIT="$(git rev-parse --short=12 HEAD)"
export BUILD_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
export BUILD_TIME="$(date -Iseconds)"
export BUILD_ID="$(date +%Y%m%d%H%M%S)-${BUILD_COMMIT}"
echo "${BUILD_ID}"
```

3. 停止并移除可重建服务旧容器：

```bash
docker compose stop frontend backend celery-worker
docker compose rm -f frontend backend celery-worker
```

4. 清理 Docker 构建缓存并无缓存重建：

```bash
docker builder prune -f
docker compose build --no-cache backend frontend
```

如果 `celery-worker` 在当前 Compose 中有单独 build 配置，可补充执行；若它复用 backend 镜像或提示无需构建，可忽略：

```bash
docker compose build --no-cache celery-worker
```

5. 强制重建启动：

```bash
docker compose up -d --force-recreate --remove-orphans backend celery-worker frontend
docker compose ps
```

6. 验证版本和健康状态：

```bash
TARGET_COMMIT="$(git rev-parse --short=12 HEAD)"
echo "target=${TARGET_COMMIT}"

curl -fsS http://127.0.0.1:3012/api/health
curl -fsS http://127.0.0.1:3012/api/ready
curl -fsS http://127.0.0.1:${FRONTEND_HTTP_PORT:-80}/build-info.json || curl -fsS http://127.0.0.1:8080/build-info.json
docker compose exec frontend sh -lc 'cat /usr/share/nginx/html/build-info.json'
```

验收口径：

- Git HEAD、`/api/health` 的 `version.commit`、`/build-info.json` 的 `commit` 三者一致；
- backend、celery-worker、frontend 均为 `Up`，backend health 通过；
- 浏览器使用无痕窗口访问，或 DevTools -> Network -> Disable cache -> Empty Cache and Hard Reload 后验证；
- 产品库、资信库、历史记录、DOCX 导出等本次改动路径全部真实点击验证。

禁止操作：

```bash
docker compose down -v
docker volume rm postgres_data
docker volume rm app_uploads app_outputs app_storage app_backups app_parsed_outputs
git reset --hard
git clean -fdx
```

### 7.7 公网 80 入口切换

正式演示入口需要使用 `http://8.160.187.226` 时，先确认阿里云安全组放通 TCP `80`，再执行：

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
grep -q '^FRONTEND_HTTP_PORT=' .env && sed -i 's/^FRONTEND_HTTP_PORT=.*/FRONTEND_HTTP_PORT=80/' .env || echo 'FRONTEND_HTTP_PORT=80' >> .env
grep -q '^APP_PUBLIC_BASE_URL=' .env && sed -i 's#^APP_PUBLIC_BASE_URL=.*#APP_PUBLIC_BASE_URL=http://8.160.187.226#' .env || echo 'APP_PUBLIC_BASE_URL=http://8.160.187.226' >> .env
docker compose up -d frontend backend celery-worker
curl -fsS http://127.0.0.1/api/health
curl -fsS -I http://127.0.0.1/
```

若继续使用测试端口，保持 `FRONTEND_HTTP_PORT=8080` 或不设置该变量，并告知客户入口为 `http://8.160.187.226:8080`。

### 7.8 数据库迁移发布

数据库变更属于高风险操作。必须先执行第 10 节数据库备份，并确认迁移脚本支持重复执行。

推荐迁移入口：

```bash
scripts/migrate_postgres.sh
```

首次环境或手工排障可使用：

```bash
bash scripts/init_postgres_schema.sh
```

迁移后验证：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -At -c \
"select extname from pg_extension where extname in ('pgcrypto','vector') order by extname;"

docker compose exec -T postgres psql -U bidding -d bidding -At -c \
"select proname from pg_proc where proname in ('match_knowledge_chunks','match_knowledge_assets') order by proname;"

docker compose exec -T postgres psql -U bidding -d bidding -At -c \
"select table_name from information_schema.tables where table_schema='public' and table_name in ('app_users','bid_projects','knowledge_documents','document_chunks','knowledge_assets','bid_generation_tasks','bid_export_tasks') order by table_name;"
```

迁移完成后重建或重启受影响服务：

```bash
docker compose up -d --force-recreate backend celery-worker
```

## 8. 服务器存在本地改动时的处理

### 8.1 判断含义

以下输出不是 Git 合并冲突：

```text
error: Your local changes to the following files would be overwritten by merge
```

它表示服务器工作区存在未提交修改，Git 为防止覆盖而中止拉取。

### 8.2 标准处理

先备份差异：

```bash
mkdir -p /root/ai-bidding-release-backups
git diff > /root/ai-bidding-release-backups/server-local-changes-$(date +%Y%m%d-%H%M%S).patch
git status --short
```

只暂存已修改的跟踪文件，不要把客户压缩包和大文件放入 stash：

```bash
git stash push -m "server manual changes before release $(date +%Y%m%d-%H%M%S)" -- \
  <已修改文件1> \
  <已修改文件2>
```

然后拉取：

```bash
git pull --ff-only origin feat/aliyun-test-readiness
git log -1 --oneline
git stash list
```

不要立即执行 `git stash pop`。先比较暂存改动是否已经包含在新提交中：

```bash
git stash show --stat stash@{0}
git stash show -p stash@{0}
```

确认线上功能正常且暂存内容不再需要后，再删除：

```bash
git stash drop stash@{0}
```

### 8.3 未跟踪文件

`git status` 中的 `??` 表示未跟踪文件。未跟踪的客户资料包通常不会阻止 fast-forward pull，但应移出代码目录，避免误提交和构建上下文膨胀：

```bash
mkdir -p /opt/ai-bidding/packages
mv <资料包.tar.gz> /opt/ai-bidding/packages/
```

移动前必须确认该文件当前没有被入库脚本使用。

### 8.4 禁止操作

未经负责人明确确认，不得执行：

```bash
git reset --hard
git clean -fd
git clean -fdx
docker compose down -v
docker volume rm <volume>
```

这些命令可能删除服务器热修复、客户资料、数据库、上传文件和导出文件。

## 9. 首次部署

### 9.1 初始化系统

```bash
apt update
apt upgrade -y
timedatectl set-timezone Asia/Shanghai
apt install -y curl wget git vim htop unzip zip ca-certificates gnupg lsb-release
```

安装 Docker 后确认：

```bash
docker --version
docker compose version
systemctl enable docker
systemctl start docker
```

### 9.2 拉取代码

```bash
mkdir -p /opt/ai-bidding
cd /opt/ai-bidding
git clone -b feat/aliyun-test-readiness --single-branch \
  git@gitee.com:mainiutech/ai-bid.git ai_bidding_power_grid
cd ai_bidding_power_grid
```

### 9.3 配置环境变量

```bash
cp .env.example .env
chmod 600 .env
vim .env
```

至少配置：

- 应用公网地址和 CORS；
- PostgreSQL 强密码；
- 登录会话密钥；
- DeepSeek API Key；
- DashScope API Key、Embedding 模型和 Rerank 模型；
- 本地存储或 OSS 配置；
- LibreOffice 容器路径；
- 泰昌企业主体信息。

不要直接沿用 `.env.example` 中的示例密码和占位密钥。

### 9.4 构建和启动

```bash
docker compose config --quiet
docker compose build backend frontend
docker compose up -d postgres redis
docker compose ps postgres redis
```

确认 PostgreSQL 和 Redis healthy 后：

```bash
docker compose up -d backend celery-worker frontend
docker compose ps
```

### 9.5 初始化数据库

```bash
bash scripts/init_postgres_schema.sh
docker compose restart backend celery-worker frontend
```

### 9.6 首次验收

```bash
curl -fsS http://127.0.0.1:3012/api/health
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS http://127.0.0.1:8080/api/ready
curl -fsS -I http://127.0.0.1:8080/
docker compose exec backend soffice --version
```

首次部署完成不等于业务数据已准备完成。企业知识库、资信库和产品库还需要按 RAG 专项 SOP 入库。

## 10. 备份与恢复

### 10.1 发布前数据库备份

创建仅 root 可访问的备份目录：

```bash
install -d -m 700 /opt/ai-bidding/backups
```

执行 PostgreSQL 逻辑备份：

```bash
BACKUP_FILE="/opt/ai-bidding/backups/bidding-$(date +%Y%m%d-%H%M%S).dump"
docker compose exec -T postgres pg_dump \
  -U bidding -d bidding -Fc > "$BACKUP_FILE"
ls -lh "$BACKUP_FILE"
```

校验备份可读取：

```bash
pg_restore --list "$BACKUP_FILE" | head
```

如果宿主机没有 `pg_restore`，在临时 PostgreSQL 容器中校验：

```bash
docker run --rm -v /opt/ai-bidding/backups:/backups postgres:16 \
  pg_restore --list "/backups/$(basename "$BACKUP_FILE")" | head
```

### 10.2 文件数据备份

上传、导出、知识资产和解析结果保存在 Docker volumes。先查看真实 volume 名称：

```bash
docker volume ls --format '{{.Name}}' | grep ai_bidding
```

使用只读挂载备份单个 volume。以下以 `app_storage` 对应的真实 volume 名称为例：

```bash
VOLUME_NAME="<docker volume ls 查到的 storage volume 名称>"
docker run --rm \
  -v "${VOLUME_NAME}:/source:ro" \
  -v /opt/ai-bidding/backups:/backup \
  alpine:3.20 \
  tar -czf "/backup/${VOLUME_NAME}-$(date +%Y%m%d-%H%M%S).tar.gz" -C /source .
```

对 `app_uploads`、`app_outputs`、`app_storage` 和 `app_parsed_outputs` 分别执行。大文件备份前先检查磁盘空间。

### 10.3 数据库恢复

数据库恢复会覆盖或叠加现有数据，必须在维护窗口执行。先停止业务写入：

```bash
docker compose stop backend celery-worker frontend
```

恢复到新建空库最安全。若必须恢复当前测试库，应先得到负责人确认。示例：

```bash
cat <备份文件.dump> | docker compose exec -T postgres pg_restore \
  -U bidding -d bidding --clean --if-exists --no-owner
```

恢复后：

```bash
docker compose start backend celery-worker frontend
curl -fsS http://127.0.0.1:8080/api/ready
```

## 11. 版本回滚

### 11.1 仅回滚应用代码

读取发布前版本：

```bash
cat /tmp/ai-bidding-before-release.commit
```

创建回滚分支，避免改动正式分支指针：

```bash
ROLLBACK_COMMIT="$(cat /tmp/ai-bidding-before-release.commit)"
git checkout -b "rollback/aliyun-$(date +%Y%m%d-%H%M%S)" "$ROLLBACK_COMMIT"
```

按改动范围重建：

```bash
docker compose build frontend
docker compose up -d --force-recreate frontend
```

或：

```bash
docker compose build backend
docker compose up -d --force-recreate backend celery-worker
```

完成健康检查后，在发布记录中注明临时运行的 rollback 分支和 commit。故障处理完成后，应由开发人员在正式分支提交修复，不要长期运行临时回滚分支。

### 11.2 数据库回滚

- 仅代码回滚且 schema 向后兼容时，不恢复数据库；
- 数据迁移不可逆或已污染数据时，使用第 10 节备份恢复；
- RAG 批次数据优先使用 `scripts/rag/rollback_customer_corpus.py` 按 `ingestion_batch_id` dry-run，再经确认执行；
- 禁止用 `docker compose down -v` 代替数据库回滚。

## 12. 发布后业务验收

### 12.1 基础技术检查

```bash
docker compose ps
curl -fsS http://127.0.0.1:3012/api/health
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS http://127.0.0.1:8080/api/ready
curl -fsS -I http://127.0.0.1:8080/
```

成功标准：

- 所有核心服务为 `running` 或 `healthy`；
- `/api/health` 返回 HTTP 200；
- `/api/ready` 返回 HTTP 200，关键 checks 通过；
- 首页返回 HTTP 200；
- 日志没有持续循环异常。

### 12.2 MVP 业务冒烟

按优先级执行：

1. 登录系统；
2. 打开企业资信库和企业产品库；
3. 检查泰昌证照、资质、检验报告和产品图片；
4. 点开图片或资料，确认文件可加载；
5. 确认页面不展示 `enterprise_evidence`、`product_image`、`taichang_*` 等内部值；
6. 企业知识库询问泰昌资质、CPVC 检验报告和企业证明材料；
7. 使用小型 PDF/DOCX 跑上传、解析、解读、大纲、单节正文、合规检查；
8. 导出 DOCX 并使用 Word/WPS 打开；
9. 检查封面、目录、正文、页眉页脚、页码和图片。

涉及 RAG、企业事实来源或 DOCX 的改动，应按项目 AGENTS.md 要求补专项真实链路和运行记录。

## 13. 日常巡检

### 13.1 每日或演示前

```bash
cd /opt/ai-bidding/ai_bidding_power_grid
docker compose ps
curl -fsS http://127.0.0.1:8080/api/ready
df -h
docker system df
```

检查最近错误：

```bash
docker compose logs --since=24h backend | grep -Ei 'error|exception|traceback' | tail -100
docker compose logs --since=24h celery-worker | grep -Ei 'error|exception|traceback' | tail -100
docker compose logs --since=24h frontend | grep -Ei 'error|crit|alert' | tail -100
```

### 13.2 每周

- 检查备份文件是否生成且可读取；
- 检查系统盘、Docker 镜像和日志占用；
- 检查失败或长期运行的 Celery 任务；
- 检查数据库和 RAG 资产数量是否异常下降；
- 检查 `.env`、SSH key 和安全组是否有未授权变更；
- 使用真实浏览器完成一次最小主流程。

### 13.3 磁盘清理

先查看空间：

```bash
docker system df
du -sh /opt/ai-bidding/backups
```

只清理无引用构建缓存：

```bash
docker builder prune -f
```

不要在未确认时执行：

```bash
docker system prune -a
docker volume prune
```

## 14. 常见故障

### 14.1 `git pull` 提示本地修改会被覆盖

**原因：** 服务器源码被手工改动。

**处理：** 按第 8 节导出 patch、定向 stash、pull、比较后再决定是否删除 stash。

**禁止：** 直接 `git reset --hard`。

### 14.2 前端重建后仍显示旧页面

按以下顺序检查：

```bash
git log -1 --oneline
git status --short
curl -fsS http://127.0.0.1:8080/build-info.json
docker compose exec frontend sh -lc 'ls -lh /usr/share/nginx/html/assets | head'
```

先确认服务器源码和 commit，再确认容器静态包，最后检查浏览器缓存。重建旧源码不会产生新页面。

### 14.3 `/api/health` 正常但业务不可用

检查就绪接口：

```bash
curl -i http://127.0.0.1:8080/api/ready
```

根据返回的 `checks` 排查 PostgreSQL、Redis、存储、模型 Key 或 pgvector RPC。

### 14.4 容器 unhealthy

```bash
docker compose ps
docker inspect --format '{{json .State.Health}}' ai-bidding-backend
docker compose logs --tail=200 backend
```

不要先盲目重启。先保存错误日志和时间点，再根据具体依赖处理。

### 14.5 Celery 任务长期排队

```bash
docker compose ps celery-worker redis
docker compose logs --tail=200 celery-worker
docker compose exec celery-worker \
  celery -A backend.tasks.celery_app:celery_app inspect ping
```

确认 Redis、worker、模型 API 和数据库连接均正常。后端代码变更后必须同时重建 `backend` 和 `celery-worker`。

### 14.6 Docker Hub 拉取超时

先重试单个基础镜像：

```bash
docker pull nginx:1.27-alpine
docker pull node:22-alpine
docker pull python:3.12-slim
```

如果持续超时，按实施清单中的 Docker registry mirror 配置处理。不要把网络错误误判为代码构建错误。

### 14.7 DOCX 页码或目录未刷新

```bash
docker compose exec backend soffice --version
docker compose exec backend printenv SOFFICE_BIN
docker compose logs --tail=200 backend | grep -i soffice
```

容器内路径应为：

```text
/usr/bin/soffice
```

同时检查导出任务 metadata 中的 `field_refresh` 状态。

### 14.8 产品库或资信库为空

企业知识库文本和产品/资信资产是两条数据链：

- 企业知识库读取 `knowledge_documents`、`document_chunks`；
- 产品库和资信库读取 `knowledge_assets` 以及本地文件 volume。

检查数量：

```bash
docker compose exec -T postgres psql -U bidding -d bidding -c "
select 'documents' as item, count(*) from public.knowledge_documents
union all
select 'chunks', count(*) from public.document_chunks
union all
select 'assets', count(*) from public.knowledge_assets;"
```

不要因为产品库为空就重复导入文本语料。应先确认 `knowledge_assets` 和资产文件是否存在。

## 15. 发布验收清单

| 状态 | 检查项 | 验收标准 |
| --- | --- | --- |
| [ ] | 本地源码已提交 | 无遗漏的功能源码 |
| [ ] | 目标 commit 已推送 Gitee | 开发和服务器 commit 一致 |
| [ ] | 服务器本地改动已处理 | 已备份 patch 或确认工作区 clean |
| [ ] | 数据库已按风险备份 | 备份文件存在且可读取 |
| [ ] | 仅重建受影响服务 | 前端、后端或联合构建选择正确 |
| [ ] | Compose 服务正常 | 核心服务 running/healthy |
| [ ] | `/api/health` 通过 | 后端直连和前端反代均为 200 |
| [ ] | `/api/ready` 通过 | PostgreSQL、Redis、存储、模型配置正常 |
| [ ] | 浏览器冒烟通过 | 登录和本次功能可用 |
| [ ] | 数据未异常减少 | 项目、知识库和资产数量正常 |
| [ ] | 发布记录已填写 | 包含 commit、操作、结果和回滚点 |

## 16. 发布记录模板

```markdown
## 发布记录：YYYY-MM-DD HH:mm

- 发布人员：
- 环境：阿里云单 ECS 测试环境
- 分支：feat/aliyun-test-readiness
- 发布前 commit：
- 发布后 commit：
- 改动范围：frontend / backend / celery / database / rag
- 数据库备份：
- 构建命令：
- 重建服务：
- `/api/health`：
- `/api/ready`：
- 浏览器验收：
- 业务冒烟：
- 异常与处理：
- 回滚分支或 commit：
- 最终结论：通过 / 部分通过 / 回滚
```

建议将每次重要发布记录追加到：

```text
docs/development/runs/
```

## 17. 接手人员首日操作

新接手人员按以下顺序熟悉环境：

1. 阅读本文和上游实施清单；
2. 登录服务器，但不修改任何文件；
3. 执行 `git status --short`、`git log -1 --oneline` 和 `docker compose ps`；
4. 调用 `/api/health`、`/api/ready` 和 `/build-info.json`；
5. 查看 backend、celery-worker、frontend 最近 100 行日志；
6. 确认数据库和六个 Docker volumes 的用途；
7. 使用浏览器登录并完成产品库、资信库和企业知识库检查；
8. 在非演示时段完成一次只重建前端的练习发布；
9. 使用本模板记录练习结果；
10. 在负责人陪同下完成一次数据库备份和恢复演练。

完成上述步骤后，接手人员应能够独立完成常规发布、版本核对、健康检查、日志排查和应用代码回滚。

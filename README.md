# 电力 AI 标书系统
**AI Bidding Workbench for Power Grid Projects**

把招标文件、企业知识库和标书编写放进同一个工作台：解析要求、规划分册、辅助写作、检查响应覆盖，最后导出可编辑的 Word 标书。

适合电力工程、设备供货和运维服务企业的投标资料编制，也可作为企业文档智能应用的工程参考。当前默认采用 **PostgreSQL + pgvector + 本地文件存储**；Supabase 相关配置属于兼容与迁移路径。

[快速开始](#快速开始) · [功能与架构](#功能与架构) · [部署文档](docs/deployment/quickstart.md) · [文档索引](docs/README.md)

## 能做什么

| 环节 | 具体能力 |
| --- | --- |
| 文件解读 | 上传招标文件，提取要求、评分项与风险；可选 MinerU OCR |
| 企业知识库 | 检索资信、产品和历史资料，使用向量召回、Rerank 与关键词兜底 |
| 编写工作台 | 按技术、商务、资格等分册规划大纲，流式生成和编辑章节 |
| 合规辅助 | 规则检查与 LLM 语义复核，定位响应缺失并给出补强建议 |
| 交付与追踪 | DOCX 导出、任务记录、模型调用用量与成本记录 |

AI 输出需要结合原始招标文件和企业材料复核；检查结果用于辅助编制，不保证中标，也不替代投标人的最终审核。

## 快速开始

以下为 **macOS / Linux 本地开发路径**。准备 Python 3.11 / 3.12、Node.js 22 和 Docker Compose。Windows 操作及完整配置见[部署指南](docs/deployment/quickstart.md)。

### 1. 获取代码和配置

~~~bash
git clone https://github.com/sunShineLoveMe/ai_bidding_power_grid.git
cd ai_bidding_power_grid

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
~~~

编辑项目根目录的 .env，至少确认：

| 变量 | 本地用途 |
| --- | --- |
| AI_PROVIDER | 默认 deepseek，选择写作模型提供方 |
| DEEPSEEK_API_KEY | 章节写作、文件解读等模型调用 |
| DASHSCOPE_API_KEY | 默认知识库 Embedding / Rerank；使用 DeepSeek 时仍需配置 |
| DB_PROVIDER / DATABASE_URL | 默认 postgres，连接本地 15432 端口 |
| STORAGE_PROVIDER | 本地运行保持 local |
| APP_SESSION_SECRET | 替换示例值，设置至少 24 字符的随机会话密钥 |

各阶段模型名称以 [.env.example](.env.example) 为准，不需要把密钥写进前端代码。系统设置页用于调整模型与企业画像等非敏感配置。

### 2. 初始化本地数据库

~~~bash
docker compose up -d postgres
docker compose ps postgres
~~~

等待 PostgreSQL 显示 healthy，再初始化表结构与基础定价：

~~~bash
bash scripts/init_postgres_schema.sh
~~~

默认数据库连接：

~~~dotenv
DB_PROVIDER=postgres
DATABASE_URL=postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding
STORAGE_PROVIDER=local
~~~

这里的数据库口令仅对应 Compose 中的本地开发默认值。自定义账号或端口时，同步调整 .env。更多说明见[本地 PostgreSQL](docs/deployment/local-postgres-docker.md)。

### 3. 构建页面并启动

~~~bash
cd frontend
npm ci
npm run build
cd ..

python main.py
~~~

打开 **http://127.0.0.1:3012**，从注册页创建本地账号后登录。后端同时托管 frontend/dist 中的页面。

另开终端检查：

~~~bash
curl -fsS http://127.0.0.1:3012/api/health
~~~

返回 status 为 ok 只说明 Web 服务启动成功；模型调用、数据库与文件导出仍需按下面的业务流程验证。

前端热更新开发时，在保持后端运行的同时，另开终端执行：

~~~bash
cd frontend
npm run dev
~~~

开发页面位于 **http://localhost:5173**，Vite 将 /api 请求代理到 3012 端口。

## 第一次体验

1. 在「系统设置」填写企业画像，导入脱敏资信或产品材料。
2. 上传一份招标文件，检查解析出的要求、评分项与风险。
3. 生成分册大纲，选择一个章节生成正文并在 Tiptap 编辑器中修改。
4. 查看响应覆盖情况和 AI 用量记录，再导出 DOCX。

扫描件识别可配置 MinerU；默认 Tiptap 编辑和 Word 下载不要求部署 ONLYOFFICE。LibreOffice 用于刷新导出文件中的目录和页码，缺失时需要在 Word 中手动更新。具体安装和选项见[部署指南](docs/deployment/quickstart.md)。

## 功能与架构

~~~mermaid
flowchart LR
    A["招标文件 / 企业资料"] --> B["Flask API / 解析与任务"]
    B <--> C["PostgreSQL + pgvector"]
    B <--> D["LLM / Embedding / Rerank"]
    B --> E["React 编写工作台"]
    E --> F["合规辅助 / DOCX 导出"]
~~~

- **前端**：React 18、TypeScript、Vite、Ant Design、Tiptap。
- **后端**：Flask、Python、模型接口适配、文档解析与导出模块。
- **数据**：PostgreSQL、pgvector、本地文件存储；可选 OSS。

| 路径 | 内容 |
| --- | --- |
| frontend/ | 编写、知识库、资信、产品与用量页面 |
| backend/ai/ | 大纲、章节写作、解读与合规逻辑 |
| backend/rag/ | 入库、检索和向量存储 |
| backend/export/ | Markdown 到 DOCX 的转换 |
| migrations/postgres/ | PostgreSQL 表结构与迁移 |
| tests/ | 后端回归测试 |

## 开发验证与常见问题

~~~bash
# 项目根目录，已激活 Python 环境
python -m unittest discover -s tests

# 前端构建与 TypeScript 检查
cd frontend
npm run build
~~~

| 现象 | 先检查 |
| --- | --- |
| 首页提示缺少 Vite 产物 | 是否执行 frontend 下的 npm run build |
| 注册或项目列表报表不存在 | 是否执行数据库初始化脚本，DATABASE_URL 是否指向同一实例 |
| 写作可用、知识库失败 | 是否同时配置 DASHSCOPE_API_KEY |
| 容器部署端口和本地不同 | 完整 Compose 的前端是 8080；本节本地方案是 3012 / 5173 |
| 导出页码未刷新 | LibreOffice / SOFFICE_BIN 配置及 Word 域更新 |

## 延伸阅读与许可

[部署与配置](docs/deployment/quickstart.md) · [安全与访问控制](docs/deployment/security.md) · [架构](docs/architecture/overview.md) · [API](docs/development/api-reference.md) · [功能文档](docs/README.md)

代码按 [MIT License](LICENSE) 分发。示例资料的来源和使用说明见对应目录；实际业务请使用有权处理的企业材料。

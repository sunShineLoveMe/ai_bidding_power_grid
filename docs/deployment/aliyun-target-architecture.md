# 阿里云目标架构

本文说明电力/电网项目面向国内企业交付时的目标部署形态。当前本地开发使用 Docker PostgreSQL，生产环境目标为阿里云 RDS PostgreSQL + OSS。

## 推荐架构

```mermaid
flowchart LR
    U[企业内网用户] --> FE[前端静态资源 / Nginx]
    FE --> API[后端 Flask 服务]
    API --> RDS[(阿里云 RDS PostgreSQL)]
    RDS --> Vec[pgvector]
    API --> OSS[阿里云 OSS 私有 Bucket]
    API --> OCR[MinerU / OCR 服务]
    API --> LLM[DeepSeek / DashScope]
    API --> Office[ONLYOFFICE Docs 可选]
```

## 资源职责

| 资源 | 用途 | 本地对应 |
| --- | --- | --- |
| ECS 或容器服务 | 运行后端、前端、任务进程、可选 OnlyOffice | 本机 Python/Node/Docker |
| RDS PostgreSQL | 业务数据、解析结果、任务状态、AI 用量、pgvector 向量检索 | Docker PostgreSQL |
| OSS | 招标文件、知识库文件、资质/产品资料、导出文件 | `storage/` 本地目录 |
| 日志服务，可选 | 运行日志、审计日志、错误追踪 | `logs/` |
| VPC / 安全组 | 内网访问、端口隔离 | 本机回环地址 |

## 环境变量映射

| 本地开发 | 阿里云生产 |
| --- | --- |
| `DATABASE_URL=postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding` | `DATABASE_URL=postgresql://<user>:<password>@<rds-private-host>:5432/<db>` |
| `STORAGE_PROVIDER=local` | `STORAGE_PROVIDER=oss` |
| `LOCAL_STORAGE_ROOT=storage` | OSS Bucket、Endpoint、AccessKey 相关配置 |
| `APP_ENV=development` | `APP_ENV=production` |
| `APP_LOCAL_ONLY=false` | 内网部署可按客户网络策略设置 |

## 交付原则

- 生产数据库优先使用 RDS PostgreSQL，不在 ECS 上长期自建数据库。
- 文件类资产优先使用 OSS 私有 Bucket，不放入代码仓库和数据库大字段。
- 后端服务通过内网地址访问 RDS 和 OSS，公网只开放必要入口。
- `.env` 由实施人员在目标环境维护，不提交到 Git。
- 数据库迁移脚本必须可重复执行或具备明确执行顺序。
- 备份、恢复、监控、日志和密钥轮换纳入正式交付清单。

## 当前迁移状态

本仓库已具备本地 Docker PostgreSQL 基础设施配置。业务代码仍处于从 Supabase SDK 向标准 PostgreSQL + 本地/OSS 存储抽象迁移的过程中。迁移完成前，涉及数据库访问的改动应优先收敛到 `backend/db/`，避免在 API 或业务模块中继续散落供应商专属调用。


# 本地 Docker PostgreSQL

本项目的国内企业交付路线使用：

- 本地开发：Docker PostgreSQL + pgvector + 本地文件存储
- 阿里云生产：RDS PostgreSQL + OSS

这也是新成员进入项目时默认使用的数据库方案。Supabase 只作为历史环境和迁移参考。

## 启动数据库

```bash
docker compose up -d postgres
```

默认连接信息：

```env
DATABASE_URL=postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding
```

检查状态：

```bash
docker compose ps postgres
docker compose logs postgres
```

进入数据库：

```bash
docker compose exec postgres psql -U bidding -d bidding
```

确认扩展：

```sql
select extname from pg_extension where extname in ('pgcrypto', 'vector');
```

## 数据持久化

数据库数据保存在 Docker named volume `ai_bidding_power_grid_postgres_data` 中，停止容器不会丢数据：

```bash
docker compose stop postgres
docker compose start postgres
```

如果需要重建空库，先确认没有重要数据，再删除 volume：

```bash
docker compose down -v
docker compose up -d postgres
```

不要在 Docker Desktop 中执行 Reset to factory defaults、Clean / Purge data 之类操作，否则镜像、容器和 volume 可能被清除。

## 团队默认配置

Docker Desktop 推荐资源：

```text
CPU limit: 6
Memory limit: 16 GB
Swap: 4 GB
Disk usage limit: 200 GB
```

多人并行项目较多时可以降到 4 CPU / 12 GB；大量导入知识库、图片、历史标书或批量向量化时可临时升到 8 CPU / 24 GB。

## 说明

当前 `sql/` 目录里部分脚本仍包含 Supabase Storage 专属对象，例如 `storage.buckets` 和 storage policy，不能原样作为原生 PostgreSQL 初始化脚本执行。

新环境初始化必须使用 `migrations/postgres/` 正式迁移链；`sql/` 和 `docs/deployment/supabase-*.md` 仅作为历史/迁移参考。电网 RAG 新资料入库必须走 v2 父子分块链路和评测流程，不再使用早期 `rag_seed/.../_scripts/ingest_power_grid_rag_seed.py` 作为正式入口。

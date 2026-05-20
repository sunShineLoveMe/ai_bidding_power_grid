# Supabase 到 PostgreSQL 迁移

本文记录当前电力/电网项目从 Supabase 迁移到本地 Docker PostgreSQL，并为后续阿里云 RDS PostgreSQL + OSS 交付做准备的标准流程。

## 迁移目标

- 数据库：Supabase PostgreSQL -> 本地 Docker PostgreSQL -> 阿里云 RDS PostgreSQL
- 文件：Supabase Storage -> `storage/` 本地目录 -> 阿里云 OSS
- 向量：保留 pgvector `vector(1024)` 字段和向量检索函数
- 代码：后续逐步从 Supabase SDK 切换到 PostgreSQL + Storage 抽象

## 当前源端盘点

源端已确认可访问，核心对象包括：

- 项目/文件/解析/章节表：`bid_projects`、`bid_files`、`bid_analysis`、`bid_requirements`、`bid_scoring_items`、`bid_risks`、`bid_chapter_suggestions`、`bid_sections`
- 知识库表：`knowledge_documents`、`document_chunks`、`knowledge_assets`
- 运行表：`app_users`、`onlyoffice_documents`、`ai_model_prices`、`ai_usage_logs`、`bid_generation_tasks`、`bid_export_tasks`
- Storage：`tender-files`、`knowledge-files`、`generated-docx`、`qualification-files`、`product-files`
- 历史 Storage：`knowledge-assets`、`knowledge`。这两个 bucket 名来自早期资料入库脚本，迁移脚本会兼容下载。

## 执行迁移

先确认本地数据库容器健康：

```bash
docker compose ps postgres
```

执行完整迁移：

```bash
venv/bin/python scripts/migrate_supabase_to_postgres.py
```

仅迁移表，不下载 Storage：

```bash
venv/bin/python scripts/migrate_supabase_to_postgres.py --skip-storage
```

仅下载 Storage，不重导表：

```bash
venv/bin/python scripts/migrate_supabase_to_postgres.py --skip-tables
```

迁移报告输出到：

```text
migration_reports/supabase_to_postgres_latest.json
```

## 校验迁移

执行：

```bash
venv/bin/python scripts/verify_postgres_migration.py
```

校验内容：

- 本地 PostgreSQL 核心表行数
- `document_chunks` 和 `knowledge_assets` 向量数量
- `bid_files`、`knowledge_documents`、`knowledge_assets` 和缩略图引用的本地文件是否存在

校验报告输出到：

```text
migration_reports/postgres_migration_verify_latest.json
```

## 本地目录映射

```text
storage/
  tender-files/
  generated-docx/
  knowledge-files/
  qualification-files/
  product-files/
```

数据库仍保留 `bucket/object_path` 或 `storage_bucket/storage_path` 字段，方便后续无缝映射到 OSS Bucket。

## 注意事项

- `sql/` 下历史脚本中包含 Supabase Storage policy、`storage.buckets` 等专属对象，不能直接作为原生 PostgreSQL 初始化脚本。
- 当前 PostgreSQL schema 位于 `migrations/postgres/001_schema.sql`。
- 完整流程跑通前，不删除 `backend/db/supabase_*`，先保留作为源端迁移和回退参考。
- 迁移完成后必须执行数据校验和主流程验收，再进行后端访问层替换。

## 本次迁移记录

截至 2026-05-20，已完成真实 Supabase 源端到本地 PostgreSQL / 本地 Storage 的迁移。

表数据导入结果：

| 表 | 行数 |
| --- | ---: |
| `bid_projects` | 26 |
| `bid_files` | 26 |
| `bid_analysis` | 21 |
| `bid_requirements` | 1600 |
| `bid_scoring_items` | 1152 |
| `bid_risks` | 1260 |
| `bid_chapter_suggestions` | 630 |
| `bid_sections` | 789 |
| `knowledge_documents` | 39 |
| `document_chunks` | 1255 |
| `knowledge_assets` | 99 |
| `app_users` | 3 |
| `onlyoffice_documents` | 0 |
| `ai_model_prices` | 7 |
| `ai_usage_logs` | 561 |
| `bid_generation_tasks` | 19 |
| `bid_export_tasks` | 14 |

向量数据：

| 对象 | 数量 |
| --- | ---: |
| `document_chunks.embedding` | 570 |
| `knowledge_assets.embedding` | 99 |

Storage 迁移：

| 项 | 数量 |
| --- | ---: |
| 本地文件数 | 212 |
| 本地 Storage 体积 | 约 221 MB |
| 数据库引用文件 | 208 |
| 已匹配本地文件 | 207 |
| 缺失引用 | 1 |

唯一缺失引用是历史 `knowledge` bucket 下的临时 PDF：

```text
knowledge/temp/9bcc6415-15eb-4e2c-a48f-3b843a59487d-19__b7a2c0d3.pdf
```

已确认 Supabase 源端 `knowledge` bucket 不存在，标准 `knowledge-files` bucket 中也没有该对象，因此这是历史脏引用，不是本次下载失败。

## 代码切换状态

已新增 `backend/db/postgres_compat.py`。当 `.env` 中配置：

```env
DB_PROVIDER=postgres
DATABASE_URL=postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding
STORAGE_PROVIDER=local
LOCAL_STORAGE_ROOT=storage
```

现有 `get_supabase_client().table(...).select/insert/update/upsert/delete/rpc` 会走本地 PostgreSQL 兼容层；Storage 上传/下载会走本地 `storage/`。

已验证：

- 后端健康检查正常。
- 历史记录接口可从 PostgreSQL 返回迁移项目。
- 用量统计接口可从 PostgreSQL 返回迁移日志。
- 知识资产列表接口可从 PostgreSQL 返回迁移资产。
- 知识资产文件接口可从本地 `storage/` 返回图片文件。
- pgvector `match_knowledge_assets` / `match_knowledge_chunks` 函数可返回结果。
- 后端测试 `venv/bin/python -m unittest discover -s tests` 通过。

下一步应执行一次新的端到端业务验收：上传电力招标文件、解析、生成大纲、生成章节、合规检查、DOCX 导出，并确认全过程不再依赖 Supabase。

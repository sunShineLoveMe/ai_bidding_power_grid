# Supabase 初始化与补充表

> 快速开始见 [quickstart.md](./quickstart.md)

所有 SQL 脚本都在项目根目录 `sql/` 下。复制文件内容粘贴到 Supabase 控制台 → SQL Editor 执行即可。

---

## 必须执行（否则功能异常）

按**从上到下**的顺序执行，每个脚本互相独立但后者可能依赖前者创建的表。

| # | SQL 文件 | 不执行的后果 |
| :-: | --- | --- |
| 1 | `sql/20260426_create_bid_sections.sql` | 无法保存章节大纲和章节正文，标书编制工作台全部报错 |
| 2 | `sql/20260428_create_knowledge_assets.sql` | 企业资信库/产品库资产上传报错；RAG 无图片召回 |
| 3 | `sql/20260429_app_users_and_onlyoffice_documents.sql` | 首页刷新报 `Could not find the table 'public.app_users'` 错误；OnlyOffice 编辑保存回调找不到文件 |
| 4 | `sql/20260507_create_ai_usage_tracking.sql` | 一级菜单「用量与成本」无法展示 Token 统计；每次 AI 调用写日志失败 |
| 5 | `sql/20260508_create_bid_generation_tasks.sql` | "一键编写全文"刷新后无法恢复批量章节生成进度 |
| 6 | `sql/20260508_create_bid_export_tasks.sql` | DOCX 导出没有任务化，长文档导出可能 HTTP 超时 |
| 7 | `sql/20260508_supabase_idempotency_indexes.sql` | 知识库文档/资产可能产生重复记录；**执行前若有重复数据需先清理** |
| 8 | `sql/20260508_add_asset_applicable_volumes.sql` | RAG 无法按分册（技术标/商务标/资格/报价/附件）硬过滤资产 |
| 9 | `sql/20260510_seed_deepseek_v4_flash_pricing.sql` | DeepSeek V4 Flash 用量能记录 Token，但无法按人民币价格估算成本 |

---

## 可选执行

| SQL 文件 | 何时需要 |
| --- | --- |
| `sql/20260507_update_ai_usage_pricing_cny.sql` | 仅当历史环境已写入过 USD 口径价格或日志时执行，把历史数据折算为人民币 |

---

## 执行后必须刷新 Schema 缓存

Supabase 有一层 PostgREST schema 缓存，新建的表/列不会立刻对前后端可见。执行完 SQL 后二选一：

- **推荐**：Supabase 控制台 → Settings → API → 点击 **Reload schema**
- 或在 SQL Editor 执行：`NOTIFY pgrst, 'reload schema';`

---

## 验证是否全部执行成功

在 Supabase SQL Editor 执行下面这段，应该返回 **17 行**（每张表一行）：

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'bid_projects', 'bid_files', 'bid_analysis',
    'bid_requirements', 'bid_scoring_items', 'bid_risks',
    'bid_chapter_suggestions', 'bid_sections',
    'knowledge_documents', 'document_chunks', 'knowledge_assets',
    'app_users', 'onlyoffice_documents',
    'ai_model_prices', 'ai_usage_logs',
    'bid_generation_tasks', 'bid_export_tasks'
  )
order by table_name;
```

少了哪张表就回头执行对应编号的 SQL。

---

## 各脚本职责说明

### `20260429_app_users_and_onlyoffice_documents.sql`

创建两张表：

| 表 | 用途 |
| --- | --- |
| `app_users` | 浏览器匿名指纹与单机版操作人员 ID，替代早期 SQLite `users` 表 |
| `onlyoffice_documents` | OnlyOffice 文档 key、项目 ID、本地文件路径、回调下载地址 |

如果这张表缺失，后端日志会反复打印：
```
APIError: Could not find the table 'public.app_users' in the schema cache
```
系统会自动回退到本地 SQLite，但每次刷新都会产生一次失败往返，增加延迟。

### `20260507_create_ai_usage_tracking.sql`

创建 Token 用量与成本统计的全套对象：

| 对象 | 用途 |
| --- | --- |
| `ai_model_prices` | 模型输入/输出/Embedding/Rerank/OCR 单价 |
| `ai_usage_logs` | 每次 AI/OCR 调用的明细：项目、阶段、模型、Token、费用、原始 usage |
| `ai_usage_project_summary` | 按项目汇总调用次数、Token、费用 |
| `ai_usage_project_stage_summary` | 按项目 + 业务阶段汇总 |
| `ai_usage_daily_summary` | 按日期汇总全局用量 |
| `get_ai_usage_project_cost(project_id)` | 项目级成本查询 RPC |

未执行时一级菜单「用量与成本」是空的，主链路功能不受影响。

### `20260508_create_bid_generation_tasks.sql`

记录"一键编写全文"的后端任务态，支持刷新后恢复批量章节生成进度。

### `20260508_create_bid_export_tasks.sql`

记录 DOCX 导出任务，支持长文档后台导出和前端轮询状态。

### `20260508_supabase_idempotency_indexes.sql`

给 `knowledge_documents`、`document_chunks`、`knowledge_assets` 补充防重复索引。其中资信/产品资产按 `storage_bucket/storage_path` 防重。

**执行前如果历史库已有重复记录**，需先备份并清理重复数据，否则 SQL 会报唯一约束冲突。清理示例（仅保留每组最早创建的一条）：

```sql
delete from knowledge_assets a
using knowledge_assets b
where a.id > b.id
  and a.storage_bucket = b.storage_bucket
  and a.storage_path = b.storage_path;
```

### `20260508_add_asset_applicable_volumes.sql`

给企业资信库和产品库新增 `applicable_volumes` 字段，并升级 `match_knowledge_assets` RPC 函数，支持 RAG 和 DOCX 自动插图按技术标 / 商务标 / 资格 / 报价 / 附件做硬过滤。

---

## Storage Buckets

除了上述 SQL，还需要在 Supabase Storage 里创建以下 bucket（权限统一设为 **private**）：

| Bucket | 用途 |
| --- | --- |
| `tender-files` | 原始招标文件、补遗、答疑 |
| `generated-docx` | 生成的 Word / Markdown / 导出归档 |
| `knowledge-files` | 企业知识库资料、行业资料、历史标书 |
| `qualification-files` | 资质、证书、人员、财务等资料 |
| `product-files` | 产品手册、参数、图纸、案例材料 |

Bucket 名称必须与 `.env` 中的 `SUPABASE_STORAGE_*_BUCKET` 配置一致。

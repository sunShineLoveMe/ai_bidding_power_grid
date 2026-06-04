# 章节正文生成卡死问题 — 根因分析报告

> 编写日期：2026-06-04  
> 问题级别：🔴 P0 阻塞（用户核心链路不可用）  
> 涉及组件：Celery Worker、PostgreSQL、章节生成批任务、数据库迁移体系  
> 关联任务清单：阿里云测试环境准备任务清单 P1-1（Celery 章节生成）、P1-3（Alembic 迁移管理）

---

## 1. 问题现象

用户在完成招标文件上传与章节目录规划后，点击"生成正文"按钮，前端进入无限等待状态：

- 前端以 ~330ms 间隔不断轮询 `GET /api/bidding/interpretations/{project_id}/section-generation-tasks/{task_id}`
- 后端每次都返回 HTTP 200，任务记录存在且可读
- 但任务状态（`status`）永远停留在 `"queued"`，从不进入 `"running"` 或任何终态
- 约 270 秒后（900 次轮询上限），前端抛出错误：`"章节正文后台任务仍在处理中，请稍后刷新任务状态。"`
- Celery Worker、Redis、PostgreSQL 容器均正常启动且健康检查通过

**后端日志（截取）**：

```json
{"timestamp": "2026-06-04T08:44:11.724380+00:00", "level": "INFO", "module": "http", "stage": "request", "request_id": "req_20260604084411_35a8c4be7c", "message": "http_request_completed", "method": "GET", "path": "/api/bidding/interpretations/55a92409-5e14-4717-ae11-4537326cebfe/section-generation-tasks/3d7e3333-7414-4e36-aa3e-283c7d9dc18f", "status_code": 200, "duration_ms": 31}
{"timestamp": "2026-06-04T08:44:11.724380+00:00", "level": "INFO", "module": "http", "stage": "request", "request_id": "req_20260604084412_cf6d4c7c81", "message": "http_request_completed", "method": "GET", "path": "/api/bidding/interpretations/55a92409-5e14-4717-ae11-4537326cebfe/section-generation-tasks/3d7e3333-7414-4e36-aa3e-283c7d9dc18f", "status_code": 200, "duration_ms": 25}
-- ... 无限重复，status_code 始终 200，duration_ms 始终 ~25-40ms ...
```

注意：后端日志仅包含 HTTP 请求日志，Celery Worker 的错误日志需在 Worker 进程中查看。

---

## 2. 用户操作链路追踪

```
用户点击"生成正文"
  │
  ├─ [前端] generateCurrentSection()
  │   └─ POST /api/bidding/interpretations/{project_id}/section-generation-tasks
  │       → 创建 bid_generation_tasks 记录，status="queued"
  │       → 返回 task_id = "3d7e3333-..."
  │
  ├─ [前端] pollSectionGenerationTask(projectId, taskId)
  │   └─ 每 300ms GET /section-generation-tasks/{task_id}
  │       → 检查 task.status 是否为终态
  │       → 900 次后超时抛错
  │
  ├─ [后端] dispatch_section_generation_task()
  │   └─ run_bid_section_generation.delay(project_id, task_id)
  │       → 投递 Celery 任务到 Redis broker ✅
  │
  └─ [Celery Worker] bid.sections.generate_task
      └─ _dispatch_next_sections()
          └─ lease_bid_generation_task_items()
              └─ client.rpc("lease_bid_generation_task_items", ...)
                  → 💥 RPC 函数不存在
```

---

## 3. 根因分析

### 3.1 直接原因：PostgreSQL 中缺少 5 个关键 RPC 函数和 2 张表

`run_bid_section_generation` Celery 任务在执行时依次调用以下 PostgreSQL RPC 函数，但这些函数**均未在数据库中被创建**：

| 缺失对象 | 对象类型 | 定义文件 | 调用位置 | 失败后果 |
|---------|---------|---------|---------|---------|
| `bid_generation_task_items` | 表 | `sql/20260603_create_bid_generation_task_items.sql` | `_sync_generation_task_items_snapshot()` | 静默失败（有 try/except），但后续 lease 依赖此表 |
| `bid_generation_task_events` | 表 | 同上 | `_record_generation_task_event()` | 静默失败，事件审计链断裂 |
| `lease_bid_generation_task_items` | RPC 函数 | `sql/20260603_add_bid_generation_task_item_lease.sql` | `lease_bid_generation_task_items()` | **硬失败** — Celery 任务直接抛异常 |
| `heartbeat_bid_generation_task_item` | RPC 函数 | 同上 | `heartbeat_bid_generation_task_item()` | 即使 lease 跳过也会在生成过程中失败 |
| `expire_bid_generation_task_items` | RPC 函数 | 同上 | `expire_bid_generation_task_items()` | lease 超时回收失败 |
| `set_bid_generation_task_items_updated_at` | RPC 函数 | `sql/20260603_create_bid_generation_task_items.sql` | 表触发器 | `updated_at` 不自动更新 |
| `update_bid_generation_task_item_atomic` | RPC 函数 | `migrations/postgres/007_atomic_section_task_item.sql` | `update_bid_generation_task_item()` (PG 模式) | 并发更新可能丢数据 |

**预期 Celery Worker 错误日志**：

```
function public.lease_bid_generation_task_items(uuid, uuid, integer, text, integer) does not exist
HINT: No function matches the given name and argument types.
```

### 3.2 根本原因：数据库迁移体系存在结构性缺陷

#### 3.2.1 初始化脚本版本滞后

[`scripts/init_postgres_schema.sh`](scripts/init_postgres_schema.sh) **仅执行 001-005 号迁移**：

```bash
run_sql_file "migrations/postgres/001_schema.sql"   # 核心 schema
run_sql_file "migrations/postgres/002_app_login.sql" # 登录表
run_sql_file "migrations/postgres/003_seed_deepseek_v4_flash_pricing.sql"  # 价格种子
run_sql_file "migrations/postgres/004_seed_deepseek_v4_pro_pricing.sql"    # 价格种子
run_sql_file "migrations/postgres/005_bid_parse_tasks.sql"                 # 解析任务表
```

**遗漏的迁移文件**：

| 迁移编号 | 文件 | 重要性 |
|---------|------|--------|
| 006 | `migrations/postgres/006_rag_p0_filtered_recall.sql` | RAG 召回过滤（次要） |
| 007 | `migrations/postgres/007_atomic_section_task_item.sql` | 章节任务并发安全更新 RPC（**P0 阻塞**） |
| 007 | `migrations/postgres/007_power_grid_goods_list_rows.sql` | 电网货物清单（次要） |

#### 3.2.2 关键 DDL 散落在被标注为"历史/废弃"的 `sql/` 目录中

最关键的 3 个 SQL 文件（表创建 + lease/heartbeat/expire RPC）**不在 `migrations/postgres/` 中，而在 `sql/` 目录**：

- `sql/20260603_create_bid_generation_task_items.sql` — 创建 `bid_generation_task_items` 表和 `bid_generation_task_events` 表
- `sql/20260603_add_bid_generation_task_item_lease.sql` — 创建 `lease_bid_generation_task_items`、`heartbeat_bid_generation_task_item`、`expire_bid_generation_task_items` 三个 RPC 函数

而 `sql/` 目录在 [阿里云测试环境准备任务清单](阿里云测试环境准备任务清单.md) P0-6 中被明确标注为：

> "标注 `sql/` 为历史/补丁参考，不整目录执行"
>
> "避免 Supabase 时代脚本污染 PostgreSQL 初始化"

这个决策在 P0-6 执行时是正确的（避免误跑 Supabase 专属脚本），但**副作用是 6 月 3 日新增的关键 DDL 也被一起"隔离"了**，从未被纳入正式的迁移和初始化流程。

#### 3.2.3 Celery 任务缺少失败保护

[`backend/tasks/section_tasks.py`](backend/tasks/section_tasks.py) L541：

```python
@celery_app.task(name="bid.sections.generate_task", bind=True, max_retries=0)
def run_bid_section_generation(self, project_id: str, task_id: str) -> dict:
    from backend.db.supabase_repo import get_bid_generation_task
    with log_context(project_id=project_id, task_id=task_id):
        task = get_bid_generation_task(project_id, task_id)
        if not task:
            raise RuntimeError("章节生成任务不存在")
        # ...
        return _dispatch_next_sections(project_id, task_id)
        # ↑ 无 try/except 包裹！如果 _dispatch_next_sections 内部任何一步失败：
        #   1. Celery 任务标记为 FAILURE（仅 Redis result backend 可见）
        #   2. max_retries=0 → 永不重试
        #   3. bid_generation_tasks 表记录永远停留在 status="queued"
        #   4. 前端无限轮询，永远等不到终态
```

#### 3.2.4 部分错误被静默吞掉

`create_bid_generation_task()` 在创建任务后会调用 `_sync_generation_task_items_snapshot()`，该函数有 try/except 包裹：

```python
# supabase_repo.py L1342
except Exception:
    logging.exception("同步 bid_generation_task_items 失败，保留 JSON 快照作为兼容回退: %s", task_id)
```

这意味着**即使 `bid_generation_task_items` 表不存在，任务创建也不会报错**。用户看到的表象是"任务创建成功"，但后续的 lease 操作因依赖同一张表而必然失败。这是一个渐进式静默退化的路径。

---

## 4. 影响范围

| 影响项 | 程度 | 说明 |
|--------|------|------|
| **单章生成正文** | 🔴 完全不可用 | 用户点击"生成本章正文"后永久卡死 |
| **一键编写全文** | 🔴 完全不可用 | 同上，所有章节批量生成的入口 |
| **章节重试** | 🔴 完全不可用 | 依赖相同的 Celery + lease 链 |
| **章节续写恢复** | 🔴 完全不可用 | 同上 |
| **SSE 流式生成** | 🟢 不受影响 | `/sections/stream` 是独立路径，走的是 `stream_generate_bid_section_events()`，不经过 Celery/lease 体系。但这仅在旧版前端路径中存在；当前前端 `generateCurrentSection()` 已经改为走批任务 API。 |
| **DOCX 导出** | 🟢 不受影响 | Celery `bid.export.docx` 任务不依赖这些 RPC |
| **招标文件解析** | 🟢 不受影响 | Celery 解析管线不依赖这些 RPC |
| **知识库入库** | 🟢 不受影响 | 同上 |

---

## 5. 与项目已知技术债的对应关系

此问题恰好印证了 [阿里云测试环境准备任务清单](阿里云测试环境准备任务清单.md) 1.3.3 节中多项警告：

| 清单警告编号 | 原文 | 本次印证 |
|-------------|------|---------|
| 第 3 条 | "章节正文仍是 SSE 请求内实时生成" | 章节生成的 Celery 迁移代码已写（`section_tasks.py` 541 行），但配套 DDL 未部署到位，形成"代码就绪、数据库缺位"的半吊子状态 |
| 第 5 条 | "集成/E2E 测试仍不足" | 如果有一条最小 E2E（上传 → 解析 → 大纲 → 单章生成 → 导出），此问题在合入当天就会被发现 |
| P1-3 备注 | "Alembic 有壳无增量能力...后续改表仍需手写 SQL" | `sql/` 与 `migrations/postgres/` 双目录并存、初始化脚本手动维护文件列表，正是"无增量迁移管理"的直接后果 |

---

## 6. 修复方案（供评审，暂不执行）

### 6.1 立即止血：手动补执行缺失的 SQL

在运行中的 PostgreSQL 数据库上依次执行：

```bash
# 按依赖顺序执行
docker compose exec -T postgres psql -U bidding -d bidding < sql/20260603_create_bid_generation_task_items.sql
docker compose exec -T postgres psql -U bidding -d bidding < sql/20260603_add_bid_generation_task_item_lease.sql
docker compose exec -T postgres psql -U bidding -d bidding < sql/20260603_update_bid_generation_task_status_model.sql
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/007_atomic_section_task_item.sql
docker compose exec -T postgres psql -U bidding -d bidding < migrations/postgres/006_rag_p0_filtered_recall.sql
```

### 6.2 防御性加固：Celery 任务补失败回写

`run_bid_section_generation` 需要 try/except 包裹 `_dispatch_next_sections()`，在 Celery 任务失败时将 `bid_generation_tasks.status` 更新为 `"failed"`，确保前端轮询能看到终态。

### 6.3 体系性修复：迁移管理规范化

| 修复项 | 优先级 | 说明 |
|--------|--------|------|
| 将 `sql/` 中 6 月 3 日的 3 个文件迁入 `migrations/postgres/` 并编号 | P0 | 消除双目录并存 |
| 更新 `init_postgres_schema.sh` 纳入 006、007（及新增的 008-010） | P0 | 新环境初始化不再遗漏 |
| 为 `run_bid_section_generation` 补 try/except 失败回写 | P0 | 防御性加固，避免将来任何原因导致的永久挂起 |
| 补一条最小 E2E 冒烟测试 | P1 | 防止类似问题再次漏到手工测试阶段 |
| Alembic 纳入 006-010，支持增量 up/down | P1 | 替换手写 SQL 编号体系，实现真正的版本管理 |

### 6.4 验证步骤（修复后执行）

```bash
# 1. 验证 RPC 函数已创建
docker compose exec -T postgres psql -U bidding -d bidding -c \
  "SELECT proname FROM pg_proc WHERE proname LIKE '%lease_bid%' OR proname LIKE '%heartbeat_bid%' OR proname LIKE '%expire_bid%';"

# 2. 验证表已创建
docker compose exec -T postgres psql -U bidding -d bidding -c \
  "SELECT table_name FROM information_schema.tables WHERE table_name IN ('bid_generation_task_items', 'bid_generation_task_events');"

# 3. 重新尝试章节生成
# 在前端点击"生成正文"，观察任务状态是否从 queued → running → completed
```

---

## 7. 总结

**这是一个典型的"代码先行、数据库滞后"的迁移管理缺陷**，不是 Celery 或 Redis 的运行时问题，也不是 LLM 调用失败。

核心矛盾在于：章节生成的 Celery 迁移代码于 6 月 3 日提交，配套的数据库 DDL 也于同日在 `sql/` 目录中写好，但因为：

1. `sql/` 目录被标记为"历史/补丁参考，不整目录执行"
2. 初始化脚本版本未同步更新
3. Alembic 仅有一个 baseline revision，无法自动检测增量
4. 缺少 E2E 冒烟测试作为保护网

这些 DDL 从未被实际部署到任何数据库实例中，导致 Celery Worker 在执行章节生成任务时调用的 RPC 函数全部不存在，任务静默失败，前端永久轮询。

**修复难度**：低。核心是补执行 ~200 行 SQL（5 个文件），加 15 行 Python 的 try/except 防御。体系性修复（迁移规范化 + E2E）约 3-5 人天。

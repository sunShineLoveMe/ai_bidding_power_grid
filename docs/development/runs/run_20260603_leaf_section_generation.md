# 2026-06-03 P0-07 叶子小节级正文生成回归记录

## 范围

- 大纲阶段前置拆分大叶子章节。
- 父级章节作为结构容器，不直接生成正文。
- 一键生成全文只创建叶子小节任务 item。
- 前端进度按叶子小节统计。

## 代码变更

- `backend/ai/chapter_planner.py`
  - 新增大叶子章节拆分逻辑。
  - 超过阈值的叶子章节转为 `section_role=container`。
  - 自动新增真实子章节，标记 `section_role=leaf`。
- `backend/db/supabase_repo.py`
  - `create_bid_generation_task` 创建任务前过滤非叶子 item。
  - 任务 metadata 写入 `leaf_generation_only`、`requested_item_count`、`effective_item_count`。
- `frontend/src/pages/BidEditor/index.tsx`
  - 生成进度、正文字数和一键生成目标改为叶子小节口径。
  - 父级章节显示为“结构容器”。
  - 单章生成点到父级时自动切换到第一个叶子小节。

## 静态回归

```bash
.venv/bin/python -m py_compile backend/ai/chapter_planner.py backend/db/supabase_repo.py backend/api/sections.py backend/tasks/section_tasks.py
cd frontend && npm run build -- --mode development
```

结果：

- Python 编译通过。
- 前端构建通过，仅保留既有 chunk size / dynamic import 警告。

## 大纲拆分 smoke

使用真实项目代码路径调用规则大纲构建函数，未改写数据库：

```text
total=74
containers=13
leaves=53
large_leaves=0
```

样例容器：

```text
container 5.1 发包人要求响应 target_words=0 child_count=6
```

样例叶子：

```text
leaf 5.1.1 发包人要求响应 - 编制依据 target_words=1000 generation_mode=single_pass
leaf 5.1.2 发包人要求响应 - 工程概况 target_words=1000 generation_mode=single_pass
```

## 真实后端与数据库验证

项目：

- `project_id=70323ce8-f18e-46ca-8d22-33865525a7f7`

操作：

```http
GET /api/bidding/interpretations/70323ce8-f18e-46ca-8d22-33865525a7f7/bid-outline/stream
```

结果：

```text
status=200
events=start:1, meta:1, stage:17, chapter:70, done:1
elapsed=3.71s
```

落库检查：

```text
db_total=74
db_containers=13
db_leaf_candidates=52
db_large_leaf_candidates=0
```

样例落库容器：

```text
1  level=2  投标函及投标函附录  target=0  children=3
37 level=2  发包人要求响应      target=0  children=6
44 level=2  承包人建议书        target=0  children=6
```

样例落库叶子：

```text
2  level=3  投标函及投标函附录 - 编制依据  target=1000  single_pass
3  level=3  投标函及投标函附录 - 工程概况  target=1000  single_pass
4  level=3  投标函及投标函附录 - 总体部署  target=1000  single_pass
```

额外发现并修复：

- 真实 API 验证时发现 `save_bid_outline` 会使用旧 `analysis.project_meta` 快照写回 `outline_locked=true`，导致 quick outline 虽然通过 SSE 返回，但 `replace_bid_sections_from_outline` 被大纲锁跳过。
- 已改为保存大纲前读取最新 `project_meta`，避免陈旧快照覆盖锁状态。
- 验证过程中清理了 2 条旧后台精修消息，避免旧任务继续占用 worker 或覆盖目录。

后端过滤验证：

```text
requested=20
filtered=14
container_requested=5
container_passed=0
```

## 验证结论

基础版已满足 P0-07 的架构方向：目录阶段前置拆分，正文生成只面向叶子小节。后续重点不是再做运行时隐藏拆分，而是继续增强前端任务详情面板和导出时父子章节聚合展示。

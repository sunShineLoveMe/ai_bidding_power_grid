# P1-4 正文进度口径与 P2 基础体验真实回归

日期：2026-06-27

## 结论

状态：PASS。

本轮关闭 P1-4“首页/历史记录/编辑器正文进度口径不一致”，并完成 P2 基础体验收口：加载态与空状态分离、前后端版本追踪一致、导出任务时间字段口径一致、受保护图片缩略图请求去重。

## 修复范围

### P1-4 正文进度口径

- 后端 `GET /api/bidding/history` 改为直接按当前 `bid_sections` 统计项目进度。
- 统一字段：
  - `section_count`
  - `leaf_section_count`
  - `generated_section_count`
  - `generated_leaf_count`
  - `word_count`
  - `writing_total_count`
  - `writing_done_count`
- 统计口径与编辑器一致：
  - 只统计叶子章节；
  - `status in generated/edited/completed` 且正文非占位，才算已生成；
  - 字数按已生成叶子章节正文去空白字符统计。
- 首页最近任务、历史记录均改用同一进度字段展示，避免旧的 `0/1` 占位计数。

### P2 基础体验

- 产品库、资信库加载中显示明确加载态，不再短暂显示“暂无资料”。
- 前端启动日志同时输出前端 `/build-info.json` 和后端 `/api/health` version，方便线上确认前后端是否同一 commit。
- 后端 `/api/health` 与 `/api/ready` 返回后端 `commit/branch/builtAt`。
- DOCX 导出任务 `started_at/finished_at` 改为与数据库 `created_at` 一致的北京时间 `+08:00` 输出口径。
- `AuthenticatedImage` 对受保护资源 URL 增加 object URL 缓存和引用计数，同一缩略图/原图短时间重复展示不重复请求。

## 真实验证

### 版本追踪

- 后端：`GET http://127.0.0.1:3012/api/health`
- 前端：`GET http://127.0.0.1:5173/build-info.json`
- 结果：前端和后端均为 `5b198ff908bc`，分支均为 `feat/aliyun-test-readiness`。

### 正文进度接口一致性

项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`

历史接口返回：

```json
{
  "section_count": 102,
  "leaf_section_count": 75,
  "generated_leaf_count": 75,
  "writing_total_count": 75,
  "writing_done_count": 75,
  "word_count": 173534,
  "stage": "正文初稿完成",
  "next_step": "formal_check"
}
```

编辑器等价统计：

```json
{
  "section_count": 102,
  "leaf_section_count": 75,
  "generated_leaf_count": 75,
  "word_count": 173534
}
```

结论：历史接口与编辑器一致。

### 页面回归

截图：

- `output/playwright/local-p1-4-p2-progress-loading-20260627/01-history-progress.png`
- `output/playwright/local-p1-4-p2-progress-loading-20260627/02-home-recent-progress.png`

页面结果：

- 历史记录显示 `正文 75/75` 和字数；
- 首页最近任务显示同一正文进度；
- 未再出现旧口径 `正文 0/1`。

### 加载态回归

产品库延迟接口时：

- 显示 `正在加载产品资料...`
- 未显示 `暂无产品资料`

资信库延迟接口时：

- 显示 `正在加载资信资料...`
- 未显示 `暂无资信文件`

截图：

- `output/playwright/local-p1-4-p2-progress-loading-20260627/03-product-loading-state.png`
- `output/playwright/local-p1-4-p2-progress-loading-20260627/04-product-loaded.png`
- `output/playwright/local-p1-4-p2-progress-loading-20260627/06-qualification-loading-state.png`
- `output/playwright/local-p1-4-p2-progress-loading-20260627/07-qualification-loaded.png`

### 缩略图请求去重

产品详情打开两次，统计受保护图片请求：

```json
{
  "secondOpenNewImageRequests": 0,
  "requestCounts": {
    "/api/knowledge/assets/17e53f70-649b-4a0c-8716-dfc5a502ed02/file?variant=thumb": 1,
    "/api/knowledge/assets/17e53f70-649b-4a0c-8716-dfc5a502ed02/file": 1
  },
  "duplicateUrls": []
}
```

截图：

- `output/playwright/local-p1-4-p2-progress-loading-20260627/05-product-detail-image-cache.png`

### 导出任务时间字段

真实章节 DOCX 导出任务：`64491e86-9ff2-4762-8466-258f1a3ee315`

```json
{
  "status": "completed",
  "created_at": "2026-06-27T10:07:42.033913+08:00",
  "started_at": "2026-06-27T10:07:42.611650+08:00",
  "finished_at": "2026-06-27T10:07:44.747405+08:00",
  "consistentOrder": true
}
```

结论：`created_at <= started_at <= finished_at`，且均为 `+08:00` 输出口径。

## 自动化检查

```bash
python3 -m py_compile backend/db/supabase_repo.py backend/api/health.py backend/tasks/export_tasks.py
```

结果：通过。

```bash
cd frontend && npm run build
```

结果：通过。保留既有 Vite 警告：

- `frontend/src/api/bidProject.ts` 同时被动态和静态导入，无法独立拆 chunk。
- bundle chunk 超过 `500 kB`。

## 说明

本轮为了验证导出任务时间字段，已重启本地 Celery worker。阿里云部署后需要用线上同一接口复验 `/api/health` version、历史记录正文进度和导出任务时间顺序。

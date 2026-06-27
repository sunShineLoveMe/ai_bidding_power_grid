# 阿里云测试环境缺陷与本地复核记录

日期：2026-06-26

## 测试范围

- 阿里云测试环境：`http://8.160.187.226`
- 本地后端：`http://127.0.0.1:3012`
- 本地前端：`http://127.0.0.1:5173`
- 测试账号：`admin / 12345678`
- 真实浏览器：Google Chrome 149，Chrome DevTools Protocol

## 线上真实流程结论

已完成登录、首页、招标项目、正式检查、企业知识库、企业资信库、企业产品库、用量与成本、历史记录、知识问答、标书编制、下载前检查、DOCX 草稿导出任务创建与完成。

DOCX 导出任务：

- 任务 ID：`08bd1081-da3f-4bd9-ae57-8da6685b3e48`
- `POST /api/bidding/interpretations/<project_id>/download-docx`：201
- `GET /api/bidding/interpretations/<project_id>/export-tasks/<task_id>`：200
- `status=completed`
- `progress=100`
- `field_refresh.status=refreshed`
- 文件大小：`4110378` bytes

截图：

- `output/playwright/aliyun-e2e-20260626/`
- `output/playwright/local-defect-recheck-20260626/`

## 本地复核结论

### 产品库页面空表

本地未复现。

本地真实浏览器打开 `/products`：

- 页面显示产品资料数：409
- 表格分页显示：`共 409 条`
- 空状态：否
- 截图：`output/playwright/local-defect-recheck-20260626/products.png`

但本地确认存在接口设计问题：

- 页面请求：`GET /api/knowledge/assets?library_type=product`
- 响应：数组，409 条
- 响应体大小：约 7.56 MB
- 当前前端使用 AntD 前端分页，服务端未分页。

线上“产品库空表”仍需单独定位，优先怀疑：

1. 线上前端包、接口响应和当前本地代码存在运行时差异；
2. 线上页面加载过程中全量数据过大导致状态异常或渲染失败；
3. 线上产品库页面有短时间空状态，用户看到空状态时接口尚未完成或状态被覆盖。

### 资信库页面

本地可正常显示。

- 页面显示资信文件数：190
- 表格分页显示：`共 190 条`
- 请求：`GET /api/knowledge/assets?library_type=qualification`
- 响应体大小：约 3.53 MB
- 服务端未分页。

### 知识库文档页面

本地接口确认也是全量查询。

- 请求：`GET /api/knowledge/documents`
- 响应：数组，198 条
- 响应体大小：约 0.52 MB
- 服务端未分页。

### 重复请求

本地开发模式下产品库和资信库都出现同一接口请求两次：

- `/api/knowledge/assets?library_type=product` 两次
- `/api/knowledge/assets?library_type=qualification` 两次

本地原因：`frontend/src/main.tsx` 使用 `React.StrictMode`，开发环境会触发 `useEffect` 双执行。生产构建通常不会重复；该项不作为生产阻断缺陷，但仍建议后续用 React Query 或请求去重改善开发体验。

## 相关查询接口梳理

### 企业知识库

| 页面/功能 | 前端调用 | 后端路由 | 当前返回 | 分页状态 |
| --- | --- | --- | --- | --- |
| 知识库列表 | `GET /api/knowledge/documents` | `backend/api/knowledge.py:get_knowledge_documents` | 文档数组 | 未分页 |
| 文档详情 | `GET /api/knowledge/documents/<document_id>` | `backend/api/knowledge.py:get_knowledge_document` | 文档详情 + 前 20 个 chunk | chunk 固定 `limit(20)` |
| 上传资料 | `POST /api/knowledge/upload` | `backend/api/knowledge.py:upload_knowledge` | 上传任务 | 不涉及分页 |
| 知识问答流式 | `POST /api/knowledge/search/stream` | `backend/api/knowledge.py:search_knowledge_stream` | SSE/stream | 不涉及分页 |
| 追问建议 | `POST /api/knowledge/followups` | `backend/api/knowledge.py:generate_knowledge_followups` | JSON | 不涉及分页 |

### 企业资信库 / 产品库

| 页面/功能 | 前端调用 | 后端路由 | 当前返回 | 分页状态 |
| --- | --- | --- | --- | --- |
| 资信库列表 | `GET /api/knowledge/assets?library_type=qualification` | `backend/api/assets.py:get_knowledge_assets` | 资信资产数组 | 未分页 |
| 产品库列表 | `GET /api/knowledge/assets?library_type=product` | `backend/api/assets.py:get_knowledge_assets` | 产品资产数组 | 未分页 |
| 资产详情 | `GET /api/knowledge/assets/<asset_id>` | `backend/api/assets.py:get_knowledge_asset` | 单条资产 | 不涉及分页 |
| 缩略图/原图 | `GET /api/knowledge/assets/<asset_id>/file?variant=thumb/original` | `backend/api/assets.py:get_knowledge_asset_file` | 文件流 | 不涉及分页 |
| 批量签名 URL | `POST /api/knowledge/assets/signed-urls` | `backend/api/assets.py:get_knowledge_asset_signed_urls_api` | 最多 50 个 URL | 有请求上限 |
| 上传资产 | `POST /api/knowledge/assets/upload` | `backend/api/assets.py:upload_knowledge_asset` | 单条资产 | 不涉及分页 |
| 更新资产 | `PATCH /api/knowledge/assets/<asset_id>` | `backend/api/assets.py:update_knowledge_asset_api` | 单条资产 | 不涉及分页 |

后端仓储实现：

- `backend/db/supabase_repo.py:list_knowledge_assets(asset_type=None, category=None)`
- 当前逻辑：`select("*").order("created_at", desc=True).execute()`
- 没有 `limit`、`offset`、`range`、`count`。

### 首页统计

| 模块 | 前端调用 | 问题 |
| --- | --- | --- |
| 企业知识库文件数 | `GET /api/knowledge/documents` | 为统计全量下载文档列表 |
| 企业资信库文件数 | `GET /api/knowledge/assets?library_type=qualification` | 为统计全量下载资信资产 |
| 企业产品库资料数 | `GET /api/knowledge/assets?library_type=product` | 为统计全量下载产品资产 |
| 历史任务数 | `GET /api/bidding/history?limit=100` | 已有限制，但只是取 100 条后本地计数 |

首页统计应改为专用轻量聚合接口，避免加载首页时下载约 11 MB 资产 JSON。

## 缺陷清单与优先级

### P0

当前未发现新的 P0 阻断。服务、登录、知识问答、DOCX 草稿导出后端链路可用。

### P1-1：产品库线上空表但接口有数据

状态：线上存在，本地未复现。

证据：

- 线上 API 返回 407 条产品资产；
- 线上页面显示空表；
- 本地同路径显示 409 条。

建议处理：

1. 优先重建并部署 frontend，确保前端包与当前分支一致；
2. 在线上浏览器复测 `/products` 的 DOM 状态、console error、XHR body；
3. 若仍复现，再定位 `displayAssetCategory`、分类过滤、Table dataSource 或接口响应字段差异。

### P1-2：资产列表接口缺少服务端分页

状态：本地确认存在。

影响：

- 产品库一次返回约 7.56 MB；
- 资信库一次返回约 3.53 MB；
- 首页统计也全量拉取产品库和资信库；
- 数据继续增长后会影响首屏速度、内存、Nginx/浏览器稳定性。

建议处理：

1. `GET /api/knowledge/assets` 增加 `page/page_size/search/category/library_type/status`；
2. 响应改为 `{ items, total, page, page_size }`；
3. `list_knowledge_assets` 使用 `.range(start, end)` 和 count；
4. 产品库、资信库 AntD Table 改为服务端分页；
5. 首页改用轻量统计接口，不再拉全量资产。

### P1-3：DOCX 导出完成后缺少明确下载入口

状态：线上确认存在。

证据：

- 导出任务 completed；
- 文件接口可 200 访问；
- 页面没有保留明显下载链接；
- 浏览器本机下载目录未发现新 DOCX。

建议处理：

1. 导出完成弹窗展示“下载 DOCX”主按钮；
2. 使用 `download_url` 显式创建 `<a download>` 或调用下载；
3. 同时展示任务状态、文件名、文件大小、刷新状态。

### P1-4：项目正文状态口径不一致

状态：线上确认存在。

证据：

- 首页/历史记录显示正文 `0/1`；
- 编辑器显示总章节 `185`、已生成正文小节 `83/145`、字数 `137478`。

建议处理：

1. 统一首页、历史记录、编辑器统计字段；
2. 历史接口返回 `section_count/generated_section_count/generated_leaf_count/word_count`；
3. UI 避免使用 `0/1` 这种无业务语义的占位计数。

### P2-1：部分页面短时间显示空状态

状态：线上确认存在，本地页面能正常加载但全量接口有性能风险。

建议处理：

- 加载中只显示 Skeleton/Spin，不显示“暂无资料”；
- 接口完成后再展示空状态；
- 页面增加加载超时和错误态区分。

### P2-2：线上前端 build info 与后端 HEAD 不一致

状态：线上确认存在。

证据：

- 线上 console：`commit=dffaf30d7992`
- 线上后端已更新到：`03fa733`

建议处理：

- 后续部署必须同时重建 frontend；
- `/build-info.json` 或页面 console 中展示当前 git HEAD。

### P2-3：导出任务时间字段时区/口径不一致

状态：线上确认存在。

证据：

- `created_at` 与 `started_at/finished_at` 显示相差 8 小时，但都带 `+08:00`。

建议处理：

- 后端统一存 UTC；
- API 输出统一 ISO UTC 或统一北京时间；
- 前端统一格式化展示。

### P3：缩略图重复请求与开发模式重复请求

状态：线上/本地均可观察到不同程度重复。

建议处理：

- 缩略图组件增加浏览器缓存命中或批量 signed URL；
- 前端数据层引入 React Query/SWR 做请求去重；
- 开发模式 StrictMode 重复请求不作为生产阻断。

## 推荐修复顺序

1. P1-1：先重建并部署 frontend，复测线上产品库空表。
2. P1-2：资产列表和首页统计改造为服务端分页/聚合统计。
3. P1-3：DOCX 导出完成后补明确下载入口。
4. P1-4：统一项目正文进度统计口径。
5. P2-1：加载态和空状态区分。
6. P2-2：部署版本追踪一致性。
7. P2-3：时间字段统一。
8. P3：缩略图和开发模式请求去重优化。

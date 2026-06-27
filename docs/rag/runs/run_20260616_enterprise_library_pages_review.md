# Run 31 - 企业知识库/资信库/产品库页面与 P1C-2 关联复核（2026-06-16）

## 触发原因

客户后续大概率会持续补充资料，并且前端菜单中的“企业知识库”“企业资信库”“企业产品库”均支持用户单独上传资料。本轮复核这些页面是否可用，以及它们和 `P1C-2 关键词兜底缓存失效机制` 的关联边界。

## 执行环境

- 当前真实后端：Gunicorn 进程实际监听 `0.0.0.0:3012`。
- 当前前端：用户已有 Vite 进程监听 `127.0.0.1:5173`，但代理默认目标为 `http://127.0.0.1:8000`。
- 临时验证前端：为避免改动用户进程，额外启动一次 `VITE_API_PROXY_TARGET=http://127.0.0.1:3012 npm run dev -- --host 127.0.0.1 --port 5174`，仅用于页面实测。
- 登录账号：`codex_regression_20260616`。
- 真实服务检查：直连 `http://127.0.0.1:3012/api/ready` 返回 `ok`，database、Redis、Celery、model_config、storage 均正常。

## 当前 5173 用户侧问题

当前 `5173` 前端页面的 `/api/users/login` 会被 Vite 代理到默认 `127.0.0.1:8000`，但真实后端不在 8000，导致登录请求返回 `500`。因此用户如果直接打开当前 `5173`，会停留在登录页，无法进入三类库页面。

处理建议：启动前端时显式设置：

```bash
VITE_API_PROXY_TARGET=http://127.0.0.1:3012 npm run dev
```

或将后端按默认配置绑定到 `8000`。

## 后端接口实测

直连真实后端 `3012`：

| 接口 | 状态 | 结果 |
| --- | --- | --- |
| `POST /api/users/login` | 200 | 登录成功，返回 JWT |
| `GET /api/ready` | 200 | `status=ok` |
| `GET /api/knowledge/documents` | 200 | 198 条文档 |
| `GET /api/knowledge/assets?asset_type=qualification_image` | 200 | 208 条资信资产 |
| `GET /api/knowledge/assets?asset_type=product_image` | 200 | 389 条产品资产 |

## 页面实测

在临时 `5174` 正确代理下，使用真实后端、真实数据库完成页面检查：

| 页面 | 列表接口 | 页面状态 | 上传/新增入口 | 详情/表单 |
| --- | --- | --- | --- | --- |
| 企业知识库 `/knowledge` | 200 | 正常渲染，显示资料总数 198、索引完成率 100% | “上传资料”按钮可见 | 文档详情弹窗可打开，解析内容预览可见 |
| 企业资信库 `/qualification` | 200 | 正常渲染，显示资信文件数 208 | “上传资信文件”“新增资信资料”可见 | 新增表单可打开；无文件/缺字段时出现必填校验 |
| 企业产品库 `/products` | 200 | 正常渲染，显示产品资料数 389 | “新增产品”“上传产品资料”“新增产品资料”可见 | 新增表单可打开；无文件/缺字段时出现必填校验 |

说明：本轮未创建测试资产，避免污染正式泰昌资料库；验证范围覆盖真实列表、真实详情、表单打开和前端校验。

## 与 P1C-2 的关联判断

### 企业知识库

强相关。页面上传走：

```text
POST /api/knowledge/upload
  -> create_knowledge_document
  -> sync_and_parse_knowledge Celery
  -> document_chunks 写入
  -> search_knowledge_base
  -> _keyword_search_knowledge_chunks
  -> _CHUNK_KEYWORD_CACHE
```

因此客户新增知识文档、重抽取或重入库后，如果 Web 进程已经生成过 `_CHUNK_KEYWORD_CACHE`，后续关键词兜底可能仍读取旧 `document_chunks` 快照。P1C-2 必须覆盖这个场景。

### 企业资信库 / 企业产品库

间接相关但不是同一个缓存。页面上传走：

```text
POST /api/knowledge/assets/upload
  -> _asset_payload_from_form
  -> _maybe_attach_asset_embedding
  -> create_knowledge_asset
  -> search_knowledge_assets
  -> _keyword_search_knowledge_assets
```

资产上传时会即时根据标题、说明、分类、标签、适用章节和规格字段生成 `searchable_text` 与 asset embedding；资产关键词兜底每次直接查询 `knowledge_assets limit 500`，不使用 `_CHUNK_KEYWORD_CACHE`。因此 P1C-2 的核心不是资产上传缓存，而是文档分片关键词兜底缓存；但资信/产品库仍应纳入回归抽样，确认新增资产不会因 embedding 失败或检索过滤被漏召回。

## 风险与后续

1. 先修正本地前端代理启动方式，否则用户从 `5173` 无法登录页面。
2. P1C-2 实现时优先增加 `document_chunks` 写入/重入库后的缓存失效入口，或在 `_keyword_search_knowledge_chunks` 上增加版本/TTL。
3. 后续如果客户通过页面上传资信/产品资产，应增加真实新增资产抽样：上传后立即用 `/api/knowledge/search/stream` 问对应资料，验证 asset embedding 和资产关键词兜底均可命中。

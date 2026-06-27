# P1-2 资产列表分页与首页统计接口修复记录

日期：2026-06-26

## 背景

阿里云测试环境复测发现企业产品库、资信库和首页统计存在全量加载问题。随着客户资料增长，前端一次性下载所有资产 JSON 会造成首屏变慢、内存压力和页面空状态误判风险。

本次优先收口 P1-2：

1. 产品库/资信库列表改为服务端分页；
2. 首页数据准备情况改为轻量统计接口；
3. 保留老接口兼容性，避免影响写作、正式检查、导出等仍依赖全量资产的内部逻辑。

## 修改内容

### 后端

- `backend/db/supabase_repo.py`
  - 新增 `list_knowledge_assets_page(...)`
  - 新增 `get_knowledge_asset_stats(...)`
  - 新增 `get_knowledge_overview_stats()`
  - 分页查询使用 `.select(..., count="exact").range(start, end)`；
  - `library_type=product/qualification` 在分页和统计路径下落到 `asset_type=product_image/qualification_image` 过滤。

- `backend/api/assets.py`
  - `GET /api/knowledge/assets` 支持 `page/page_size/limit/offset`；
  - 带分页参数时返回：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 10,
  "stats": {}
}
```

  - 不带分页参数时仍返回旧数组，保持兼容。
  - 新增 `GET /api/knowledge/assets/stats?library_type=product|qualification`。

- `backend/api/knowledge.py`
  - 新增 `GET /api/knowledge/stats`，返回首页需要的知识库、资信库、产品库统计。

### 前端

- `frontend/src/pages/ProductBase/index.tsx`
  - 产品库改为服务端分页；
  - 分类切换重新请求第一页；
  - 顶部指标使用后端 stats，总数不再误显示当前页数量。

- `frontend/src/pages/QualificationBase/index.tsx`
  - 资信库改为服务端分页；
  - 分类统计使用后端 stats；
  - 表格分页由后端 total 驱动。

- `frontend/src/components/home/KnowledgeStats.tsx`
  - 首页改为调用 `GET /api/knowledge/stats`；
  - 不再调用：
    - `GET /api/knowledge/documents`
    - `GET /api/knowledge/assets?library_type=qualification`
    - `GET /api/knowledge/assets?library_type=product`

## 本地接口验证

登录后真实接口结果：

| 接口 | 修改前 | 修改后 |
| --- | ---: | ---: |
| `GET /api/knowledge/assets?library_type=product` | 409 条，约 7.56 MB | 旧兼容路径仍保持 |
| `GET /api/knowledge/assets?library_type=product&page=1&page_size=10` | 无 | 10 条，约 36 KB |
| `GET /api/knowledge/assets?library_type=qualification` | 190 条，约 3.53 MB | 旧兼容路径仍保持 |
| `GET /api/knowledge/assets?library_type=qualification&page=1&page_size=10` | 无 | 10 条，约 37 KB |
| `GET /api/knowledge/assets/stats?library_type=product` | 无 | 约 558 bytes |
| `GET /api/knowledge/stats` | 无 | 约 1.2 KB |

## 真实浏览器验证

本地 Chrome + Vite：

- 首页 `/`
  - 企业知识库文件数：198
  - 企业资信库文件数：190
  - 企业产品库资料数：409
  - 页面只调用 `GET /api/knowledge/stats`，不再全量拉取资产列表。

- 产品库 `/products`
  - 顶部产品资料数：409
  - 表格分页：`共 409 条`
  - 当前页加载 10 条
  - 请求：`GET /api/knowledge/assets?library_type=product&page=1&page_size=10`
  - 响应体约 36 KB

- 资信库 `/qualification`
  - 顶部资信文件数：190
  - 表格分页：`共 190 条`
  - 当前页加载 10 条
  - 请求：`GET /api/knowledge/assets?library_type=qualification&page=1&page_size=10`
  - 响应体约 37 KB

截图目录：

```text
output/playwright/local-p1-2-pagination-20260626/
```

## 验证命令

```bash
python3 -m py_compile backend/db/supabase_repo.py backend/api/assets.py backend/api/knowledge.py
cd frontend && npm run build
```

结果：

- Python 编译通过；
- 前端 TypeScript + Vite 构建通过；
- Vite 仅提示既有大 chunk 警告，不影响本次功能。

## 后续注意

- 本地开发环境中 React StrictMode 会让 `useEffect` 请求执行两次；生产构建通常不会重复。这不是本次 P1-2 阻断项。
- 旧全量资产接口仍保留，后续可逐步把写作、正式检查、导出链路中的内部全量调用拆成更精细的检索或按需查询。
- 阿里云部署时需要同时重建 frontend，否则线上仍可能使用旧前端包。

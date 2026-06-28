# 2026-06-27 正式检查按钮与分页回归

## 背景

客户反馈“正式检查”页面处理路径按钮文字颜色不明显，同时底部分页组件切换 `20 条/页` 后没有生效。该问题会影响正式检查页面的操作可读性和分页体验。

## 问题定位

1. 按钮文字变灰：
   - `.formal-check-action-cell span` 用于处理说明文字，但该选择器也覆盖了 Ant Design Button 内部的文字 `span`。
   - 结果是主按钮虽然设置了蓝底白字，但按钮内文字又被覆盖为灰蓝色。

2. 页容量选择不生效：
   - 正式检查表格配置了 `pagination={{ pageSize: 12 }}`。
   - Ant Design 的页容量下拉会显示 10/12/20/50/100，但 `pageSize` 固定传入后会把用户选择覆盖回 12。
   - 同类风险也存在于历史记录、知识库、用量成本、招标解读等使用固定 `pageSize` 的表格。

## 修改范围

- `frontend/src/pages/FormalCheck/index.tsx`
  - 处理说明文字改为 `.formal-check-action-description`，不再用泛化 `span` 选择器。
  - 正式检查表格分页改为 `defaultPageSize: 12`，并显式开放 `[10, 12, 20, 50, 100]`。
- `frontend/src/index.css`
  - 主操作按钮内部 `span` 和 `svg` 强制为白色。
- `frontend/src/pages/History/index.tsx`
  - 历史记录表格改为 `defaultPageSize`。
- `frontend/src/pages/KnowledgeBase/index.tsx`
  - 企业知识库表格改为 `defaultPageSize`。
- `frontend/src/pages/UsageCost/index.tsx`
  - 项目成本汇总和完整调用明细表格改为 `defaultPageSize`。
- `frontend/src/pages/Interpretation/index.tsx`
  - 招标解读页高级信息、合规检查、要求、风险、评分、章节建议等表格改为 `defaultPageSize`。

说明：

- 企业产品库、企业资信库已经是服务端受控分页，保留 `pageSize: pagination.pageSize` 和 `onChange`。
- 用量成本“模型类型成本拆分”表格明确 `showSizeChanger: false`，不会出现页容量选择器失效问题。

## 真实浏览器回测

环境：

- 前端：`http://127.0.0.1:5173`
- 浏览器：本机 Google Chrome，Playwright 控制
- 登录账号：本地测试账号 `admin`

正式检查页：

| 验证项 | 结果 |
| --- | --- |
| 初始页容量 | PASS。显示 `12 条/页`，首屏实际表格行数 12。 |
| 切换 20 条/页 | PASS。选择 `20 条/页` 后实际表格行数从 12 变为 20。 |
| 主按钮颜色 | PASS。`去投标确认` 按钮 `buttonColor=rgb(255,255,255)`、`spanColor=rgb(255,255,255)`、`svgColor=rgb(255,255,255)`、`background=rgb(37,99,235)`。 |

其他页面抽测：

| 页面 | 初始 | 切换后 | 结果 |
| --- | --- | --- | --- |
| 历史记录 | 10 行 / `10 条/页` | 20 行 / `20 条/页` | PASS |
| 企业知识库 | 10 行 / `10 条/页` | 20 行 / `20 条/页` | PASS |
| 企业产品库 | 10 行 / `10 条/页` | 20 行 / `20 条/页` | PASS |
| 企业资信库 | 10 行 / `10 条/页` | 20 行 / `20 条/页` | PASS |
| 用量与成本 | 14 行 / `10 条/页` | 24 行 / `20 条/页` | PASS |
| 招标项目 | 当前数据态未出现页容量选择器 | 代码已修为 `defaultPageSize` | 当前无可操作选择器 |

截图记录：

- `output/playwright/formal-check-pagination-20-and-button-white.png`
- `output/playwright/pagination-other-pages-smoke.png`

## 命令验证

```bash
npm run build
```

结果：

- 前端构建通过。
- Vite 保留既有大 chunk 和动态/静态混用提示，不影响本次修复。


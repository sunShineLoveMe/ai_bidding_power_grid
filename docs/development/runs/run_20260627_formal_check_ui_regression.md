# 2026-06-27 正式检查页面体验回归

## 背景

客户反馈“正式检查”页面存在首屏闪空态、生成时间显示 ISO 字符串、检查项明细滚动卡住、操作按钮和英文内部字段不便理解等问题。该页面属于正式导出前门禁，首屏误导会影响客户对项目状态的判断。

## 修改范围

- `frontend/src/pages/FormalCheck/index.tsx`
  - 首次加载期间显示骨架屏，不再提前渲染“当前项目暂无正式检查报告”。
  - 生成时间改用项目统一 `formatDateTime`，按北京时间中文习惯展示。
  - 用户可见证据、来源、规则说明增加内部字段中文兜底映射。
  - 规则总数卡片不再展示 `formal_bid_check_rules.v1` 等内部规则文件标识。
- `frontend/src/index.css`
  - 放开正式检查表格区域纵向滚动链，避免表格区域截断主页面滚动。
  - 增强处理路径按钮对比度，阻断项主操作为白字蓝底并设置最小宽度。
- `backend/services/formal_bid_check.py`
  - 后端正式检查证据生成时将投标确认字段 key 转换为中文标签。
  - 返回 `fieldLabels`，保留 `fieldKeys` 仅用于前端跳转定位。
- `tests/test_formal_bid_check.py`
  - 增加证据中文化回归断言，防止 `total_bid_price` 等内部 key 再次泄露到页面证据。

## 真实浏览器回测

环境：

- 前端：`http://127.0.0.1:5173`
- 浏览器：本机 Google Chrome，Playwright 控制
- 登录账号：本地测试账号 `admin`
- 页面：`/formal-check`

结果：

| 验证项 | 结果 |
| --- | --- |
| 首屏加载态 | PASS。进入页面 150ms 时显示 `.formal-check-loading-card` 骨架屏，未出现“当前项目暂无正式检查报告”。 |
| 数据加载完成 | PASS。报告加载后展示 61 条规则、阻断项、项目、规则集和检查项明细。 |
| 时间格式 | PASS。生成时间显示为 `2026/06/27 12:12`，未出现 `2026-...T...+00:00` ISO 字符串。 |
| 英文字段中文化 | PASS。页面文本未命中 `total_bid_price`、`bid_bond_amount`、`authorized_representative`、`signature_date`、`formal_bid_check_rules.v1`；证据显示“投标总价”“投标保证金金额”“授权代表”“签署日期”。 |
| 表格滚动 | PASS。低高度视口下 `main.scrollHeight=2094`、`clientHeight=508`；鼠标在检查项表格内滚轮可将主页面 `scrollTop` 从 `951.5` 推进到 `1586`，向上滚动可回到 `1086`。 |
| 展开行后滚动 | PASS。展开检查项证据链后，鼠标在展开内容内滚轮可将主页面 `scrollTop` 从 `408` 推进到 `958`。 |
| 操作按钮可读性 | PASS。阻断项“去投标确认”按钮样式为白字蓝底，`backgroundColor=rgb(37, 99, 235)`、`color=rgb(255, 255, 255)`、`minWidth=108px`。 |

截图记录：

- `output/playwright/formal-check-ui-fix-after-login.png`
- `output/playwright/formal-check-ui-fix-scroll-buttons.png`
- `output/playwright/formal-check-ui-fix-short-viewport.png`
- `output/playwright/formal-check-ui-fix-table-wheel.png`
- `output/playwright/formal-check-ui-fix-expanded-scroll.png`

## 命令验证

```bash
.venv/bin/python -m unittest tests.test_formal_bid_check
npm run build
```

结果：

- `tests.test_formal_bid_check`：7 tests passed。
- `frontend npm run build`：通过。Vite 仅保留既有大 chunk 和动态/静态混用提示，不影响本次修改。


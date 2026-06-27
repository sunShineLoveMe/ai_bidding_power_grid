# P1-3 分册导出完成下载按钮真实回归

日期：2026-06-27

## 结论

状态：PASS。

标书编制页已把单一下载入口调整为“导出投标文件”下拉入口，并在 DOCX 导出任务完成后展示明确下载按钮。技术标、商务标均完成真实浏览器导出、弹窗确认和文件下载回归。

## 验证环境

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:3012`
- 浏览器：Chrome CDP `127.0.0.1:9223`
- 项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 测试账号：本地临时账号 `codex_p13_*`

## 页面验证

页面：`/bid-editor?projectId=a1d853bc-ca4e-43b4-bbea-256f561c8a3d`

验证项：

- 顶部操作区存在“导出投标文件”按钮。
- 下拉菜单包含：
  - 下载技术标 DOCX
  - 下载商务标 DOCX
  - 下载完整投标文件 DOCX
- 完成弹窗显示交付包、文件名、文件大小、字段刷新状态、图片插入统计。
- 完成弹窗提供明确下载按钮，不再只依赖自动打开下载地址。

截图：

- `output/playwright/local-p1-3-export-completion-20260627/01-editor-export-button.png`
- `output/playwright/local-p1-3-export-completion-20260627/02-export-menu.png`
- `output/playwright/local-p1-3-export-completion-20260627/03-technical-export-completed-modal.png`
- `output/playwright/local-p1-3-export-completion-20260627/04-business-export-completed-modal.png`

## 技术标真实导出

- 任务 ID：`8caee0be-9b2e-4ab6-9b43-e0bae74b78b1`
- 请求：`POST /api/bidding/interpretations/a1d853bc-ca4e-43b4-bbea-256f561c8a3d/download-docx`
- 请求体关键字段：`volumeType=technical`，`withImages=true`
- 完成弹窗标题：`技术标 DOCX 已生成`
- 文件名：`国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.docx`
- 文件大小：`4.84 MB`
- 字段刷新：已刷新目录和页码
- 图片插入：插入 `24` 张，跳过 `0` 张，失败 `0` 张
- 下载按钮：`下载技术标 DOCX`
- 下载验证：点击按钮触发 Chrome `download` 事件并保存成功

下载样本：

`output/playwright/local-p1-3-export-completion-20260627/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.docx`

## 商务标真实导出

- 任务 ID：`deed0129-d229-4bae-8aeb-b8e04308fd19`
- 请求：`POST /api/bidding/interpretations/a1d853bc-ca4e-43b4-bbea-256f561c8a3d/download-docx`
- 请求体关键字段：`volumeType=business`，`withImages=true`
- 完成弹窗标题：`商务标 DOCX 已生成`
- 文件名：`国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.docx`
- 文件大小：`4.17 MB`
- 字段刷新：已刷新目录和页码
- 图片插入：插入 `18` 张，跳过 `0` 张，失败 `0` 张
- 下载按钮：`下载商务标 DOCX`
- 下载验证：点击按钮触发 Chrome `download` 事件并保存成功

下载样本：

`output/playwright/local-p1-3-export-completion-20260627/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.docx`

## 自动化检查

```bash
cd frontend && npm run build
```

结果：通过。保留既有 Vite 警告：

- `frontend/src/api/bidProject.ts` 同时被动态和静态导入，无法独立拆 chunk。
- bundle chunk 超过 `500 kB`。

```bash
python3 -m py_compile backend/api/assets.py backend/api/knowledge.py backend/db/supabase_repo.py
```

结果：通过。

## 后续

- 阿里云环境部署后，需要用线上域名复验同一流程，重点确认浏览器下载策略、Nginx 反向代理、HTTP/HTTPS 混合策略不会阻断 DOCX 下载。
- 若线上仍走 HTTP，优先继续保留同页明确下载按钮；正式客户环境建议启用 HTTPS。

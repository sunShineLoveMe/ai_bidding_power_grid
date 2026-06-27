# run_20260626_formal_check_processing_path

- 日期：2026-06-26
- 范围：正式检查页面、正式检查 API、投标确认页定位、正文编辑跳转
- 结论：PASS

## 背景

客户进入正式检查页后，不能只看到阻断项和建议，还需要知道“去哪里改、改什么、依据是什么”。本轮将正式检查项补齐为可处理事项，形成检查项到投标确认页、正文编辑页、企业资信库、企业产品库的处理路径。

## 改动摘要

1. 正式检查后端每条检查项新增：
   - `action.type`
   - `action.label`
   - `action.target`
   - `action.description`
   - `evidenceChain`
   - `checkType`
   - `fieldKeys`
2. 正式检查前端表格新增“处理路径”列。
3. 正式检查表格支持展开查看证据链：规则依据、当前证据、处理建议。
4. 投标确认页支持 `focus=<fieldKey>`，可从正式检查项跳转并定位客户确认字段。
5. 正文编辑页支持 `sectionId=<sectionId>`，可从正式检查项进入对应章节。

## 真实浏览器回归

- 页面：`http://localhost:5173/formal-check`
- 登录账号：`admin`
- 当前项目：`4d632dbe-f6e6-4066-8fe2-929ecb54ba1d`
- 正式检查 API：`GET /api/bidding/projects/4d632dbe-f6e6-4066-8fe2-929ecb54ba1d/formal-check`
- 规则总数：60
- 当前阻断项：8

### 验证点

| 项目 | 结果 |
| --- | --- |
| 正式检查页可加载 | PASS |
| 页面展示“处理路径”列 | PASS |
| 表格可展开证据链 | PASS |
| `B-002 投标总价必须客户确认` 返回 `action.type=prefill`、`target=total_bid_price` | PASS |
| `Q-001 营业执照资料必须存在` 返回 `action.type=qualification_library` | PASS |
| `T-001 技术规范响应章节必须存在` 返回 `action.type=bid_editor` 和章节 ID | PASS |
| 点击 `B-002` 的“去投标确认” | PASS |
| 跳转 URL 包含 `/prefill?projectId=...&focus=total_bid_price` | PASS |
| 投标确认页渲染 `data-prefill-field=total_bid_price` | PASS |

截图：

- `output/playwright/formal-check-processing-path.png`

## 自动化验证

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=. .venv/bin/python -m pytest tests/test_formal_bid_check.py -q` | PASS，6 passed |
| `cd frontend && npm run build` | PASS，仅保留既有 dynamic import / chunk size 警告 |

## 结论

正式检查页已从“只展示检查结果”推进到“检查结果 + 证据链 + 明确处理路径”。当前 P1 的“检查项跳转处理、分级筛选、分类筛选、检查项证据链展示”已完成第一版真实链路验证。

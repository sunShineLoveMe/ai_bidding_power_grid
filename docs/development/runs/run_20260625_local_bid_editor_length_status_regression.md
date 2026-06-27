# run_20260625_local_bid_editor_length_status_regression

## 目标

验证 P0 `SG-UX-001/002`：

- 完成章节的主状态必须显示为 `已完成`，偏长/偏短只作为质量提示。
- 偏长章节新增 `压缩到目标`，避免用户只能选择重新生成。
- `shorten` 支持整章压缩，不再被旧的 5000 字上限误伤。

## 环境

```text
本地前端：Vite http://127.0.0.1:5173
本地后端：http://127.0.0.1:3012
账号：admin / 12345678
项目：628ed517-0c31-44ea-a5cb-95b25db06fc2
页面：/bid-editor?projectId=628ed517-0c31-44ea-a5cb-95b25db06fc2
```

## 代码验证

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| 后端语法 | `python3 -m py_compile backend/services/ai_editing.py` | PASS |
| 前端生产构建 | `cd frontend && npm run build` | PASS；仅保留既有 Vite dynamic import / chunk size warning |

## 浏览器真实回归

| 编号 | 操作 | 结果 |
| --- | --- | --- |
| R1 | Chrome 打开本地登录页并登录 `admin / 12345678` | 登录成功 |
| R2 | 进入本地标书编辑页并切换 `目录模式` | 项目加载成功，206 章 |
| R3 | 检查偏长章节行文案 | `1.1 编制依据` 显示 `已完成 1672字` + `偏长 1672/1000字` |
| R4 | 检查偏短章节行文案 | `25.1 编制依据` 显示 `已完成 608字` + `偏短 608/950字` |
| R5 | 检查偏长章节动作 | 同一行含 `重新生成`、`压缩到目标`、`预览`、`更多` |
| R6 | 打开 `更多` 菜单 | 菜单含 `自定义编写`、`新增子章节`、`修改标题`、`上移章节`、`下移章节`、`删除章节` |
| R7 | 打开 `压缩到目标` 确认框并取消 | 弹窗显示当前字数、目标字数，说明不会重新生成整章；取消成功 |
| R8 | 新浏览器会话查看 console | 0 errors，0 warnings |

截图：

```text
output/playwright/local_bid_editor_length_status_final_20260625.png
```

## 真实压缩链路

为避免污染正式章节，使用本地项目临时创建章节，真实调用 `POST /sections/ai-edit` 的 `shorten`，保存结果后删除临时章节。

| 编号 | 输入 | 结果 | 清理 |
| --- | --- | --- | --- |
| API-1 | 4378 字临时章节 | 压缩为 128 字，保存状态 `edited` | 已删除 `5a91d4c3-dfc3-47de-81e5-2a7d4f3f52df` |
| API-2 | 6198 字临时章节，超过旧 5000 字限制 | 压缩为 130 字，保存状态 `edited` | 已删除 `4f350e5b-1608-4ee5-afaa-8e1d9ab110ac` |

清理确认：

```text
temp_5a91_exists=False
temp_4f35_exists=False
section_count=206
```

## 结论

`SG-UX-001` 和 `SG-UX-002` 本地实现与真实回归通过。下一项 P0 应继续处理 `SG-AI-001`：自定义编写要求持久化，并确保后台任务真实读取。

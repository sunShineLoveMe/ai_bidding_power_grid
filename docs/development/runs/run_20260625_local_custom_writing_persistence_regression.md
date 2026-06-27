# 2026-06-25 本地自定义编写持久化回归

## 目标

验证 `SG-AI-001`：单章“自定义编写”要求不再只停留在前端内存，必须持久化到章节，并进入章节生成任务 item metadata 快照，保证后台 Celery 生成可追溯。

## 环境

```text
分支：feat/aliyun-test-readiness
本地前端：http://127.0.0.1:5173
本地后端：http://127.0.0.1:3012
测试账号：admin / 12345678
测试项目：628ed517-0c31-44ea-a5cb-95b25db06fc2
```

## 涉及改动

| 文件 | 说明 |
| --- | --- |
| `frontend/src/pages/BidEditor/index.tsx` | 自定义编写弹窗改为受控 Modal；保存时调用 `saveBidSection()` 持久化 `writing_notes` 和 `metadata.custom_writing`；创建单章/批量生成任务时写入 item metadata 快照 |
| `frontend/src/api/bidProject.ts` | `SectionGenerationTaskItem` 和创建任务 payload 支持 `metadata` |
| `backend/db/supabase_repo.py` | `_normalize_generation_task_items()` 与 `bid_generation_task_items` 行同步保留 item `metadata` |

## API 回归

步骤：

1. 登录本地 API。
2. 创建临时章节 `临时自定义编写回归-自动删除-20260625162049`。
3. 写入唯一自定义要求到 `writing_notes` 与 `metadata.custom_writing`。
4. 创建真实 `section-generation-tasks`，设置 `autoStart=false`，避免触发真实大模型生成。
5. 读取 task，验证 item metadata 保留 `writing_notes/custom_writing`。
6. 取消任务，删除临时章节。

结果：

```json
{
  "ok": true,
  "section_id": "147fe5a8-6de3-4105-b1c9-7fcd88fe9e2c",
  "task_id": "fb1c6d15-0fc8-48a5-8441-81d227340beb",
  "task_status_after_cancel": "cancelled",
  "section_writing_notes_count": 1,
  "task_item_metadata_keys": [
    "custom_writing",
    "source",
    "writing_notes",
    "writing_notes_count"
  ]
}
```

结论：通过。

## 浏览器回归

步骤：

1. 清理 Playwright 会话数据。
2. 打开 `/bid-editor?projectId=628ed517-0c31-44ea-a5cb-95b25db06fc2`。
3. 未登录状态自动跳转 `/login`。
4. 使用 `admin / 12345678` 登录。
5. 再次进入标书编辑页。
6. 创建临时章节 `临时浏览器自定义编写回归-自动删除-20260625162135`。
7. 使用章节搜索框定位临时章节。
8. 点击该行“章节操作”，确认菜单存在。
9. 点击“自定义编写”，输入：

```text
浏览器回归-20260625162135：本章必须说明责任部门、完成时限、验收材料索引。
```

10. 点击“保存写作要求”。
11. 通过 API 读取同一章节，验证要求已持久化。
12. 删除临时章节。

浏览器菜单检查：

| 菜单项 | 结果 |
| --- | --- |
| 编写章节 | 存在 |
| 自定义编写 | 存在 |
| 添加章节 | 存在 |
| 上移章节 | 存在 |
| 下移章节 | 存在，末尾章节下移禁用 |
| 修改标题 | 存在 |
| 删除章节 | 存在 |

API 验证结果：

```json
{
  "ok": true,
  "section_id": "4876d643-e294-47ab-8fdd-0c3a8530ccbd",
  "persisted_writing_notes_count": 1,
  "last_instruction": "浏览器回归-20260625162135：本章必须说明责任部门、完成时限、验收材料索引。",
  "cleanup_deleted": true,
  "before_cleanup_count": 207,
  "after_cleanup_count": 206
}
```

结论：通过。

## 构建与静态检查

```text
npm run build
python3 -m py_compile backend/db/supabase_repo.py
```

结果：

- 前端构建通过。
- 后端 Python 语法检查通过。
- Vite 仍提示既有大 chunk 与动态导入警告，不阻断。

## 遗留告警

浏览器 console 出现：

```text
Warning: [antd: message] Static function can not consume context like dynamic theme. Please use 'App' component instead.
```

判断：

- 功能未失败，持久化和清理均成功。
- 该告警来自项目内大量静态 `message.*` 调用，非本次链路独有。
- 建议后续前端统一切换到 Ant Design `App.useApp()`，避免真实浏览器回归中产生 console error 级别告警。

## 结论

`SG-AI-001` 本地验收通过。下一项 P0 进入 `SG-DATA-001`：新增子章节继承父章节分册，并在当前筛选中可见。

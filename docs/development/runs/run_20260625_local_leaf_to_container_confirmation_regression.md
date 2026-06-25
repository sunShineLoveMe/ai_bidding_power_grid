# 2026-06-25 本地回归：叶子章节转结构容器确认

## 范围

- 任务：`SG-DATA-002`
- 项目：`628ed517-0c31-44ea-a5cb-95b25db06fc2`
- 页面：`http://127.0.0.1:5173/bid-editor?projectId=628ed517-0c31-44ea-a5cb-95b25db06fc2`
- 后端：`http://127.0.0.1:3012`
- 账号：`admin`

## 验收目标

| 目标 | 验收结论 |
| --- | --- |
| 叶子章节新增子章节前不静默转容器 | 通过 |
| 已有正文/目标字数章节弹出确认 | 通过 |
| 支持保留父章节正文作为概述 | 通过 |
| 支持迁移父章节正文到新子章节 | 通过 |
| 新子章节继承父章节分册 metadata | 通过 |
| 测试数据不污染项目 | 通过 |

## 实施要点

- `frontend/src/pages/BidEditor/index.tsx` 新增受控确认弹窗 `LeafToContainerConfirmModal`。
- 增加 `keep_parent_summary` 与 `move_content_to_child` 两种处理策略。
- 父章节转结构容器时补充可追溯 metadata：`section_role`、`leaf_generation`、`container_conversion_mode`、`container_content_policy`、`container_conversion_source`。
- 迁移正文到子章节时补充 `migrated_from_parent_id`、`migrated_from_parent_title`、`migration_source`、`migrated_at`。

## 真实回归记录

| 步骤 | 方式 | 结果 |
| --- | --- | --- |
| 构建 | `npm run build` | 通过；保留既有 Vite chunk size / 动态导入 warning |
| 创建保留策略父章节 | 真实 API | 创建 `P0回归叶子转容器-keep-164900` |
| 保留策略页面操作 | Playwright 真实浏览器 | 点击“添加章节”后出现确认弹窗，确认后创建 `新增章节` |
| 保留策略 API 核对 | 真实 API | 父章节 `container_conversion_mode=keep_parent_summary`，子章节继承技术分册 |
| 创建迁移策略父章节 | 真实 API | 创建 `P0回归叶子转容器-move-164900`，写入真实 Markdown 正文 |
| 迁移策略页面操作 | Playwright 真实浏览器 | 弹窗展示当前正文约 73 字，选择“将本章正文迁移到新子章节”后确认 |
| 迁移策略 API 核对 | 真实 API | 父章节改为结构容器概述；新子章节保留原正文并记录迁移 metadata |
| 测试数据清理 | 真实 API | 删除 2 个父章节和 2 个子章节 |
| 清理核对 | 真实 API | 项目章节数恢复 206，`regression_case=leaf_to_container_confirmation` 剩余 0 |
| 浏览器 console | Playwright CLI | 本功能操作完成后 `console error` 为 0 |

## 关键 API 结果

保留策略父章节：

```json
{
  "section_role": "container",
  "leaf_generation": false,
  "container_conversion_mode": "keep_parent_summary",
  "container_content_policy": "parent_content_kept_as_overview",
  "volume_type": "technical"
}
```

迁移策略父章节：

```json
{
  "section_role": "container",
  "leaf_generation": false,
  "container_conversion_mode": "move_content_to_child",
  "container_content_policy": "original_content_moved_to_first_child",
  "volume_type": "technical"
}
```

迁移策略子章节：

```json
{
  "migrated_from_parent_id": "cf2a2c01-bcca-4a95-9278-d8cf3aba18d2",
  "migration_source": "leaf_to_container_conversion",
  "volume_type": "technical"
}
```

## 遗留观察

- 本次功能操作链路未新增 console error。
- 登录成功提示仍会触发项目既有 Ant Design 5 静态 `message.*` context warning：`Static function can not consume context like dynamic theme`；该问题来自全局静态 message 使用方式，建议后续统一迁移到 `App.useApp()`，不要混在本次数据语义修复内扩散改动范围。

## 结论

`SG-DATA-002` 本地真实回归通过。下一项 P0 是 `SG-DATA-003：删除真实提示与撤销/回收站兜底`。

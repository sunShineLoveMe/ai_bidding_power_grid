# 2026-06-25 本地新增子章节分册继承回归

## 目标

验证 `SG-DATA-001`：在技术/商务筛选下新增章节，或对父章节新增子章节时，新章节必须继承正确分册 metadata，并在当前筛选下立即可见，避免再次出现 `volume_type=None/other` 导致技术视图看不到新章节。

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
| `frontend/src/pages/BidEditor/index.tsx` | 新增章节时根据父章节或当前分册筛选写入 `volume_type/volume_name/export_group/document_role`；子章节记录 `inherited_from_parent_id` 和 `created_from_active_volume` |
| `backend/db/supabase_repo.py` | `upsert_bid_section()` 增加父章节分册继承兜底；客户端未传有效分册时从父章节 metadata 补齐，并修正 `export_group` |

## API 回归

步骤：

1. 登录本地 API。
2. 创建临时技术父章节，metadata 指定 `volume_type=technical`、`export_group=技术标文件`。
3. 创建默认标题 `新增章节` 的子章节，不主动传 metadata。
4. 读取保存结果，验证后端自动继承分册字段。
5. 删除临时父子章节。

结果：

```json
{
  "ok": true,
  "parent_id": "1bfb345f-06fa-40c3-b668-c3fad63b29f5",
  "child_id": "f612d62e-3228-4c8b-a10b-0a5129ded5d2",
  "child_metadata": {
    "document_role": "正文",
    "export_group": "技术标文件",
    "inherited_from_parent_id": "1bfb345f-06fa-40c3-b668-c3fad63b29f5",
    "volume_name": "技术标",
    "volume_type": "technical"
  },
  "before_count": 206,
  "after_cleanup_count": 206
}
```

结论：通过。

## 浏览器回归

步骤：

1. 创建临时技术父章节 `临时UI技术父章节-自动删除-20260625163330`。
2. 打开浏览器并登录。
3. 进入 `/bid-editor?projectId=628ed517-0c31-44ea-a5cb-95b25db06fc2`。
4. 切换到“技术”分册筛选。
5. 在技术视图下找到临时父章节，打开“章节操作”菜单。
6. 点击“添加章节”。
7. 验证新增子章节在技术视图中立即可见。
8. 通过 API 验证子章节 metadata。
9. 删除临时父子章节。

页面现象：

| 验收项 | 结果 |
| --- | --- |
| 父章节可见性 | 临时技术父章节在技术筛选中可见 |
| 新增后计数 | 技术计数 `126 -> 127`，总章节 `207 -> 208` |
| 子章节可见性 | 左侧技术视图显示 `29.1 新增章节` |
| 右侧标签 | 子章节详情区显示 `技术标 / 技术标` |
| 清理 | 临时父子章节删除后章节数恢复 206 |

API 验证结果：

```json
{
  "ok": true,
  "parent_id": "30e01c31-d14e-4dc9-9f55-139878d55b75",
  "child_id": "9f2ff10e-8a41-4fa7-a235-eea135084122",
  "child_title": "新增章节",
  "child_metadata": {
    "created_from_active_volume": "technical",
    "document_role": "正文",
    "export_group": "技术标文件",
    "inherited_from_parent_id": "30e01c31-d14e-4dc9-9f55-139878d55b75",
    "volume_name": "技术标",
    "volume_type": "technical"
  },
  "before_cleanup_count": 208,
  "after_cleanup_count": 206,
  "left_count": 0
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

浏览器登录流程仍出现既有 Ant Design 静态 `message.*` context warning：

```text
Warning: [antd: message] Static function can not consume context like dynamic theme. Please use 'App' component instead.
```

该告警与本次分册继承功能无直接关系，功能验证通过。建议后续统一改造全局 `message.*` 调用。

## 结论

`SG-DATA-001` 本地验收通过。下一项 P0 进入 `SG-DATA-002`：叶子章节转结构容器前增加确认和正文处理策略。

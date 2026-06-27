# 2026-06-26 真实浏览器全流程标书正文生成回归

## 结论

本次使用 Chrome 真实页面流程，从上传真实辽宁招标文件开始，完成：

上传招标文件 -> 招标文件解析 -> AI 招标解读 -> 分册大纲生成 -> 投标信息确认 -> 标书正文编辑页 -> 一键编写全文 -> partial 草稿续写 -> 75/75 个叶子正文全部完成。

最终结果：通过。正文生成主链路可完成，但暴露 3 个需要跟踪的产品/状态同步缺陷。

## 测试环境

- 日期：2026-06-26
- 前端：`http://localhost:5173`
- 后端：`http://localhost:3012`
- 浏览器：Chrome 插件真实浏览器
- 登录账号：`admin`
- 测试方式：真实页面操作 + 真实后端 API + PostgreSQL 状态核验
- 投标主体默认口径：河北泰昌电力器材科技有限公司

## 测试文件

```text
rag_seed/power_grid_resources/01_tender_documents/22_国网辽宁电力2025年第三次物资协议库存招标采购/extracted/电缆保护管CPVC/包1_完整招标文件_53488484541066181/国网辽宁电力2025年第三次物资协议库存招标采购招标文件.docx
```

## 关键对象

- 项目 ID：`4d632dbe-f6e6-4066-8fe2-929ecb54ba1d`
- 上传返回 fileId：`7ceb1a89-a2a5-4acc-9224-eb99ecc6e96a`
- 上传返回 supabaseFileId：`d66f75c0-3fb3-4429-bc5a-3cc88e97e304`
- 招标解读任务 ID：`607b9ea6-2f7d-4fef-a0b9-db2f0a600e63`
- 正文生成任务 ID：`86730fcc-4f4b-40e5-a5e5-2335889ee693`

## 页面流程记录

| 步骤 | 结果 | 证据 |
| --- | --- | --- |
| 登录本地系统 | 通过，进入首页 | `output/playwright/fullflow-after-login.png` |
| 上传真实招标文件 | 通过，`POST /api/bidding/upload` 返回 201 | `output/playwright/fullflow-after-upload.png` |
| 解析招标文件 | 通过，页面从 `supabase_synced` 自动恢复并进入解读 | 页面轮询 + DB `bid_analysis=1` |
| AI 招标解读 | 通过，分段 14/14 后融合完成 | `GET /ai-report-tasks/...` 全部 200 |
| 分册大纲生成 | 通过，进入投标确认页 | `GET /bid-outline/stream` 200 |
| 投标确认报告 | 手动点击刷新后通过，生成 35 个字段、9 个正式必填缺口 | `output/playwright/fullflow-prefill-refresh.png` |
| 应用确认并进入正文编辑 | 通过 | `output/playwright/fullflow-after-prefill-apply.png` |
| 一键编写全文 | 首轮 74/75 done，1 个 partial | `output/playwright/fullflow-after-click-generate-all.png` |
| 批量续写草稿 | 通过，唯一 partial 续写完成 | `output/playwright/fullflow-after-resume-partial-click.png` |
| 最终浏览器核验 | 通过，页面显示 `75/75`、任务已完成 | `output/playwright/fullflow-final-75-of-75.png` |

## 数据库核验

正文生成任务：

```text
status=completed
total_count=75
done_count=75
failed_count=0
stopped_count=0
started_at=2026-06-26 13:09:52+08
finished_at=2026-06-26 13:29:27+08
```

正文任务项：

```text
done: 75
```

章节正文：

```text
leaf_count=75
leaf_with_content=75
suspicious_leaf_content=0
sections_with_content=75
sections_total=102
total_chars=265322
```

页面最终统计：

```text
已生成正文小节 75/75
正文字数 272755
条款覆盖率 52%
待处理覆盖项 118
高风险待覆盖 48
```

页面与数据库总字数存在统计口径差异：页面按可见/编辑器口径估算，数据库按 `bid_sections.content` 字符长度统计。

## 发现缺陷

| 编号 | 优先级 | 现象 | 影响 | 证据 | 建议 |
| --- | --- | --- | --- | --- | --- |
| E2E-FLOW-001 | P1 | 项目 `bid_projects.status` 最终仍为 `uploaded`，首页最近任务仍显示“解析中” | 用户会误以为项目还在解析，历史记录/首页状态与真实进度不一致 | DB `bid_projects.status=uploaded`，页面最近任务显示“解析中” | 在解析、解读、大纲、正文任务完成后统一回写项目生命周期状态，例如 `interpreted/outline_ready/bid_writing/completed_draft` |
| E2E-FLOW-002 | P1 | 自动流程进入投标确认页时显示“当前项目暂无投标确认报告”，需要手动点击“刷新报告” | 从上传到正文编辑的自动流程中断，普通用户不知道下一步要刷新 | `output/playwright/fullflow-after-outline-wait.png`、刷新后才出现 35 字段报告 | 进入投标确认页时自动拉取/生成 prefill report；若为空，给出明确自动生成状态 |
| E2E-FLOW-003 | P1 | 一键编写全文首轮出现 1 个 `partial_generated`，原因 `MODEL_STREAM_IDLE_TIMEOUT`，需要手动“批量续写草稿” | “一键编写全文”不能完全无人值守完成；虽然可恢复，但需要用户理解 partial 语义 | 章节“（5）纳入严重违反失信企业名单（黑名单）信息”首轮 partial，续写后 done | 对 idle timeout 的 partial 增加一次安全自动续写，或在任务结束时明确弹出“还有 1 章待续写”并提供主按钮 |
| E2E-FLOW-004 | P2 | 控制台出现 Ant Design message context warning | 不影响流程，但会污染控制台和自动化监控 | `Warning: [antd: message] Static function can not consume context like dynamic theme.` | 后续将全局 `message` 静态调用迁移到 AntD `App` context |

## 质量观察

- 正文主流程已真实完成，75 个叶子章节均有正文。
- 正式检查仍显示待处理覆盖项和高风险待覆盖项，这属于正式投标前门禁问题，不影响“正文初稿已生成”的结论。
- 投标确认报告仍有报价、保证金、授权代表、税率等客户决策字段缺口；这些字段不得由模型自动编造。
- 本次没有新增资料入库、metadata 调整或召回策略变更，因此未跑 RAG 增量召回门禁。

## 后续处理建议

1. 先处理 P1 `E2E-FLOW-001` 项目状态同步，避免首页/历史记录误导客户。
2. 再处理 P1 `E2E-FLOW-002`，让上传自动流程进入投标确认页后无需手动刷新。
3. 对 P1 `E2E-FLOW-003` 做产品化收口：要么自动续写一次，要么显著提示并提供主按钮。

# API 接口参考

> 完整路由实现见 `backend/api/` 目录

## API 概览

主要接口前缀：

```text
/api/bidding/*
/api/knowledge/*
/api/outputs/*
/api/users/*
```

常用接口：

| 接口 | 说明 |
| --- | --- |
| `POST /api/bidding/upload` | 上传招标文件 |
| `GET /api/bidding/parse-status/<file_id>` | 查询解析状态 |
| `GET /api/bidding/interpretations/latest` | 获取最近的招标解读 |
| `GET /api/bidding/interpretations/<project_id>` | 获取项目解读 |
| `POST /api/bidding/interpretations/<project_id>/ai-report` | 生成 AI 深度解读 |
| `POST /api/bidding/interpretations/<project_id>/bid-outline` | 生成分册化章节大纲，返回 `volumes + chapters` |
| `GET /api/bidding/interpretations/<project_id>/bid-outline/stream` | SSE 流式生成分册化章节大纲 |
| `POST /api/bidding/interpretations/<project_id>/length-settings` | 保存全文篇幅设置，按技术标/商务标目标页数或字数刷新章节写作计划 |
| `POST /api/bidding/interpretations/<project_id>/semantic-compliance-check` | 对高风险、评分、未覆盖和待补强项执行 LLM 语义合规复核 |
| `POST /api/bidding/interpretations/<project_id>/sections/stream` | 流式生成章节正文 |
| `POST /api/bidding/interpretations/<project_id>/download-docx` | 创建 DOCX 导出任务；可传 `volumeType` 单独导出技术标或商务标 |
| `GET /api/bidding/interpretations/<project_id>/export-tasks/<task_id>` | 查询 DOCX 导出任务状态和下载地址 |
| `POST /api/knowledge/upload` | 上传知识库资料 |
| `POST /api/knowledge/search` | RAG 检索问答 |
| `POST /api/knowledge/search/stream` | SSE 流式 RAG 检索问答 |
| `POST /api/knowledge/followups` | 基于用户问题、回答、资料和图片资产生成模型追问建议 |
| `GET /api/knowledge/documents` | 查询知识库文档列表 |
| `PATCH /api/knowledge/assets/<asset_id>` | 编辑企业资信库和产品库资产，可只更新结构化信息，也可替换图片或附件 |

分册导出示例：

```json
{
  "volumeType": "technical",
  "withImages": true
}
```

不传 `volumeType` 时导出完整投标文件；传入 `technical` 时导出技术标；传入 `business` 时导出商务标，并自动包含内部的商务响应、资格文件、报价文件、附件材料和其他非技术章节。导出的 DOCX 文件名、文档标题和页眉保留中文项目名与分册名；正式正文会清理 emoji、图钉、告警图标等装饰性符号，只保留纯文字提醒。

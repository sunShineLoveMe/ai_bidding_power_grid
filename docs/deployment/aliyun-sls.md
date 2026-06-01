# 阿里云 SLS 日志采集与告警方案

> 适用阶段：阿里云测试环境基础版。  
> 当前代码状态：后端与 Celery worker 默认输出 JSON 日志，`docker-compose.yml` 已设置 `LOG_FORMAT=json`。本文先固化字段、采集路径、查询模板和告警口径；真实接入需等客户阿里云账号、SLS Project/Logstore 和 RAM 权限到位后执行。

## 目标

- 把 `backend`、`celery-worker`、`frontend/nginx` 的标准输出采集到 SLS。
- 通过结构化字段定位上传、解析、AI 调用、SSE、DOCX 导出、Celery worker 和健康检查问题。
- 测试环境先做少量高价值告警，不追求完整 APM。

## 采集路线

推荐测试环境使用 **Logtail / LoongCollector 采集 Docker 容器标准输出**：

1. 在 ECS 上安装并配置 SLS Logtail。
2. 为本项目单独创建 Project 和 Logstore，例如：
   - Project：`ai-bidding-test`
   - Logstore：`app-json`
3. 采集对象选择容器标准输出。
4. 采集范围至少包含以下容器：
   - `ai-bidding-backend`
   - `ai-bidding-celery-worker`
   - `ai-bidding-frontend`
   - 如 OnlyOffice 独立部署，也单独采集 OnlyOffice 容器日志。
5. 后端和 worker 必须保持：

```env
LOG_FORMAT=json
LOG_LEVEL=INFO
ACCESS_LOG_LEVEL=WARNING
```

说明：本项目 Python 服务日志写 stdout/stderr，不建议在容器内落本地日志文件再采集，避免容器重建后日志丢失和路径漂移。

## 字段索引

SLS 中建议开启全文索引，同时为下表字段创建字段索引；需要做 `count`、`avg`、`max`、`group by` 的字段开启统计。

| 字段 | 类型 | 开启统计 | 来源 | 用途 |
| --- | --- | --- | --- | --- |
| `timestamp` | text | 否 | JSON 日志 | 日志时间，SLS 自身也有采集时间 |
| `level` | text | 是 | JSON 日志 | `ERROR` / `WARNING` / `INFO` 过滤 |
| `logger` | text | 是 | JSON 日志 | 定位 Python logger |
| `module` | text | 是 | `http` / `celery` / 模块名 | 区分 HTTP、Celery、AI、导出等来源 |
| `stage` | text | 是 | `request` / `task` / AI stage | 过滤请求、任务和模型阶段 |
| `message` | text | 是 | 日志消息 | 关键事件名，例如 `http_request_completed` |
| `request_id` | text | 是 | HTTP 中间件 | 一次 HTTP 请求串联排查 |
| `project_id` | text | 是 | 业务上下文 | 单个投标项目排查 |
| `file_id` | text | 是 | 解析任务上下文 | 招标解析、知识库入库排查 |
| `task_id` | text | 是 | 业务任务 ID | DOCX 导出、章节生成任务排查 |
| `section_id` | text | 是 | 章节上下文 | 单章生成排查 |
| `user_id` | text | 是 | 登录/识别上下文 | 用户操作排查 |
| `celery_task_id` | text | 是 | Celery request id | worker 任务级排查 |
| `celery_task_name` | text | 是 | Celery task name | 统计任务类型 |
| `method` | text | 是 | HTTP 完成日志 | 请求方法 |
| `path` | text | 是 | HTTP 完成日志 | API 路径 |
| `status_code` | long | 是 | HTTP 完成日志 | HTTP 错误率统计 |
| `duration_ms` | long | 是 | HTTP/Celery 日志 | 慢请求、慢任务统计 |
| `remote_addr` | text | 否 | HTTP 完成日志 | 排查来源 IP，通常不作为告警条件 |
| `exception` | text | 是 | 异常日志 | 错误栈，已脱敏 |
| `parse_id` | text | 是 | 解析任务日志 | 与 `file_id` 互补 |
| `supabase_file_id` | text | 是 | 历史命名，实际为 bid file id | 招标文件记录排查 |
| `document_id` | text | 是 | 知识库任务日志 | 知识文档入库排查 |

字段说明：

- `task_id` 是业务任务 ID，例如 DOCX 导出任务表 `bid_export_tasks.id`。
- `celery_task_id` 是 Celery broker 层任务 ID。两者不要混用。
- 日志 formatter 会对 token、password、access key、数据库连接串等敏感内容做脱敏，但仍不应主动打印完整密钥或客户正文。

## 查询模板

以下查询以 SLS 标准查询分析写法表达，字段需已建立索引。

### 1. 按 request_id 串联一次请求

```sql
request_id: "req_20260531142558_80976339f6"
```

### 2. 最近 30 分钟 HTTP 5xx

```sql
module: http and status_code >= 500
| select date_trunc('minute', __time__) as minute, count(*) as errors
  group by minute
  order by minute desc
```

### 3. 慢请求 Top 20

```sql
module: http and duration_ms >= 3000
| select path, method, status_code, duration_ms, request_id
  order by duration_ms desc
  limit 20
```

### 4. 按项目排查所有日志

```sql
project_id: "替换为项目 UUID"
```

### 5. 解析链路失败

```sql
message: "parse" and (level: ERROR or parse_status: "mineru_failed" or parse_status: "mineru_download_failed" or parse_status: "index_failed")
```

### 6. Celery 任务失败

```sql
module: celery and message: "celery_task_failed"
| select celery_task_name, celery_task_id, project_id, file_id, task_id, exception
  order by __time__ desc
  limit 50
```

### 7. DOCX 导出失败

```sql
task_id: * and (message: "后台 DOCX 导出任务失败" or message: "写入 DOCX 导出任务失败状态失败")
```

### 8. AI 调用错误

```sql
(logger: "root" or logger: "backend.ai.qwen_client") and (message: "DashScope" or message: "DeepSeek") and level: ERROR
```

### 9. SSE 相关接口错误

```sql
module: http and (path: "/api/bidding/interpretations/*/bid-outline/stream" or path: "/api/bidding/interpretations/*/sections/stream") and status_code >= 400
```

### 10. P1-7 冒烟脚本失败后定位

先拿脚本输出的失败步骤，再按对应条件查：

| 脚本失败步骤 | 优先查询 |
| --- | --- |
| `upload_tender` | `path: "/api/bidding/upload"` |
| `wait_parse_completed` | `file_id: "脚本输出 fileId"` |
| `generate_ai_report` | `project_id: "脚本输出 projectId" and message: "ai_interpretation"` |
| `generate_outline` | `project_id: "脚本输出 projectId" and path: "/api/bidding/interpretations/*/bid-outline/stream"` |
| `generate_one_section` | `project_id: "脚本输出 projectId" and path: "/api/bidding/interpretations/*/sections/stream"` |
| `wait_docx_export` | `task_id: "脚本输出 taskId"` |

## 告警规则基础版

测试环境建议先配 6 条，避免告警噪声过大。

| 告警 | 查询条件 | 建议阈值 | 处理人 | 说明 |
| --- | --- | --- | --- | --- |
| HTTP 5xx 突增 | `module: http and status_code >= 500` | 5 分钟内 >= 3 次 | 后端/实施 | 第一优先级 |
| `/api/ready` 失败 | `path: "/api/ready" and status_code: 503` | 5 分钟内 >= 1 次 | 实施 | DB/Redis/存储/模型配置异常 |
| Celery 任务失败 | `module: celery and message: "celery_task_failed"` | 10 分钟内 >= 1 次 | 后端 | 解析、导出、大纲精炼任务失败 |
| DOCX 导出失败 | `message: "后台 DOCX 导出任务失败"` | 10 分钟内 >= 1 次 | 后端 | 客户可见交付物失败 |
| 慢请求 | `module: http and duration_ms >= 30000` | 10 分钟内 >= 3 次 | 后端 | 重点看 SSE、AI 和导出状态查询 |
| worker 无任务完成日志 | `module: celery and message: "celery_task_completed"` | 30 分钟内为 0 且业务有上传/导出 | 实施 | 需要结合业务时间段判断，防止误报 |

通知渠道测试期建议先用钉钉/企业微信机器人或邮件，告警内容至少包含：

- 环境名
- 告警名称
- 查询时间窗口
- 触发数量
- 示例 `request_id` / `project_id` / `file_id` / `task_id`
- SLS 查询链接

## 上线检查

云上测试环境部署完成后逐项确认：

- [ ] `backend` 容器 stdout 中每行 Python 应用日志是 JSON。
- [ ] `celery-worker` 容器 stdout 中可以看到 `celery_task_started` / `celery_task_completed`。
- [ ] SLS Logstore 能看到 `module=http` 的 `http_request_completed`。
- [ ] 调用 `/api/ready` 后能用 `path: "/api/ready"` 查到日志。
- [ ] 跑 `scripts/smoke_key_flow.py` 后能用 `project_id` 查到上传、解析、AI、大纲、章节、DOCX 日志。
- [ ] 人为触发一次非法上传，SLS 中能查到 `status_code=400`，且无密钥泄漏。
- [ ] 告警规则已创建并完成一次手动触发验证。

## 暂不做的事

- 不在测试环境强行引入 OpenTelemetry / APM。
- 不采集完整客户文档正文、Prompt 全文、模型响应全文。
- 不把 SLS 作为业务状态源；业务状态仍以 PostgreSQL 表为准。

## 参考

- 阿里云 SLS 查询语法：<https://help.aliyun.com/zh/sls/query-syntax/>
- 阿里云 SLS Docker 容器标准输出采集：<https://help.aliyun.com/zh/sls/user-guide/collect-docker-container-standard-output>

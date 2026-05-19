# 安全配置指南

> 快速开始见 [quickstart.md](./quickstart.md)

安全相关说明：

- CORS 不再默认开放所有来源，后端读取 `APP_CORS_ORIGINS` 作为白名单；生产环境禁止配置为 `*`。
- `APP_LOCAL_ONLY=true` 时只允许本机或内网地址访问，适合单机试用和内网部署。
- `APP_AUTH_ENABLED=true` 时接口要求 `X-App-Auth-Token` 或 `Authorization: Bearer <token>`，生产环境应配置足够长度的 `APP_AUTH_TOKEN`。
- `APP_ENV=production` 或 `REQUIRE_STRICT_CONFIG=true` 时会启动严格配置校验，缺少 DeepSeek/DashScope、Supabase service role、OnlyOffice JWT 或使用弱占位值会直接拒绝启动。
- 500 错误默认返回通用提示，详细异常只写入后端日志；开发调试需要临时查看详细错误时，可在非生产环境设置 `APP_EXPOSE_DEBUG_ERRORS=true`。
- 上传入口已增加扩展名和 MIME 校验，允许类型可通过 `ALLOWED_TENDER_EXTENSIONS`、`ALLOWED_KNOWLEDGE_EXTENSIONS`、`ALLOWED_ASSET_EXTENSIONS` 调整。

#### 实施人员安全配置指南

实施部署时优先根据实际场景选择配置模板。不要直接照抄生产配置，尤其不要使用示例密钥、弱口令或 `*` 跨域。

| 场景 | 推荐配置 | 说明 |
| --- | --- | --- |
| 本机开发 / 演示 | `APP_ENV=development`、`APP_AUTH_ENABLED=false`、`APP_LOCAL_ONLY=false`、`REQUIRE_STRICT_CONFIG=false` | 不需要访问令牌，不影响前端开发和本机调试。 |
| 单机部署，只在本机浏览器使用 | `APP_ENV=development`、`APP_LOCAL_ONLY=true`、`APP_AUTH_ENABLED=false` | 只允许本机或内网地址访问，适合客户电脑单机试用。 |
| 企业内网多人使用 | `APP_ENV=production`、`APP_LOCAL_ONLY=true`、`APP_AUTH_ENABLED=true`、配置 `APP_AUTH_TOKEN` | 建议开启访问令牌，避免内网任意人员直接访问上传、生成、设置和下载接口。 |
| 公网或云服务器部署 | `APP_ENV=production`、`REQUIRE_STRICT_CONFIG=true`、`APP_AUTH_ENABLED=true`、配置明确 `APP_CORS_ORIGINS` | 必须配置前端域名白名单、强访问令牌和真实密钥；不要使用 `*`。 |

常用安全参数说明：

| 参数 | 是否必填 | 推荐值 | 作用 | 填错后的表现 |
| --- | --- | --- | --- | --- |
| `APP_ENV` | 建议填写 | 本地填 `development`，生产填 `production` | 决定是否按生产环境执行严格安全校验 | 生产环境误填 `development` 会降低启动校验强度 |
| `REQUIRE_STRICT_CONFIG` | 生产建议 `true` | `false` / `true` | 即使 `APP_ENV` 不是 production，也强制检查关键密钥 | 设为 `true` 后，示例密钥或弱密钥会导致后端拒绝启动 |
| `APP_CORS_ORIGINS` | 必填 | `http://客户前端域名,https://客户前端域名` | 允许哪些前端地址访问后端 API | 前端域名未加入时，浏览器会出现跨域请求失败 |
| `APP_LOCAL_ONLY` | 可选 | 单机/内网填 `true`，公网填 `false` | 限制只允许本机或内网访问 | 公网部署误填 `true` 可能导致外部用户访问失败 |
| `APP_AUTH_ENABLED` | 可选 | 内网多人/公网建议 `true` | 开启简单访问令牌保护 | 开启后前端或调用方未带令牌会返回 401 |
| `APP_AUTH_TOKEN` | 开启认证时必填 | 至少 24 位随机字符串 | API 访问令牌 | 为空、太短或使用示例值时，生产严格模式会拒绝启动 |
| `APP_EXPOSE_DEBUG_ERRORS` | 本地临时可开 | 默认 `false` | 是否把详细后端异常返回给前端 | 生产不要开启，否则可能暴露路径、SQL 或外部服务响应 |
| `MAX_UPLOAD_MB` | 必填 | `200` 或按客户要求调整 | 控制单个上传文件最大体积 | 上传超过限制会返回 413 |
| `ALLOWED_TENDER_EXTENSIONS` | 必填 | `pdf,doc,docx,txt,md` | 控制招标文件允许上传的后缀 | 不在列表内会被拒绝上传 |
| `ALLOWED_KNOWLEDGE_EXTENSIONS` | 必填 | `pdf,doc,docx,txt,md,xls,xlsx,csv,png,jpg,jpeg,webp` | 控制知识库文件允许上传的后缀 | 不在列表内会被拒绝上传 |
| `ALLOWED_ASSET_EXTENSIONS` | 必填 | `png,jpg,jpeg,webp,pdf,doc,docx` | 控制资信库/产品库资产允许上传的后缀 | 不在列表内会被拒绝上传 |
| `DOCX_MAX_IMAGES` | 可选 | `24` | Word 转换阶段整份文档允许插入的 Markdown 图片上限 | 超出后跳过并记录导出任务图片报告 |
| `DOCX_TOTAL_ASSET_IMAGE_LIMIT` | 可选 | `36` | 自动从资信库/产品库插入标书的图片资产总上限 | 避免图文并茂导出图片过多导致 Word 过大或排版失控 |
| `DOCX_TOC_MAX_LEVEL` | 可选 | `4` | Word 正式目录最多展示到第几级标题 | 只影响目录页展示层级，不改变正文标题层级 |
| `DOCX_ALLOW_REMOTE_IMAGES` | 可选 | `false` | 是否允许 DOCX 导出下载外部 HTTP/HTTPS 图片 | 默认关闭；开启后仍会拦截 localhost、内网、回环和非公网地址 |
| `DOCX_REFRESH_FIELDS` | 可选 | `true` | 导出 DOCX 后是否调用 LibreOffice headless 刷新目录页码、页脚页码和总页数 | 未安装 LibreOffice 时不会阻断导出，但下载后页码可能需 Word 打开时刷新 |
| `SOFFICE_BIN` | 推荐填写 | Mac M1/M2 常见 `/opt/homebrew/bin/soffice`，Linux 常见 `/usr/bin/soffice` | LibreOffice 命令行程序路径 | 路径错误会跳过服务端页码刷新，导出任务 metadata 会记录失败原因 |
| `DOCX_REFRESH_TIMEOUT_SECONDS` | 可选 | `180` | LibreOffice 单次刷新 DOCX 的超时时间 | 过短可能导致大文档刷新失败，过长会拉长导出等待 |
| `ONLYOFFICE_JWT_SECRET` | 使用 OnlyOffice 时必填 | 至少 24 位随机字符串 | OnlyOffice 文档编辑鉴权密钥 | 未配置时无法生成 OnlyOffice 编辑配置 |
| `AI_PROVIDER` | 必填 | `deepseek` | 文本生成供应商；标书写作默认使用 DeepSeek | 填错后会走错误的模型调用协议 |
| `DEEPSEEK_API_KEY` | DeepSeek 写作必填 | 客户 DeepSeek API Key | 标书解读、大纲、正文和知识库问答的文本生成鉴权 | 缺失时写作模型调用直接失败 |
| `DEEPSEEK_BASE_URL` | DeepSeek 写作必填 | `https://api.deepseek.com` | OpenAI-compatible Base URL | 填错会导致连接失败或 404 |
| `DEEPSEEK_MODEL` | DeepSeek 写作必填 | `deepseek-v4-flash` | 标书写作模型 | 填错会出现模型不存在或无权限 |
| `DEEPSEEK_KNOWLEDGE_MODEL` | DeepSeek 写作必填 | `deepseek-v4-flash` | 知识库问答文本模型 | 填错会影响知识库助手回答 |
| `DASHSCOPE_API_KEY` | 必填 | 客户 DashScope API Key | 当前知识库向量化和 Rerank 默认仍依赖 DashScope | 缺失时知识库入库、检索增强或重排失败 |
| `DASHSCOPE_REQUEST_TIMEOUT_SECONDS` | 必填 | `120` | 普通文本模型请求超时时间 | 过短会导致长章节生成中断，过长会拉长失败等待 |
| `DASHSCOPE_STREAM_CONNECT_TIMEOUT_SECONDS` | 必填 | `15` | 流式生成连接建立超时 | 网络慢时可适当调大 |
| `DASHSCOPE_STREAM_READ_TIMEOUT_SECONDS` | 必填 | `180` | 流式生成读取超时 | 长章节生成或客户网络不稳定时可调大 |
| `DASHSCOPE_MAX_RETRIES` | 必填 | `2` | 模型调用失败后的最大重试次数，不含首次请求 | 设置过高会增加等待时间和重复调用风险 |
| `DASHSCOPE_RETRY_BASE_DELAY_SECONDS` | 必填 | `1.5` | 第一次重试前等待秒数 | 数值越小恢复越快，但限流场景容易继续失败 |
| `DASHSCOPE_RETRY_MAX_DELAY_SECONDS` | 必填 | `12` | 指数退避最大等待秒数 | 控制重试最长等待时间 |
| `DASHSCOPE_RETRY_STATUS_CODES` | 必填 | `429,500,502,503,504` | 哪些模型服务状态码允许自动重试 | 不建议把 400、401、403 加入，配置或权限错误不应重试 |
| `MINERU_DOWNLOAD_AUTO_RETRIES` | 可选 | `6` | parse-status 查询时自动重试 MinerU 结果 zip 下载的最大次数 | 仅对 MinerU 已完成但结果下载失败的任务生效 |
| `MINERU_DOWNLOAD_RETRY_STALE_SECONDS` | 可选 | `120` | 判断下载重试任务是否卡住的秒数 | 超时后允许下一次查询重新触发下载重试 |
| `MINERU_DOWNLOAD_RESUME` | 可选 | `true` | MinerU 结果 zip 下载失败后是否保留 `.part` 并断点续传 | 建议开启，适合客户网络不稳定或 CDN 连接中断场景 |
| `MINERU_DOWNLOAD_KEEP_PARTIAL` | 可选 | `true` | 下载失败时是否保留临时分片文件 | 关闭后每次失败都会删除临时文件，下次只能完整重下 |

访问令牌开启后的调用方式：

```http
X-App-Auth-Token: 这里填写 APP_AUTH_TOKEN
```

也支持标准 Bearer 形式：

```http
Authorization: Bearer 这里填写 APP_AUTH_TOKEN
```

实施配置示例：

```ini
# 企业内网多人使用示例
APP_ENV=production
REQUIRE_STRICT_CONFIG=true
APP_CORS_ORIGINS=http://192.168.1.20:3012,http://192.168.1.20:5173
APP_LOCAL_ONLY=true
APP_AUTH_ENABLED=true
APP_AUTH_TOKEN=replace_with_random_32_chars_or_longer
APP_EXPOSE_DEBUG_ERRORS=false
MAX_UPLOAD_MB=200
ALLOWED_TENDER_EXTENSIONS=pdf,doc,docx,txt,md
ALLOWED_KNOWLEDGE_EXTENSIONS=pdf,doc,docx,txt,md,xls,xlsx,csv,png,jpg,jpeg,webp
ALLOWED_ASSET_EXTENSIONS=png,jpg,jpeg,webp,pdf,doc,docx
ONLYOFFICE_JWT_SECRET=replace_with_random_32_chars_or_longer
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_KNOWLEDGE_MODEL=deepseek-v4-flash
DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_MAX_RETRIES=2
DASHSCOPE_RETRY_BASE_DELAY_SECONDS=1.5
DASHSCOPE_RETRY_MAX_DELAY_SECONDS=12
DASHSCOPE_RETRY_STATUS_CODES=429,500,502,503,504
DOCX_REFRESH_FIELDS=true
SOFFICE_BIN=/opt/homebrew/bin/soffice
DOCX_REFRESH_TIMEOUT_SECONDS=180
```

配置完成后的检查方法：

```bash
python main.py
```

启动失败时优先检查后端日志。常见原因包括：

- `APP_CORS_ORIGINS` 在生产环境配置了 `*`。
- `APP_AUTH_ENABLED=true` 但没有配置 `APP_AUTH_TOKEN`。
- `APP_ENV=production` 或 `REQUIRE_STRICT_CONFIG=true` 时仍使用 `.env.example` 中的占位密钥。
- `ONLYOFFICE_JWT_SECRET` 太短或仍是示例值。
- 前端访问地址没有加入 `APP_CORS_ORIGINS`。

企业画像会参与招标解读、章节大纲、章节正文和旧版标书流程的 Prompt 组装。开源或更换企业使用时，建议先在系统设置中维护企业名称、行业定位、业务范围、核心能力、目标客户和 AI 写作约束，避免生成内容带有固定企业信息。

## 安全与开源注意事项

请不要提交以下内容：

- `.env`
- Supabase service role key
- LLM API key
- MinerU token
- ONLYOFFICE JWT secret
- 客户真实招标文件、资质文件、报价文件
- `uploads/`、`outputs/`、`parsed_outputs/` 中的业务文件
- 本地数据库、向量库、缓存和日志

建议在开源仓库中提供：

- `.env.example`
- 脱敏的演示数据
- 可公开下载的种子资料脚本
- 最小可运行 SQL
- Docker Compose 示例
- API 文档或 OpenAPI 文件

# Task Plan: Token 用量与成本统计

## Goal
将 AI/OCR 用量统计升级为独立一级菜单，用于按标书项目评估单次生成流程消耗了多少 token、使用了哪些模型、调用是否成功，以及人民币预估成本。

## Scope
- DashScope 原生文本生成调用用量采集。
- DashScope 流式章节生成用量采集，无法获取 usage 时按字符数估算并标记。
- OpenAI 兼容 Embedding 调用用量采集。
- DashScope Rerank 调用用量采集。
- 一级菜单「用量与成本」展示近 30 天调用次数、输入 token、输出 token、人民币预估费用、项目筛选、模型类型拆分和最近调用明细。

## Phases
- [x] Phase 1: 查询模型厂商官方 usage 字段和计费口径
- [x] Phase 2: 提供 Supabase SQL 表、视图和 RPC
- [x] Phase 3: 后端增加统一 AI 用量落库函数和成本估算
- [x] Phase 4: 接入 Qwen 文本生成、流式生成、Embedding、Rerank
- [x] Phase 5: 增加 `/api/bidding/settings/ai-usage` 查询接口
- [x] Phase 6: 设置页新增“用量与成本”Tab
- [x] Phase 7: 后端编译、前端构建和接口探测验证
- [x] Phase 8: 将“用量与成本”升级为一级菜单，移出设置页，补充项目筛选、模型类型拆分和 CNY 展示

## Files Changed
- `sql/20260507_create_ai_usage_tracking.sql`
- `backend/db/supabase_repo.py`
- `backend/ai/qwen_client.py`
- `backend/ai/section_writer.py`
- `backend/ai/chapter_planner.py`
- `backend/ai/interpreter.py`
- `backend/ai/rerank_client.py`
- `backend/rag/vector_store.py`
- `backend/api/routes.py`
- `frontend/src/pages/Settings/index.tsx`
- `frontend/src/pages/UsageCost/index.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/layout/AppLayout.tsx`
- `sql/20260507_update_ai_usage_pricing_cny.sql`

## Verification
```bash
python -m py_compile backend/db/supabase_repo.py backend/ai/qwen_client.py backend/rag/vector_store.py backend/ai/rerank_client.py backend/ai/section_writer.py backend/ai/chapter_planner.py backend/ai/interpreter.py backend/api/routes.py
npm run build
curl -s -o /tmp/ai_usage_summary.json -w "%{http_code}\n" "http://127.0.0.1:3012/api/bidding/ai-usage?days=30"
```

验证结果：
- 后端编译通过。
- 前端构建通过，仍有既有 chunk size warning。
- 用量统计接口返回 `200`。

## Notes
- 费用为预估值，最终以模型厂商账单为准。
- 当前已覆盖主要 AI 调用链路；MinerU/OCR 价格已在 SQL 中预留页数统计和手工价格配置，后续可接解析链路。
- 成本中心统一按人民币 CNY 展示。若历史 SQL 已写入 USD 口径价格或日志，执行 `sql/20260507_update_ai_usage_pricing_cny.sql` 转为人民币口径。
- 若 DashScope 原生流式接口未返回 usage，系统会按输入/输出字符数估算 token，并标记 `usage_estimated=true`。

## Status
**Complete** - Token 用量与成本统计已升级为独立一级菜单和人民币成本中心。

---

# Task Plan: P0 开源与安全最小闭环

## Goal
补齐单机版/私有化部署前的最低安全基线，降低配置泄露、跨域误开放、上传异常文件、错误详情暴露和弱密钥风险。

## Scope
- `.env.example` 完整化。
- CORS 白名单环境变量化。
- 生产环境启动配置校验。
- 本地访问保护和可选访问令牌。
- 500 错误响应脱敏。
- 上传文件扩展名、MIME 和大小限制。
- 调试 `print` 收敛为 logging。

## Phases
- [x] Phase 1: 新增集中安全工具模块 `backend/core/security.py`
- [x] Phase 2: Flask 启动接入 CORS 白名单、访问保护、生产配置校验和错误脱敏
- [x] Phase 3: 招标文件、MinerU zip、知识库文件、资信/产品资产上传接入文件校验
- [x] Phase 4: 移除默认 ONLYOFFICE 弱密钥，改为环境变量必填校验
- [x] Phase 5: 补全 `.env.example` 安全、模型、Supabase、MinerU、OnlyOffice、上传和路径配置
- [x] Phase 6: 清理核心运行链路调试 print，改为 logging
- [x] Phase 7: README 路线图同步完成状态

## Files Changed
- `backend/core/security.py`
- `main.py`
- `backend/api/routes.py`
- `backend/api/users.py`
- `backend/ai/qwen_client.py`
- `backend/export/md_to_word.py`
- `.env.example`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m py_compile main.py backend/core/security.py backend/api/routes.py backend/api/users.py backend/ai/qwen_client.py backend/export/md_to_word.py
python -c "import main; print(main.app.test_client().get('/api/health').json)"
python -c "from io import BytesIO; import main; c=main.app.test_client(); r=c.post('/api/bidding/upload', data={'userId':'1','file':(BytesIO(b'x'),'bad.exe')}, content_type='multipart/form-data'); print(r.status_code, r.json)"
```

验证结果：
- 后端编译通过。
- Flask test client 健康检查返回 `{'status': 'ok'}`。
- 非法上传 `.exe` 被拦截并返回 `400`。

## Notes
- `APP_AUTH_ENABLED=false` 时不影响现有本机开发流程；生产或客户环境可开启 `APP_AUTH_ENABLED=true` 并配置 `APP_AUTH_TOKEN`。
- `APP_ENV=production` 或 `REQUIRE_STRICT_CONFIG=true` 会启用严格配置校验，弱密钥和占位密钥会导致启动失败。
- 目前未执行“开源前移除真实业务文件、生成文件、解析产物、缓存、日志和本地运行配置”，该项需要在正式开源/交付前单独清理工作区。

## Status
**Complete** - P0 安全与部署最小闭环已完成，正式开源/交付前仍需单独清理本地真实业务文件和生成产物。

---

# Task Plan: P1.1 DashScope/Qwen 调用稳定性增强

## Goal
降低标书解读、章节正文生成、RAG 问答等模型调用在限流、网络抖动和临时服务异常下的失败率，并让失败原因和重试情况可追踪。

## Scope
- DashScope 普通文本生成增加自动重试。
- DashScope 流式生成增加连接前/首包前重试，已输出正文后不自动重试，避免重复内容。
- 支持指数退避、最大重试次数、重试状态码和超时时间配置。
- 限流和临时服务不可用返回更明确的用户级错误。
- AI 用量日志 metadata 记录 attempts、retry_attempts、max_retries、retryable、final_success。
- README 和 `.env.example` 同步实施配置说明。

## Phases
- [x] Phase 1: 抽取 DashScope 重试、退避、状态码判断和公开错误提示工具函数
- [x] Phase 2: 非流式文本生成接入重试与最终一次用量落库
- [x] Phase 3: 流式生成接入安全重试策略，避免已输出正文后重复重试
- [x] Phase 4: 增加 `.env.example` 和 runtime settings 默认配置
- [x] Phase 5: README 路线图和实施配置说明同步

## Files Changed
- `backend/ai/qwen_client.py`
- `backend/core/config.py`
- `.env.example`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m py_compile backend/ai/qwen_client.py backend/core/config.py
```

验证结果：
- 后端编译通过。
- 本地 monkeypatch 验证：第一次返回 429 后自动等待并重试，第二次成功返回，usage metadata 记录 `attempts=2`、`retry_attempts=1`。

## Notes
- 默认 `DASHSCOPE_MAX_RETRIES=2`，即首次请求失败后最多再试 2 次。
- 默认重试状态码为 `429,500,502,503,504`；认证、参数错误等非临时错误不重试。
- 流式生成如果已经向前端输出正文片段，后续异常不自动重试，避免重复拼接正文。

## Status
**Complete** - DashScope/Qwen 主调用已完成重试、指数退避、限流提示和可配置超时接入。

---

# Task Plan: P1.2 Supabase 写入幂等设计

## Goal
降低章节编辑、批量排序、批量生成状态更新和知识库入库在重复点击、网络重试、刷新页面或前端临时 ID 失效时造成的数据重复、外键错误和状态错乱。

## Scope
- 章节保存：支持有效 UUID 复用；更新找不到行时按同 ID 新建；无 ID 时按项目、标题、排序、层级和父级匹配已有章节后更新。
- 章节父子关系：保存和排序前校验 `parent_id` 是否属于当前项目，不存在时降级为空，避免外键报错。
- 批量排序：保留原有正文和元数据，仅更新父级、顺序和层级，并增加 Supabase 写入重试。
- 批量生成状态重置：增加 Supabase upsert 重试，避免瞬时失败。
- 章节正文保存：继续保留按标题找回和重建的降级策略。
- 知识库文档：相同 bucket/object_path 重复入库时复用原 document，并清理旧 chunk 后重新写入。
- 知识库 chunk：批量写入增加重试；失败时抛出明确异常。
- 资信/产品资产：相同 storage_bucket/storage_path 重复保存时更新已有资产。
- 数据库辅助：新增可选 SQL，为知识库文档、chunk 和资产补充防重复 unique index。

## Phases
- [x] Phase 1: 增加 Supabase 写入重试和章节父级校验工具函数
- [x] Phase 2: 改造 `upsert_bid_section`，支持重复保存复用和失效 ID 降级创建
- [x] Phase 3: 改造 `reorder_bid_sections` 和 `reset_bid_sections_generation`，避免无效 parent_id 和瞬时写入失败
- [x] Phase 4: 改造知识库文档和 chunk 入库，重复解析时先清理旧分片
- [x] Phase 5: 改造知识资产保存，按 bucket/object_path 更新已有资产
- [x] Phase 6: 增加 `sql/20260508_supabase_idempotency_indexes.sql`
- [x] Phase 7: README 路线图和 SQL 说明同步

## Files Changed
- `backend/db/supabase_repo.py`
- `backend/rag/ingestion.py`
- `sql/20260508_supabase_idempotency_indexes.sql`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m py_compile backend/db/supabase_repo.py backend/rag/ingestion.py
```

验证结果：
- 后端编译通过。

## Notes
- `20260508_supabase_idempotency_indexes.sql` 是数据库防重增强脚本；历史库如果已有重复记录，需先备份并清理后再执行；资信/产品资产使用 `storage_bucket/storage_path` 字段。
- 章节排序遇到已删除父章节时会自动把该章节提升为根节点，不再直接触发 `bid_sections_parent_id_fkey`。
- 知识库重复解析同一对象路径会复用原文档 ID，清理旧分片后重新写入，避免智能检索重复召回。

## Status
**Complete** - Supabase 写入幂等设计第一版已完成，覆盖章节保存/排序/生成状态重置、知识库文档/chunk 入库和知识资产保存。

---

# Task Plan: P1.3 批量章节生成后端任务态

## Goal
把“一键编写全文”的批量章节生成进度从纯前端内存态逐步迁移到后端任务态，降低刷新页面、离开编辑页、网络抖动后任务状态丢失的问题。

## Scope
- 新增 `bid_generation_tasks` 表，记录整批任务、分册范围、是否图文并茂、总数和各状态计数。
- 每个任务的 `items` JSONB 保存章节 ID、标题、状态、进度、字数、错误和开始/结束时间。
- 后端新增创建任务、查询最近任务、更新单章任务状态、取消任务接口。
- 前端“一键编写全文”开始前创建后端任务。
- 前端每章运行、完成、失败、停止时同步任务状态；运行中进度按 5 秒节流写入。
- 页面加载或项目重载后读取最近一次任务，并恢复目录行内进度标识。
- README 同步 SQL 和路线图完成状态。

## Phases
- [x] Phase 1: 增加 `sql/20260508_create_bid_generation_tasks.sql`
- [x] Phase 2: 后端 Supabase repo 增加批量任务创建、查询、更新、取消函数
- [x] Phase 3: 后端 API 增加批量章节生成任务接口
- [x] Phase 4: 前端 API 增加任务态调用封装
- [x] Phase 5: BidEditor 批量生成接入任务创建、状态同步和刷新恢复
- [x] Phase 6: README 和任务清单同步

## Files Changed
- `sql/20260508_create_bid_generation_tasks.sql`
- `backend/db/supabase_repo.py`
- `backend/api/routes.py`
- `frontend/src/api/bidProject.ts`
- `frontend/src/pages/BidEditor/index.tsx`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m py_compile backend/db/supabase_repo.py backend/api/routes.py
npm run build
```

验证结果：
- 后端编译通过。
- 前端构建通过，仍有既有 chunk size warning。

## Notes
- 这是“逐步迁移”的第一版：后端已经持久化整批任务和每章状态，实际正文流式生成仍由前端发起，避免一次性改成后端队列导致风险过大。
- 用户刷新页面后，可以恢复最近一次批量生成任务的章节状态；继续未完成章节仍使用现有“一键编写全文”入口筛选未生成章节。
- 正式使用前需要在 Supabase 执行 `sql/20260508_create_bid_generation_tasks.sql`。

## Status
**Complete** - 批量章节生成后端任务态第一版已完成，支持任务创建、单章状态同步、取消任务和刷新后恢复最近任务进度。

---

# Task Plan: P1.4 章节生成失败保稿保护

## Goal
确保单章重写、批量章节生成或模型流式异常时，不会误清空用户已经编辑过的正文，也不会覆盖上一版成功生成的正文。

## Scope
- 后端章节正文保存函数支持 `preserve_existing_content`，失败状态只更新状态和错误 metadata。
- 流式章节生成异常时不再调用空正文覆盖数据库，只记录 `writing_error`。
- 前端单章生成开始时保留原正文快照，失败后恢复快照。
- 前端批量生成每章开始时保留原正文快照，失败后恢复快照。
- 批量任务状态继续记录失败原因，但提示“已保留原正文”。
- README 路线图同步完成状态。

## Phases
- [x] Phase 1: 排查所有生成失败清空正文路径
- [x] Phase 2: 后端 `update_bid_section_content` 增加失败保稿参数和 metadata patch
- [x] Phase 3: 后端流式生成异常只更新失败状态，不覆盖正文
- [x] Phase 4: 前端单章生成失败恢复原正文
- [x] Phase 5: 前端批量章节生成失败恢复原正文并同步任务错误
- [x] Phase 6: README 和任务清单同步

## Files Changed
- `backend/db/supabase_repo.py`
- `backend/api/routes.py`
- `frontend/src/pages/BidEditor/index.tsx`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m py_compile backend/db/supabase_repo.py backend/api/routes.py
npm run build
```

验证结果：
- 后端编译通过。
- 前端构建通过，仍有既有 chunk size warning。

## Notes
- 生成开始时前端仍会展示新流式正文，但失败后会恢复生成前正文快照。
- 后端失败状态使用 `preserve_existing_content=True`，数据库正文不会被空字符串覆盖。
- 若章节 ID 已失效并需要降级重建，失败状态下会优先使用请求中的原正文内容。

## Status
**Complete** - 章节生成失败保稿保护已完成，单章和批量生成失败均不会清空已有正文。

---

# Task Plan: P1.5 DOCX 导出任务化

## Goal
将全书、分册和单章 DOCX 导出从长时间同步 HTTP 请求改为后端任务，避免长文档、图文并茂导出时请求超时、重复点击和用户无进度反馈。

## Scope
- 新增 `bid_export_tasks` 表，记录导出范围、状态、进度、文件名、下载地址和错误信息。
- `/download-docx` 改为创建导出任务并启动后台线程。
- 后端后台执行 Markdown 组装和 DOCX 转换，持续更新任务状态。
- 新增导出任务查询接口，前端轮询任务进度。
- 前端下载按钮改为创建任务、显示进度、成功后自动打开下载链接。
- 支持全书导出、分册导出和单章导出。
- README 和任务清单同步。

## Phases
- [x] Phase 1: 增加 `sql/20260508_create_bid_export_tasks.sql`
- [x] Phase 2: Supabase repo 增加导出任务创建、查询和更新函数
- [x] Phase 3: 后端 `/download-docx` 改为任务化并增加后台执行函数
- [x] Phase 4: 后端新增导出任务查询接口
- [x] Phase 5: 前端 API 增加导出任务类型和查询函数
- [x] Phase 6: BidEditor 下载流程改为创建任务并轮询状态
- [x] Phase 7: README 和任务清单同步

## Files Changed
- `sql/20260508_create_bid_export_tasks.sql`
- `backend/db/supabase_repo.py`
- `backend/api/routes.py`
- `frontend/src/api/bidProject.ts`
- `frontend/src/pages/BidEditor/index.tsx`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m py_compile backend/db/supabase_repo.py backend/api/routes.py
npm run build
```

验证结果：
- 后端编译通过。
- 前端构建通过，仍有既有 chunk size warning。

## Notes
- 正式使用前需要在 Supabase 执行 `sql/20260508_create_bid_export_tasks.sql`。
- 任务化后 `/download-docx` 返回的是任务 ID，不再同步等待 DOCX 生成完成。
- 后端使用后台线程执行导出；单进程本地/私有化 MVP 足够使用。后续如部署多实例，应升级为持久化队列或任务 worker。

## Status
**Complete** - DOCX 导出任务化第一版已完成，支持全书、分册和单章后台导出，前端轮询进度并在成功后打开下载链接。

---

# Task Plan: 企业资产编辑闭环

## Goal
将企业产品库和企业资信库中的“编辑/更新”占位按钮改为真实可用的资产维护能力，支持用户在已上传资料基础上修改检索属性和可选替换附件。

## Scope
- 统一产品库和资信库列表操作按钮名称为“编辑”。
- 编辑时回填标题、分类、说明、标签、适用章节、允许自动插入、证照编号/发证机构或产品型号等字段。
- 保存时支持只更新结构化信息，不强制重新上传文件。
- 保存时支持可选替换图片、PDF、Word 等附件。
- 后端新增知识资产 PATCH 更新接口，更新 `knowledge_assets` 结构化字段、检索文本和 embedding。
- README 和任务清单同步。

## Phases
- [x] Phase 1: 后端增加 `update_knowledge_asset` 数据库更新函数
- [x] Phase 2: 后端新增 `PATCH /api/knowledge/assets/<asset_id>` 资产编辑接口
- [x] Phase 3: 抽取上传和编辑共用的资产 payload、检索文本和 embedding 生成逻辑
- [x] Phase 4: 产品库编辑弹窗回填和保存接入真实接口
- [x] Phase 5: 资信库编辑弹窗回填和保存接入真实接口
- [x] Phase 6: README 和任务清单同步

## Files Changed
- `backend/db/supabase_repo.py`
- `backend/api/routes.py`
- `frontend/src/pages/ProductBase/index.tsx`
- `frontend/src/pages/QualificationBase/index.tsx`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m py_compile backend/api/routes.py backend/db/supabase_repo.py
npm run build
```

验证结果：
- 后端编译通过。
- 前端构建通过，仍有既有 chunk size warning。
- 前端占位提示已清理，资信库仅保留“临期提醒待接入到期字段”这一非编辑功能提示。

## Notes
- 本任务不需要新增 SQL。
- 替换附件时会写入新的存储路径和缩略图信息；旧文件清理未纳入本次 MVP，可后续通过存储清理任务统一处理。

## Status
**Complete** - 企业产品库和企业资信库编辑功能已从占位改为真实可用，支持元数据编辑和可选替换附件。

---

# Task Plan: P1.6 图文并茂 DOCX 导出可靠性加固

## Goal
提升图文并茂 Word 导出的可解释性和稳定性，避免图片随机插入、插图过多、图片下载失败导致导出失败或用户无法追溯图片来源。

## Scope
- 章节图片插入增加分册和章节级数量上限。
- 每张自动插入图片记录命中原因、来源资产、所属分册、章节和匹配分数。
- DOCX 转换阶段记录图片插入成功、跳过和失败明细。
- 图片下载失败、路径失效、超大小、格式异常时降级跳过，不影响整份 DOCX 导出。
- 导出任务 metadata 写入图片插入报告，便于后续前端展示下载前/下载后风险提示。
- README 和任务清单同步。

## Phases
- [x] Phase 1: 梳理现有 Markdown 图片生成和 DOCX 插入链路
- [x] Phase 2: 章节图片选择增加命中解释、来源记录和数量上限
- [x] Phase 3: DOCX 图片解析插入增加失败降级和转换报告
- [x] Phase 4: 导出任务写入图片 manifest 和转换报告
- [x] Phase 5: 后端编译、前端构建或必要的轻量验证
- [x] Phase 6: README 和任务清单同步

## Files Changed
- `backend/api/routes.py`
- `backend/export/md_to_word.py`
- `frontend/src/api/bidProject.ts`
- `frontend/src/pages/BidEditor/index.tsx`
- `.env.example`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m py_compile backend/api/routes.py backend/export/md_to_word.py backend/db/supabase_repo.py
npm run build
python - <<'PY'
from pathlib import Path
from backend.export.md_to_word import convert_md_to_word
p = Path('/private/tmp/docx_image_probe.md')
p.write_text('# 测试项目\n\n## 章节\n\n![不存在图片](/private/tmp/not-exist-image.png)\n\n正文内容。\n', encoding='utf-8')
out, report = convert_md_to_word(p, return_report=True)
print(out.exists(), report['found'], report['inserted'], report['skipped'], report['failed'])
PY
```

验证结果：
- 后端编译通过。
- 前端构建通过，仍有既有 chunk size warning。
- 失效图片冒烟验证通过：DOCX 正常生成，图片报告为 `True 1 0 1 0`。

## Notes
- `DOCX_ALLOW_REMOTE_IMAGES` 默认关闭，避免导出时下载外部 HTTP 图片带来 SSRF 风险；知识资产的内部 `/api/knowledge/assets/<id>/file` 图片不受影响。
- 图片失败、超限或跳过不会中断 DOCX 导出，结果会写入 `bid_export_tasks.metadata.image_conversion`。
- 自动图片选择结果会写入 `bid_export_tasks.metadata.image_selection.manifest`，包含资产 ID、章节、分册、匹配分和命中原因。

## Status
**Complete** - 图文并茂 DOCX 导出已增加图片选择解释、分册数量上限、失败降级、转换报告和前端复核提示。

---

# Task Plan: P1.7 MinerU 下载、解析、导入断点重试和失败原因展示

## Goal
提升 MinerU/OCR 主链路稳定性，让结果 zip 下载失败、手动导入失败、解析失败和原生抽取失败都有可重试状态、用户可读原因和明确处理阶段。

## Scope
- MinerU 结果 zip 下载支持保留 `.part` 临时文件并在后续重试时断点续传。
- 下载失败时保留 retryable、failure_stage、error_type、user_message、download_retry_count 等字段。
- 手动导入 MinerU zip 失败时写入 `mineru_import_failed` 和用户可读原因。
- parse-status 接口返回失败阶段、错误类型、用户提示、重试次数和可重试标记。
- 历史记录页展示失败阶段和下载重试次数。
- 自动流程解析等待页展示下载重试状态和用户提示。
- README、`.env.example` 和任务清单同步。

## Phases
- [x] Phase 1: 梳理现有 MinerU 状态机、下载重试、手动导入和历史记录展示
- [x] Phase 2: MinerU zip 下载增加断点续传和下载报告
- [x] Phase 3: 解析、下载、导入失败状态标准化
- [x] Phase 4: parse-status 和历史记录接口透出失败阶段、重试次数和用户提示
- [x] Phase 5: 前端工作流和历史记录页展示失败原因与重试信息
- [x] Phase 6: 后端编译、前端构建和必要冒烟验证
- [x] Phase 7: README 和任务清单同步

## Files Changed
- `backend/parsing/mineru_client.py`
- `backend/parsing/document_parser.py`
- `backend/api/routes.py`
- `frontend/src/types/bid.ts`
- `frontend/src/components/workflow/BidWorkflow.tsx`
- `frontend/src/pages/History/index.tsx`
- `.env.example`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m py_compile backend/parsing/mineru_client.py backend/parsing/document_parser.py backend/api/routes.py
npm run build
```

验证结果：
- 后端编译通过。
- 前端构建通过，仍有既有 chunk size warning。

## Notes
- MinerU 结果 zip 下载默认保留 `.part` 临时文件，后续重试优先使用 HTTP Range 断点续传；curl 兜底也会尝试 `--continue-at -`。
- parse-status 返回 `failureStage`、`errorType`、`userMessage`、`retryable` 和 `downloadRetryCount`，历史记录页和自动流程会展示这些信息。
- 手动导入 MinerU zip 失败会写入 `mineru_import_failed`，不再只是接口返回 500。

## Status
**Complete** - MinerU 下载、解析和导入链路已增加断点重试、失败阶段标准化和用户可见错误提示。

---

# Task Plan: P3.1 后端 Smoke Test 最小闭环

## Goal
补齐第一版后端自动化 smoke test，用于在继续拆分路由、增强解析和导出能力前锁住最基础的主链路行为。

## Scope
- 使用 Python 标准库 `unittest`，避免新增测试依赖。
- 覆盖 `/api/health` 健康检查。
- 覆盖非法招标文件上传在外部服务前被拦截。
- 覆盖 MinerU 下载失败状态中的失败阶段、错误类型、用户提示、可重试标记和重试次数透出。
- 覆盖 DOCX 转换遇到失效 Markdown 图片时降级跳过，不中断 Word 生成。
- README 同步测试文件、测试命令和适用场景。

## Phases
- [x] Phase 1: 确认 Flask app 初始化和可测试接口边界
- [x] Phase 2: 新增 `tests/test_smoke.py`
- [x] Phase 3: 编写健康检查、上传校验、解析状态和 DOCX 图片降级测试
- [x] Phase 4: 执行 `python -m unittest discover -s tests`
- [x] Phase 5: README 和任务清单同步

## Files Changed
- `tests/test_smoke.py`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m py_compile tests/test_smoke.py
python -m unittest discover -s tests
```

验证结果：
- `tests/test_smoke.py` 编译通过。
- 后端 smoke test 通过，当前共 4 个测试。

## Notes
- 测试不依赖真实 DashScope、MinerU 或 Supabase 调用。
- 解析状态测试会 mock Supabase 文件查询和 MinerU 下载重试函数，只验证 Flask 路由返回字段和自动重试触发。
- DOCX 图片降级测试使用临时目录生成 Markdown 和 Word 文件，不污染项目输出目录。

## Status
**Complete** - 后端 smoke test 最小闭环已完成，可用 `python -m unittest discover -s tests` 执行。

---

# Task Plan: P3.2 后端 MVP 生产场景测试扩展

## Goal
在第一版 smoke test 基础上，继续覆盖真实生产更容易出问题的 DOCX、章节 API、MinerU 导入/下载和合规覆盖口径，形成可持续扩展的后端 MVP 测试集。

## Scope
- DOCX 导出回归：正式文本清理、表格保留、图片插入上限和跳过报告。
- 章节 API：非法项目 ID、章节保存、章节排序、导出任务非法参数。
- MinerU 状态：手动导入坏 zip 写入失败状态、断点续传 Range 请求、有效 zip 产物识别。
- 合规检查：正文实质命中后覆盖率提升，高风险缺失项识别。
- README 同步测试文件和覆盖场景。

## Phases
- [x] Phase 1: 新增 `tests/test_docx_export.py`
- [x] Phase 2: 新增 `tests/test_api_sections.py`
- [x] Phase 3: 新增 `tests/test_mineru_status.py`
- [x] Phase 4: 新增 `tests/test_compliance.py`
- [x] Phase 5: 执行 `python -m unittest discover -s tests`
- [x] Phase 6: README 和任务清单同步

## Files Changed
- `tests/test_docx_export.py`
- `tests/test_api_sections.py`
- `tests/test_mineru_status.py`
- `tests/test_compliance.py`
- `README.md`
- `task_plan.md`

## Verification

```bash
python -m unittest discover -s tests
```

验证结果：
- 后端 MVP 测试通过，当前共 16 个测试。

## Notes
- 仍然不是完整覆盖率测试；当前重点是锁住无外部依赖的高风险主链路。
- 测试使用 mock 和临时目录，避免真实调用模型厂商、MinerU、Supabase 或污染输出目录。
- 后续应继续补无关问题拒答、DOCX 更细粒度样式测试、用量统计成本测试和前端 Playwright 流程测试。

## Status
**Complete** - 后端 MVP 生产场景测试已扩展到 DOCX、章节 API、MinerU 状态和合规覆盖基础口径。

---

# Task Plan: P3.3 RAG 召回质量确认与补齐

## Goal
确认企业知识助手、企业资信库、企业产品库和标书章节生成中的 RAG/资产召回真实能力，并补齐可重复验证的 MVP 测试与任务状态说明。

## Scope
- 区分“已有通用 RAG/图片资产召回”和“分册维度显式过滤/加权”的能力边界。
- 验证知识库文本召回、图片资产向量召回、关键词兜底、Prompt 来源与图片上下文。
- 验证章节生成和 DOCX 自动配图对技术标、资格文件、商务文件的资产选择是否符合业务常识。
- 同步 README 和分册整改 TODO，避免后续误判为“RAG 未接入”。

## Phases
- [x] Phase 1: 梳理现有 RAG 与资产召回实现
- [x] Phase 2: 新增 RAG/资产召回质量测试
- [x] Phase 3: 根据测试结果补齐轻量逻辑缺口
- [x] Phase 4: 执行后端 MVP 测试集
- [x] Phase 5: README、任务清单和分册 TODO 同步

## Findings
- 企业知识助手已通过 `backend/rag/retrieval.py` 支持文本分片、图片/资质资产、Rerank 和关键词兜底召回。
- 标书章节生成已通过 `backend/ai/section_writer.py` 按分册策略选择企业资料候选。
- DOCX 图文导出已通过 `backend/api/routes.py` 对图片资产做章节/分册打分、数量限制和导出报告。
- 当前缺口主要是缺少测试证明与任务清单状态修正，不是从零接入 RAG。
- 新增测试确认：技术标优先产品/设备图，资格文件优先资信/证照图，商务文件默认谨慎插图，仅明确附件或证明材料时插图。
- 当时独立“适用分册”字段仍未新增；后续已在 P2.4 中补齐 `applicable_volumes`。

## Files Changed
- `tests/test_rag_retrieval.py`
- `tests/test_rag_asset_scoring.py`
- `README.md`
- `docs/技术标商务标分册整改TODO.md`
- `task_plan.md`

## Verification

```bash
python -m unittest discover -s tests
```

验证结果：
- 后端 MVP 测试通过，当前共 26 个测试。

## Errors Encountered
- `python -m unittest tests.test_rag_retrieval tests.test_rag_asset_scoring` 因 `tests/` 不是 Python package 导致模块名导入失败；改用 `python -m unittest discover -s tests -p 'test_rag*.py'` 后通过。
- 初版商务标插图测试预期过宽；实际策略是商务标默认谨慎插图。测试已改为同时覆盖“默认不插图”和“明确证明材料时插图”。

## Status
**Complete** - RAG 召回质量已通过后端测试确认，资料/产品/资信召回能力和分册资产匹配状态已同步到 README 与分册整改 TODO。

---

# Task Plan: P2.4 企业资产适用分册硬过滤

## Goal
为企业资信库和产品库增加独立适用分册字段，并让 RAG、章节生成和 DOCX 自动插图优先遵守该字段，减少跨分册误召回。

## Scope
- Supabase 增加 `knowledge_assets.applicable_volumes` 字段和 GIN 索引。
- 升级 `match_knowledge_assets` RPC，支持 `filter_applicable_volume`。
- 后端上传/编辑资产时保存 `applicable_volumes`，同时写入 `specs/metadata` 兼容老代码和老数据。
- 企业产品库、企业资信库编辑弹窗增加“适用分册”多选。
- RAG 资产检索、章节资料候选、DOCX 图片选择接入显式分册过滤；未标注老数据保持兼容召回。
- 补充测试验证显式分册过滤和跨分册阻断。

## Phases
- [x] Phase 1: 新增 Supabase SQL migration
- [x] Phase 2: 后端资产 payload、RAG 检索和图片选择接入 `applicable_volumes`
- [x] Phase 3: 产品库、资信库前端表单增加适用分册字段
- [x] Phase 4: 补充 RAG/资产匹配测试
- [x] Phase 5: 执行后端测试、语法检查和前端 build
- [x] Phase 6: README 和分册整改 TODO 同步

## Files Changed
- `sql/20260508_add_asset_applicable_volumes.sql`
- `sql/20260428_create_knowledge_assets.sql`
- `backend/core/bid_volumes.py`
- `backend/api/routes.py`
- `backend/ai/section_writer.py`
- `backend/rag/retrieval.py`
- `frontend/src/pages/ProductBase/index.tsx`
- `frontend/src/pages/QualificationBase/index.tsx`
- `frontend/src/pages/KnowledgeBase/KnowledgeSearchDrawer.tsx`
- `tests/test_rag_retrieval.py`
- `tests/test_rag_asset_scoring.py`
- `README.md`
- `docs/技术标商务标分册整改TODO.md`
- `task_plan.md`

## Verification

```bash
python -m unittest discover -s tests -p 'test_rag*.py'
python -m unittest discover -s tests
python -m py_compile backend/core/bid_volumes.py backend/api/routes.py backend/ai/section_writer.py backend/rag/retrieval.py
npm run build
```

验证结果：
- RAG 相关测试通过，当前 12 个 RAG 测试。
- 后端 MVP 测试通过，当前共 28 个测试。
- Python 语法检查通过。
- 前端生产构建通过；Vite 仍提示主包超过 500 kB，这是既有体积警告，不影响本次功能。

## Notes
- 新库或已上线 Supabase 环境需要执行 `sql/20260508_add_asset_applicable_volumes.sql`。
- 新字段为硬过滤优先；空字段老资产仍允许按原规则召回，避免历史数据突然不可用。
- 产品库默认适用 `technical`；资信库默认适用 `qualification/business/attachment`。

## Status
**Complete** - 企业资产适用分册字段、RAG 硬过滤、前端维护入口、测试和文档同步已完成。

---

# Task Plan: P3.4 分册维度合规检查与质量闭环

## Goal
将条款响应检查从整本/技术标/商务包扩展为技术标、商务响应、资格文件、报价文件、附件材料等内部分册摘要，让用户在下载前明确知道各分册响应率和高风险缺口。

## Scope
- 后端合规检查新增内部 `volumeSummaries`。
- 保持 `volumeType=business` 商务包兼容口径：覆盖商务、资格、报价、附件和其他非技术章节。
- 支持 `volumeType=qualification|price|attachment` 内部分册精确检查。
- 工作台质量仪表盘展示各分册响应率、未响应项和高风险数量。
- 补充测试覆盖资格文件分册统计和商务包兼容口径。

## Phases
- [x] Phase 1: 梳理现有合规检查和下载前检查口径
- [x] Phase 2: 后端合规报告扩展内部分册摘要
- [x] Phase 3: 前端质量仪表盘展示分册摘要
- [x] Phase 4: 补充分册合规测试
- [x] Phase 5: 执行后端测试、语法检查和前端 build
- [x] Phase 6: README 和分册整改 TODO 同步

## Files Changed
- `backend/ai/compliance_checker.py`
- `frontend/src/pages/BidEditor/index.tsx`
- `frontend/src/types/interpretation.ts`
- `tests/test_compliance.py`
- `README.md`
- `docs/技术标商务标分册整改TODO.md`
- `task_plan.md`

## Verification

```bash
python -m unittest discover -s tests -p 'test_compliance.py'
python -m unittest discover -s tests
python -m py_compile backend/ai/compliance_checker.py backend/api/routes.py
npm run build
```

验证结果：
- 合规专项测试通过，当前 4 个合规测试。
- 后端 MVP 测试通过，当前共 30 个测试。
- Python 语法检查通过。
- 前端生产构建通过；Vite 仍提示主包超过 500 kB，这是既有体积警告。

## Notes
- `business` 仍是用户下载商务标时的商务包口径，内部摘要会显示商务响应、资格文件、报价文件和附件材料。
- 规则版合规检查仍不是 LLM 语义复核；后续可继续增强评分权重和证据摘录。

## Status
**Complete** - 分册维度条款响应摘要、工作台质量展示、测试和文档同步已完成。

---

# Task Plan: P2.5 标书篇幅自定义设置

## Goal
让客户可以在标书工作台中清晰设置技术标、商务标的目标页数或目标字数，同时系统必须做篇幅可行性判断，避免为了凑页数生成重复、空泛或无关内容。

## Product Principles
- 入口放在标书工作台顶部的【全文设置】。
- 面向单企业部署，不区分普通用户/高级用户。
- 设置维度只保留技术标和商务标，不单独暴露资格文件、报价文件、附件材料篇幅设置。
- 用户可以输入目标页数或目标字数，但系统实际按目标字数控制生成。
- 页数是 Word 排版估算值，最终会受目录、图片、表格、附件、页边距和人工排版影响。
- 当目标页数明显超过当前资料可支撑范围时，系统必须提示风险和补充资料建议，不能硬凑。

## Scope
- 新增全文设置弹窗：篇幅控制、目标页数/字数、扩写策略和风险提示。
- 支持技术标、商务标两类目标篇幅。
- 资格文件、报价文件、附件材料并入商务标整体控制，但不鼓励按字数扩写。
- 将篇幅设置保存到项目级 metadata，刷新后可恢复。
- 章节写作计划读取用户目标篇幅，按章节重要性、评分项、风险项、章节类型分配目标字数。
- 生成正文时使用章节目标字数，不再完全依赖 AI 自行判断篇幅。
- 工作台顶部展示目标页数、当前估算页数、目标字数、当前字数和完成比例。
- 对不足目标篇幅的章节显示“建议扩写”。
- 后续可扩展“一键扩写不足章节”，本阶段先预留但不强制实现。

## To Do

### P0：产品入口和设置模型
- [x] 将顶部【全文设置】按钮改为明确入口，增加 Tooltip：设置目标页数、目标字数、分册篇幅和生成策略。
- [x] 新增“全文生成设置”弹窗。
- [x] 弹窗支持控制方式：
  - [x] 按目标页数
  - [x] 按目标字数
- [x] 设置项只保留：
  - [x] 技术标目标页数 / 目标字数
  - [x] 商务标目标页数 / 目标字数
  - [x] 预计总页数
  - [x] 预计总字数
- [x] 增加固定提示：页数为正式 Word 排版估算，系统实际按目标字数控制正文生成。

### P0：默认值和换算规则
- [x] 默认技术标目标页数：80 页。
- [x] 默认商务标目标页数：40 页。
- [x] 默认完整标书目标页数：约 120 页。
- [x] 技术标按约 700 字/页估算。
- [x] 商务标按约 550 字/页估算。
- [x] 资格文件、报价文件、附件材料不单独设置篇幅，并提示其以资料完整性和人工复核为主。
- [x] 用户切换页数/字数模式时自动互相换算，避免两套数据不一致。

### P1：篇幅可行性评估
- [x] 根据招标文件解析结果、评分项数量、风险项数量、章节数量、企业资料命中情况估算“可支撑页数区间”。
- [x] 当目标页数超过可支撑范围时，弹出明确风险提示。
- [x] 风险提示包含：
  - [x] 当前资料可支撑约多少页
  - [x] 用户目标页数
  - [x] 强行扩写的风险：重复、空泛、无关、虚构
  - [x] 需要补充的资料类型：专项方案、设备资料、项目业绩、图纸、检测报告、附件图片等
- [x] 用户仍可保存高目标页数，但系统标记为“超出建议篇幅”，后续生成时不得无依据灌水。

### P1：章节字数分配
- [x] 按技术标/商务标目标字数分配到章节。
- [x] 高权重评分项章节增加字数权重。
- [x] 高风险或否决项相关章节增加字数权重。
- [x] 技术核心章节增加字数权重，例如施工组织、质量安全、进度资源、关键工艺、设备配置。
- [x] 资格、报价、附件类章节即使归入商务标，也要限制扩写，优先输出资料清单、占位和人工复核提示。
- [x] 每章写入 `writing_plan.target_words` 或 metadata 中的目标字数。

### P1：生成链路接入
- [x] 单章生成读取章节目标字数。
- [x] 批量生成读取全文设置后的章节目标字数。
- [x] Prompt 中明确“不得为了达到字数编造事实、业绩、人员、金额、设备参数或无关内容”。
- [x] 如果章节资料不足，允许输出“当前资料不足以合理扩写到目标字数”的待补充提示。
- [x] 生成完成后刷新当前字数、预计页数和完成比例。

### P2：工作台可视化
- [x] 顶部蓝色统计条显示：
  - [x] 目标页数 / 当前估算页数
  - [x] 目标字数 / 当前字数
  - [x] 技术标目标与当前
  - [x] 商务标目标与当前
- [x] 章节列表或目录模式中显示章节目标字数与当前字数。
- [x] 对低于目标明显不足的章节标记“建议扩写”。
- [x] 对超过目标过多的章节标记“篇幅偏长，建议复核”。

### P2：扩写策略预留
- [x] 在全文设置中提供“不足目标篇幅时”的策略选项：
  - [x] 仅提示补写
  - [x] 允许自动扩写相关章节
- [x] 本阶段默认“仅提示补写”，避免自动扩写导致不可控。
- [x] 后续任务可增加“一键扩写不足章节”。

### P3：测试和文档
- [x] 增加篇幅设置换算测试。
- [x] 增加章节目标字数分配测试。
- [x] 增加超大页数目标的风险提示测试。
- [x] 增加生成 Prompt 是否带目标字数和禁编造约束的测试。
- [x] 更新 README：说明页数/字数设置、估算规则、风险提示和使用边界。
- [x] 更新 `docs/技术标商务标分册整改TODO.md` 或新增专门 TODO，记录篇幅控制能力状态。

## Acceptance Criteria
- 用户能在【全文设置】中清楚看到并设置技术标、商务标目标页数或目标字数。
- 系统能展示目标页数、当前估算页数、目标字数、当前字数和完成比例。
- 章节生成会使用用户设置后的目标字数。
- 用户设置 500 页这类超大目标时，系统会提示当前资料支撑不足和风险，而不是直接硬凑。
- 资格文件、报价文件不被鼓励按篇幅扩写，仍以资料完整性和人工复核为主。
- 所有新增能力有后端测试或前端构建验证。

## Status
**Complete** - 已完成全文设置入口、项目级保存、章节目标字数分配、生成 Prompt 约束、顶部目标统计、章节篇幅提示、后端测试和 README/分册 TODO 同步。

## Follow-up Fix
- [x] 修复设置更高目标页数后，“一键编写全文”只判断章节是否已生成、没有把低于目标 75% 的章节纳入重写的问题。
- [x] 修复历史批量任务 `running` 状态恢复到页面后，覆盖已生成章节状态，导致目录行一直显示“正在编写”的问题。
- [x] 批量章节完成时等待最终任务状态同步，降低刚完成后立即刷新拿到旧 running 状态的概率。

---

# Task Plan: P5.1 LLM 语义合规复核 MVP

## Goal
在现有规则版条款响应检查基础上，增加高价值检查项的 LLM 语义复核，输出评分权重、证据摘录、置信度和补强建议。

## Scope
- 复用现有 `build_compliance_report` rows，不重复解析招标文件。
- 默认只复核高风险、评分项、未覆盖和待补强项，控制 token 成本。
- 输出 `status`、`evidence`、`confidence`、`weight`、`suggestion`、`targetSectionId`。
- 前端质量面板增加“语义复核”入口，抽屉中展示语义结果。
- 测试覆盖已覆盖、部分覆盖、未覆盖和 LLM 失败兜底。

## Phases
- [x] Phase 1: 新增后端语义复核模块和成本控制策略。
- [x] Phase 2: 新增 API 路由和前端 API 类型。
- [x] Phase 3: 工作台接入“语义复核”按钮与结果展示。
- [x] Phase 4: 增加后端单元测试。
- [x] Phase 5: README、任务状态和构建验证。

## Status
**Complete** - 已完成 LLM 语义合规复核 MVP、成本控制、规则兜底、前端入口、结果抽屉、测试和 README 同步。

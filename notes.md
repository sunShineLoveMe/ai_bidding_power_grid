# Notes: 技术标 / 商务标分册大纲升级

## Existing Implementation
- `backend/ai/chapter_planner.py` 原先只要求模型输出 `chapters`，规则版 fallback 也只返回扁平章节列表。
- `backend/db/supabase_repo.py` 的 `replace_bid_sections_from_outline` 只消费顶层 `chapters`，通过 `_section_payload` 和 `ensure_section_volume` 写入 `metadata.volume_type`。
- `backend/core/bid_volumes.py` 已提供分册推断、名称和 `ensure_section_volume`，适合继续承载轻量分册模型。
- 前端工作台已有分册 Tabs 和按 `metadata.volume_type` 筛选逻辑，但类型定义没有声明 `BidOutline.volumes`。

## Implementation Notes
- 本轮采用兼容输出：`volumes` 保存真实业务分册，`chapters` 保存全量扁平章节，避免破坏现有工作台和解读页。
- 规则版 fallback 通过历史 `chapters` 结构推断分册并输出 `volumes`。
- AI Prompt 已改为优先输出 `ai-volume-v1` 的 `volumes[].chapters`。
- 章节写作计划现在优先读取 `metadata.volume_type`，再回退标题关键词。

## Current Implementation Notes: 分册正文生成策略升级
- `backend/core/bid_volumes.py` 新增 `VOLUME_GENERATION_STRATEGIES`，集中定义技术标、商务标、资格文件、报价文件、附件材料的写作侧重点、强制约束、资料召回提示和图片策略。
- `backend/ai/section_writer.py` 在 Prompt 中注入所属分册、分册策略、强制约束、资料召回侧重点、图片/附件策略和按分册筛选的企业资料候选。
- `backend/ai/bid_writing_plan.py` 的写作计划会把分册策略合并进 `strategy`，并在已有 `metadata.volume_type` 时减少标题关键词误判。
- `backend/api/routes.py` 的自动配图按分册过滤：技术标偏产品/设备/工艺图，资格文件偏证照/业绩样张，商务标谨慎插证明类图片，报价文件默认不自动插图。

## Current Implementation Notes: 用户侧二分法投标包
- 真实用户第一层只需要理解和操作 `技术标`、`商务标` 两个投标包；`全部` 仅作为总览。
- 内部细分类继续保留：`qualification`、`price`、`attachment`、`other` 均归入用户侧商务标，用于资料匹配、写作策略和风险约束。
- 首页 `BidVolumeOverview` 已改为两个工作区卡片：技术标、商务标。
- 工作台 Tabs 已改为 `全部 / 技术标 / 商务标`，章节正文标题区同时显示用户侧分册和内部资料类型。
- 后端 DOCX 导出 `volumeType=business` 时会聚合非技术标章节，符合多数施工类招标文件的最终提交习惯。

## Current Implementation Notes: DOCX 正式导出规范
- `backend/api/routes.py` 将内部输出目录 slug 和用户可见文件名拆开：目录仍可使用 ASCII，下载 DOCX 文件名保留中文项目名、分册名和章节名。
- OnlyOffice 和下载接口返回的 `downloadUrl` 会对中文路径做 URL 编码，避免浏览器或文档服务解析失败。
- `backend/export/md_to_word.py` 在 Markdown 转 DOCX 时清理 emoji、图钉、告警图标、变体选择符和零宽字符，页眉使用清理后的中文文档标题。
- `backend/ai/section_writer.py` 已在生成 Prompt 中明确禁止正式标书正文使用 emoji、图标符号或装饰性提示符。

## Current Implementation Notes: 条款响应覆盖率
- 新增 `docs/合规覆盖度整改TODO.md` 作为合规覆盖度整改的跨模型交接清单，按 P0/P1/P2/P3 跟踪。
- 当前“覆盖率”已改名为“条款响应覆盖率”，强调它是招标条款、评分项、风险项到当前章节映射/正文片段的响应追踪，不是最终 Word 标书合规结论。
- 解读页顶部指标卡直接展示条款响应率、未响应数量和高风险未响应数量，原 `合规覆盖` Tab 改为 `条款响应`。
- 顶部指标卡图标支持鼠标悬浮说明，用于解释每个指标的统计口径和业务用途，减少页面常驻文字噪音。
- 标书工作台下载完整文件或分册前会实时拉取条款响应报告；存在未响应或高风险未响应项时弹窗提示，用户可继续下载或返回补强。
- `backend/ai/compliance_checker.py` 的规则版匹配已增强：除静态映射和精确片段外，也读取章节正文、章节目标和标题，通过条款关键词重合度判断正文是否已响应。
- 标书工作台已新增实时质量仪表盘，正文模式和目录模式都显示已生成章节、正文字数、条款响应率、未响应项、高风险未响应项和最后检查时间。
- 进入工作台、单章正文生成完成、批量生成完成、保存章节、切换分册时会刷新条款响应报告；未保存编辑会提示“保存后更新响应率”。
- 条款响应接口支持 `volumeType=technical|business`，工作台切换技术标/商务标会按当前分册拉取响应率；分册下载前也按当前分册风险弹窗，全本下载按整本风险弹窗。
- 条款响应行已增加建议补强章节；工作台仪表盘可打开未响应清单，并通过“定位章节”跳转到建议补强位置。
- 工作台未响应清单支持“生成补强”，后端基于检查项和建议章节生成 300-600 字正式补强段落，前端追加到章节、保存并刷新响应率。
- DOCX 导出时统一由章节树生成标题编号，并剥离章节正文开头的重复 Markdown 标题，避免 Word 中出现重复章节编号。
- DOCX 模板已调整为更接近正式投标文件：正文仿宋小四、固定 28 磅行距、A4 页边距 2.54/3.18cm、标题黑体分级、表格五号/小四居中、页眉页脚小五。
- DOCX 图片导出链路已区分预览和正式输出：前端资信库/产品库预览继续使用 `variant=thumb` 缩略图；标书导出优先使用本地原图或后端 `variant=original` 文件接口，Markdown 转 Word 时仅对超大图片做 2400px 长边、90 质量 JPEG/优化 PNG 的清晰压缩。

## Archived Previous Notes: 本地带图片标书 MVP

### Existing Project Findings
- `main.py` 使用 Flask，上传目录为 `uploads`，输出目录为 `outputs`，关系库为 `bidding.db`。
- `routes.py` 当前支持招标文件上传、预分析、章节生成、OnlyOffice 回调等标书流程。
- `file_to_chroma.py` 当前将 PDF/DOCX/TXT 抽取为文本 chunk，并用 DashScope `text-embedding-v3` 写入 ChromaDB。
- `md_to_word.py` 当前支持标题、段落、列表、Markdown 表格和 Mermaid 图片，但尚不支持普通 Markdown 图片语法。
- `requirements.txt` 已包含 Flask、ChromaDB、OpenAI client、PyPDF2、python-docx 等基础依赖。

### MVP Direction
- 保持现有架构，新增“素材库”能力。
- PDF 产品手册解析后形成两类数据：文本 chunk 用于 RAG 生成产品说明、技术响应；图片 asset 用于按产品型号、章节、图注、附近文本检索并插入 Word。
- 图片检索第一版不依赖视觉模型，先用图片附近文本、章节标题、页码、人工标签做检索。
- 输出 Word 的最小做法是让 AI 生成 Markdown，其中包含图片占位语法，再由 `md_to_word.py` 插入真实图片。

### Mac M1 Local Dependencies
- `PyMuPDF` 用于 PDF 文本和图片抽取。
- `Pillow` 用于图片格式检查和缩放。
- `python-docx` 已存在，用于 Word 插图。
- SQLite 可继续作为 MVP 关系数据库。
- ChromaDB 可继续作为 MVP 向量库。

### Suggested New Files
- `asset_store.py`: 素材库数据库表、写入、查询。
- `pdf_asset_parser.py`: 产品 PDF 手册解析，抽文字、图片、页码、上下文。
- `asset_retriever.py`: 按章节需求检索图片素材。
- `scripts/ingest_product_manual.py`: 命令行导入产品手册。
- `scripts/generate_image_bid_demo.py`: 生成带图片 Word 的端到端 demo。

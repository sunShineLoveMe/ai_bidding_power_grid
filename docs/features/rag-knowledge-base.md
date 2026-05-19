# RAG 知识库架构

> 相关代码：`backend/rag/`、`rag_seed/water_resources/`

## RAG 知识库架构

系统使用 Supabase PostgreSQL + pgvector 作为企业知识库主链路。ChromaDB 仍保留为本地兼容能力，便于早期测试和离线验证。

### RAG 技术框架与模型

当前 RAG 知识库采用"Supabase 业务库 + pgvector 向量检索 + DashScope Embedding + LLM 流式问答"的实现方式。

| 层级 | 技术/模型 | 作用 |
| --- | --- | --- |
| 业务数据库 | Supabase PostgreSQL | 保存知识文档元数据、文档分片、解析状态和业务表 |
| 向量检索 | pgvector | 在 PostgreSQL 内保存 embedding 向量并执行相似度检索 |
| 对象存储 | Supabase Storage | 保存原始知识库文件、招标文件和生成文档 |
| 向量模型 | 默认 DashScope `text-embedding-v4`，维度默认 1024，可在系统设置中调整 | 将用户问题、知识分片和图片资产描述转换为向量 |
| Rerank 重排 | 默认 DashScope `qwen3-rerank`，可切换 `gte-rerank-v2`，系统设置可关闭 | 对 pgvector 初召回结果二次排序，提升水利术语、设备型号、资质名称匹配准确率 |
| 问答模型 | 默认 `qwen-long`，可在系统设置中调整 | 基于召回片段和企业图片资产生成最终回答 |
| 追问意图模型 | 默认读取 `knowledge_followup_model`，未配置时回退到系统文本模型 | 回答结束后识别用户下一步意图，生成 3 个业务追问 |
| 流式输出 | DashScope SSE / Flask `text/event-stream` | 支持 RAG 回答逐段返回，降低首屏等待体感 |
| 文本抽取 | PyPDF2 / Mammoth / Markdown 读取 | 处理普通 PDF、DOCX 和 Markdown 文档 |
| OCR/版面解析 | MinerU，可选 | 处理扫描版 PDF、复杂表格、图片型招标文件 |
| 图片预览与导出 | Pillow + Supabase Storage | 上传企业资信/产品图片时生成 WebP 缩略图，详情预览优先加载缩略图；DOCX 导出优先使用本地/存储原图，超大图片写入 Word 前按清晰压缩处理 |
| 本地兼容向量库 | ChromaDB | 早期 MVP 兼容保留，主链路已转向 Supabase pgvector |

当前核心代码：

| 文件 | 说明 |
| --- | --- |
| `backend/rag/ingestion.py` | 上传知识库资料后的解析、图片上下文提取、embedding 和 `document_chunks` 写入 |
| `backend/rag/retrieval.py` | 用户问题向量化、调用 Supabase RPC 检索、组装 Prompt、生成 RAG 回答 |
| `rag_seed/water_resources/_scripts/ingest_water_rag_seed.py` | 水利行业种子资料批量入库脚本 |
| `backend/rag/vector_store.py` | DashScope embedding 封装与 ChromaDB 兼容逻辑 |
| `backend/api/routes.py` | `/api/knowledge/search`、`/api/knowledge/search/stream` 和 `/api/knowledge/followups` API |

RAG 检索链路：

```text
用户问题
→ 系统配置的 Embedding 模型生成 query embedding
→ Supabase RPC: match_knowledge_chunks
→ pgvector 相似度检索 document_chunks
→ Supabase RPC: match_knowledge_assets 检索企业资信/产品图片资产
→ 图片资产关键词兜底召回，覆盖营业执照、社保、业绩、产品图片等短文本资产
→ 召回 top-k 文档分片
→ 组装带来源信息和图片资产信息的 Prompt
→ 系统配置的知识库问答模型生成回答
→ SSE 流式返回答案
→ 前端展示答案、内联图片、参考资料来源
→ 回答完成后异步调用 /api/knowledge/followups 生成模型追问建议
```

追问建议链路：

```text
RAG 回答完成
→ 前端先基于规则生成兜底追问，保证用户立即可继续操作
→ 前端异步提交用户问题、AI 回答、召回资料、图片资产到 /api/knowledge/followups
→ 后端调用系统配置的追问意图模型
→ 模型输出固定 JSON: intent + followups
→ 后端兼容字符串 JSON 和 dict 两种模型返回格式，并做去重、长度和问号规范化
→ 前端用模型追问替换兜底追问；模型失败时保留规则兜底
```

分片与元数据策略：

- 文本分片默认按段落和长度切分，水利种子库入库脚本使用约 `1800` 字符的 chunk，并保留少量上下文重叠。
- 每个分片写入 `document_chunks.content`，向量写入 `document_chunks.embedding`。
- `document_chunks.metadata` 保存资料分类、文档类型、来源单位、原始 URL、文件路径、标签和 hash。
- 前端 RAG 回答完成后展示参考资料来源，帮助用户核对答案依据。
- 企业资信库、企业产品库上传的图片/附件写入 `knowledge_assets`，可通过向量召回和关键词兜底参与 RAG 问答。
- RAG 回答若提到 `图片资产1`、`图片资产2、3、4` 等编号，前端会自动把对应图片以 Markdown 图片形式插入到相应段落后，避免只输出文字描述。
- 图片预览优先加载缩略图，原图保留用于标书正文插图、附件查看和 DOCX 导出。

当前已验证的水利种子库入库结果：

- 有效资料：26 份
- 向量分片：558 条
- 分类：水利招标文件、水利政策法规、水利标准规范、水利标准话术
- 检索接口：`POST /api/knowledge/search`
- 流式检索接口：`POST /api/knowledge/search/stream`
- 追问建议接口：`POST /api/knowledge/followups`

### RAG 数据流

```mermaid
flowchart TD
    A[知识资料文件] --> B[资料分类]
    B --> C[上传 Supabase Storage]
    C --> D[创建 knowledge_documents]
    D --> E[文本抽取/OCR 解析]
    E --> F[按段落和长度切片]
    F --> G[Embedding 向量化]
    G --> H[写入 document_chunks]
    H --> I[pgvector 相似度检索]
    I --> J[组装上下文]
    J --> K[LLM 生成答案/标书内容]
```

### RAG 资料分类

当前水利行业种子库使用以下分类：

| 分类 | 用途 |
| --- | --- |
| `water_tender_documents` | 公开招标公告、招标文件、施工/监理/设计类样本 |
| `water_policy_regulations` | 招投标、水利建设、质量、安全、验收、信用等法规 |
| `water_standards_specs` | 标准施工招标文件示范文本、标准规范目录 |
| `water_standard_phrases` | 自建投标话术、章节库、检查清单、施工组织设计模板 |

### RAG 入库脚本

水利行业种子资料位于：

```text
rag_seed/water_resources/
```

目录结构：

```text
rag_seed/water_resources/
├── 01_tender_documents/      # 公开招标文件与公告样本
├── 02_policy_regulations/    # 政策法规
├── 03_standards_specs/       # 标准规范目录与示范文本
├── 04_standard_phrases/      # 自建标准话术与章节模板
├── _scripts/
│   ├── download_water_rag_seed.py
│   └── ingest_water_rag_seed.py
├── index.csv
├── index.jsonl
└── README.md
```

重新下载公开资料：

```bash
python rag_seed/water_resources/_scripts/download_water_rag_seed.py
```

入库到 Supabase RAG 知识库：

```bash
python rag_seed/water_resources/_scripts/ingest_water_rag_seed.py
```

入库逻辑：

1. 读取 `index.csv`。
2. 只处理 `status=downloaded` 或 `status=generated` 的有效资料。
3. 跳过下载失败的 `.url.md` 占位文件。
4. 将原始文件上传到 Supabase Storage。
5. 写入 `knowledge_documents`。
6. 抽取文本并按段落切片。
7. 调用 Embedding 模型生成向量。
8. 写入 `document_chunks`。
9. 生成 `ingestion_report.md` 和 `ingestion_report.json`。

当前种子库已验证可入库：

- 有效资料：26 份
- 向量分片：558 条
- 检索链路：`search_knowledge_base()` 可正常召回水利行业资料

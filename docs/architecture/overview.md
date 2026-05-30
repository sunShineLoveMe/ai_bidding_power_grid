# 系统架构总览

> 详细部署说明见 [deployment/quickstart.md](../deployment/quickstart.md)

当前项目定位为电力/电网侧 AI 标书编制系统。默认交付路线是本地 Docker PostgreSQL + 本地文件存储，生产环境平移到阿里云 RDS PostgreSQL + OSS。Supabase 相关内容仅作为历史架构和迁移参考。

## 技术栈

### 后端

- Python 3.9+
- Flask / Flask-CORS
- PostgreSQL / pgvector（统一向量库，已移除 ChromaDB）
- 数据访问层迁移目标：标准 PostgreSQL 驱动或 ORM
- PyPDF2 / Mammoth / python-docx
- Pillow 图片处理，用于企业资信库和产品库缩略图生成
- MinerU API
- OpenAI-compatible SDK，用于调用通义千问等兼容模型服务

### 前端

- Vite
- React 18
- TypeScript
- Ant Design 5
- Tailwind CSS
- React Router
- TanStack Query
- Zustand
- Axios
- lucide-react
- Tiptap / ProseMirror（AI 章节编辑器）

### 存储与外部服务

- 本地 Docker PostgreSQL：开发环境业务数据、结构化解析结果、知识库元数据
- 阿里云 RDS PostgreSQL：生产环境数据库目标
- 本地文件存储 / 阿里云 OSS：招标文件、知识库文件、生成文档
- pgvector：RAG 向量检索
- DashScope / OpenAI-compatible LLM：文本生成、Embedding
- MinerU：复杂 PDF / OCR 解析
- ONLYOFFICE Docs：终稿在线编辑，可选（需 Docker 部署）

## 系统架构

```mermaid
flowchart LR
    U[用户浏览器] --> FE[Vite React 前端]
    FE --> API[Flask API]

    API --> Storage[本地 Storage / 阿里云 OSS]
    API --> DB[(PostgreSQL / 阿里云 RDS)]
    DB --> Vec[(pgvector)]

    API --> Parser[文档解析层]
    Parser --> Native[原生文本抽取]
    Parser --> MinerU[MinerU OCR/版面解析]

    API --> LLM[大语言模型]
    API --> Docx[python-docx 生成 DOCX]
    FE --> Tiptap[Tiptap AI 章节编辑器]
    FE --> Office[ONLYOFFICE / 终稿编辑，可选]

    Storage --> Parser
    Parser --> DB
    Parser --> Vec
    Vec --> LLM
    LLM --> API
```

## 核心业务流程

```mermaid
flowchart TD
    A[上传招标文件] --> B[保存文件与项目信息]
    B --> C{是否需要 OCR}
    C -->|普通文本 PDF/DOCX| D[原生文本抽取]
    C -->|扫描版/复杂版式| E[MinerU 解析]
    D --> F[结构化解析]
    E --> F
    F --> G[项目概况/要求/评分/风险落库]
    G --> H[AI 深度解读]
    H --> I[生成标书章节大纲]
    I --> J[合规覆盖检查]
    J --> K[章节正文生成]
    K --> L[Word 导出/在线编辑]
```

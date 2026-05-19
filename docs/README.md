# 项目文档中心

本文档中心是团队进入项目后的第一入口。新成员应先阅读本文，再按角色进入部署、架构、开发或功能文档。

## 当前项目定位

本项目当前定位为电力/电网侧 AI 标书编制系统，面向国内企业私有化和阿里云交付环境。默认技术路线：

- 本地开发：Docker PostgreSQL + pgvector + 本地文件存储
- 测试/生产：阿里云 RDS PostgreSQL + OSS
- 模型服务：DeepSeek 负责写作与推理，DashScope 负责 Embedding/Rerank
- 文档解析：本地解析能力 + MinerU OCR/版面解析

Supabase 相关文档和代码属于历史架构与迁移参考，后续新开发应优先面向 PostgreSQL + OSS 抽象，不再新增 Supabase 专属依赖。

## 阅读顺序

### 新成员上手

1. [文档制度](./development/documentation-standards.md)
2. [快速开始](./deployment/quickstart.md)
3. [本地 Docker PostgreSQL](./deployment/local-postgres-docker.md)
4. [项目目录结构](./development/project-structure.md)
5. [系统架构总览](./architecture/overview.md)

### 后端开发

- [数据模型](./architecture/data-model.md)
- [API 参考](./development/api-reference.md)
- [安全配置](./deployment/security.md)
- [成本统计](./features/cost-tracking.md)
- [RAG 知识库](./features/rag-knowledge-base.md)

### 前端开发

- [项目目录结构](./development/project-structure.md)
- [章节大纲生成](./features/outline-generation.md)
- [章节写作](./features/section-writing.md)
- [合规检查](./features/compliance.md)
- [DOCX 导出](./features/docx-export.md)

### 部署与实施

- [快速开始](./deployment/quickstart.md)
- [本地 Docker PostgreSQL](./deployment/local-postgres-docker.md)
- [阿里云目标架构](./deployment/aliyun-target-architecture.md)
- [安全配置](./deployment/security.md)
- [Supabase 初始化](./deployment/supabase-setup.md)：仅历史环境或迁移参考使用

## 文档维护要求

- 任何影响启动方式、环境变量、数据库、对象存储、模型配置、外部服务和部署流程的变更，必须同步更新部署文档。
- 任何影响核心表结构、字段含义、数据流向的变更，必须同步更新架构和数据模型文档。
- 任何新增功能入口、交互流程、导出规则、生成策略，必须同步更新对应 feature 文档。
- 文档默认使用中文，命令、路径、环境变量、表名和字段名使用英文原文。
- 历史路线可以保留，但必须明确标注“历史/迁移参考”，避免新成员误用。


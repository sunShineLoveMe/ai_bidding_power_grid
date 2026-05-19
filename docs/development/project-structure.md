# 项目目录结构

## 项目目录

```text
.
├── main.py                         # Flask 服务入口
├── tests/                          # 后端 smoke test
│   └── test_smoke.py
├── backend/                        # 后端业务代码包
│   ├── api/                        # Flask API 路由与用户接口
│   │   ├── routes.py
│   │   └── users.py
│   ├── ai/                         # 大模型调用、解读、章节规划和正文生成
│   │   ├── qwen_client.py
│   │   ├── rerank_client.py
│   │   ├── interpreter.py
│   │   ├── chapter_planner.py
│   │   ├── section_writer.py
│   │   ├── bid_writing_plan.py
│   │   └── compliance_checker.py
│   ├── core/                       # 配置读取与通用工具
│   │   ├── config.py
│   │   └── llm_json_utils.py
│   ├── db/                         # Supabase 客户端与业务数据访问层
│   │   ├── supabase_client.py
│   │   └── supabase_repo.py
│   ├── parsing/                    # MinerU/OCR、招标文件解析和结构化解读
│   │   ├── document_parser.py
│   │   ├── mineru_client.py
│   │   └── bid_interpreter.py
│   ├── rag/                        # 知识库入库、向量化、检索与 RAG 问答
│   │   ├── ingestion.py
│   │   ├── retrieval.py
│   │   └── vector_store.py
│   └── export/                     # DOCX / Word 导出
│       └── md_to_word.py
├── frontend/                       # Vite + React 前端
├── sql/                            # 数据库 SQL
├── rag_seed/water_resources/       # 水利行业 RAG 种子资料
├── parsed_outputs/                 # 文档解析产物，建议加入 .gitignore
├── uploads/                        # 上传文件，建议加入 .gitignore
└── outputs/                        # 生成文件，建议加入 .gitignore
```

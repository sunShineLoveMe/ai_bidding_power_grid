# Project Agent Instructions

## 国家电网 RAG 基座数据工程 Skill

当用户要求处理电网/国家电网 RAG 基座数据、客户标书模板、招标文件包、技术规范书、货物清单、合同条款、分块、metadata、入库、召回评测或回归跟踪时，必须先使用以下 Skill：

- Skill 路径：`.agents/skills/power-grid-rag-ingestion/`
- 核心文档目录：`docs/rag/`
- 客户资料目录：`rag_seed/power_grid_resources/01_tender_documents/`
- 评测结果目录：`docs/rag/runs/`

执行原则：

- 先 inventory，再解析/清洗/分块/入库；
- 默认父子双层分块，child 召回、parent 写作回溯；
- 召回必须优先 metadata 过滤，再向量检索；
- `.xlsx` 货物清单和技术参数表必须结构化，不得只做普通文本向量；
- 每次新增客户资料或调整召回策略后，必须重跑 `scripts/rag/eval_recall.py`，并更新 `docs/rag/evaluation-records.md` 与 `docs/rag/todo.md`；
- 出现水利或其他非电网资料时，先隔离/删除，再复跑召回评测。

## 飞书文档导入 Skill

当用户要求将本项目生成的 Markdown 文档同步、发布、上传、归档到飞书时，使用以下 Skill：

- Skill 路径：.agents/skills/feishu-doc-import/
- 默认文档目录：feishu/docs/
- 目标知识库：AI标书系统-国家电网
- 知识库地址：https://acn03r8l9jgi.feishu.cn/wiki/space/7646261306835635128

## 当前稳定链路

V1 只执行：

本地 Markdown → lark-cli drive +import → 飞书 Docx 云文档 URL

不要自动移动到知识库。导入成功后，由用户手动移动到知识库。

## 执行命令

当用户说“同步到飞书”“发布到飞书”“上传到飞书知识库”时，优先执行：

```bash
.agents/skills/feishu-doc-import/scripts/import-to-feishu-docx.sh "<markdown文件路径>" "<标题>"

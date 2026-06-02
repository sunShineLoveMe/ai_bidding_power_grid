# 国网招投标 RAG 工程文档

本目录沉淀 RAG 基座数据工程的实现记录，便于团队复用、回归与对外技术分享。

## 文档索引

| 文档 | 说明 |
| --- | --- |
| [chunking-strategy.md](chunking-strategy.md) | 父子双层分块策略与按文件类型的切分规则（实现依据） |
| [water-data-cleanup.md](water-data-cleanup.md) | 水利历史数据清理记录（范围、备份、执行、校验） |
| [base-testset.md](base-testset.md) | Base 测试集设计、标注规范与用例清单 |
| [evaluation-records.md](evaluation-records.md) | 召回评测记录（基线 / 各次迭代对比） |

## 相关代码

| 路径 | 作用 |
| --- | --- |
| `backend/rag/chunking.py` | 父子分块器（按 doc_role 路由） |
| `scripts/rag/cleanup_water_data.py` | 水利数据清理脚本（带备份） |
| `scripts/rag/eval_recall.py` | Base 测试集召回评测脚本 |
| `tests/rag/base_testset.jsonl` | Base 测试集（JSONL 标注） |

## 战略文档

技术路线与方案评审见 `feishu/docs/国家电网物资协议库存标书RAG技术路线评审稿.md`。本目录是该方案的**落地实现记录**。

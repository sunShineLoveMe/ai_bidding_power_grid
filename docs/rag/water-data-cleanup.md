# 水利历史数据清理记录

> 目的：将知识库回归为国网电力场景纯净集，避免水利资料污染国网招投标召回与验收基线。
> 执行日期：2026-06-02
> 脚本：`scripts/rag/cleanup_water_data.py`（带 JSON 备份，dry-run 默认）

## 背景

知识库早期混入了水利行业种子数据与 mock 资产。这些数据：

- 与国网电力场景无关，会在召回时产生“高相似度但不可用”的噪声；
- 其向量仍是百炼 `text-embedding-v4` 旧空间，与本项目已切换的 Ollama `qwen3-embedding`（1024 维）不在同一空间，混用会进一步降低召回质量。

因此在 P0 之前先行清理。

## 清理范围

| 表 | 条件 | 数量 |
| --- | --- | --- |
| `knowledge_documents` | `category LIKE 'water%'` | 38 |
| `document_chunks` | 关联上述文档 或 `metadata->>'seed_corpus' IN ('water_resources','water_enterprise_mock')` | 570 |
| `knowledge_assets` | `industry = '水利行业'` | 99 |

**未触碰**：712 条 `embedding IS NULL` 的 chunk —— 它们属于招标解析（`bid_projects`，有 `project_id`、无 `document_id` 关联到 water 文档），与水利知识无关。

## 执行与校验

```bash
# 1. dry-run（仅统计 + 备份，不删除）
python scripts/rag/cleanup_water_data.py

# 2. 实际删除
python scripts/rag/cleanup_water_data.py --apply
```

执行结果：

```
knowledge_assets    deleted = 99
document_chunks(seed) deleted = 570
knowledge_documents deleted = 38（关联 chunk 级联删除）
```

清理后校验：

| 指标 | 值 |
| --- | --- |
| 残留 water 文档 | 0 |
| 残留 water 资产 | 0 |
| `power_grid_resources` chunk | 279（全部 1024 维 Ollama 向量） |
| 招标解析 chunk（无 embedding） | 712（保留，未受影响） |

## 备份与回滚

删除前自动备份到 `backups/water_cleanup_<时间戳>/`，含三张表被删行的完整 JSON（保留 embedding 字段）。如需恢复，可基于备份 JSON 重新插入；或重跑水利种子导入脚本。

## 备注

- 清理是幂等的：再次运行 dry-run 会显示 0 条范围。
- 后续如需多行业共存，应改为按 `industry` / `grid_company` metadata 物理隔离或分库，而非混入同一无过滤召回空间（见技术路线评审稿 §4）。

# Run 20260608 — 企业知识库参考来源中文化与确定性来源去重

## 背景

企业知识库问答参考来源中出现 `taichang_production_capacity_private.md`、`power_grid_tender_documents` 等内部英文/拼音命名；同一 MPP 检验报告的结构化参数命中 5 行时，页面重复展示同一份报告 5 次。

## 处理内容

- 新增中文显示名统一层：`backend/rag/display_names.py`。
- 后端检索返回和提示词构建前统一补充中文 `source_display_name/category_label/evidence_type_label/target_library_label`。
- 前端参考来源按确定性来源合并：同一结构化参数报告按“来源名 + 报告编号 + 规格型号”去重，普通来源按“来源名 + URL”去重。
- 新增现有数据库展示 metadata 修复脚本：`scripts/rag/repair_chinese_display_names.py`。
- 将 9 个遗留资产目录 staging Markdown 从 `taichang_*_private.md` 重命名为中文文件名，并更新 `scripts/rag/stage_liaoning_taichang_mvp.py`，后续生成资产目录 Markdown 时直接使用中文专业命名。
- `AGENTS.md` 已追加 SOP：后续新增资料和用户可见来源必须中文命名；内部枚举只允许作为 metadata 过滤字段；确定性来源不得重复堆满 5 条。

## 数据修复

| 阶段 | 结果文件 | 结果 |
| --- | --- | --- |
| dry-run | `docs/rag/runs/run_20260608_chinese_display_names_dry_run.json` | 预计修复 174 文档、36555 chunk、300 图片资产 |
| execute | `docs/rag/runs/run_20260608_chinese_display_names_execute.json` | 已修复 174 文档、36555 chunk、300 图片资产 |
| 分类二次修复 | `docs/rag/runs/run_20260608_chinese_display_names_execute_after_enterprise_category.json` | 已修复 4377 chunk、300 图片资产 |
| 文件名二次修复 | `docs/rag/runs/run_20260608_chinese_display_names_execute_after_file_rename.json` | 已修复 9 文档、763 chunk 的中文 `source_file` 路径 |

## 真实链路验证

| 场景 | 结果文件 | 验证结论 |
| --- | --- | --- |
| MPP 环刚度真实 stream | `docs/rag/runs/run_20260608_chinese_display_names_real_stream_after_file_rename.json` | raw context 5 条结构化参数，前端去重后展示 1 条确定性报告来源；回答保留 `66.40 kN/m²` |
| 泰昌能力资料真实 stream | `docs/rag/runs/run_20260608_chinese_display_names_real_stream_after_file_rename.json` | 参考来源无内部英文/拼音展示；分类为“泰昌企业资料” |

## 回归结果

- `.venv/bin/python -m pytest tests/test_rag_display_names.py tests/test_taichang_product_parameter_query.py tests/test_rag_retrieval.py -q`
- `.venv/bin/python -m py_compile backend/rag/display_names.py backend/rag/product_parameters.py backend/api/knowledge.py backend/rag/retrieval.py scripts/rag/repair_chinese_display_names.py`
- `cd frontend && npm run build`
- 文件名迁移后复跑 Base 和泰昌专项召回：结果不变。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

## 边界说明

本轮已重命名用户可见资产目录 staging Markdown；MinerU 中间目录、UUID 解析文件和客户原始资料路径仍保留不动，避免破坏资产/原文追溯。用户界面、导出、参考来源和答案引用必须使用中文 display metadata。

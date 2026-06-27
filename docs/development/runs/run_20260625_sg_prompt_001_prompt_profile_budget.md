# 2026-06-25 本地回归：SG-PROMPT-001 Prompt profile 分级瘦身与生成输入预算

## 范围

- P0：`SG-PROMPT-001`
- 目标：按章节类型拆分 prompt profile，控制 RAG、企业资料、泰昌事实包和 prompt 总字符预算，并把 profile 指标写入生成任务 metadata。
- 本次不调整并发 policy 和慢流提前中止；这两项继续进入后续 P0。

## 变更

- 新增 `backend/ai/section_prompt_policy.py`，定义 `simple_plan`、`fact_grounded`、`technical_parameter`、`structured_table`、`attachment_index`、`price_sensitive`、`continuation_slim` 七类 profile。
- `build_section_prompt()`、补写 prompt 和续写 prompt 按 profile 控制 `rag_limit`、`asset_limit`、事实包模式、列表上限和 `max_prompt_chars`。
- 续写 profile 不再加载 RAG/企业资料候选，只保留草稿末尾、客户确认变量和最小事实边界，避免 partial 续写继续带入大 prompt。
- `stream_bid_section()` 在首个 `start` 事件输出 `prompt_profile`、`prompt_chars`、`max_prompt_chars`、`rag_limit`、`asset_limit`、`fact_pack_mode`。
- Celery worker 接收 `start` 事件后写入 task item `metadata`，并同步到 legacy task JSON；SQL 白名单已允许 `metadata` 原子更新。

## 验证

| 验收项 | 结果 |
| --- | --- |
| 后端语法 | `.venv/bin/python -m py_compile backend/ai/section_prompt_policy.py backend/ai/section_writer.py backend/services/section_generation.py backend/tasks/section_tasks.py backend/db/supabase_repo.py` 通过 |
| Prompt profile 单测 | `tests/test_section_prompt_policy.py` 5 passed |
| 章节生成相关回归 | `tests/test_section_prompt_policy.py tests/test_length_settings.py tests/test_section_generation_autoresume.py tests/test_postgres_schema_init.py` 21 passed |
| API/RAG 相关回归 | `tests/test_api_sections.py tests/test_section_prompt_policy.py tests/test_length_settings.py tests/test_section_generation_autoresume.py tests/test_rag_asset_scoring.py` 35 passed |
| DOCX/Celery 导出单测 | `tests/test_docx_export.py tests/test_celery_export_tasks.py` 48 passed |
| SQL 初始化 | `./scripts/init_postgres_schema.sh` 通过，`update_bid_generation_task_item_atomic` 已重新创建 |
| 本地 RAG 门禁 | `scripts/rag/run_local_rag_gate.py --run-id run_20260625_sg_prompt_001` PASS |
| 真实单章生成 | 临时章节任务 `d2af70bd-2391-4303-ba99-cfebe019e557` completed，item metadata 记录 `prompt_profile=simple_plan`、`prompt_chars=5000`、`max_prompt_chars=5000`、`rag_limit=1`、`asset_limit=1`、`fact_pack_mode=identity_only` |
| 完整 DOCX 链路 | 项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d` 创建导出任务 `84af9199-f3cc-44ce-bf3f-9bb5c882cced`，正式门禁 `formal`、阻断项 0、DOCX completed |

## RAG 门禁指标

产物：

```text
docs/rag/runs/run_20260625_sg_prompt_001_summary.md
docs/rag/runs/run_20260625_sg_prompt_001_incremental_summary.md
```

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 265 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 594 ms | 27 |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 354 ms | 0 |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 698 ms | 30 |

真实 stream 抽样：`done=true`，contexts=5，assets=4，images=4。

## DOCX 导出结果

- 文件：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`
- 模板：`formal_bid_standard`
- 封面字段：项目名称、招标编号 `2225AC`、包号 `包1`、投标人 `河北泰昌电力器材科技有限公司` 已写入；分标编号、目标包名称仍按客户确认规则保留确认口径。
- 图片：selected 23、inserted 23、failed 0、skipped 0。
- 字段刷新：LibreOffice `returncode=0`，`status=refreshed`，`manual_refresh_required=false`。
- 表格：刷新报告识别 166 个表格，页眉页脚和 media 资源存在。

## 临时数据

- 临时测试用户：`codex_sg_prompt_*`，仅用于本地 API 回归。
- 临时章节生成任务：
  - 旧 worker 任务：`2b36c4cb-d31e-4084-af59-61632f293814`，completed，但因 worker 未重启，未体现新 profile metadata。
  - 新 worker 任务：`d2af70bd-2391-4303-ba99-cfebe019e557`，completed，已验证 profile metadata。
- 临时章节已删除；对应 item 明细随外键级联清理，任务主记录保留 completed 状态用于审计。

## 结论

`SG-PROMPT-001` 本地实现并通过单测、真实 Celery 单章生成、RAG 门禁和完整 DOCX 导出链路。当前已解决“所有章节共用大 prompt”的第一阶段问题；后续 P0 应继续实现慢流提前保护、partial 草稿续写和自适应并发。

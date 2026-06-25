# SG-PARTIAL-001 partial 草稿续写闭环回归

日期：2026-06-25

## 背景

`SG-CONCURRENCY-001` 已完成任务级自适应并发，但 partial 草稿仍存在两个生产风险：自动续写没有独立上限和复核态，且 partial-only 任务会被 coordinator 早退跳过，客户需要手动续写时也缺少批量入口。

## 本轮改动

- `backend/services/section_generation_policy.py` 新增 `partial_resume_v1` 策略，按草稿占目标比例、尝试次数、慢流次数和 prompt profile 决定 `auto_resume`、`needs_review` 或 `manual_resume`。
- `backend/tasks/section_tasks.py` 允许 partial-only 任务进入 `_dispatch_next_sections()`，修复 coordinator 因无 queued item 直接返回导致自动续写不触发的问题。
- `_dispatch_next_sections()` 对 partial item 写入 `partial_review_required`、`partial_resume_reason`、`partial_draft_ratio`、`retry_policy` 等可观测 metadata。
- `requeue_bid_generation_task_item()` 支持附加策略 metadata；手动/批量续写写入 `manual_resume_requested`，并清除复核阻断。
- `/section-generation-tasks/<task_id>/resume` 支持 `reason`，前端批量续写使用 `batch_resume_partial`。
- `BidEditor` 目录模式新增 partial/慢流/复核/当前并发统计；partial 行区分“草稿可续写”和“草稿需复核”；工具栏新增“批量续写草稿”。

## 真实链路回归

本轮使用本地真实服务、真实 Celery worker、真实 DeepSeek 流式生成和真实 PostgreSQL 数据。测试前将 Celery worker 收敛为 1 套当前代码 worker，避免旧进程消费任务。

| 验收项 | 结果 |
| --- | --- |
| 短 partial 自动续写 | PASS，临时任务 `096b97ea-0315-4df7-aa75-7f807f115f78` 从 `partial_generated` 自动续写到 `done`，`retry_reason=auto_resume_partial`，`prompt_profile=continuation_slim` |
| 自动续写上限/复核态 | PASS，临时任务 `5276347b-d8f2-4ff2-8c8a-76a103395b8b` 在 attempt=2 慢流 partial 后保持 `partial_generated`，写入 `partial_review_required=true`、`partial_resume_reason=slow_partial_limit_reached` |
| 批量续写 API | PASS，同一复核态任务经 `/resume` + `reason=batch_resume_partial` 续写到 `done`，`manual_resume_requested=true`、`partial_review_required=false`、`prompt_profile=continuation_slim` |
| 临时数据清理 | PASS，`regression_case=sg_partial_001` 与 `sg_partial_001_ui` 临时任务和章节剩余 0 |
| 页面基础回归 | PASS，`/bid-editor?projectId=628ed517-0c31-44ea-a5cb-95b25db06fc2` 1440px 目录页 206 行，无横向溢出 |
| 页面 partial 入口 | PASS，真实 API 临时 partial 任务下工具栏出现“批量续写草稿”，顶部统计显示“草稿待续写/需复核/模型慢流”，无横向溢出 |

浏览器截图：

- `output/playwright/sg_partial_bid_editor_1440.png`
- `output/playwright/sg_partial_bid_editor_partial_button_1440.png`

## 自动化测试

| 测试 | 结果 |
| --- | --- |
| partial policy / 调度 / prompt 定向测试 | `tests/test_section_generation_policy.py tests/test_section_generation_autoresume.py tests/test_section_prompt_policy.py`，24 passed |
| 章节/API/DOCX 相关回归 | `tests/test_api_sections.py tests/test_section_writer_formal_quality.py tests/test_docx_export.py tests/test_celery_export_tasks.py tests/test_formal_bid_check.py`，61 passed |
| 前端构建 | `npm --prefix frontend run build`，PASS |
| RAG 本地门禁 | `scripts/rag/run_local_rag_gate.py --run-id run_20260625_sg_partial_001`，PASS |

RAG 增量门禁指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 264 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 607 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 342 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 704 ms |

## 结论

`SG-PARTIAL-001` 已完成本地真实环境验收。partial 草稿不再被无限自动续写；短草稿可自动用 slim prompt 续写，连续慢流或接近目标篇幅会转复核态，客户可通过单章或批量入口继续处理。

下一项建议进入：

```text
SG-PROGRESS-001：前端可解释进度与下载前 partial 草稿提示。
```

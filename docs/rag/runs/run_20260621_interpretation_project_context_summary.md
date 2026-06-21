# run_20260621_interpretation_project_context - RAG 本地门禁自动化入口

- 生成时间：2026-06-21T03:56:25.605900+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2136 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 978 ms | exit_code=0 | docs/rag/runs/run_20260621_interpretation_project_context_pytest.log |
| incremental_regression_gate | PASS | 72837 ms | exit_code=0 | docs/rag/runs/run_20260621_interpretation_project_context_incremental_gate.log |
| stream_sample | PASS | 16068 ms | done=True; contexts=5; assets=8; images=8; error=None | docs/rag/runs/run_20260621_interpretation_project_context_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260621_interpretation_project_context_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=8，done=True

## 结论

- 本地 RAG 门禁通过。

## 客户反馈与根因

客户在“招标项目”菜单点击后直接进入解读页，但页面没有说明当前展示的是哪一次招标文件解析，也没有在当前页提供历史项目切换入口。真实接口核验后确认：`/api/bidding/interpretations/latest` 的语义是“最近一个已有结构化解读的招标项目”，不是任意最新上传文件；前几次解析记录存在于 `/api/bidding/history`，并可通过 `/interpretation?projectId=<项目ID>` 精确打开。

本轮真实历史记录抽样显示，当前同名项目至少存在 3 次解析：

| 项目ID | 创建时间 | 要求 | 风险 | 章节 | 阶段 |
| --- | --- | ---: | ---: | ---: | --- |
| `628ed517-0c31-44ea-a5cb-95b25db06fc2` | 2026-06-20 17:30 | 80 | 60 | 206 | 标书编制 |
| `fa4c8a41-5df2-49a9-984d-1c3ce0de57ea` | 2026-06-18 12:16 | 80 | 60 | 194 | 标书编制 |
| `a1d853bc-ca4e-43b4-bbea-256f561c8a3d` | 2026-06-17 14:42 | 80 | 60 | 102 | 标书编制 |

默认入口当前返回项目 `628ed517-0c31-44ea-a5cb-95b25db06fc2`，即 2026-06-20 17:30 创建的最近一次已完成结构化解读项目。

## 本轮修复

| 范围 | 调整 |
| --- | --- |
| 招标项目页 | 顶部新增项目上下文区，展示“最近一次已完成解读 / 历史项目精确打开”、项目名称、项目 ID、创建时间、招标编号、招标文件名 |
| 历史切换 | 当前页新增“切换历史招标项目”下拉，选择后跳转到 `/interpretation?projectId=<项目ID>`；同时保留“查看全部历史”入口 |
| 操作语义 | 历史记录和首页最近任务中，已进入标书编制的项目按钮显示为“继续编制”，只有未进入编制但有解读时显示“查看解读” |
| 标签可用性 | 资格、风险、评分、章节建议标签显示数量；章节建议在旧字段为空时回退展示 `bid_outline` 或 `sections`，避免架构调整后页面看起来像功能失效 |
| 窄屏布局 | 项目上下文区在 900px 以下改为纵向排列，历史下拉占满可用宽度 |

## 红框标签功能核验

| 标签 | 当前数据来源 | 当前项目结果 | 结论 |
| --- | --- | ---: | --- |
| 解读总览 | `analysis.project_meta.interpretation_report` / `ai_report` | 已返回项目摘要 | 可用 |
| 条款响应 | `/api/bidding/interpretations/<projectId>/compliance-check` | 页面加载时真实请求 | 可用 |
| 资格与要求 | `requirements` | 80 | 可用 |
| 风险检查 | `risks` | 60 | 可用 |
| 评分办法 | `scoringItems` | 80 | 可用 |
| 章节建议 | `chapterSuggestions` -> `bid_outline` -> `sections` | 页面显示 253 条候选/章节 | 可用，已兼容旧字段为空的情况 |

## 真实页面验证

使用本机 Google Chrome 无头模式访问 `http://localhost:5173/interpretation`，注入真实登录态后完成页面验证：

| 检查项 | 结果 |
| --- | --- |
| 项目来源标签 | 显示“最近一次已完成解读” |
| 项目名称 | `国网辽宁电力2025年第三次物资协议库存招标采购` |
| 项目 ID | `628ed517-0c31-44ea-a5cb-95b25db06fc2` |
| 创建时间 | `2026-06-20 17:30` |
| 招标编号 | `2225AC` |
| 招标文件名 | `国网辽宁电力2025年第三次物资协议库存招标采购招标文件.docx` |
| 历史项目下拉 | 存在 |
| 查看全部历史 | 存在 |
| 进入标书编制 | 存在 |
| 1440 宽横向溢出 | 无 |

截图保存到本地临时文件：`/tmp/interpretation_project_context_1440.png`。

## 定向回归

| 命令 | 结果 |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_project_latest_interpretation.py tests/test_celery_interpretation_tasks.py tests/test_api_sections.py tests/test_bid_prefill.py -q` | PASS，23 passed |
| `cd frontend && npm run build` | PASS，仅保留既有 Vite chunk 体积警告 |
| 真实 HTTP 抽样 `/api/bidding/history?limit=5`、`/api/bidding/interpretations/latest` | PASS，返回最新项目与历史项目一致 |
| `scripts/rag/run_local_rag_gate.py --run-id run_20260621_interpretation_project_context` | PASS |

## 阿里云测试环境注意

- 本轮前端改动不需要迁移数据库；部署到阿里云测试环境后，确认前端构建产物和后端 `/api/bidding/history`、`/api/bidding/interpretations/latest` 接口使用同一目标库即可。
- 阿里云环境若已有多次同名招标项目，应重点验证默认入口显示“最近一次已完成解读”，并能通过下拉切换到历史项目。
- 若目标库尚未同步企业库展示修复，仍需按 P1C-12 执行人员证书归库修复脚本；本轮不重复修改图片资产和知识库图片 URL。

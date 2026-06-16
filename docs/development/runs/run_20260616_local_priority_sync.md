# 云环境暂挂后的本地任务优先级同步记录 - 2026-06-16

## 背景

客户暂未提供阿里云测试环境账号，因此阿里云 ECS/RDS/OSS/Redis 全栈联调继续暂挂。本轮不等待云资源，先按泰昌单企业试点、本地真实环境可验证、直接影响客户试用稳定性的口径同步后续任务优先级。

## 本次同步结果

已更新：

- `docs/development/local-next-phase-tasks.md`
- `docs/rag/todo.md`
- `docs/rag/evaluation-records.md`

新增 run 产物：

- `docs/rag/runs/run_20260616_local_priority_sync_baseline_summary.md`
- `docs/rag/runs/run_20260616_local_priority_sync_baseline_base_off.json`
- `docs/rag/runs/run_20260616_local_priority_sync_baseline_base_qwen3.json`
- `docs/rag/runs/run_20260616_local_priority_sync_baseline_customer_off.json`
- `docs/rag/runs/run_20260616_local_priority_sync_baseline_customer_qwen3.json`
- `docs/rag/runs/run_20260616_local_priority_sync_stream.jsonl`

## 第一任务

`P1C-1 泰昌 20260606 正式图片资产 embedding backfill`

选择原因：

- 云环境暂挂时，该任务可在本地真实环境独立推进。
- 当前真实库仍有明确缺口：`knowledge_assets` 共 `597` 条，已有 embedding `297` 条，缺失 `300` 条。
- 缺失批次集中，风险边界清楚：`customer_liaoning_taichang_20260606_p0_formal_full_page_assets_v1`。
- 该任务直接影响泰昌知识库图文问答、语义找图和正式 DOCX 自动配图排序。

## 真实环境检查

### API ready

真实请求：

```bash
curl -sS --max-time 20 http://127.0.0.1:3012/api/ready
```

结果：

| 检查项 | 状态 |
| --- | --- |
| database | ok |
| Redis | ok |
| Celery | ok，workers=1 |
| model_config | ok |
| storage | ok，provider=local |

### 图片资产 embedding 统计

真实数据库查询结果：

| 批次 | 资产数 | 已有 embedding |
| --- | ---: | ---: |
| `customer_liaoning_taichang_20260606_p0_formal_full_page_assets_v1` | 300 | 0 |
| `customer_taichang_supplement_20260611` | 297 | 297 |
| 合计 | 597 | 297 |

## 真实增量回归

执行命令：

```bash
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_incremental_regression_gate.py --run-id run_20260616_local_priority_sync_baseline
```

结果：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 260 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 564 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 327 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 647 ms |

门禁结论：PASS。

## 真实 stream 抽样

第一次未带登录态直接调用真实接口，被认证拦截，返回“请先登录后再访问”。随后通过真实注册/登录接口创建本地回归账号 `codex_regression_20260616`，携带 Bearer token 重试。

真实请求：

```bash
curl -N -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -X POST http://127.0.0.1:3012/api/bidding/knowledge/search/stream \
  -d '{"query":"泰昌有哪些生产线或生产制造能力图片资料？","metadata_filter":{"enterprise":"泰昌"}}'
```

结果：

| 指标 | 结果 |
| --- | ---: |
| HTTP/SSE | 返回 `start/status/retrieved/chunk/done` |
| 召回资料 | 4 条 |
| 召回图片资产 | 8 个 |
| 原始记录 | `docs/rag/runs/run_20260616_local_priority_sync_stream.jsonl` |

结论：真实 API、登录鉴权、知识库文本召回、图片资产召回和 LLM 流式回答链路可用。

## 后续验收口径

执行 P1C-1 时必须满足：

1. 对 `customer_liaoning_taichang_20260606_p0_formal_full_page_assets_v1` 缺失 embedding 的 300 条资产做 backfill，或给出不应向量化的排除清单。
2. 补齐后复核 `knowledge_assets` 总数、已有 embedding 数、缺失数。
3. 真实 `/api/knowledge/search/stream` 抽样覆盖营业执照、生产线、检测设备、检验报告、绿色低碳等问法。
4. 复跑 Base + 泰昌专项增量回归门禁，结果写入 `docs/rag/runs/` 和 `docs/rag/evaluation-records.md`。

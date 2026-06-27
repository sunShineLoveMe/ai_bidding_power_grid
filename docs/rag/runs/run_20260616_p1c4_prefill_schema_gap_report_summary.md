# run_20260616_p1c4_prefill_schema_gap_report - RAG 本地门禁自动化入口

- 生成时间：2026-06-16T14:25:04.404487+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2155 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 958 ms | exit_code=0 | docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_pytest.log |
| incremental_regression_gate | PASS | 60733 ms | exit_code=0 | docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_incremental_gate.log |
| stream_sample | PASS | 14526 ms | done=True; contexts=5; assets=8; images=8; error=None | docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=8，done=True

## 结论

- 本地 RAG 门禁通过。

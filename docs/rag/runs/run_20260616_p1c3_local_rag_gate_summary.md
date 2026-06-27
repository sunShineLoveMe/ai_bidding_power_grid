# run_20260616_p1c3_local_rag_gate - RAG 本地门禁自动化入口

- 生成时间：2026-06-16T08:18:40.286820+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2149 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 942 ms | exit_code=0 | docs/rag/runs/run_20260616_p1c3_local_rag_gate_pytest.log |
| incremental_regression_gate | PASS | 60126 ms | exit_code=0 | docs/rag/runs/run_20260616_p1c3_local_rag_gate_incremental_gate.log |
| stream_sample | PASS | 15134 ms | done=True; contexts=5; assets=8; images=8; error=None | docs/rag/runs/run_20260616_p1c3_local_rag_gate_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260616_p1c3_local_rag_gate_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=8，done=True

## 结论

- 本地 RAG 门禁通过。

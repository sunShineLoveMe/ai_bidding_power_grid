# run_20260618_p1c10_formal_gate_closure - RAG 本地门禁自动化入口

- 生成时间：2026-06-18T14:44:11.324729+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2279 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 937 ms | exit_code=0 | docs/rag/runs/run_20260618_p1c10_formal_gate_closure_pytest.log |
| incremental_regression_gate | PASS | 60707 ms | exit_code=0 | docs/rag/runs/run_20260618_p1c10_formal_gate_closure_incremental_gate.log |
| stream_sample | PASS | 14192 ms | done=True; contexts=5; assets=8; images=8; error=None | docs/rag/runs/run_20260618_p1c10_formal_gate_closure_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260618_p1c10_formal_gate_closure_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=8，done=True

## 结论

- 本地 RAG 门禁通过。

# run_20260618_formal_export_gate_real_acceptance - RAG 本地门禁自动化入口

- 生成时间：2026-06-18T07:52:55.867707+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2289 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 899 ms | exit_code=0 | docs/rag/runs/run_20260618_formal_export_gate_real_acceptance_pytest.log |
| incremental_regression_gate | PASS | 59773 ms | exit_code=0 | docs/rag/runs/run_20260618_formal_export_gate_real_acceptance_incremental_gate.log |
| stream_sample | PASS | 12929 ms | done=True; contexts=5; assets=8; images=8; error=None | docs/rag/runs/run_20260618_formal_export_gate_real_acceptance_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260618_formal_export_gate_real_acceptance_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=8，done=True

## 结论

- 本地 RAG 门禁通过。

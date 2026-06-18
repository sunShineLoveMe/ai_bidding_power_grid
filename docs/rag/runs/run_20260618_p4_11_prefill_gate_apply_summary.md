# run_20260618_p4_11_prefill_gate_apply - RAG 本地门禁自动化入口

- 生成时间：2026-06-18T03:11:30.770940+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2330 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 891 ms | exit_code=0 | docs/rag/runs/run_20260618_p4_11_prefill_gate_apply_pytest.log |
| incremental_regression_gate | PASS | 61434 ms | exit_code=0 | docs/rag/runs/run_20260618_p4_11_prefill_gate_apply_incremental_gate.log |
| stream_sample | PASS | 15119 ms | done=True; contexts=5; assets=8; images=8; error=None | docs/rag/runs/run_20260618_p4_11_prefill_gate_apply_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260618_p4_11_prefill_gate_apply_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=8，done=True

## 结论

- 本地 RAG 门禁通过。

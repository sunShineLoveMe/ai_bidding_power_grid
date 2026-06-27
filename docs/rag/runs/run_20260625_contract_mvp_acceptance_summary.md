# run_20260625_contract_mvp_acceptance - RAG 本地门禁自动化入口

- 生成时间：2026-06-25T13:32:10.550681+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2103 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 18315 ms | exit_code=0 | docs/rag/runs/run_20260625_contract_mvp_acceptance_pytest.log |
| incremental_regression_gate | PASS | 61476 ms | exit_code=0 | docs/rag/runs/run_20260625_contract_mvp_acceptance_incremental_gate.log |
| stream_sample | PASS | 9288 ms | done=True; contexts=5; assets=4; images=4; error=None | docs/rag/runs/run_20260625_contract_mvp_acceptance_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260625_contract_mvp_acceptance_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=4，done=True

## 结论

- 本地 RAG 门禁通过。

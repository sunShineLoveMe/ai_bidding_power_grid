# run_20260626_aliyun_enterprise_source_convergence_final - RAG 本地门禁自动化入口

- 生成时间：2026-06-26T00:14:23.623053+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2215 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 928 ms | exit_code=0 | docs/rag/runs/run_20260626_aliyun_enterprise_source_convergence_final_pytest.log |
| incremental_regression_gate | PASS | 60293 ms | exit_code=0 | docs/rag/runs/run_20260626_aliyun_enterprise_source_convergence_final_incremental_gate.log |
| stream_sample | PASS | 11485 ms | done=True; contexts=3; assets=6; images=6; error=None | docs/rag/runs/run_20260626_aliyun_enterprise_source_convergence_final_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260626_aliyun_enterprise_source_convergence_final_incremental_summary.md`
- 真实 stream 抽样：contexts=3，assets=6，done=True

## 结论

- 本地 RAG 门禁通过。

# run_20260626_taichang_enterprise_source_scope_final - RAG 本地门禁自动化入口

- 生成时间：2026-06-26T03:22:55.425400+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2215 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 1073 ms | exit_code=0 | docs/rag/runs/run_20260626_taichang_enterprise_source_scope_final_pytest.log |
| incremental_regression_gate | PASS | 61573 ms | exit_code=0 | docs/rag/runs/run_20260626_taichang_enterprise_source_scope_final_incremental_gate.log |
| stream_sample | PASS | 7263 ms | done=True; contexts=3; assets=6; images=6; error=None | docs/rag/runs/run_20260626_taichang_enterprise_source_scope_final_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260626_taichang_enterprise_source_scope_final_incremental_summary.md`
- 真实 stream 抽样：contexts=3，assets=6，done=True

## 结论

- 本地 RAG 门禁通过。

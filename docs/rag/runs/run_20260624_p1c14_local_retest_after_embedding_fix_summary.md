# run_20260624_p1c14_local_retest_after_embedding_fix - RAG 本地门禁自动化入口

- 生成时间：2026-06-24T08:22:03.237809+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2242 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 945 ms | exit_code=0 | docs/rag/runs/run_20260624_p1c14_local_retest_after_embedding_fix_pytest.log |
| incremental_regression_gate | PASS | 60236 ms | exit_code=0 | docs/rag/runs/run_20260624_p1c14_local_retest_after_embedding_fix_incremental_gate.log |
| stream_sample | PASS | 8543 ms | done=True; contexts=5; assets=4; images=4; error=None | docs/rag/runs/run_20260624_p1c14_local_retest_after_embedding_fix_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260624_p1c14_local_retest_after_embedding_fix_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=4，done=True

## 结论

- 本地 RAG 门禁通过。

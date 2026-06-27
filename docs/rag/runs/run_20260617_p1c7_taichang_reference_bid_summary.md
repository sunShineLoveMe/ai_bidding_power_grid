# run_20260617_p1c7_taichang_reference_bid - RAG 本地门禁自动化入口

- 生成时间：2026-06-17T12:27:35.532831+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2268 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 1001 ms | exit_code=0 | docs/rag/runs/run_20260617_p1c7_taichang_reference_bid_pytest.log |
| incremental_regression_gate | PASS | 60838 ms | exit_code=0 | docs/rag/runs/run_20260617_p1c7_taichang_reference_bid_incremental_gate.log |
| stream_sample | PASS | 10452 ms | done=True; contexts=5; assets=8; images=8; error=None | docs/rag/runs/run_20260617_p1c7_taichang_reference_bid_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260617_p1c7_taichang_reference_bid_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=8，done=True

## 结论

- 本地 RAG 门禁通过。

# run_20260626_product_qualification_upload_index_regression - RAG 本地门禁自动化入口

- 生成时间：2026-06-26T07:06:14.032322+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2248 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 1093 ms | exit_code=0 | docs/rag/runs/run_20260626_product_qualification_upload_index_regression_pytest.log |
| incremental_regression_gate | PASS | 61688 ms | exit_code=0 | docs/rag/runs/run_20260626_product_qualification_upload_index_regression_incremental_gate.log |
| stream_sample | PASS | 15856 ms | done=True; contexts=5; assets=7; images=7; error=None | docs/rag/runs/run_20260626_product_qualification_upload_index_regression_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260626_product_qualification_upload_index_regression_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=7，done=True

## 结论

- 本地 RAG 门禁通过。

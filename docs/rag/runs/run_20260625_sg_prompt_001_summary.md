# run_20260625_sg_prompt_001 - RAG 本地门禁自动化入口

- 生成时间：2026-06-25T09:54:49.219097+00:00
- 门禁状态：PASS

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2157 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 754 ms | exit_code=0 | docs/rag/runs/run_20260625_sg_prompt_001_pytest.log |
| incremental_regression_gate | PASS | 60184 ms | exit_code=0 | docs/rag/runs/run_20260625_sg_prompt_001_incremental_gate.log |
| stream_sample | PASS | 10528 ms | done=True; contexts=5; assets=4; images=4; error=None | docs/rag/runs/run_20260625_sg_prompt_001_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260625_sg_prompt_001_incremental_summary.md`
- 真实 stream 抽样：contexts=5，assets=4，done=True

## 结论

- 本地 RAG 门禁通过。

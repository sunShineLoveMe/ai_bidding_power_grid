# run_20260624_p1c14_local_retest - RAG 本地门禁自动化入口

- 生成时间：2026-06-24T08:17:21.805661+00:00
- 门禁状态：FAIL

## 步骤结果

| 步骤 | 状态 | 耗时 | 详情 | 产物 |
| --- | --- | ---: | --- | --- |
| api_ready | PASS | 2093 ms | http=200; status=ok; failed_checks=[] | - |
| rag_unit_tests | PASS | 922 ms | exit_code=0 | docs/rag/runs/run_20260624_p1c14_local_retest_pytest.log |
| incremental_regression_gate | FAIL | 5873 ms | exit_code=1; output_tail=py", line 1047, in request
    raise self._make_status_error_from_response(err.response) from None
openai.InternalServerError: Error code: 502

>>> Base rerank off
/Users/chris/Documents/项目/AI标书项目/ai_bidding_power_grid/.venv/bin/python scripts/rag/eval_recall.py --k 5 --rerank off --save docs/rag/runs/run_20260624_p1c14_local_retest_incremental_base_off.json
Traceback (most recent call last):
  File "/Users/chris/Documents/项目/AI标书项目/ai_bidding_power_grid/scripts/rag/run_incremental_regression_gate.py", line 175, in <module>
    raise SystemExit(main())
                     ~~~~^^
  File "/Users/chris/Documents/项目/AI标书项目/ai_bidding_power_grid/scripts/rag/run_incremental_regression_gate.py", line 146, in main
    "base_off": _run_eval("Base rerank off", ["--k", str(args.k), "--rerank", "off"], outputs["base_off"]),
                ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/chris/Documents/项目/AI标书项目/ai_bidding_power_grid/scripts/rag/run_incremental_regression_gate.py", line 37, in _run_eval
    raise RuntimeError(f"{label} failed with exit code {completed.returncode}")
RuntimeError: Base rerank off failed with exit code 1
 | docs/rag/runs/run_20260624_p1c14_local_retest_incremental_gate.log |
| stream_sample | FAIL | 4849 ms | done=False; contexts=0; assets=0; images=0; error=检索问答失败，请查看后端日志。 | docs/rag/runs/run_20260624_p1c14_local_retest_stream.jsonl |

## 关键产物

- 增量回归门禁：`docs/rag/runs/run_20260624_p1c14_local_retest_incremental_summary.md`
- 真实 stream 抽样：contexts=0，assets=0，done=False

## 结论

- 本地 RAG 门禁失败，请优先查看状态为 FAIL 的步骤和对应产物。

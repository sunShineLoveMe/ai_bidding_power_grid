# 30 章节真实长任务压测报告

- project_id: `e3d516b7-c2e0-4349-8ede-efab6241076b`
- task_id: `88dc10b6-81dd-4896-b893-413a9eff10d0`
- result: `completed`
- sections: `30`
- target_words_total: `83600`
- duration_seconds: `367`
- content_chars_range: `2295-5689`
- json: `docs/development/runs/run_20260605_091856_section_longtask_30_real.json`

## Steps

| step | elapsed_ms | detail |
| --- | ---: | --- |
| `register_login` | 101 | user=codex_longtask_20260605_091249 |
| `select_leaf_sections` | 10 | available=41 selected=30 |
| `create_section_generation_task` | 110 | task_id=88dc10b6-81dd-4896-b893-413a9eff10d0 total=30 |
| `wait_section_generation_task` | 367504 | status=completed done=30 failed=0 |
| `verify_section_content` | 9 | empty=0 min_chars=2295 max_chars=5689 |

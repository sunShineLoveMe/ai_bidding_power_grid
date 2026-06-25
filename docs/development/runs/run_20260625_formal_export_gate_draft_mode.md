# run_20260625_formal_export_gate_draft_mode — 正式导出门禁草稿版降级

- 时间：2026-06-25 10:51:02 CST
- 范围：全文/分册 DOCX 导出前正式检查门禁、草稿版导出 metadata、前端提示、Celery 任务 metadata 保留
- 真实项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`

## 变更摘要

- `POST /api/bidding/interpretations/<project_id>/download-docx` 在全文/分册导出前执行正式检查。
- 阻断项为 0 时返回 `exportMode=formal`；阻断项存在或检查失败时返回 `exportMode=draft`，仍允许创建草稿版导出任务。
- 导出任务 metadata 新增 `formal_export_gate`，记录检查状态、阻断项数量、规则版本、前几条阻断项摘要。
- Celery 导出任务完成时保留初始 `formal_export_gate`，不会被图片插入和字段刷新 metadata 覆盖。
- 标书编辑页创建任务和轮询完成时均识别草稿版，提示“不能作为正式投标文件提交”。
- 章节导出不触发全文正式门禁，metadata 标记为 `section_export_not_full_formal_gate`。

## 真实门禁抽样

命令：

```bash
set -a; source .env; set +a; PYTHONPATH=. .venv/bin/python - <<'PY'
from backend.api.export import _build_formal_export_gate
project_id = 'a1d853bc-ca4e-43b4-bbea-256f561c8a3d'
gate = _build_formal_export_gate(project_id, scope='full')
print(gate)
PY
```

结果摘要：

| 项 | 结果 |
| --- | --- |
| checked | `True` |
| scope | `full` |
| export_mode | `draft` |
| can_formal_export | `False` |
| formal_export_label | `仅允许草稿版导出` |
| blocked_count | `6` |
| top_blocker_ids | `B-005,B-006,B-009,T-003,F-005` |

结论：当前真实项目存在正式阻断项时，全文导出会被系统门禁降级为草稿版，不会冒充正式版。

## 回归验证

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| 后端正式检查与导出任务回归 | `PYTHONPATH=. .venv/bin/pytest tests/test_celery_export_tasks.py tests/test_formal_bid_check.py -q` | PASS，14 passed |
| 前端构建 | `npm --prefix frontend run build` | PASS |
| 真实正式检查服务抽样 | `build_formal_bid_check_report('a1d853bc-ca4e-43b4-bbea-256f561c8a3d')` | PASS，返回 `blocked=6`、`formalExportLabel=仅允许草稿版导出` |
| 真实 DOCX 导出链路 | `scripts/rag/verify_taichang_full_bid_acceptance.py --run-id run_20260625_formal_export_gate_docx_chain` | 链路完成，严格验收 FAIL；唯一失败项为 `placeholders=650`，门禁应阻断正式版 |

## DOCX 链路复验

真实链路输出：

- 报告：`docs/development/runs/run_20260625_formal_export_gate_docx_chain.md`
- JSON：`docs/development/runs/run_20260625_formal_export_gate_docx_chain.json`
- DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`

验收结论：

- `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice` 已真实执行完成。
- DOCX 可打开，封面、目录、页眉页脚、字段刷新、图片、表格和字体检查通过。
- 正文仍有 `650` 处占位符，因此正式导出门禁未通过；这验证本轮草稿版降级是必要且正确的。
- 验收脚本已修正项目名口径：优先使用封面字段/解析项目名，避免要求页眉包含“招标文件”字样。

## 未完成项

- 动态招标检查项仍需逐条增强到正式检查明细。
- 导出后成品检查已能读取导出任务 metadata，但图片候选、表格保真和第六章固定表单仍需继续强化。
- 正式版放行仍依赖客户确认关键字段和清理正文占位符，当前真实项目尚未达到正式版导出条件。

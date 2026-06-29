# 2026-06-29 P1-1 历史父级容器正文治理回归

## 背景

P0 已经保证父级容器不进入正文编辑态，正式 DOCX 导出也会忽略父级 `content`。但数据库中仍残留历史父级正文，长期保留会造成两个风险：

- 后续功能误用父级 `content`，再次把父级概述或内部草稿写进正式标书。
- 客户或实施人员看到父级有正文，误以为父级可以直接编辑或导出正文。

本轮 P1-1 目标是把历史父级正文做可追溯治理：先备份，再隔离，必要迁移只做人工复核标记，不自动把父级内容塞进叶子章节。

## 新增脚本

脚本：`scripts/rag/govern_bid_container_content.py`

能力：

- 识别父级容器：`section_role=container`、`leaf_generation=false` 或存在子章节的节点。
- 默认 dry-run：盘点容器、分类内容、写备份和 summary，不改数据库。
- `--apply --clear-content`：写入 metadata 审计，并清空父级 `content`。
- 不把历史全文写入 metadata，只保存 `content_sha256`、字数、分类、备份路径和治理动作。

关键 metadata：

- `container_content_policy=ignored_for_formal_export`
- `container_content_governance`
- `container_content_governance_history`
- `container_note`
- `migration_review_required=true`

## 执行项目

项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`

命令：

```bash
set -a; source .env; set +a; .venv/bin/python scripts/rag/govern_bid_container_content.py \
  --project-id a1d853bc-ca4e-43b4-bbea-256f561c8a3d \
  --run-id run_20260629_bid_container_content_governance \
  --apply \
  --clear-content
```

审计文件：

- 备份：`docs/development/runs/run_20260629_bid_container_content_governance_container_content_backup.json`
- Summary：`docs/development/runs/run_20260629_bid_container_content_governance_container_content_governance_summary.json`

## 治理结果

执行前 dry-run：

- 父级容器：`27`
- 有历史正文的父级容器：`27`
- 内部提示类：`0`
- 正式概述候选：`27`

判断：

- 这批历史内容更像父级概述，不是 `编写要点/需准备资料/风险与复核` 这类内部提示。
- 不自动迁移到叶子小节。原因是父级概述覆盖范围宽，直接塞进第一个叶子小节会造成正文重复、章节主题漂移和目录/正文口径不一致。
- 本轮采取“备份 + 清空父级 content + 标记迁移复核候选”的保守治理方式。

执行后数据库复核：

```json
{
  "sections_total": 102,
  "containers": 27,
  "container_nonempty_content": 0,
  "governed_containers": 27,
  "migration_review_required": 27,
  "leaf_nonempty_content": 75
}
```

## 真实 DOCX 复测

链路：

```bash
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

输出：

- Markdown：`output/playwright/run_20260629_bid_container_content_governance/a1d853bc/泰昌_2225AC_包1_投标文件_20260629.md`
- DOCX：`output/playwright/run_20260629_bid_container_content_governance/a1d853bc/泰昌_2225AC_包1_投标文件_20260629.docx`
- 字段刷新：`refreshed`

污染扫描：

| 关键词 | Markdown 命中 | DOCX XML 命中 |
| --- | ---: | ---: |
| 编写要点 | 0 | 0 |
| 需准备资料 | 0 | 0 |
| 风险与复核 | 0 | 0 |
| 目标字数 | 0 | 0 |
| 硬性篇幅上限 | 0 | 0 |
| 参考客户同类标书目录组织本节 | 0 | 0 |
| 历史父级正文已备份 | 0 | 0 |

## 自动化验证

```bash
.venv/bin/python -m pytest tests/test_bid_container_content_governance.py tests/test_length_settings.py tests/test_docx_export.py -q
```

结果：`74 passed, 1 warning`

## 回滚方式

如需恢复历史父级正文，使用备份文件中的 `id/content/metadata/status` 字段按 `project_id + id` 回写 `bid_sections`。不建议直接恢复到正式环境，除非已经确认父级概述需要保留，并将对应节点显式配置为后续 P2-1 的 `container_content_policy=formal_overview` 白名单。

## 结论

P1-1 已完成：

- 历史父级正文已备份。
- 父级 `content` 已清空。
- 父级容器 metadata 已明确标记不进入正式导出。
- 叶子章节正文未受影响。
- 清理后真实 DOCX 导出稳定，内部提示和治理 metadata 未泄露到正式文件。

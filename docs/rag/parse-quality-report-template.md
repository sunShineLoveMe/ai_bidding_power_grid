# 客户资料解析质量报告模板

> 文件名建议：`parsed_outputs/power_grid_customer_corpus/<ingestion_batch_id>/parse_quality_report.md`。  
> 用途：在正式入库前判断解析产物是否足够支撑 RAG、智能问答、标书写作和图文并茂资产选择。

## 1. 批次信息

| 项 | 内容 |
| --- | --- |
| `ingestion_batch_id` | `<batch_id>` |
| 批次名称 | `<batch_name>` |
| MVP 试点企业 | 泰昌 |
| 投标申请主体 | 泰昌 |
| 招标场景 | `<province/batch/package/material>` |
| manifest | `parsed_outputs/power_grid_customer_corpus/<batch_id>/manifest.json` |
| 解析产物目录 | `parsed_outputs/power_grid_customer_corpus/<batch_id>/` |
| 报告生成时间 | `<timestamp>` |

## 2. 资料边界结论

| 资料域 | 文件数 | 质量结论 | 入库用途 | 边界 |
| --- | ---: | --- | --- | --- |
| 泰昌企业事实 | 0 | `pass/warn/fail` | 企业资信、生产、检测、财务、绿色低碳、图片资产 | 可作为泰昌事实 |
| 辽宁招标要求 | 0 | `pass/warn/fail` | 招标要求、货物清单、技术规范、合同条款 | 不作为泰昌事实 |
| 河北豪乾参考稿 | 0 | `pass/warn/fail` | 目录、格式、表达参考 | `reference_only=true`，不作为泰昌事实 |

## 3. 文件级质量表

| 文件 | 类型 | 解析器 | 页数/Sheet | 文本量 | 表格数 | 图片资产数 | 质量 | 问题 | 处理建议 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| `<file>` | `pdf/docx/xlsx` | `mineru_ocr` | 0 | 0 | 0 | 0 | `pass/warn/fail` | `<issue>` | `<action>` |

质量取值：

- `pass`：文本、表格、图片或关键证据满足入库和引用要求。
- `warn`：可入库，但有客户确认项、少量页码缺失、少量 OCR 噪声或规格覆盖不确定。
- `fail`：正文为空、乱码严重、关键表格丢失、扫描件未 OCR、图片资产不可追溯、资料域 metadata 错误。

## 4. 文本解析检查

| 检查项 | 门槛 | 结果 | 说明 |
| --- | --- | --- | --- |
| 空文本 | 可入库文件不得为空 | `pass/warn/fail` |  |
| 乱码 | 关键章节不得出现大面积乱码 | `pass/warn/fail` |  |
| 标题层级 | 主招标文件和投标模板应保留章节层级 | `pass/warn/fail` |  |
| 页码追溯 | PDF/OCR 资料应能追溯页码 | `pass/warn/fail` |  |
| 重复内容 | 页眉页脚、目录、重复段落应可清洗 | `pass/warn/fail` |  |

## 5. 表格解析检查

| 表格类型 | 文件 | 原始结构 | 检索摘要 | 行级记录 | 质量 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 货物清单 | `<file.xlsx>` | `yes/no` | `yes/no` | `yes/no` | `pass/warn/fail` |  |
| 技术参数表 | `<file>` | `yes/no` | `yes/no` | `yes/no` | `pass/warn/fail` |  |
| 偏差表 | `<file>` | `yes/no` | `yes/no` | `yes/no` | `pass/warn/fail` |  |

`.xlsx`、技术参数表、货物清单、偏差表不得只做普通文本向量化。

## 6. 图片资产检查

| evidence_type | 资产数 | 代表文件 | 可用于问答 | 可用于图文写作 | 质量 | 说明 |
| --- | ---: | --- | --- | --- | --- | --- |
| `business_license` | 0 |  | `yes/no` | `yes/no` | `pass/warn/fail` |  |
| `certification` | 0 |  | `yes/no` | `yes/no` | `pass/warn/fail` |  |
| `production_capacity` | 0 |  | `yes/no` | `yes/no` | `pass/warn/fail` |  |
| `testing_capacity` | 0 |  | `yes/no` | `yes/no` | `pass/warn/fail` |  |
| `green_low_carbon` | 0 |  | `yes/no` | `yes/no` | `pass/warn/fail` |  |
| `inspection_report` | 0 |  | `yes/no` | `yes/no` | `pass/warn/fail` |  |

图片资产最低要求：

- 有稳定 `asset_id`。
- 有 `source_file`、`page_no` 或原始图片路径。
- 有 `enterprise`、`doc_owner`、`source_domain`、`evidence_type`。
- 泰昌资产必须 `reference_only=false`。
- 河北豪乾参考稿图片不得进入泰昌企业事实选图候选。

## 7. Metadata 完整性

| 检查项 | 通过标准 | 结果 |
| --- | --- | --- |
| `source_domain` | 每个文件必填 | `pass/warn/fail` |
| `doc_owner` | 每个文件必填 | `pass/warn/fail` |
| 泰昌企业事实 | `enterprise=泰昌` 且 `fact_source_allowed_for_enterprise=true` | `pass/warn/fail` |
| 辽宁招标资料 | `source_domain=tender_requirement` 且不作为企业事实 | `pass/warn/fail` |
| 河北豪乾参考稿 | `reference_only=true` 且 `citation_policy=reference_style_only` | `pass/warn/fail` |
| 租户可见性 | 泰昌内部资料为 `tenant_visibility=taichang_only` | `pass/warn/fail` |
| 回滚字段 | 有 `ingestion_batch_id`、`content_sha256`、`doc_version` | `pass/warn/fail` |

## 8. 召回与真实链路回归

| 回归项 | 命令或证据 | 结果 |
| --- | --- | --- |
| Base Recall@5 | `scripts/rag/eval_recall.py --k 5` |  |
| 泰昌/辽宁专项 Recall@5 | `--testset tests/rag/customer_liaoning_taichang_testset.jsonl` |  |
| 禁用关键词命中 | 专项评测 forbidden hit |  |
| 智能问答图片 | 泰昌问题返回泰昌资产图片 |  |
| 标书图文写作 | `withImages=true` 章节生成命中真实资产 URL |  |
| DOCX 导出 | 打开文档检查图片、目录、页码、页眉页脚 |  |

## 9. Blocker 与人工复核

| 优先级 | 问题 | 影响 | 负责人 | 截止或处理方式 |
| --- | --- | --- | --- | --- |
| P0 |  | 阻断入库或阻断真实标书输出 |  |  |
| P1 |  | 可入库但需业务确认 |  |  |
| P2 |  | 质量优化项 |  |  |

## 10. 结论

选择一项：

- `ready_for_ingestion`：可以正式入库。
- `ready_with_warnings`：可以入库，但必须把 warn 项写入 todo 或客户确认清单。
- `blocked`：不得正式入库，需补解析、补 metadata 或补客户资料。

结论说明：

```text
<写明本批是否可入库、哪些资料域可用、哪些文件/规格/图片仍需确认。>
```

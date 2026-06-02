# 客户资料解析 QA 清单

> 批次：`customer_jx_sx_20260602_p1`
> 测试集：`tests/rag/customer_parse_qa_cases.jsonl`
> 评测脚本：`scripts/rag/eval_parse_quality.py`

## 目标

在正式 RAG 入库前，先确认本地解析产物没有丢失标书写作和知识库问答必需的关键证据。该 QA 不评估向量召回，只检查 `parsed_outputs/` 中的文本/表格产物是否包含指定关键词。

## 覆盖范围

| 类别 | 覆盖文件 |
| --- | --- |
| 主招标文件 | 江西 V2 招标文件、山西招标文件 |
| 招标公告 | 江西资格预审/资格后审公告、山西公告 |
| 投标注意事项 | 江西 `投标注意事项V3.docx` |
| 技术规范 | 江西铁附件、山西接地铁镀锌扁钢、山西不锈钢电缆支架 |
| 货物清单 | 江西 `1826AA`、山西 `0526AB` |
| 合同条款 | 履约保证金、交货条款 |

## 本次结果

| 指标 | 结果 |
| --- | ---: |
| QA 用例 | 12 |
| 命中 | 12 |
| 命中率 | 100.0% |
| 无候选文件 | 0 |

产物：

- `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/parse_qa_report.md`
- `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/parse_qa_report.json`

## 复现命令

```bash
python scripts/rag/eval_parse_quality.py \
  parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/manifest.json
```

## 结论

本地 `mammoth + LibreOffice + openpyxl` 解析链路在本批关键样本上通过 QA 门禁，可以进入 staging 入库和召回评测。该结论不代表所有后续客户资料都无需 MinerU；新批次仍需先跑 QA，若出现空文本、表格缺失、扫描件或复杂版式丢失，再切换 MinerU/人工复核。

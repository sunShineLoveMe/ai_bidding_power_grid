# 泰昌历史标书增量资产提取与入库报告

> 批次：`customer_taichang_historical_bid_20260713_p1_01_knowledge_only_v1`
> 执行方式：`execute`
> 生成时间：2026-07-13T22:17:05+08:00

## 总览

| 指标 | 数量 |
| --- | ---: |
| 策略自动接收候选 | 169 |
| 已实际提取文件 | 169 |
| 通过数据库入库门禁 | 0 |
| 实际写入 | 0 |
| 写入失败 | 0 |

## 去重与质量处置

| 处置 | 数量 |
| --- | ---: |
| `already_ingested` | 133 |
| `quality_review_required` | 5 |
| `same_evidence_existing` | 31 |

## 强制边界

- 所有入库项均为 `knowledge_only + allowed_for_bid=false + formal_bid_ready=false`。
- Word 内嵌页不得作为精确技术参数、证书有效性或检验报告实测值来源。
- 同名完整原始 PDF/整页资产已存在时，只建立追溯关系，不新建重复资产。
- 技术参数表另走结构化抽取和原始检验报告交叉校验，不从图片猜测数值或单位。

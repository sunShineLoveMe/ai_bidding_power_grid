# 泰昌历史标书复用 P0-06 分级自动接收与异常复核运行记录

> 日期：2026-07-13
> 范围：河北泰昌电力器材科技有限公司物资类投标试点
> 数据策略：离线分级，不写数据库、不修改 RAG、不改变 DOCX 选图

## 一、调整原因

泰昌主动提供《技术补充文件》《商务补充文件》用于系统整理和历史标书复用，已经构成来源文件处理授权。P0-06 v1 仍将 461 条候选全部等待人工审批，造成“已批准 0、可入库 0”，把来源授权和正式资产质量批准混为一谈。

本轮改为三段式分流：低风险知识资料自动接收，高风险/异常事实人工复核，重复/冲突/结构参考自动关联或阻断。自动接收只赋予 `knowledge_only` 处理资格，不赋予正式投标使用资格。

## 二、分流结果

| 指标 | 结果 |
| --- | ---: |
| 候选总数 | 896 |
| 来源授权覆盖 | 896 |
| 策略自动接收 | 169 |
| 异常人工复核 | 290 |
| 异常证据组 | 60 |
| 自动关联、阻断或仅参考 | 437 |
| 关联已有资产/证据包 | 272 |
| 策略批准 | 169 |
| 人工批准 | 0 |
| 可进入媒体提取和入库校验 | 169 |

169 条自动接收项包括绿色低碳资料 112、企业能力资料 35、生产制造能力资料 22。全部记录为：

```text
quality_tier_after_review=knowledge_only
review_status_after_review=policy_auto_accepted
allowed_for_bid=false
formal_bid_ready=false
ingestion_readiness=ready_for_extraction_and_validation
```

## 三、风险门禁

- 自动接收仅覆盖工艺流程、生产制造环境、绿色低碳、ESG、三废治理、绿色发展和智能制造等低风险章节。
- 证书、凭证、查询、绩效评价、股权、合同、中标、授权、人员、审计和保证金等章节显式排除。
- 证照、财务、人员、检验报告、产品参数、项目业绩、时效事实、敏感资料和疑似重复仍进入异常复核。
- 精确重复 270 条改为“关联已有资产”；同证据不同载体 2 条改为“关联同一证据包”，均不重复建业务主记录。
- 历史 Word 内嵌媒体尚未提取为独立文件，169 条只进入 P1-01 提取和质量校验，不代表已写数据库。

## 四、产物

- `scripts/rag/prepare_taichang_p0_06_asset_review.py`
- `docs/development/taichang-bid-v1-data/p0_06_review/asset_policy_auto_accepted.json/csv`
- `docs/development/taichang-bid-v1-data/p0_06_review/asset_review_candidates.json/csv`
- `docs/development/taichang-bid-v1-data/p0_06_review/asset_auto_blocked_or_reference.json/csv`
- `docs/development/taichang-bid-v1-data/p0_06_review/asset_approved_decisions.json/csv`
- `docs/development/taichang-bid-v1-data/p0_06_review/asset_ingestion_candidates.json/csv`
- `docs/development/taichang-bid-v1-data/p0_06_review/泰昌历史标书资产增量入库审批表.xlsx`

## 五、验证

| 验证项 | 结果 |
| --- | --- |
| P0-02 至 P1-02 联合专项 | PASS，48 passed |
| 后端全量回归 | PASS，400 passed，2 subtests passed，11 个既有弃用告警 |
| 工作簿原生读取 | PASS，5 个工作表、169 条自动接收、290 条异常复核、437 条关联/阻断/参考 |
| LibreOffice 转存回读 | PASS，工作表、行数和 8 组下拉校验保持完整 |
| Python 编译 | PASS |
| 差异检查 | PASS，`git diff --check` 无格式错误 |

## 六、门禁结论

本轮没有写数据库、没有修改 RAG 语料/metadata/召回、没有改变正式资产选图或 DOCX 导出，因此不执行 Base 30 + 泰昌专项 30 召回门禁和真实 stream。P1-01 完成 169 条候选的媒体提取、质量过滤和实际增量入库后，必须执行标准增量回归门禁与真实 `/api/knowledge/search/stream` 抽样；如后续提升为正式配图，还必须执行正式 DOCX 导出与 XML 审计。

# 泰昌历史标书复用 P0-03 只读解析运行记录

> 日期：2026-07-13
> 状态：PASS
> 试点主体：河北泰昌电力器材科技有限公司
> 解析方式：原生 DOCX XML、样式、编号、表格、媒体关系和 Word 目录页码
> MinerU/OCR：未调用
> 数据库：未写入

## 输入文件

- `assets/template_words/技术补充文件.docx`
- `assets/template_words/商务补充文件.docx`
- 对照招标文件：`assets/template_words/包1_完整招标文件_92475576192439826/SL2655招标文件-预审.docx`
- 去重基线：`docs/development/taichang-bid-v1-data/current_asset_baseline.json`

## 解析结果

| 指标 | 技术补充文件 | 商务补充文件 |
| --- | ---: | ---: |
| Word 声明页数 | 368 | 325 |
| 目录标题/正文标题匹配 | 73/73 | 61/61 |
| 表格 | 10 | 4 |
| 媒体文件 | 352 | 339 |
| 媒体出现次数 | 357 | 341 |
| 事实/参数候选 | 46 | 4 |
| 候选总记录 | 486 | 410 |

技术标 368 页的渲染分页标记完整；商务标渲染分页标记覆盖 323/325 页，但 61 个正文标题全部取得目录页码，因此章节页序完整，章节内部媒体页码仍标记为近似定位。

## 来源属性

两份泰昌历史参考骨架共 134 个章节。该产物只用于与当次项目动态骨架做差异对照，不是新项目最终目录：

| origin_type | 数量 |
| --- | ---: |
| `tender_mandated` | 34 |
| `tender_conditional` | 5 |
| `tender_scoring_derived` | 48 |
| `taichang_habitual_addition` | 5 |
| `reference_layout_only` | 29 |
| `uncertain` | 13 |

其中 39 个章节已与 SL2655 样本实际位于第六章的“投标文件格式”内容直接匹配，其余 95 个保持人工复核状态，没有被自动视为招标强制目录。该章节号仅是本样本来源位置，不构成其他项目的定位规则；后续项目必须对招标文件包全文语义定位并生成 `project_bid_skeleton.json`。

## 关键事实门禁

- `2024100312005501712`、`2024100312005501713` 已与现有结构化基线匹配，仅补充历史章节映射，不重复建立资产。
- `2024400312005505333`、`2025200312005503479` 当前仅有历史 Word 索引，标记 `needs_original_evidence`。
- “完全响应/符合招标文件要求”标记为 `generic_response_not_value`，禁止进入正式参数层。
- 产品清单规格标记为 `candidate_product_spec`，必须继续核验检验报告和当前货物清单覆盖关系。
- 698 次媒体出现全部为 `review_only + allowed_for_bid=false`，未解包为正式图片资产。

## 验证

| 验证项 | 结果 |
| --- | --- |
| Python 编译 | PASS |
| 定向测试 | PASS，9 passed（含 P0-02 基线测试） |
| JSON/CSV 行数一致 | PASS |
| 同源重跑确定性 | PASS，连续重跑的章节数、候选记录数与来源分类统计一致；`generated_at` 等运行字段不纳入内容确定性判断 |
| 章节来源字段完整 | PASS |
| 事实候选证据字段完整 | PASS |
| 正式资产误提升检查 | PASS，0 条 `formal_bid_ready`，0 条 `allowed_for_bid=true` |
| 媒体关系完整性 | PASS，无法解析关系 0 |

## 未执行项说明

- 本轮没有调用 MinerU/OCR；图片内部文字、签章、证书有效期和图片型表格数值不进入事实候选。
- 本轮没有新增资料入库、修改 metadata、召回策略或正式 DOCX 选图，因此不执行 Base 30 + 泰昌 30 增量召回门禁，也不执行正式 DOCX 导出。
- P0-04 才执行文件、图像、文本语义和业务主键四层去重；本轮只生成可追溯候选与来源标签。

## 输出

- `docs/development/taichang-bid-v1-data/taichang_technical_bid_candidate_inventory.json/csv`
- `docs/development/taichang-bid-v1-data/taichang_business_bid_candidate_inventory.json/csv`
- `docs/development/taichang-bid-v1-data/taichang_historical_reference_skeleton.json`
- `docs/development/taichang-historical-skeleton-tender-crosswalk-20260713.md`
- `docs/development/taichang-historical-bid-parse-quality-report-20260713.md`

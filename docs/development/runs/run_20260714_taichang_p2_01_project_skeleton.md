# P2-01 项目级招标规则与动态骨架执行记录

## 验收结论

P2-01 已完成。目录生成入口已从“历史标书/通用大纲优先”调整为“当次招标文件规则优先”，历史标书仅用于逐项差异对照，不得覆盖当前项目规则。当前 SL2655 验收样本不存在因历史标书内容过多而扩张目录的问题。

## 实现范围

- 原生读取 DOCX 格式表、投标文件组成、投标人须知和技术规范，结构化保存来源文件、章节、页码、文档角色、检测方式和置信度。
- 规则状态覆盖 `required`、`conditional`、`inherited_from_prequalification`、`supplement_allowed`、`update_required`、`not_applicable`、`forbidden`、`reference_only`。
- 记录批次/分标/包作用域和价格/商务/技术分册提交范围；价格按包，商务和技术按分标。
- 动态骨架先于历史参考生成；历史差异使用确定性标题/别名匹配，不使用模糊相似度决定章节。
- 编制页目录模式新增“目录已按本次招标文件核定”提示及纳入、排除、历史新增、条件变化和低置信度数量。

## SL2655 样本结果

| 项目 | 结果 |
| --- | ---: |
| 项目规则总数 | 43 |
| 纳入成稿目录 | 19 |
| 排除成稿目录 | 24 |
| 必选 | 16 |
| 条件适用 | 2 |
| 不适用 | 21 |
| 资格预审继承 | 1 |
| 允许补充 | 1 |
| 需要更新 | 1 |
| 禁止 | 1 |

价格文件纳入 3 条、按包提交；商务文件纳入 11 条、排除 10 条、按分标提交；技术文件纳入 5 条、排除 14 条、按分标提交。投标保证金判定为不适用；业绩、技术服务、售后、质量方案、生产装备、检测设备、制造工艺、认证证书、人员和检测报告等未勾选项不进入目录。

参数覆盖状态为 `PRODUCT_FAMILY_MATCHED_BUT_SPEC_NOT_COVERED`：泰昌 MPP 报告规格 `250×22`、断裂伸长率 `176%`，不能覆盖项目 `200×14`、断裂伸长率 `≥200%`，正式导出继续阻断。

## 交付物

- `docs/development/taichang-bid-v1-data/p2_01_project_skeleton/project_bid_skeleton.json`
- `docs/development/taichang-bid-v1-data/p2_01_project_skeleton/project_bid_rules.json`
- `docs/development/taichang-bid-v1-data/p2_01_project_skeleton/historical_skeleton_difference.json`
- `docs/development/taichang-bid-v1-data/p2_01_project_skeleton/scope_matrix.json`
- 《SL2655项目级投标编制规则清单》
- 《SL2655动态骨架与历史参考骨架差异清单》
- 《SL2655批次分标包规则作用域清单》

## 测试与真实回归

| 验证项 | 结果 |
| --- | --- |
| P2-01/章节规划定向测试 | 22 passed |
| 后端全量 | 446 passed、2 subtests passed、11 个既有弃用告警 |
| 前端生产构建 | PASS；仅有既有大分块提示 |
| 真实目录 SSE | PASS；HTTP 200、`text/event-stream`、结束事件完整、作用域正确 |
| 真实浏览器 | PASS；1440×960，目录核定提示和统计可见，控制台错误 0 |
| 浏览器截图 | `.playwright-cli/page-2026-07-14T04-11-08-469Z.png` |
| 真实知识库流 | PASS；返回 3 条泰昌事实，明确拒绝 `250×22` 跨规格证明 `200×14` |
| Base + 泰昌门禁 | PASS；详见 `docs/rag/runs/20260714_taichang_p2_01_project_skeleton_summary.md` |

## 门禁指标

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨角色串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100% | 0.944 | 0% | 0% |
| Base | qwen3-rerank | 96.7% | 100% | 0.944 | 0% | 0% |
| 泰昌专项 | off | 93.3% | 100% | 0.917 | 3.3% | 0% |
| 泰昌专项 | qwen3-rerank | 100% | 100% | 0.973 | 0% | 0% |

## 下一任务

P2-02 已开始：将 36 行参数、84 行业务台账、16 个证据包、2 行项目业绩、166 个结构化 RAG 分块和 133 条历史知识资产定向映射到当前动态章节，生成 `chapter_content_manifest` 和技术/商务正文抽样，不再以“能够召回”代替“正文实际使用”。

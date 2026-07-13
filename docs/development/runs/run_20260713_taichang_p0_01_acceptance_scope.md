# 泰昌专版 P0-01 验收口径锁定运行记录

> 日期：2026-07-13
> 状态：PARTIAL PASS（内部评估通过，外部确认项未完成）

## 执行内容

- 读取 SL2655 招标文件、第六章目录和 MPP 专用技术规范。
- 读取 SL265A 10kV 架空绝缘导线招标文件和货物清单路径。
- 核对泰昌 MPP/CPVC 结构化检验报告参数。
- 扫描 `assets/template_words` 与 `rag_seed/power_grid_resources/01_tender_documents` 下 28 份 XLSX 货物清单，按产品族和 250 规格检查正向候选。
- 调用真实 `/api/ready` 与 `/api/knowledge/search/stream` 验证参数问答、SL2655 规格覆盖和 SL265A 跨产品阻断。

## 测试结果

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 服务就绪 | PASS | `/api/ready`：数据库、Redis、Celery、模型配置均正常 |
| XLSX 扫描 | PASS | 28 份，解析错误 0；未发现 MPP/CPVC φ250 招标货物清单 |
| SL2655 参数提取 | PASS | 200 mm、14.0 mm、断裂伸长率≥200%、环刚度≥24 kN/m² |
| 泰昌 MPP 单参数问答 | PASS | 断裂伸长率 176%，报告 `2024100312005501712` |
| SL2655 规格覆盖问答 | PASS | 明确判定 250×22/176% 不覆盖 200×14/≥200% |
| SL265A 跨产品阻断问答 | PASS | 明确不得用 MPP/CPVC 资料证明 10kV 架空绝缘导线能力 |
| MPP 复合参数问答 | FAIL | 同时询问规格、环刚度、伸长率时仅召回环刚度并误报伸长率缺失；单参数查询正常 |
| 最终成稿正向样本 | BLOCKED | 当前文件集合无精确匹配项目；待客户补项目或补对应规格证据 |

## 真实链路记录

- `docs/rag/runs/run_20260713_taichang_p0_01_mpp_parameter_summary.md`
- `docs/rag/runs/run_20260713_taichang_p0_01_mpp_elongation_summary.md`
- `docs/rag/runs/run_20260713_taichang_p0_01_sl2655_coverage_summary.md`
- `docs/rag/runs/run_20260713_taichang_p0_01_sl265a_block_summary.md`

## 状态结论

- 已锁定 SL2655 和 SL265A 两类验收样本。
- 已锁定正向样本准入标准，但未锁定具体正向项目。
- P0-01 标记为进行中，不进入“全部完成”。
- 本轮未新增客户资料、未修改 metadata/召回算法、未写入数据库，因此未重跑 Base 30 + 泰昌 30 全量增量门禁；后续修复复合参数召回或新增正向项目资料时必须重跑。

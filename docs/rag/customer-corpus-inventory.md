# 江西/山西客户标书资料 Inventory

> 状态日期：2026-06-11
> 范围：客户提供的江西、山西、辽宁国家电网物资协议库存公开招标采购资料包，以及泰昌 MVP 试点企业资料。
> 目标：为 P1 真实标书 RAG 入库、跨批次负样本和表格结构化解析提供文件清单。

## 总览

| 省份 | 批次 | 物料/包 | 目录 | 入库优先级 |
| --- | --- | --- | --- | --- |
| 江西 | 2026 年第一次配网（省网）协议库存物资类公开招标采购 | 铁构件 / 包 1 | `rag_seed/power_grid_resources/01_tender_documents/20_国网江西电力2026年第一次配网省网协议库存物资类公开招标采购/` | P1 |
| 山西 | 2026 年第二次物资协议库存公开招标采购 | 铁构件 / 包 1 | `rag_seed/power_grid_resources/01_tender_documents/21_国网山西电力2026年第二次物资协议库存公开招标采购/` | P1 |
| 辽宁 | 2025 年第三次物资协议库存招标采购 | 电缆保护管 CPVC / MPP，CPVC 包 1-2、MPP 包 1-4 | `rag_seed/power_grid_resources/01_tender_documents/22_国网辽宁电力2025年第三次物资协议库存招标采购/` | P1 |
| 泰昌 | MVP 试点企业资料 | 企业资质、财务、生产、检测、绿色低碳材料 | `rag_seed/power_grid_resources/05_enterprise_documents/01_泰昌MVP试点企业资料/` | P1 |
| 泰昌 | 资质补充资料（2026-06-11） | Logo、检验报告、生产/检测/财务/绿色低碳/项目业绩补充材料 | `rag_seed/power_grid_resources/05_enterprise_documents/02_泰昌资质文件补充_20260611/` | P1A |

解析准备批次：

| 批次 ID | Manifest | 质量报告 | 状态 |
| --- | --- | --- | --- |
| `customer_jx_sx_20260602_p1` | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/manifest.json` | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/parse_quality_report.md` | 23 个 `.doc/.docx/.xlsx` 已解析，21 个归档文件已登记，`needs_review=0` |
| `customer_liaoning_taichang_20260606` | `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_inventory.json` | `docs/rag/liaoning-taichang-mvp-corpus-review.md` | 已完成解压和初步 inventory；尚未正式 OCR、分块、入库、评测 |
| `customer_taichang_supplement_20260611` | `parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/manifest.json` | `docs/rag/runs/run_20260611_taichang_supplement_full_summary.md` | 已完成 70 个文件 inventory，13 份文本资料入库，297 个正式图片资产入库，增量回归门禁 PASS |

当前解压后发现的核心文件类型：

| 类型 | 数量 | 处理策略 |
| --- | ---: | --- |
| `.docx` | 18 | 优先用 Mammoth/Docx 结构解析；大文件需检查标题层级和表格丢失 |
| `.doc` | 3 | 优先 LibreOffice 转 `.docx`，失败再走 MinerU/OCR |
| `.xlsx` | 2 | 用 openpyxl 结构化解析，不能只转长文本 |
| `.zip` | 17 | 已解压或作为原始包保留，不直接入 RAG |
| `.rar` | 1 | 山西铁构件历史技术规范包，需后续解包确认 |
| `.zb` / `.sign` | 3 | 平台/签名文件，暂不入 RAG，仅做归档 |

## 江西批次核心文件

| 文件 | 类型 | 角色建议 | metadata 建议 | 处理优先级 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `（资格预审）国网江西电力2026年第一次配网（省网）协议库存物资类公开招标采购招标文件V2.docx` | docx | `main_tender_file` | `province=江西`、`batch_no=2026-01`、`package_no=1`、`material_category=铁构件`、`qualification_mode=prequalification` | P1-2 | 约 22M，主招标文件，需抽资格/评标/否决项 |
| `（资格预审）国网江西电力2026年第一次配网（省网）协议库存物资类公开招标采购招标公告.docx` | docx | `tender_notice` | 同上，`qualification_mode=prequalification` | P1-2 | 约 21M，公告文件 |
| `（资格后审）国网江西电力2026年第一次配网（省网）协议库存物资类公开招标采购招标公告.docx` | docx | `tender_notice` | 同上，`qualification_mode=postqualification` | P1-2 | 约 21M，适合与资格预审做对照 |
| `投标注意事项V3.docx` | docx | `bid_instructions` | 同上 | P1-2 | 约 15K，适合转合规/风险规则 |
| `国家电网江西公司物资固化技术规范书_铁附件.doc` | doc | `technical_spec` | 同上，`material_category=铁附件/铁构件` | P1-3 | 约 1.4M，老 `.doc`，优先 LibreOffice 转换 |
| `货物清单_1826AA_铁构件20260403_193635_546.xlsx` | xlsx | `goods_list` | `province=江西`、`batch_no=2026-01`、`package_no=1`、`package_code=1826AA`、`material_category=铁构件` | P1-4 | 约 4.7K，表格结构化优先 |
| `5.120 10kV及以下协议库存货物采购合同通用条款（材料类）（2024版）.docx` | docx | `contract_general_terms` | 同上 | P1-2 | 合同通用条款 |
| `5.120 10kV及以下协议库存货物采购合同（材料类）（2024版）.docx` | docx | `contract_special_terms` | 同上 | P1-2 | 合同模板 |
| `合同专用条款其他文件202510290022128.docx` | docx | `contract_special_terms` | 同上 | P1-2 | 合同专用条款 |

## 山西批次核心文件

| 文件 | 类型 | 角色建议 | metadata 建议 | 处理优先级 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `国网山西电力2026年第二次物资协议库存公开招标采购招标文件.docx` | docx | `main_tender_file` | `province=山西`、`batch_no=2026-02`、`package_no=1`、`material_category=铁构件` | P1-2 | 约 4.0M，主招标文件 |
| `国网山西电力2026年第二次物资协议库存公开招标采购招标公告.docx` | docx | `tender_notice` | 同上 | P1-2 | 约 3.4M，公告文件 |
| `国网山西省电力公司第一次固化ID编制接地铁(05GH-500075342-00002).doc` | doc | `technical_spec` | 同上，`material_category=接地铁`、`solidified_id=05GH-500075342-00002` | P1-3 | 约 50K，接地铁核心技术规范 |
| `铁构件技术规范书-不锈钢电缆支架.doc` | doc | `technical_spec` | 同上，`material_category=不锈钢电缆支架` | P1-3 | 约 217K，细分物料技术规范 |
| `接地铁镀锌扁钢（角钢、圆钢）-技术规范书（上传）.docx` | docx | `technical_spec` | 同上，`material_category=接地铁镀锌扁钢/角钢/圆钢` | P1-2 | 约 32K，首批建议重点入库 |
| `货物清单_0526AB_铁构件20260430_153228_019.xlsx` | xlsx | `goods_list` | `province=山西`、`batch_no=2026-02`、`package_no=1`、`package_code=0526AB`、`material_category=铁构件` | P1-4 | 约 16K，表格结构化优先 |
| `5.120 10kV及以下协议库存货物采购合同通用条款（材料类）（2024版）.docx` | docx | `contract_general_terms` | 同上 | P1-2 | 合同通用条款 |
| `5.120 10kV及以下协议库存货物采购合同（材料类）（2024版）.docx` | docx | `contract_special_terms` | 同上 | P1-2 | 合同模板 |
| `合同专用条款其他文件20250331100191.docx` | docx | `contract_special_terms` | 同上 | P1-2 | 合同专用条款 |

## 辽宁 / 泰昌 MVP 批次核心文件

详细评估见 `docs/rag/liaoning-taichang-mvp-corpus-review.md`。

| 文件 | 类型 | 角色建议 | metadata 建议 | 处理优先级 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `国网辽宁电力2025年第三次物资协议库存招标采购_招标文件包.zip` | zip | `raw_tender_package` | `province=辽宁`、`batch_no=2025-03`、`package_code=2225AC`、`material_category=电缆保护管CPVC/MPP` | P1 | 原始包保留，多层 zip 已解压 |
| `国网辽宁电力2025年第三次物资协议库存招标采购招标文件.docx` | docx | `main_tender_file` | 同上，按 CPVC/MPP 包号补充 `package_no` | P1 | 每包均有主招标文件 |
| `货物清单_2225AC_电缆保护管CPVC*.xlsx` | xlsx | `goods_list` | `material_category=电缆保护管CPVC`、`package_no=包1/包2` | P1 | 去重后 CPVC 覆盖 φ50/100/150/200；xlsx dimension 异常，需 XML 兼容解析 |
| `货物清单_2225AC_电缆保护管MPP*.xlsx` | xlsx | `goods_list` | `material_category=电缆保护管MPP`、`package_no=包1-包4` | P1 | 去重后 MPP 覆盖 φ100/150/175/200 |
| `技术补充文件_电缆保护管CPVC.pdf` | pdf | `technical_response_reference` | `doc_owner=河北豪乾`、`reference_only=true`、`material_category=电缆保护管CPVC` | P1 | 468 页，非泰昌主体，只能作参考 |
| `泰昌资料.zip` | zip | `raw_enterprise_package` | `enterprise=泰昌`、`privacy_level=private` | P1 | 原始包保留，已解压 |
| `泰昌资料/*` | pdf/jpg | `enterprise_evidence` | `enterprise=泰昌`、`evidence_type=finance/certification/production/testing/green_low_carbon` | P1 | 扫描件多，需 MinerU/OCR 和脱敏 |
| `商务投标文件-中标，按投标人制作.pdf` | pdf | `winning_bid_reference` | `doc_owner=河北豪乾`、`reference_only=true`、`material_category=电缆保护管CPVC/MPP/NHAP` | P1 | 362 页，非泰昌主体，禁止作为泰昌事实来源 |

## 泰昌资质补充资料（2026-06-11）

| 文件/目录 | 类型 | 角色建议 | metadata 建议 | 处理状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `泰昌资质文件(补充).zip` | zip | `raw_enterprise_package` | `enterprise=泰昌`、`source_domain=enterprise_fact`、`tenant_visibility=taichang_only` | 已落位并解压 | 原始包保留在 `05_enterprise_documents/02_泰昌资质文件补充_20260611/` |
| `assets/icons/taichang.png` / `泰昌官方Logo.png` | png | `brand_logo` | `evidence_type=brand_logo`、`target_library=qualification_library` | 已入库 | 可用于标书封面、页眉、企业介绍页，需遵循正式导出版式 |
| CPVC/MPP 内径 250 检验报告 | pdf/jpg | `inspection_report` | `evidence_type=inspection_report`、`target_library=product_library` | 文本与整页图片已入库 | 报告编号与既有结构化参数一致：MPP `2024100312005501712`，CPVC `2024100312005501713` |
| 生产线、产品实物、检测设备图片 | jpg/png/pdf | `enterprise_evidence` | `evidence_type=production_capacity/testing_capacity` | 正式图片资产已入库 | 可用于生产制造能力、试验检测能力章节配图 |
| 财务、资质证书、绿色低碳、项目业绩材料 | pdf/jpg/png | `enterprise_evidence` | `evidence_type=finance/certification/green_low_carbon/project_performance` | 文本可抽取项与整页图片已入库 | 包含合同协议书和中标通知书，作为项目业绩证明材料 |
| 公章、法人章、签名图片 | png/jpg | `restricted_signature_seal` | `allowed_for_bid=false`、`fact_source_allowed_for_enterprise=false` | 仅归档，不自动用于标书 | 需人工授权后才可用于签章流程 |

## 首批真实场景建议

优先选择“铁构件 / 接地铁”作为 P1 首个真实物料场景，原因：

- 江西、山西均有铁构件包，可做跨省/跨批次负样本；
- 山西有接地铁、镀锌扁钢、角钢、圆钢、不锈钢电缆支架等细分技术规范；
- 两省均有货物清单 `.xlsx`，可验证表格结构化解析和精确过滤；
- 主招标文件、公告、合同、技术规范、货物清单齐全，覆盖问答、写作、合规、表格四类 RAG 场景。

## 后续入库顺序

1. `.docx` 主招标文件/公告/投标注意事项：抽资格要求、否决项、评分/响应要求。
2. `.doc` 技术规范：LibreOffice 转换为 `.docx/.md`，失败标 `needs_review`。
3. `.xlsx` 货物清单：openpyxl 结构化解析为原始表格、检索摘要、行级记录三形态。
4. 合同文件：按通用/专用条款分 `contract_general_terms` / `contract_special_terms`。
5. 写入 metadata：至少包含 `province/batch_no/package_no/package_code/material_category/doc_role/source_file`。
6. 扩展测试集：加入江西问句、山西问句、跨省负样本和表格精确查询样本。

## 待确认问题

- 江西大文件 `.docx` 约 21-22M，需确认 Mammoth 解析是否完整保留标题层级和关键表格。
- `.zb` 平台文件是否包含可解析文本，当前暂不入库。
- 山西 `.rar` 是否需要解包并纳入历史技术规范对比。
- 客户资料是否需要脱敏后再进入持久化 RAG 库。
- 辽宁/泰昌批次中，河北豪乾参考稿必须与泰昌企业事实隔离；泰昌敏感材料需先确认脱敏和授权边界。

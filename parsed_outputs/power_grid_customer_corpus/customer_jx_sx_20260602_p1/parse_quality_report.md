# 江西/山西客户资料解析质量报告

> 批次：`customer_jx_sx_20260602_p1`
> 生成时间：2026-06-02T16:20:54

## 总览

| 指标 | 数量 |
| --- | ---: |
| 文件总数 | 44 |
| 已解析 | 23 |
| 仅归档 | 21 |
| 需复核 | 0 |
| 文本字符数 | 650301 |
| 表格行数 | 107 |

## 解析结果

| 状态 | 省份 | 角色 | 类型 | 文件 | 解析器 | 输出 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| archived | 江西 | `archive_only` | zip | `包1_完整招标文件_89112639724864228.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| archived | 江西 | `archive_only` | sign | `bidpkgsign20260403_193512_348.sign` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| archived | 江西 | `archive_only` | zip | `包1_技术规范书_89112634200096205.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| archived | 江西 | `archive_only` | zip | `国网江西省电力有限公司_2021年江西公司配省网协议库存固化ID编制（G00K-500118948-00001）.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 江西 | `technical_spec` | doc | `国家电网江西公司物资固化技术规范书_铁附件.doc` | libreoffice_doc_to_docx+mammoth | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/国家电网江西公司物资固化技术规范书_铁附件_52360b5128.md` | converted_docx=parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/converted_docx/国家电网江西公司物资固化技术规范书_铁附件.docx；Message(type='warning', message='A |
| parsed | 江西 | `technical_spec` | docx | `国网江西省电力有限公司_2021年江西公司配省网协议库存固化ID编制（G00K-500118948-00001）.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/国网江西省电力有限公司_2021年江西公司配省网协议库存固化ID编制_G00K-500118948-00001_6971512b3d.md` |  |
| archived | 江西 | `archive_only` | zip | `合同文件.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 江西 | `contract_general_terms` | docx | `5.120 10kV及以下协议库存货物采购合同通用条款（材料类）（2024版）.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/5.120_10kV及以下协议库存货物采购合同通用条款_材料类_2024版_27c942f02b.md` | Message(type='warning', message='An unrecognised element was ignored: w:permStart')；Message(type='warning', message='An unrecognised element was ignored: w:tblP |
| parsed | 江西 | `contract_special_terms` | docx | `5.120 10kV及以下协议库存货物采购合同（材料类）（2024版）.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/5.120_10kV及以下协议库存货物采购合同_材料类_2024版_f660ddf36e.md` | Message(type='warning', message='An unrecognised element was ignored: w:tblPrEx') |
| archived | 江西 | `archive_only` | zip | `合同专用条款文件.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 江西 | `contract_special_terms` | docx | `合同专用条款其他文件202510290022128.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/合同专用条款其他文件202510290022128_fd602a98db.md` | Message(type='warning', message='An unrecognised element was ignored: w:tblPrEx') |
| archived | 江西 | `archive_only` | zip | `国网江西电力2026年第一次配网（省网）协议库存物资类公开招标采购招标公告.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 江西 | `bid_instructions` | docx | `投标注意事项V3.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/投标注意事项V3_b254c5a57b.md` |  |
| parsed | 江西 | `tender_notice` | docx | `（资格后审）国网江西电力2026年第一次配网（省网）协议库存物资类公开招标采购招标公告.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/资格后审_国网江西电力2026年第一次配网_省网_协议库存物资类公开招标采购招标公告_d14daf991a.md` | Message(type='warning', message='An unrecognised element was ignored: v:path')；Message(type='warning', message='An unrecognised element was ignored: v:fill') |
| parsed | 江西 | `tender_notice` | docx | `（资格预审）国网江西电力2026年第一次配网（省网）协议库存物资类公开招标采购招标公告.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/资格预审_国网江西电力2026年第一次配网_省网_协议库存物资类公开招标采购招标公告_6063786e8c.md` | Message(type='warning', message='An unrecognised element was ignored: v:path')；Message(type='warning', message='An unrecognised element was ignored: v:fill') |
| parsed | 江西 | `goods_list` | xlsx | `货物清单_1826AA_铁构件20260403_193635_546.xlsx` | openpyxl | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/tables/货物清单_1826AA_铁构件20260403_193635_546_b18faec8fe.json` |  |
| archived | 江西 | `archive_only` | zip | `（资格预审）国网江西电力2026年第一次配网（省网）协议库存物资类公开招标采购招标文件V2.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| archived | 江西 | `archive_only` | zb | `1826AA招标文件.zb` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 江西 | `main_tender_file` | docx | `（资格预审）国网江西电力2026年第一次配网（省网）协议库存物资类公开招标采购招标文件V2.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/资格预审_国网江西电力2026年第一次配网_省网_协议库存物资类公开招标采购招标文件V2_a00555b1ec.md` | Message(type='warning', message='An unrecognised element was ignored: v:path')；Message(type='warning', message='An unrecognised element was ignored: v:fill') |
| archived | 江西 | `archive_only` | zip | `国网江西电力2026年第一次配网（省网）协议库存物资类公开招标采购_招标文件包(1).zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| archived | 山西 | `archive_only` | zip | `包1_完整招标文件_64281725749688283.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| archived | 山西 | `archive_only` | sign | `bidpkgsign20260430_153133_048.sign` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| archived | 山西 | `archive_only` | zip | `包1_技术规范书_64281724551341496.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| archived | 山西 | `archive_only` | zip | `国网山西省电力公司_2022年山西公司物资类采购结构化固化ID编制（G00F-500118948-00004）.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 山西 | `technical_spec` | docx | `国网山西省电力公司_2022年山西公司物资类采购结构化固化ID编制（G00F-500118948-00004）.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/国网山西省电力公司_2022年山西公司物资类采购结构化固化ID编制_G00F-500118948-00004_7b80dfb41c.md` |  |
| archived | 山西 | `archive_only` | zip | `国网山西省电力公司_2025年山西公司物资类采购结构化固化ID编制（G00F-500118948-00007）.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 山西 | `technical_spec` | docx | `国网山西省电力公司_2025年山西公司物资类采购结构化固化ID编制（G00F-500118948-00007）.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/国网山西省电力公司_2025年山西公司物资类采购结构化固化ID编制_G00F-500118948-00007_045c22cd97.md` |  |
| archived | 山西 | `archive_only` | rar | `山西省电力公司-配网标准化物资固化技术规范书_铁构件.rar` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 山西 | `technical_spec` | doc | `国网山西省电力公司第一次固化ID编制接地铁(05GH-500075342-00002).doc` | libreoffice_doc_to_docx+mammoth | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/国网山西省电力公司第一次固化ID编制接地铁_05GH-500075342-00002_51d6ec8e35.md` | converted_docx=parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/converted_docx/国网山西省电力公司第一次固化ID编制接地铁(05GH-500075342-00002).docx；Message(type |
| archived | 山西 | `archive_only` | zip | `国网山西省电力有限公司_2025年山西公司物资类采购结构化固化ID编制（G00F-500082436-00001）.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 山西 | `technical_spec` | docx | `国网山西省电力有限公司_2025年山西公司物资类采购结构化固化ID编制（G00F-500082436-00001）.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/国网山西省电力有限公司_2025年山西公司物资类采购结构化固化ID编制_G00F-500082436-00001_acd26f91c2.md` |  |
| parsed | 山西 | `technical_spec` | docx | `接地铁镀锌扁钢（角钢、圆钢）-技术规范书（上传）.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/接地铁镀锌扁钢_角钢_圆钢_-技术规范书_上传_6f3fbc57e3.md` |  |
| archived | 山西 | `archive_only` | zip | `国网山西省电力有限公司_2026年山西公司物资类采购结构化固化ID编制（G00F-500118948-00008）.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 山西 | `technical_spec` | docx | `国网山西省电力有限公司_2026年山西公司物资类采购结构化固化ID编制（G00F-500118948-00008）.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/国网山西省电力有限公司_2026年山西公司物资类采购结构化固化ID编制_G00F-500118948-00008_83bf728b78.md` |  |
| parsed | 山西 | `technical_spec` | doc | `铁构件技术规范书-不锈钢电缆支架.doc` | libreoffice_doc_to_docx+mammoth | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/铁构件技术规范书-不锈钢电缆支架_87faeba272.md` | converted_docx=parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/converted_docx/铁构件技术规范书-不锈钢电缆支架.docx |
| archived | 山西 | `archive_only` | zip | `合同文件.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 山西 | `contract_general_terms` | docx | `5.120 10kV及以下协议库存货物采购合同通用条款（材料类）（2024版）.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/5.120_10kV及以下协议库存货物采购合同通用条款_材料类_2024版_7bf7dfc201.md` | Message(type='warning', message='An unrecognised element was ignored: w:permStart')；Message(type='warning', message='An unrecognised element was ignored: w:tblP |
| parsed | 山西 | `contract_special_terms` | docx | `5.120 10kV及以下协议库存货物采购合同（材料类）（2024版）.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/5.120_10kV及以下协议库存货物采购合同_材料类_2024版_aaba9e23ed.md` | Message(type='warning', message='An unrecognised element was ignored: w:tblPrEx') |
| archived | 山西 | `archive_only` | zip | `合同专用条款文件.zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |
| parsed | 山西 | `contract_special_terms` | docx | `合同专用条款其他文件20250331100191.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/合同专用条款其他文件20250331100191_42b4414ce8.md` | Message(type='warning', message='An unrecognised element was ignored: w:tblPrEx')；Message(type='warning', message='An unrecognised element was ignored: v:path') |
| parsed | 山西 | `tender_notice` | docx | `国网山西电力2026年第二次物资协议库存公开招标采购招标公告.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/国网山西电力2026年第二次物资协议库存公开招标采购招标公告_ff3968af64.md` | Message(type='warning', message='An unrecognised element was ignored: w:tblPrEx')；Message(type='warning', message='An unrecognised element was ignored: v:path') |
| parsed | 山西 | `main_tender_file` | docx | `国网山西电力2026年第二次物资协议库存公开招标采购招标文件.docx` | mammoth_docx | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/texts/国网山西电力2026年第二次物资协议库存公开招标采购招标文件_082e75eeb3.md` | Message(type='warning', message='An unrecognised element was ignored: w:tblPrEx')；Message(type='warning', message='An unrecognised element was ignored: v:path') |
| parsed | 山西 | `goods_list` | xlsx | `货物清单_0526AB_铁构件20260430_153228_019.xlsx` | openpyxl | `parsed_outputs/power_grid_customer_corpus/customer_jx_sx_20260602_p1/tables/货物清单_0526AB_铁构件20260430_153228_019_ac3cc66908.json` |  |
| archived | 山西 | `archive_only` | zip | `国网山西电力2026年第二次物资协议库存公开招标采购_招标文件包(1).zip` | archive_only | `-` | archive/signature/platform file is preserved but not parsed for RAG |

## 入库前结论

- `parsed` 文件可以进入下一步清洗、父子分块 dry-run。
- `archived` 文件只保留原始归档，不进入 RAG。
- `needs_review` 文件不得静默入库，必须先补依赖、换解析器或人工复核。
- `.xlsx` 必须以 manifest 中的表格 JSON 为基础生成结构化表和检索摘要，不能只按普通长文本入库。

# run_20260626_reference_template_volume_docx — 参考模板样式分册 DOCX 回归

- 生成时间：2026-06-26T16:16:37
- 项目 ID：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 状态：PASS

## 验证范围

- 参考文件：`assets/template_words/5d2a2c833dad4bb3b3ccc0856f755b54.docx`、`assets/template_words/1523993.doc`。
- 策略：参考样式规则扩展 `formal_bid_standard`，不直接套打正文。
- 链路：`build_project_bid_markdown(volume_type, with_images=true) -> convert_md_to_word(return_report=true) -> refresh_docx_fields_with_soffice`。

## 结果

| 分册 | 文件类型 | 章节 | 图片选中/插入/失败 | 正文图片尺寸 | 表格 | 字段刷新 | 目录 | 结果 |
| --- | --- | ---: | --- | --- | ---: | --- | --- | --- |
| technical | 技术投标文件 | 50 | 24 / 24 / 0 | 5.8x8.2:24 | 110 | refreshed | PAGEREF+点引导线 | PASS |
| business | 商务投标文件 | 52 | 17 / 17 / 0 | 5.8x8.2:17 | 56 | refreshed | PAGEREF+点引导线 | PASS |

## 输出文件

- 技术投标文件 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.docx`
- 商务投标文件 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.docx`

## 检查结论

- 技术标和商务标均已应用参考模板元数据、正式排版、目录域、统一图片显示尺寸和字段刷新。

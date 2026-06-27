# run_20260626_body_xiaosi_1_5_line_spacing — 正文小四与 1.5 倍行距 DOCX 回归

- 生成时间：2026-06-26T16:27:56
- 项目 ID：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 状态：PASS

## 验证范围

- 正文字号：仿宋_GB2312 小四 `12pt`。
- 正文行距：`1.5` 倍行距。
- 正文首行缩进：`2` 字符，即 `24pt`。
- 链路：`build_project_bid_markdown(volume_type, with_images=true) -> convert_md_to_word(return_report=true) -> refresh_docx_fields_with_soffice`。

## 结果

| 分册 | 文件类型 | 章节 | 正文样式 | 图片选中/插入/失败 | 表格 | 字段刷新 | 结果 |
| --- | --- | ---: | --- | --- | ---: | --- | --- |
| technical | 技术投标文件 | 50 | 12.0pt / ONE_POINT_FIVE 1.5 / 缩进24.0pt | 24 / 24 / 0 | 110 | refreshed | PASS |
| business | 商务投标文件 | 52 | 12.0pt / ONE_POINT_FIVE 1.5 / 缩进24.0pt | 17 / 17 / 0 | 56 | refreshed | PASS |

## 输出文件

- 技术投标文件 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.docx`
- 商务投标文件 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.docx`

## 检查结论

- 技术标和商务标均已应用正文小四、1.5 倍行距，并完成字段刷新、目录、表格和图片尺寸回归。

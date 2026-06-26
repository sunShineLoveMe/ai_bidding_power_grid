# 2026-06-26 新疆技术/商务参考模板分册真实复验

## 背景

用户要求对前述 5 个 DOCX 正式导出问题做真实复验，确认新疆中标技术标/商务标参考 profile 是否已经约束当前技术标、商务标导出。

重点复验问题：

1. 页眉不得带公司 Logo 图片。
2. 目录条目字体不得加粗，点引导线需更密集、右侧页码对齐。
3. 章节目录标题不得重复父标题或读起来混乱。
4. 全文标题和正文不得出现蓝色等非正式颜色。
5. 主要章节/正式表单切换需分页，不得连续挤在同一页底部。

## 真实链路

- 项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 技术标链路：`build_project_bid_markdown(volume_type=technical, with_images=true) -> convert_md_to_word(return_report=true) -> refresh_docx_fields_with_soffice`
- 商务标链路：`build_project_bid_markdown(volume_type=business, with_images=true) -> convert_md_to_word(return_report=true) -> refresh_docx_fields_with_soffice`
- PDF 预览：LibreOffice `--convert-to pdf`
- PDF 抽样：`pdftoppm` 抽取技术/商务目录页和正文页

## 本轮修正

- 在 `backend/export/md_to_word.py` 中补充正式表单分页规则：
  - 当正文中的正式表单小标题从一种表单类型切换到另一种表单类型时，例如 `投标函 -> 法定代表人授权书`，自动插入实际分页符。
  - 不使用 `pageBreakBefore`，避免 Word/WPS 显示格式标记时出现黑色方块。
- 新增单元测试：`test_formal_form_subheading_switch_starts_on_new_page`。

## 输出文件

- 技术标 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.docx`
- 商务标 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.docx`
- 技术标 PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.pdf`
- 商务标 PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.pdf`
- JSON 审计：`docs/development/runs/run_20260626_xinjiang_profile_volume_revalidation.json`
- PDF 抽样截图：`docs/development/runs/run_20260626_xinjiang_profile_volume_revalidation_pages/`

## 审计结果

| 检查项 | 技术标 | 商务标 |
| --- | --- | --- |
| 模板 profile | `technical_bid_standard` | `business_bid_standard` |
| 字段刷新 | `refreshed` | `refreshed` |
| 页眉 Logo 图片 | 无 | 无 |
| 目录真实加粗 run | 0 | 0 |
| 目录点引导线 | 51/51 | 54/54 |
| 非黑色文字 | 无 | 无 |
| 重复父标题模式 | 无 | 无 |
| H1/H2 分页 | 13/13 | 21/21 |
| 正式表单切换分页 | 不涉及 | 15 |
| Failures | 无 | 无 |

说明：目录 XML 中存在 `<w:b w:val="false">`，这是显式取消加粗，不是加粗显示；审计按 `w:val=false` 不计入加粗。

## PDF 可视化复核

- 技术标第 2 页目录：页眉无 Logo，目录条目不加粗，点引导线密集，页码右对齐。
- 技术标第 5 页正文：标题/正文均为黑色，表格边框清晰。
- 商务标第 2 页目录：页眉无 Logo，目录条目不加粗，点引导线密集，页码右对齐。
- 商务标第 5 页正文：`二、法定代表人授权书` 已不再挤在页底，正式表单切换分页生效。

## 自动化回归

- `.venv/bin/python -m pytest tests/test_docx_export.py -q`
  - 结果：`44 passed, 1 warning`
- `.venv/bin/python -m pytest tests/test_docx_export.py tests/test_celery_export_tasks.py -q`
  - 结果：`55 passed, 7 warnings`

## 结论

本轮真实复验通过。当前技术标/商务标导出确实走新疆参考模板族，且针对用户截图中的 5 个问题，已通过真实 DOCX、LibreOffice 字段刷新、PDF 转换和截图抽样复核。

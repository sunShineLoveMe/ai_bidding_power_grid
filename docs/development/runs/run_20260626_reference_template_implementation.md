# run_20260626_reference_template_implementation — 技术标/商务标参考模板族落地

- 时间：2026-06-26
- 项目 ID：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 状态：PASS

## 背景

客户提供兄弟公司刚中标的正式标书参考文件：

- `assets/template_words/技术文件 - 10kV架空绝缘导线-新疆.docx`
- `assets/template_words/商务文件 - 10kV架空绝缘导线-新疆(1).docx`

审阅后确认两份文件是正式成稿分册，不是空白套打模板。技术标约 `96MB / 512页 / 82张表 / 408个媒体资源`，商务标约 `31MB / 177页 / 168个媒体资源`。本轮只抽取版式、目录组织和分册结构，不复用兄弟公司事实内容。

## 实现内容

- 新增 `technical_bid_standard` 模板 profile。
- 新增 `business_bid_standard` 模板 profile。
- 两者归属 `formal_bid_xinjiang_sgcc_reference` 模板族。
- 导出器根据封面字段 `文件类型` 自动选择：
  - `技术投标文件` -> `technical_bid_standard`
  - `商务投标文件` -> `business_bid_standard`
  - 其他/完整标书 -> `formal_bid_standard`
- 技术/商务 profile 应用参考稿版式：
  - A4。
  - 上/下边距 `2.54cm`。
  - 左/右边距 `3.17cm`。
  - 页眉距 `1.5cm`。
  - 页脚距 `1.75cm`。
  - 目录支持 1-4 级。
  - 目录条目宋体 `10.5pt`、非加粗、`15pt` 行距、点引导线。
  - 页眉页脚宋体 `9pt`。
  - 页眉不插 Logo。
  - 文本保持黑白，表头灰阶。
- 模板 metadata 记录：
  - `template_id`
  - `template_family`
  - `reference_path`
  - `runtime_policy`
  - `reference_outline`
  - `margins_cm`
  - `toc_font`
  - `toc_max_level`

## 真实用户链路

本轮按本地正式环境处理：

1. 重启 Celery worker，确保使用最新代码。
2. 使用本地登录 API `admin / 12345678` 获取登录态。
3. 调用真实导出接口：
   - `POST /api/bidding/interpretations/<project_id>/download-docx`
   - `{"withImages": true, "volumeType": "technical"}`
   - `{"withImages": true, "volumeType": "business"}`
4. 轮询：
   - `GET /api/bidding/interpretations/<project_id>/export-tasks/<task_id>`
5. Celery 实际执行：
   - `build_project_bid_markdown`
   - `convert_md_to_word`
   - `refresh_docx_fields_with_soffice`
6. LibreOffice 额外转换 PDF，用于抽样截图核验。

## 输出文件

技术标：

- DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.docx`
- PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.pdf`

商务标：

- DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.docx`
- PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.pdf`

## 验收结果

- 单元/集成测试：
  - 命令：`.venv/bin/python -m pytest tests/test_docx_export.py tests/test_formal_placeholders.py tests/test_bid_prefill.py tests/test_celery_export_tasks.py -q`
  - 结果：`67 passed, 7 warnings`
- 技术标真实 API 导出：
  - `template_id=technical_bid_standard`
  - `template_family=formal_bid_xinjiang_sgcc_reference`
  - `toc_font=宋体`
  - 字段刷新：`refreshed`
  - XML 审计 failures：`[]`
- 商务标真实 API 导出：
  - `template_id=business_bid_standard`
  - `template_family=formal_bid_xinjiang_sgcc_reference`
  - `toc_font=宋体`
  - 字段刷新：`refreshed`
  - XML 审计 failures：`[]`
- 完整标书回归：
  - 命令：`.venv/bin/python scripts/rag/verify_taichang_full_bid_acceptance.py --run-id run_20260626_reference_template_full_acceptance --project-id a1d853bc-ca4e-43b4-bbea-256f561c8a3d --pdf-preview`
  - 结果：PASS，无 failures/warnings。

## 审计文件

- 参考稿审阅：`docs/development/runs/run_20260626_reference_bid_templates_review.md`
- 真实 API 导出任务：`docs/development/runs/run_20260626_reference_template_real_api_tasks.json`
- DOCX XML 审计：`docs/development/runs/run_20260626_reference_template_docx_audit.json`
- PDF 抽样截图：`docs/development/runs/run_20260626_reference_template_real_export_pages/`
- 完整标书验收：`docs/development/runs/run_20260626_reference_template_full_acceptance.md`

## 边界和后续

本轮已把参考稿形成正式模板 profile，并完成真实导出验证。剩余主要问题不是 DOCX 样式，而是章节对象模型：若要进一步贴近中标稿，应把当前通用章节树升级为“分册对象模型”，按技术偏差表、技术特性参数表、点对点应答、商务偏差表、查询报告、财务状况、附件证据页等对象生成和渲染。

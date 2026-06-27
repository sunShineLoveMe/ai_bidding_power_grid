# run_20260626_p1_volume_docx_export — 分册 DOCX 正式导出回归

- 日期：2026-06-26
- 项目 ID：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 目标：验证泰昌 MVP 默认完整投标文件不变，同时技术标/商务标单独导出具备稳定封面、目录、页眉、页脚字段和 metadata。

## 改动范围

- `backend/core/bid_volumes.py`
  - 新增 `delivery_volume_file_type()`，统一输出分册正式文件类型。
- `backend/api/routes.py`
  - 分册导出报告新增 `scope`、`volume_type`、`volume_name`、`delivery_file_type`、`section_count`。
  - 分册导出时把 `文件类型` 写入 `cover_fields`，技术标为“技术投标文件”，商务标为“商务投标文件”。
- `backend/export/md_to_word.py`
  - DOCX 页眉右侧从固定“投标文件”改为读取封面 `文件类型`。
  - `docx_template_report.header_footer.header_text` 记录实际页眉口径。
- `tests/test_docx_export.py`
  - 增加分册导出 metadata、封面文件类型和页眉文件类型回归。

## 真实链路

```text
build_project_bid_markdown(volume_type=technical/business, with_images=true)
-> convert_md_to_word(return_report=true, cover_fields=...)
-> refresh_docx_fields_with_soffice
```

## 真实导出结果

| 分册 | 章节数 | 文件类型 | 图片选中/插入/失败 | 表格数 | 字段刷新 | 封面 | 页眉 | 页脚字段 |
| --- | ---: | --- | --- | ---: | --- | --- | --- | --- |
| 技术标 | 50 | 技术投标文件 | 24 / 24 / 0 | 110 | refreshed, returncode=0 | PASS | PASS | PASS |
| 商务标 | 52 | 商务投标文件 | 17 / 17 / 0 | 56 | refreshed, returncode=0 | PASS | PASS | PASS |

## 输出文件

- 技术标 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.docx`
- 商务标 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.docx`

## 自动化测试

```bash
.venv/bin/python -m pytest tests/test_docx_export.py -q
# 40 passed

.venv/bin/python -m pytest tests/test_celery_export_tasks.py -q
# 11 passed

.venv/bin/python -m pytest tests/test_compliance.py tests/test_formal_bid_check.py -q
# 9 passed
```

## 结论

P1“分册格式增强”在当前 MVP 口径下已收口：默认完整导出仍是面向泰昌的正式投标文件；单独导出技术标/商务标时，封面、目录、页眉、页脚字段和导出 metadata 均按分册区分。资格文件、报价文件、附件材料继续作为商务标内部资料类型处理。

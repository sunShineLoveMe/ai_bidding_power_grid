# DOCX 技术标/商务标封面签章区留白回归记录

日期：2026-06-29

## 1. 背景

客户参考稿封面在 `文件类别` 与 `投标人`、`法定代表人（单位负责人）或其授权代表人` 签章区之间存在明显空白，用于盖章和签字区域视觉分隔。

当前系统导出的技术标/商务标封面该区域过于紧凑，`文件类别` 后紧接 `投标人`，正式观感不如客户参考稿。

## 2. 修复

- 技术标/商务标 `sgcc_reference_volume_cover` 增加 `signature_block_space_before_pt=96`。
- `_add_cover_page()` 中 `投标人` 段前距改为读取 profile 配置。
- 仅影响 `technical_bid_standard` / `business_bid_standard` 新疆参考分册 profile。
- `formal_bid_standard` 通用模板保持原有自适应封面布局，不受影响。

## 3. 自动化验证

```bash
.venv/bin/python -m pytest \
  tests/test_docx_export.py::DocxExportRegressionTest::test_technical_bid_reference_profile_uses_volume_template_layout_and_toc_depth \
  tests/test_docx_export.py::DocxExportRegressionTest::test_business_bid_reference_profile_uses_business_template_metadata \
  -q
```

结果：

```text
2 passed, 1 warning
```

测试断言：

- `cover_layout.signature_block_space_before_pt == 96`
- `投标人：河北泰昌电力器材科技有限公司（盖单位章）` 段前距为 `96pt`

## 4. 真实导出链路

项目：

```text
a1d853bc-ca4e-43b4-bbea-256f561c8a3d
国网辽宁电力2025年第三次物资协议库存招标采购
```

链路：

```text
build_project_bid_markdown
-> convert_md_to_word
-> refresh_docx_fields_with_soffice
-> LibreOffice PDF
-> pdftoppm first page PNG
```

输出记录：

```text
output/docx-cover-signature-spacing-regression/run_20260629_docx_cover_signature_spacing_regression.json
```

技术标：

- `template_id=technical_bid_standard`
- `field_refresh_status=refreshed`
- `signature_block_space_before_pt=96`
- `bidder_space_before_pt=96.0`
- 图片插入 `9/9`，失败 `0`
- 首页截图：`output/docx-cover-signature-spacing-regression/technical_cover.png`

商务标：

- `template_id=business_bid_standard`
- `field_refresh_status=refreshed`
- `signature_block_space_before_pt=96`
- `bidder_space_before_pt=96.0`
- 图片插入 `5/5`，失败 `0`
- 首页截图：`output/docx-cover-signature-spacing-regression/business_cover.png`

## 5. 结论

封面签章区已形成明显留白，`文件类别` 与 `投标人/法定代表人` 区域不再紧贴；技术标和商务标首页截图未发现文本重叠、溢出或签章区压缩问题。

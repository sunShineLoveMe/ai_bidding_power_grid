# 2026-06-27 本地辽宁招标文件完整真实回归

## 结论

本轮按用户要求使用 Chrome 真实浏览器和本地真实服务，从辽宁 CPVC 包 1 招标文件上传解析开始，跑通到标书正文生成和完整 DOCX 导出。

主链路可行，且已产出完整投标文件 DOCX 成品；但当前导出结果被正式门禁判定为草稿版，不能直接作为正式递交文件。主要原因是正式检查未认可部分投标确认字段，正文仍残留待补充/人工复核占位，并有高风险覆盖项未闭环。

## 测试环境

- 日期：2026-06-27
- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:3012`
- 浏览器：Chrome 插件真实浏览器
- 登录账号：`admin`
- 投标主体：河北泰昌电力器材科技有限公司
- 项目 ID：`5d064d0a-29ba-41bb-ab07-9d51e6c9e084`
- 解析任务 ID：`e60b4a81-07fd-4e1c-90ad-a1bfb871d60d`
- 正文生成任务 ID：`f8f1cb31-ddab-4cad-92bf-82c38a6af391`
- DOCX 导出任务 ID：`021ba227-42f1-4cdc-9b8d-ba10ce94e815`

## 测试文件

先尝试上传完整 ZIP 包：

```text
rag_seed/power_grid_resources/01_tender_documents/22_国网辽宁电力2025年第三次物资协议库存招标采购/extracted/电缆保护管CPVC/包1_完整招标文件_53488484541066181.zip
```

页面真实拒绝，提示 `.zip 不在允许范围内。允许类型：doc, docx, md, pdf, txt。`

随后改用正式上传入口允许的主招标文件：

```text
rag_seed/power_grid_resources/01_tender_documents/22_国网辽宁电力2025年第三次物资协议库存招标采购/extracted/电缆保护管CPVC/包1_完整招标文件_53488484541066181/国网辽宁电力2025年第三次物资协议库存招标采购招标文件.docx
```

## 页面流程记录

| 步骤 | 结果 | 证据 |
| --- | --- | --- |
| 本地服务健康检查 | 通过，后端 `/api/health` 与 `/api/ready` 均正常 | 后端 3012、前端 5173 |
| 登录系统 | 通过 | `output/playwright/run_20260627_local_liaoning_full_e2e/02-after-login.png` |
| 上传 ZIP 招标包 | 被正式入口拒绝 | `output/playwright/run_20260627_local_liaoning_full_e2e/03-after-upload-setfile.png` |
| 上传 DOCX 招标文件 | 通过，`POST /api/bidding/upload` 返回 201 | `output/playwright/run_20260627_local_liaoning_full_e2e/04-after-docx-upload.png` |
| 招标文件解析 | 通过，`native_text` 解析并入库 | `parsed_outputs/e60b4a81-07fd-4e1c-90ad-a1bfb871d60d/native_text/full.md` |
| 招标解读与大纲 | 通过，生成 102 个章节 | `output/playwright/run_20260627_local_liaoning_full_e2e/06-after-outline.png` |
| 投标信息确认 | 使用测试值补齐并应用 | `output/playwright/run_20260627_local_liaoning_full_e2e/08-prefill-ready.png` |
| 进入正文编辑 | 通过 | `output/playwright/run_20260627_local_liaoning_full_e2e/09-bid-editor-open.png` |
| 一键编写全文 | 首轮 74/75 完成，1 个 partial | `MODEL_STREAM_IDLE_TIMEOUT` |
| partial 续写 | 通过，最终 75/75 完成 | `output/playwright/run_20260627_local_liaoning_full_e2e/14-writing-completed-editor.png` |
| 完整 DOCX 导出 | 任务完成，字段刷新成功 | `outputs/5d064d0a/泰昌_2225AC_投标文件_20260627_图文.docx` |

## 解析与正文结果

招标文件解析结果：

```text
markdown_chars=332050
content_blocks=42
requirements=80
scoring_items=80
risks=60
```

正文生成结果：

```text
section_count=102
generated_sections=75
section_content_chars=216079
page_stat_words=194166
page_stat_generated=75/75
coverage_percent=52
pending_coverage_items=117
high_risk_pending=48
```

一键编写全文首轮出现 1 个 partial：

```text
section=投标保证金明细表
error=MODEL_STREAM_IDLE_TIMEOUT: 模型流式输出超过 45 秒没有新 token，已停止继续等待。
```

通过真实后端 retry/续写接口恢复后，正文任务完成：

```text
status=completed
done=75
failed=0
```

## 投标确认测试值

本轮为回归流程使用测试值，不能视为泰昌真实报价或正式授权。关键字段包括：

- 包号：包1
- 包名称：电缆保护管CPVC包1
- 投标人：河北泰昌电力器材科技有限公司
- 投标总价：1280000.00元
- 大写金额：人民币壹佰贰拾捌万元整
- 税率：13%
- 投标保证金：20000.00元
- 授权代表：李明
- 授权代表身份证号：130102199001010011
- 投标有效期：90天
- 签署日期：2026年06月27日

## DOCX 成品

真实导出链路：

```text
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

成品文件：

```text
outputs/5d064d0a/泰昌_2225AC_投标文件_20260627_图文.docx
output/playwright/run_20260627_local_liaoning_full_e2e/泰昌_2225AC_投标文件_20260627_图文.docx
```

导出任务 metadata：

```text
status=completed
progress=100
export_mode=draft
field_refresh=refreshed
selected_images=22
section_count=102
blocked_count=9
formal_required_gaps=16
high_risk_missing=48
```

DOCX 审计：

```text
file_size=3791915
paragraph_count=3717
non_empty_paragraph_count=3629
table_count=128
inline_shape_count=24
media_count=11
page_size=A4
margins_cm=top 2.5, bottom 2.5, left 2.8, right 2.5
PAGE_fields=36
NUMPAGES_fields=1
TOC_fields=3
```

正文验证：

```text
has_bidder=true
has_project_name=true
has_title_type=true
has_price_upper=true
has_representative=true
```

禁用内部字段审计：

```text
/api/bidding/knowledge/assets=0
parsed_outputs=0
source_display_name=0
production_capacity=0
green_low_carbon=0
business_license=0
certification=0
匹配依据=0
metadata=0
页面_=0
原图=0
```

残留正式风险：

```text
placeholder_wait_count=179
manual_review_count=9
cover_package_no=客户确认后填写（包号）
```

## 发现问题

| 编号 | 优先级 | 现象 | 影响 | 建议 |
| --- | --- | --- | --- | --- |
| E2E-LN-001 | P1 | 正式上传入口不支持 ZIP 招标包，只能上传 DOC/DOCX/PDF/TXT/MD | 用户按招标包上传会被拦截，不能完成“整包上传解析” | 明确产品策略：若要支持招标文件包，应增加 ZIP 上传、解压、manifest 和多文件解析流程；否则页面文案需明确“请上传主招标文件” |
| E2E-LN-002 | P0 | 投标确认页显示测试字段已补齐，但完整导出正式门禁仍认为投标总价、保证金、授权代表、签署日期、投标有效期等未正式确认 | 用户以为已确认，导出仍只能草稿；正式交付链路不闭环 | 统一 prefill readiness、formal check、DOCX export gate 的字段来源和 key 映射；补充当前项目回归用例 |
| E2E-LN-003 | P0 | DOCX 正文仍有 179 处“待补充”和 9 处“需人工复核” | 当前成品不能作为正式递交文件 | 一键生成后增加占位符治理步骤；正式版导出前必须阻断或提供一键清理/确认工作台 |
| E2E-LN-004 | P1 | 页面“导出投标文件”下拉菜单 DOM 存在三项，但当前 Chrome 会话点击/悬停后菜单保持 hidden | 真实页面操作可能无法触发下载，只能用同源 API 创建导出任务 | 复查 Ant Design Dropdown 触发区域、父级遮罩/布局和 disabled 状态；加入真实浏览器点击回归 |
| E2E-LN-005 | P1 | 一键编写全文首轮仍可能出现 `MODEL_STREAM_IDLE_TIMEOUT` partial，需要续写恢复 | 长文生成不能完全无人值守 | 对 idle timeout partial 增加自动续写一次，或在任务完成弹窗中提供明确主按钮 |
| E2E-LN-006 | P1 | 封面包号仍为“客户确认后填写（包号）”，虽然测试中已应用包号 | 封面字段与投标确认字段未完全贯通 | 确认封面字段来源优先级，优先读取已确认 `package_no` |

## 剩余任务

1. 修复正式确认字段与 DOCX formal gate 的口径不一致。
2. 修复完整 DOCX 正文占位符残留治理，正式版导出必须做到 0 处待补充/人工复核。
3. 修复封面包号/包名称读取已确认字段。
4. 复查导出下拉菜单真实点击下载路径。
5. 明确 ZIP 招标包上传策略，支持整包或在页面明确限制。
6. 对正文生成 partial 增加自动恢复或显著提示。


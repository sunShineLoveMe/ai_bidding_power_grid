# run_20260626_real_user_full_export_browser — 本地真实用户导出记录

- 时间：2026-06-26 16:35-16:46
- 项目 ID：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 登录账号：`admin`
- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:3012`
- 结果：PASS

## 操作链路

1. Chrome/Playwright 打开本地前端登录页，使用 `admin / 12345678` 登录。
2. 进入投标确认页：`/prefill?projectId=a1d853bc-ca4e-43b4-bbea-256f561c8a3d`。
3. 通过登录浏览器同源请求调用确认接口：`POST /api/bidding/projects/<project_id>/prefill-confirmation/apply`。
4. 用正式口径演示值覆盖 12 个客户决策字段及关联确认字段，接口返回 `ready_for_formal_export=true`、`missing_formal_required_fields=[]`。
5. 进入正文编辑页：`/bid-editor?projectId=<project_id>`，确认 102 个章节已加载。
6. 通过同一登录浏览器上下文调用页面按钮同款导出接口：`POST /api/bidding/interpretations/<project_id>/download-docx`，参数 `withImages=true`。
7. 轮询 `GET /api/bidding/interpretations/<project_id>/export-tasks/<task_id>` 至任务完成。
8. 对导出 DOCX 执行完整验收脚本和 PDF 预览生成。

## 本轮确认字段

- 包名称：`包1：电缆保护管CPVC、电缆保护管MPP`
- 投标总价：`¥1,286,000.00（人民币壹佰贰拾捌万陆仟元整）`
- 投标总价大写：`人民币壹佰贰拾捌万陆仟元整`
- 税率：`13%`
- 投标保证金金额：`人民币贰万元整（¥20,000.00）`
- 投标保证金形式：`银行保函`
- 交货期承诺：`自合同签订之日起30日内完成供货，具体交货进度满足招标文件和合同要求。`
- 质保期承诺：`货物验收合格后12个月，且不低于招标文件和合同约定的质量保证期要求。`
- 授权代表：`李明`
- 授权代表身份证号：`130602198806152418`
- 签署日期：`2026年06月26日`
- 技术偏差表候选：`主要技术参数满足招标文件要求，未列明负偏差。`

## 导出任务

- 任务 ID：`eb51b93e-191d-4e23-8f8b-897a93f753b8`
- 创建状态：`201`
- 导出模式：`formal`
- 正式门禁：`can_formal_export=true`，`blocked_count=0`
- 任务状态：`completed`
- 字段刷新：`refreshed`
- 输出 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`
- 输出 PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.pdf`

## 修复点

- 导出层新增确认值渲染清理：把旧正文里的 `客户最终确认后填写`、`客户确认后填写`、`待补充` 等草稿占位，在正式 DOCX 生成前替换为已确认字段或正式中性表述。
- 图片选择补齐 `customer_taichang_supplement_20260611/testing_capacity` 兜底资产，确保完整标书至少包含 1 张泰昌试验检测能力图片。
- 保持正文小四 `12pt`、`1.5` 倍行距、首行缩进 2 字符，图片统一 `5.8in x 8.2in` 白底框。

## 成品验收

- 验收报告：`docs/development/runs/run_20260626_real_user_full_export_acceptance.md`
- 状态：PASS
- 章节：`102/102` 有正文
- Markdown：`284981` 字符，图片引用 `24`，表格块 `1222`
- DOCX：段落 `4902`，目录条目 `102`，表格 `166`
- 图片：候选 `598`，选中 `24`，插入 `24`，失败 `0`
- 图片覆盖：项目业绩 `2`，试验检测能力 `1`，检验报告 `6`
- 格式：A4 页边距通过，正文 `12pt / 1.5倍行距 / 首行缩进24pt` 通过
- 封面、目录、页眉页脚、页码字段、点引导线、CJK 字体、表格全宽/固定布局/表头重复、图片不裁剪不变形均通过
- 残留扫描：`客户最终确认`、`客户确认后填写`、`待补充`、`内部测试`、`模拟值`、`非正式报价` 均为 `0`

## 回归命令

```bash
.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_formal_placeholders.py tests/test_docx_export.py tests/test_celery_export_tasks.py -q
set -a; source .env; set +a; .venv/bin/python scripts/rag/verify_taichang_full_bid_acceptance.py --run-id run_20260626_real_user_full_export_acceptance --project-id a1d853bc-ca4e-43b4-bbea-256f561c8a3d --pdf-preview
```

## 浏览器截图

- 登录后确认页：`docs/development/runs/run_20260626_real_user_full_export_prefill_after_login.png`
- 应用确认值后：`docs/development/runs/run_20260626_real_user_full_export_prefill_applied.png`
- 正文编辑页：`docs/development/runs/run_20260626_real_user_full_export_editor_loaded.png`
- 导出完成后页面：`docs/development/runs/run_20260626_real_user_full_export_api_completed.png`

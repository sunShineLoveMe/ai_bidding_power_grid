# SG-PROGRESS-001 下载前草稿确认与用户视角进度回归

- 日期：2026-06-25
- 环境：本地真实前端 `http://127.0.0.1:5173`、真实后端 `http://127.0.0.1:3012`
- 项目：`628ed517-0c31-44ea-a5cb-95b25db06fc2`
- 结论：PASS

## 目标

SG-PROGRESS-001 的目标不是向客户解释技术调度细节，而是在下载/导出前明确告诉客户当前文件是否仍是草稿版，避免客户把未完成正文、已保存草稿或待复核章节误认为正式投标文件。

## 实现范围

- 目录顶部统计改为客户可理解的业务口径：全部章节、已生成章节、待完成章节、正在写、排队、草稿待续写、需复核。
- 移除客户界面上的“模型慢流”“当前并发”等技术提示。
- 下载全文 DOCX 前新增草稿版确认：
  - 标题：`下载前确认：当前文件仍是草稿版`
  - 主提示：`当前标书正文尚未全部完成`
  - 风险说明：草稿版可用于内部查看，但不能作为正式投标文件提交。
  - 操作：`下载草稿版` / `返回继续编写`
- partial 章节 tooltip 改为用户口径：草稿已保存、需要人工复核或系统会保留已有内容继续编写。

## 真实回归

| 验证项 | 结果 |
| --- | --- |
| 前端构建 | PASS，`npm --prefix frontend run build` |
| 章节/API/DOCX 相关单测 | PASS，`74 passed` |
| 后端 ready | PASS，`/api/ready` 返回 `status=ok`，Celery workers=1 |
| 真实 partial 草稿夹具 | PASS，通过真实 API 创建临时 generation task，并把未完成叶子章节“偏差核对”标记为 `partial_generated` |
| 浏览器目录页 | PASS，显示 `待完成章节`、`草稿待续写：1`、`需复核：1`，未出现“模型慢流/当前并发/partial_generated”等技术词 |
| 下载前确认弹窗 | PASS，显示草稿版风险、待完成、已保存草稿、需人工复核、返回继续编写 |
| 取消下载路径 | PASS，点击 `返回继续编写` 后弹窗关闭，未创建导出任务 |
| 临时数据清理 | PASS，`regression_case=sg_progress_001_ui` 临时任务 2 条已删除 |
| RAG 本地门禁 | PASS，`docs/rag/runs/run_20260625_sg_progress_001_summary.md` |

浏览器截图：

```text
output/playwright/sg_progress_outline_1440.png
output/playwright/sg_progress_download_warning_1440.png
```

## 备注

首次夹具选到了已有正文的叶子章节“编制依据”，页面按“已完成优先”归并为完成状态，这是正确行为。随后改用未完成叶子章节“偏差核对”完成目标路径验证，并在验证后清理所有临时任务。

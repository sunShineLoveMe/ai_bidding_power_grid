# 2026-06-27 P0 产品适配性拦截与 DOCX 短命名回归

## 背景

阿里云真实浏览器全流程验收客户新疆 10kV 架空绝缘导线招标文件包时发现两个 P0 问题：

1. 投标确认页、技术参数候选和技术章节正文会混入辽宁 2025、CPVC/MPP、电缆保护管资料。
2. 技术标 DOCX 草稿导出任务因长项目名拼入物理路径失败，错误为 `[Errno 36] File name too long`。

## 修复内容

- 新增 `backend/services/bid_compatibility.py`，统一判断当前招标包物料与泰昌已核验产品族的适配性。
- 预填页在检测到“架空绝缘导线/电力电缆”等非泰昌现有 CPVC/MPP 产品族时，不再回退使用辽宁 2225AC CPVC/MPP 结构化行级数据。
- 章节正文生成在产品不适配的技术章节中降级：不加载泰昌 CPVC/MPP 产品事实包、不展示 CPVC/MPP 企业资产候选、不召回章节级 RAG 写作依据；prompt 只允许输出风险说明、资料补充清单和待补充占位。
- 正式检查新增 `T-000 投标产品必须通过适配性预检`，冲突时阻断正式导出。
- DOCX 导出物理目录改为短 `project_id[:8]`，下载文件名改为短格式：`泰昌_<招标编号>_<包号>_<分册>_<日期>.docx`。
- 导出任务完成后写回 `download_file_name`，便于前端展示和客户下载归档。

## 验证

### 定向自动化测试

命令：

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_bid_prefill.py tests/test_formal_bid_check.py tests/test_docx_export.py -q
```

结果：

```text
64 passed, 1 warning
```

覆盖点：

- 新疆架空绝缘导线项目不再带出辽宁 2225AC CPVC/MPP 货物清单、技术参数和泰昌产品参数候选。
- 正式检查 `T-000` 对产品不适配项目返回 blocked，并阻断正式版导出。
- 超长项目名导出时，Markdown/DOCX 物理路径不再包含完整项目名，文件名为短格式。

### 真实 DOCX 链路回归

链路：

```text
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

输入：

- 项目 ID：`580b8c82-42c2-4a51-a0d2-17b60afa22b9`
- 招标编号：`SL265A`
- 包号：`包1`
- 物料：`10kV架空绝缘导线-新疆`

结果：

```text
document_title= 国家电网有限公司2026年西北、西藏区域第一次联合采购10kV架空绝缘导线新疆技术标商务标超长项目名称用于真实导出回归投标文件-技术标
markdown_name= 泰昌_SL265A_包1_技术投标文件_20260627.md
markdown_parent= 580b8c82
download_file_name= 泰昌_SL265A_包1_技术投标文件_20260627.docx
docx_exists= True
docx_name= 泰昌_SL265A_包1_技术投标文件_20260627.docx
template= technical_bid_standard
field_refresh_status= refreshed
compatibility_prompt_block= True
asset_detail_leaked= False
```

结论：真实 DOCX 转换和字段刷新通过；产品不适配 prompt 已阻断 CPVC/MPP 资产详情进入新疆导线包技术章节。

## 边界

- 本轮未修改 RAG 入库、embedding、向量 RPC 或知识库索引；因此未重跑 Base + 泰昌专项全量召回门禁。
- 阿里云线上仍需在部署新代码后，用同一新疆项目复测技术标、商务标、完整投标文件草稿导出任务是否全部完成。

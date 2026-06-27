# DOCX P0 二次问题修复真实导出记录

运行 ID：`run_20260609_docx_quality_p0_cleanup_real_export`

日期：2026-06-09

项目 ID：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`

## 背景

客户查看真实链路生成的 DOCX 后发现三个正式交付问题：

1. Mermaid 流程图转换失败后，源码块进入了正式 DOCX。
2. 目录和章节标题重复父章节前缀，例如 `2.1.1 企业基本资格资料 - 响应要求`。
3. 图片题注展示了内部来源库、匹配依据等调试/检索信息。

这三项均按 P0 处理，因为它们直接影响客户最终看到的正式投标文件观感。

## 修复范围

- 章节规划：拆分子章节时，子章节标题不再拼接父章节标题；父章节信息保留在 metadata。
- 导出兜底：DOCX 导出前移除重复父章节前缀，避免历史数据或上游生成结果继续污染目录。
- Mermaid 处理：Mermaid 转图成功则插入图片；转换失败时跳过源码块并记录 skipped，不把 ```mermaid 和 `graph TD` 等源码写入正式 DOCX。
- 图片题注：正式 DOCX 中仅展示 `图示：资料标题`；来源库、匹配依据、得分等内部信息只保留在 metadata/manifest。
- SOP 同步：`AGENTS.md` 已补充目录命名、Mermaid 失败兜底、正式图片题注规则。

## 自动化测试

命令：

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_docx_export.py tests/test_rag_asset_scoring.py tests/test_chapter_planner.py tests/test_celery_export_tasks.py -q
```

结果：

```text
48 passed, 5 warnings
```

## 真实链路

执行链路：

```text
build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice
```

输出文件：

- Markdown：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.md`
- DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou_Zhao_Biao_Wen_Jian/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`
- JSON 记录：`docs/development/runs/run_20260609_docx_quality_p0_cleanup_real_export.json`

## 验收结果

模板与版式：

- 模板：`sgcc_taichang_bid`
- 页面：A4
- 页边距：上 2.0cm、下 2.0cm、左 3.18cm、右 3.18cm
- 正文：宋体 10.5pt
- 页眉：`河北泰昌电力器材科技有限公司投标文件`
- 字段刷新：LibreOffice 自动刷新成功

图片与 Mermaid：

- 图片 found/inserted/skipped/failed：`24/24/0/0`
- Mermaid found/inserted/skipped：`1/0/1`
- 当前环境未安装 `mmdc`，因此 Mermaid 未转图，但源码已被正式导出层跳过。

清理检查：

```json
{
  "contains_mermaid_fence": false,
  "contains_internal_image_source": false,
  "repeated_title_patterns_found": []
}
```

目录抽样：

```text
2.1 企业基本资格资料
2.1.1 响应要求
2.1.2 资料清单
2.1.3 有效性说明
2.2 信誉与合规承诺
2.2.1 条款响应
2.2.2 承诺事项
2.2.3 偏离说明
```

## 结论

本次二次验收发现的三个 P0 问题已通过自动化测试和真实 DOCX 导出链路验证。当前剩余风险是 Mermaid 只能在安装 `mmdc` 后转为图片；在未安装时，系统已按正式交付要求跳过源码并记录 skipped。

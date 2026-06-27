# run_20260617_p1c8_reference_outline_rebuild — 参考模板目录解析修复

- 日期：2026-06-17
- 项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 范围：先解决“章节目录为什么这么少”的问题，PDF 字体/乱码另行处理。

## 根因

P1C-7 为了快速去掉施工组织、水利、BIM、建造师等不适用于物资供货投标的模板污染，供货类大纲使用了代码内手写的 `_supply_reference_base_chapters()`。该兜底结构只有 23 个节点，虽然能避免施工类内容，但没有真正读取客户提供的河北豪乾参考标书目录。

真实参考稿目录其实已经抽取在：

- `parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/reference_templates/haoqian_reference_templates.json`

其中技术参考稿和商务参考稿均包含大量 `toc_lines`。上一轮只把这些目录概括成 prompt hint，没有作为真实大纲来源。

## 修复

- 新增参考模板 TOC 解析逻辑：
  - 读取 `haoqian_reference_templates.json`；
  - 清洗点引导线、页码、目录页噪声；
  - 按 `（一）`、`1.`、`1.1`、`1.1.1` 等编号层级建树；
  - 供货类项目优先使用解析目录，解析失败才回退到 23 节基准目录。
- 合并必备供货结构：
  - 参考稿缺少或截断时，补入投标函、授权、保证金、售后、报价、附件索引等必备结构。
- 事实边界清洗：
  - 目录只复用结构，不保留河北豪乾供应商名、具体专利名、软件名、历史业绩项目名；
  - 这类标题泛化为“原材料供应商资质文件”“专利证书”“软件著作权登记证书”“同类项目业绩证明材料”等。
- DOCX 友好层级：
  - 大纲规范化最大层级从 5 级收敛到 4 级。

## 真实项目重建结果

| 指标 | 结果 |
| --- | ---: |
| 重建前章节 | 23 |
| 重建后章节 | 102 |
| 一级章节 | 6 |
| 二级章节 | 27 |
| 三级章节 | 30 |
| 四级章节 | 39 |
| 最大层级 | 4 |
| 已有正文回填 | 14 个同名章节 |
| 豪乾具体事实标题命中 | 0 |

根章节：

- 投标函及法定格式文件
- 商务响应文件
- 技术评分支撑材料
- 技术响应文件
- 报价文件及货物清单
- 附件清单及页码索引

备份和报告：

- 首次重建前备份：`docs/development/runs/run_20260617_p1c8_reference_outline_rebuild_before_sections.json`
- 二次清洗重建前备份：`docs/development/runs/run_20260617_p1c8_reference_outline_rebuild_before_second_rebuild_sections.json`
- JSON 报告：`docs/development/runs/run_20260617_p1c8_reference_outline_rebuild.json`

## 验证

```bash
.venv/bin/python -m py_compile backend/ai/chapter_planner.py
.venv/bin/python -m pytest tests/test_chapter_planner.py -q
```

结果：`10 passed`。

## 结论

本次章节少不是 PDF 目录渲染问题，而是大纲源头使用了手写 23 节兜底结构。当前已改为从客户参考稿解析目录，真实项目已重建为 102 节，并保留已有正文。

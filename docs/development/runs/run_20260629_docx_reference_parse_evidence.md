# DOCX 新疆技术/商务参考稿解析证据记录

运行日期：2026-06-29

## 目的

为 `docs/development/docx-export-format-priority-todo.md` 中 `P0-2` 提供可复核证据：客户提供的两份新疆 10kV 架空绝缘导线中标参考稿仅作为版式、目录组织、分册结构和交付观感参考，不复用其中企业事实、产品参数、证书、附件内容。

## 解析命令

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from zipfile import ZipFile
import hashlib, re, json

files = [
    Path('assets/template_words/技术文件 - 10kV架空绝缘导线-新疆.docx'),
    Path('assets/template_words/商务文件 - 10kV架空绝缘导线-新疆(1).docx'),
]
# 读取 section 页面设置、页眉页脚、段落/表格/图片数量、页码字段、字体统计。
PY
```

本次解析使用 `python-docx 1.1.2`，并直接读取 DOCX ZIP XML 中的 `word/footer*.xml`、`word/header*.xml`、`word/document.xml` 与 `word/_rels/document.xml.rels`。

## 文件与哈希

| 文件 | SHA256 | 文件大小 |
| --- | --- | --- |
| `assets/template_words/技术文件 - 10kV架空绝缘导线-新疆.docx` | `f531a90ab1f45195236376128471f0d46c44b19242a44a5f7d61df872af5fb99` | 100,892,623 bytes |
| `assets/template_words/商务文件 - 10kV架空绝缘导线-新疆(1).docx` | `e252c2eeb4841077d4d73f9db739730dfe50ae3ac5c53ea981a5e207d4e00939` | 32,160,267 bytes |

## 核心解析结果

| 维度 | 技术文件参考稿 | 商务文件参考稿 |
| --- | --- | --- |
| Section 数 | 33 | 12 |
| 非空段落 | 1291 | 133 |
| 表格数 | 82 | 3 |
| `document.xml` 绘图/图片节点 | 420 | 170 |
| relationship 图片数 | 407 | 167 |
| 主页面 | A4，21cm x 29.7cm | A4，21cm x 29.7cm |
| 主页边距 | 上下 2.54cm，左右 3.17cm | 上下 2.54cm，左右 3.17cm |
| 主页眉距 / 页脚距 | 1.5cm / 1.75cm | 1.5cm / 1.75cm |
| 首页特殊页眉页脚 | `different_first_page=false` | `different_first_page=false` |
| 页眉文本 | 空 | 空 |
| 页脚字段 | `PAGE \* MERGEFORMAT`，无 `NUMPAGES` | `PAGE \* MERGEFORMAT`，无 `NUMPAGES` |
| 页脚文字 | 无“第/共/页” | 无“第/共/页” |
| 主要字体 | 宋体 | 宋体 |

补充说明：技术文件参考稿存在少量横向 section 和个别页眉/页脚距变化，用于放置宽表或附件页；但页眉仍为空，页脚仍使用纯 `PAGE` 字段。

## 标题与编号样本

技术文件参考稿样本：

```text
Heading 1: （一）技术偏差表
Heading 2: 1.技术偏差表
Heading 1: （二）专项投标文件
Heading 2: 1.技术特性参数表
Heading 3: 1.1.（9985-500143417-00001）
Heading 4: 附:技术规范点对点应答
Heading 5: 1）原材料进厂检验管理制度及规程
```

商务文件参考稿样本：

```text
Heading 1: （一）商务偏差表
Heading 2: 1.商务偏差表
Heading 1: (二)补充文件
Heading 2: 1.投标人与国家电网公司系统人员关系说明
Heading 3: 2.1.“国家企业信用信息公示系统”网站查询报告
Heading 4: 4.1.1.应急保供感谢信
```

## 对 P0/P1 任务的影响

- 支撑 `P0-3`：技术/商务分册参考稿页眉为空，本项目新疆技术/商务 profile 应支持页眉留空。
- 支撑 `P0-4`：参考稿页脚为居中纯 `PAGE` 字段，无 `NUMPAGES` 和中文页码包装。
- 支撑 `P0-5`：参考稿 `different_first_page=false`，但是否显示封面页码仍需结合真实导出渲染确认。
- 支撑 `P0-6`：参考稿主要中文字体为宋体，技术/商务 profile 改宋体有版式依据和线上字体稳定性收益。
- 支撑 `P1-3`：参考稿编号是国网混合编号体系，不适合继续完全依赖模型自由输出。
- 支撑 `P2-1/P2-2/P2-3`：技术文件 420 个图片节点、82 张表，说明附件体量和逐规格/点对点应答是内容组织问题，不是简单 DOCX 样式问题。

## 结论

两份新疆参考稿可以作为技术标/商务标分册观感参考，但不是全项目唯一模板。当前 P0 应优先修复技术/商务分册中肉眼明显且低风险的页眉、页脚、首页页码策略和字体稳定性；完整投标文件是否套用同类 profile 另行决策。

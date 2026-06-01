# MinerU 与 PaddleOCR 私有化解析方案对比

更新时间：2026-05-21  
适用项目：AI 标书系统 / 电网招投标场景  
文档目的：为招标文件解析、OCR、私有化部署和后续解析器架构选型提供依据。

## 1. 结论摘要

在本项目中，MinerU 和 PaddleOCR 都值得保留在技术视野内，但二者定位不同。

MinerU 更像面向 RAG、知识库和 Agent 工作流的一站式文档解析引擎，适合把 PDF、图片、DOCX、PPTX、XLSX 等文件快速转换成 Markdown / JSON，再进入标书解读、章节生成、合规检查和知识库检索流程。

PaddleOCR 更像国产 OCR 和文档智能模型工具箱，覆盖文字识别、版面分析、表格识别、公式识别、印章识别、文档视觉语言模型等能力。它在私有化、国产化、坐标级控制、二次训练和行业模型优化方面更有优势。

因此，一期建议：

```text
主链路：MinerU
增强/兜底链路：PaddleOCR
```

不建议现在直接用 PaddleOCR 替换 MinerU。更稳的做法是继续保持 MinerU 主解析链路，同时规划 PaddleOCR 作为本地私有化增强和失败兜底解析器。

## 2. 当前项目解析链路

当前项目已经接入 MinerU 在线精准解析 API。

关键配置：

```env
MINERU_API_TOKEN=your_mineru_api_token
MINERU_API_BASE_URL=https://mineru.net
MINERU_PARSE_PDF_FIRST=true
```

当前流程：

```text
用户上传招标文件
  ↓
后端申请 MinerU 上传 URL
  ↓
上传文件到 MinerU
  ↓
轮询解析任务
  ↓
下载 MinerU 结果 zip
  ↓
提取 Markdown / JSON / 图片等产物
  ↓
导入 PostgreSQL
  ↓
向量化入库
  ↓
用于招标解读、章节生成、合规检查、知识库问答
```

这条链路对当前 MVP 最友好，因为 MinerU 输出已经天然接近 RAG 入库格式。

## 3. 技术定位对比

```text
PaddleOCR
├─ PP-OCRv5：文字检测 + 文字识别
├─ PP-StructureV3：版面分析 + 表格 + 公式 + 阅读顺序 + Markdown / JSON
├─ PaddleOCR-VL：文档视觉语言模型，处理复杂版式、图表、印章、多语言
└─ 更像“文档智能工具箱 / 模型体系”

MinerU
├─ 文档上传/解析任务
├─ PDF / 图片 / DOCX / PPTX / XLSX 转 Markdown / JSON
├─ 版面、表格、公式、图片、阅读顺序处理
├─ API / CLI / WebUI / Router
└─ 更像“面向 RAG 的完整文档解析引擎”
```

## 4. 多维度对比

| 维度 | PaddleOCR | MinerU | 对本项目的影响 |
|---|---|---|---|
| 产品定位 | OCR + 文档解析模型套件 | 一站式文档解析引擎 | MinerU 接入更快，PaddleOCR 可控性更强 |
| 文字识别 | PP-OCRv5 很强，支持 100+ 语言 | 内部也具备 OCR / VLM 解析能力 | 纯 OCR 任务 PaddleOCR 更直接 |
| PDF 转 Markdown | PP-StructureV3 / PaddleOCR-VL 支持 | 核心能力，天然输出 Markdown / JSON | MinerU 更贴近当前入库流程 |
| 表格识别 | PP-StructureV3 强，坐标粒度细 | 支持表格、跨页表格、结构输出 | 电网投标文件表格多，两者都需实测 |
| 版面还原 | PP-StructureV3 强，PaddleOCR-VL 更强 | 强调阅读顺序、标题层级、语义连贯 | 标书解析更看重阅读顺序和层级 |
| 扫描件/拍照件 | PaddleOCR-VL 对倾斜、光照、印章等场景更有针对性 | MinerU 也支持复杂文档解析 | 需用真实招标文件做 A/B 测试 |
| 坐标信息 | 更细，文本、表格单元格、版面区域坐标更可控 | 更偏最终结构化产物 | 如需原文高亮、页码定位，PaddleOCR 有优势 |
| 私有化部署 | 非常适合，国产生态成熟 | 支持本地、Docker、API、Router | 两者都可私有化 |
| 二次训练 | 支持数据集训练和模型替换 | 更偏开箱即用解析 | 如果后续做电网行业专用 OCR，PaddleOCR 更适合 |
| 工程接入 | 需要自己拼装解析 pipeline | 当前项目已经接入 | 短期 MinerU 成本低 |
| 国产化交付 | 百度飞桨生态，国产化背书强 | OpenDataLab / 上海 AI Lab 生态 | 两者国内接受度都可以 |
| 商用许可 | 需按 PaddleOCR 和相关模型组件确认 | MinerU 为 Apache 2.0 附加条款 | 正式商用前都要做 license 审查 |

## 5. 场景适配图

| 场景 | 更推荐 |
|---|---|
| 纯图片 OCR、证照、资质文件识别 | PaddleOCR |
| 印章、截图、扫描件、复杂图片文字识别 | PaddleOCR-VL / PP-OCRv5 |
| 招标文件一键解析成 Markdown / JSON 入库 | MinerU |
| 标书 RAG 知识库构建 | MinerU 优先，PaddleOCR 可备选 |
| 精确坐标、原文高亮、表格单元格定位 | PaddleOCR |
| 电网行业专用 OCR 微调 | PaddleOCR |
| 快速上线、减少自研 pipeline | MinerU |
| 客户要求完全内网、国产化可控 | 两者都可以，PaddleOCR 可控性更强 |
| 当前项目短期平滑接入 | MinerU |

## 6. 公开指标参考

PaddleOCR 官方 PP-StructureV3 文档中给出了一组 OmniDocBench 指标，PP-StructureV3 在多个指标上优于 MinerU 0.9.3 / 1.3.11。

其中中文 Overall Edit 指标如下，数值越低越好：

| 工具 | 中文 Overall Edit |
|---|---:|
| PP-StructureV3 | 0.206 |
| MinerU 0.9.3 | 0.357 |
| MinerU 1.3.11 | 0.310 |

但这组数据需要谨慎理解：

1. 对比对象不是 MinerU 最新 3.1 / MinerU2.5-Pro。
2. PaddleOCR 官方文档中的指标不等于本项目真实招标文件效果。
3. 招标文件场景更关注章节层级、表格、页码、废标条款、评分办法、附件结构等业务可用性。
4. 最终应以真实样本 A/B 测试为准。

因此不能简单得出“PaddleOCR 一定比 MinerU 强”或“MinerU 一定比 PaddleOCR 强”的结论。

## 7. 私有化部署视角

### 7.1 MinerU 私有化

MinerU 支持 CLI、API、WebUI、Router 等方式，适合部署成独立文档解析服务。

推荐形态：

```text
业务后端 ECS
  ↓
MinerU API 服务
  ↓
解析产物 Markdown / JSON / 图片
  ↓
业务后端导入 PostgreSQL / OSS / 向量库
```

优点：

- 与当前项目链路兼容度高。
- 输出 Markdown / JSON，适合 RAG 和知识库。
- 接入成本低。
- 支持 Docker、FastAPI、Router。

风险：

- 本地版本与线上 API 版本需要锁定，否则解析结果可能不一致。
- 生产部署建议使用 Linux + NVIDIA GPU。
- macOS Docker 不适合 MinerU 加速实验。
- 对长文档、大并发仍需要任务队列和失败重试。

### 7.2 PaddleOCR 私有化

PaddleOCR 适合做更底层、更可控的 OCR / 文档智能能力。

推荐形态：

```text
业务后端 ECS
  ↓
PaddleOCR 服务
  ↓
OCR / 版面 / 表格 / 坐标 / 印章识别
  ↓
统一转换成项目标准 DocumentParseResult
  ↓
导入 PostgreSQL / OSS / 向量库
```

优点：

- 国产化生态成熟。
- OCR 模型和版面模型可控。
- 坐标信息更细。
- 支持二次训练，适合电网行业定制。
- 可作为 MinerU 失败后的增强兜底。

风险：

- 需要我们自己设计更完整的结构化转换 pipeline。
- 直接接入成本高于 MinerU。
- 输出结果需要适配本项目的章节、分片、页码、质量报告格式。

## 8. 推荐系统架构

不建议业务层直接绑定某一个解析器。建议抽象统一解析接口。

```text
backend/parsing/
├─ mineru_adapter.py       # MinerU 主解析器
├─ paddleocr_adapter.py    # PaddleOCR 增强/兜底解析器
├─ parser_router.py        # 根据文件类型、页数、失败原因选择解析器
└─ normalized_document.py  # 统一输出结构
```

统一输出结构建议：

```text
DocumentParseResult
├─ markdown                # 主文本，供 RAG 与章节分析使用
├─ pages                   # 页级内容
├─ blocks                  # 段落、标题、列表、图片、表格等块
├─ tables                  # 表格结构
├─ images                  # 图片引用与裁剪结果
├─ source_positions        # 页码、坐标、原文位置
├─ quality_report          # 解析质量报告
└─ parser_metadata         # 解析器、版本、参数、耗时、错误信息
```

这样未来无论底层使用 MinerU、PaddleOCR，还是其他解析器，业务层都不需要大改。

## 9. 建议落地路线

### 阶段一：保持 MinerU 主链路

目标：稳定跑通 MVP。

任务：

- 保留当前 MinerU 在线 API。
- 继续完善下载重试、手动导入 zip、解析状态展示。
- 对当前电网样本和客户提供的国网标书包做解析质量记录。

### 阶段二：本地实验 PaddleOCR

目标：验证 PaddleOCR 在招标文件中的实际价值。

任务：

- 本机或开发服务器安装 PaddleOCR。
- 选 5 - 10 份典型文件做对比：
  - 扫描 PDF
  - 原生 PDF
  - 表格密集型招标文件
  - 资质证书图片
  - 带印章/签字/图片附件的文件
- 对比指标：
  - 解析耗时
  - OCR 准确性
  - 表格还原
  - 章节层级
  - 页码保留
  - 图片/印章识别
  - 入库后 RAG 检索效果

### 阶段三：实现解析器路由

目标：形成生产级稳定性。

路由策略示例：

```text
普通 PDF / Office 文档
  → MinerU

MinerU 解析失败
  → PaddleOCR 兜底

扫描件 / 图片型 PDF
  → MinerU 优先，PaddleOCR 复核

证照 / 资质图片
  → PaddleOCR 优先

需要原文坐标高亮
  → PaddleOCR 增强
```

### 阶段四：阿里云私有化交付

目标：满足客户正式上线与数据合规。

推荐部署：

```text
业务服务：ECS
数据库：RDS PostgreSQL
文件存储：OSS
任务队列：Redis
解析服务：独立 GPU ECS
解析器：MinerU 主服务 + PaddleOCR 增强服务
```

## 10. 对电网标书场景的判断

电网招投标文件通常具备以下特点：

- 页数较长。
- 表格多。
- 评分办法、废标条款、资格条款密集。
- 附件、资信、产品资料复杂。
- 需要页码、条款、章节、材料之间建立可追溯关系。

因此，单纯 OCR 不够，必须关注：

- 阅读顺序是否正确。
- 标题层级是否稳定。
- 表格是否可用。
- 页码和原文定位是否保留。
- 解析结果是否能稳定进入 RAG。
- 解析失败是否能重试或兜底。

从这个角度看：

```text
MinerU 适合做主解析结果。
PaddleOCR 适合做 OCR、坐标、表格、证照、扫描件增强。
```

## 11. 当前建议

短期不替换 MinerU。

中期增加 PaddleOCR 实验分支。

长期建设统一解析器抽象，形成：

```text
MinerU 主解析
+ PaddleOCR 增强
+ 手动导入兜底
+ 解析质量评估
+ 解析器路由
```

这样最符合本项目的交付节奏，也为后续电网行业私有化和国产化部署留下空间。

## 12. 参考资料

- PaddleOCR GitHub：<https://github.com/PaddlePaddle/PaddleOCR>
- PaddleOCR 官方文档：<https://www.paddleocr.ai/main/en/index.html>
- PP-StructureV3 官方文档：<https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-StructureV3/PP-StructureV3.html>
- MinerU GitHub：<https://github.com/opendatalab/MinerU>
- MinerU 官网：<https://mineru.net/>
- MinerU Docker 部署文档：<https://opendatalab.github.io/MinerU/quick_start/docker_deployment/>
- MinerU 扩展模块文档：<https://opendatalab.github.io/MinerU/quick_start/extension_modules/>

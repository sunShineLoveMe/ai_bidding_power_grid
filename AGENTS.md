# Project Agent Instructions

## 国家电网 RAG 基座数据工程 Skill

当用户要求处理电网/国家电网 RAG 基座数据、客户标书模板、招标文件包、技术规范书、货物清单、合同条款、分块、metadata、入库、召回评测或回归跟踪时，必须先使用以下 Skill：

- Skill 路径：`.agents/skills/power-grid-rag-ingestion/`
- 核心文档目录：`docs/rag/`
- 客户资料目录：`rag_seed/power_grid_resources/01_tender_documents/`
- 评测结果目录：`docs/rag/runs/`

执行原则：

- 先 inventory，再解析/清洗/分块/入库；
- 默认父子双层分块，child 召回、parent 写作回溯；
- 召回必须优先 metadata 过滤，再向量检索；
- `.xlsx` 货物清单和技术参数表必须结构化，不得只做普通文本向量；
- 每次新增客户资料或调整召回策略后，必须重跑 `scripts/rag/eval_recall.py`，并更新 `docs/rag/evaluation-records.md` 与 `docs/rag/todo.md`；
- 出现水利或其他非电网资料时，先隔离/删除，再复跑召回评测。

## 泰昌 MVP 试点企业规则

当前 MVP 试点企业和默认投标主体是：

```text
河北泰昌电力器材科技有限公司
```

简称：泰昌。

执行原则：

- 所有标书生成、企业事实问答、图文配图、企业资质/产品/资信引用，默认以泰昌为投标申请主体。
- 标书标题、文件名、封面、页眉和正文主体口径必须使用“投标文件 / 投标人：河北泰昌电力器材科技有限公司”，不得沿用“招标文件”口径。
- 辽宁资料仅作为招标场景样本，用于招标要求、技术规范、货物清单、合同条款、评分/否决项等，不作为泰昌企业事实。
- 河北豪乾资料仅作为格式、目录、章节组织和写法参考，`reference_only=true`，不得作为泰昌资质、业绩、设备、人员、财务、图片资产等企业事实来源。
- 严禁把泰昌企业事实、辽宁招标要求、河北豪乾参考稿混用；如资料来源不清，先补 metadata 或人工确认，不要直接入库或用于生成正式标书。

## 泰昌 / 辽宁 / 河北豪乾 Metadata 边界

泰昌企业事实资料默认 metadata：

```text
enterprise=泰昌
doc_owner=泰昌 或 河北泰昌电力器材科技有限公司
source_domain=enterprise_fact
reference_only=false
fact_source_allowed_for_enterprise=true
tenant_visibility=taichang_only
access_scope=taichang_tenant_internal
```

辽宁招标资料默认 metadata：

```text
source_domain=tender_requirement
doc_owner=国网辽宁省电力有限公司
province=辽宁
fact_source_allowed_for_enterprise=false
```

河北豪乾参考稿默认 metadata：

```text
source_domain=reference_template
doc_owner=河北豪乾电气设备科技有限公司
reference_only=true
fact_source_allowed_for_enterprise=false
citation_policy=reference_style_only
do_not_mix_with=["泰昌企业事实"]
```

## 泰昌图片资产规则

泰昌解析出来的图片资产必须保留 metadata，以支持知识库问答、标书图文并茂、智能客服图片展示和后续批量入库。

图片资产至少记录：

- `asset_id`
- `source_file`
- `page_no` 或可追溯路径
- `enterprise`
- `doc_owner`
- `source_domain`
- `evidence_type`
- `target_library`
- `tenant_visibility`
- `access_scope`

执行原则：

- 标书图文导出只允许使用泰昌企业事实资产。
- 不允许使用河北豪乾参考稿图片作为泰昌企业事实配图。
- 不允许使用辽宁招标资料图片作为泰昌企业资质或能力配图。
- 模型正文中凭空生成的图片路径不得进入正式 DOCX；正式导出只保留已入库、可解析、可追溯的真实资产图片。

## DOCX 正式投标文件导出规则

DOCX 导出属于客户第一印象和正式交付质量问题，任何相关改动都必须按正式投标文件标准处理。

默认模板：

```text
sgcc_taichang_bid
```

默认版式：

- A4；
- 上下边距 `2.0cm`；
- 左右边距 `3.18cm`；
- 正文宋体 `10.5pt`；
- 正文固定行距 `20pt`；
- 目录标题为 `目  录`；
- 目录页码右对齐，并使用点引导线；
- 页眉为 `河北泰昌电力器材科技有限公司投标文件`；
- 页脚使用连续页码和总页数字段；
- 未显式关闭时，DOCX 导出默认 `withImages=true`。

导出后必须刷新 Word 字段，包括目录页码、页脚页码和总页数。若客户后续提供可编辑 Word 模板，应优先进入 `template_docx` 模式，而不是继续只靠内置模板。

## 回归与文档同步规则

涉及 RAG 入库、metadata、召回策略或客户资料边界调整时：

- 必须跑 Base + 客户专项召回评测；
- 必须检查跨资料域串用，尤其是泰昌/辽宁/河北豪乾边界；
- 必须更新 `docs/rag/evaluation-records.md`、`docs/rag/todo.md` 或对应 run 文档。

涉及 DOCX 导出、标书格式、图片资产或正式文件观感时，至少验证：

- 标题、封面、目录；
- 正文字体、字号、行距、页边距；
- 页眉页脚和页码字段刷新；
- 图片资产选中数、插入数、失败数；
- 是否误用河北豪乾参考稿或辽宁招标资料；
- 测试记录应写入 `docs/development/runs/` 或对应功能文档。

真实链路测试优先使用真实服务和真实 LLM，不使用 mock；除非用户明确要求 mock 或当前任务只是窄范围单元测试。

## 飞书文档导入 Skill

当用户要求将本项目生成的 Markdown 文档同步、发布、上传、归档到飞书时，使用以下 Skill：

- Skill 路径：.agents/skills/feishu-doc-import/
- 默认文档目录：feishu/docs/
- 目标知识库：AI标书系统-国家电网
- 知识库地址：https://acn03r8l9jgi.feishu.cn/wiki/space/7646261306835635128

## 当前稳定链路

V1 只执行：

本地 Markdown → lark-cli drive +import → 飞书 Docx 云文档 URL

不要自动移动到知识库。导入成功后，由用户手动移动到知识库。

## 执行命令

当用户说“同步到飞书”“发布到飞书”“上传到飞书知识库”时，优先执行：

```bash
.agents/skills/feishu-doc-import/scripts/import-to-feishu-docx.sh "<markdown文件路径>" "<标题>"

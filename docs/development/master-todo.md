# 项目任务总账

更新日期：2026-06-25

本文档是 AI 标书系统当前唯一的项目级任务优先级入口。其他 TODO、roadmap、专项清单和 run 记录只作为详情来源、验收记录或历史上下文，不再单独定义更高优先级。

## 使用规则

1. 新增 P0/P1/P2 任务必须先进入本文档，再链接到专项文档或验证记录。
2. 专项文档可以保留细节、执行记录和领域 SOP，但任务优先级以本文档为准。
3. 每个 P0 任务必须写清楚验收口径、关联文档和最近验证记录。
4. 已完成任务不从本文档删除，移入“已完成关键任务”，避免后续重复发现。
5. 涉及客户正式交付、数据安全、资料边界、正式投标文件质量的问题，默认不得低于 P0/P1。

## 状态标记

| 状态 | 含义 |
| --- | --- |
| 未开始 | 已确认要做，但尚未动手 |
| 进行中 | 已有实现或文档，但未完全通过验收 |
| 阻塞 | 依赖客户资料、外部环境、账号权限或人工确认 |
| 已完成 | 已实现并有可追溯验证记录 |
| 延后 | 暂不进入当前迭代，但保留任务 |

## 合同 MVP 功能清单覆盖映射

本节根据合同截图《系统功能清单 1》整理。判断口径：合同中标为 MVP 的能力，若尚未形成可演示、可验收、可追踪的最小闭环，应进入当前 P0 或 P1，不得长期沉在普通 roadmap。

| 合同 MVP 功能 | 合同描述摘要 | 当前覆盖判断 | 总账处理 |
| --- | --- | --- | --- |
| 招标文件智能解析 | 支持 PDF/DOCX/TXT、OCR/MinerU、原生解析、抽取关键字段 | 基本覆盖，仍需按正式检查口径持续验收关键字段抽取质量 | 纳入 P0“正式检查与导出门禁收口”和 P1“企业资料与 RAG 持续门禁” |
| 国网招标文件样本分析 | 基于甲方提供 5-10 份样本做字段、评分、资格、否决项分析 | 部分覆盖；已有辽宁、江西、山西样本链路，但需要形成合同验收报告 | 新增 P0“合同 MVP 功能覆盖验收与缺口关闭” |
| 电力行业术语与知识库 | 建设基础版电力知识库 | 基本覆盖；已有电网种子库、RAG、召回评测 | 纳入 P1“企业资料与 RAG 持续门禁” |
| 电力分册结构配置 | 支持技术标、商务标、资格标、报价/货物清单、附件结构 | 基本覆盖；分册基础模型完成，分册格式和分册进度仍需增强 | 纳入 P1“分册格式增强” |
| 企业资信库 | 支持企业资质、检测报告、业绩、授权、体系认证上传管理 | 基本覆盖；云上展示与来源收敛仍在进行 | 纳入 P0“阿里云企业库展示与来源收敛” |
| 产品库 | 支持电缆、开关柜、变压器、互感器、保护装置、通信设备等资料管理 | 部分覆盖；当前泰昌 MVP 重点是电缆保护管，通用产品分类和多品类演示需补齐 | 新增 P1“产品库多品类 MVP 展示收口” |
| OCR 信息提取 | 支持投标人、项目概况、评分标准、资质要求、废标条款等抽取 | 基本覆盖；仍需以正式检查和样本分析报告证明 | 纳入 P0“合同 MVP 功能覆盖验收与缺口关闭” |
| 章节大纲生成 | 生成电网投标分册大纲 | 已覆盖；仍需保持真实项目回归 | 归入已完成关键任务，后续由 P1“分册格式增强”延续 |
| 标书正文生成 | 生成商务标、技术标、服务方案、实施计划等初稿 | 基本覆盖；正式交付仍受客户关键字段和 DOCX 观感影响 | 纳入 P0“正式投标关键字段确认闭环”和 P0“DOCX 正式交付排版升级” |
| 合规覆盖检查 | 条款响应检查、评分项覆盖、重点风险提示 | 基本覆盖；统一到正式检查门禁，避免只看条款覆盖率 | 纳入 P0“正式检查与导出门禁收口” |
| AI 辅助编辑 | 支持扩写、缩写、润色、风格调整 | 缺口；合同 MVP 项，当前总账不能继续放在 P2 | 新增 P0“AI 辅助编辑 MVP 最小闭环” |
| RAG（检索增强生成） | 解读、大纲、正文、补写、问答接入企业知识库 | 基本覆盖；补写/编辑侧 RAG 与 AI 辅助编辑需打通 | 纳入 P1“企业资料与 RAG 持续门禁”和 P0“AI 辅助编辑 MVP 最小闭环” |
| 排版调优 | 支持基础 Word 格式、目录、页码、标题层级、表格、图片 | 部分覆盖；客户反馈观感像草稿，已重新提升为 P0 | 纳入 P0“DOCX 正式交付排版升级” |
| 多格式导出 | Word 必做；PDF 可作为转换能力，不保证复杂格式完全一致 | Word 基本覆盖，PDF 转换能力已有验证但需产品口径收口 | 新增 P1“多格式导出与 PDF 口径收口” |
| 阿里云部署 | 单企业部署 | 进行中；单 ECS 测试部署和云上试用已开展，入口和交接仍需收口 | 纳入 P1“阿里云单 ECS 测试部署收口” |
| 智能助手 | 悬浮智能问答助手 | 基本覆盖；需与企业库来源收敛一起验收 | 纳入 P0“阿里云企业库展示与来源收敛” |
| 使用范围 | 单体范围，只支持一个企业标书 | 已按泰昌单企业 MVP 执行 | 归入已完成关键任务，后续不扩多租户 |

## 当前 P0

| 状态 | 任务 | 所属模块 | 为什么是 P0 | 验收口径 | 关联文档 |
| --- | --- | --- | --- | --- | --- |
| 进行中 | 合同 MVP 功能覆盖验收与缺口关闭 | 产品验收 / 项目管理 | 合同截图中的所有功能均标为 MVP；必须有统一覆盖判断和缺口关闭记录，不能只按内部技术路线图验收 | 合同 MVP 17 项覆盖报告已形成；缺口必须进入本文档 P0/P1 并有验收记录，直到 AI 辅助编辑、产品库多品类、PDF 口径等缺口关闭 | `docs/development/runs/run_20260625_contract_mvp_coverage_review.md`、本文档、`docs/development/roadmap.md`、`docs/rag/todo.md` |
| 进行中 | 批量章节生成可靠性与 Prompt 分级瘦身 | 标书正文生成 / AI 调度 | 客户线上真实测试已出现后半段大量 `MODEL_STREAM_WALL_TIMEOUT`，体感为全文编写卡死；这是合同 MVP“标书正文生成”和客户试用转化的核心风险 | 已完成 SG-UX-001/002：完成状态与偏长/偏短质量提示拆分，新增“压缩到目标”；已完成 SG-AI-001：自定义编写要求持久化，并进入生成任务 item metadata 快照；已完成 SG-DATA-001：新增子章节继承父章节分册并在当前筛选可见；已完成 SG-DATA-002：叶子章节新增子章节前确认，并支持保留父章节概述/迁移正文到子章节；已完成 SG-DATA-003：删除真实提示、后端子树删除和页面内撤销恢复；已完成 SG-PROMPT-001：prompt profile 分级、输入预算、真实任务 metadata 与完整 DOCX 链路回归；后续继续慢流保护、自适应并发、partial 草稿续写和前端可解释进度 | `docs/development/section-generation-adaptive-writing-plan.md`、`docs/development/runs/run_20260625_aliyun_section_generation_timeout_diagnosis.md`、`docs/development/runs/run_20260625_local_bid_editor_length_status_regression.md`、`docs/development/runs/run_20260625_local_custom_writing_persistence_regression.md`、`docs/development/runs/run_20260625_local_child_section_volume_inheritance_regression.md`、`docs/development/runs/run_20260625_local_leaf_to_container_confirmation_regression.md`、`docs/development/runs/run_20260625_local_delete_subtree_undo_regression.md`、`docs/development/runs/run_20260625_sg_prompt_001_prompt_profile_budget.md` |
| 进行中 | DOCX 正式交付排版升级 | DOCX / 产品交付 | Word 是客户第一眼看到的正式交付物；当前导出观感被客户认为像草稿，会直接影响信任和试用转化 | 默认提供“通用正式标书格式”并可保留“国网/泰昌紧凑格式”；正文、标题、表格、页眉页脚、目录、封面、第六章格式表单均按正式投标文件标准验收；真实链路 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice` 通过并写入 run 记录 | `docs/development/docx-bid-export-quality-todo.md`、`docs/section-generation-production-remediation-todo.md`、`AGENTS.md` |
| 已完成 | AI 辅助编辑 MVP 最小闭环 | 编辑器 / AI 伴写 | 合同 MVP 明确要求扩写、缩写、润色、风格调整；当前若只支持人工编辑和整章生成，会被认为缺少合同功能 | 正文编辑器已支持选中文本扩写、缩写、润色、正式化；调用真实模型；结果可预览、采纳、撤销；已用真实章节完成 API 与浏览器验收 | `docs/development/runs/run_20260625_ai_edit_mvp_real_api_acceptance.md`、`docs/development/runs/run_20260625_ai_edit_mvp_ui_acceptance.md` |
| 已完成 | 正式检查与导出门禁收口 | 正式检查 / 导出前门禁 | 不能把可下载草稿误导成正式投标文件；必须区分草稿版和正式版 | 阻断项为 0 才允许正式版导出；阻断项存在时只允许草稿版；检查项覆盖客户确认字段、条款覆盖、资料边界、正文占位、DOCX 成品质量；当前演示项目正式检查阻断项 0、占位符 0，完整 DOCX 验收 PASS | `docs/development/formal-check-todo.md`、`docs/development/runs/run_20260625_placeholder_cleanup_current_project.md`、`docs/development/runs/run_20260625_placeholder_cleanup_docx_acceptance.md`、`docs/development/runs/run_20260625_placeholder_cleanup_default_acceptance.md`、`rules/power_grid/formal_bid_check_rules.v1.json` |
| 进行中 | 阿里云企业库展示与来源收敛 | 企业知识库 / 云环境 | 客户正在真实试用；来源混入、分类不准、入口不稳定会直接影响可信度 | 云上企业知识库问答与页面展示不混入错误来源；人员证书、资质证书、检验报告、产品资料分类准确；公网入口说明清晰 | `docs/rag/todo.md` P1C-15、`docs/rag/runs/run_20260624_aliyun_online_rag_regression.md` |
| 已完成 | 正式投标关键字段确认闭环 | 投标确认 / 正式交付 | 报价、保证金、授权代表、签署日期等字段不能由模型编造，但缺失会阻断正式交付 | 前导确认页、正式检查、导出提示使用同一缺口来源；当前演示项目已应用 31 个确认字段，正式必填缺口 0，仍保留人工终审提示 | `docs/rag/todo.md` P4-11、`docs/development/formal-check-todo.md`、`docs/development/docx-bid-export-quality-todo.md`、`docs/development/runs/run_20260625_placeholder_cleanup_current_project.md` |
| 已完成 | 项目任务总账收口 | 项目管理 / 工程治理 | 多个 TODO 分散导致优先级遗忘和重复建清单 | 新增本文档并将主要散落任务映射到统一 P0/P1/P2；后续优先级以本文档为准 | 本文档 |

## 当前 P1

| 状态 | 任务 | 所属模块 | 验收口径 | 关联文档 |
| --- | --- | --- | --- | --- |
| 未开始 | DOCX 格式方案选择产品化 | DOCX / 前端 | 导出时支持国网/泰昌标准格式、通用正式标书、紧凑上传版、图文展示版；默认不让普通用户承担复杂配置 | `docs/development/docx-bid-export-quality-todo.md` |
| 未开始 | 可编辑 Word 模板导入 `template_docx` | DOCX / 模板化 | 客户上传可编辑 Word 模板后，可继承模板样式或按模板套打；优先级高于内置模板 | `docs/development/docx-bid-export-quality-todo.md`、`AGENTS.md` |
| 进行中 | 分册格式增强 | 标书分册 / DOCX | 商务标、技术标、资信标、报价文件支持不同封面、目录和页眉文案；分册导出观感稳定 | `docs/技术标商务标分册整改TODO.md`、`docs/development/docx-bid-export-quality-todo.md` |
| 进行中 | 第六章格式表单保真 | DOCX / 正式检查 | 投标函、授权委托书、商务偏差表、技术偏差表、承诺函等固定格式不被普通 Markdown 转换破坏 | `docs/development/docx-bid-export-quality-todo.md`、`docs/development/formal-check-todo.md` |
| 未开始 | 产品库多品类 MVP 展示收口 | 产品库 / 企业资料 | 合同写明产品库覆盖电缆、开关柜、变压器、互感器、保护装置、通信设备等资料管理；当前试点资料集中在电缆保护管，需要给出演示口径或补齐分类 | 产品库页面具备多品类中文分类；无资料品类显示空状态和资料上传入口；泰昌现有资料不被错误扩展为其他品类事实 | `docs/rag/todo.md`、`frontend/src/pages/ProductBase/index.tsx` |
| 未开始 | 多格式导出与 PDF 口径收口 | DOCX / PDF / 导出 | 合同写明 Word 必做、PDF 可作为转换能力且不保证复杂格式完全一致；产品需明确能力边界 | 导出页面和 metadata 明确 Word 为正式主交付；PDF 为预览/转换能力；PDF 生成失败不冒充正式交付；至少一次真实 DOCX -> PDF 验证记录 | `docs/development/docx-bid-export-quality-todo.md` |
| 进行中 | 正式检查页面处理路径增强 | 正式检查 / 前端 | 检查项支持筛选、分类、证据链展示和跳转到投标确认页、章节编辑页、企业库或产品库 | `docs/development/formal-check-todo.md` |
| 进行中 | 企业资料与 RAG 持续门禁 | RAG / 数据工程 | 新增客户资料后严格执行 inventory、metadata、入库、Base + 泰昌专项回归和真实 stream 抽样 | `docs/rag/todo.md`、`docs/rag/evaluation-records.md` |
| 未开始 | 开源前敏感资料清理 | 安全 / 开源治理 | 移除真实业务文件、生成文件、解析产物、缓存、日志和本地运行配置；保留可复现实验样例 | `docs/development/roadmap.md` |
| 进行中 | 阿里云单 ECS 测试部署收口 | 部署 / 运维 | 安全组、HTTP/HTTPS 入口、Docker Compose、LibreOffice 字段刷新、备份与交接文档完整 | `docs/deployment/aliyun-ubuntu-single-ecs-deploy-checklist-20260622.md` |

## 当前 P2

| 状态 | 任务 | 所属模块 | 验收口径 | 关联文档 |
| --- | --- | --- | --- | --- |
| 未开始 | 高级 DOCX 自定义格式面板 | DOCX / 前端 | 支持编号、正文、页面、图表等设置，并可恢复默认模板 | `docs/development/docx-bid-export-quality-todo.md` |
| 未开始 | 企业模板保存与复用 | DOCX / 企业配置 | 用户可另存企业模板并在后续项目复用 | `docs/development/docx-bid-export-quality-todo.md` |
| 未开始 | 招标文件格式约束自动抽取 | 解析 / DOCX | 自动抽取第六章、前附表、否决项中的格式要求，并提示用户确认 | `docs/development/docx-bid-export-quality-todo.md` |
| 未开始 | 后端大路由继续拆分 | 工程结构 | `backend/api/routes.py` 按项目、解析、解读、章节、知识库、导出等模块拆分 | `docs/development/roadmap.md` |
| 未开始 | 前端标书编辑器拆分 | 工程结构 / 前端 | `frontend/src/pages/BidEditor/index.tsx` 拆为章节树、正文编辑、批量生成、下载、状态 hooks | `docs/development/roadmap.md` |
| 未开始 | 章节版本管理 | 产品能力 / 数据 | 支持单章生成版本、人工编辑版本、导出版本和回滚 | `docs/development/roadmap.md` |
| 未开始 | 混合检索与引用来源标注 | RAG | 支持 BM25/全文检索 + pgvector 混合检索，并能追溯章节正文来源 | `docs/rag/todo.md`、`docs/development/roadmap.md` |

## 已完成关键任务

| 完成时间 | 任务 | 说明 | 关联文档 |
| --- | --- | --- | --- |
| 2026-06 | DOCX 基础正式目录和字段刷新 | 目录独立成页、点引导线、页码域、页脚页码和总页数字段刷新已完成 | `docs/development/docx-bid-export-quality-todo.md` |
| 2026-06 | DOCX 表格和图片基础正式化 | 表格全宽、固定布局、表头加粗、图片只用泰昌企业事实资产、内部检索字段不进入正式 DOCX | `docs/development/docx-bid-export-quality-todo.md` |
| 2026-06 | DOCX 国网正式通用排版默认模板 | 默认模板切换为 `formal_bid_standard`，已按 A4、页边距、仿宋四号正文、22 磅行距、标题层级、表格小四、页眉页脚和字段刷新跑通真实导出验收 | `docs/development/runs/run_20260625_docx_formal_standard_local_acceptance.md` |
| 2026-06 | AI 辅助编辑 MVP 最小闭环 | 正文编辑器支持选区扩写、缩写、润色、正式化，真实模型返回后可预览、采纳、撤销并触发保存状态 | `docs/development/runs/run_20260625_ai_edit_mvp_ui_acceptance.md` |
| 2026-06 | 正式检查与导出门禁收口 | 当前演示项目正式检查阻断项 0、未解决占位符 0；完整 DOCX 导出验收 failures/warnings 均为空 | `docs/development/runs/run_20260625_placeholder_cleanup_docx_acceptance.md` |
| 2026-06 | 章节任务状态与批量生成可靠性基础版 | 任务表、章节 item、lease、超时、失败保稿、刷新恢复等基础能力已完成 | `docs/section-generation-production-remediation-todo.md` |
| 2026-06 | 技术标/商务标分册基础模型 | `volume_type`、分册 Tabs、分册生成和分册导出基础能力已完成 | `docs/技术标商务标分册整改TODO.md` |
| 2026-06 | 条款覆盖率命名和下载前风险提示 | “合规覆盖度”已收口为条款覆盖率/条款响应，下载前有风险提示 | `docs/合规覆盖度整改TODO.md` |
| 2026-06 | 泰昌/辽宁/河北豪乾资料边界 | 泰昌企业事实、辽宁招标要求、河北豪乾参考稿边界和 metadata 规则已建立 | `docs/rag/todo.md`、`AGENTS.md` |
| 2026-06 | 泰昌产品参数与项目业绩结构化 | CPVC/MPP 检验报告参数、项目业绩合同/中标通知书结构化抽取与真实问答链路已完成 | `docs/rag/todo.md` |
| 2026-06 | 企业库中文展示和人员证书归库 | 资信库/产品库中文展示名、人员证书归库和云上修复已完成主体闭环 | `docs/rag/todo.md` |
| 2026-06 | 单企业使用范围收口 | 当前 MVP 默认投标主体为河北泰昌电力器材科技有限公司，按单企业标书范围执行，不扩展多租户 | `AGENTS.md` |

## 散落文档归档规则

| 文档 | 现定位 | 是否继续维护 |
| --- | --- | --- |
| `docs/development/docx-bid-export-quality-todo.md` | DOCX 正式导出专项详情和验证记录 | 是，但优先级同步到本文档 |
| `docs/section-generation-production-remediation-todo.md` | 章节生成和 DOCX 历史整改详情 | 是，作为历史和专项执行记录 |
| `docs/rag/todo.md` | RAG、客户资料、泰昌数据工程专项详情 | 是，作为 RAG 专项总账 |
| `docs/development/formal-check-todo.md` | 正式检查模块专项详情 | 是，作为正式检查执行清单 |
| `docs/development/roadmap.md` | 中长期路线图 | 是，但不再作为当前优先级唯一来源 |
| `docs/合规覆盖度整改TODO.md` | 条款覆盖率历史整改记录 | 只归档，新增任务迁入本文档或正式检查专项 |
| `docs/技术标商务标分册整改TODO.md` | 分册化历史整改记录 | 只保留分册细节，新增任务迁入本文档 |
| `docs/deployment/aliyun-ubuntu-single-ecs-deploy-checklist-20260622.md` | 阿里云部署执行清单 | 是，作为部署操作记录 |

## 最近决策记录

| 日期 | 决策 | 影响 |
| --- | --- | --- |
| 2026-06-25 | 将 DOCX 正式交付排版升级重新提升为 P0 | 当前客户反馈的 Word 观感问题不再作为 P1/P2 延后处理 |
| 2026-06-25 | 建立项目任务总账 | 后续所有新任务和优先级变更必须先写入本文档 |
| 2026-06-25 | 将合同 MVP 功能清单纳入总账 | AI 辅助编辑由 P2 提升为 P0；产品库多品类展示、多格式导出口径进入 P1 |
| 2026-06-25 | DOCX 默认模板切换为 `formal_bid_standard` | 用户认可的国网正式通用排版口径已进入代码、验收脚本和文档；历史 `sgcc_taichang_bid` 不再作为默认 |
| 2026-06-25 | AI 辅助编辑 MVP 最小闭环完成 | 合同 MVP 中“扩写、缩写、润色、风格调整”已有真实模型与页面验收记录 |
| 2026-06-25 | 全文/分册 DOCX 导出接入正式检查门禁 | 阻断项存在时导出任务和前端提示均降级为草稿版，`formal_export_gate` metadata 可追溯 |
| 2026-06-25 | 正式检查与投标关键字段闭环完成 | 当前演示项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d` 已收口到阻断项 0、正文占位 0、正式必填缺口 0；完整 DOCX 真实链路验收 PASS |
| 2026-06-25 | 自定义编写要求持久化完成 | 单章“自定义编写”已从前端内存态改为章节 `writing_notes` + `metadata.custom_writing` 持久化，并作为生成任务 item metadata 快照进入后台链路 |
| 2026-06-25 | 新增子章节分册继承完成 | 技术/商务筛选下新增章节会写入对应分册 metadata；子章节默认继承父章节分册，后端也有父章节 metadata 继承兜底 |
| 2026-06-25 | 叶子章节转结构容器确认完成 | 对已有正文或目标字数的叶子章节新增子章节前会二次确认；支持保留父章节概述或迁移正文到首个子章节，并记录父子章节转换 metadata |
| 2026-06-25 | Prompt profile 分级瘦身完成 | 章节生成已按 profile 控制 RAG/企业资料/事实包/prompt 字符预算，并把 profile 指标写入任务 metadata；下一步进入慢流提前保护 |
| 2026-06-25 | 删除章节真实提示与撤销兜底完成 | 删除章节会明确提示同步删除后端数据；后端按章节子树删除；页面内保留最近一次删除的撤销恢复入口 |

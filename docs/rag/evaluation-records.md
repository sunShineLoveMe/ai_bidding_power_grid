# 召回评测记录

> 评测脚本：`scripts/rag/eval_recall.py`
> 测试集：`tests/rag/base_testset.jsonl`（30 条）
> 原始结果：`docs/rag/_run_filtered.json`、`docs/rag/_run_nofilter.json`

每次入库/策略调整后重跑并在此追加记录，形成可追溯的质量基线。

---

## Run 20260627 — 产品库/资信库上传表单资料规范产品化（2026-06-27）

> 总记录：`docs/development/runs/run_20260627_asset_upload_form_productization.md`
> 增量门禁：`docs/rag/runs/run_20260627_asset_upload_form_productization_gate_summary.md`

### 触发原因

客户后续会自行上传大量图片、PDF、Word、Excel、CSV 等资料。上传入口如果不做资料类型引导、文件质量预检和正式标书使用门禁，二维码、印章、局部截图、表格截图、内部文件名等低质量资料会进入 RAG 和正式 DOCX 候选，影响正式投标文件质量。

### 结果

- 产品库/资信库上传表单新增正式中文资料类型、推荐格式提示和文件质量预检。
- 资产上传支持 `.xls/.xlsx/.csv`，表格资料默认 `knowledge_only`，不自动作为正式标书图片插入。
- 后端上传入库写入 `quality_tier`、`quality_tier_label`、`quality_notes`、`user_requested_bid_usage`；DOCX 自动选图只允许 `formal_bid_ready`。
- 真实 API 上传 `泰昌上传表单回归产品参数表.csv`，返回 `quality_tier=knowledge_only`、`allowed_for_bid=false`，测试资产已删除。
- Chrome 页面回归：产品库 CSV 预检为“仅用于知识库”；资信库低质量局部截图预检为“需人工复核”。
- 定向测试：上传 payload `5 passed, 2 subtests passed`；DOCX/RAG/display `95 passed, 1 warning`；前端 build PASS。

### 增量门禁

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 93.3% | 100.0% | 0.917 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.973 | 0.0% | 0.0% |

门禁状态：PASS。Rerank 正式路径无召回、来源排序、禁用关键词或跨资料域串扰退化。

### 结论

产品库/资信库上传入口已具备面向用户的正式资料准入体验，后端同步执行质量等级和正式 DOCX 配图门禁，后续客户随意上传资料时不会直接污染正式标书正文。

---

## Run 20260627 — 泰昌正式资产治理本地真实回归（2026-06-27）

> 总记录：`docs/development/runs/run_20260627_local_formal_asset_regression.md`
> 资产审计：`docs/development/runs/run_20260627_local_formal_asset_regression_audit.md`
> 真实 stream：`docs/rag/runs/run_20260627_local_formal_asset_stream_regression.json`
> 增量门禁：`docs/rag/runs/run_20260627_local_formal_asset_regression_gate_summary.md`

### 触发原因

本地泰昌数据资产已完成正式中文化和图片题注治理，需要在推送阿里云测试环境前，用真实服务确认资产、RAG、页面和 DOCX 导出均不再暴露内部字段或旧式图片题注。

### 结果

- 资产审计：真实图片资产 599、知识文档 77、文档分块 6347，正式可见/RAG 可见问题均为 0；历史 staging payload 仍为解析中间产物，不参与正式展示。
- 真实 `/api/knowledge/search/stream`：覆盖 CPVC 检验报告参数、MPP 检验报告、生产制造能力、试验检测设备、资质证书、绿色低碳资料 6 类，HTTP 200，禁用字段命中 0。
- Chrome 页面：企业知识库列表和知识库助手 CPVC 参数问答页面渲染后禁用字段命中 0。
- DOCX 真实链路：技术标选中图片 16、商务标选中图片 5，字段刷新均 `refreshed`，禁用表达命中 0、页码型题注命中 0。
- 定向测试：`12 passed, 1 warning`。

### 增量门禁

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 50.0% | 63.3% | 0.500 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 53.3% | 63.3% | 0.533 | 0.0% | 0.0% |

门禁状态为 FAIL。Base 未退化；泰昌专项失败仍是旧评测集与本轮治理目标不一致导致，旧用例要求召回已被隔离的资产索引/解析中间 chunk。下一步需要更新泰昌专项评测集，改为检验正式资产、中文来源、结构化参数和页面同源回答。

### 结论

本地正式资产治理回归通过，可以进入阿里云测试环境发布与线上复验。剩余 P1 问题：更新泰昌专项评测集；试验检测设备问答中仍可能引用碳足迹报告里的设备描述，来源精度可继续收敛。

---

## Run 20260627 — 泰昌正式资料资产中文化与 RAG 可见字段治理（2026-06-27）

> 资产审计：`docs/development/runs/run_20260627_taichang_formal_asset_audit_visible_and_rag_zero.md`
> 增量门禁：`docs/rag/runs/run_20260627_taichang_formal_asset_cleanup_gate_summary.md`
> DOCX 真实导出：`docs/development/runs/run_20260627_formal_docx_asset_cleanup_v2/summary.json`

### 触发原因

真实技术标 DOCX 中出现 `图示：泰昌CPVC电缆保护管检验报告内径250第1页`、`图示：泰昌试验设备台账原图` 等不适合正式投标文件的图片说明。该问题会把内部追溯信息、解析命名和页码型说明暴露到正式投标正文，存在废标风险。

### 修复范围

- 新增正式资产命名与题注策略，区分正式标题、正式题注和追溯 metadata。
- RAG 选图和 DOCX 导出不再直接使用内部标题、解析目录名、`原图`、`页面_`、UUID、API 路径或页码型追溯说明。
- 批量回填泰昌真实图片资产、知识文档和文档分块的中文正式展示字段。
- 将 mock/test 资产、MinerU 局部切图、资产索引中间 chunk、解析路径类 chunk 隔离出正式 RAG 和标书选图。
- 知识问答公开返回字段做脱敏，避免把 `source_domain`、`target_library`、`specs`、`file_name`、`asset_path`、`parsed_outputs`、embedding/searchable_text 等内部字段返回到页面同源 stream。

### 本地审计结果

| 范围 | 扫描数 | 正式可见/RAG 可见问题数 |
| --- | ---: | ---: |
| 真实图片资产 | 599 | 0 |
| 知识文档 | 77 | 0 |
| 文档分块 | 6347 | 0 |
| staging 图片 payload | 539 | 539 |

staging 图片 payload 是历史解析中间产物，保留用于追溯和复核，不作为正式展示、RAG 问答或 DOCX 配图来源。后续新增客户资料必须按 SOP 重新生成整页正式资产，不能把 staging 局部切图直接入正式库。

### 增量门禁结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 286 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 634 ms |
| 泰昌专项 | off | 53.3% | 63.3% | 0.533 | 3.3% | 0.0% | 354 ms |
| 泰昌专项 | qwen3-rerank | 56.7% | 63.3% | 0.567 | 0.0% | 0.0% | 612 ms |

门禁状态为 FAIL。Base 未退化；泰昌专项失败的主要原因是旧专项用例仍期待历史资产索引/解析中间 chunk 被召回，而这些 chunk 本轮已按正式投标要求隔离为 `internal_only` / `exclude_from_rag`。处理结论是更新泰昌专项评测集，改为校验正式资产、结构化参数和中文参考来源，不应为通过旧门禁重新放开内部 chunk。

### 真实链路验证

- 本地真实 `/api/knowledge/search/stream` 抽样：未再暴露 `图示：`、`原图`、`页面_`、解析路径、内部枚举、向量字段或 API 资产路径。
- 本地真实技术标/商务标 DOCX：走 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`。技术标选图 16、商务标选图 5，字段刷新均为 `refreshed`，DOCX XML 审计 `forbidden_hits=[]`、`caption_page_hits=[]`。
- 尚未完成：阿里云线上数据库修复脚本执行、线上真实浏览器知识问答/标书导出复验。

### 结论

本地正式资产可见字段、RAG 返回字段和 DOCX 图片题注问题已收口；线上发布与专项评测集更新仍为后续阻塞项。

---

## Run 20260626 — 产品库/资信库上传入口收口与新资产索引回归（2026-06-26）

> 汇总：`docs/rag/runs/run_20260626_product_qualification_upload_index_regression_summary.md`
> 增量门禁：`docs/rag/runs/run_20260626_product_qualification_upload_index_regression_incremental_summary.md`
> 产品/资信库回归：`docs/development/runs/run_20260626_product_qualification_upload_index_regression.md`

### 触发原因

客户反馈产品库存在多个上传/新增入口，含义不清；同时产品图片上传后必须能按客户输入的资料名称、规格型号、标签和说明进入知识问答、技术标正文和标书配图索引。

### 修复范围

- 产品库和资信库上传入口收口为单一主入口。
- 新上传知识资产默认补充泰昌企业事实 metadata，避免真实 stream 中因 `enterprise/source_domain` 过滤无法命中新上传资产。
- 资产召回新增精确标题/规格关键词补召回，并对向量召回和关键词补召回结果去重重排。

### 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 255 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 599 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 352 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 749 ms |

真实浏览器上传 `泰昌CPVC电缆保护管模拟产品图片-20260626070309` 后，`POST /api/knowledge/search/stream` 命中新增资产 `17e53f70-649b-4a0c-8716-dfc5a502ed02`，返回内容包含新增标题和规格型号 `CPVC-DN250-真实回归`。

### 结论

本轮无召回、来源排序、禁用关键词或跨资料域串扰退化。上传入口收口和新上传资产索引链路通过真实页面、真实 API stream 和本地 RAG 门禁。

---

## Run 20260626 — 泰昌企业资料来源误解读专项收敛（2026-06-26）

> 汇总：`docs/rag/runs/run_20260626_taichang_enterprise_source_scope_final_review.md`
> 自动门禁：`docs/rag/runs/run_20260626_taichang_enterprise_source_scope_final_summary.md`
> 增量门禁：`docs/rag/runs/run_20260626_taichang_enterprise_source_scope_final_incremental_summary.md`
> 6 问审计：`docs/rag/runs/run_20260626_taichang_enterprise_source_audit_final_summary.json`

### 触发原因

阿里云 `f97b31a` 发布后，线上复查发现“泰昌有哪些资质证书？”仍可能受误标 `certification` 的 ESG、绿色发展、废水废气废固等资料污染。本轮按同类问题举一反三，检查本地真实库中其他资料是否存在被误解读或展示分类被覆盖。

### 修复范围

- 新增集中式证据类型收敛：资质证书、绿色低碳、人员社保、检验报告、生产制造能力、试验检测设备、营业执照。
- 同一收敛规则应用于文本上下文和图片资产，避免答案正文被不相关资产污染。
- 修复展示层 `sanitize_source_metadata`，不再用泛化“泰昌企业资料”覆盖具体分类；当 `category_label` 泛化且存在 `evidence_type` 时，展示具体证据类型。
- 新增 `scripts/rag/repair_taichang_green_asset_metadata.py`，用于把 ESG、绿色供应链、绿色发展规划、碳足迹、废水废气废固统一纠正为 `green_low_carbon`。
- 本地执行 metadata 修复：221 条绿色/低碳资产、1205 条相关 chunk 收敛为绿色低碳资料；修复后绿色/ESG/碳足迹/废水资料中 `certification_with_green_terms=0`。

### 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 254 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 573 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 353 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 690 ms |

真实 API 6 问审计全部 PASS：

- 资质证书：仅质量、环境、职业健康安全管理体系认证证书。
- 企业证明材料：三体系证书、营业执照、社保证明。
- 绿色低碳资料：ESG、绿色供应链、碳足迹、绿色发展规划，均显示为绿色低碳资料。
- 人员证书或社保证明：仅人员证书、人员花名册、社保证明。
- CPVC 检验报告：仅 CPVC 内径250结构化参数和检验报告原始页。
- 生产制造能力：仅厂房、生产线、生产制造能力资料。

### 结论

本地真实服务已完成企业资料来源误解读专项收敛，无召回、来源排序、禁用关键词或跨资料域串扰退化。下一步需提交并发布到阿里云，执行同一 metadata 修复脚本和线上 6 问复测后关闭 P1C-15。

---

## Run 20260626 — 阿里云资质证书负向来源过滤热修（2026-06-26）

> 自动门禁：`docs/rag/runs/run_20260626_aliyun_cert_negative_filter_hotfix_summary.md`
> 增量门禁：`docs/rag/runs/run_20260626_aliyun_cert_negative_filter_hotfix_incremental_summary.md`
> 真实 stream：`docs/rag/runs/run_20260626_aliyun_cert_negative_filter_hotfix_stream.jsonl`

### 触发原因

阿里云发布 `f97b31a` 后，容器代码检查确认存在 `_is_formal_certification_context`，但线上源码显示过滤顺序存在缺陷：先用泛化“认证证书”命中返回 True，再执行 ESG/绿色发展/废水类负向排除。若绿色发展、ESG、废水废气废固资料被误标为 `certification`，或正文/说明中带有“认证证书”，仍可能进入“泰昌有哪些资质证书？”的参考来源和回答资产。

### 修复范围

- 负向来源词优先拦截：`ESG`、`绿色发展规划`、`绿色供应链`、`碳足迹`、`废水废气`、`废水废气废固`。
- 正式证书正向命中只保留三类体系认证证书：质量管理体系、环境管理体系、职业健康安全管理体系。
- 资质证书查询不再在没有正式证书命中时回退填充绿色发展/ESG/废水类资料。
- 资质证书查询下同步过滤图片资产输入，避免参考来源已收敛但答案正文仍被资产污染。

### 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 275 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 597 ms |
| 泰昌专项 | off | 93.3% | 100.0% | 0.933 | 3.3% | 0.0% | 356 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 694 ms |

- 定向单测：`PYTHONPATH=. .venv/bin/pytest tests/test_rag_retrieval.py -q`，27 passed。
- 本地 RAG 门禁：PASS，api_ready / rag_unit_tests / incremental_regression_gate / stream_sample 全部通过。
- 真实 `/api/knowledge/search/stream` 资质证书问题：PASS，contexts=3，assets=6，BAD_TERMS=[]。
- `raw_contexts` 仅包含：质量管理体系认证证书、环境管理体系认证证书、职业健康安全管理体系认证证书。
- 本轮未新增资料、未执行入库、未批量修改数据库 metadata；仅调整检索后处理和资产输入过滤。

### 结论

本地热修通过，需发布到阿里云后重新执行线上 `/api/knowledge/search/stream` 抽样和真实页面复测，再关闭 P1C-15。

---

## Run 20260626 — 阿里云企业库展示与来源收敛本地收口（2026-06-26）

> 汇总：`docs/rag/runs/run_20260626_aliyun_enterprise_source_convergence_final_review.md`
> 自动门禁：`docs/rag/runs/run_20260626_aliyun_enterprise_source_convergence_final_summary.md`
> 增量门禁：`docs/rag/runs/run_20260626_aliyun_enterprise_source_convergence_final_incremental_summary.md`

### 触发原因

P1C-15 收口阿里云企业库剩余缺陷：资质证书问答来源混入 ESG/绿色发展/废水类资料、CPVC 检验报告回答泛化规格覆盖范围，以及公网 80 入口说明不清。

### 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 239 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 589 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 345 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 736 ms |

- API ready：PASS。
- RAG 定向单测：PASS，38 passed。
- Base 30 + 泰昌专项 30 增量门禁：PASS。
- 真实 `/api/knowledge/search/stream` 资质证书问题：PASS，contexts=3，assets=6，来源仅三体系认证证书。
- 真实 `/api/knowledge/search/stream` CPVC 检验报告问题：PASS，contexts=5，assets=6，回答限定为内径250/`DS 250×15×6000 SN16 PVC-C`/报告编号 `2024100312005501713`。
- 本轮未新增资料、未执行入库、未批量修改数据库 metadata；仅调整检索后处理、回答约束和部署端口配置。
- 云上只读检查：`http://8.160.187.226:8080/api/health` PASS；`http://8.160.187.226/api/health` 仍为 `Empty reply from server`，需发布本轮代码并设置 `FRONTEND_HTTP_PORT=80` 后复测。

### 结论

本地收口通过，无召回、来源排序、禁用关键词或跨资料域串扰退化。阿里云 P0 不提前关闭，待云上发布和 80 入口复测后关闭。

---

## Run 20260625 — 合同 MVP 覆盖验收 RAG 真实门禁（2026-06-25）

> 汇总：`docs/rag/runs/run_20260625_contract_mvp_acceptance_summary.md`
> 增量门禁：`docs/rag/runs/run_20260625_contract_mvp_acceptance_incremental_summary.md`

### 触发原因

合同 MVP 17 项功能进入统一真实链路验收，需要确认服务重启后知识库、企业资料、图片资产、metadata 边界和页面同源 stream 未退化。

### 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 268 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 590 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 350 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 734 ms |

- API ready：PASS。
- RAG 单测：PASS。
- Base 30 + 泰昌专项 30 增量门禁：PASS。
- 真实 `/api/knowledge/search/stream`：PASS，返回 5 条上下文、4 个资产、4 张图片。
- 本轮未新增资料、未调整 metadata 或召回策略，因此不执行入库和 inventory 变更。

### 结论

合同 MVP 验收未引入召回退化、来源排序退化或泰昌/辽宁/河北豪乾跨域串扰。

---

## Run 20260624 — 阿里云企业知识库线上真实回归（2026-06-24）

> 运行记录：`docs/rag/runs/run_20260624_aliyun_online_rag_regression.md`

### 触发原因

阿里云环境完成正式整页图片资产重建与 embedding backfill 后，需要复测 Run 39 中失败的企业知识库三问，确认二维码/局部裁剪图问题是否消失，并记录剩余云上缺陷。

### 本轮结论

- `GET http://8.160.187.226:8080/api/health` PASS，前端 `:8080` 可登录访问。
- formal batch 与 supplement batch 的 `knowledge_assets.embedding` 均已补齐：300/300、296/296。
- “泰昌有哪些资质证书？”主答案 PASS：返回质量、环境、职业健康安全三项认证，图片为整页证书，不再出现二维码/局部裁剪图。
- “泰昌有哪些企业证明材料？”主答案 PASS：返回营业执照、三体系认证、社保证明、土地租赁协议和土地使用证明；人员/社保证明归库修复后，参考来源“泰昌社保证明”已展示为“人员证书 · 资信库资料”。
- “泰昌 CPVC 电缆保护管有哪些检验报告？”主答案 PASS：返回 CPVC 内径250报告、规格 `DS 250×15×6000 SN16 PVC-C`、报告编号 `2024100312005501713` 和整页报告图片。

### 剩余缺陷

| 编号 | 优先级 | 问题 |
| --- | --- | --- |
| ALI-RAG-002 | P1 | 资质证书问答参考来源混入 ESG、废水废气废固报告，主答案正确但来源收敛不够干净 |
| ALI-RAG-003 | P1 | CPVC 报告回答存在“无需补充其他规格”与“仅覆盖内径250”的措辞冲突 |
| ALI-RAG-004 | P1 | 公网 80 端口返回 `Empty reply from server`，实际测试入口为 `:8080` |

已关闭缺陷：

| 编号 | 原优先级 | 处理结果 |
| --- | --- | --- |
| ALI-RAG-001 | P0 | 阿里云执行 `repair_enterprise_asset_library_display.py --execute` 后，596 条资产扫描、18 条更新、18 条人员资产迁移；Chrome 真实页面复测确认“泰昌社保证明”显示为“人员证书 · 资信库资料” |

### 处理结论

阿里云 RAG 核心修复通过，ALI-RAG-001 已关闭，可以进入最小标书主流程云上冒烟；ALI-RAG-002、ALI-RAG-003 和 ALI-RAG-004 继续按 P1 收口。

---

## Run 20260621 — 招标项目项目化上下文与解读页可用性回归（2026-06-21）

> 回归记录：`docs/rag/runs/run_20260621_interpretation_project_context_summary.md`
> 增量门禁：`docs/rag/runs/run_20260621_interpretation_project_context_incremental_summary.md`
> 真实 stream 抽样：`docs/rag/runs/run_20260621_interpretation_project_context_stream.jsonl`

### 触发原因

客户测试发现点击“招标项目”后直接进入解读页，但不知道当前是哪一次招标文件解析、是否为最近一次、前几次解析从哪里找；同时怀疑“解读总览、条款响应、资格与要求、风险检查、评分办法、章节建议”等标签在多轮架构调整后是否仍真实可用。

### 本轮结论

- 默认 `/interpretation` 入口确认为“最近一个已有结构化解读的招标项目”，当前返回项目 `628ed517-0c31-44ea-a5cb-95b25db06fc2`，创建时间 `2026-06-20 17:30`。
- 前几次解析记录仍在历史记录中，可通过 `/interpretation?projectId=<项目ID>` 精确打开；页面已新增历史项目下拉和“查看全部历史”入口。
- 红框标签真实可用：当前项目要求 80、风险 60、评分 80；章节建议旧字段为空，但已回退使用分册大纲/章节数据，页面显示 253 条候选/章节。
- 浏览器真实页面验证通过：项目来源、项目 ID、创建时间、招标编号、招标文件名、历史切换、进入标书编制按钮均可见，1440 宽无横向溢出。

### 回归门禁

| 命令 | 结果 |
| --- | --- |
| `pytest tests/test_project_latest_interpretation.py tests/test_celery_interpretation_tasks.py tests/test_api_sections.py tests/test_bid_prefill.py -q` | PASS，23 passed |
| `cd frontend && npm run build` | PASS，仅保留既有 chunk size 警告 |
| 真实 HTTP 抽样 `/api/bidding/history?limit=5`、`/api/bidding/interpretations/latest` | PASS |
| `scripts/rag/run_local_rag_gate.py --run-id run_20260621_interpretation_project_context` | PASS |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 296 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 830 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 342 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 850 ms |

### 阿里云测试环境注意

本轮不需要数据库迁移。部署到阿里云测试环境后，重点检查目标库中 `/api/bidding/history` 和 `/api/bidding/interpretations/latest` 是否返回同一批项目数据，并确认页面可切换历史项目。

---

## Run 20260621 — 企业库客户测试展示与人员证书归库修复（2026-06-21）

> 资产修复 dry-run：`docs/rag/runs/run_20260621_enterprise_asset_display_repair_dry_run.json`
> 资产修复执行记录：`docs/rag/runs/run_20260621_enterprise_asset_display_repair_execute.json`
> 资产修复后检查：`docs/rag/runs/run_20260621_enterprise_asset_display_repair_postcheck.json`
> 本地门禁：`docs/rag/runs/run_20260621_enterprise_asset_display_repair_summary.md`
> 增量门禁：`docs/rag/runs/run_20260621_enterprise_asset_display_repair_incremental_summary.md`

### 触发原因

客户测试发现企业资信库“人员证书”为空、人员证书误出现在企业产品库，且企业资信库/产品库/知识库展示的资料名称不够友好；编辑资产时缺少当前图片预览，不利于客户判断是否替换。

### 修复范围

| 项 | 结果 |
| --- | ---: |
| 扫描知识资产 | 597 |
| 更新人员相关资产 | 26 |
| 从产品资产迁回资信资产 | 18 |
| 修复后人员证书资信资产 | 26 |
| 修复后产品库人员证书残留 | 0 |

本轮只更新人员证书相关资产的 `asset_type/category/metadata/specs/searchable_text`，不移动文件、不改变 asset id 和 storage path；企业资信库、企业产品库和企业知识库页面使用展示层友好名称，不批量重写非人员资产底层标题。

### 回归门禁

| 命令 | 结果 |
| --- | --- |
| `py_compile backend/api/assets.py backend/rag/display_names.py scripts/rag/repair_enterprise_asset_library_display.py` | PASS |
| `pytest tests/test_asset_display_repair.py tests/test_rag_display_names.py tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q` | PASS，30 passed |
| `cd frontend && npm run build` | PASS，仅保留既有 chunk size 警告 |
| `scripts/rag/run_local_rag_gate.py --run-id run_20260621_enterprise_asset_display_repair` | PASS |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 285 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 660 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 336 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 849 ms |

### 阿里云测试环境注意

部署到阿里云后，需在目标数据库执行一次：

```bash
set -a; source .env; set +a; .venv/bin/python scripts/rag/repair_enterprise_asset_library_display.py --execute --save docs/rag/runs/run_aliyun_enterprise_asset_display_repair_execute.json
```

脚本默认只迁移人员证书相关资产；非人员资产标题清洗必须显式增加 `--include-title-cleanup`，避免上线前批量改写检索文本。

### 结论

- 企业资信库人员证书归库问题已修复，产品库不再显示人员证书。
- 页面展示和编辑体验已优化，不影响标书自动插图和知识库图片文件 URL。
- 本地 RAG 门禁 PASS，无召回、来源排序、禁用关键词或跨资料域串扰退化。

---

## Run 20260619-P1C-11 — 内部演示完整标书模拟确认值回归（2026-06-19）

> 模拟确认值应用记录：`docs/development/runs/run_20260619_p1c11_simulated_complete_bid.md`
> DOCX/PDF 验收记录：`docs/development/runs/run_20260619_p1c11_simulated_complete_bid_acceptance.md`
> 本地门禁：`docs/rag/runs/run_20260619_p1c11_simulated_complete_bid_summary.md`
> 增量门禁：`docs/rag/runs/run_20260619_p1c11_simulated_complete_bid_incremental_summary.md`

### 触发原因

客户未回复投标总价、保证金、授权代表等正式决策字段，但当前目标是先真实生成一份参考客户模板的完整标书用于内部演示和系统回归。因此本轮通过显式开关 `--simulate-formal-fields` 写入模拟确认值，并在 metadata 标记 `simulated_for_regression=true`。这些值不代表正式投标承诺。

### 模拟字段

| 字段 | 模拟值口径 |
| --- | --- |
| 投标总价 | `8888888.00 元（内部测试模拟值，非正式报价）` |
| 投标总价大写 | `人民币捌佰捌拾捌万捌仟捌佰捌拾捌元整（内部测试模拟值，非正式报价）` |
| 税率 | `13%（内部测试模拟值）` |
| 投标保证金金额 | `100000.00 元（内部测试模拟值，非正式保证金金额）` |
| 投标保证金形式 | `投标保证保险（内部测试模拟值）` |
| 交货期承诺 | `按招标文件及合同约定执行，内部测试模拟为合同签订后 30 日内完成供货。` |
| 质保期承诺 | `按招标文件及合同约定执行，内部测试模拟为到货验收合格后 12 个月。` |
| 投标有效期 | `90` |
| 授权代表 | `张三（内部测试模拟授权代表）` |
| 授权代表身份证号 | `110101199001011234（内部测试模拟身份证号）` |
| 签署日期 | `2026年06月19日（内部测试模拟签署日期）` |

### 真实项目验收

真实项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d`：

| 项 | 结果 |
| --- | ---: |
| 章节节点 | 102 |
| 有正文章节 | 102 |
| 空叶子章节 | 0 |
| 正文占位符 | 0 |
| 正式必填缺口 | 0 |
| 图片候选 / 选中 / 插入 / 失败 | 597 / 23 / 23 / 0 |
| 补充包项目业绩资产 | 2 |
| 补充包检测能力资产 | 4 |
| 补充包检验报告资产 | 5 |
| 表格数量 | 166 |
| LibreOffice 字段刷新 | refreshed |
| DOCX/PDF 验收状态 | PASS |

输出文件：

- DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.docx`
- PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-图文.pdf`

### 回归门禁

| 命令 | 结果 |
| --- | --- |
| `py_compile scripts/rag/run_taichang_formal_export_gate_closure.py backend/services/bid_prefill.py backend/api/routes.py` | PASS |
| `pytest tests/test_bid_prefill.py tests/test_docx_export.py -q` | PASS，46 passed |
| `scripts/rag/run_taichang_formal_export_gate_closure.py --run-id run_20260619_p1c11_simulated_complete_bid --project-id a1d853bc-ca4e-43b4-bbea-256f561c8a3d --include-containers --simulate-formal-fields` | PASS，正式缺口 0 |
| `scripts/rag/verify_taichang_full_bid_acceptance.py --run-id run_20260619_p1c11_simulated_complete_bid_acceptance --project-id a1d853bc-ca4e-43b4-bbea-256f561c8a3d --expected-min-sections 100 --expected-min-non-empty-sections 100 --pdf-preview` | PASS |
| `scripts/rag/run_local_rag_gate.py --run-id run_20260619_p1c11_simulated_complete_bid` | PASS |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 281 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 693 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 353 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 845 ms |

### 结论

- 内部演示完整标书版已真实导出并通过成品结构验收。
- 当前 PASS 基于模拟客户确认字段，只能用于演示/回归；正式投标前必须替换为客户真实确认值并复跑验收。
- RAG 本地门禁 PASS，无召回、来源排序、禁用关键词或跨资料域串扰退化。

---

## Run 20260618-P1C-10 — 正式导出门禁正文与图片收口回归（2026-06-18）

> 生成收口记录：`docs/development/runs/run_20260618_p1c10_formal_gate_closure.md`
> DOCX/PDF 验收记录：`docs/development/runs/run_20260618_p1c10_formal_gate_acceptance_final6.md`
> 本地门禁：`docs/rag/runs/run_20260618_p1c10_formal_gate_closure_summary.md`
> 增量门禁：`docs/rag/runs/run_20260618_p1c10_formal_gate_closure_incremental_summary.md`

### 触发原因

P1C-9 已证明正式导出门禁能正确阻断半成品，但真实项目仍有 63 个空叶子章节、26 处正文占位符和 17 个正式必填缺口。本轮按真实环境继续收口：只自动应用可确认字段和结构化候选，生成剩余章节正文，清理模型遗留占位；投标总价、保证金、交货期、授权代表等客户决策字段继续阻断，不自动编造。

### 真实项目验收

真实项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d`：

| 项 | 结果 |
| --- | ---: |
| 章节节点 | 102 |
| 有正文章节 | 102 |
| 空叶子章节 | 0 |
| 正文占位符 | 0 |
| 正式必填缺口 | 11 |
| 图片候选 / 选中 / 插入 / 失败 | 597 / 23 / 23 / 0 |
| 补充包项目业绩资产 | 2 |
| 补充包检测能力资产 | 4 |
| 补充包检验报告资产 | 5 |
| 表格数量 | 166 |
| LibreOffice 字段刷新 | refreshed |
| 验收状态 | FAIL，仅因客户确认字段未填 |

缺口字段包括：投标总价、投标总价大写、税率、投标保证金金额、投标保证金形式、交货期承诺、质保期承诺、投标有效期、授权代表、授权代表身份证号、签署日期。

### 回归门禁

| 命令 | 结果 |
| --- | --- |
| `py_compile backend/api/routes.py` | PASS |
| `pytest tests/test_docx_export.py -q` | PASS，37 passed |
| `scripts/rag/run_taichang_formal_export_gate_closure.py --run-id run_20260618_p1c10_formal_gate_closure --project-id a1d853bc-ca4e-43b4-bbea-256f561c8a3d --include-containers` | PASS，生成 88/88，空叶子章节 0，占位 0 |
| `scripts/rag/verify_taichang_full_bid_acceptance.py --run-id run_20260618_p1c10_formal_gate_acceptance_final6 --project-id a1d853bc-ca4e-43b4-bbea-256f561c8a3d --expected-min-sections 100 --expected-min-non-empty-sections 90 --pdf-preview` | FAIL，符合客户字段阻断预期 |
| `scripts/rag/run_local_rag_gate.py --run-id run_20260618_p1c10_formal_gate_closure` | PASS |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 284 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 601 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 346 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 680 ms |

### 结论

- 正文与图片自动化收口通过：空章节、正文占位和补充包图片覆盖问题已关闭。
- 正式交付门禁仍必须保持 FAIL，直到客户确认 11 个投标决策字段。
- RAG 本地门禁 PASS，无召回、来源排序、禁用关键词或跨资料域串扰退化。

---

## Run 20260618 — 正式导出门禁真实验收与回归（2026-06-18）

> DOCX/PDF 验收记录：`docs/development/runs/run_20260618_formal_export_gate_real_acceptance.md`
> 本地门禁：`docs/rag/runs/run_20260618_formal_export_gate_real_acceptance_summary.md`
> 增量门禁：`docs/rag/runs/run_20260618_formal_export_gate_real_acceptance_incremental_summary.md`

### 触发原因

P4-11 已完成章节候选确认值批量应用与导出前门禁。本轮按真实环境验收口径复核：正式 DOCX/PDF 导出链路可以生成文件，但如果前导确认字段、正文占位符或章节正文未达标，验收脚本必须明确 FAIL，避免把“可生成”误认为“可正式交付”。

### 真实项目验收

真实项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d`：

| 项 | 结果 |
| --- | ---: |
| 章节节点 | 102 |
| 有正文章节 | 14 |
| 空叶子章节 | 63 |
| 正文占位符 | 26 |
| 正式必填缺口 | 17 |
| 图片候选 / 选中 / 插入 / 失败 | 597 / 24 / 24 / 0 |
| LibreOffice 字段刷新 | refreshed |
| 验收状态 | FAIL |

缺口字段包括：招标人、包号、包名称、货物清单摘要、投标总价、投标总价大写、税率、投标保证金金额、投标保证金形式、交货期承诺、质保期承诺、投标有效期、授权代表、授权代表身份证号、签署日期、技术参数表候选摘要、技术偏差表候选。

### 回归门禁

| 命令 | 结果 |
| --- | --- |
| `py_compile scripts/rag/verify_taichang_full_bid_acceptance.py backend/services/bid_prefill.py` | PASS |
| `pytest tests/test_bid_prefill.py tests/test_docx_export.py -q` | PASS，46 passed |
| `scripts/rag/verify_taichang_full_bid_acceptance.py --run-id run_20260618_formal_export_gate_real_acceptance --project-id a1d853bc-ca4e-43b4-bbea-256f561c8a3d --expected-min-sections 100 --expected-min-non-empty-sections 90 --pdf-preview` | FAIL，符合门禁预期 |
| `scripts/rag/run_local_rag_gate.py --run-id run_20260618_formal_export_gate_real_acceptance` | PASS |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 277 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 586 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 339 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 682 ms |

### 结论

- 验收脚本已把 `formal_readiness.ready=false` 纳入失败项。
- 当前真实项目仍不得作为正式投标文件交付；必须先补齐客户确认字段、清理正文占位符，并生成/补齐剩余叶子章节正文。
- RAG 本地门禁 PASS，无召回、来源排序、禁用关键词或跨资料域串扰退化。

---

## Run 20260618-P4-11 — 章节候选确认值批量应用与导出前门禁（2026-06-18）

> 实施记录：`docs/rag/runs/run_20260618_p4_11_prefill_gate_apply_impl.md`
> 本地门禁：`docs/rag/runs/run_20260618_p4_11_prefill_gate_apply_summary.md`
> 增量门禁：`docs/rag/runs/run_20260618_p4_11_prefill_gate_apply_incremental_summary.md`

### 触发原因

P4-10 已完成章节级候选展示。本轮把展示层推进到确认闭环：页面支持按章节采纳候选到客户确认草稿，后端应用确认值后返回章节级应用摘要和导出前 gate。仍然只替换明确占位符，不生成正文，不处理 PDF 字体或乱码。

### 功能验证

真实项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d`：

| 项 | 结果 |
| --- | ---: |
| 章节候选数 | 22 |
| 当前草稿正式必填缺口 | 10 |
| 正文未解析占位符 | 39 |
| readyForFormalExport | false |

真实浏览器验证：

- 页面显示“导出前门禁”和“仍需收口”。
- 页面显示 `正文占位 39`。
- 页面存在 22 个“采纳本章候选”按钮。
- 点击首个“采纳本章候选”只更新本地草稿，未提交正式应用。
- 控制台仅有既有 Ant Design `Drawer bodyStyle` 弃用提示，无 P4-11 新增功能错误。
- 截图：`output/playwright/run_20260618_p4_11_prefill_gate.png`

### 回归门禁

| 命令 | 结果 |
| --- | --- |
| `py_compile backend/services/bid_prefill.py` | PASS |
| `pytest tests/test_bid_prefill.py -q` | PASS，9 passed |
| `cd frontend && npm run build` | PASS |
| `scripts/rag/run_local_rag_gate.py --run-id run_20260618_p4_11_prefill_gate_apply` | PASS |

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 293 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 611 ms | 26 |
| 泰昌专项 | off | 93.3% | 100.0% | 0.933 | 3.3% | 0.0% | 349 ms | 0 |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 688 ms | 30 |

门禁结论：PASS。以 qwen3-rerank 为泰昌专项正式门禁口径，无来源排序、禁用关键词或跨资料域串扰退化。

---

## Run 20260618-P4-10 — 章节级候选展示与缺口清单 UI 收口（2026-06-18）

> 实施记录：`docs/rag/runs/run_20260618_p4_section_candidate_ui_impl.md`
> 本地门禁：`docs/rag/runs/run_20260618_p4_section_candidate_ui_summary.md`
> 增量门禁：`docs/rag/runs/run_20260618_p4_section_candidate_ui_incremental_summary.md`

### 触发原因

P4-8/P4-9 已把货物清单、技术参数表、技术偏差表和泰昌检验报告参数佐证接入前导页候选层。本轮把这些结构化候选按真实标书章节归类展示，便于客户确认“哪些表格字段要进入哪一章”。本轮不生成正文，不处理 PDF 字体或乱码。

### 功能验证

真实项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d`：

| 项 | 结果 |
| --- | ---: |
| 章节候选数 | 22 |
| 总缺口数 | 25 |
| 技术响应文件 | 候选 10，缺口 6 |
| 技术偏差表 | 候选 2，缺口 2 |
| 技术特性参数表 | 候选 2，缺口 1 |
| 产品制造与质量控制 | 候选 3，缺口 1 |

真实浏览器验证：

- 页面显示“章节候选与缺口清单”。
- 页面包含 `技术特性参数表`、`技术偏差表`、`报价文件及货物清单`、`产品制造与质量控制`。
- 章节候选卡片展示来源边界：招标要求候选需客户确认，禁止作为泰昌企业事实；偏差表候选不自动生成无偏差结论。
- 截图：`docs/rag/runs/artifacts/run_20260618_p4_section_candidate_ui.png`

### 回归门禁

| 命令 | 结果 |
| --- | --- |
| `py_compile backend/services/bid_prefill.py` | PASS |
| `pytest tests/test_bid_prefill.py -q` | PASS，8 passed |
| `cd frontend && npm run build` | PASS |
| `scripts/rag/run_local_rag_gate.py --run-id run_20260618_p4_section_candidate_ui` | PASS |

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 279 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 595 ms | 27 |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 337 ms | 0 |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 672 ms | 30 |

门禁结论：PASS，无召回、来源排序、禁用关键词或跨资料域串扰退化。

---

## Run 1 — P0 基线（2026-06-02）

### 环境

| 项 | 值 |
| --- | --- |
| Embedding | Ollama `qwen3-embedding:0.6b` @ 1024 维 |
| 向量库 | pgvector pg16，HNSW（m=16, ef_construction=64） |
| 分块 | 父子双层 v2（`parent_child_v2`） |
| 语料 | power_grid 种子库：298 parent + 2449 child（child 全部嵌入） |
| 召回 | `match_knowledge_chunks_filtered`，k=5，threshold=0.2 |
| Rerank | 未启用（基线） |

### A/B：metadata 过滤的价值

| 指标 | 过滤 ON | 过滤 OFF | 差值 |
| --- | --- | --- | --- |
| Recall@5 | **86.7%** | 80.0% | +6.7pp |
| 来源类别准确率(top1) | **100%** | 83.3% | +16.7pp |
| 跨 doc_role 串扰均值 | **0.0%** | 30.0% | −30.0pp |
| 关键词命中率 | 86.7% | 93.3% | −6.6pp |

分场景 Recall@5：

| scenario | 过滤 ON | 过滤 OFF |
| --- | --- | --- |
| qa (15) | 93% | 93% |
| writing (11) | 91% | 82% |
| compliance (4) | 50% | 25% |

### 结论

1. metadata 过滤把**跨 doc_role 串扰从 30% 降到 0%**，来源类别准确率升到 100%，验证了评审稿“过滤先行”的核心判断。
2. compliance 场景受益最大（25%→50%），因为合规问题最容易召回到相邻但错误的法规/规章。
3. 关键词命中率在过滤 OFF 时略高，是因为关键词可能出现在“相似但 doc_role 不对”的片段里——这正是串扰，过滤后被正确排除，属预期。

### 失败用例分析（过滤 ON 未命中 4 条）

| 用例 | 现象 | 根因 | 处置 |
| --- | --- | --- | --- |
| T17 国网招标活动管理办法 | top1 召回到“中国政府网版权”片段 | **源数据问题**：文件 25 的 source_url 是 gov.cn 占位，抓到政府网首页而非规章正文 | 需重新采集源文件（非 RAG 缺陷） |
| T18 国网供应商不良行为 | top1 召回到“个人中心/邮箱/无障碍”导航 | 同上，文件 26 源数据为网站导航 | 需重新采集 |
| T04 否决投标情形 | 实际 top1 是“第四十二条 否决所有投标”，内容正确 | 关键词标注过严（“无效”未覆盖“否决”表述） | 优化测试集关键词 |
| T20 配电网技术导则 | 召回到标准目录条目而非正文 | 该标准仅入库了标准号/名称索引 | 待 P1 补全文解析 |

> 4 条失败中，2 条是源数据采集问题、1 条是测试集标注偏严、1 条是标准全文待解析——**没有一条是分块或召回逻辑的缺陷**。真实可改进项是源数据质量。

### 复现命令

```bash
ollama serve            # 启动本地 embedding
python scripts/rag/eval_recall.py --k 5 --save docs/rag/_run_filtered.json
python scripts/rag/eval_recall.py --k 5 --no-filter --save docs/rag/_run_nofilter.json
```

---

## 待办（下一次 Run 前）

- [ ] 重新采集国网规章 25/26/27 源文件（解决 T17/T18）。
- [ ] P1：解析客户江西/山西铁构件标书（.docx/.doc/.xlsx），纳入测试集与负样本。
- [ ] 对比启用 Rerank（qwen3-rerank）对 Recall@5 / MRR 的增量。
- [ ] 升维实验：1024 vs 1536（需全量重嵌）在本测试集上的收益。

---

## Run 20260611 — 泰昌资质补充包与 Logo 入库回归（2026-06-11）

> 完整记录：`docs/rag/runs/run_20260611_taichang_supplement_full_summary.md`
> 增量门禁：`docs/rag/runs/run_20260611_taichang_supplement_ingestion_summary.md`
> 真实 stream：`docs/rag/runs/run_20260611_taichang_supplement_real_stream.json`

### 触发原因

客户补充 `泰昌资质文件(补充).zip` 和泰昌官方 Logo，需要按泰昌 MVP 试点企业事实资料入库，并验证不会破坏既有 Base 与泰昌专项召回质量。

### 入库数据

| 项 | 数量 |
| --- | ---: |
| inventory 文件 | 70 |
| 文本入库文档 | 13 |
| parent chunks | 33 |
| child chunks / embeddings | 331 |
| 正式图片资产 payload | 297 |
| 图片资产导入成功 | 297 |
| metadata blocked | 0 |

### 回归门禁

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% |

门禁结论：PASS，无召回、来源排序、禁用关键词或跨资料域串扰退化。

### 真实链路抽样

真实 `/api/bidding/knowledge/search/stream` 验证了：

- CPVC/MPP 内径 250 检验报告参数可返回报告编号、平均内径、环刚度；
- 泰昌官方 Logo、MPP 生产线、宣传彩页等图片资产可被召回；
- 中标通知书专项问题可返回项目名称、招标编号 `0322AB`、包号 `157-保护管（CPVC和MPP） 包2_电缆保护管MPP和CPVC`；
- 复合问题“合同或中标通知书”中，检索层能命中资料，但生成回答漏提中标通知书，记录为回答合成完整性待优化项。

### 处置记录

- 新增 staging 脚本 `scripts/rag/stage_taichang_supplement_20260611.py`。
- 文本抽取清洗 NUL/control 字符，解决 PostgreSQL text 写入限制。
- 签名、手章、公章图片仅归档，设置为不自动用于标书。
- CPVC/MPP 检验报告编号与既有结构化参数层一致，本次只补充可追溯文本与图片来源，不重复新增参数行。

---

## Run 20260611-P1B — 泰昌补充资料质量增强与复合问答修复（2026-06-11）

> 质量复核：`docs/rag/runs/run_20260611_taichang_supplement_p1b_quality.md`
> DOCX 验证：`docs/development/runs/run_20260611_taichang_supplement_p1b_docx_export.md`
> 增量门禁：`docs/rag/runs/run_20260611_taichang_supplement_p1b_compound_fix_summary.md`

### 触发原因

针对 P1B 清单继续推进泰昌资质补充资料，从“已入库可检索”提升到“能支撑真实问答和真实 DOCX 导出”。重点修复复合问题“合同或中标通知书”漏答，并验证新增资产在正式标书导出中的使用情况。

### 处理内容

- `backend/rag/retrieval.py` 补充合同、中标通知书、项目业绩等并列证据的关键词扩展与资产补召回。
- 知识库回答 prompt 增加多资料类型逐项核对要求，避免检索命中后仍笼统回答“未发现”。
- `backend/api/routes.py` 增加项目业绩、Logo 证据类型画像，并收紧自动插图章节，避免图片额度被泛化章节提前耗尽。
- 导出图片 manifest 增加 `evidence_type`、`target_library`、`source_batch_id`，便于追溯本次补充包是否进入 DOCX。

### 真实库与真实 stream

| 指标 | 数量 |
| --- | ---: |
| 补充批次文档 | 13 |
| 补充批次 chunks | 364 |
| 补充批次图片资产 | 297 |
| 异常资产 metadata | 0 |

真实 `/api/bidding/knowledge/search/stream` 抽样：

| 用例 | HTTP | 资料/资产召回 | 结论 |
| --- | ---: | --- | --- |
| 合同或中标通知书 | 200 | 2/8 | 通过，同时覆盖合同和中标通知书，含招标编号 `0322AB` |
| Logo 与生产线/产品图片 | 200 | 4/8 | 通过 |
| CPVC/MPP 内径 250 检验报告参数 | 200 | 5/8 | 通过 |

### 增量回归

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% |

门禁结论：PASS。

### DOCX 真实导出

真实链路 `build_project_bid_markdown -> convert_md_to_word -> refresh_docx_fields_with_soffice`：

- 图片候选 597，选中 24，插入 24，失败 0；
- 选中图片中 18 张来自 `customer_taichang_supplement_20260611`；
- 覆盖证据类型：基础证照 2、资质证书 5、项目业绩 4、试验检测 4、生产制造 2、检验报告 1；
- 字段刷新 `refreshed`；
- DOCX 未出现 Mermaid 源码、内部来源字段、匹配依据或 metadata 文案；
- Warning：Logo 已在资产库，但尚未自动插入 DOCX 封面/页眉，后续归入 P1B-6。

---

## Run 20260612-P1B-OCR — 泰昌补充资料 MinerU OCR 增强（2026-06-12）

> OCR 报告：`parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/p1b_mineru_ocr_report.md`
> 入库报告：`parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/ingest_customer_corpus_report.md`
> 真实 stream：`docs/rag/runs/run_20260612_taichang_supplement_p1b_mineru_ocr_fix2_stream.md`
> 增量门禁：`docs/rag/runs/run_20260612_taichang_supplement_p1b_mineru_ocr_fix2_summary.md`

### 触发原因

客户确认继续推进 PDF OCR 增强。补充包中部分扫描 PDF 原生文本量为 0 或低于 1000 字，之前主要作为整页图片资产参与展示，不能稳定支撑问答和后续结构化抽取。

### 处理内容

- 新增 `scripts/rag/run_taichang_supplement_mineru_ocr.py`，按补充包 inventory 筛选低文本/无文本 PDF 并逐份提交真实 MinerU。
- 15 份扫描 PDF 完成 MinerU OCR，失败 0；包含土地证明、人员证书/花名册、体系认证证书、投标保证金凭证、中标通知书、绿色证书和 50 页宣传彩页。
- `manifest.json` 更新 15 份 OCR 结果，`parser=mineru_ocr`、`ocr_enhanced=true`、`source_domain=enterprise_fact`，仍保持泰昌企业事实边界。
- 真实入库后，本批文本资料从 13 份扩展到 24 份，写入 213 个 parent、1687 个 child embedding；数据库复核为 24 个文档、1900 个 chunk、297 个图片资产、异常资产 metadata=0。
- OCR 后合同 chunk 数量增加，复合问题“合同或中标通知书”一度被合同上下文挤占；已补充复合证据覆盖排序，确保合同和中标通知书同时进入上下文/资产结果。
- 同步补充“输电线路施工主要工序”关键词兜底，修复 Base T26 在 self_phrase 场景下偶发 0 召回。

### 回归门禁

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% |

门禁结论：PASS，无召回、来源排序、禁用关键词或跨资料域串扰退化。

### 真实链路抽样

真实 `/api/bidding/knowledge/search/stream` 抽样通过：

- 合同或中标通知书复合问题可同时覆盖供货合同和中标通知书，并保留招标编号 `0322AB`；
- Logo、生产线、产品图片等资产仍可按泰昌企业事实召回；
- CPVC/MPP 内径 250 检验报告参数仍可返回结构化参数和来源。

---

## Run 2 — 删除水利误入库记录后的复验（2026-06-02）

> 摘要：`docs/rag/runs/run_20260602_152803_summary.md`
> 原始结果：`docs/rag/runs/run_20260602_152803_filtered.json`、`docs/rag/runs/run_20260602_152803_nofilter.json`

### 触发原因

从本地 PostgreSQL 的 `knowledge_documents` 中删除误入库水利资料：

```text
19_塔里木河流域希尼尔水库除险加固工程坝基防渗处理施工标招标文件_b7a2c0d3.pdf
```

删除后复跑 Base 测试集，确认电网 RAG 基座召回质量没有退化。

### 数据快照

| 项 | 数量 |
| --- | ---: |
| `knowledge_documents` | 26 |
| `document_chunks` | 3459 |
| `document_chunks.embedding is not null` | 2449 |
| `power_grid_docs` | 26 |
| `power_grid_chunks` | 2747 |

### A/B：metadata 过滤的价值

| 指标 | 过滤 ON | 过滤 OFF | 差值 |
| --- | ---: | ---: | ---: |
| Recall@5 | **86.7%** | 80.0% | +6.7pp |
| 来源类别准确率(top1) | **100.0%** | 83.3% | +16.7pp |
| 跨 doc_role 串扰均值 | **0.0%** | 30.0% | -30.0pp |
| 关键词命中率 | 86.7% | 93.3% | -6.6pp |

分场景 Recall@5：

| scenario | 过滤 ON | 过滤 OFF |
| --- | ---: | ---: |
| qa (15) | 93% | 93% |
| writing (11) | 91% | 82% |
| compliance (4) | 50% | 25% |

### 失败用例分析（过滤 ON 未命中 4 条）

| 用例 | 现象 | 根因 | 处置 |
| --- | --- | --- | --- |
| T04 否决投标情形 | top1 是“第四十二条 否决所有投标” | 关键词标注偏严，`无效` 未覆盖 `否决` 表述 | 优化测试集关键词 |
| T17 国网招标活动管理办法 | top1 召回到“中国政府网版权”片段 | 源文件抓到政府网首页/版权页 | 重新采集源文件 |
| T18 国网供应商不良行为 | top1 召回到“个人中心/邮箱/无障碍”导航 | 源文件含网站导航噪声 | 重新采集源文件 |
| T20 配电网技术导则 | top1 是标准编号/名称摘要 | 该标准仅入库标准目录/摘要，非正文全文 | P1 补全文解析 |

### 结论

Run 2 与 Run 1 指标保持一致，删除误入库水利资料后没有造成召回退化。metadata 过滤仍将跨 `doc_role` 串扰控制在 0%，可继续作为客户江西/山西真实标书入库前的基线。

---

## Run 3 — 场景化测试集评测（2026-06-02）

> 摘要：`docs/rag/runs/run_20260602_scenario_summary.md`
> 测试集：`tests/rag/scenario_testset.jsonl`（12 条）
> 原始结果：`docs/rag/runs/run_20260602_scenario_filtered.json`、`docs/rag/runs/run_20260602_scenario_nofilter.json`

### 触发原因

为区分知识库问答和标书写作场景，新增场景化测试集，单独跟踪：

- `qa_recall`
- `writing_parent_coverage`
- `compliance_recall`
- `table_recall`

### A/B：metadata 过滤的价值

| 指标 | 过滤 ON | 过滤 OFF | 差值 |
| --- | ---: | ---: | ---: |
| Recall@5 | **100.0%** | 75.0% | +25.0pp |
| 来源类别准确率(top1) | **100.0%** | 83.3% | +16.7pp |
| 跨 doc_role 串扰均值 | **0.0%** | 41.7% | -41.7pp |
| 关键词命中率 | **100.0%** | 75.0% | +25.0pp |

分指标 Recall@5：

| metric | 过滤 ON | 过滤 OFF |
| --- | ---: | ---: |
| `qa_recall` | 100% | 67% |
| `writing_parent_coverage` | 100% | 67% |
| `compliance_recall` | 100% | 67% |
| `table_recall` | 100% | 100% |

### 结论

场景化测试集进一步证明 metadata 过滤是必要条件。关闭过滤后，问答、合规和写作父块覆盖均退化，且跨 `doc_role` 串扰升至 41.7%。当前写作父块回溯在样例集上可用，但仍需加入江西/山西真实标书和 `.xlsx` 表格样本后再判断生产可用性。

---

## Run 4 — 江西/山西客户资料 staging 入库与召回评测（2026-06-02）

> 摘要：`docs/rag/runs/run_20260602_customer_jx_sx_summary.md`
> 测试集：`tests/rag/customer_jx_sx_testset.jsonl`（17 条）
> 原始结果：`docs/rag/runs/run_20260602_customer_jx_sx_filtered.json`、`docs/rag/runs/run_20260602_customer_jx_sx_nofilter.json`

### 触发原因

客户江西/山西铁构件样本资料完成本地解析 QA 后，进行 staging 入库和客户真实场景召回评测，验证本地解析是否足以支撑 P1 样板库建设。

### 入库数据

| 项 | 数量 |
| --- | ---: |
| `knowledge_documents` | 23 |
| `document_chunks` | 4238 |
| parent chunk | 223 |
| child/table 检索块 | 4015 |
| embedding | 4015 |
| 结构化货物清单行 | 105 |
| 仅归档文件 | 21 |

### A/B：metadata 过滤的价值

| 指标 | 过滤 ON | 过滤 OFF | 差值 |
| --- | ---: | ---: | ---: |
| Recall@5 | **100.0%** | 70.6% | +29.4pp |
| 来源类别准确率(top1) | **100.0%** | 58.8% | +41.2pp |
| 关键词命中率 | **100.0%** | 88.2% | +11.8pp |
| 跨 doc_role 串扰均值 | **0.0%** | 50.9% | -50.9pp |
| 禁用关键词命中率 | **0.0%** | 0.0% | 0.0pp |

分场景 Recall@5：

| scenario | 过滤 ON | 过滤 OFF |
| --- | ---: | ---: |
| qa | 100% | 43% |
| compliance | 100% | 100% |
| writing | 100% | 67% |
| table | 100% | 100% |

### Base 回归

新增客户资料后，原 Base filtered 复跑结果仍为 Recall@5 86.7%、来源类别准确率 100%、跨 `doc_role` 串扰 0%，与 Run 1/2 基线一致，未发现退化。

### 结论

1. 本地解析链路在本批客户样本上通过 QA，暂不需要强制切到 MinerU。
2. 客户资料 staging 入库后，过滤 ON 的客户测试集 Recall@5 达到 100%。
3. 过滤 OFF 明显退化，说明 `province/package_code/doc_role/ingestion_batch_id` 过滤必须作为上线门禁。
4. 表格召回已可用，且本批已补 `power_grid_goods_list_rows` 结构化表/JSONB 精确查询层。

---

## Run 5 — PDF 标准源文件入库前审计与错源排除（2026-06-02）

> 审计脚本：`scripts/rag/audit_power_grid_pdf_standards.py`  
> 当前复审报告：`docs/rag/runs/run_20260602_pdf_standard_audit.md`  
> 当前复审原始结果：`docs/rag/runs/run_20260602_pdf_standard_audit.json`

### 触发原因

本地下一阶段任务将“PDF 国标/行标样板入库”列为最高优先级。入库前先对 `rag_seed/power_grid_resources/index.csv` 中 `03_standards_specs` 下已下载 PDF 做源文件一致性审计，避免把文件名正确但正文不匹配的 PDF 写入技术标知识库。

### 首次审计结果

| 状态 | 数量 |
| --- | ---: |
| `match` | 1 |
| `mismatch` | 6 |
| 合计 | 7 |

主要问题：

- `GB 50150-2016 电气装置安装工程电气设备交接试验标准` 实际抽取到 HJ/T 351-2007 环境标志产品技术要求。
- `GB 50168-2018 电气装置安装工程电缆线路施工及验收标准` 实际抽取到 HJ2057-2018 铅冶炼废水治理工程技术规范。
- `GB 50169-2016`、`GB 50171-2016`、`DL/T 5729-2016` 等也未在前 20 页抽取结果中稳定命中对应标准号和标题，不能直接进入 RAG。

### 处置后复审

根据客户后续安排，错误 PDF 暂不继续第三方下载，改由客户提供正确源文件。已将以下 6 条从 `downloaded` 改为 `needs_customer_source`，并清空 `file_path` / `sha256`，使 `scripts/rag/ingest_power_grid_v2.py` 在入库时跳过：

- GB/T 50430-2017 工程建设施工企业质量管理规范
- GB 50150-2016 电气装置安装工程电气设备交接试验标准
- GB 50168-2018 电气装置安装工程电缆线路施工及验收标准
- GB 50169-2016 电气装置安装工程接地装置施工及验收规范
- GB 50171-2016 电气装置安装工程盘、柜及二次回路接线施工及验收规范
- DL/T 5729-2016 配电网规划设计技术导则

复审结果：

| 状态 | 数量 |
| --- | ---: |
| `match` | 1 |
| 合计 | 1 |

### 结论

PDF 标准入库前必须增加源文件审计门禁。当前错源 GB/DL 标准 PDF 已从自动入库候选中排除；下一步等待客户提供正确源文件，重跑审计通过后再做 MinerU/OCR 解析、条文级分块和召回评测。

---

## Run 6 — 辽宁 / 泰昌 MVP 正式入库与专项回归（2026-06-06）

> Staging manifest：`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/staging_manifest.json`  
> 入库汇总：`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/formal_ingestion_summary.md`  
> Base filtered：`docs/rag/runs/run_20260606_taichang_mvp_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260606_taichang_mvp_customer_filtered.json`

### 正式入库结果

| 表 / 对象 | 数量 |
| --- | ---: |
| `knowledge_documents` | 124 |
| `document_chunks` | 29683 |
| `power_grid_goods_list_rows` | 87 |
| `knowledge_assets` | 242 |
| `knowledge_assets.embedding` | 242 |

资产目标库：

| target_library | 数量 |
| --- | ---: |
| `qualification_library` | 105 |
| `product_library` | 137 |

### 召回回归

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 86.7% | 93.3% | 86.7% | 0.0% | - |
| 辽宁/泰昌专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

专项分场景 Recall@5：

| scenario | cases | Recall@5 |
| --- | ---: | ---: |
| `asset_search` | 2 | 100% |
| `format_reference` | 2 | 100% |
| `negative` | 3 | 100% |
| `qa` | 5 | 100% |
| `table` | 2 | 100% |
| `writing` | 3 | 100% |

### 处置记录

- 为了让图片 metadata 在 `eval_recall.py` 的 `document_chunks` 评测链路中可测，新增 9 个泰昌图片资产目录文本块；正式图片仍写入 `knowledge_assets`。
- 资产目录正文去掉“河北豪乾”字样，仅在 metadata 保留 `do_not_mix_with`，避免泰昌事实召回命中禁用关键词。
- 补入 1 条 `self_phrase` Base 回归话术，使 T23 恢复命中；Base Recall@5 回到既有 86.7% 门槛。
- 修复 `backend/db/supabase_repo.py` 中 `upload_knowledge_asset_file()` 调用未定义 `_knowledge_asset_bucket()` 的问题，否则正式资产上传会全部失败。

### 剩余风险

- Base 未命中 T04/T17/T18/T20 仍为既有问题：T04 关键词标注偏严，T17/T18 源数据质量差，T20 标准仅有摘要/目录。
- 泰昌 CPVC/MPP 检验报告为“内径250”，与辽宁清单中的 φ50/100/150/175/200 覆盖关系仍需业务确认。

---

## Run 7 — 泰昌 MVP 图片智能问答与图文并茂选图 P0 回归（2026-06-06）

> Base filtered：`docs/rag/runs/run_20260606_taichang_mvp_asset_p0_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260606_taichang_mvp_asset_p0_customer_filtered.json`

### 范围边界

- 泰昌是 MVP 试点企业，`enterprise_fact/doc_owner=泰昌` 是企业事实主线。
- 辽宁资料仅作为电缆保护管招标场景样本，用于招标要求、技术规范、货物清单、合同条款召回。
- 河北豪乾资料仅作为格式/目录/写法参考，`reference_only=true`，不得作为泰昌企业事实或泰昌图片来源。

### 修复内容

- 智能问答图片资产检索支持 metadata 过滤；当查询或显式过滤指向泰昌时，仅召回泰昌企业事实资产，并排除参考稿。
- 图片资产检索文本补入 `metadata/specs` 标量和列表值，使 `evidence_type/target_library/enterprise/source_domain` 可参与关键词补召回。
- 标书导出“图文并茂”按章节语义推断 `evidence_type`，对生产制造、试验检测、绿色低碳、营业执照/证书、检验报告做强匹配，避免泛化的“设备/证书”关键词误选。

### 真实库验证

当前 `knowledge_assets` 候选池 242 个资产。真实库模拟结果：

| 查询/章节 | 期望 evidence_type | 结果 |
| --- | --- | --- |
| 泰昌企业资信与营业执照 | `business_license`、`certification` | 命中泰昌营业执照与认证证书 |
| 泰昌生产制造能力 | `production_capacity` | 命中泰昌生产线/生产制造资产 |
| 泰昌试验检测能力 | `testing_capacity` | 命中电子天平、万能试验机等试验检测资产 |
| 泰昌绿色低碳与绿色供应链能力 | `green_low_carbon` | 命中绿色低碳/绿色供应链资产 |

智能问答资产检索验证：

| 查询 | Top evidence_type |
| --- | --- |
| 泰昌营业执照图片 | `business_license` |
| 泰昌 MPP 生产线图片 | `production_capacity` |
| 泰昌电子天平和万能试验机图片 | `testing_capacity` |
| 泰昌绿色供应链证书图片 | `green_low_carbon` |

### 召回回归

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 86.7% | 93.3% | 86.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 单测

- `PYTHONPATH=. .venv/bin/pytest tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q`
- 结果：16 passed，1 个 PyPDF2 deprecation warning。

---

## Run 8 — 泰昌正式图片资产整页化重建与中文命名（2026-06-07）

> 重建报告：`parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/rebuild_formal_image_assets_report.md`  
> Base filtered：`docs/rag/runs/run_20260607_taichang_formal_assets_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_taichang_formal_assets_customer_filtered.json`

### 背景

- 资信库、产品库中原有 242 个图片资产来自 MinerU `extract/images` 局部切图，包含二维码、页脚、签名/印章附近局部、文字块和表格局部。
- 页面展示直接使用资产 `title/category/tags`，因此出现 `taichang_*`、`production_capacity`、`green_low_carbon` 等内部英文/拼音值。
- 客户已提供营业执照、开户许可证、审计报告、管理体系证书、CPVC/MPP 检验报告、生产线/厂房/设备/人员/社保/绿色低碳等 PDF/JPG，可按正式投标文件规则处理为整页/原图资产。

### 处理内容

- 新增 `scripts/rag/rebuild_taichang_formal_image_assets.py`。
- 删除旧批次 `knowledge_assets` 中 242 个 MinerU 局部图资产。
- 使用客户已提供 42 个 PDF 和 1 个 JPG，按 PDF 文件顺序逐页渲染整页图片，导入 300 个正式图片资产。
- 用户可见字段全部改为中文：标题、分类、标签、说明均不再出现拼音或英文枚举。
- 技术枚举仅保留在 metadata/specs 内，用于过滤和召回，例如 `evidence_type`、`target_library`、`asset_visual_type`。
- 更新 `AGENTS.md`，固化国内中文命名规则和正式图片资产门禁规则。
- 更新产品库、资信库页面旧文案，把“公开素材/公开来源素材/脱敏合成规格图”改为“泰昌资料/客户提供资料/客户自有资料”口径。

### 数据库验证

| 指标 | 结果 |
| --- | ---: |
| 删除旧局部图片资产 | 242 |
| 导入正式整页/原图资产 | 300 |
| `product_image` | 203 |
| `qualification_image` | 97 |
| 标题英文/拼音残留 | 0 |
| 标签英文枚举残留 | 0 |

正式资产分类：

| 分类 | 数量 |
| --- | ---: |
| 绿色低碳资料 | 111 |
| 财务资料 | 67 |
| 试验检测设备 | 46 |
| 生产制造能力 | 24 |
| 人员证书 | 18 |
| 厂房仓储资料 | 14 |
| 检验报告 | 10 |
| 资质证书 | 8 |
| 基础证照 | 2 |

### 回归验证

- Base filtered Recall@5：86.7%，top1 来源准确率：93.3%，关键词命中率：86.7%，跨 doc_role 串扰均值：0.0%。
- 泰昌专项 filtered Recall@5：100.0%，top1 来源准确率：100.0%，关键词命中率：100.0%，禁用关键词命中率：0.0%。
- `PYTHONPATH=. .venv/bin/pytest tests/test_rag_asset_scoring.py tests/test_rag_retrieval.py -q`
- 结果：16 passed，1 个 PyPDF2 deprecation warning。
- `cd frontend && npm run build`
- 结果：构建通过；Vite 仅提示既有大 chunk 和动态/静态 import 混用警告。

### 剩余风险

- CPVC/MPP 现有检验报告为“内径250”，是否覆盖辽宁清单中的其他口径仍需客户业务确认。
- 产品实物高清照片、生产线/检测设备原始照片、同类业绩合同/中标通知书/验收证明、项目级盖章扫描件和官方 Logo 仍需客户补充。

---

## Run 9 — 泰昌企业知识库问答入口与参考来源收紧（2026-06-07）

### 背景

- MVP 版本已确定以河北泰昌电力器材科技有限公司为试点企业。
- 企业知识库助手原先仍向用户暴露“自动判断资料范围”和“问答/写作/合规/货物清单”等场景选择，容易让业务用户误以为可以跨省份、跨包号或跨主体选择资料。
- 回答下方“参考资料来源”直接展示 `province/package_code/material_category/doc_role` 等 metadata，导致江西、山西、辽宁等招标资料在企业事实问答中被明示展示，不符合泰昌企业事实边界。

### 处理内容

- 前端 `KnowledgeSearchDrawer` 移除资料范围和问答类型下拉控件，默认入口文案改为泰昌企业资信、产品资料和标书材料问答。
- 后端 `/api/knowledge/search` 与 `/api/knowledge/search/stream` 默认使用泰昌企业事实过滤：
  - `enterprise=泰昌`
  - `source_domain=enterprise_fact`
  - `fact_source_allowed_for_enterprise=true`
  - `reference_only=false`
- 文本参考来源返回前执行企业事实门禁、同源去重、按 `similarity` 降序排序，最多返回 5 条。
- 前端来源卡片不再展示省份、包号、物料类别等招标资料标签，仅展示企业事实标题、中文化说明、内容预览和相关度。

### 回归验证

- 本次未新增客户资料，未执行重新入库。
- `./.venv/bin/python -m pytest tests/test_rag_retrieval.py -q`
- 结果：8 passed，1 个 PyPDF2 deprecation warning。
- `cd frontend && npm run build`
- 结果：构建通过；Vite 仅提示既有大 chunk 和动态/静态 import 混用警告。
- `curl -I http://127.0.0.1:5173/`
- 结果：本地前端服务返回 HTTP 200。

### 剩余风险

- 本次锁定的是企业知识库助手的泰昌试点口径；如后续恢复多企业租户模式，需要把试点企业常量改为租户上下文，而不是重新暴露省份/包号型筛选。
- Playwright 未安装，未做自动截图；已通过 TypeScript 构建、静态文本检查和本地服务可访问性检查。

---

## Run 10 — P2 版本去重与引用边界门禁（2026-06-07）

> Run summary：`docs/rag/runs/run_20260607_p2_version_citation_summary.md`  
> Base filtered：`docs/rag/runs/run_20260607_p2_version_citation_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_p2_version_citation_customer_filtered.json`

### 背景

- P2-4 要求同一模板新旧版本不能同时污染召回。
- P2-5 要求区分企业事实、招标要求、参考模板、法规/标准等引用边界，避免把参考稿当事实、把招标要求写成企业能力。

### 处理内容

- 新增 `scripts/rag/customer_metadata_policy.py`：
  - `enterprise_fact` -> `citation_policy=enterprise_fact_citable`
  - `tender_requirement` -> `citation_policy=tender_requirement_citable`
  - `reference_template` -> `citation_policy=reference_style_only`
  - `policy_regulation` -> `citation_policy=law_or_standard_citable`
  - `base_seed` -> `citation_policy=summary_only`
- `scripts/rag/ingest_customer_corpus.py` 在 dry-run 和正式入库前执行 metadata 门禁。
- 入库 metadata 统一补齐或校验 `source_sha256`、`doc_identity_key`、`doc_version`、`superseded_by`。
- 正式入库时，同一 `doc_identity_key`、不同 `source_sha256` 且新版本不低于旧版本的旧文档会被置为 `superseded`。
- 强校验泰昌企业事实、辽宁/江西/山西招标要求、河北豪乾参考稿三类边界。

### dry-run

| manifest | documents | skipped | blocked_metadata | parent | child/table 检索块 | embedding |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 泰昌/辽宁 P0 staging | 124 | 0 | 0 | 2023 | 27660 | 27660 |
| 江西/山西 P1 manifest | 44 | 21 | 0 | 223 | 4015 | 4015 |

### 回归验证

- `./.venv/bin/python -m pytest tests/test_customer_metadata_policy.py tests/test_rag_retrieval.py -q`
- 结果：14 passed，1 个 PyPDF2 deprecation warning。
- Base filtered Recall@5：86.7%，top1 来源准确率：93.3%，关键词命中率：86.7%，跨 doc_role 串扰均值：0.0%。
- 泰昌专项 filtered Recall@5：100.0%，top1 来源准确率：100.0%，关键词命中率：100.0%，禁用关键词命中率：0.0%。

### 剩余风险

- 历史已入库文档如果没有 `doc_identity_key`，无法自动反向判定新旧版本关系；后续新批次按新门禁入库后会稳定生效。
- 如果客户后续提供同一资料但文件名变化的新版本，manifest 应显式填写稳定 `doc_key` 或 `document_key`。

---

## Run 11 — P3 Query Rewrite / 关键词补召回 / Authority 排序（2026-06-07）

> Run summary：`docs/rag/runs/run_20260607_p3_query_keyword_summary.md`  
> Base filtered：`docs/rag/runs/run_20260607_p3_query_keyword_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_p3_query_keyword_customer_filtered.json`

### 背景

- P2 后 Base Recall@5 为 86.7%，未命中集中在标准规范、国网规则和合规类问题。
- 原评测脚本直接调用 RPC，未覆盖生产检索链路中的 rerank、后处理和后续增强逻辑。

### 处理内容

- `search_knowledge_base()` 增加轻量 Query Rewrite，提取标准号、包号、技术规范编码、物料编码、供应商管理、不良行为、施工工艺等关键词。
- 增加 document chunk 关键词补召回：向量召回不足或高精度关键词未命中时触发，并继续执行 metadata 边界过滤。
- 对关键词命中的网页型国网规则分片补充来源文件名、标签、类型、来源单位作为上下文前缀，缓解网页导航噪声。
- 增加 authority/citation 排序：正式法规/标准、招标要求、企业事实加权；`reference_style_only` 降权。
- `scripts/rag/eval_recall.py` 改为调用生产检索函数，确保回归覆盖 Query Rewrite、关键词补召回和 authority 排序。

### 回归验证

- `./.venv/bin/python -m pytest tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
- 结果：25 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile backend/rag/retrieval.py scripts/rag/eval_recall.py`
- 结果：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- Base 仅剩 T04 合规用例未命中关键词；top1 doc_role 已正确为 `policy_regulation`。
- 国网规则网页存在明显导航噪声，应在后续重洗并重新入库。
- 关键词补召回暂在应用层过滤；后续可补数据库侧关键词索引或专用 RPC。

---

## Run 12 — 国网规则网页噪声重洗与回归（2026-06-07）

> Run summary：`docs/rag/runs/run_20260607_sgcc_rule_clean_summary.md`  
> Base filtered：`docs/rag/runs/run_20260607_sgcc_rule_clean_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_sgcc_rule_clean_customer_filtered.json`

### 背景

- `国家电网有限公司招标活动管理办法`、`国家电网有限公司供应商管理办法`、`国家电网有限公司物资采购标准` 三份 seed 文档的原正文为门户首页导航/新闻内容，不是制度原文。
- 该问题会污染国网规则问答和合规召回，且影响后续 P4 技术参数表抽取前的整体回归稳定性。

### 处理内容

- 新增 `scripts/rag/repair_sgcc_rule_seed_docs.py`，重洗三份异常 markdown，并同步 `index.csv`、`index.jsonl` 的 `sha256` 与错误说明。
- 三份异常资料改为明确标注的“检索种子摘要”，均标明原始采集链接失效、待官方原文复核、`citation_policy=summary_only`。
- 重新入库 `02_policy_regulations`：11 文档、266 parent、2180 child。
- 重新入库 `04_standard_phrases`：6 文档、16 parent、22 child，用于恢复本次回归暴露的标准话术库不完整问题。
- `search_knowledge_base()` 补充 `质量安全环保/质量目标/安全目标` 领域关键词，并将关键词补召回改为分页扫描，避免固定窗口漏扫小类资料。

### 回归验证

- `./.venv/bin/python -m pytest tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
- 结果：26 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile backend/rag/retrieval.py scripts/rag/eval_recall.py scripts/rag/repair_sgcc_rule_seed_docs.py`
- 结果：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- Base 仅剩 T04：top1 `policy_regulation` 正确，但关键词口径仍是“无效”与“否决所有投标”的表达差异。
- 三份国网规则当前仍是检索种子摘要，不是官方制度全文；后续拿到官方原文后仍需替换 seed、重入库并复跑评测。

---

## Run 13 — P4-2 技术参数表抽取（2026-06-07）

> Run summary：`docs/rag/runs/run_20260607_p4_technical_parameters_summary.md`  
> Base filtered：`docs/rag/runs/run_20260607_p4_technical_parameters_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_p4_technical_parameters_customer_filtered.json`

### 背景

- P4-2 要求技术参数表不能只做普通文本向量，必须保留原始结构、检索摘要和行级记录。
- 后续客户继续提供技术规范书、技术补充文件、技术响应参考稿、检验报告参数页或偏差表时，也需要按同一方式结构化。

### 处理内容

- 更新 `AGENTS.md`，固化后续客户技术资料的技术参数表抽取规则。
- 新增 `scripts/rag/extract_customer_technical_parameters.py`。
- 对辽宁/泰昌 MVP staging manifest 中 39 份 `technical_spec` 文档进行抽取。
- 输出：
  - `technical_parameter_rows.json`
  - `technical_parameter_rows.csv`
  - `technical_parameter_summary.md`
  - `extract_technical_parameters_report.json`

### 抽取结果

| 指标 | 数量 |
| --- | ---: |
| 技术规范文档 | 39 |
| 成功抽取文档 | 39 |
| 技术参数行 | 928 |
| CPVC 参数行 | 285 |
| MPP 参数行 | 643 |
| 尺寸参数行 | 349 |
| 性能参数行 | 369 |
| 投标响应参数行 | 210 |

### 回归验证

- `./.venv/bin/python -m pytest tests/test_technical_parameter_extraction.py tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
- 结果：27 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile scripts/rag/extract_customer_technical_parameters.py backend/rag/retrieval.py`
- 结果：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- 本轮只生成 JSON/CSV/summary chunk，尚未新增 `power_grid_technical_parameter_rows` 数据库表。
- 本批招标技术规范中的 `投标人响应值`、`投标人保证值` 多为空白，字段已保留；后续可由泰昌产品资料、检验报告或人工确认值补齐。

---

## Run 14 — P4-4 技术偏差辅助判断（2026-06-07）

> Run summary：`docs/rag/runs/run_20260607_p4_deviation_summary.md`  
> Base filtered：`docs/rag/runs/run_20260607_p4_deviation_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260607_p4_deviation_customer_filtered.json`

### 背景

- P4-2 已产出 `technical_parameter_rows.json`。
- P4-4 初版要求先支持“项目需求值/标准值 vs 投标响应/保证值”的差异判断，用于技术偏差表、漏项检查和检验报告覆盖性判断。

### 处理内容

- 新增 `scripts/rag/generate_technical_deviation_report.py`。
- 对 928 行技术参数生成偏差辅助判断：
  - `pending_response`
  - `no_deviation`
  - `positive_deviation`
  - `negative_deviation`
  - `manual_review`
  - `informational`
- 输出：
  - `technical_deviation_rows.json`
  - `technical_deviation_rows.csv`
  - `technical_deviation_summary.md`
  - `technical_deviation_report.json`

### 产物结果

| 指标 | 数量 |
| --- | ---: |
| 参数行 | 928 |
| 需处理行 | 900 |
| `pending_response` | 900 |
| `informational` | 28 |
| `medium` 风险 | 900 |
| `low` 风险 | 28 |

本批大量参数被标为 `pending_response`，原因是招标技术规范里有明确项目需求值或标准值，但 `投标人响应值`、`投标人保证值` 多为空白。该结果符合预期，不能直接写成无偏差。

### 回归验证

- `./.venv/bin/python -m pytest tests/test_technical_deviation_report.py tests/test_technical_parameter_extraction.py tests/test_rag_retrieval.py tests/test_rag_asset_scoring.py tests/test_customer_metadata_policy.py -q`
- 结果：33 passed，1 个 PyPDF2 deprecation warning。
- `./.venv/bin/python -m py_compile scripts/rag/generate_technical_deviation_report.py scripts/rag/extract_customer_technical_parameters.py backend/rag/retrieval.py`
- 结果：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- 初版偏差判断尚未接入泰昌检验报告或产品规格作为保证值来源。
- 本轮未新增结构化数据库表，产物仍以 JSON/CSV/Markdown 为主。

---

## Run 15 — 泰昌产品/检验报告参数抽取（2026-06-08）

> Run summary：`docs/rag/runs/run_20260608_taichang_product_params_summary.md`  
> Base filtered：`docs/rag/runs/run_20260608_taichang_product_params_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260608_taichang_product_params_customer_filtered.json`

### 背景

用户明确业务边界：辽宁需求只代表辽宁省公司本批招标要求，不代表全国电网或其他省公司要求。本轮不把泰昌检验报告自动映射为“覆盖辽宁全部规格”，只抽取泰昌原始产品/检验报告参数；辽宁参数最多作为抽取 QA/异常校验参照。

### 处理内容

- 更新 `AGENTS.md`，固化辽宁资料仅作样本/QA 参照、不作泰昌覆盖义务的规则。
- 新增 `scripts/rag/extract_taichang_product_parameters.py`。
- 从泰昌 CPVC/MPP 内径 250 检验报告 MinerU `full.md` 中抽取企业事实参数。
- 输出：
  - `taichang_product_parameter_rows.json`
  - `taichang_product_parameter_rows.csv`
  - `taichang_product_parameter_summary.md`
  - `extract_taichang_product_parameters_report.json`

### 抽取结果

| 指标 | 数量 |
| --- | ---: |
| 泰昌检验报告 | 2 |
| 成功抽取文档 | 2 |
| 企业事实参数行 | 36 |
| CPVC 电缆保护管参数行 | 19 |
| MPP 电缆保护管参数行 | 17 |

| 产品 | 报告编号 | 规格型号 | 参数行 |
| --- | --- | --- | ---: |
| CPVC电缆保护管 | `2024100312005501713` | `DS 250×15×6000 SN16 PVC-C` | 19 |
| MPP电缆保护管 | `2024100312005501712` | `DF 250×22×9000 SN40 MPP` | 17 |

### 回归验证

- `.venv/bin/python -m pytest tests/test_taichang_product_parameter_extraction.py tests/test_technical_parameter_extraction.py tests/test_technical_deviation_report.py -q`
- 结果：9 passed。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- 本轮不自动将泰昌报告参数写入辽宁 `technical_deviation_rows.json` 作为响应/保证值，避免形成错误覆盖结论。
- 后续若具体省公司投标需要做偏差判断，应在明确目标省公司、规格、报告适用范围和客户业务确认后再生成正式偏差结论。

---

## Run 16 — 泰昌产品参数真实 API / 页面同源链路专项测试（2026-06-08）

> Run summary：`docs/rag/runs/run_20260608_taichang_product_params_real_chain_summary.md`  
> API 结果：`docs/rag/runs/run_20260608_taichang_product_params_real_api.json`  
> Stream 结果：`docs/rag/runs/run_20260608_taichang_product_params_real_stream.json`

### 背景

用户已启动后端和前端服务，要求不使用 mock，直接进行真实 API / 页面问答链路专项测试。

### 测试内容

- `GET /api/health`：通过。
- `GET http://127.0.0.1:5173/api/health`：通过，确认前端 Vite 代理可达后端。
- `POST /api/users/register`：通过，获取真实 session token。
- `POST /api/knowledge/search`：完成真实非流式问答。
- `POST http://127.0.0.1:5173/api/knowledge/search/stream`：完成页面同源流式问答。

### 测试结论

| 测试问题 | 结果 |
| --- | --- |
| 泰昌 MPP 内径250 环刚度 | 未达标。真实链路未返回 `66.40`，而是提示文本未提取出具体数值 |
| 泰昌 CPVC 内径250 平均内径/壁厚 | 未达标。真实链路未返回 `250.2~250.4` / `15.2~15.3` |
| 两份内径250报告是否覆盖辽宁全部规格 | 通过。回答明确不能直接说明覆盖辽宁所有规格 |

### 根因判断

真实问答链路当前没有接入 P4-5 产出的 `taichang_product_parameter_rows.json`。接口主要召回报告基础信息和图片资产，`sources=0`，因此无法稳定回答结构化参数值。

### 后续处理

P4-6 下一步应先接入 staging JSON 查询层，而不是立即新增数据库表：

- 命中泰昌 + CPVC/MPP + 规格/参数名的问题时，优先查结构化参数行；
- 将报告编号、规格型号、参数名、标准要求、检验结果作为高优先级 context；
- 继续保持辽宁仅作 QA/异常校验参照，不输出覆盖义务。

---

## Run 17 — 泰昌产品参数 JSON 查询接入真实问答链路（2026-06-08）

> Run summary：`docs/rag/runs/run_20260608_taichang_product_params_json_query_summary.md`  
> Base filtered：`docs/rag/runs/run_20260608_taichang_product_params_json_query_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260608_taichang_product_params_json_query_customer_filtered.json`  
> 非流式 API 结果：`docs/rag/runs/run_20260608_taichang_product_params_real_api_after_json.json`  
> 页面同源 Stream 结果：`docs/rag/runs/run_20260608_taichang_product_params_real_stream_after_json.json`

### 背景

Run 16 已证明真实链路缺少结构化参数查询。本轮不新增数据库表，先把 P4-5 产出的 `taichang_product_parameter_rows.json` 接入知识库问答链路。

### 处理内容

- 新增 `backend/rag/product_parameters.py`，基于真实 JSON 查询泰昌产品参数。
- 更新 `backend/api/knowledge.py`，在 `/api/knowledge/search` 和 `/api/knowledge/search/stream` 中把结构化参数作为高优先级 context 注入。
- 新增 `tests/test_taichang_product_parameter_query.py`，覆盖 MPP 环刚度、CPVC 平均内径/壁厚和辽宁边界。

### 真实链路验证

| 问题 | 结果 |
| --- | --- |
| 泰昌 MPP 内径250 环刚度 | 已返回 `66.40 kN/m2`，报告编号 `2024100312005501712` |
| 泰昌 CPVC 内径250 平均内径/壁厚 | 已返回 `250.2~250.4` / `15.2~15.3`，报告编号 `2024100312005501713` |
| 两份内径250报告是否覆盖辽宁全部规格 | 已明确回答不能覆盖辽宁全部规格 |

### 回归验证

- 相关单测：22 passed，1 个 PyPDF2 deprecation warning。
- 二次复验：14 passed，1 个 PyPDF2 deprecation warning。
- `py_compile`：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- 当前仍是 staging JSON 查询层，不是数据库表；多批次、多版本、多规格持续增长后，需要评估结构化表。
- 当前仅接入泰昌产品检验报告参数，不自动把这些值用于具体省公司偏差判断；偏差判断仍需目标省公司/批次/规格和客户确认口径。

---

## Run 18 — 企业知识库参考来源中文化与确定性来源去重（2026-06-08）

> Run summary：`docs/rag/runs/run_20260608_chinese_display_names_summary.md`  
> DB 修复 dry-run：`docs/rag/runs/run_20260608_chinese_display_names_dry_run.json`  
> DB 修复 execute：`docs/rag/runs/run_20260608_chinese_display_names_execute.json`、`docs/rag/runs/run_20260608_chinese_display_names_execute_after_enterprise_category.json`、`docs/rag/runs/run_20260608_chinese_display_names_execute_after_file_rename.json`  
> 页面同源 Stream 结果：`docs/rag/runs/run_20260608_chinese_display_names_real_stream_after_file_rename.json`  
> Base filtered：`docs/rag/runs/run_20260608_chinese_display_names_base_filtered_after_file_rename.json`  
> Customer filtered：`docs/rag/runs/run_20260608_chinese_display_names_customer_filtered_after_file_rename.json`

### 背景

用户指出企业知识库问答参考来源中仍出现 `taichang_production_capacity_private.md`、`power_grid_tender_documents` 等拼音/英文内部命名，并且 MPP 检验报告结构化参数命中 5 行时页面重复展示同一份报告 5 次。

### 处理内容

- 新增 `backend/rag/display_names.py`，统一把内部 source/category/evidence/target library 转为中文展示名。
- 更新知识库检索与提示词构建，返回来源前补充中文 `source_display_name`、`category_label`、`evidence_type_label`、`target_library_label`。
- 新增 `scripts/rag/repair_chinese_display_names.py`，在不修改原始文件内容和追溯路径的前提下，修复现有 `knowledge_documents`、`document_chunks`、`knowledge_assets` 的用户可见 metadata。
- 更新前端参考来源展示逻辑：同一确定性文件、同一检验报告或同一结构化参数来源命中多行时合并展示，不再为了凑满 5 条重复显示。
- 将 9 个遗留资产目录 staging Markdown 从 `taichang_*_private.md` 重命名为中文专业文件名，并同步更新 staging manifest/report 引用；生成脚本后续也输出中文文件名。
- 更新 `AGENTS.md`，把后续新增资料必须中文命名、内部枚举不得直接展示、确定性来源必须去重固化为 SOP。

### 修复结果

- 首次执行修复：174 个文档、36555 个 chunk、300 个图片资产写入中文展示 metadata。
- 企业资料分类二次修复：4377 个 chunk、300 个图片资产的分类展示从内部/泛化库名修正为“泰昌企业资料”。
- 文件级重命名后二次修复：9 个文档、763 个 chunk 的 `source_file` metadata 从旧英文/拼音 md 路径改为中文文件名路径。
- MPP 环刚度真实页面同源 stream：raw context 5 条结构化参数，前端去重后展示 1 条确定性来源；回答仍返回 `66.40 kN/m²`。
- 泰昌产品/生产/检测能力真实页面同源 stream：参考来源无内部英文/拼音展示，分类为“泰昌企业资料”。

### 回归验证

- `.venv/bin/python -m pytest tests/test_rag_display_names.py tests/test_taichang_product_parameter_query.py tests/test_rag_retrieval.py -q`
- 结果：17 passed，1 个 PyPDF2 deprecation warning。
- `py_compile`：通过。
- `frontend/npm run build`：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

### 剩余风险

- 本轮已重命名用户可见的资产目录 staging Markdown；MinerU 中间目录、UUID 解析文件和原始资料路径仍保留不动，避免破坏资产/原文定位。
- 后续如果新增解析脚本直接生成英文 staging Markdown，必须在入库前改为中文文件名或补中文 `source_display_name`，否则不得进入正式展示链路。

---

## Run 19 — P3-4 在线 Rerank 对比实验（2026-06-08）

> Run summary：`docs/rag/runs/run_20260608_p3_rerank_summary.md`  
> Base off：`docs/rag/runs/run_20260608_p3_rerank_base_off.json`  
> Base qwen3：`docs/rag/runs/run_20260608_p3_rerank_base_qwen3.json`  
> Customer off：`docs/rag/runs/run_20260608_p3_rerank_customer_off.json`  
> Customer qwen3：`docs/rag/runs/run_20260608_p3_rerank_customer_qwen3.json`

### 背景

用户确认在线 rerank 可使用，要求启动 P3-4，并做好测试回归和任务状态同步。本轮对比关闭 rerank 与在线 `qwen3-rerank` 的召回排序效果。

### 处理内容

- `rerank_documents` 支持显式 `enabled/model` 覆盖，实验不受运行时配置文件干扰。
- `search_knowledge_base` 支持 `rerank_enabled/rerank_model` 参数。
- `eval_recall.py` 新增 `--rerank default|off|on`、`--rerank-model`、MRR、平均耗时、`rerank_scored_cases`。
- 补充 rerank 单测，覆盖强制关闭和显式模型覆盖。

### 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 396 ms | 0/30 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 781 ms | 28/30 |
| 泰昌 MVP 专项 | off | 100.0% | 100.0% | 0.971 | 689 ms | 0/17 |
| 泰昌 MVP 专项 | qwen3-rerank | 100.0% | 100.0% | 0.971 | 1000 ms | 17/17 |

### 结论

- 在线 `qwen3-rerank` 已验证可用，无召回、排序和跨域隔离退化。
- 当前测试集上未观察到指标提升，主要增加了 300-400 ms 级平均耗时。
- 暂保持可控开关，不扩大默认候选池；下一步 P3-5 应补充更难的相似资料/错误引用负样本，再判断是否默认开启更强 rerank 策略。

### 回归验证

- `.venv/bin/python -m pytest tests/test_rerank_client.py tests/test_rag_retrieval.py tests/test_rag_display_names.py tests/test_taichang_product_parameter_query.py -q`
- 结果：21 passed，1 个 PyPDF2 deprecation warning。
- `py_compile`：通过。

---

## Run 20 — P3-5 困难样本评测集扩展与真实链路回归（2026-06-08）

> Run summary：`docs/rag/runs/run_20260608_p3_hard_eval_summary.md`  
> Base off：`docs/rag/runs/run_20260608_p3_hard_base_off.json`  
> Base qwen3：`docs/rag/runs/run_20260608_p3_hard_base_qwen3.json`  
> Customer off：`docs/rag/runs/run_20260608_p3_hard_customer_off.json`  
> Customer qwen3：`docs/rag/runs/run_20260608_p3_hard_customer_qwen3.json`  
> 页面同源 Stream 抽样：`docs/rag/runs/run_20260608_p3_hard_real_stream.json`

### 背景

用户强调 P3-5 必须完全按真实链路进行评估和测试。本轮扩展泰昌专项评测集，从常规样本升级为包含相似资料、误引用负样本和 rerank 排序困难样本的 30 条专项集。

### 处理内容

- `tests/rag/customer_liaoning_taichang_testset.jsonl` 从 17 条扩展到 30 条。
- 新增 13 条困难样本，覆盖泰昌/辽宁/河北豪乾资料域边界、CPVC/MPP 相似检验报告、生产/检测/绿色低碳相似资产、合同/货物清单混淆和内部资料访问边界。
- 复跑 Base 30 + 泰昌专项 30，合计 60 条真实召回评测。
- 使用页面同源 `/api/knowledge/search/stream` 抽样验证困难 query 的真实问答链路。

### 结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base 30 | off | 96.7% | 100.0% | 0.944 | 0.0% | 375 ms | 0/30 |
| Base 30 | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 741 ms | 28/30 |
| 泰昌专项 30 | off | 96.7% | 100.0% | 0.950 | 3.3% | 451 ms | 0/30 |
| 泰昌专项 30 | qwen3-rerank | 100.0% | 100.0% | 0.983 | 0.0% | 756 ms | 30/30 |

### 真实页面链路

- CPVC 检验报告与 MPP 参数混淆问题：stream 完成，5 条上下文，无错误可见来源。
- 泰昌生产制造能力与河北豪乾/辽宁招标混淆问题：stream 完成，5 条上下文，无错误可见来源。

### 结论

- 困难样本扩展后，在线 `qwen3-rerank` 对泰昌专项有明确收益：Recall@5、MRR 和禁用关键词命中率均改善。
- Base 无退化，跨 doc_role 串扰仍为 0。
- 下一步 P3-6 应把 Base + 泰昌专项 + 困难样本评测固化为增量回归门禁，并记录每次新增客户资料后的退化原因。

### 回归验证

- `.venv/bin/python -m pytest tests/test_rerank_client.py tests/test_rag_retrieval.py tests/test_rag_display_names.py tests/test_taichang_product_parameter_query.py -q`
- 结果：21 passed，1 个 PyPDF2 deprecation warning。
- `py_compile`：通过。

---

## Run 21 — P3-6 增量回归门禁固化（2026-06-08）

> Gate summary：`docs/rag/runs/run_20260608_p3_incremental_gate_summary.md`  
> Base off：`docs/rag/runs/run_20260608_p3_incremental_gate_base_off.json`  
> Base qwen3：`docs/rag/runs/run_20260608_p3_incremental_gate_base_qwen3.json`  
> Customer off：`docs/rag/runs/run_20260608_p3_incremental_gate_customer_off.json`  
> Customer qwen3：`docs/rag/runs/run_20260608_p3_incremental_gate_customer_qwen3.json`

### 背景

用户要求把 P3-5 形成的 Base + 泰昌专项 + 困难样本真实链路评测固化为后续新增资料后的必跑门禁。本轮新增一键脚本，避免后续手工漏跑或漏记指标。

### 处理内容

- 新增 `scripts/rag/run_incremental_regression_gate.py`，自动执行四组真实召回评测：
  - Base / rerank off；
  - Base / `qwen3-rerank`；
  - 泰昌专项 / rerank off；
  - 泰昌专项 / `qwen3-rerank`。
- 脚本自动生成四个 JSON 结果和一份 gate summary。
- 脚本内置门禁阈值：Base qwen3 Recall@5 不低于 96.67%、Top1 100%、跨 doc_role 串扰 0；泰昌专项 qwen3 Recall@5 100%、Top1 100%、禁用关键词命中 0、跨 doc_role 串扰 0，并要求记录 rerank_score。
- 新增 `tests/test_incremental_regression_gate.py`，覆盖门禁通过和 rerank 未实际运行时失败的判断。
- 更新 `AGENTS.md`，把标准命令收敛为 `run_incremental_regression_gate.py --run-id <run>`。

### 真实门禁结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 254 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 619 ms | 28 |
| 泰昌专项 | off | 96.7% | 100.0% | 0.950 | 3.3% | 0.0% | 333 ms | 0 |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.983 | 0.0% | 0.0% | 689 ms | 30 |

### 结论

- Gate PASS。
- 后续新增客户资料、调整 metadata、召回、rerank 或参考来源展示时，优先运行：

```bash
set -a; source .env; set +a; .venv/bin/python scripts/rag/run_incremental_regression_gate.py --run-id <run>
```

- 若门禁失败，必须保留失败 JSON 和 summary，并在 evaluation records 中说明退化原因和修复策略。

### 回归验证

- `.venv/bin/python -m pytest tests/test_incremental_regression_gate.py tests/test_rerank_client.py tests/test_rag_retrieval.py -q`
- 结果：17 passed，1 个 PyPDF2 deprecation warning。
- `py_compile`：通过。

---

## Run 22 — 泰昌产品参数自动重抽取与真实链路回归（2026-06-08）

> Run summary：`docs/rag/runs/run_20260608_taichang_product_parameter_refresh_summary.md`  
> 页面同源 Stream 抽样：`docs/rag/runs/run_20260608_taichang_product_parameter_refresh_real_stream.json`  
> Gate summary：`docs/rag/runs/run_20260608_taichang_product_parameter_refresh_gate_summary.md`

### 背景

用户确认客户后续还会持续补充泰昌产品参数、检验报告和技术资料，要求把“新增资料后自动重抽取、真实问答验证、回归记录同步”固化为标准流程，并开始执行本轮验证。

### 处理内容

- 新增 `scripts/rag/run_taichang_product_parameter_refresh.py`，一键执行泰昌产品参数重抽取、抽取报告校验、参数查询测试、增量回归门禁和真实页面同源 stream 抽样。
- 新增 `tests/test_taichang_product_parameter_refresh.py`，覆盖抽取报告门禁与真实 stream 结果校验逻辑。
- 更新 `AGENTS.md`，新增“泰昌产品参数与检验报告重抽取 SOP”，要求客户新增同类资料后必须运行该流程，并同步 `docs/rag/runs/`、`evaluation-records.md` 和 `todo.md`。
- 保持辽宁技术参数只作 QA/异常校验参照，不自动推出泰昌覆盖辽宁全部规格或全部需求。

### 抽取与真实链路结果

| 项目 | 结果 |
| --- | --- |
| 检验报告文档 | 2 |
| 成功抽取文档 | 2 |
| 产品参数行 | 36 |
| QA 参照边界 | `qa_only_not_coverage_judgement` |
| MPP 真实问答校验 | 返回环刚度 `66.40 kN/m²` |
| CPVC 真实问答校验 | 返回平均内径 `250.2/250.4 mm`、壁厚 `15.2/15.3 mm` |

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 | Rerank 打分用例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 259 ms | 0 |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 622 ms | 28 |
| 泰昌专项 | off | 96.7% | 100.0% | 0.950 | 3.3% | 0.0% | 317 ms | 0 |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.983 | 0.0% | 0.0% | 678 ms | 30 |

### 结论

- Run PASS。
- 后续客户新增泰昌产品参数、检验报告或等价技术资料后，优先运行：

```bash
set -a; source .env; set +a; .venv/bin/python scripts/rag/run_taichang_product_parameter_refresh.py --run-id <run>
```

- 该流程失败时不得只记录接口可返回，必须保留失败 summary/JSON 并在本文件说明未达标项。

### 回归验证

- `.venv/bin/python -m pytest tests/test_taichang_product_parameter_refresh.py tests/test_taichang_product_parameter_extraction.py tests/test_taichang_product_parameter_query.py -q`
- 结果：9 passed。
- `.venv/bin/python -m py_compile scripts/rag/run_taichang_product_parameter_refresh.py scripts/rag/extract_taichang_product_parameters.py backend/rag/product_parameters.py`
- 结果：通过。

---

## Run 23 — P1B-5 泰昌项目业绩结构化抽取（2026-06-12）

> 抽取报告：`parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/extract_taichang_project_performance_report.md`
> 真实 Stream：`docs/rag/runs/run_20260612_taichang_project_performance_real_stream.json`
> Gate summary：`docs/rag/runs/run_20260612_taichang_project_performance_p1b5_summary.md`

### 处理内容

- 从泰昌合同协议书与中标通知书抽取同一项目的结构化业绩记录，输出 JSON、CSV 和抽取报告。
- 中标通知书保留 9 行数量、金额和总部采购申请号；合同保留产品族、规格和合同页码，通过每行含税金额唯一匹配，不按两份文件的不同排序直接拼接。
- 新增 `backend/rag/project_performance.py`，企业知识库问答优先读取结构化业绩层。
- 合同签署日期在原件字段中为空，记录为 `contract_sign_date_blank_in_source`，未使用中标日期或交货日期代填。

### 抽取结果

| 项目 | 结果 |
| --- | --- |
| 项目业绩 | 1 项 |
| 证据文件 | 2 份 |
| 逐项明细 | 每份 9 行，共 18 行交叉核验 |
| 招标编号/包号 | `0322AB` / 包2 |
| 产品 | MPP、CPVC 电缆保护管 |
| 总数量 | 54,678 米 |
| 含税金额 | 6,372,409.05 元 |
| 中标日期 | 2022-11-21 |
| 合同签署日期 | 原件字段为空，未推断 |

### 真实链路结果

- 真实 HTTP `/api/knowledge/search/stream` 返回正确项目名称、招标编号、产品、数量、金额、甲乙方、中标日期、合同日期缺失状态和来源页码。
- 结构化结果纠正了此前普通 RAG 曾生成的错误汇总值；当前准确值为 54,678 米、6,372,409.05 元。
- 单元与查询回归：`21 passed`，1 个既有 PyPDF2 deprecation warning。

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨域串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3 | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% |
| 泰昌专项 | qwen3 | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% |

### 结论

- Gate PASS，P1B-5 完成。
- 后续新增合同、中标通知书、验收单或发票时，按 `AGENTS.md` 中“泰昌项目业绩结构化抽取 SOP”重跑并记录差异。

---

## Run 24 — P1B-6 Logo 与图片资产 DOCX 版式验证（2026-06-12）

> 验证报告：`docs/development/runs/run_20260612_taichang_supplement_p1b6_logo_image_layout.md`

### 处理内容

- 正式 DOCX 封面和页眉接入高清 `assets/icons/taichang_logo.png`。
- 正文图片插入改为按可用宽高等比例缩放，不做裁剪、不按固定框填充。
- 验证脚本新增 DOCX 图片版式审计：检查 `a:srcRect` 裁剪标记、媒体原始宽高比和 Word 内联显示宽高比。

### 真实导出结果

| 项目 | 结果 |
| --- | ---: |
| 图片候选 | 597 |
| 自动选图 | 24 |
| 补充包选中图片 | 18 |
| 图片插入 | 24 |
| 图片失败 | 0 |
| DOCX 图片裁剪标记 | 0 |
| 比例检查图片 | 27 |
| 最大比例偏差 | 0.000101 |

### 结论

- P1B-6 PASS。
- Logo 已稳定进入封面和页眉；正式 DOCX 中整页扫描件和资产图片保持完整显示，没有裁剪标记和比例变形。

---

## Run 25 — P1B-7 泰昌 MVP 资料完整性评分（2026-06-12）

> 完整性评分表：`docs/rag/taichang-material-completeness-scorecard.md`  
> 增量门禁：`docs/rag/runs/run_20260612_taichang_material_completeness_scorecard_summary.md`  
> 真实 Stream：`docs/rag/runs/run_20260612_taichang_material_completeness_scorecard_stream.md`

### 处理内容

- 新增泰昌 MVP 资料完整性评分表，按标书章节和资料域评估企业基本情况、资质证书、财务、检验报告、产品实物、生产制造、试验检测、绿色低碳、人员、项目业绩、偏差表、签章授权、招标场景样本、标准规范和 DOCX 交付版式。
- 明确区分“MVP 演示可用”和“正式投标资料完整”：当前 MVP 演示与本地试点可用度为 86/100，正式投标资料完整度为 76/100。
- 将客户仍需补充或确认的资料分为 P0/P1/P2：目标项目完整招标文件包及实际语义定位到的投标文件格式/组成/编制要求、目标规格参数覆盖、投标保证值、签章授权、正确 GB/DL 标准 PDF、验收/履约证明、产品实物照片、银行资信和信用证明等。

### 真实链路验证

真实 DB + `/api/bidding/knowledge/search/stream` 专项验证：

| 指标 | 结果 |
| --- | ---: |
| 补充批次文档 | 24 |
| 补充批次 chunks | 1900 |
| 补充批次图片资产 | 297 |
| 异常资产 metadata | 0 |
| 复合合同/中标通知书问题 | HTTP 200，5 个文本上下文 / 8 个资产，PASS |
| Logo/生产线/产品图片问题 | HTTP 200，5 个文本上下文 / 8 个资产，PASS |
| CPVC/MPP 检验报告参数问题 | HTTP 200，5 个文本上下文 / 8 个资产，PASS |

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨域串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 258 ms |
| Base | qwen3 | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 572 ms |
| 泰昌专项 | off | 93.3% | 100.0% | 0.933 | 3.3% | 0.0% | 321 ms |
| 泰昌专项 | qwen3 | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 656 ms |

### 结论

- Gate PASS，P1B-7 完成。
- 当前资料可支撑泰昌 MVP 演示、企业知识库问答和正式 DOCX 初稿；正式投标前仍需按目标招标文件补齐或确认 P0/P1 清单中的规格覆盖、偏差保证值、签章授权、验收/履约证明和正确标准 PDF。

---

## Run 26 — DeepSeek 全量重写完整标书与客户版导出回归（2026-06-12）

> DeepSeek 全量重写记录：`docs/development/runs/run_20260612_taichang_deepseek_full_rewrite.md`  
> DOCX/PDF 验收记录：`docs/development/runs/run_20260612_taichang_full_bid_final_v6.md`  
> RAG 增量门禁：`docs/rag/runs/run_20260612_taichang_full_bid_deepseek_rewrite_regression_summary.md`

### 处理内容

- 针对客户反馈修复正式标书导出问题：封面首页清空页眉 Logo，正文页保留泰昌页眉；Logo 自动裁白并解除固定行距裁切；正文使用 `SimSun`、标题使用 `Arial Unicode MS`，并统一 DOCX 四类字体字段，避免 PDF 字体替换异常。
- 新增 `scripts/rag/regenerate_taichang_full_bid_deepseek.py`，按章节先清空旧正文，再调用真实 DeepSeek 生成并保存，不使用历史 30 章正文替换。
- 新增/增强客户验收检查：封面首页页眉为空、配置中文字体存在、空章节数、目录点引导线、页脚页码字段、图片插入、表格版式、内部字段泄漏和重复父章节标题。

### 真实 DeepSeek 生成结果

| 项目 | 结果 |
| --- | ---: |
| 模型 | `deepseek-v4-flash` |
| 目标章节 | 74 |
| 成功章节 | 74 |
| 失败章节 | 0 |
| 生成耗时 | 1979.87 秒 |

### 真实 DOCX/PDF 导出结果

| 指标 | 结果 |
| --- | ---: |
| 有正文章节 | 74/74 |
| Markdown 字符数 | 166913 |
| DOCX 段落 | 2747 |
| DOCX 标题 | 74 |
| 目录条目 | 65 |
| 表格数量 | 109 |
| 图片选中/插入/失败 | 24 / 24 / 0 |
| 封面首页页眉为空 | 通过 |
| 配置中文字体检查 | 通过 |
| PDF 预览 | 已生成 |

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨域串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 228 ms |
| Base | qwen3 | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 592 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 311 ms |
| 泰昌专项 | qwen3 | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 639 ms |

### 结论

- Gate PASS。
- 本轮客户版完整标书已经完成真实 DeepSeek 全量章节重写、正式 DOCX 导出、LibreOffice 字段刷新、PDF 生成和 Base + 泰昌专项增量回归。

---

## Run 27 — 泰昌标书待补充信息与资料入库反查（2026-06-12）

> 审计清单：`docs/rag/taichang-bid-information-gap-audit-20260612.md`
> DOCX/PDF 验证：`docs/development/runs/run_20260612_taichang_bid_numbering_final.md`
> 增量回归：`docs/rag/runs/run_20260612_taichang_bid_information_gap_audit_summary.md`

- 最终 Markdown 检出 `845` 处 `【待补充】`，归并后 `404` 类。
- 泰昌补充批次已有 `24` 份文本资料、`1687` 个 child/table 检索块，三体系证书、合同、中标通知书、检验报告、企业报告和人员资料均已真实解析入库。
- 审计确认大量占位属于“已有资料未回填”，不能归为客户资料缺失；另有设备台账、审计报告、开户图片等需要二次结构化和人工核验。
- 真正需要客户确认的核心项为本次投标包、最终报价、交货/质保/有效期承诺、保证金信息、项目角色指定、签章日期和量化产能/服务承诺。
- 施工资质、建造师、BIM、水利施工等与电缆保护管供货无关的内容列为不适用清理项，不向客户索要。
- 编号修复后的真实 DOCX/PDF 导出 PASS；原 360+ 全文连续序号已消失。
- 增量回归 Gate PASS：Base off/qwen3 Recall@5 均为 `96.7%`，泰昌专项 off 为 `96.7%`、qwen3 为 `100.0%`；四组 Top1 来源准确率均为 `100%`，跨 doc_role 串扰均为 `0%`。

---

## Run 28 — 泰昌企业事实约束重写、残留占位归类与真实回归（2026-06-12）

> DeepSeek 事实约束重写：`docs/development/runs/run_20260612_taichang_fact_grounded_full_rewrite.md`
> DOCX/PDF 客户演示验收：`docs/development/runs/run_20260612_taichang_fact_grounded_final.md`
> 残留占位逐项归类：`docs/rag/taichang-bid-remaining-placeholders-classification-20260612.md`
> 真实 stream：`docs/rag/runs/run_20260612_taichang_fact_grounded_targeted_stream.md`
> 增量门禁：`docs/rag/runs/run_20260612_taichang_fact_grounded_full_rewrite_summary.md`

### 处理内容

- 新增企业事实约束写作链路，将泰昌统一社会信用代码、三体系证书、MPP/CPVC 检验报告、0322AB 项目业绩、生产/检测能力等可追溯事实注入章节 prompt。
- 清理与电缆保护管供货不适用的施工模板语义，标题和正文禁止继续引入水利施工、桩基、防渗墙、BIM、建造师、施工总承包等内容。
- 74 个章节全部通过真实 `deepseek-v4-flash` 重写，生成阶段没有失败章节，没有触发禁用主题二次清理。
- 对成品 Markdown 中 `649` 处残留 `【待补充】` 逐项归类，输出 649 行 CSV；按优先级归并为 P0 `436`、P1 `155`、P2 `58`，其中 P0 主要是最终报价、包件货物清单、交货/质保/响应期限、保证金银行信息、授权签章等不可由模型编造的信息。

### 真实 DOCX/PDF 导出结果

| 指标 | 结果 |
| --- | ---: |
| 状态 | PASS |
| 章节节点/有正文 | 74 / 74 |
| Markdown 字符数 | 186251 |
| DOCX 段落/标题 | 2834 / 74 |
| 目录条目 | 65 |
| 表格数量 | 130 |
| 图片选中/插入/失败 | 24 / 24 / 0 |
| 图片裁剪标记 | 0 |
| 页眉页脚/页码字段 | 通过 |
| LibreOffice 字段刷新 | refreshed |

### 真实 stream 验证

- `run_20260612_taichang_fact_grounded_real_stream` 真实 DB + stream 质量复核中，数据库、资产 metadata、报告参数、Logo/生产线问答均通过；综合“合同或中标通知书”问法未显式带出 `0322AB`，按失败样本保留。
- 追加专项真实 stream `run_20260612_taichang_fact_grounded_targeted_stream` 通过：`0322AB`、包2、合同金额 `6,372,409.05`、数量 `54,678`、合同签署日期空白状态均可从真实链路回答；完整标书不可编造项分类问答通过。

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨域串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 249 ms |
| Base | qwen3 | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 586 ms |
| 泰昌专项 | off | 93.3% | 100.0% | 0.933 | 3.3% | 0.0% | 314 ms |
| 泰昌专项 | qwen3 | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 664 ms |

### 自动化回归

- `.venv/bin/python -m pytest tests/test_length_settings.py tests/test_section_generation_autoresume.py tests/test_docx_export.py -q`
- 结果：`51 passed, 1 warning`。

### 结论

- Gate PASS，P1B-10 完成。
- 当前客户演示版可展示真实全流程结果；正式投标前必须优先让客户确认 P0 清单，不能由模型自动补全报价、包件、期限、保证金、授权签章等实质性承诺信息。

---

## Run 29 — 云环境暂挂后的本地优先级同步与真实基线回归（2026-06-16）

> 任务清单同步：`docs/rag/todo.md` P1C、`docs/development/local-next-phase-tasks.md`
> 增量门禁：`docs/rag/runs/run_20260616_local_priority_sync_baseline_summary.md`
> 真实 stream：`docs/rag/runs/run_20260616_local_priority_sync_stream.jsonl`
> 任务状态记录：`docs/development/runs/run_20260616_local_priority_sync.md`

### 触发原因

客户暂未提供阿里云测试环境账号，因此云上 ECS/RDS/OSS/Redis 联调继续暂挂。本轮按本地真实环境可验证、且直接影响泰昌单企业试点客户试用稳定性的口径，重新同步任务优先级。

### 真实环境检查

- `/api/ready` 真实健康检查通过：database、Redis、Celery、model_config、storage 均为 `ok`，在线 Celery worker 数为 `1`。
- 直连 PostgreSQL 复核 `knowledge_assets`：总数 `597`，已有 embedding `297`，缺失 embedding `300`。
- 缺失 embedding 的资产全部集中在 `source_batch_id=customer_liaoning_taichang_20260606_p0_formal_full_page_assets_v1`；`customer_taichang_supplement_20260611` 批次 `297/297` 已有 embedding。
- 真实 `/api/bidding/knowledge/search/stream` 登录鉴权后抽样通过：问题“泰昌有哪些生产线或生产制造能力图片资料？”召回 `4` 条资料、`8` 个图片资产，并返回 `done`。

### 优先级同步

- 第一任务确认为：`P1C-1 泰昌 20260606 正式图片资产 embedding backfill`。
- 同步新增本地优先任务：图片资产 embedding backfill、关键词兜底缓存失效、RAG 本地门禁自动化入口、前导确认页变量 schema v1。
- 云上联调继续列为外部条件阻塞，不纳入当前本地 P0 执行序列。

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨域串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 260 ms |
| Base | qwen3 | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 564 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 327 ms |
| 泰昌专项 | qwen3 | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 647 ms |

### 结论

- Gate PASS。
- 本轮没有新增资料入库，也没有修改召回策略代码；仅同步任务清单并建立当前真实环境基线。
- 下一步执行 P1C-1 时必须在补齐资产 embedding 后复跑真实资产语义召回、真实 `/api/knowledge/search/stream` 抽样和 Base + 泰昌专项增量回归门禁。

---

## Run 30 — 泰昌 20260606 正式图片资产 embedding backfill（2026-06-16）

> Backfill 脚本：`scripts/rag/backfill_knowledge_asset_embeddings.py`
> Backfill 记录：`docs/rag/runs/run_20260616_taichang_asset_embedding_backfill_asset_embedding_backfill.md`
> 增量门禁：`docs/rag/runs/run_20260616_taichang_asset_embedding_backfill_gate_summary.md`
> 真实 stream：`docs/rag/runs/run_20260616_taichang_asset_embedding_backfill_stream_*.jsonl`

### 触发原因

P1C-1 要求补齐 `customer_liaoning_taichang_20260606_p0_formal_full_page_assets_v1` 批次 300 条正式整页/原图资产的 embedding。该批次此前 300 条资产全部 `embedding is null`，影响图片资产语义召回和后续 DOCX 自动配图排序。

### 执行环境

- Embedding 后端：本地 Ollama OpenAI-compatible，`EMBEDDING_BASE_URL=http://localhost:11434/v1`
- Embedding 模型：`qwen3-embedding:0.6b`
- 向量维度：`1024`
- 执行命令：

```bash
set -a; source .env; set +a
.venv/bin/python scripts/rag/backfill_knowledge_asset_embeddings.py \
  --run-id run_20260616_taichang_asset_embedding_backfill \
  --batch-size 20
```

### Backfill 结果

| 批次 | before total | before with embedding | before missing | after with embedding | after missing |
| --- | ---: | ---: | ---: | ---: | ---: |
| `customer_liaoning_taichang_20260606_p0_formal_full_page_assets_v1` | 300 | 0 | 300 | 300 | 0 |

执行统计：

| 指标 | 数量 |
| --- | ---: |
| selected | 300 |
| updated | 300 |
| skipped_empty_text | 0 |
| failed | 0 |

脚本在首次真实执行时触发了非阻断的 AI 用量记录日志：`usage_context.batch_id` 传入了非 UUID 的 run id，导致 `ai_usage_logs.batch_id` 写入失败；embedding 生成与资产更新均已成功。随后已修正脚本，改为把 run id 写入 metadata，不再占用 UUID 字段。

### 资产召回抽样

直接资产召回验证：

| 问法 | 结果 |
| --- | --- |
| 泰昌营业执照图片 | 命中营业执照副本原图和 20260606 批次“泰昌营业执照副本第1页” |
| 泰昌MPP生产线图片 | 命中 MPP 生产线原图和 20260606 批次生产线页 |
| 泰昌检测设备图片 | 命中试验设备台账、锤击试验装置等 testing_capacity 资产 |
| 泰昌CPVC电缆保护管检验报告图片 | 命中 CPVC 检验报告原图和 20260606 批次检验报告页 |
| 泰昌MPP电缆保护管检验报告图片 | 命中 MPP 检验报告原图和 20260606 批次检验报告页 |
| 泰昌绿色低碳资料图片 | 命中绿色发展规划报告、绿色供应链认证证书等资产 |

真实 `/api/bidding/knowledge/search/stream` 抽样：

| 问法 | contexts | assets | 状态 | 代表性图片 |
| --- | ---: | ---: | --- | --- |
| 泰昌MPP生产线有哪些图片资料？ | 5 | 8 | done | MPP生产线第1页、MPP生产线原图 |
| 泰昌MPP电缆保护管检验报告图片资料有哪些？ | 5 | 8 | done | MPP检验报告原图、MPP检验报告第3页/第1页 |
| 泰昌营业执照图片资料有哪些？ | 4 | 8 | done | 营业执照副本原图、营业执照副本第1页 |
| 泰昌营业执照和绿色低碳资料图片有哪些？ | 2 | 8 | done | 绿色发展规划报告、绿色供应链认证证书 |

说明：复合问法“营业执照和绿色低碳”被绿色低碳资产占据靠前位置，因此追加单独营业执照问法作为验收样本；后续若要求复合问法逐类均衡展示，可归入资产排序/多证据覆盖优化。

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨域串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 229 ms |
| Base | qwen3 | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 590 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 320 ms |
| 泰昌专项 | qwen3 | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 651 ms |

### 结论

- Gate PASS。
- P1C-1 完成，当前真实库 `knowledge_assets` 两个泰昌批次合计 597 条资产均已有 embedding。
- 下一任务顺延为 P1C-2：关键词兜底缓存失效机制。

---

## Run 31 — 企业知识库/资信库/产品库页面与 P1C-2 关联复核（2026-06-16）

> 页面复核记录：`docs/rag/runs/run_20260616_enterprise_library_pages_review.md`

### 触发原因

客户后续大概率持续补充资料，同时前端“企业知识库”“企业资信库”“企业产品库”支持用户单独上传资料。本轮先复核三类页面是否可用，并确认它们与 `P1C-2 关键词兜底缓存失效机制` 的关系。

### 真实环境结果

- 真实后端实际监听 `0.0.0.0:3012`，`/api/ready` 返回 `ok`。
- 当前用户侧 `5173` 前端仍代理到默认 `127.0.0.1:8000`，浏览器登录请求 `/api/users/login` 返回 `500`，三类页面会停留在登录页。
- 使用临时 `5174` 前端并设置 `VITE_API_PROXY_TARGET=http://127.0.0.1:3012` 后，登录和三类页面均可正常访问。

### 页面和接口抽样

| 页面/接口 | 结果 |
| --- | --- |
| `GET /api/knowledge/documents` | 200，198 条文档 |
| `GET /api/knowledge/assets?asset_type=qualification_image` | 200，208 条资信资产 |
| `GET /api/knowledge/assets?asset_type=product_image` | 200，389 条产品资产 |
| 企业知识库页面 | 列表正常，上传资料按钮可见，文档详情和解析内容预览可打开 |
| 企业资信库页面 | 列表正常，新增/上传入口可见，新增表单和必填校验正常 |
| 企业产品库页面 | 列表正常，新增/上传入口可见，新增表单和必填校验正常 |

### 与 P1C-2 的结论

- 企业知识库文档上传强相关：上传后会写入 `knowledge_documents` 和 `document_chunks`，而 `_keyword_search_knowledge_chunks` 使用进程级 `_CHUNK_KEYWORD_CACHE`，必须在新增/重入库后失效。
- 企业资信库/企业产品库资产上传间接相关：上传写 `knowledge_assets`，并即时生成 asset embedding；资产关键词兜底直接查询 `knowledge_assets`，不使用 `_CHUNK_KEYWORD_CACHE`。
- P1C-2 仍有必要，核心验收应覆盖“Web 不重启 + 新增文档 chunk + 真实 stream 可立即命中”；资信/产品上传作为补充回归样本，验证 asset embedding 和资产检索链路。

---

## Run 32 — P1C-2 关键词兜底缓存失效机制（2026-06-16）

> 实现记录：`docs/rag/runs/run_20260616_p1c2_keyword_cache_invalidation_summary.md`
> 真实 stream：`docs/rag/runs/run_20260616_p1c2_keyword_cache_invalidation_after_stream.jsonl`
> 增量门禁：`docs/rag/runs/run_20260616_p1c2_keyword_cache_invalidation_gate_summary.md`

### 触发原因

客户后续会持续补充资料，且企业知识库页面支持单独上传资料。原关键词兜底缓存为 Web 进程内全局 `_CHUNK_KEYWORD_CACHE`，存在新增/重入库 `document_chunks` 后读取旧快照的风险。

### 实现内容

- `backend/rag/retrieval.py` 新增 `document_chunks` 水位指纹：总数、最新 `created_at`、最新 `id`。
- 关键词兜底每次使用缓存前先读取轻量指纹；指纹变化时自动重建缓存。
- 新增 `invalidate_chunk_keyword_cache(reason)` 显式清理入口。
- `backend/rag/ingestion.py` 在删除旧分片和写入新分片后调用显式清理。
- `tests/test_rag_retrieval.py` 增加显式失效和指纹变化自动重建测试。

### 测试与真实验收

| 验收项 | 结果 |
| --- | --- |
| `py_compile` | PASS |
| `pytest tests/test_rag_retrieval.py -q` | 16 passed |
| 真实 stream 预热旧缓存后插入新 chunk | PASS |
| 不重启 Web 命中新 chunk | PASS，`after_contains_secret=true`、`after_done=true` |
| 测试数据清理 | PASS |

说明：真实 stream 验收中，测试 chunk 必须带完整泰昌企业事实 metadata，尤其是 `reference_only=false`；缺失该字段时会被泰昌试点过滤正确排除。

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨域串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 268 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 619 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 357 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 686 ms |

### 结论

- Gate PASS。
- P1C-2 完成。
- 下一任务顺延为 P1C-3：RAG 本地门禁自动化入口。

---

## Run 33 — P1C-3 RAG 本地门禁自动化入口（2026-06-16）

> 本地门禁脚本：`scripts/rag/run_local_rag_gate.py`
> 本地门禁汇总：`docs/rag/runs/run_20260616_p1c3_local_rag_gate_summary.md`
> 增量门禁汇总：`docs/rag/runs/run_20260616_p1c3_local_rag_gate_incremental_summary.md`
> 真实 stream：`docs/rag/runs/run_20260616_p1c3_local_rag_gate_stream.jsonl`

### 触发原因

P1C-3 要求把本地 RAG 质量门禁固化为一个可重复入口，避免每次 RAG 改动后依赖人工记忆分别执行 API ready、单元测试、增量回归和真实 stream 抽样。

### 实现内容

- 新增 `scripts/rag/run_local_rag_gate.py`：
  - 真实 `GET /api/ready`；
  - RAG 相关单测；
  - 调用现有 `scripts/rag/run_incremental_regression_gate.py`；
  - 登录真实本地账号并调用 `/api/knowledge/search/stream`；
  - 输出 JSON/Markdown 汇总、步骤耗时、产物路径和 PASS/FAIL。
- 新增 `tests/test_local_rag_gate.py`，覆盖 SSE 事件解析和 stream 汇总逻辑。

### 执行命令

```bash
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_local_rag_gate.py \
  --run-id run_20260616_p1c3_local_rag_gate
```

### 本地门禁结果

| 步骤 | 状态 | 耗时 | 结果 |
| --- | --- | ---: | --- |
| api_ready | PASS | 2149 ms | database、Redis、Celery、model_config、storage 均正常 |
| rag_unit_tests | PASS | 942 ms | exit_code=0 |
| incremental_regression_gate | PASS | 60126 ms | exit_code=0 |
| stream_sample | PASS | 15134 ms | contexts=5、assets=8、images=8、done=true |

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨域串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 291 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 607 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 323 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 670 ms |

### 结论

- 本地 RAG 门禁 PASS。
- P1C-3 完成。
- 下一任务顺延为 P1C-4：前导确认页变量 schema v1 与预填缺口报告。

---

## Run 34 — P1C-4 前导确认页变量 schema v1 与预填缺口报告（2026-06-16）

> 功能验收：`docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_feature_summary.md`
> 本地门禁汇总：`docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_summary.md`
> 增量门禁汇总：`docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_incremental_summary.md`
> 真实 stream：`docs/rag/runs/run_20260616_p1c4_prefill_schema_gap_report_stream.jsonl`

### 触发原因

P1C-4 要求把前导确认页从产品概念推进到真实可用能力：将当前正式投标高风险占位从大量正文缺口收敛为可确认的投标字段 schema、预填来源规则和客户确认缺口报告，并提供前端旁路只读页面。

### 实现内容

- 新增 `backend/services/bid_prefill.py`：定义 `2026-06-16.v1` 变量 schema，共 32 个字段。
- 新增 `GET /api/bidding/projects/<project_id>/prefill-report`：基于真实项目解读、招标文本和知识资产生成报告。
- 新增 `/prefill` 投标信息确认页：默认读取最新项目，支持 `?projectId=<id>`，展示字段分组、候选值、来源规则和客户确认缺口。
- 主导航新增“投标确认”；招标项目页新增“投标信息确认”入口。
- 新增 `tests/test_bid_prefill.py`，覆盖客户决策字段不得自动补全、企业资产仅作为候选来源。

### 真实接口与页面验收

| 项 | 结果 |
| --- | --- |
| 真实项目 | `4bc3ee73-9ec5-4184-aafd-eaede9f90798` |
| 新接口 | PASS，`schemaVersion=2026-06-16.v1` |
| 字段数 | 32 |
| 客户需填写 | 10 |
| 待人工确认 | 10 |
| 正式必填缺口 | 15 |
| 旁路只读 | `readonlyFirst=true` |
| 导出契约 | `affectsSectionsSnapshotExport=false` |
| 前端页面 | 使用本地真实账号登录访问 `/prefill` PASS，截图：`docs/development/runs/run_20260616_p1c4_prefill_page.png` |

### 执行命令

```bash
.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_local_rag_gate.py
cd frontend && npm run build
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_local_rag_gate.py \
  --run-id run_20260616_p1c4_prefill_schema_gap_report
```

### 本地门禁结果

| 步骤 | 状态 | 结果 |
| --- | --- | --- |
| api_ready | PASS | http=200；database、Redis、Celery、model_config、storage 均正常 |
| targeted pytest | PASS | `tests/test_bid_prefill.py tests/test_local_rag_gate.py` 4 passed |
| frontend build | PASS | `npm run build` 成功 |
| rag_unit_tests | PASS | 门禁脚本内 RAG 单测 exit_code=0 |
| incremental_regression_gate | PASS | exit_code=0 |
| stream_sample | PASS | contexts=5、assets=8、images=8、done=true |

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词 | 跨域串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 279 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 614 ms |
| 泰昌专项 | off | 93.3% | 100.0% | 0.933 | 3.3% | 0.0% | 328 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 692 ms |

### 结论

- Gate PASS。
- P1C-4 完成第一版真实可用闭环。
- 当前版本为旁路只读确认页，不写入 `bid_sections`，不替代正文编辑，不影响 `sectionsSnapshot` DOCX 导出契约。
- 下一步建议进入“变量确认后的显式回填引擎”，继续保持用户确认优先。

---

## Run 35 — P1C-7 泰昌参考模板标书成品度收口（2026-06-17）

> 开发验收：`docs/development/runs/run_20260617_p1c7_taichang_reference_bid.md`
> 本地门禁汇总：`docs/rag/runs/run_20260617_p1c7_taichang_reference_bid_summary.md`
> 增量门禁汇总：`docs/rag/runs/run_20260617_p1c7_taichang_reference_bid_incremental_summary.md`
> 真实 stream：`docs/rag/runs/run_20260617_p1c7_taichang_reference_bid_stream.jsonl`

### 触发原因

用户指出真实生成标书仍像半成品，且没有贴近客户提供的河北豪乾参考标书结构。按资料边界，河北豪乾只能作为目录、表式和写法参考，泰昌企业事实必须来自泰昌资料，辽宁资料只作为招标要求样本。

### 实现内容

- 前导确认页新增确认值后端应用和审计，回填显式占位符但不覆盖用户编辑正文。
- 纯物资供货项目大纲改为 23 节参考结构，覆盖业绩、投标函、商务响应、技术响应、报价文件和附件索引。
- 章节写作注入泰昌核验事实包，统一社会信用代码、法人、产品检验报告、参数和真实业绩不再写成待补充。
- 新增正式占位归并，重复泛化占位压缩为少量客户确认项。
- DOCX 导出新增正式 readiness metadata，记录空章节、占位、必填缺口和模板策略。

### 真实项目验收

| 项 | 结果 |
| --- | --- |
| 项目 | `a1d853bc-ca4e-43b4-bbea-256f561c8a3d` |
| 章节节点 | 23 |
| 叶子章节 | 19 |
| 有正文叶子章节 | 19 |
| 空叶子章节 | 0 |
| 正文占位 | 39 |
| 禁用主题 | 0 |
| DOCX 字段刷新 | `refreshed` |
| PDF 预览 | `generated` |
| 图片 | selected 24，inserted 24，failed 0 |
| formal readiness | `false`，剩余 15 个客户/招标文件确认字段 |

### 执行命令

```bash
.venv/bin/python -m pytest \
  tests/test_bid_prefill.py \
  tests/test_section_writer_formal_quality.py \
  tests/test_chapter_planner.py \
  tests/test_length_settings.py \
  tests/test_section_generation_autoresume.py \
  tests/test_docx_export.py -q
cd frontend && npm run build
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_local_rag_gate.py \
  --run-id run_20260617_p1c7_taichang_reference_bid
```

### 本地门禁结果

| 步骤 | 状态 | 结果 |
| --- | --- | --- |
| api_ready | PASS | http=200；status=ok |
| targeted pytest | PASS | `67 passed, 1 warning` |
| frontend build | PASS | Vite build 成功，仅既有 chunk 警告 |
| rag_unit_tests | PASS | 门禁脚本内 RAG 单测 exit_code=0 |
| incremental_regression_gate | PASS | exit_code=0 |
| stream_sample | PASS | contexts=5、assets=8、images=8、done=true |

### 增量回归门禁

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词 | 跨域串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 282 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 604 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 344 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 684 ms |

### 结论

- Gate PASS。
- P1C-7 完成工程链路和真实项目草稿收口。
- 产物不再是空章节/施工模板污染的半成品，但正式投标前必须由客户或招标文件补齐 15 个报价、包件、保证金、授权签署等字段，之后重新应用前导确认并导出 readiness 为 `true` 的最终版。

---

## Run 36 — P1C-8 客户参考模板目录解析修复（2026-06-17）

> 开发验收：`docs/development/runs/run_20260617_p1c8_reference_outline_rebuild.md`
> JSON 报告：`docs/development/runs/run_20260617_p1c8_reference_outline_rebuild.json`

### 触发原因

用户指出 P1C-7 导出的目录只有 23 节，明显少于客户参考标书。复核后确认问题不是 DOCX/PDF 目录渲染，而是大纲源头使用了手写 23 节兜底结构，没有真正读取客户提供的河北豪乾参考稿 TOC。

### 实现内容

- 供货类大纲优先读取 `haoqian_reference_templates.json` 中商务/技术参考稿的 `toc_lines`。
- 清洗目录点引导线、页码和目录页噪声，并按 `（一）`、`1.`、`1.1`、`1.1.1` 等编号层级建树。
- 目录只复用结构，河北豪乾供应商名、具体专利名、软件名和历史业绩项目名被泛化为结构项。
- 最大目录层级收敛为 4 级，避免正式 DOCX 目录过深。
- 参考稿缺失或截断时合并投标函、授权、保证金、售后、报价、附件索引等必备供货结构。

### 真实项目验收

| 项 | 结果 |
| --- | --- |
| 项目 | `a1d853bc-ca4e-43b4-bbea-256f561c8a3d` |
| 重建前章节 | 23 |
| 重建后章节 | 102 |
| 一级章节 | 6 |
| 二级章节 | 27 |
| 三级章节 | 30 |
| 四级章节 | 39 |
| 最大层级 | 4 |
| 已有正文回填 | 14 个同名章节 |
| 豪乾具体事实标题命中 | 0 |

### 执行命令

```bash
.venv/bin/python -m py_compile backend/ai/chapter_planner.py
.venv/bin/python -m pytest tests/test_chapter_planner.py -q
```

结果：`10 passed`。

### 结论

- P1C-8 完成。
- 后续供货类大纲不再默认落到 23 节兜底目录。
- 下一任务进入 P4：货物清单/技术参数表结构化联动增强，优先提升包号、包名称、货物清单摘要、产品规格型号和技术参数表的自动预填质量。

---

## Run 37 — P4-8 货物清单结构化联动前导页候选（2026-06-17）

> 实现记录：`docs/rag/runs/run_20260617_p4_structured_prefill_linkage_impl.md`
> 本地门禁：`docs/rag/runs/run_20260617_p4_structured_prefill_linkage_summary.md`
> 增量门禁：`docs/rag/runs/run_20260617_p4_structured_prefill_linkage_incremental_summary.md`

### 触发原因

P1C-8 修复章节目录后，下一优先级进入 P4。目标是在不生成正文、不处理 PDF 的前提下，让章节/前导页所需的包号、包名称、货物清单摘要先从结构化表取候选，避免继续靠正文正则猜测。

### 实现内容

- `backend/services/bid_prefill.py` 接入辽宁 2225AC 货物清单行级记录 `goods_tables/goods_rows.json`。
- 按项目编号、包号、CPVC/MPP 物料关键词过滤结构化货物清单。
- 为 `package_no`、`package_name`、`material_category`、`goods_list_summary` 生成前导页候选。
- 证据标记为 `sourceDomain=tender_requirement` 且 `factSourceAllowedForEnterprise=false`，不把辽宁招标清单作为泰昌企业事实。
- 确认应用逻辑未改变：只有客户确认后的值才会替换正文占位符。

### 真实项目抽样

项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d`：

| 字段 | 状态 | 结果 |
| --- | --- | --- |
| 包号 | 待人工确认 | `包1` |
| 包名称 | 待人工确认 | `电缆保护管CPVC、电缆保护管MPP（需按目标包确认）` |
| 物料类别 | 系统已识别 | `电缆保护管CPVC、电缆保护管MPP` |
| 货物清单摘要 | 待人工确认 | 共 38 行需求，包1 合计 102583 米，技术规范编码 10 个 |
| 产品规格型号 | 企业库带出 | 仍来自泰昌核验事实包，未被辽宁清单覆盖 |

### 测试与回归

```bash
.venv/bin/python -m py_compile backend/services/bid_prefill.py
.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_chapter_planner.py -q
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_local_rag_gate.py --run-id run_20260617_p4_structured_prefill_linkage
```

定向测试：`17 passed`。

本地门禁结果：

| 步骤 | 状态 | 结果 |
| --- | --- | --- |
| api_ready | PASS | http=200；status=ok |
| rag_unit_tests | PASS | exit_code=0 |
| incremental_regression_gate | PASS | exit_code=0 |
| stream_sample | PASS | contexts=5、assets=8、images=8、done=true |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 252 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 636 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 336 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 696 ms |

### 结论

- P4-8 完成，门禁 PASS。
- 前导页已能从结构化货物清单获取可追溯候选。
- 辽宁招标要求、泰昌企业事实边界保持隔离。
- 本次未生成正文，也未处理 DOCX/PDF 字体、格式或乱码问题。

---

## Run 38 — P4-9 技术参数表联动章节占位与偏差表候选（2026-06-18）

> 实现记录：`docs/rag/runs/run_20260618_p4_technical_parameter_linkage_impl.md`
> 本地门禁：`docs/rag/runs/run_20260618_p4_technical_parameter_linkage_summary.md`
> 增量门禁：`docs/rag/runs/run_20260618_p4_technical_parameter_linkage_incremental_summary.md`

### 触发原因

P4-8 已把货物清单结构化候选接入前导页。本轮继续推进技术参数表和偏差表，但仍保持边界：不生成正文，不处理 DOCX/PDF，只把结构化参数和缺口做成客户可确认候选。

### 实现内容

- `backend/services/bid_prefill.py` 新增 `technical_parameter_summary`、`technical_deviation_candidates`、`taichang_parameter_match_summary` 3 个候选字段。
- 接入辽宁技术参数表 `technical_parameter_rows.json`、偏差辅助表 `technical_deviation_rows.json` 和泰昌产品参数 `taichang_product_parameter_rows.json`。
- 技术参数和偏差候选按项目编号、包号、物料类别过滤，证据标记为 `sourceDomain=tender_requirement` 且 `factSourceAllowedForEnterprise=false`。
- 泰昌参数佐证标记为 `sourceDomain=enterprise_fact`，但覆盖判断优先对比货物清单实际规格，并明确“不构成覆盖辽宁全部规格结论”。
- 确认应用链路未改变：只有客户确认后的值才替换正文占位符，不自动写无偏差。

### 真实项目抽样

项目 `a1d853bc-ca4e-43b4-bbea-256f561c8a3d`：

| 字段 | 状态 | 结果 |
| --- | --- | --- |
| 技术参数表候选摘要 | 待人工确认 | 包1 共 300 行，CPVC/MPP，待补投标响应/保证值 300 行 |
| 技术偏差表候选 | 待人工确认 | `pending_response` 284 行、`informational` 16 行；不自动写入无偏差 |
| 泰昌参数佐证摘要 | 待人工确认 | 泰昌结构化检验报告 36 行、2 份报告；现有内径 250 报告未直接覆盖辽宁货物清单规格 50/100/150/200 |

### 测试与回归

```bash
.venv/bin/python -m py_compile backend/services/bid_prefill.py
.venv/bin/python -m pytest tests/test_bid_prefill.py tests/test_taichang_product_parameter_query.py tests/test_technical_deviation_report.py -q
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_local_rag_gate.py --run-id run_20260618_p4_technical_parameter_linkage
```

定向测试：`18 passed`。

本地门禁结果：

| 步骤 | 状态 | 结果 |
| --- | --- | --- |
| api_ready | PASS | http=200；status=ok |
| rag_unit_tests | PASS | exit_code=0 |
| incremental_regression_gate | PASS | exit_code=0 |
| stream_sample | PASS | contexts=5、assets=8、images=8、done=true |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 276 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 590 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 342 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 705 ms |

### 结论

- P4-9 完成，门禁 PASS。
- 技术参数表、技术偏差表和泰昌检验报告参数已进入前导页/章节占位候选层。
- 辽宁招标要求与泰昌企业事实边界保持隔离。
- 本次未生成正文，也未处理 DOCX/PDF 字体、格式或乱码问题。

---

## Run 39 — 阿里云企业知识库问答冒烟（2026-06-24）

> 运行记录：`docs/rag/runs/run_20260624_aliyun_enterprise_knowledge_qa_smoke.md`

### 测试范围

在阿里云真实页面登录企业知识库助手，执行：

1. 泰昌有哪些资质证书？
2. 泰昌 CPVC 电缆保护管有哪些检验报告？
3. 泰昌有哪些企业证明材料？

### 结果

| 问题 | 结果 | 关键结论 |
| --- | --- | --- |
| 泰昌有哪些资质证书？ | FAIL | 未优先使用三份正式体系认证证书，展示内部 `certification/taichang_*` 名称 |
| 泰昌 CPVC 电缆保护管有哪些检验报告？ | 基本通过 | 报告编号、规格和结构化参数正确，但暴露内部 API 路径且来源标签重复 |
| 泰昌有哪些企业证明材料？ | FAIL | 错误声明缺少已入库基础证照，社保证明分类错误，暴露 `parsed_outputs/` 路径 |

### 结论

- `/api/health`、`/api/ready`、数据库、Redis、Celery、存储和模型配置均正常。
- 问答链路可用，但企业事实来源优先级、缺口判断和用户展示不达标。
- 本轮未发现辽宁招标要求或河北豪乾参考稿直接作为泰昌企业事实返回。
- 新增 P1C-14，修复并复测前不进入最小标书主流程验收。

---

## Run 40 — P1C-14 企业知识库问答事实与来源本地修复回归（2026-06-24）

> 本地门禁：`docs/rag/runs/run_20260624_p1c14_local_final_summary.md`
> 增量门禁：`docs/rag/runs/run_20260624_p1c14_local_final_incremental_summary.md`
> 三问真实复测：`docs/rag/runs/run_20260624_p1c14_local_final_three_question_stream_summary.md`

### 触发原因

Run 39 在阿里云真实页面发现企业知识库问答存在 P0/P1 缺陷：资质证书问题未优先命中三份正式体系认证证书，企业证明材料问题误判已入库基础证照缺失，社保证明分类混乱，并暴露 `taichang_*`、`production_capacity`、`parsed_outputs/` 和内部 API 路径。

### 修复范围

- 企业事实问答扩大召回候选并按问题意图重排，资质证书优先质量、环境、职业健康安全三体系认证。
- 企业证明材料问答合并文本片段与图片资产，营业执照、体系认证、社保证明等资产可进入回答依据。
- 参考来源与图片资产展示经过中文化和安全清洗，过滤内部路径、英文枚举、API 文件地址和重复来源。
- 本地 Ollama `qwen3-embedding:0.6b` 通过真实 `/v1/embeddings` 兼容分支完成向量请求，解决 OpenAI SDK/httpx 对 Ollama 返回 502 导致门禁无法跑通的问题；DashScope 生产分支不变。
- 追问建议过滤未经证实的“目前缺少/未提供”等缺口结论。

### 测试与回归

| 验证项 | 结果 |
| --- | --- |
| 定向后端测试 | PASS，`35 passed` |
| 前端构建 | PASS，仅保留既有 chunk size 警告 |
| `/api/ready` | PASS，数据库、Redis、Celery、模型配置、存储均正常 |
| 本地 RAG 门禁 | PASS，api_ready / rag_unit_tests / incremental_regression_gate / stream_sample 全部通过 |
| 三问真实 stream 复测 | PASS，3/3 通过 |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 241 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 556 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 345 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 664 ms |

三问复测结果：

| 问题 | 结果 | 关键结论 |
| --- | --- | --- |
| 泰昌有哪些资质证书？ | PASS | 明确返回质量、环境、职业健康安全三项正式体系认证证书，来源为客户原始证书资产，不再优先 ESG 或绿色发展资料 |
| 泰昌 CPVC 电缆保护管有哪些检验报告？ | PASS | 返回报告编号 `2024100312005501713`、规格 `DS 250×15×6000 SN16 PVC-C` 和结构化参数/原始报告来源，不暴露内部 API 路径 |
| 泰昌有哪些企业证明材料？ | PASS | 返回营业执照、三体系认证、社保证明和企业现场材料，不再错误声明基础证照缺失，社保证明不再归入生产制造或试验检测能力 |

### 结论

- P1C-14 本地真实环境修复通过，可进入提交、推送和阿里云测试环境部署。
- 云上部署后仍需按 Run 39 的同三问口径做真实页面复测；云上复测通过前，阿里云环境仍不应进入最小标书主流程正式验收。

---

## Run 41 — SG-PROMPT-001 Prompt profile 输入预算回归（2026-06-25）

> 本地门禁：`docs/rag/runs/run_20260625_sg_prompt_001_summary.md`
> 增量门禁：`docs/rag/runs/run_20260625_sg_prompt_001_incremental_summary.md`
> 开发运行记录：`docs/development/runs/run_20260625_sg_prompt_001_prompt_profile_budget.md`

### 触发原因

批量章节生成在客户真实测试中出现后半段慢流与 `MODEL_STREAM_WALL_TIMEOUT`，且旧 `build_section_prompt()` 对大量简单章节仍加载企业上下文、事实包、资料候选、RAG 和完整章节约束。本轮先完成可验证的 prompt profile 分级、输入预算和任务 metadata，为后续慢流提前保护与自适应并发提供指标基础。

### 修复范围

- 章节生成新增七类 profile：轻量方案、事实支撑、技术参数、结构化表格、附件索引、报价敏感和草稿续写。
- 不同 profile 独立控制 RAG 条数、企业资料条数、泰昌事实包模式、列表输入上限和 `max_prompt_chars`。
- `stream_bid_section()` 的 `start` 事件输出 profile 指标；Celery item metadata 和 legacy task JSON 同步保存这些指标。
- PostgreSQL 原子更新函数白名单允许 patch `metadata`，避免 profile 指标只存在明细表、不进入任务快照。

### 测试与回归

| 验证项 | 结果 |
| --- | --- |
| Prompt profile 单测 | PASS，`tests/test_section_prompt_policy.py` 5 passed |
| 章节生成相关回归 | PASS，21 passed |
| API/RAG 相关回归 | PASS，35 passed |
| DOCX/Celery 导出单测 | PASS，48 passed |
| 本地 RAG 门禁 | PASS，api_ready / rag_unit_tests / incremental_regression_gate / stream_sample 全部通过 |
| 真实 stream 抽样 | PASS，contexts=5、assets=4、images=4、done=true |
| 完整 DOCX 链路 | PASS，正式导出任务 completed，图片 selected/inserted/failed 为 `23/23/0`，LibreOffice 字段刷新成功 |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 265 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 594 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 354 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 698 ms |

### 结论

- `SG-PROMPT-001` 已完成，本地真实环境验证通过。
- 本轮未新增客户资料、未改变 RAG 入库策略；召回门禁无退化，泰昌/辽宁/河北豪乾边界未出现跨资料域串扰。
- 后续 P0 继续进入慢流提前保护、partial 草稿释放并发槽、自适应并发和前端可解释进度。

---

## Run 42 — SG-SLOW-001 慢流提前保护回归（2026-06-25）

> 本地门禁：`docs/rag/runs/run_20260625_sg_slow_001_summary.md`
> 增量门禁：`docs/rag/runs/run_20260625_sg_slow_001_incremental_summary.md`
> 开发运行记录：`docs/development/runs/run_20260625_sg_slow_001_slow_stream_protection.md`

### 触发原因

客户真实批量章节生成已出现后半段慢流和 `MODEL_STREAM_WALL_TIMEOUT`，旧链路会长期占用生成槽直到 300 秒超时，导致全文编制体感为卡死。本轮在 SG-PROMPT-001 输入预算基础上，增加流式低吞吐提前保护，让慢章节尽早保存 partial 草稿并释放生成槽。

### 修复范围

- `stream_bid_section()` 增加流式监控，记录首 token 延迟、输出字符数、chars/min 和慢流原因。
- 慢流阈值支持环境变量配置，并按 prompt profile 设置默认最小字符数。
- 低吞吐时抛出 `MODEL_STREAM_SLOW_TIMEOUT`，任务 item 进入 `partial_generated`，并保存 `partial_chars`、`partial_words`、`timeout_code` 和慢流指标。
- `generate_and_save_bid_section()` 与 Celery worker 均透传 `stream_metric/timeout` metadata，legacy task JSON 和任务明细保持一致。
- 本轮未新增客户资料、未改 RAG 入库策略、未改召回排序；仅按专项规则执行 RAG 回归门禁。

### 测试与回归

| 验证项 | 结果 |
| --- | --- |
| 后端编译检查 | PASS |
| 慢流/续写单测 | PASS，13 passed |
| 章节/API 相关回归 | PASS，30 passed |
| DOCX/Celery 导出单测 | PASS，48 passed |
| 本地 RAG 门禁 | PASS，api_ready / rag_unit_tests / incremental_regression_gate / stream_sample 全部通过 |
| 强制慢流真实任务 | PASS，任务 `29c99120-38e9-4b3d-a67c-5eef6925dbd3` 进入 `partial_failed`，item 为 `partial_generated`，`timeout_code=MODEL_STREAM_SLOW_TIMEOUT` |
| 正常阈值真实任务 | PASS，任务 `41b912db-3d7a-4ca5-b8aa-1e64dbfcfe66` completed，`slow_stream=false` |
| 临时数据清理 | PASS，两个回归临时章节均已删除，回归 metadata 剩余 0 |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 242 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 594 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 344 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 706 ms |

真实 stream 抽样：`done=true`，contexts=5，assets=4，images=4。

### 结论

- `SG-SLOW-001` 已完成，本地真实环境验证通过。
- 召回门禁无退化，泰昌/辽宁/河北豪乾边界未出现跨资料域串扰。
- 后续 P0 继续进入 `SG-CONCURRENCY-001`：自适应并发调度与任务级慢流窗口降档。

---

## Run 43 — SG-CONCURRENCY-001 自适应并发调度回归（2026-06-25）

> 本地门禁：`docs/rag/runs/run_20260625_sg_concurrency_001_summary.md`
> 增量门禁：`docs/rag/runs/run_20260625_sg_concurrency_001_incremental_summary.md`
> 开发运行记录：`docs/development/runs/run_20260625_sg_concurrency_001_adaptive_scheduler.md`

### 触发原因

SG-SLOW-001 已能让低吞吐章节提前保存 partial 草稿并释放生成槽，但调度器仍按固定 `SECTION_GEN_CONCURRENCY` 补位。如果模型服务整体变慢，固定补位会持续把新章节推入慢流窗口。本轮增加任务级自适应并发策略，让慢流窗口自动降档，稳定窗口具备恢复并发能力。

### 修复范围

- 新增 `section_generation_policy.resolve_section_generation_concurrency()`，独立计算调度窗口。
- `_dispatch_next_sections()` 按 policy 输出的 `current_concurrency` 租约补位，不再直接用固定并发。
- 任务 metadata 写入 `scheduler_policy/current_concurrency/max_concurrency/recent_slow_count/slow_stream_count/timeout_count/policy_message`。
- 慢流 partial 写入 `partial_reason/next_action/retry_policy`，后续续写和前端展示可解释。
- `requeue_bid_generation_task_item()` 保留原 item metadata，避免 partial 续写丢失慢流历史。
- 本轮未新增客户资料、未改 RAG 入库策略、未改召回排序；仅按 P0 回归规则执行 RAG 门禁。

### 测试与回归

| 验证项 | 结果 |
| --- | --- |
| 自适应 policy/调度单测 | PASS，13 passed |
| 章节/API 相关回归 | PASS，35 passed |
| DOCX/Celery 导出单测 | PASS，48 passed |
| 本地 RAG 门禁 | PASS，api_ready / rag_unit_tests / incremental_regression_gate / stream_sample 全部通过 |
| 初始窗口真实任务 | PASS，任务 `98ad8494-ba70-40c7-8856-f01c77db2cc9` completed，`current_concurrency=2`、`max_concurrency=3` |
| 慢流降档真实任务 | PASS，任务 `3881462f-e18f-4aa3-88d7-965d740f0b97` 在 2 个慢流 partial 后 `current_concurrency=1`、`last_policy_change=reduce_concurrency`，只单路补位 |
| 临时数据清理 | PASS，4 个 `regression_case=sg_concurrency_001` 临时章节剩余 0，测试任务行剩余 0 |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 239 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 580 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 340 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 712 ms |

真实 stream 抽样：`done=true`，contexts=5，assets=4，images=4。

### 结论

- `SG-CONCURRENCY-001` 已完成，本地真实环境验证通过。
- 召回门禁无退化，泰昌/辽宁/河北豪乾边界未出现跨资料域串扰。
- 后续 P0 继续进入 `SG-PARTIAL-001`：partial 草稿续写上限、复核态与批量续写入口。

---

## Run 44 — SG-PARTIAL-001 partial 草稿续写闭环回归（2026-06-25）

> 本地门禁：`docs/rag/runs/run_20260625_sg_partial_001_summary.md`
> 增量门禁：`docs/rag/runs/run_20260625_sg_partial_001_incremental_summary.md`
> 开发运行记录：`docs/development/runs/run_20260625_sg_partial_001_partial_resume.md`

### 触发原因

SG-CONCURRENCY-001 已能按任务慢流窗口降档，但 partial 草稿还缺少明确的续写上限、复核态和批量续写入口。真实回归同时发现 coordinator 对 partial-only 任务存在早退：没有 queued item 时不会进入 `_dispatch_next_sections()`，导致自动续写策略无法触发。

### 修复范围

- 新增 `partial_resume_v1` 策略，按草稿占目标比例、尝试次数、慢流次数和 prompt profile 判定自动续写、人工复核或手动续写。
- 修复 partial-only coordinator 早退，确保已有 partial 草稿也能进入调度策略。
- partial item metadata 写入 `partial_resume_action`、`partial_review_required`、`partial_resume_reason`、`partial_draft_ratio`、`retry_policy` 和 `next_action`。
- 手动/批量续写写入 `manual_resume_requested`，保留草稿并清除复核阻断。
- 标书目录页新增 partial/复核/慢流/当前并发统计，行级状态区分“草稿可续写/草稿需复核”，工具栏新增“批量续写草稿”。
- 本轮未新增客户资料、未改 RAG 入库策略、未改召回排序；仅按 P0 回归规则执行 RAG 门禁。

### 测试与回归

| 验证项 | 结果 |
| --- | --- |
| partial policy / 调度 / prompt 定向测试 | PASS，24 passed |
| 章节/API/DOCX 相关回归 | PASS，61 passed |
| 前端构建 | PASS |
| 本地 RAG 门禁 | PASS，api_ready / rag_unit_tests / incremental_regression_gate / stream_sample 全部通过 |
| 短 partial 自动续写真实任务 | PASS，任务 `096b97ea-0315-4df7-aa75-7f807f115f78` completed，`retry_reason=auto_resume_partial`、`partial_resume_action=auto_resume`、`prompt_profile=continuation_slim` |
| 复核态真实任务 | PASS，任务 `5276347b-d8f2-4ff2-8c8a-76a103395b8b` 保持 `partial_generated`，`partial_review_required=true`、`partial_resume_reason=slow_partial_limit_reached` |
| 批量续写真实 API | PASS，同一复核态任务经 `/resume` + `reason=batch_resume_partial` 续写到 `done`，`manual_resume_requested=true`、`partial_review_required=false`、`prompt_profile=continuation_slim` |
| 页面入口真实回归 | PASS，真实 API 临时 partial 任务下出现“批量续写草稿”，顶部统计显示草稿/复核/慢流，1440px 无横向溢出 |
| 临时数据清理 | PASS，`regression_case=sg_partial_001` 与 `sg_partial_001_ui` 临时任务和章节剩余 0 |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 264 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 607 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 342 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 704 ms |

真实 stream 抽样：`done=true`，contexts=5，assets=4，images=4。

### 结论

- `SG-PARTIAL-001` 已完成，本地真实环境验证通过。
- 召回门禁无退化，泰昌/辽宁/河北豪乾边界未出现跨资料域串扰。
- 后续 P0 继续进入 `SG-PROGRESS-001`：前端可解释进度与下载前 partial 草稿提示。

---

## Run 45 — SG-PROGRESS-001 客户视角进度与下载前草稿提示回归（2026-06-25）

> 本地门禁：`docs/rag/runs/run_20260625_sg_progress_001_summary.md`
> 增量门禁：`docs/rag/runs/run_20260625_sg_progress_001_incremental_summary.md`
> 开发运行记录：`docs/development/runs/run_20260625_sg_progress_001_user_readiness.md`

### 触发原因

SG-PARTIAL-001 已让 partial 草稿可自动续写、转复核和批量续写，但客户不需要理解慢流、并发窗口等技术概念。下载/导出前必须用业务语言明确提示当前文件是否仍是草稿版，避免客户把未完成正文或待复核草稿误认为正式投标文件。

### 修复范围

- 目录页顶部统计改为“待完成章节、正在写、排队、草稿待续写、需复核”等客户可理解口径。
- 移除客户界面上的“模型慢流”“当前并发”等技术提示，技术细节继续保留在任务 metadata 和内部运行记录。
- 全文 DOCX 下载前新增草稿版确认，说明草稿版仅用于内部查看，不能作为正式投标文件提交。
- partial tooltip 改为“草稿已保存、建议复核、继续编写保留已有内容”等用户口径。
- 本轮未新增客户资料、未改 RAG 入库策略、未改召回排序；仅按 P0 回归规则执行 RAG 门禁。

### 测试与回归

| 验证项 | 结果 |
| --- | --- |
| 前端构建 | PASS |
| 章节/API/DOCX 相关回归 | PASS，74 passed |
| 本地 RAG 门禁 | PASS，api_ready / rag_unit_tests / incremental_regression_gate / stream_sample 全部通过 |
| 页面进度真实回归 | PASS，真实 API 临时 partial 任务下显示“待完成章节”“草稿待续写：1”“需复核：1”，未出现技术词 |
| 下载前确认真实回归 | PASS，点击“标书下载”先弹出“下载前确认：当前文件仍是草稿版”，并可返回继续编写 |
| 临时数据清理 | PASS，`regression_case=sg_progress_001_ui` 临时任务 2 条剩余 0 |

增量回归指标：

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 266 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 569 ms |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% | 343 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% | 711 ms |

真实 stream 抽样：`done=true`，contexts=5，assets=4，images=4。

### 结论

- `SG-PROGRESS-001` 已完成，本地真实环境验证通过。
- 召回门禁无退化，泰昌/辽宁/河北豪乾边界未出现跨资料域串扰。
- 批量章节生成可靠性与 Prompt 分级瘦身 P0 主链路已完成，后续进入维护回归；下一阶段回到项目总账继续处理剩余 P0。

---

## Run 46 — 阿里云线上企业库来源收敛回归与前端来源标题补丁（2026-06-26）

> 线上回归记录：`docs/rag/runs/run_20260626_aliyun_online_source_scope_regression.md`
> 本地收敛门禁：`docs/rag/runs/run_20260626_taichang_enterprise_source_scope_final_review.md`

### 触发原因

用户已将 `ac01c14` 发布到阿里云线上环境，需要按 P0 清单对“阿里云企业库展示与来源收敛收口”做真实 API 与 Chrome 页面回归，重点确认“泰昌有哪些资质证书？”不再把 ESG、绿色发展规划、绿色供应链、碳足迹、废水废气等资料作为资质证书参考来源。

### 测试与回归

| 验证项 | 结果 |
| --- | --- |
| 线上版本确认 | PASS，`buildId=20260626113858-ac01c14e699a`，`commit=ac01c14e699a` |
| `/api/health` | PASS |
| `/api/ready` | PASS，database / redis / celery / storage / vector / model_config ready |
| 线上临时账号注册登录 | PASS |
| API：资质证书问答 | PASS，只命中 3 项正式体系认证证书，未混入绿色低碳资料 |
| API：企业证明材料问答 | PASS，营业执照、体系证书、社保证明等企业证明材料边界正确 |
| API：绿色低碳问答 | PASS，ESG、绿色发展规划、碳足迹等绿色资料可正常召回 |
| API：人员证书/社保证明问答 | PASS，只命中人员/社保证明相关资料 |
| API：CPVC 检验报告问答 | PASS，命中 CPVC 内径 250 检验报告和结构化参数来源 |
| API：生产制造能力问答 | PASS，命中生产线、厂房、土地租赁等生产制造能力资料 |
| Chrome 页面：资质证书问答 | PASS，页面回答未出现 ESG、绿色发展规划、绿色供应链、碳足迹、废水废气等资料 |
| Chrome 页面：绿色低碳问答 | 核心语义 PASS；发现参考来源标题优先级残留 |
| 前端构建 | PASS，`npm run build` |
| Chrome 页面：前端标题补丁发布后复验 | PASS，线上 `cfd1e4e03dd5` 参考来源标题已显示“绿色发展规划报告”“碳足迹报告”，未再显示旧目录名 |

### 发现与修复

线上 Chrome 反向场景发现一个展示层残留：绿色低碳资料的 `source_display_name` 已是“绿色发展规划报告”，但旧 `source_document_name` 仍是“泰昌资质证书图片资产目录”；前端参考来源标题优先展示旧字段，导致页面标题不够干净。

本轮已做最小修复：

- `frontend/src/pages/KnowledgeBase/KnowledgeSearchDrawer.tsx` 新增 `sourcePrimaryName()`；
- `sourceTitle()` 优先使用清洗后的 `source_display_name`；
- `sourceKey()` 去重使用同一主展示名，避免旧目录名影响页面来源展示。

### 结论

- 阿里云线上 `ac01c14` 的后端来源收敛、metadata 修复和核心问答链路已通过真实 API + Chrome 页面验证。
- 前端标题补丁 `cfd1e4e03dd5` 发布后，Chrome 页面复验通过。
- 资质证书问答参考来源污染问题已消除，绿色低碳参考来源标题已收敛，`P1C-15` 按严格 P0 口径关闭。

---

## Run 47 — 阿里云线上泰昌正式资产中文化与图文导出全流程回归（2026-06-27）

> 运行记录：`docs/development/runs/run_20260627_aliyun_browser_full_regression.md`

### 触发原因

用户已将泰昌正式资料资产中文化、RAG 来源显示修复和 DOCX 图片题注清洗同步到阿里云测试环境，需要按真实正式投标场景做线上全流程验证，确认企业知识库、产品库、资信库、问答和技术/商务标图文导出不再暴露 `图示：XX第X页`、内部枚举、解析路径或 API 资产路径。

### 测试与回归

| 验证项 | 结果 |
| --- | --- |
| 线上服务 | PASS，`http://8.160.187.226` 可访问，`/api/health` 返回 `status=ok` |
| Chrome 登录 | PASS，`admin` 登录成功 |
| 企业知识库页面 | PASS，禁用字段命中 0 |
| 企业产品库页面 | PASS，禁用字段命中 0 |
| 企业资信库页面 | PASS，禁用字段命中 0 |
| 知识库助手 CPVC 参数问答 | PASS，禁用字段命中 0 |
| 6 类真实 stream | PASS，CPVC、MPP、生产制造能力、试验检测设备、资质证书、绿色低碳资料均 HTTP 200，禁用字段命中 0 |
| 技术标 DOCX 导出 | PASS，任务 completed，图片候选/插入/失败/跳过为 26/24/0/2，字段刷新 `refreshed` |
| 商务标 DOCX 导出 | PASS，任务 completed，图片候选/插入/失败/跳过为 24/24/0/0，字段刷新 `refreshed` |
| DOCX 文件级 XML 审计 | PASS，技术标/商务标 `word/*.xml` 中禁用表达命中 0 |
| 正式导出门禁 | PASS，当前新疆 10kV 导线项目仍因客户确认字段和产品适配 `T-000` 被阻断正式导出，仅允许草稿导出 |

### 发现与边界

- 技术标任务 metadata 的 `image_conversion.captions.samples.source` 保留旧原始题注作为后台追溯；实际写入 DOCX 的题注已正式化为 `资料：MPP电缆保护管检验报告` 等中文表达，下载文件 XML 审计确认旧题注未进入正文。
- `/api/health` 的 `branch/commit` 仍为 `unknown`，不影响本轮功能验收；线上版本以服务器 `git log`、容器重建和真实行为为准。
- 当前招标包物料为 10kV 导线类，泰昌现有已核验产品资料主要覆盖 CPVC/MPP 电缆保护管，因此 `T-000` 继续阻断正式投标文件导出，符合真实投标风险控制。

### 结论

阿里云测试环境泰昌正式资料资产中文化、RAG 问答展示、产品库/资信库页面展示和技术/商务分册 DOCX 图文导出主链路已通过真实浏览器回归。本轮 P0/P1 线上验收关闭；后续仍需更新泰昌专项旧评测集，避免继续要求召回已被正式隔离的解析中间 chunk。

---

## Run 48 — 泰昌专项评测集正式资料口径更新与增量门禁闭环（2026-06-27）

> 门禁记录：`docs/rag/runs/run_20260627_taichang_formal_asset_cleanup_gate_v2_summary.md`
> 豪乾 metadata 修复：`docs/rag/runs/run_20260627_haoqian_reference_metadata_repair.md`

### 触发原因

泰昌正式资料资产治理后，旧专项评测集仍要求召回历史图片资产索引、`asset_path`、`bbox`、`display_contexts`、`parsed_outputs` 等解析内部字段。按正式投标场景，这些内容已被隔离且不得进入用户可见问答或标书正文，因此需要更新评测集口径并重新跑标准门禁。

### 修复内容

- 修复河北豪乾参考稿 metadata：2 个参考文档、70 个 chunk 已统一为 `source_domain=reference_template`、`reference_only=true`、`fact_source_allowed_for_enterprise=false`、`citation_policy=reference_style_only`。
- 更新 `tests/rag/customer_liaoning_taichang_testset.jsonl`：
  - 企业事实用例显式增加 `doc_role=enterprise_evidence`，避免“响应”等字样被自动推断为 `self_phrase`；
  - 资产用例不再以内部字段为成功条件，改为验证正式中文资料、泰昌企业事实和禁用内部字段；
  - 河北豪乾参考稿用例只验证格式/目录/章节结构参考，不再允许作为泰昌事实来源；
  - 绿色低碳、生产制造、试验检测等 hard case 问题改为贴近当前正式资料标题和用户真实问法。

### 门禁结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 269 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 620 ms |
| 泰昌专项 | off | 93.3% | 100.0% | 0.917 | 3.3% | 0.0% | 351 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.973 | 0.0% | 0.0% | 714 ms |

### 结论

标准增量回归门禁 PASS。泰昌专项已从旧口径失败恢复为正式资料治理口径下的 100% 召回，且禁用关键词命中率和跨资料域串扰均为 0。本轮不新增客户资料、不重入库；仅修复河北豪乾参考稿 metadata 和评测集口径。

---

## Run 49 — 产品库/资信库上传入口正式资产回归（2026-06-27）

> 真实链路记录：`docs/rag/runs/run_20260627_upload_entry_formal_asset_regression.md`  
> 门禁记录：`docs/rag/runs/run_20260627_upload_entry_formal_asset_gate_summary.md`

### 触发原因

泰昌正式资产治理完成后，需要验证后续客户从产品库/资信库页面新增上传图片或附件时，不会再次把 `页面_`、`原图`、`taichang_*`、`production_capacity`、`product_image`、`technical` 等内部字段带入用户侧展示、RAG 问答或正式标书配图链路。

### 修复内容

- `backend/api/assets.py` 在上传/更新资产入库前生成正式中文标题、分类、标签、说明、`source_display_name` 和正式题注策略。
- 新增证据类型推断，覆盖营业执照、资质证书、检验报告、生产制造能力、试验检测能力、绿色低碳、项目业绩、财务、人员证书和产品图片。
- `searchable_text` 排除内部枚举字段，并把卷册字段写为“技术标/资格文件/商务标”等中文词。
- `backend/rag/display_names.py` 将用户侧资产返回中的 `product_image/qualification_image` 映射为“产品图片/资信图片”。

### 真实验证

| 验证项 | 结果 |
| --- | --- |
| 真实登录 | PASS，`POST /api/users/login` 使用 `admin` 登录成功 |
| 真实上传 | PASS，`POST /api/knowledge/assets/upload` 上传测试图 `泰昌MPP生产线_页面_9原图.png` |
| 上传返回 | PASS，标题 `泰昌MPP生产线资料`、分类 `生产制造能力`、标签 `泰昌/生产制造能力` |
| 列表/详情 | PASS，用户侧禁用字段命中 0 |
| 真实 stream | PASS，问题 `泰昌MPP生产线资料可以作为技术标生产制造能力配图吗？` 召回新上传资产，回答正文禁用字段命中 0 |
| 测试资产清理 | PASS，测试资产已从数据库删除，详情接口返回“知识资产不存在” |
| 自动化测试 | PASS，`tests/test_knowledge_asset_upload_payload.py tests/test_rag_display_names.py tests/test_rag_retrieval.py` 为 40 passed |

### 门禁结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 246 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 567 ms |
| 泰昌专项 | off | 90.0% | 100.0% | 0.867 | 3.3% | 0.0% | 327 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.973 | 0.0% | 0.0% | 691 ms |

### 结论

P1-5 上传入口新资产规则回归通过。后续新上传资产默认以正式中文字段入库，RAG 主链路和用户侧 SSE 不再暴露内部枚举或解析追溯痕迹。本轮只删除回归测试资产，不修改泰昌正式资产数据。

---

## Run 50 — 泰昌法定代表人问答污染修复与回归（2026-06-29）

> 门禁记录：`docs/rag/runs/run_20260629_taichang_legal_representative_fact_fix_summary.md`

### 触发原因

客户在知识库助手提问“这家公司的法人代表是谁？”时，回答曾输出错误姓名“王伟杰”。排查确认不是单纯模型幻觉，而是泰昌知识库中“宣传彩页/OCR中间片段”被错误作为可引用企业事实参与召回，且片段内含 `法定代表人：王伟杰`、`法人代表：刘志勇` 等与营业执照冲突的工商字段。

### 修复内容

- 新增泰昌企业工商基础信息结构化上下文，法人、法定代表人、统一社会信用代码、注册资本、成立日期、注册地址等问题优先依据核验事实包、营业执照副本和企业信用报告。
- 新增 `enterprise_basic_info` 查询范围；基础工商信息问题不再回退到宣传彩页、生产线、审计报告、人员花名册、劳动合同等无关或低可信 OCR 片段。
- 执行 `scripts/rag/repair_taichang_legal_representative_facts.py --execute`，将 5 个冲突 chunk 标记为 `exclude_from_rag=true`、`rag_visibility=internal_only`、`fact_source_allowed_for_enterprise=false`。
- 新增回归测试覆盖检索意图、结构化企业事实和知识库排序过滤。

### 真实验证

| 验证项 | 结果 |
| --- | --- |
| 脏数据隔离 | PASS，5 个冲突 chunk 已禁止进入 RAG |
| 直接检索 | PASS，仅返回“泰昌企业工商基础信息｜优先依据”，法定代表人 `晁坤琳` |
| 流式问答 | PASS，`/api/knowledge/search/stream` 返回 `晁坤琳`，未出现 `王伟杰` |
| 非流式问答 | PASS，`/api/knowledge/search` 返回 `晁坤琳`，未出现 `王伟杰` |
| 定向测试 | PASS，`tests/test_rag_retrieval.py tests/test_taichang_enterprise_facts.py tests/test_knowledge_enterprise_scope.py` 为 38 passed |

### 门禁结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 259 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 589 ms |
| 泰昌专项 | off | 93.3% | 100.0% | 0.900 | 3.3% | 0.0% | 338 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.973 | 0.0% | 0.0% | 677 ms |

### 结论

标准增量回归门禁 PASS。法定代表人类企业基础事实问答已从低可信 OCR 召回切换为确定性企业工商事实优先，当前真实链路返回“晁坤琳”，未再出现“王伟杰”。

---

## Run 51 — 企业工商基础事实通用防护与来源展示收敛（2026-06-29）

> 门禁记录：`docs/rag/runs/run_20260629_taichang_enterprise_basic_fact_guard_summary.md`

### 触发原因

首次修复虽然解决了“法人代表误答王伟杰”，但修复脚本仍存在按错误姓名枚举的倾向，不能支撑后续客户追问统一社会信用代码、注册资本、成立日期、注册地址等企业基础事实。同时知识库助手“参考资料来源”仍展示 5 条来源，且低相关来源中出现空括号和 `enterprise_profile` 等用户不可见内部枚举。

### 修复内容

- repair 脚本改为通用字段冲突检测：从低可信/OCR片段中抽取高置信工商字段，与泰昌核验事实包比对；不再按“王伟杰/刘志勇”等具体错误姓名枚举。
- 企业基础工商事实问题统一进入 `enterprise_basic_info` 范围，优先依据结构化事实包、营业执照和企业信用报告。
- 参考资料来源后端合并限制为 Top 3，前端展示限制为 Top 3，提示词要求参考依据最多引用前三条资料。
- 来源展示清理空括号，`公司人员花名册（）` 显示为 `公司人员花名册`；`enterprise_profile` 映射为“企业宣传资料”。
- 本轮真实库额外隔离 6 个高置信冲突 chunk，覆盖错误法定代表人、错误注册资本和错误统一社会信用代码 OCR 片段。

### 真实验证

| 验证项 | 结果 |
| --- | --- |
| 通用冲突检测 | PASS，任意错误姓名（测试用“张三”）会因与核验事实冲突被识别，不依赖固定姓名枚举 |
| 法人代表 stream | PASS，返回 `晁坤琳`，来源 3 条，无 `王伟杰`、无空括号、无内部枚举 |
| 统一社会信用代码 stream | PASS，返回 `91130607056539515C`，来源 3 条，无空括号、无内部枚举 |
| 定向测试 | PASS，47 passed |
| 前端构建 | PASS，`npm run build` 成功 |

### 门禁结果

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 | 平均耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 252 ms |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% | 570 ms |
| 泰昌专项 | off | 93.3% | 100.0% | 0.917 | 3.3% | 0.0% | 335 ms |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.973 | 0.0% | 0.0% | 659 ms |

### 结论

标准增量回归门禁 PASS。企业工商基础事实问答已具备通用防护，不再依赖单个错误样本补丁；知识库助手参考来源已收敛为相关度最高前三条，并清理空括号和内部枚举展示。

---

## Run 52 — 泰昌历史标书复用 P0-01 验收口径专项验证（2026-07-13）

> 总记录：`docs/development/runs/run_20260713_taichang_p0_01_acceptance_scope.md`

### 触发原因

开发泰昌历史标书复用前，先锁定最终成稿正向、SL2655 规则/资料缺口和 SL265A 跨产品阻断三类验收项目，防止后续把相近规格或跨产品资料误判为可正式投标。

### 真实验证

| 验证项 | 结果 |
| --- | --- |
| 服务就绪 | PASS，`/api/ready` 中数据库、Redis、Celery 和模型配置正常 |
| 泰昌 MPP 断裂伸长率单参数问答 | PASS，真实 stream 返回 176%、报告编号 `2024100312005501712` |
| SL2655 规格覆盖问答 | PASS，真实 stream 逐项判定 250×22/176% 不覆盖 200×14/≥200% |
| SL265A 跨产品阻断问答 | PASS，真实 stream 明确 MPP/CPVC 不得证明 10kV 架空绝缘导线能力 |
| MPP 复合参数问答 | FAIL，组合询问规格、环刚度和伸长率时只召回环刚度并误报伸长率缺失；单参数问答正常 |
| 正向项目清单扫描 | BLOCKED，28 份 XLSX 解析错误 0，但未发现与泰昌现有 MPP/CPVC φ250 报告精确匹配的招标项目 |

### 结论

SL2655 和 SL265A 两类样本已锁定，产品/规格边界判定可用。最终成稿正向项目尚待客户补充或确认，P0-01 保持进行中。本轮未新增资料、未修改 metadata 或召回策略，因此未重复执行 Base 30 + 泰昌 30 全量门禁；复合参数召回修复或正向项目资料新增后必须执行标准增量回归门禁。

---

## Run 53 — 泰昌历史标书复用 P0-02 数字资产基线快照（2026-07-13）

> 总记录：`docs/development/runs/run_20260713_taichang_p0_02_asset_baseline.md`

### 触发原因

在拆解两份泰昌历史标书前，先从当前真实数据库、staging 和原始资料冻结资产基线，避免沿用旧数量或把解析中间产物、重复文件、参考模板误当成可新增泰昌事实。

### 验证结果

| 验证项 | 结果 |
| --- | --- |
| 当前资产快照 | PASS，共 7,716 条统一记录，每条具有稳定业务键 |
| 数据库正式资产审计 | PASS，图片资产 599、知识文档 77、分块 6,347，用户可见/RAG可见问题均为 0 |
| staging 隔离 | PASS，539 条候选全部标记为解析中间产物，不进入正式展示、RAG或DOCX |
| 原始文件哈希 | PASS，116 份文件、91 个唯一哈希、25 份重复拷贝 |
| 结构化参数/业绩 | PASS，产品参数 36 行、项目业绩证据 2 条 |
| 快照生成单测 | PASS，4 passed |

### 结论

P0-02 基线快照完成。本轮没有新增资料、修改 metadata、调整召回或改变 DOCX 资产选择，因此不重复执行增量召回门禁和 DOCX 导出；发现的重复、质量等级缺口及 2 个测试资产残留已转入 P0-04/P0-05，不在本任务中直接修改正式数据。

---

## Run 54 — 泰昌历史标书复用 P0-03 两份 Word 只读解析（2026-07-13）

> 总记录：`docs/rag/runs/run_20260713_taichang_p0_03_historical_bid_inventory_summary.md`

### 触发原因

在进入四层去重和正式资产分类前，对泰昌标书人员提供的《技术补充文件》《商务补充文件》做原生 Word 只读盘点，提取历史参考骨架、表格、媒体关系、事实/参数候选和页序，并与 SL2655 样本中实际识别到的投标文件格式内容逐项对照。该对照不将第六章固化为其他项目定位规则。

### 验证结果

| 验证项 | 结果 |
| --- | --- |
| 技术标原生解析 | PASS，368 页、73 章、10 表、352 个媒体文件、486 条候选 |
| 商务标原生解析 | PASS，325 页、61 章、4 表、339 个媒体文件、410 条候选 |
| 目录页码覆盖 | PASS，技术 73/73、商务 61/61 标题取得目录页码 |
| 招标来源属性 | PASS，134 个章节全部带 `origin_type/source_file/source_section/confidence/review_status` |
| 参数证据分级 | PASS，既有报告、历史索引、笼统响应、候选规格分开处理 |
| 正式资产门禁 | PASS，全部候选为 `review_only + allowed_for_bid=false` |
| 定向测试 | PASS，9 passed（含 P0-02 基线测试） |

### 结论

P0-03 完成。原生 DOCX 解析已足以恢复两份历史稿的固定章节、表格、媒体关系和主要页序，本轮没有调用 MinerU/OCR。由于未新增资料入库、修改 metadata、召回策略或正式 DOCX 资产选择，本轮不执行增量召回门禁和正式 DOCX 导出；图片内部事实继续保持未识别状态，不能从历史截图自动提升为正式资产。

---

## Run 55 — 泰昌历史标书复用 P0-04 四层去重（2026-07-13）

> 总记录：`docs/rag/runs/run_20260713_taichang_p0_04_asset_dedup_summary.md`

### 触发原因

在 P0-05 标签、质量分级和任何增量入库前，先将两份泰昌历史标书的全部候选与现有数字资产基线做四层去重，防止 Word 内嵌图、同一检验报告的不同载体、历史项目字段或重复设备资料形成新的重复/冲突资产。

### 验证结果

| 验证项 | 结果 |
| --- | --- |
| 候选全覆盖 | PASS，896/896 均有 `dedup_status` |
| 精确重复阻断 | PASS，270 条全部禁止提升/入库 |
| 视觉疑似保护 | PASS，142 条全部要求人工复核，空白页/小图有保护标记 |
| 文本疑似保护 | PASS，5 条名称相同但缺业务主键的候选未自动合并 |
| 证据包映射 | PASS，2 个既有报告编号归入同证据不同载体候选 |
| 事实冲突阻断 | PASS，15 个历史项目号/固化 ID 均不得复用 |
| 冻结输入不变 | PASS，基线和两份候选清单 SHA-256 未变化 |
| 重复执行一致性 | PASS，忽略生成时间后 JSON 完全一致 |
| 定向/前序回归 | PASS，18 passed |

### 结论

P0-04 完成。全部候选仍为 `review_only + allowed_for_bid=false + promotion_eligible=false`；未连接数据库、未修改 metadata、未自动合并或正式入库。本轮不改变 RAG 语料/召回和 DOCX 资产选择，因此不重复执行 Base+泰昌全量召回门禁或 DOCX 导出；P0-05 若发生审核入库或 metadata 变更，必须执行标准增量门禁与真实 stream。

---

## Run 56 — 泰昌历史标书复用 P0-05 标签、分类与质量分级（2026-07-13）

> 总记录：`docs/rag/runs/run_20260713_taichang_p0_05_tag_classification_summary.md`

### 触发原因

P0-04 已完成 896 条历史标书候选的四层去重。本轮在任何人工批准或增量入库前，统一补齐标签、分类、质量、敏感性和中文展示字段，并建立 P0-06 人工复核队列，防止把“未发现重复”误解为“可以直接入库或用于正式标书”。

### 验证结果

| 验证项 | 结果 |
| --- | --- |
| 候选全覆盖 | PASS，896/896 已完成分类与必填 metadata |
| 质量等级 | PASS，`review_only` 838、`restricted` 58 |
| 人工复核队列 | PASS，461 条进入 P0-06 |
| 重复/冲突阻断 | PASS，270 条精确重复和 15 条事实冲突均不进入复核队列或入库候选 |
| 产品事实门禁 | PASS，产品族不明确不得提升为正式可用 |
| 中文展示门禁 | PASS，用户可见字段禁用表达命中 0 |
| 显式批准门禁 | PASS，无 P0-06 批准时正式增量入库候选为 0；仅传入批准 ID 也不能绕过质量门禁 |
| 重复执行与输入冻结 | PASS，忽略生成时间后输出一致，三份输入 SHA-256 未变化 |
| 定向/前序回归 | PASS，27 passed |

### 结论

P0-05 完成。本轮只新增离线分类脚本、JSON/CSV 和治理文档，未写数据库、未修改 RAG 语料/metadata/召回或 DOCX 选图，因此不重复执行 Base+泰昌全量召回门禁和正式 DOCX 导出。P0-06 实际批准并写入资产或修改 metadata 后，必须执行标准增量门禁、真实 `/api/knowledge/search/stream` 抽样和必要的正式 DOCX XML 审计。

---

## Run 57 — 泰昌历史标书复用 P0-06 人工复核与入库批准准备（2026-07-13）

> 总记录：`docs/rag/runs/run_20260713_taichang_p0_06_asset_review_preparation_summary.md`
> 历史口径：本 Run 的“默认批准 0”已由 Run 59 的分级自动接收策略替代。

### 触发原因

P0-05 已生成 461 条待人工复核候选。为防止程序替客户自动确认历史事实，本轮建立中文审批表、证据分组和严格审批校验，明确分离“程序可自动阻断”和“必须由泰昌资料管理人员确认”的范围。

### 验证结果

| 验证项 | 结果 |
| --- | --- |
| 全量分流 | PASS，896/896 全部进入人工复核或自动阻断/仅参考清单 |
| 人工复核 | 461 条，归并为 65 个完整报告/证据组 |
| 自动处理 | 270 条禁止新增、15 条禁止复用、148 条保留历史参考、2 条禁止独立入库 |
| 默认审批 | PASS，已批准 0、可执行增量入库 0 |
| 敏感/过期/参数门禁 | PASS，敏感和受限资料阻断，3 条过期证书延后补证，参数表保持结构化抽取 |
| 审批表完整性 | PASS，候选编号删除、增加或重复会阻断批准输出 |
| Excel 兼容性 | PASS，OpenPyXL 与 LibreOffice 转存回读均保持 4 个工作表和 461 条候选 |
| 重复执行 | PASS，忽略生成时间后主要 JSON 输出一致 |
| 定向及前序回归 | PASS，37 passed |

### 结论

P0-06 技术准备 PASS，业务审批 PENDING。当前未写数据库、未修改正式资产 metadata、RAG 召回或 DOCX 选图，因此不重复执行 Base+泰昌全量召回门禁、真实 stream 或正式 DOCX 导出。待泰昌资料管理人员填写审批表后，实际入库或 metadata 更新必须执行标准增量门禁、真实 `/api/knowledge/search/stream` 抽样；涉及配图时执行正式 DOCX XML 审计。

---

## Run 58 — 泰昌历史标书复用 P1-02 文件级证据包（2026-07-13）

> 总记录：`docs/rag/runs/run_20260713_taichang_p1_02_evidence_bundles_summary.md`

### 触发原因

P1-02 执行时 P0-06 尚未形成可入库候选，因此本轮只读复用现有已入库泰昌企业事实资产，建立报告/证书/审计/项目业绩的文件级证据包和完整页序，为后续章节证据映射与整包导出提供确定输入。P0-06 v2 后续自动接收的 169 条历史 Word 候选尚未完成媒体提取和入库，不追加入本轮证据包。

### 验证结果

| 验证项 | 结果 |
| --- | --- |
| 真实资产基线 | PASS，实时快照与冻结基线一致：资产 599、文档 77、分块 6347、产品参数 36、项目业绩证据 2 |
| 证据包 | PASS，16 个稳定业务对象、149 页 |
| 页序完整性 | PASS，16/16 完整，缺页 0、重页 0 |
| 重复载体治理 | PASS，21 个重复 PDF/关键页 JPG 仅作 rendition，不作为正式页源 |
| 结构化关联 | PASS，CPVC/MPP 分别关联 19/17 行参数，项目业绩关联合同和中标通知书 2 条结构化证据 |
| 时效/条件门禁 | PASS，过期职业健康安全证书阻断；设备/体系证书有效期、审计年度保留复核或条件选择 |
| 资料缺口 | PASS，资格预审结果无独立原件，不从历史 Word 推断或补造 |
| 来源边界 | PASS，P0-06 尚未提取/入库的 169 条候选、辽宁招标资料、河北豪乾参考稿均未进入 |
| 专项回归 | PASS，30 passed |
| 后端全量回归 | PASS，`PYTHONPATH=. .venv/bin/pytest -q` 为 400 passed、2 subtests passed；首次未设置 `PYTHONPATH` 的执行在收集阶段失败，已按正确项目环境重跑 |

### 结论

P1-02 完成。本轮只新增只读清单生成器、证据包 JSON/CSV/Markdown 和测试，没有写数据库，也没有修改 RAG 语料、metadata、召回策略、页面接口或 DOCX 选图/导出逻辑，因此不触发 Base+泰昌召回门禁、真实 stream 或正式 DOCX 导出。P1-01 可基于 P0-06 v2 的 169 条低风险候选继续媒体提取和 `knowledge_only` 入库；P1-03 可直接使用本轮证据包主键推进证书、设备、审计和人员等结构化台账。

---

## Run 59 — 泰昌历史标书复用 P0-06 分级自动接收与异常复核（2026-07-13）

> 总记录：`docs/rag/runs/run_20260713_taichang_p0_06_tiered_acceptance_summary.md`

### 触发原因

泰昌主动提供两份历史标书用于系统整理和复用，已经构成来源文件处理授权。Run 57 仍将 461 条候选全部等待人工批准，导致“批准 0、可入库 0”，不符合客户提供资料后应由系统主动整理的用户预期。本轮保留正式资产质量门禁，同时将低风险资料改为策略自动接收，仅让异常事实进入人工复核。

### 验证结果

| 验证项 | 结果 |
| --- | --- |
| 全量分流 | PASS，896/896 全覆盖 |
| 低风险自动接收 | PASS，169 条：绿色低碳 112、企业能力 35、生产制造能力 22 |
| 异常人工复核 | PASS，290 条，归并为 60 个证据组 |
| 自动关联/阻断/参考 | PASS，437 条；其中已有资产/同证据包关联 272 条 |
| 使用边界 | PASS，169 条全部为 `knowledge_only + allowed_for_bid=false + formal_bid_ready=false` |
| 高风险隔离 | PASS，证照、财务、人员、合同、业绩、报告、参数、时效和敏感资料未自动接收 |
| Excel 兼容性 | PASS，OpenPyXL 与 LibreOffice 转存回读均保持 5 个工作表、行数和 8 组下拉校验 |
| P0-02 至 P1-02 联合专项 | PASS，48 passed |
| 后端全量回归 | PASS，400 passed、2 subtests passed；11 个既有弃用告警 |

### 结论

P0-06 v2 分级策略 PASS。当前策略批准 169、可进入媒体提取和入库校验 169、人工批准 0；“可进入处理流程”不等于已写数据库，也不等于正式标书可用。本轮未改变数据库、RAG、metadata、召回或 DOCX 选图，因此不执行召回/真实 stream/DOCX 门禁。P1-01 实际提取和入库后必须执行 Base 30 + 泰昌专项 30 增量回归门禁与真实 stream；如提升为正式配图，再执行正式 DOCX XML 审计。

---

## Run 60 — 泰昌历史标书复用 P1-01 实际提取、严格去重与参数精度回归（2026-07-13）

> 总记录：`docs/rag/runs/run_20260713_taichang_p1_01_historical_bid_ingestion_summary.md`

### 触发原因

P0-06 已按客户来源授权自动接收 169 条低风险 Word 内嵌媒体，但这些候选仍需与真实系统资产重新比对、完成实际媒体提取和质量门禁后才能写库。同时客户特别要求技术标表格中的数值和单位不得误识别，因此本轮将图片资产入库与原生表格结构化抽取分开执行。

### 数据与入库结果

| 验证项 | 结果 |
| --- | --- |
| 来源冻结 | PASS，技术/商务 Word SHA-256 分别为 `2dd987a9...d80d`、`62423abd...9135` |
| 实际媒体提取 | PASS，169/169 |
| 真实库严格去重 | PASS，133 新增；5 同证据、2 视觉重复、24 视觉疑似、5 低质量未入库 |
| 数据库写入 | PASS，真实资产 599 → 732，本批 133 条、embedding 133/133 |
| 幂等性 | PASS，第二次执行新增 0，133 条识别为已入库 |
| 正式使用边界 | PASS，本批 `allowed_for_bid/formal_bid_ready/parameter_fact_allowed` 均为 0，全部排除 DOCX |
| 中文展示 | PASS，用户可见内部枚举命中 0 |

### 表格和参数精度

| 验证项 | 结果 |
| --- | --- |
| 原生表格 | 技术 10、商务 4，主解析器为 Word OOXML，未调用 MinerU/OCR |
| 技术候选 | 20 行，全部待核验且不写参数事实层 |
| 单位 | `DN`、`φ` 原样保留，未换算 `mm`；数量“以实际数量为准”不转数字 |
| 报告关联 | 1712/1713 只关联现有原始报告；N-HAP/UPVC 历史报告号等待原件 |
| 敏感/时效 | 人员、企业信息、股东、财务表均 restricted；职业健康安全证书已过期阻断 |

### 真实链路缺陷与修复

首次真实 stream 发现 CPVC“平均内径+壁厚”复合查询被“承口平均内径 280.5 mm”抢占。修复后，明确产品族执行硬过滤；未提“承口”时禁止承口参数替代管体参数；同报告多个参数在来源去重时合并正文。最终真实 stream 正确返回 CPVC `250.2~250.4 mm`、`15.2~15.3 mm` 和报告 `2024100312005501713`，且不含 `280.5` 或 MPP 报告号；MPP 环刚度正确返回 `66.40 kN/m²` 和报告 `2024100312005501712`。

### 最终回归

| 测试集 | 模式 | Recall@5 | Top1 | MRR | 禁用关键词 | 跨角色串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100% | 0.944 | 0% | 0% |
| Base | qwen3-rerank | 96.7% | 100% | 0.944 | 0% | 0% |
| 泰昌专项 | off | 93.3% | 100% | 0.917 | 3.3% | 0% |
| 泰昌专项 | qwen3-rerank | 100% | 100% | 0.973 | 0% | 0% |

- 标准增量门禁：PASS。
- 真实 `/api/knowledge/search/stream`：PASS。
- 后端全量：413 passed、2 subtests passed、11 个既有弃用告警。

### 结论

P1-01 完成。本批全部是 `knowledge_only` 历史 Word 载体，不覆盖现有 36 行原始检验报告参数，不参与正式 DOCX 选图，因此本轮不执行正式 DOCX XML 审计。剩余 290 条异常候选继续按 P0-06 证据组人工复核。

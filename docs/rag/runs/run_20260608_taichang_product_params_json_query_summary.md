# Run 17：泰昌产品参数 JSON 查询接入真实问答链路

> 日期：2026-06-08  
> Base filtered：`docs/rag/runs/run_20260608_taichang_product_params_json_query_base_filtered.json`  
> Customer filtered：`docs/rag/runs/run_20260608_taichang_product_params_json_query_customer_filtered.json`  
> 非流式 API 结果：`docs/rag/runs/run_20260608_taichang_product_params_real_api_after_json.json`  
> 页面同源 Stream 结果：`docs/rag/runs/run_20260608_taichang_product_params_real_stream_after_json.json`

## 背景

Run 16 真实链路测试发现：知识库问答能召回泰昌检验报告图片和基础信息，但没有接入 P4-5 产出的 `taichang_product_parameter_rows.json`，导致无法回答环刚度、平均内径、壁厚等具体结构化参数。

本轮不新增数据库表，先把 staging JSON 作为真实查询层接入后端问答链路。

## 处理内容

- 新增 `backend/rag/product_parameters.py`：
  - 读取 `taichang_product_parameter_rows.json`；
  - 支持按泰昌、CPVC/MPP、内径、参数名匹配；
  - 生成 `structured_product_parameter_json` 高优先级 RAG context；
  - 每次查询直接读取 JSON，避免客户后续重新抽取资料后被长期缓存卡住。
- 更新 `backend/api/knowledge.py`：
  - `/api/knowledge/search` 接入结构化参数 context；
  - `/api/knowledge/search/stream` 接入结构化参数 context；
  - 仍保留泰昌企业事实过滤和图片资产召回。
- 新增 `tests/test_taichang_product_parameter_query.py`，基于真实 JSON 验证：
  - MPP 环刚度命中 `66.40`；
  - CPVC 平均内径命中 `250.2~250.4`；
  - CPVC 壁厚命中 `15.2~15.3`；
  - 辽宁仅作为 QA/异常校验参照，不构成覆盖义务。

## 真实链路验证

| 问题 | `/api/knowledge/search` | `/api/knowledge/search/stream` |
| --- | --- | --- |
| 泰昌 MPP 内径250 环刚度 | 返回 `66.40 kN/m2`、报告编号 `2024100312005501712` | 返回 `66.40 kN/m2`、报告编号 `2024100312005501712` |
| 泰昌 CPVC 内径250 平均内径/壁厚 | 返回 `250.2~250.4`、`15.2~15.3`、报告编号 `2024100312005501713` | 返回 `250.2~250.4`、`15.2~15.3`、报告编号 `2024100312005501713` |
| 两份内径250报告是否覆盖辽宁全部规格 | 明确回答不能覆盖辽宁全部规格 | 明确回答不能覆盖辽宁全部规格 |

## 回归验证

- `.venv/bin/python -m pytest tests/test_taichang_product_parameter_query.py tests/test_taichang_product_parameter_extraction.py tests/test_rag_retrieval.py tests/test_customer_metadata_policy.py -q`
  - 结果：22 passed，1 个 PyPDF2 deprecation warning。
- `.venv/bin/python -m pytest tests/test_taichang_product_parameter_query.py tests/test_rag_retrieval.py -q`
  - 结果：14 passed，1 个 PyPDF2 deprecation warning。
- `.venv/bin/python -m py_compile backend/rag/product_parameters.py backend/api/knowledge.py`
  - 结果：通过。

| 测试集 | Recall@5 | top1 来源准确率 | 关键词命中率 | 跨 doc_role 串扰 | 禁用关键词命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base filtered | 96.7% | 100.0% | 96.7% | 0.0% | - |
| 泰昌 MVP 专项 filtered | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

## 结论

P4-6 已完成：真实 API 和页面同源 stream 问答均可基于泰昌产品参数 JSON 回答具体参数值，同时保持辽宁资料边界，不输出覆盖辽宁全部规格的错误结论。

## 后续建议

当前 JSON 查询层可以支撑近期客户持续补资料后的快速验证。等产品参数继续增加到多规格、多批次、多报告后，再评估新增 `power_grid_product_parameter_rows` 数据库表。

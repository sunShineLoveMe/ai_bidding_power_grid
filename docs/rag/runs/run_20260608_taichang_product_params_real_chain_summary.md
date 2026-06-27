# Run 16：泰昌产品参数真实 API / 页面同源链路专项测试

> 日期：2026-06-08  
> API 结果：`docs/rag/runs/run_20260608_taichang_product_params_real_api.json`  
> Stream 结果：`docs/rag/runs/run_20260608_taichang_product_params_real_stream.json`

## 测试范围

- 后端健康检查：`GET http://127.0.0.1:3012/api/health`
- 前端开发服务：`http://127.0.0.1:5173`
- 前端代理健康检查：`GET http://127.0.0.1:5173/api/health`
- 真实登录链路：`POST /api/users/register`
- 真实知识库问答 API：`POST /api/knowledge/search`
- 页面同源流式问答接口：`POST /api/knowledge/search/stream`

本轮不使用 mock。页面组件 `KnowledgeSearchDrawer` 调用的就是 `/api/knowledge/search/stream`，本轮通过前端 Vite 代理 `127.0.0.1:5173/api/knowledge/search/stream` 进行同源链路复验。

## 测试问题

1. 泰昌MPP电缆保护管内径250的环刚度检验结果是多少？请说明报告编号和资料来源。
2. 泰昌CPVC电缆保护管内径250的平均内径和壁厚检验结果是多少？请说明报告编号和资料来源。
3. 泰昌这两份内径250检验报告是否能说明覆盖辽宁所有CPVC和MPP规格需求？请说明边界。

## 结果

| 链路 | 结果 |
| --- | --- |
| 后端健康检查 | 通过，`status=ok` |
| 前端代理健康检查 | 通过，`status=ok` |
| 真实注册/登录 | 通过，获取真实 session token |
| `/api/knowledge/search` 非流式问答 | 可生成回答，但精确参数值未答出 |
| `/api/knowledge/search/stream` 页面同源问答 | 可完成流式回答，无 error 事件，但精确参数值未答出 |
| 辽宁覆盖边界问题 | 通过，回答明确不能直接说明覆盖辽宁所有规格 |

## 关键发现

当前知识库问答链路没有接入 `taichang_product_parameter_rows.json` 这类结构化参数。问 MPP 环刚度、CPVC 平均内径/壁厚时，系统主要召回图片资产和报告基础信息，未召回结构化参数行，因此回答会保守表述为“文本未提取出具体数值”。

这说明 P4-5 已完成“参数抽取”，但真实 API / 页面问答还未完成“参数查询接入”。

## 结论

- 边界控制有效：系统没有把两份内径250检验报告错误说成覆盖辽宁所有规格。
- 精确参数问答未达标：真实链路还不能稳定回答 `环刚度=66.40`、`CPVC平均内径=250.2~250.4`、`CPVC壁厚=15.2~15.3` 等结构化结果。

## 后续任务

进入 P4-6：泰昌产品参数真实查询接入。建议先不新增数据库表，先在后端知识库问答链路中接入 staging JSON 查询层：

- 当问题命中泰昌 + CPVC/MPP + 规格/参数名时，先查 `taichang_product_parameter_rows.json`；
- 将命中的结构化参数作为高优先级 context 注入回答；
- sources 中返回报告编号、规格型号、参数名、标准要求、检验结果、原始 PDF；
- 继续保留辽宁仅作 QA/异常校验参照，不作为覆盖义务。

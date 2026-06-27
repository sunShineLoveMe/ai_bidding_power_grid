# 产品库/资信库上传入口收口与检索索引回归

- 日期：2026-06-26
- 范围：企业产品库、企业资信库、知识资产上传 API、知识资产召回
- 结论：PASS

## 触发背景

客户在企业产品库页面看到多个上传/新增入口，无法判断“新增产品”“上传产品资料”“新增产品资料”的区别。同时客户仍有大量产品资料未提供，需要上传后的产品图片、资料说明、规格型号和标签能进入知识问答、技术标正文和标书配图索引。

## 改动摘要

1. 产品库入口收口为一个主按钮：`上传/新增产品资料`。
2. 资信库入口收口为一个主按钮：`上传/新增资信资料`。
3. 产品库补齐合同口径多品类中文分类：电缆与附件、开关柜与成套设备、变压器与箱变、互感器、继电保护与自动化、通信与调度设备等。
4. 空分类不展示伪事实，提示上传客户真实资料后使用。
5. 上传资产默认补充泰昌企业事实 metadata：`enterprise=泰昌`、`source_domain=enterprise_fact`、`target_library=product_library/qualification_library`、`tenant_visibility=taichang_only` 等。
6. 知识资产召回增加精确标题/规格/长词关键词补召回，避免新上传资产被旧高相似资产压住。

## 真实流程验证

### 浏览器上传

- 登录账号：`admin`
- 页面：`http://localhost:5173/products`
- 上传文件：`/tmp/codex-taichang-cpvc-test-product.png`
- 资料名称：`泰昌CPVC电缆保护管模拟产品图片-20260626070309`
- 分类：`电缆与附件`
- 规格型号：`CPVC-DN250-真实回归`
- 标签：`CPVC`、`电缆保护管`、`真实回归`
- 结果：页面提示 `产品资料已保存并接入检索`

### 资产落库

- 产品资产总数：409
- 新增资产 ID：`17e53f70-649b-4a0c-8716-dfc5a502ed02`
- 资产类型：`product_image`
- 分类：`电缆与附件`
- metadata 校验：
  - `enterprise=泰昌`
  - `doc_owner=河北泰昌电力器材科技有限公司`
  - `source_domain=enterprise_fact`
  - `target_library=product_library`
  - `target_library_label=产品库资料`
  - `tenant_visibility=taichang_only`
  - `access_scope=taichang_tenant_internal`

### 知识问答 stream

- 接口：`POST /api/knowledge/search/stream`
- 查询：`查询泰昌CPVC电缆保护管模拟产品图片-20260626070309的产品资料、规格型号和适用章节`
- 结果：PASS
- 验证点：
  - stream 返回 `done`
  - `raw_contexts` 命中新增资产 `17e53f70-649b-4a0c-8716-dfc5a502ed02`
  - 返回内容包含新增标题和 `CPVC-DN250-真实回归`

### 页面入口

| 页面 | 新统一入口 | 旧重复入口 |
| --- | ---: | ---: |
| 产品库 | 1 | 0 |
| 资信库 | 1 | 0 |

## 自动化回归

| 命令 | 结果 |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_rag_retrieval.py -q` | PASS，32 passed |
| `cd frontend && npm run build` | PASS，仅保留既有 chunk size / dynamic import 警告 |
| `set -a; source .env; set +a; .venv/bin/python scripts/rag/run_local_rag_gate.py --run-id run_20260626_product_qualification_upload_index_regression` | PASS |

RAG 门禁产物：

- `docs/rag/runs/run_20260626_product_qualification_upload_index_regression_summary.md`
- `docs/rag/runs/run_20260626_product_qualification_upload_index_regression_incremental_summary.md`
- `docs/rag/runs/run_20260626_product_qualification_upload_index_regression_stream.jsonl`

## 剩余说明

- 本次真实库中保留了 2 条模拟 CPVC 产品图测试资产，其中最新有效回归资产为 `17e53f70-649b-4a0c-8716-dfc5a502ed02`。
- 第一条历史测试资产是在 metadata 修复前创建，后续可作为清理项，不影响新链路验收结论。

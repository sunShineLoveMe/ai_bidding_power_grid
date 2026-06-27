# run_20260627_upload_entry_formal_asset_regression - 上传入口正式资产回归

- 日期：2026-06-27
- 状态：PASS
- 范围：产品库/资信库上传入口新资产正式中文展示、metadata、RAG 召回和用户侧字段清洗
- 门禁：`docs/rag/runs/run_20260627_upload_entry_formal_asset_gate_summary.md`

## 修复内容

- 上传/更新资产入库前统一推断 `evidence_type`，并生成正式中文 `title/category/tags/description/source_display_name/formal_caption`。
- `searchable_text` 不再拼接 `product_image`、`technical`、`production_capacity` 等内部枚举，卷册字段改为“技术标/资格文件/商务标”等中文词。
- 用户侧资产返回中的 `product_image/qualification_image` 映射为“产品图片/资信图片”，避免 SSE 或页面链路暴露内部枚举。

## 真实链路验证

| 验证项 | 结果 |
| --- | --- |
| 登录 | PASS，`POST /api/users/login` 使用 `admin` 登录成功 |
| 上传 | PASS，`POST /api/knowledge/assets/upload` 上传测试图 `泰昌MPP生产线_页面_9原图.png` |
| 上传返回 | PASS，标题为 `泰昌MPP生产线资料`，分类为 `生产制造能力`，标签为 `泰昌 / 生产制造能力` |
| metadata | PASS，包含 `source_display_name=泰昌MPP生产线资料`、`evidence_type_label=生产制造能力`、`target_library_label=产品库资料`、`formal_caption=资料：MPP生产线资料` |
| 列表/详情 | PASS，`GET /api/knowledge/assets/<asset_id>` 和分页列表禁用字段命中 0 |
| 流式问答 | PASS，`POST /api/knowledge/search/stream` 召回 4 条资料、4 个图片资产、4 张图片，新上传资产被召回 |
| SSE/回答清洗 | PASS，答案正文和去除允许图片 URL 后的 SSE 中 `页面_`、`原图`、`taichang`、`production_capacity`、`technical`、`product_image`、`parsed_outputs`、`rag_seed` 命中均为 0 |
| 测试资产清理 | PASS，测试资产 `b522d9fb-5011-43e7-840f-f9b85710b14e` 已从数据库删除，详情接口返回“知识资产不存在” |

> 本轮测试图片为 1x1 回归样张，仅用于验证上传入口；已删除 DB 记录，避免进入正式产品库、RAG 或标书选图。本地对象存储没有 remove 接口，遗留孤立文件无 DB 索引，不参与业务链路。

## 自动化测试

```text
.venv/bin/python -m pytest tests/test_knowledge_asset_upload_payload.py tests/test_rag_display_names.py tests/test_rag_retrieval.py -q
40 passed, 1 warning
```

```text
python3 -m py_compile backend/api/assets.py backend/rag/display_names.py
PASS
```

## 增量门禁

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 90.0% | 100.0% | 0.867 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 0.973 | 0.0% | 0.0% |

## 结论

P1-5 上传入口新资产规则回归通过。后续客户从产品库/资信库上传新图片或附件时，新资产默认以正式中文标题、中文分类、中文标签和正式 caption 入库，不再把解析痕迹、英文枚举或内部追溯名带入用户侧问答和正式标书链路。

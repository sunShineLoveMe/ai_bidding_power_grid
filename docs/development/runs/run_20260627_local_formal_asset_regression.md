# 泰昌正式资产治理本地真实回归

> Run：`run_20260627_local_formal_asset_regression`
> 日期：2026-06-27
> 环境：本地服务，后端 `http://127.0.0.1:3012`，前端 `http://127.0.0.1:5173`
> 登录账号：`admin`

## 验证范围

本轮用于确认泰昌本地数据资产修复后，正式展示字段、RAG 问答、页面展示和 DOCX 导出是否仍会暴露内部解析信息、页码型题注、英文枚举或不适合正式投标的图片说明。

## 资产审计

命令：

```bash
set -a; source .env; set +a
.venv/bin/python scripts/rag/audit_taichang_formal_assets.py --run-id run_20260627_local_formal_asset_regression_audit
```

结果：

| 范围 | 扫描数 | 问题数 |
| --- | ---: | ---: |
| 真实图片资产 | 599 | 0 |
| 知识文档 | 77 | 0 |
| 文档分块 | 6347 | 0 |
| staging 图片 payload | 539 | 539 |

staging 图片 payload 是历史解析中间产物，仍不作为正式展示、RAG 问答或 DOCX 配图来源。

## 真实 API Stream

接口：`POST /api/knowledge/search/stream`，使用真实登录 token。

| 用例 | HTTP | 耗时 | 禁用字段命中 |
| --- | ---: | ---: | --- |
| CPVC 检验报告参数 | 200 | 17540 ms | 0 |
| MPP 检验报告 | 200 | 12886 ms | 0 |
| 生产制造能力 | 200 | 8801 ms | 0 |
| 试验检测设备 | 200 | 12800 ms | 0 |
| 资质证书 | 200 | 7056 ms | 0 |
| 绿色低碳资料 | 200 | 12025 ms | 0 |

禁用字段包含：`图示：`、`原图`、`页面_`、`asset_path`、`parsed_outputs`、`source_domain`、`target_library`、`embedding`、`searchable_text`、`file_name`、`specs`、`taichang_`、`product_library`、`qualification_library`。

记录：`docs/rag/runs/run_20260627_local_formal_asset_stream_regression.json`。

## 浏览器页面

使用 Chrome/Playwright 打开真实前端，登录后访问 `/knowledge`。

| 页面 | 结果 |
| --- | --- |
| 企业知识库列表 | 页面文本禁用字段命中 0 |
| 知识库助手 CPVC 参数问答 | 页面渲染后禁用字段命中 0 |

截图：

- `docs/development/runs/run_20260627_local_browser_knowledge_page.png`
- `docs/development/runs/run_20260627_local_browser_knowledge_assistant_cpvc.png`

## DOCX 真实导出

链路：

```text
build_project_bid_markdown(volume_type=technical/business, with_images=true)
-> convert_md_to_word(return_report=true)
-> refresh_docx_fields_with_soffice
-> DOCX XML audit
```

| 分册 | 选中图片 | 字段刷新 | 禁用表达命中 | 页码型题注命中 | 格式/正式告警 |
| --- | ---: | --- | ---: | ---: | ---: |
| 技术标 | 16 | refreshed | 0 | 0 | 2 |
| 商务标 | 5 | refreshed | 0 | 0 | 2 |

记录：`docs/development/runs/run_20260627_local_formal_docx_regression/summary.json`。

## 自动化测试

```bash
.venv/bin/python -m pytest tests/test_rag_asset_scoring.py tests/test_docx_export.py::DocxExportRegressionTest::test_formal_image_caption_is_sanitized_centered_and_small -q
```

结果：`12 passed, 1 warning`。

## 增量门禁

命令：

```bash
set -a; source .env; set +a
.venv/bin/python scripts/rag/run_incremental_regression_gate.py --run-id run_20260627_local_formal_asset_regression_gate
```

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 50.0% | 63.3% | 0.500 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 53.3% | 63.3% | 0.533 | 0.0% | 0.0% |

门禁状态：FAIL。Base 未退化；泰昌专项失败仍是旧评测集与本轮治理目标不一致导致，旧用例要求召回已被隔离的资产索引/解析中间 chunk。下一步需要更新泰昌专项评测集，改为检验正式资产、中文来源、结构化参数和页面同源回答。

## 结论

本地正式资产治理回归通过：真实资产、RAG stream、浏览器页面和 DOCX 导出均未再暴露内部解析字段、旧式图片题注或页码型追溯说明。

## 待处理项

- P0：推送阿里云测试环境后执行同等资产修复脚本、真实 stream、真实浏览器页面和 DOCX 导出复验。
- P1：更新泰昌专项评测集，移除对内部资产索引/解析中间 chunk 的正向召回期待。
- P1：试验检测设备问答中仍可能引用碳足迹报告里的设备描述，来源精度可继续收敛，但不影响本轮“内部字段/正式题注清零”的验收结论。

# Run 20260626 — 阿里云企业库展示与来源收敛本地收口

## 结论

- 本轮未新增客户资料，未执行入库，未批量修改数据库 metadata。
- 本地代码已关闭 P1C-15 的两个问答/来源缺陷：
  - 资质证书问题只返回质量管理体系、环境管理体系、职业健康安全管理体系认证证书来源，不再用 ESG、绿色发展规划或废水废气废固报告补位。
  - CPVC 检验报告回答按产品族、规格型号和报告编号限定覆盖范围，不再给出“无需补充其他规格”或“覆盖全部 CPVC 规格”的泛化结论。
- 公网 80 入口已完成 compose 可配置和部署文档收口：`FRONTEND_HTTP_PORT=80` 可切换到 `80 -> 80`；当前云上只读检查显示 `:8080` 可用，`80` 仍返回 `Empty reply from server`，需发布后复测。

## 代码与配置变更

| 范围 | 处理 |
| --- | --- |
| 企业知识库来源后处理 | `backend/api/knowledge.py` 对资质证书查询启用严格证书来源集合；绿色/ESG/废水类资料即使 metadata 错标为 `certification` 也不进入证书参考来源 |
| RAG 回答约束 | `backend/rag/retrieval.py` 增加检验报告规格覆盖约束、证书有效性表述约束，禁止模型把“已命中证书资料”扩展为“有效/合格有效/在有效期内” |
| 端口入口 | `docker-compose.yml` 前端端口改为 `${FRONTEND_HTTP_PORT:-8080}:80`，默认兼容测试入口，云上可通过 `.env` 切 80 |
| 部署文档 | 更新阿里云部署清单和开发运维手册，明确 80/8080 入口口径、切换命令和验证命令 |

## 自动化与真实链路

| 验证项 | 结果 | 记录 |
| --- | --- | --- |
| 定向单元测试 | PASS，`38 passed` | `tests/test_rag_retrieval.py tests/test_rag_display_names.py tests/test_rag_asset_scoring.py` |
| Python 编译检查 | PASS | `backend/api/knowledge.py`、`backend/rag/retrieval.py` |
| Compose 默认端口 | PASS | 默认 `8080 -> 80` |
| Compose 80 端口配置 | PASS | `FRONTEND_HTTP_PORT=80` 后为 `80 -> 80` |
| 本地 RAG 完整门禁 | PASS | `docs/rag/runs/run_20260626_aliyun_enterprise_source_convergence_final_summary.md` |
| 资质证书真实 stream | PASS，contexts=3、assets=6 | `docs/rag/runs/run_20260626_aliyun_enterprise_source_convergence_final_stream.jsonl` |
| CPVC 检验报告真实 stream | PASS，contexts=5、assets=6 | `docs/rag/runs/run_20260626_aliyun_enterprise_source_convergence_cpvc_stream_final_summary.md` |
| 云上只读健康检查 | PARTIAL | `http://8.160.187.226:8080/api/health` 返回 200；`http://8.160.187.226/api/health` 仍为 `Empty reply from server` |

## 增量回归指标

| 测试集 | 模式 | Recall@5 | Top1 来源准确率 | MRR | 禁用关键词命中率 | 跨 doc_role 串扰 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Base | off | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| Base | qwen3-rerank | 96.7% | 100.0% | 0.944 | 0.0% | 0.0% |
| 泰昌专项 | off | 96.7% | 100.0% | 0.967 | 3.3% | 0.0% |
| 泰昌专项 | qwen3-rerank | 100.0% | 100.0% | 1.000 | 0.0% | 0.0% |

门禁口径以 qwen3-rerank 为泰昌专项正式口径，PASS。

## 待云上发布复测

发布到阿里云 ECS 后需复测：

1. `泰昌有哪些资质证书？`：参考来源只包含三体系认证证书，不混入 ESG、绿色发展规划、废水废气废固报告。
2. `泰昌 CPVC 电缆保护管有哪些检验报告？`：回答只确认内径250/`DS 250×15×6000 SN16 PVC-C` 报告，不泛化到全部 CPVC 规格。
3. 公网入口：若 `.env` 设置 `FRONTEND_HTTP_PORT=80`，`http://8.160.187.226/` 和 `/api/health` 均应返回正常。

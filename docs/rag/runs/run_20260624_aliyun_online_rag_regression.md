# Run 20260624 — 阿里云企业知识库线上真实回归

> 时间：2026-06-24
> 环境：`http://8.160.187.226:8080`
> 验证方式：Chrome 登录态真实页面，企业知识库助手三问；补充 HTTP 健康检查。

## 环境检查

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| `http://8.160.187.226:8080/` | PASS | 前端页面可打开，Chrome 已登录 `admin` |
| `GET /api/health` | PASS | 返回 `{"status":"ok"}` |
| `POST /api/bidding/knowledge/search/stream` 未登录 | PASS | 返回 401 `请先登录后再访问。`，符合登录保护预期 |
| `http://8.160.187.226/` | FAIL | 80 端口连接成功但返回 `Empty reply from server`，公网正式入口仍需 Nginx/安全组收口 |

## 数据修复前置结果

阿里云数据库经用户侧执行修复后，当前知识资产 embedding 已补齐：

| source_batch_id | total | with_embedding | missing_embedding |
| --- | ---: | ---: | ---: |
| `customer_liaoning_taichang_20260606_p0_formal_full_page_assets_v1` | 300 | 300 | 0 |
| `customer_taichang_supplement_20260611` | 296 | 296 | 0 |

本轮同时确认 `scripts/rag/backfill_knowledge_asset_embeddings.py` 原默认 `--batch-size=20` 与 DashScope embedding 接口最大 10 条限制不兼容，已将默认值调整为 10，避免阿里云环境再次批量失败。

## 三问真实页面回归

| 问题 | 结果 | 关键观察 |
| --- | --- | --- |
| 泰昌有哪些资质证书？ | PASS with P1 defects | 主答案正确返回质量管理体系、环境管理体系、职业健康安全管理体系三项认证；图片均为整页证书，不再出现二维码/局部裁剪图。参考来源第 4/5 条仍混入 ESG、废水废气废固报告，属于来源收敛噪声。 |
| 泰昌有哪些企业证明材料？ | PASS | 主答案正确返回营业执照、三体系认证、社保证明、土地租赁协议和土地使用证明；图片为原图/整页。人员/社保证明归库修复后，参考来源“泰昌社保证明”已展示为“人员证书 · 资信库资料”。 |
| 泰昌 CPVC 电缆保护管有哪些检验报告？ | PASS with P1 wording defect | 正确返回 CPVC 电缆保护管检验报告、规格 `DS 250×15×6000 SN16 PVC-C`、报告编号 `2024100312005501713`，并显示整页检验报告图片。回答中“无需额外补充其他规格的检验报告”与后文“当前资料仅覆盖内径250”存在措辞冲突，应改为“本问题仅需内径250时无需补充；其他规格需补充对应报告”。 |

## 缺陷清单

| 编号 | 优先级 | 缺陷 | 影响 | 建议处理 |
| --- | --- | --- | --- | --- |
| ALI-RAG-002 | P1 | 资质证书问题参考来源混入 ESG、废水废气废固报告 | 主答案正确，但来源解释不够干净，客户可能误以为宣传/环保报告也是证书依据 | 对 certification 问题增加来源后处理：参考来源优先只保留 `evidence_type=certification` 或证书原件，其他资料只在“补充说明”中展示 |
| ALI-RAG-003 | P1 | CPVC 报告回答存在“无需补充其他规格”与“仅覆盖内径250”的措辞冲突 | 可能误导客户认为所有 CPVC 规格都已覆盖 | 修改产品检验报告类回答约束：报告覆盖范围必须跟规格绑定，禁止给出泛化覆盖结论 |
| ALI-RAG-004 | P1 | 公网 80 端口返回 `Empty reply from server`，实际可用入口为 8080 | 客户访问默认 IP 不稳定，正式演示需要明确 URL 或修 Nginx | 将 80 端口反代到前端，或明确只开放 `:8080` 测试入口并更新部署文档 |

## 修复后复测

阿里云已执行：

```bash
docker compose exec -T backend python scripts/rag/repair_enterprise_asset_library_display.py \
  --execute \
  --save docs/rag/runs/run_20260624_aliyun_enterprise_asset_display_repair_execute.json
```

执行结果：

| 指标 | 数量 |
| --- | ---: |
| assets_scanned | 596 |
| assets_updated | 18 |
| personnel_assets_moved | 18 |

Chrome 真实页面复测“泰昌有哪些企业证明材料？”通过：参考来源“泰昌社保证明”已从“试验检测能力 · 产品库资料”改为“人员证书 · 资信库资料”，来源说明为“河北泰昌电力器材科技有限公司人员证书及社保证明资料，来源于客户已提供文件《泰昌社保证明.pdf》第1页。”因此 ALI-RAG-001 已关闭。

## 结论

阿里云企业知识库核心 RAG 链路已经恢复：正式整页图片资产可召回，embedding 补齐，三问主答案均可用，原先二维码/局部裁剪图问题已消失。

云上 P0 已关闭，可以进入最小标书主流程云上冒烟。ALI-RAG-002 和 ALI-RAG-003 作为下一轮来源精度和回答约束优化；ALI-RAG-004 作为部署入口问题处理。

# 2026-06-26 DOCX 页码与图片题注真实复验

## 背景

用户反馈目录右侧页码和页脚页码偏大，图片下方题注不合规，且要求实事求是评估泰昌产品资料是否支撑技术标。

## 真实链路

- 项目：`a1d853bc-ca4e-43b4-bbea-256f561c8a3d`
- 链路：`build_project_bid_markdown(volume_type, with_images=true) -> convert_md_to_word(return_report=true) -> refresh_docx_fields_with_soffice -> LibreOffice PDF -> DOCX XML audit`
- 范围：技术标、商务标均重新导出、刷新字段、转换 PDF，并直接审计最终 DOCX XML。

## 修正项

- 目录页码字段结果独立设置为 `9pt`，并在 LibreOffice 字段刷新后再次归一化 PAGEREF 字段结果字号。
- 页脚 PAGE/NUMPAGES 字段刷新后统一归一化为 `9pt`。
- 图片题注识别 `图示/图片/资料/图X-X` 前缀，统一清洗为 `资料：...`，居中、9pt，不展示检索参数、资料编号、原图/脱敏示意图或内部来源字段。

## 审计结果

| 检查项 | 技术标 | 商务标 |
| --- | --- | --- |
| 模板 | `technical_bid_standard` | `business_bid_standard` |
| 字段刷新 | `refreshed` | `refreshed` |
| 目录页码最大字号 | `9.0` | `9.0` |
| 页脚最大字号 | `9.0` | `9.0` |
| 题注数 | `27` | `18` |
| 不合规题注 | `0` | `0` |

## 输出文件

- 技术标 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.docx`
- 技术标 PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-技术标-图文.pdf`
- 商务标 DOCX：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.docx`
- 商务标 PDF：`outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司-商务标-图文.pdf`

## 图片题注样例

### 技术标
- `资料：CPVC电缆保护管检验报告第3页`，alignment=CENTER (1)，font=[9.0, 9.0, 9.0, 9.0, 9.0]
- `资料：MPP电缆保护管检验报告第5页`，alignment=CENTER (1)，font=[9.0, 9.0, 9.0, 9.0, 9.0]
- `资料：MPP电缆保护管检验报告第2页`，alignment=CENTER (1)，font=[9.0, 9.0, 9.0, 9.0, 9.0]
- `资料：CPVC电缆保护管检验报告首页`，alignment=CENTER (1)，font=[9.0, 9.0, 9.0]
- `资料：CPVC电缆保护管检验报告第4页`，alignment=CENTER (1)，font=[9.0, 9.0, 9.0, 9.0, 9.0]
- `资料：CPVC电缆保护管检验报告第2页`，alignment=CENTER (1)，font=[9.0, 9.0, 9.0, 9.0, 9.0]

### 商务标
- `资料：绿色电力认证证书首页`，alignment=CENTER (1)，font=[9.0]
- `资料：职业健康安全管理体系认证证书第3页`，alignment=CENTER (1)，font=[9.0, 9.0, 9.0]
- `资料：身份证明文件`，alignment=CENTER (1)，font=[9.0]
- `资料：职业健康安全管理体系认证证书第2页`，alignment=CENTER (1)，font=[9.0, 9.0, 9.0]
- `资料：职业健康安全管理体系认证证书首页`，alignment=CENTER (1)，font=[9.0]
- `资料：质量管理体系认证证书第2页`，alignment=CENTER (1)，font=[9.0, 9.0, 9.0]

## 泰昌产品资料支撑度评估

- 结论：泰昌现有资料能支撑电缆保护管 CPVC/MPP 的基础技术响应和资质证明，但产品维度仍偏薄；若投标对象是10kV架空绝缘导线，则企业事实资料明显不匹配，不能用现有泰昌电缆保护管资料硬撑导线技术标。
- 现有资料更偏向 CPVC/MPP 电缆保护管、检验报告、资质证书、项目业绩和体系证明；能支撑基础版电缆保护管技术响应，但不足以形成强技术标。
- 如果目标为 10kV 架空绝缘导线，当前泰昌资料不充分且产品事实口径不匹配，应要求客户补充导线产品资料，不能用电缆保护管材料硬套。

需补充资料：
- 目标产品完整样本/产品手册/技术参数表
- 覆盖各规格型号的型式试验或检验报告
- 生产线、关键设备、检测设备清单和实拍资料
- 原材料供应与进厂检验制度、过程检验记录样例
- 同类产品供货业绩、中标通知书、合同和验收证明
- 质量控制、售后服务、包装运输和交付能力资料

## 结论

- 本轮状态：`PASS`
- 页码字号、页脚字号、图片题注清洗与居中均通过真实导出复验。

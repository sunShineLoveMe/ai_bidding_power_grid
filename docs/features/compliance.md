# 合规检查与语义复核

> 相关代码：`backend/ai/compliance_checker.py`、`backend/ai/semantic_compliance.py`

## 合规检查

招标项目页提供第一版合规覆盖检查，用于在生成章节大纲后快速判断投标文件是否承接了关键条款。

当前检查范围：

| 检查对象 | 核查逻辑 | 输出 |
| --- | --- | --- |
| 要求条款 | 将 `bid_requirements` 与 `bid_sections.mapped_requirements`、章节标题、章节正文做匹配 | 已覆盖 / 未覆盖 |
| 评分项 | 将 `bid_scoring_items` 与 `bid_sections.mapped_scoring_items`、章节内容做匹配 | 已覆盖 / 待补强 |
| 风险项 | 将 `bid_risks` 与 `bid_sections.mapped_risks`、章节内容做匹配 | 已覆盖 / 未覆盖 |

后端已提供统一接口：

```text
GET /api/bidding/interpretations/{project_id}/compliance-check
```

返回内容包括总检查项、已覆盖项、待补强项、待覆盖项、高风险待覆盖数量、分册摘要、明细列表和处理建议。该指标在界面中命名为"条款覆盖率"，仅用于追踪招标条款、评分项、风险项是否被当前章节正文承接；投标信息确认页字段不计入该指标，也不等同于最终 Word 标书合规结论。接口支持 `volumeType=technical|business|qualification|price|attachment`；`business` 保持商务包兼容口径，会覆盖商务、资格、报价、附件和其他非技术章节。标书工作台右侧实时质量仪表盘会展示当前范围条款覆盖率，并列出技术标、商务响应、资格文件、报价文件和附件材料的分册摘要。若下载前仍存在待覆盖或高风险待覆盖项，会先按当前下载范围弹窗提示风险，再由用户决定继续下载或返回补强。

工作台还提供"语义复核"入口，对高风险项、评分项、未覆盖项和待补强项执行 LLM 语义合规复核。语义复核会输出 `已覆盖 / 部分覆盖 / 未覆盖`、正文证据摘录、置信度、评分权重或风险等级、补强建议和建议章节。为控制成本，默认不全量复核所有条款；模型调用失败时会使用规则兜底结果，保证页面不会因模型异常中断。

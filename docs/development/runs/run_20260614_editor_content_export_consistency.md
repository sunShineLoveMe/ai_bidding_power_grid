# run_20260614_editor_content_export_consistency — 正文编辑与 DOCX 导出一致性真实回归

- 生成时间：2026-06-14T11:10:43
- 项目 ID：`4bc3ee73-9ec5-4184-aafd-eaede9f90798`
- 状态：PASS
- 测试章节：`投标函及投标函附录` / `9a8de84d-200b-446b-a314-349130d006b8`

## 验证项

| 用例 | 标记进入 DOCX | DOCX |
| --- | --- | --- |
| saved_database_content_export | True | `outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司.docx` |
| editor_snapshot_unsaved_content_export | True | `outputs/Guo_Wang_Liao_Zhu_Dian_Li_2025Nian_Di_San_Ci_Wu_Zi_Xie_Yi_Ku_Cun_Zhao_Biao_Cai_Gou/国网辽宁电力2025年第三次物资协议库存招标采购投标文件-河北泰昌电力器材科技有限公司.docx` |

## 结论

- 已保存到 `bid_sections.content` 的正文修改会进入真实 DOCX 导出。
- 前端传入的 `sectionsSnapshot` 未保存编辑内容也会优先进入真实 DOCX 导出。
- 回归结束后已恢复数据库原章节正文。

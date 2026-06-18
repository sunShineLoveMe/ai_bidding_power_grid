import unittest
from unittest.mock import patch


class BidPrefillReportTest(unittest.TestCase):
    def test_customer_decision_fields_remain_customer_required(self):
        from backend.services.bid_prefill import build_bid_prefill_report

        interpretation = {
            "project": {
                "id": "11111111-1111-1111-1111-111111111111",
                "project_name": "国网辽宁省电力有限公司2026年电缆保护管采购",
                "project_no": "TC-2026-001",
            },
            "analysis": {"project_meta": {"cover_fields": {"package_no": "包2"}}},
            "requirements": [{"content": "交货期：合同签订后30日内。投标有效期不少于90天。"}],
            "risks": [],
            "documentChunks": [{"content": "货物清单：CPVC电缆保护管 数量 1125米。"}],
        }

        with patch("backend.services.bid_prefill.get_project_interpretation", return_value=interpretation), \
             patch("backend.services.bid_prefill.list_knowledge_assets", return_value=[]):
            report = build_bid_prefill_report("11111111-1111-1111-1111-111111111111")

        by_key = {field["key"]: field for field in report["fields"]}
        self.assertEqual(by_key["project_name"]["status"], "system_recognized")
        self.assertEqual(by_key["package_no"]["status"], "manual_confirm")
        self.assertEqual(by_key["total_bid_price"]["status"], "customer_required")
        self.assertEqual(by_key["bid_bond_amount"]["status"], "customer_required")
        self.assertFalse(report["summary"]["affectsSectionsSnapshotExport"])
        self.assertTrue(report["summary"]["readonlyFirst"])

    def test_enterprise_assets_are_reported_as_library_candidates(self):
        from backend.services.bid_prefill import build_bid_prefill_report

        assets = [
            {"id": "a1", "title": "泰昌营业执照第1页", "asset_type": "qualification_image", "category": "基础证照"},
            {"id": "a2", "title": "泰昌CPVC电缆保护管检验报告第3页", "asset_type": "product_image", "category": "检验报告"},
            {"id": "a3", "title": "泰昌MPP生产线资料第2页", "asset_type": "product_image", "category": "生产制造能力"},
            {"id": "a4", "title": "泰昌0322AB包2合同协议书第1页", "asset_type": "qualification_image", "category": "项目业绩"},
        ]
        interpretation = {
            "project": {"id": "11111111-1111-1111-1111-111111111111"},
            "analysis": {"project_meta": {}},
            "requirements": [],
            "risks": [],
            "documentChunks": [],
        }

        with patch("backend.services.bid_prefill.get_project_interpretation", return_value=interpretation), \
             patch("backend.services.bid_prefill.list_knowledge_assets", return_value=assets):
            report = build_bid_prefill_report("11111111-1111-1111-1111-111111111111")

        by_key = {field["key"]: field for field in report["fields"]}
        self.assertEqual(by_key["qualification_assets"]["status"], "enterprise_library")
        self.assertEqual(by_key["inspection_reports"]["status"], "enterprise_library")
        self.assertEqual(by_key["project_performance_cases"]["status"], "enterprise_library")
        self.assertEqual(by_key["product_image_assets"]["status"], "enterprise_library")

    def test_verified_taichang_facts_are_prefill_candidates(self):
        from backend.services.bid_prefill import build_bid_prefill_report

        interpretation = {
            "project": {"id": "11111111-1111-1111-1111-111111111111"},
            "analysis": {"project_meta": {}},
            "requirements": [],
            "risks": [],
            "documentChunks": [],
        }

        with patch("backend.services.bid_prefill.get_project_interpretation", return_value=interpretation), \
             patch("backend.services.bid_prefill.list_knowledge_assets", return_value=[]), \
             patch("backend.services.bid_prefill.build_taichang_prefill_values", return_value={
                 "unified_social_credit_code": "91130607056539515C",
                 "legal_representative": "晁坤琳",
                 "product_models": ["CPVC电缆保护管：DS 250×15×6000 SN16 PVC-C"],
             }):
            report = build_bid_prefill_report("11111111-1111-1111-1111-111111111111")

        by_key = {field["key"]: field for field in report["fields"]}
        self.assertEqual(by_key["unified_social_credit_code"]["status"], "enterprise_library")
        self.assertEqual(by_key["unified_social_credit_code"]["value"], "91130607056539515C")
        self.assertEqual(by_key["legal_representative"]["status"], "enterprise_library")
        self.assertEqual(by_key["product_models"]["status"], "enterprise_library")

    def test_structured_goods_rows_feed_manual_prefill_candidates(self):
        from backend.services.bid_prefill import build_bid_prefill_report

        goods_rows = [
            {
                "分标编号": "2225AC-1408006-3401",
                "包名称": "包2",
                "物资名称": "电缆保护管,CPVC,φ200",
                "数量": "30000",
                "交货地点": "辽宁省大连市",
                "技术规范编码": "G00J-500038391-00003",
                "_package_code": "2225AC",
                "_material_family": "CPVC",
                "_spec": "φ200",
            },
            {
                "分标编号": "2225AC-1408006-3401",
                "包名称": "包2",
                "物资名称": "电缆保护管,CPVC,φ150",
                "数量": "5000",
                "交货地点": "辽宁省大连市",
                "技术规范编码": "G00J-500032536-00005",
                "_package_code": "2225AC",
                "_material_family": "CPVC",
                "_spec": "φ150",
            },
            {
                "分标编号": "2225AC-1408006-3402",
                "包名称": "包4",
                "物资名称": "电缆保护管,MPP,φ200",
                "数量": "1000",
                "交货地点": "辽宁省辽阳市",
                "技术规范编码": "G00J-500021520-00006",
                "_package_code": "2225AC",
                "_material_family": "MPP",
                "_spec": "φ200",
            },
        ]
        interpretation = {
            "project": {
                "id": "11111111-1111-1111-1111-111111111111",
                "project_name": "国网辽宁电力2025年第三次物资协议库存招标采购",
                "project_no": "2225AC",
            },
            "analysis": {"project_meta": {"cover_fields": {"package_no": "包2", "material_category": "CPVC"}}},
            "requirements": [{"content": "本项目为2225AC，投标包号：包2，物资为CPVC电缆保护管。"}],
            "risks": [],
            "documentChunks": [],
        }

        with patch("backend.services.bid_prefill.get_project_interpretation", return_value=interpretation), \
             patch("backend.services.bid_prefill.list_knowledge_assets", return_value=[]), \
             patch("backend.services.bid_prefill.build_taichang_prefill_values", return_value={}), \
             patch("backend.services.bid_prefill._load_liaoning_goods_rows", return_value=goods_rows):
            report = build_bid_prefill_report("11111111-1111-1111-1111-111111111111")

        by_key = {field["key"]: field for field in report["fields"]}
        self.assertEqual(by_key["package_no"]["value"], "包2")
        self.assertEqual(by_key["package_no"]["status"], "manual_confirm")
        self.assertEqual(by_key["package_name"]["value"], "电缆保护管CPVC")
        self.assertEqual(by_key["goods_list_summary"]["status"], "manual_confirm")
        self.assertIn("共 2 行需求", by_key["goods_list_summary"]["value"])
        self.assertIn("数量汇总：包2 35000米", by_key["goods_list_summary"]["value"])
        self.assertEqual(by_key["goods_list_summary"]["evidence"]["sourceType"], "structured_tender_goods_rows")
        self.assertFalse(by_key["goods_list_summary"]["evidence"]["factSourceAllowedForEnterprise"])

    def test_structured_technical_rows_feed_chapter_and_deviation_candidates(self):
        from backend.services.bid_prefill import build_bid_prefill_report

        technical_rows = [
            {
                "package_code": "2225AC",
                "package_no": "包2",
                "material_category": "电缆保护管CPVC",
                "table_type": "dimension_parameter_table",
                "parameter_name": "公称内径 200",
                "nominal_inner_diameter": "200",
                "bidder_response_value": "",
                "bidder_guaranteed_value": "",
                "row_data": {"公称内径": "200", "公称长度": "6000"},
                "source_file": "辽宁CPVC包2技术规范.doc",
            },
            {
                "package_code": "2225AC",
                "package_no": "包2",
                "material_category": "电缆保护管CPVC",
                "table_type": "technical_parameter_table",
                "parameter_name": "环刚度",
                "project_required_value": "SN16",
                "bidder_response_value": "",
                "bidder_guaranteed_value": "",
                "source_file": "辽宁CPVC包2技术规范.doc",
            },
            {
                "package_code": "2225AC",
                "package_no": "包4",
                "material_category": "电缆保护管MPP",
                "table_type": "technical_parameter_table",
                "parameter_name": "环刚度",
                "project_required_value": "SN40",
                "source_file": "辽宁MPP包4技术规范.doc",
            },
        ]
        deviation_rows = [
            {
                "package_code": "2225AC",
                "package_no": "包2",
                "material_category": "电缆保护管CPVC",
                "parameter_name": "公称内径 200",
                "deviation_status": "pending_response",
                "risk_level": "medium",
                "suggested_action": "补充泰昌响应值、保证值或明确写入无偏差承诺后复核。",
            },
            {
                "package_code": "2225AC",
                "package_no": "包4",
                "material_category": "电缆保护管MPP",
                "parameter_name": "环刚度",
                "deviation_status": "pending_response",
                "risk_level": "medium",
                "suggested_action": "补充泰昌响应值。",
            },
        ]
        product_rows = [
            {
                "product_family": "CPVC电缆保护管",
                "specification_model": "DS 250×15×6000 SN16 PVC-C",
                "nominal_inner_diameter": "250",
                "parameter_name": "尺寸-平均内径",
                "inspection_result": "250.2~250.4",
                "report_no": "2024100312005501713",
            },
            {
                "product_family": "MPP电缆保护管",
                "specification_model": "DF 250×22×9000 SN40 MPP",
                "nominal_inner_diameter": "250",
                "parameter_name": "环刚度",
                "inspection_result": "66.40",
                "report_no": "2024100312005501712",
            },
        ]
        interpretation = {
            "project": {
                "id": "11111111-1111-1111-1111-111111111111",
                "project_name": "国网辽宁电力2025年第三次物资协议库存招标采购",
                "project_no": "2225AC",
            },
            "analysis": {"project_meta": {"cover_fields": {"package_no": "包2", "material_category": "CPVC"}}},
            "requirements": [{"content": "本项目为2225AC，投标包号：包2，物资为CPVC电缆保护管。"}],
            "risks": [],
            "documentChunks": [],
        }

        with patch("backend.services.bid_prefill.get_project_interpretation", return_value=interpretation), \
             patch("backend.services.bid_prefill.list_knowledge_assets", return_value=[]), \
             patch("backend.services.bid_prefill.build_taichang_prefill_values", return_value={}), \
             patch("backend.services.bid_prefill._load_liaoning_goods_rows", return_value=[]), \
             patch("backend.services.bid_prefill._load_liaoning_technical_parameter_rows", return_value=technical_rows), \
             patch("backend.services.bid_prefill._load_liaoning_technical_deviation_rows", return_value=deviation_rows), \
             patch("backend.services.bid_prefill._load_taichang_product_parameter_rows", return_value=product_rows), \
             patch("backend.services.bid_prefill._safe_list_bid_sections", return_value=[
                 {"id": "s1", "title": "4.2 技术特性参数表", "order_index": 42, "level": 2},
                 {"id": "s2", "title": "4.1 技术偏差表", "order_index": 41, "level": 2},
                 {"id": "s3", "title": "6. 报价文件及货物清单", "order_index": 76, "level": 1},
                 {"id": "s4", "title": "4.4 产品制造与质量控制", "order_index": 61, "level": 2},
             ]):
            report = build_bid_prefill_report("11111111-1111-1111-1111-111111111111")

        by_key = {field["key"]: field for field in report["fields"]}
        self.assertEqual(by_key["technical_parameter_summary"]["status"], "manual_confirm")
        self.assertIn("共 2 行", by_key["technical_parameter_summary"]["value"])
        self.assertIn("待补投标响应/保证值 2 行", by_key["technical_parameter_summary"]["value"])
        self.assertEqual(by_key["technical_parameter_summary"]["evidence"]["sourceType"], "structured_technical_parameter_rows")
        self.assertFalse(by_key["technical_parameter_summary"]["evidence"]["factSourceAllowedForEnterprise"])
        self.assertEqual(by_key["technical_deviation_candidates"]["status"], "manual_confirm")
        self.assertIn("pending_response 1行", by_key["technical_deviation_candidates"]["value"])
        self.assertIn("不自动写入无偏差", by_key["technical_deviation_candidates"]["value"])
        self.assertEqual(by_key["taichang_parameter_match_summary"]["status"], "manual_confirm")
        self.assertIn("辽宁技术参数表规格中未由现有泰昌结构化报告直接覆盖的内径：200", by_key["taichang_parameter_match_summary"]["value"])
        self.assertIn("不构成覆盖辽宁全部规格的结论", by_key["taichang_parameter_match_summary"]["value"])
        self.assertTrue(by_key["taichang_parameter_match_summary"]["evidence"]["factSourceAllowedForEnterprise"])
        section_by_title = {item["sectionTitle"]: item for item in report["sectionCandidates"]}
        self.assertIn("4.2 技术特性参数表", section_by_title)
        self.assertIn("4.1 技术偏差表", section_by_title)
        self.assertIn("4.4 产品制造与质量控制", section_by_title)
        self.assertTrue(any(field["key"] == "technical_parameter_summary" for field in section_by_title["4.2 技术特性参数表"]["fields"]))
        self.assertTrue(any(field["key"] == "technical_deviation_candidates" for field in section_by_title["4.1 技术偏差表"]["fields"]))
        self.assertTrue(any(field["key"] == "taichang_parameter_match_summary" for field in section_by_title["4.4 产品制造与质量控制"]["fields"]))
        self.assertGreaterEqual(section_by_title["4.1 技术偏差表"]["gapCount"], 1)
        self.assertIn("tender_requirement", section_by_title["4.1 技术偏差表"]["sourceDomains"])
        self.assertTrue(section_by_title["4.1 技术偏差表"]["boundaryWarnings"])

    def test_placeholder_replacement_is_explicit_and_preserves_ordinary_text(self):
        from backend.services.bid_prefill import apply_confirmed_values_to_text

        content = (
            "项目名称：【待补充：项目名称】\n"
            "投标人：{{bidder_name}}\n"
            "本段普通正文提到项目名称，但不是占位符。\n"
            "【待补充：分标、包号、包名称和物资范围】"
        )
        updated, count = apply_confirmed_values_to_text(content, {
            "project_name": "辽宁电缆保护管采购项目",
            "bidder_name": "河北泰昌电力器材科技有限公司",
            "package_no": "包2",
            "package_name": "电缆保护管",
        })

        self.assertEqual(count, 2)
        self.assertIn("项目名称：辽宁电缆保护管采购项目", updated)
        self.assertIn("投标人：河北泰昌电力器材科技有限公司", updated)
        self.assertIn("本段普通正文提到项目名称，但不是占位符。", updated)
        self.assertIn("【待补充：分标、包号、包名称和物资范围】", updated)

    def test_apply_confirmation_persists_audit_and_updates_only_changed_sections(self):
        from backend.services.bid_prefill import apply_bid_prefill_confirmation

        original = {
            "id": "22222222-2222-2222-2222-222222222222",
            "title": "投标函",
            "content": "项目名称：【待补充：项目名称】\n投标人：{{bidder_name}}",
            "metadata": {},
        }
        updated = {**original, "content": "项目名称：辽宁采购项目\n投标人：河北泰昌电力器材科技有限公司"}
        interpretation = {"analysis": {"project_meta": {"cover_fields": {}}}}

        with patch("backend.services.bid_prefill.get_project_interpretation", return_value=interpretation), \
             patch("backend.services.bid_prefill.list_bid_sections", side_effect=[[original], [updated]]), \
             patch("backend.services.bid_prefill.update_bid_section_content", return_value=updated) as update_mock, \
             patch("backend.services.bid_prefill.update_bid_analysis_project_meta", return_value={"id": "analysis"}) as meta_mock:
            result = apply_bid_prefill_confirmation(
                "11111111-1111-1111-1111-111111111111",
                {"project_name": "辽宁采购项目"},
            )

        self.assertEqual(result["changed_section_count"], 1)
        self.assertEqual(result["replacement_count"], 2)
        self.assertFalse(result["ready_for_formal_export"])
        self.assertTrue(result["missing_formal_required_fields"])
        self.assertIn("export_gate", result)
        self.assertFalse(result["export_gate"]["ready"])
        self.assertEqual(result["export_gate"]["unresolvedPlaceholderCount"], 0)
        self.assertTrue(result["export_gate"]["missingFormalRequiredFields"])
        self.assertTrue(result["section_application_summary"])
        self.assertTrue(any(item["sectionTitle"] == "投标函" for item in result["section_application_summary"]))
        update_mock.assert_called_once()
        saved_meta = meta_mock.call_args.args[1]["bid_prefill"]
        self.assertEqual(saved_meta["confirmed_values"]["bidder_name"], "河北泰昌电力器材科技有限公司")
        self.assertIn("export_gate", saved_meta)
        self.assertIn("section_application_summary", saved_meta)

    def test_apply_confirmation_returns_ready_gate_after_required_values_resolved(self):
        from backend.services.bid_prefill import apply_bid_prefill_confirmation

        original = {
            "id": "33333333-3333-3333-3333-333333333333",
            "title": "投标函",
            "content": "项目名称：{{project_name}}\n招标编号：{{tender_no}}\n投标人：{{bidder_name}}",
            "metadata": {},
        }
        updated = {
            **original,
            "content": "项目名称：辽宁采购项目\n招标编号：2225AC\n投标人：河北泰昌电力器材科技有限公司",
        }
        interpretation = {"analysis": {"project_meta": {"cover_fields": {}}}}

        required_values = {
            "project_name": "辽宁采购项目",
            "tender_no": "2225AC",
            "tender_unit": "国网辽宁省电力有限公司",
            "bidder_name": "河北泰昌电力器材科技有限公司",
            "package_no": "包1",
            "package_name": "电缆保护管CPVC",
            "material_category": "电缆保护管CPVC",
            "goods_list_summary": "包1 电缆保护管CPVC 1000米",
            "delivery_place": "辽宁省",
            "unified_social_credit_code": "91130607056539515C",
            "legal_representative": "晁坤琳",
            "total_bid_price": "1000000元",
            "total_bid_price_upper": "壹佰万元整",
            "bid_bond_amount": "20000元",
            "bid_bond_form": "银行保函",
            "tax_rate": "13%",
            "delivery_period": "合同签订后30日内",
            "warranty_period": "按招标文件要求执行",
            "bid_validity_days": "90",
            "authorized_representative": "张三",
            "authorized_representative_id": "110101199001011234",
            "signature_date": "2026年6月18日",
            "qualification_assets": "营业执照副本",
            "inspection_reports": "CPVC电缆保护管检验报告",
            "product_models": "CPVC电缆保护管：DS 250×15×6000 SN16 PVC-C",
            "technical_parameter_summary": "技术参数表候选已确认",
            "technical_deviation_candidates": "技术偏差表候选待写入偏差表",
        }

        with patch("backend.services.bid_prefill.get_project_interpretation", return_value=interpretation), \
             patch("backend.services.bid_prefill.list_bid_sections", side_effect=[[original], [updated]]), \
             patch("backend.services.bid_prefill.update_bid_section_content", return_value=updated), \
             patch("backend.services.bid_prefill.update_bid_analysis_project_meta", return_value={"id": "analysis"}):
            result = apply_bid_prefill_confirmation(
                "11111111-1111-1111-1111-111111111111",
                required_values,
            )

        self.assertTrue(result["ready_for_formal_export"])
        self.assertTrue(result["export_gate"]["ready"])
        self.assertEqual(result["export_gate"]["unresolvedPlaceholderCount"], 0)
        self.assertEqual(result["export_gate"]["missingFormalRequiredFields"], [])
        self.assertEqual(result["changed_section_count"], 1)
        self.assertGreaterEqual(result["replacement_count"], 3)

    def test_rejects_changing_taichang_bidder(self):
        from backend.services.bid_prefill import apply_bid_prefill_confirmation

        with patch("backend.services.bid_prefill.get_project_interpretation", return_value={"analysis": {"project_meta": {}}}):
            with self.assertRaisesRegex(ValueError, "投标主体必须为河北泰昌"):
                apply_bid_prefill_confirmation(
                    "11111111-1111-1111-1111-111111111111",
                    {"bidder_name": "其他公司"},
                )


if __name__ == "__main__":
    unittest.main()

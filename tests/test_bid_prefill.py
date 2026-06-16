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


if __name__ == "__main__":
    unittest.main()

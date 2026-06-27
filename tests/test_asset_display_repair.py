import unittest

from backend.rag.display_names import category_display_name
from scripts.rag.repair_enterprise_asset_library_display import _repair_asset


class AssetDisplayRepairTest(unittest.TestCase):
    def test_personnel_product_asset_moves_to_qualification_library(self):
        row = {
            "title": "泰昌1.陈仙瑞第1页",
            "category": "人员证书",
            "asset_type": "product_image",
            "description": "人员证书资料",
            "tags": ["泰昌", "人员证书"],
            "metadata": {"library_type": "product", "target_library": "product_library"},
            "specs": {"library_type": "product", "applicable_volumes": ["technical"]},
        }

        repaired = _repair_asset(row, include_title_cleanup=True)

        self.assertEqual(repaired["title"], "陈仙瑞人员证书（第1页）")
        self.assertEqual(repaired["category"], "人员证书")
        self.assertEqual(repaired["asset_type"], "qualification_image")
        self.assertEqual(repaired["metadata"]["library_type"], "qualification")
        self.assertEqual(repaired["metadata"]["target_library"], "qualification_library")
        self.assertEqual(repaired["specs"]["applicable_volumes"], ["qualification", "business", "attachment"])

    def test_display_label_knows_personnel_certificate(self):
        self.assertEqual(category_display_name("personnel_certificate"), "人员证书")

    def test_certification_title_is_customer_readable(self):
        row = {
            "title": "泰昌3.职业健康安全管理体系认证证书第2页",
            "category": "资质证书",
            "asset_type": "qualification_image",
            "description": "",
            "tags": [],
            "metadata": {"evidence_type": "certification"},
            "specs": {},
        }

        repaired = _repair_asset(row, include_title_cleanup=True)

        self.assertEqual(repaired["title"], "职业健康安全管理体系认证证书（第2页）")
        self.assertEqual(repaired["category"], "资质证书")
        self.assertNotEqual(repaired.get("asset_type"), "product_image")


if __name__ == "__main__":
    unittest.main()

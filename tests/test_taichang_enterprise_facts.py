import os
import unittest
from unittest.mock import patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


class TaichangEnterpriseFactsTest(unittest.TestCase):
    def test_legal_representative_query_returns_verified_business_license_context(self):
        from backend.rag.enterprise_facts import search_taichang_enterprise_fact_contexts

        contexts = search_taichang_enterprise_fact_contexts("这家公司的法人代表是谁？")

        self.assertEqual(len(contexts), 1)
        self.assertIn("法定代表人：晁坤琳", contexts[0]["content"])
        self.assertNotIn("王伟杰", contexts[0]["content"])
        self.assertEqual(contexts[0]["metadata"]["evidence_type"], "business_license")
        self.assertEqual(contexts[0]["metadata"]["source_category"], "structured_enterprise_fact_pack")

    @patch("backend.rag.enterprise_facts.load_taichang_verified_fact_pack", return_value={})
    def test_enterprise_fact_context_has_verified_fallback_when_fact_pack_missing(self, _load):
        from backend.rag.enterprise_facts import search_taichang_enterprise_fact_contexts

        contexts = search_taichang_enterprise_fact_contexts("统一社会信用代码是多少？")

        self.assertIn("91130607056539515C", contexts[0]["content"])
        self.assertIn("晁坤琳", contexts[0]["content"])

    def test_low_trust_basic_info_conflict_detection_is_value_based(self):
        from scripts.rag.repair_taichang_legal_representative_facts import _conflicts_with_verified_facts

        row = {
            "content": "宣传彩页 OCR 片段：法定代表人：张三 注册资本：50万元",
            "metadata": {
                "enterprise": "泰昌",
                "source_domain": "enterprise_fact",
                "source_display_name": "宣传彩页",
                "evidence_type": "enterprise_profile",
            },
        }
        verified = {
            "legal_representative": "晁坤琳",
            "registered_capital": "10000万元人民币",
        }

        self.assertTrue(_conflicts_with_verified_facts(row, verified))

    def test_authoritative_business_license_is_not_quarantined_by_repair_helper(self):
        from scripts.rag.repair_taichang_legal_representative_facts import _conflicts_with_verified_facts

        row = {
            "content": "营业执照副本：法定代表人：晁坤琳 注册资本：10000万元人民币",
            "metadata": {
                "enterprise": "泰昌",
                "source_domain": "enterprise_fact",
                "source_display_name": "营业执照副本",
                "evidence_type": "business_license",
            },
        }

        self.assertFalse(_conflicts_with_verified_facts(row, {"legal_representative": "晁坤琳"}))


if __name__ == "__main__":
    unittest.main()

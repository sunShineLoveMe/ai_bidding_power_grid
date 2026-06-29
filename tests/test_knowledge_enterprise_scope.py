import os
import unittest


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


class KnowledgeEnterpriseScopeTest(unittest.TestCase):
    def test_legal_representative_query_is_scoped_to_business_license(self):
        from backend.api.knowledge import _query_evidence_scope

        self.assertEqual(_query_evidence_scope("这家公司的法人代表是谁？"), "enterprise_basic_info")
        self.assertEqual(_query_evidence_scope("法定代表人是谁？"), "enterprise_basic_info")

    def test_enterprise_basic_info_prefers_business_license_over_profile_ocr(self):
        from backend.api.knowledge import _curate_pilot_enterprise_contexts

        dirty_profile = {
            "id": "dirty-profile",
            "content": "宣传彩页 OCR 片段：法定代表人：王伟杰",
            "similarity": 0.98,
            "metadata": {
                "enterprise": "泰昌",
                "source_domain": "enterprise_fact",
                "fact_source_allowed_for_enterprise": True,
                "reference_only": False,
                "source_display_name": "宣传彩页",
                "evidence_type": "enterprise_profile",
            },
        }
        business_license = {
            "id": "license",
            "content": "营业执照副本：法定代表人晁坤琳",
            "similarity": 0.9,
            "metadata": {
                "enterprise": "泰昌",
                "source_domain": "enterprise_fact",
                "fact_source_allowed_for_enterprise": True,
                "reference_only": False,
                "source_display_name": "营业执照副本",
                "evidence_type": "business_license",
            },
        }

        result = _curate_pilot_enterprise_contexts(
            [dirty_profile, business_license],
            limit=2,
            query="这家公司的法人代表是谁？",
        )

        self.assertEqual(result[0]["id"], "license")
        self.assertNotIn("dirty-profile", [item["id"] for item in result])


if __name__ == "__main__":
    unittest.main()

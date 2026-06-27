import os
import unittest

from flask import Flask


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


class KnowledgeAssetUploadPayloadTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def _payload(self, form, storage_info=None, existing=None):
        from backend.api.assets import _asset_payload_from_form

        with self.app.test_request_context(method="POST", data=form):
            return _asset_payload_from_form(storage_info=storage_info or {}, existing=existing)

    def test_product_upload_gets_formal_chinese_display_fields(self):
        payload = self._payload(
            {
                "library_type": "product",
                "title": "泰昌MPP生产线_页面_9原图",
                "category": "production_capacity",
                "tags": "泰昌,taichang,production_capacity,technical",
                "applicable_sections": "生产制造能力",
                "applicable_volumes": "technical",
                "description": "客户补充文件《3.MPP生产线_页面_9.jpg》原图。",
            },
            storage_info={
                "file_name": "3.MPP生产线_页面_9.jpg",
                "mime_type": "image/jpeg",
            },
        )

        self.assertEqual(payload["title"], "泰昌MPP生产线资料")
        self.assertEqual(payload["category"], "生产制造能力")
        self.assertEqual(payload["metadata"]["source_display_name"], "泰昌MPP生产线资料")
        self.assertEqual(payload["metadata"]["evidence_type"], "production_capacity")
        self.assertEqual(payload["metadata"]["evidence_type_label"], "生产制造能力")
        self.assertEqual(payload["metadata"]["target_library_label"], "产品库资料")
        self.assertEqual(payload["metadata"]["caption_policy"], "formal_material_caption")
        self.assertIn("formal_caption", payload["metadata"])

        visible_blob = "\n".join([
            payload["title"],
            payload["description"],
            payload["searchable_text"],
            " ".join(payload["tags"]),
        ])
        for forbidden in ("页面_", "原图", "taichang", "production_capacity", "technical", "product_image"):
            self.assertNotIn(forbidden, visible_blob)
        self.assertIn("技术标", payload["searchable_text"])

    def test_qualification_upload_keeps_business_license_as_enterprise_fact(self):
        payload = self._payload(
            {
                "library_type": "qualification",
                "title": "business_license_aa787a1c-d48d-46f6-bcbd-4806003b8428原图",
                "category": "business_license",
                "tags": "business_license,资信库",
                "applicable_sections": "基础证照",
                "applicable_volumes": "qualification,business",
            },
            storage_info={
                "file_name": "business_license_aa787a1c-d48d-46f6-bcbd-4806003b8428.png",
                "mime_type": "image/png",
            },
        )

        self.assertEqual(payload["title"], "泰昌基础证照资料")
        self.assertEqual(payload["category"], "基础证照")
        self.assertEqual(payload["metadata"]["source_domain"], "enterprise_fact")
        self.assertTrue(payload["metadata"]["fact_source_allowed_for_enterprise"])
        self.assertEqual(payload["metadata"]["tenant_visibility"], "taichang_only")
        self.assertEqual(payload["metadata"]["target_library_label"], "资信库资料")

        visible_blob = "\n".join([
            payload["title"],
            payload["description"],
            payload["searchable_text"],
            " ".join(payload["tags"]),
        ])
        for forbidden in ("business_license", "aa787a1c", "原图", "qualification_image"):
            self.assertNotIn(forbidden, visible_blob)
        self.assertIn("资格文件", payload["searchable_text"])


if __name__ == "__main__":
    unittest.main()

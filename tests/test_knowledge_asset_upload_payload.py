import os
import unittest
from io import BytesIO

from flask import Flask
from werkzeug.datastructures import FileStorage


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
        self.assertEqual(payload["metadata"]["quality_tier"], "formal_bid_ready")
        self.assertTrue(payload["metadata"]["allowed_for_bid"])
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
        self.assertEqual(payload["metadata"]["quality_tier"], "formal_bid_ready")

        visible_blob = "\n".join([
            payload["title"],
            payload["description"],
            payload["searchable_text"],
            " ".join(payload["tags"]),
        ])
        for forbidden in ("business_license", "aa787a1c", "原图", "qualification_image"):
            self.assertNotIn(forbidden, visible_blob)
        self.assertIn("资格文件", payload["searchable_text"])

    def test_small_or_partial_image_requires_review_and_blocks_bid_usage(self):
        payload = self._payload(
            {
                "library_type": "qualification",
                "title": "泰昌营业执照二维码局部截图",
                "category": "business_license",
                "applicable_volumes": "qualification,business",
                "allowed_for_bid": "true",
            },
            storage_info={
                "file_name": "营业执照二维码局部截图.png",
                "mime_type": "image/png",
                "file_size": 4096,
            },
        )

        self.assertEqual(payload["metadata"]["quality_tier"], "review_only")
        self.assertFalse(payload["metadata"]["allowed_for_bid"])
        self.assertFalse(payload["specs"]["allowed_for_bid"])
        self.assertTrue(payload["specs"]["user_requested_bid_usage"])
        self.assertTrue(any("人工复核" in note or "不自动进入正式标书" in note for note in payload["metadata"]["quality_notes"]))

    def test_product_parameter_table_is_knowledge_only_and_not_bid_image(self):
        payload = self._payload(
            {
                "library_type": "product",
                "title": "CPVC电缆保护管产品参数表",
                "evidence_type": "product_parameter_table",
                "category": "产品参数表",
                "tags": "CPVC,参数表",
                "applicable_volumes": "technical",
                "allowed_for_bid": "true",
            },
            storage_info={
                "file_name": "CPVC电缆保护管产品参数表.xlsx",
                "file_ext": "xlsx",
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "file_size": 8192,
            },
        )

        self.assertEqual(payload["category"], "产品参数表")
        self.assertEqual(payload["metadata"]["evidence_type"], "product_parameter_table")
        self.assertEqual(payload["metadata"]["evidence_type_label"], "产品参数表")
        self.assertEqual(payload["metadata"]["quality_tier"], "knowledge_only")
        self.assertFalse(payload["metadata"]["allowed_for_bid"])
        self.assertTrue(payload["metadata"]["user_requested_bid_usage"])
        self.assertIn("结构化抽取", "；".join(payload["metadata"]["quality_notes"]))

    def test_asset_upload_accepts_excel_and_csv_files(self):
        from backend.core.security import validate_uploaded_file

        for filename, mimetype in (
            ("泰昌产品参数表.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("泰昌产品参数表.csv", "text/csv"),
        ):
            with self.subTest(filename=filename):
                file = FileStorage(stream=BytesIO(b"placeholder"), filename=filename, content_type=mimetype)
                validate_uploaded_file(file, kind="asset")


if __name__ == "__main__":
    unittest.main()

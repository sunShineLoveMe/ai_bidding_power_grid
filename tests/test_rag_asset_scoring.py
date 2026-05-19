import os
import unittest


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


def _section(title: str, volume_type: str, **extra):
    return {
        "id": f"{volume_type}-section",
        "title": title,
        "purpose": extra.get("purpose", ""),
        "response_points": extra.get("response_points", []),
        "required_materials": extra.get("required_materials", []),
        "metadata": {
            "volume_type": volume_type,
            "writing_plan": {"needs_image": True},
        },
    }


PRODUCT_ASSET = {
    "id": "product-asset",
    "title": "高压旋喷桩设备产品图",
    "category": "水库除险加固",
    "asset_type": "product_image",
    "description": "白底设备产品图，展示高压旋喷桩设备、技术参数和坝基防渗施工场景。",
    "tags": ["产品图", "设备参数", "坝基防渗"],
    "applicable_sections": ["技术标", "施工组织设计", "设备配置方案"],
    "applicable_volumes": ["technical"],
    "metadata": {"library_type": "product"},
    "specs": {"library_type": "product", "allowed_for_bid": True, "applicable_volumes": ["technical"]},
}

QUALIFICATION_ASSET = {
    "id": "qualification-asset",
    "title": "脱敏质量管理体系认证证书样张",
    "category": "资质证书",
    "asset_type": "qualification_image",
    "description": "企业资信库脱敏证书样张，适用于资格文件和资质证明材料。",
    "tags": ["资质证书", "体系认证", "脱敏样张"],
    "applicable_sections": ["资格文件", "企业基本资质资料"],
    "applicable_volumes": ["qualification", "business", "attachment"],
    "metadata": {"library_type": "qualification"},
    "specs": {"library_type": "qualification", "allowed_for_bid": True, "applicable_volumes": ["qualification", "business", "attachment"]},
    "is_sensitive": True,
    "anonymized": True,
}

BUSINESS_ASSET = {
    "id": "business-asset",
    "title": "商务承诺函模板",
    "category": "商务响应模板",
    "asset_type": "qualification_image",
    "description": "付款、合同管理、保密义务、农民工工资支付等商务条款承诺。",
    "tags": ["商务", "承诺函", "合同响应"],
    "applicable_sections": ["商务标", "商务响应文件"],
    "applicable_volumes": ["business"],
    "metadata": {"library_type": "qualification"},
    "specs": {"library_type": "qualification", "allowed_for_bid": True, "applicable_volumes": ["business"]},
}


class RagAssetScoringQualityTest(unittest.TestCase):
    def test_section_writer_scores_product_assets_higher_for_technical_volume(self):
        from backend.ai.section_writer import _supporting_asset_score

        technical = _section(
            "施工组织设计与设备配置",
            "technical",
            response_points=["坝基防渗", "高压旋喷桩施工设备", "质量控制"],
        )

        product_score = _supporting_asset_score(PRODUCT_ASSET, technical, "technical")
        qualification_score = _supporting_asset_score(QUALIFICATION_ASSET, technical, "technical")

        self.assertGreater(product_score, qualification_score)
        self.assertGreaterEqual(product_score, 20)

    def test_section_writer_scores_qualification_assets_higher_for_qualification_volume(self):
        from backend.ai.section_writer import _supporting_asset_score

        qualification = _section(
            "企业基本资质资料",
            "qualification",
            required_materials=["营业执照", "质量管理体系认证证书", "人员证书"],
        )

        qualification_score = _supporting_asset_score(QUALIFICATION_ASSET, qualification, "qualification")
        product_score = _supporting_asset_score(PRODUCT_ASSET, qualification, "qualification")

        self.assertGreater(qualification_score, product_score)
        self.assertGreaterEqual(qualification_score, 24)

    def test_docx_image_selection_prefers_product_asset_for_technical_section(self):
        from backend.api.routes import _build_section_image_markdown

        technical = _section(
            "坝基防渗处理施工方案",
            "technical",
            response_points=["高压旋喷桩设备", "施工工艺", "质量检测"],
        )
        manifest = []

        markdown = _build_section_image_markdown(
            technical,
            [QUALIFICATION_ASSET, PRODUCT_ASSET],
            used_asset_ids=set(),
            image_manifest=manifest,
            remaining_limit=2,
        )

        self.assertIn("高压旋喷桩设备产品图", markdown)
        self.assertNotIn("质量管理体系认证证书", markdown)
        self.assertEqual(manifest[0]["library"], "企业产品库")
        self.assertIn("技术标优先使用产品/设备资料", manifest[0]["reason"])

    def test_docx_image_selection_prefers_qualification_asset_for_qualification_section(self):
        from backend.api.routes import _build_section_image_markdown

        qualification = _section(
            "企业基本资质资料",
            "qualification",
            required_materials=["质量管理体系认证证书", "营业执照", "人员证书"],
        )
        manifest = []

        markdown = _build_section_image_markdown(
            qualification,
            [PRODUCT_ASSET, QUALIFICATION_ASSET],
            used_asset_ids=set(),
            image_manifest=manifest,
            remaining_limit=2,
        )

        self.assertIn("脱敏质量管理体系认证证书样张", markdown)
        self.assertNotIn("高压旋喷桩设备产品图", markdown)
        self.assertEqual(manifest[0]["library"], "企业资信库")
        self.assertTrue(manifest[0]["sensitive"])

    def test_docx_image_selection_keeps_business_volume_conservative_by_default(self):
        from backend.api.routes import _build_section_image_markdown

        business = _section(
            "商务响应文件",
            "business",
            response_points=["付款承诺", "合同管理", "保密义务"],
        )

        markdown = _build_section_image_markdown(
            business,
            [PRODUCT_ASSET, BUSINESS_ASSET],
            used_asset_ids=set(),
            image_manifest=[],
            remaining_limit=2,
        )

        self.assertEqual(markdown, "")

    def test_docx_image_selection_allows_business_attachment_when_explicitly_required(self):
        from backend.api.routes import _build_section_image_markdown

        business = _section(
            "商务响应证明材料",
            "business",
            response_points=["付款承诺证明材料", "合同管理承诺附件", "保密义务"],
        )
        manifest = []

        markdown = _build_section_image_markdown(
            business,
            [PRODUCT_ASSET, BUSINESS_ASSET],
            used_asset_ids=set(),
            image_manifest=manifest,
            remaining_limit=2,
        )

        self.assertIn("商务承诺函模板", markdown)
        self.assertNotIn("高压旋喷桩设备产品图", markdown)
        self.assertEqual(manifest[0]["volume_type"], "business")

    def test_explicit_applicable_volumes_block_cross_volume_image_asset(self):
        from backend.api.routes import _build_section_image_markdown

        technical = _section(
            "施工现场证明材料",
            "technical",
            response_points=["证明材料", "施工组织"],
        )
        business_only_asset = {
            **BUSINESS_ASSET,
            "title": "商务承诺证明材料",
            "description": "证明材料、承诺函、商务响应附件。",
            "applicable_volumes": ["business"],
            "specs": {"library_type": "qualification", "allowed_for_bid": True, "applicable_volumes": ["business"]},
        }

        markdown = _build_section_image_markdown(
            technical,
            [business_only_asset],
            used_asset_ids=set(),
            image_manifest=[],
            remaining_limit=2,
        )

        self.assertEqual(markdown, "")


if __name__ == "__main__":
    unittest.main()

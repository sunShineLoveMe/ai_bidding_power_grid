import unittest


class RagDisplayNamesTest(unittest.TestCase):
    def test_internal_markdown_source_gets_chinese_display_name(self):
        from backend.rag.display_names import sanitize_source_metadata

        meta = sanitize_source_metadata({
            "source_file": "parsed_outputs/x/taichang_production_capacity_private.md",
            "category_label": "power_grid_tender_documents",
            "evidence_type": "production_capacity",
            "target_library": "product_library",
        })

        self.assertEqual(meta["source_display_name"], "泰昌生产制造能力资料")
        self.assertEqual(meta["category_label"], "电网招投标资料")
        self.assertEqual(meta["evidence_type_label"], "生产制造能力")
        self.assertEqual(meta["target_library_label"], "产品库资料")

    def test_chinese_pdf_source_is_preserved(self):
        from backend.rag.display_names import sanitize_source_metadata

        meta = sanitize_source_metadata({
            "source_file": "rag_seed/泰昌资料/3检验报告/MPP电缆保护管检验报告内径250.pdf",
            "source_category": "05_enterprise_documents",
        })

        self.assertEqual(meta["source_display_name"], "MPP电缆保护管检验报告内径250")
        self.assertEqual(meta["source_document_name"], "MPP电缆保护管检验报告内径250")
        self.assertEqual(meta["source_category_label"], "泰昌企业资料")

    def test_enterprise_fact_preserves_specific_category_label(self):
        from backend.rag.display_names import sanitize_source_metadata

        meta = sanitize_source_metadata({
            "source_domain": "enterprise_fact",
            "source_category": "05_enterprise_documents",
            "source_display_name": "绿色发展规划报告",
            "category_label": "绿色低碳资料",
            "evidence_type": "green_low_carbon",
            "target_library": "product_library",
        })

        self.assertEqual(meta["category_label"], "绿色低碳资料")
        self.assertEqual(meta["evidence_type_label"], "绿色低碳资料")
        self.assertEqual(meta["source_category_label"], "泰昌企业资料")

    def test_enterprise_fact_generic_category_falls_back_to_evidence_type(self):
        from backend.rag.display_names import sanitize_source_metadata

        meta = sanitize_source_metadata({
            "source_domain": "enterprise_fact",
            "source_category": "05_enterprise_documents",
            "source_display_name": "泰昌生产制造能力资料",
            "category_label": "泰昌企业资料",
            "evidence_type": "production_capacity",
            "target_library": "product_library",
        })

        self.assertEqual(meta["category_label"], "生产制造能力")
        self.assertEqual(meta["evidence_type_label"], "生产制造能力")

    def test_internal_paths_and_asset_fields_are_removed_from_visible_context(self):
        from backend.rag.display_names import sanitize_source_contexts

        contexts = sanitize_source_contexts([{
            "content": "- asset_path: parsed_outputs/a/taichang_certification_p1_017.png\n"
                       "可通过 /api/knowledge/assets/asset-1/file 查看 certification 资料。",
            "metadata": {
                "source_file": "parsed_outputs/a/taichang_certification_private.md",
                "evidence_type": "certification",
                "target_library": "qualification_library",
            },
        }])

        self.assertNotIn("parsed_outputs", contexts[0]["content"])
        self.assertNotIn("/api/knowledge/assets", contexts[0]["content"])
        self.assertNotIn("certification", contexts[0]["content"])
        self.assertNotIn("source_file", contexts[0]["metadata"])
        self.assertEqual(contexts[0]["metadata"]["source_display_name"], "泰昌资质证书资料")

    def test_assets_hide_parser_details_and_deduplicate_visible_titles(self):
        from backend.rag.display_names import sanitize_knowledge_assets

        assets = sanitize_knowledge_assets([
            {
                "title": "泰昌照片1原图",
                "asset_type": "product_image",
                "description": "客户已提供文件。该图片为正式整页/原图资产，不是 MinerU 局部切图。",
                "metadata": {"source_display_name": "泰昌照片1原图"},
            },
            {
                "title": "泰昌照片1原图",
                "description": "同名重复资产",
                "metadata": {"source_display_name": "泰昌照片1原图"},
            },
        ])

        self.assertEqual(len(assets), 1)
        self.assertNotIn("MinerU", assets[0]["description"])
        self.assertEqual(assets[0]["description"], "客户已提供文件。")
        self.assertEqual(assets[0]["asset_type"], "产品图片")


if __name__ == "__main__":
    unittest.main()

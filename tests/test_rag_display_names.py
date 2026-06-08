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
        self.assertEqual(meta["source_category_label"], "泰昌企业资料")


if __name__ == "__main__":
    unittest.main()

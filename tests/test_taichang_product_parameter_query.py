import unittest


class TaichangProductParameterQueryTest(unittest.TestCase):
    def test_queries_real_json_for_mpp_ring_stiffness(self):
        from backend.rag.product_parameters import search_taichang_product_parameter_contexts

        contexts = search_taichang_product_parameter_contexts(
            "泰昌MPP电缆保护管内径250的环刚度检验结果是多少？",
            limit=3,
        )

        self.assertGreaterEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["retrieval_source"], "structured_product_parameter_json")
        self.assertIn("环刚度", contexts[0]["content"])
        self.assertIn("66.40", contexts[0]["content"])
        self.assertIn("2024100312005501712", contexts[0]["content"])

    def test_queries_real_json_for_cpvc_inner_diameter_and_wall(self):
        from backend.rag.product_parameters import search_taichang_product_parameter_contexts

        contexts = search_taichang_product_parameter_contexts(
            "泰昌CPVC电缆保护管内径250的平均内径和壁厚检验结果是多少？",
            limit=5,
        )
        content = "\n".join(context["content"] for context in contexts)

        self.assertEqual(len(contexts), 2)
        self.assertIn("尺寸-平均内径", content)
        self.assertIn("250.2~250.4", content)
        self.assertIn("尺寸-壁厚", content)
        self.assertIn("15.2~15.3", content)
        self.assertIn("2024100312005501713", content)
        self.assertNotIn("尺寸-承口平均内径", content)
        self.assertNotIn("280.5", content)

    def test_query_context_keeps_liaoning_as_qa_only_boundary(self):
        from backend.rag.product_parameters import search_taichang_product_parameter_contexts

        contexts = search_taichang_product_parameter_contexts(
            "泰昌这两份内径250检验报告是否能说明覆盖辽宁所有CPVC和MPP规格需求？",
            limit=2,
        )
        content = "\n".join(context["content"] for context in contexts)

        self.assertIn("辽宁资料仅可作QA/异常校验参照", content)
        self.assertIn("不构成覆盖辽宁全部规格的结论", content)

    def test_same_report_multi_parameter_contexts_merge_without_losing_values(self):
        from backend.api.knowledge import _curate_pilot_enterprise_contexts
        from backend.rag.product_parameters import search_taichang_product_parameter_contexts

        query = "泰昌CPVC电缆保护管内径250的平均内径和壁厚检验结果是多少？"
        raw_contexts = search_taichang_product_parameter_contexts(query, limit=5)
        merged = _curate_pilot_enterprise_contexts(raw_contexts, limit=3, query=query)

        self.assertEqual(len(merged), 1)
        self.assertIn("250.2~250.4", merged[0]["content"])
        self.assertIn("15.2~15.3", merged[0]["content"])
        self.assertEqual(
            merged[0]["metadata"]["parameter_name"],
            "尺寸-平均内径；尺寸-壁厚",
        )
        self.assertNotIn("280.5", merged[0]["content"])

    def test_broad_capability_query_does_not_force_parameter_rows(self):
        from backend.rag.product_parameters import search_taichang_product_parameter_contexts

        contexts = search_taichang_product_parameter_contexts(
            "泰昌有哪些产品、生产和检测能力资料可以用于技术响应？",
            limit=5,
        )

        self.assertEqual(contexts, [])


if __name__ == "__main__":
    unittest.main()

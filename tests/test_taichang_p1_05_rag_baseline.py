import unittest

from backend.rag.taichang_scope import build_taichang_scope_filter, infer_taichang_product_scope
from scripts.rag.ingest_taichang_p1_05_rag_baseline import build_chunks


class TaichangP105RagBaselineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks = build_chunks()
        cls.parents = [row for row in cls.chunks if row["metadata"]["chunk_layer"] == "parent"]
        cls.children = [row for row in cls.chunks if row["metadata"]["chunk_layer"] == "child"]

    def test_parent_child_structure_and_metadata_are_complete(self):
        self.assertGreater(len(self.parents), 0)
        self.assertGreater(len(self.children), 100)
        parent_indexes = {row["chunk_index"] for row in self.parents}
        required = {"enterprise", "source_domain", "product_family", "material_category", "evidence_type"}
        for row in self.children:
            self.assertIn(row["metadata"]["parent_index"], parent_indexes)
            self.assertTrue(all(row["metadata"].get(key) for key in required))
            self.assertEqual(row["embedding"], "__PENDING__")

    def test_structured_sources_are_all_represented(self):
        evidence_types = {row["metadata"]["evidence_type"] for row in self.children}
        self.assertTrue({"inspection_report", "project_performance", "personnel_roster", "personnel_certificate", "scope_guard"}.issubset(evidence_types))
        self.assertEqual(sum(1 for row in self.children if row["metadata"]["evidence_type"] == "personnel_roster"), 66)
        self.assertEqual(sum(1 for row in self.children if row["metadata"]["evidence_type"] == "personnel_certificate"), 2)
        self.assertEqual(sum(1 for row in self.children if row["metadata"].get("parameter_name")), 36)
        self.assertEqual(sum(1 for row in self.children if row["metadata"].get("evidence_bundle_id")), 16)

    def test_cross_product_scope_guard_contains_no_cable_product_facts(self):
        guards = [row for row in self.children if row["metadata"]["evidence_type"] == "scope_guard"]
        self.assertEqual(len(guards), 1)
        guard = guards[0]
        self.assertEqual(guard["metadata"]["product_family"], ["架空绝缘导线"])
        self.assertIn("不得跨产品引用", guard["content"])
        for forbidden in ("CPVC", "MPP", "N-HAP", "UPVC"):
            self.assertNotIn(forbidden, guard["content"])

    def test_query_scope_filter_is_applied_before_retrieval(self):
        self.assertEqual(infer_taichang_product_scope("泰昌MPP环刚度是多少"), {"product_family": "MPP电缆保护管", "material_category": "电缆保护管MPP"})
        guard_filter = build_taichang_scope_filter("泰昌架空绝缘导线有哪些检验报告？")
        self.assertEqual(guard_filter["product_family"], ["架空绝缘导线"])
        self.assertEqual(guard_filter["material_category"], ["架空绝缘导线"])
        self.assertEqual(guard_filter["evidence_type"], "scope_guard")

    def test_structured_parameter_lookup_rejects_other_product_family(self):
        from backend.rag.product_parameters import search_taichang_product_parameter_contexts

        contexts = search_taichang_product_parameter_contexts("泰昌架空绝缘导线有哪些检验报告和结构化参数？")
        self.assertEqual(contexts, [])


if __name__ == "__main__":
    unittest.main()

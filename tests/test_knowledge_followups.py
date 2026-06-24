import unittest


class KnowledgeFollowupsTest(unittest.TestCase):
    def test_unverified_missing_material_claims_are_removed(self):
        from backend.api.knowledge import _normalize_followups

        result = _normalize_followups({
            "intent": "material_gap",
            "followups": [
                "目前泰昌缺少业绩合同和检验报告，这些是否会导致废标？",
                "泰昌是否具备业绩合同和检验报告？",
                "这些企业证明材料适合放在标书哪些章节？",
            ],
        })

        self.assertEqual(result["followups"], [
            "泰昌是否具备业绩合同和检验报告？",
            "这些企业证明材料适合放在标书哪些章节？",
        ])


if __name__ == "__main__":
    unittest.main()

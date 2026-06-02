import unittest

from backend.rag.chunking import build_parent_child_chunks


class RagChunkingTest(unittest.TestCase):
    def test_main_tender_file_skips_heading_only_parents(self):
        text = """# 招标文件
第一章 招标公告

第一章 招标公告
1.招标条件 项目资金已落实，现进行公开招标。
2.项目概况与招标范围 详见货物清单。

第二章 投标人须知

第二章 投标人须知
1.投标文件组成 商务文件、技术文件、价格文件应分别编制。
"""
        chunks = build_parent_child_chunks(text, doc_role="main_tender_file")
        parents = [chunk for chunk in chunks if chunk.layer == "parent"]

        self.assertGreaterEqual(len(parents), 2)
        self.assertNotIn("第一章 招标公告", [chunk.content for chunk in parents])
        self.assertNotIn("第二章 投标人须知", [chunk.content for chunk in parents])
        self.assertTrue(any("项目资金已落实" in chunk.content for chunk in parents))
        self.assertTrue(any("投标文件组成" in chunk.content for chunk in parents))

    def test_contract_clause_doc_skips_heading_only_parents(self):
        text = """# 合同条款
第一章 总则

第一章 总则
第一条 合同文件应能相互解释，互为说明。
第二条 买方和卖方应按合同约定履行义务。
"""
        chunks = build_parent_child_chunks(text, doc_role="contract_general_terms")
        parents = [chunk for chunk in chunks if chunk.layer == "parent"]
        children = [chunk for chunk in chunks if chunk.layer == "child"]

        self.assertEqual(len(parents), 1)
        self.assertNotEqual(parents[0].content, "第一章 总则")
        self.assertEqual(len(children), 2)


if __name__ == "__main__":
    unittest.main()

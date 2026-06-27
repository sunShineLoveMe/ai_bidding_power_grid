import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROWS = ROOT / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/taichang_project_performance_rows.json"


class TaichangProjectPerformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, "scripts/rag/extract_taichang_project_performance.py"], cwd=ROOT, check=True)

    def test_extracts_cross_checked_project_and_evidence(self):
        rows = json.loads(ROWS.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["evidence_type"] for row in rows}, {"award_notice", "supply_contract"})
        for row in rows:
            self.assertEqual(row["tender_no"], "0322AB")
            self.assertEqual(row["package_no"], "包2")
            self.assertEqual(row["total_quantity"], 54678.0)
            self.assertEqual(row["amount_tax_included_yuan"], 6372409.05)
            self.assertEqual(len(row["line_items"]), 9)

    def test_contract_date_remains_missing_and_auditable(self):
        rows = json.loads(ROWS.read_text(encoding="utf-8"))
        contract = next(row for row in rows if row["evidence_type"] == "supply_contract")
        self.assertEqual(contract["contract_sign_date"], "")
        self.assertEqual(contract["date_status"], "contract_sign_date_blank_in_source")
        self.assertEqual(contract["contract_no_buyer"], "SGTJWZ00HTMM2210273")
        self.assertEqual(contract["source_pages"]["contract_amount"], [3])
        by_spec = {(item["product_family"], item["specification_model"]): item for item in contract["line_items"]}
        self.assertEqual(by_spec[("MPP电缆保护管", "φ250")]["quantity"], 900.0)
        self.assertEqual(by_spec[("CPVC电缆保护管", "φ250")]["quantity"], 1125.0)
        self.assertEqual(by_spec[("CPVC电缆保护管", "φ200")]["quantity"], 11248.0)

    def test_structured_query_returns_both_evidence_records(self):
        from backend.rag.project_performance import search_taichang_project_performance_contexts

        contexts = search_taichang_project_performance_contexts("泰昌0322AB包2同类项目业绩的数量、金额和资料来源是什么？")
        content = "\n".join(context["content"] for context in contexts)
        self.assertEqual(len(contexts), 2)
        self.assertIn("54678 米", content)
        self.assertIn("6372409.05 元", content)
        self.assertIn("原件字段为空，未推断", content)
        self.assertTrue(all(context["retrieval_source"] == "structured_project_performance_json" for context in contexts))


if __name__ == "__main__":
    unittest.main()

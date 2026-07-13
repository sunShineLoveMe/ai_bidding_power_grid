import json
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.rag.inventory_taichang_historical_bids import (  # noqa: E402
    TenderMatcher,
    normalize_heading,
)


DATA_DIR = ROOT_DIR / "docs" / "development" / "taichang-bid-v1-data"


class TaichangHistoricalBidInventoryTest(unittest.TestCase):
    def test_normalize_heading_removes_number_upload_path_and_toc_page(self):
        value = "1.商务偏差表（上传投标工具路径：商务文件-按钮“编辑”）4"
        self.assertEqual(normalize_heading(value), "商务偏差表")

    def test_tender_matcher_marks_conditional_clause(self):
        matcher = object.__new__(TenderMatcher)
        matcher.source_file = "tender.docx"
        matcher.clauses = [
            {
                "paragraph_index": "1",
                "text": "投标保证保险（如有，本批次不适用）",
                "normalized": "投标保证保险",
            }
        ]
        result = matcher.classify("（二）投标保证保险", ["（二）投标保证保险"])
        self.assertEqual(result.origin_type, "tender_conditional")
        self.assertEqual(result.review_status, "source_matched")

    def test_generated_skeleton_has_complete_provenance_and_page_sequence(self):
        payload = json.loads(
            (DATA_DIR / "taichang_historical_reference_skeleton.json").read_text(encoding="utf-8")
        )
        technical = payload["documents"]["technical"]
        business = payload["documents"]["business"]

        self.assertFalse(payload["mineru_invoked"])
        self.assertFalse(payload["allowed_for_bid"])
        self.assertEqual(payload["artifact_role"], "historical_reference_skeleton")
        self.assertTrue(payload["not_final_project_skeleton"])
        self.assertTrue(payload["current_tender_semantic_detection_required"])
        self.assertFalse(payload["chapter_number_locator_allowed"])
        self.assertEqual(payload["project_output_contract"], "project_bid_skeleton.json")
        self.assertEqual(len(technical["chapters"]), 73)
        self.assertEqual(len(business["chapters"]), 61)
        self.assertEqual(technical["stats"]["headings_with_toc_page"], 73)
        self.assertEqual(business["stats"]["headings_with_toc_page"], 61)

        for chapter in technical["chapters"] + business["chapters"]:
            self.assertTrue(chapter["source_file"])
            self.assertTrue(chapter["source_section"])
            self.assertTrue(chapter["origin_type"])
            self.assertTrue(chapter["review_status"])
            self.assertGreaterEqual(chapter["source_page_end"], chapter["source_page_start"])
            self.assertFalse(chapter["allowed_for_bid"])

    def test_generated_fact_candidates_are_review_only_and_complete(self):
        for filename in (
            "taichang_technical_bid_candidate_inventory.json",
            "taichang_business_bid_candidate_inventory.json",
        ):
            payload = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
            self.assertFalse(payload["metadata"]["mineru_invoked"])
            for record in payload["records"]:
                self.assertEqual(record["quality_tier"], "review_only")
                self.assertFalse(record["allowed_for_bid"])
                if record["record_type"] != "fact_candidate":
                    continue
                for field in (
                    "fact_kind",
                    "evidence_strength",
                    "parameter_value_type",
                    "validity_status",
                    "reuse_decision",
                ):
                    self.assertTrue(record[field], f"{record['candidate_id']} missing {field}")

    def test_known_and_missing_report_evidence_are_separated(self):
        payload = json.loads(
            (DATA_DIR / "taichang_technical_bid_candidate_inventory.json").read_text(encoding="utf-8")
        )
        reports = {
            record["report_or_certificate_no"]: record
            for record in payload["records"]
            if record["fact_kind"] == "report_identifier"
        }
        self.assertEqual(
            reports["2024100312005501712"]["reuse_decision"],
            "duplicate_existing_asset_reference_only",
        )
        self.assertEqual(
            reports["2024400312005505333"]["reuse_decision"],
            "needs_original_evidence",
        )


if __name__ == "__main__":
    unittest.main()

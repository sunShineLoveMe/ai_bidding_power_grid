import json
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.rag.ingest_taichang_historical_bid_assets import (  # noqa: E402
    DEFAULT_APPROVED,
    DEFAULT_INVENTORIES,
    _asset_payload,
    _load_approved,
    _load_inventory_rows,
    _safe_chinese_file_name,
    _visible_violations,
)


REPORT_PATH = ROOT_DIR / "docs/development/taichang-bid-v1-data/p1_01_ingestion/taichang_historical_bid_asset_ingestion.json"


class TaichangHistoricalBidAssetIngestionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.approved = _load_approved(DEFAULT_APPROVED)
        cls.inventory = _load_inventory_rows(DEFAULT_INVENTORIES)
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.records = cls.report["records"]

    def test_approved_inventory_is_complete_but_not_blindly_ingested(self):
        self.assertEqual(len(self.approved), 169)
        self.assertEqual(len({row["candidate_id"] for row in self.approved}), 169)
        self.assertTrue(all(row["candidate_id"] in self.inventory for row in self.approved))
        self.assertEqual(len(self.records), 169)
        self.assertLess(
            sum(row["ready_for_database_ingestion"] for row in self.records),
            len(self.records),
            "严格去重后不得仍把全部历史批准候选盲目入库",
        )

    def test_dry_run_detected_existing_and_visual_duplicates(self):
        counts = self.report["metadata"]["disposition_counts"]
        self.assertEqual(counts["same_evidence_existing"], 5)
        self.assertEqual(counts["duplicate_visual_existing"], 2)
        self.assertGreaterEqual(counts["possible_visual_duplicate"], 1)
        blocked = [row for row in self.records if row["dedup_disposition"] != "ready_for_ingestion"]
        self.assertTrue(all(row["ready_for_database_ingestion"] is False for row in blocked))

    def test_visible_file_names_are_chinese_and_hide_internal_enums(self):
        self.assertEqual(_safe_chinese_file_name("泰昌生产制造环境知识资料第001项", ".JPEG"), "泰昌生产制造环境知识资料第001项.jpeg")
        with self.assertRaises(ValueError):
            _safe_chinese_file_name("production_capacity_001", ".jpg")
        for row in self.records:
            self.assertRegex(row["extracted_file_name"], r"[\u4e00-\u9fff]")
            self.assertEqual(
                _visible_violations(
                    [
                        row["title_after_ingestion"],
                        row["source_display_name_after_ingestion"],
                        row.get("category_label"),
                        *(row.get("tags") or []),
                    ]
                ),
                [],
            )

    def test_ready_asset_payload_is_for_knowledge_only_and_never_docx(self):
        row = next(row for row in self.records if row["ready_for_database_ingestion"])
        payload = _asset_payload(row, [0.1, 0.2])
        metadata = payload["metadata"]
        self.assertEqual(metadata["quality_tier"], "knowledge_only")
        self.assertFalse(metadata["allowed_for_bid"])
        self.assertFalse(metadata["formal_bid_ready"])
        self.assertTrue(metadata["exclude_from_docx"])
        self.assertFalse(metadata["parameter_fact_allowed"])
        self.assertEqual(metadata["asset_visual_type"], "word_embedded_rendition")
        self.assertTrue(metadata["requires_fact_cross_check_for_precise_values"])
        self.assertEqual(payload["specs"]["allowed_for_bid"], False)

    def test_report_records_real_database_write_with_complete_embeddings(self):
        metadata = self.report["metadata"]
        self.assertTrue(metadata["execute"])
        self.assertTrue(metadata["database_written"])
        self.assertTrue(metadata["rag_updated"])
        self.assertEqual(metadata["import_counts"], {"imported": 133})
        self.assertEqual(len(self.report["import_results"]), 133)
        self.assertTrue(all(row["status"] == "imported" for row in self.report["import_results"]))


if __name__ == "__main__":
    unittest.main()

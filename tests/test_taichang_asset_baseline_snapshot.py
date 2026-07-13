import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class TaichangAssetBaselineSnapshotTest(unittest.TestCase):
    def test_metadata_completeness_lists_missing_fields(self):
        from scripts.rag.snapshot_taichang_asset_baseline import _record

        record = _record(record_type="knowledge_asset", record_id="a1", source_file="x.pdf")

        self.assertIn("missing:source_domain", record["metadata_completeness"])
        self.assertIn("quality_tier", record["metadata_completeness"])
        self.assertIn("review_status", record["metadata_completeness"])

    def test_explicit_quality_tier_wins(self):
        from scripts.rag.snapshot_taichang_asset_baseline import _quality_tier

        self.assertEqual(
            _quality_tier({"quality_tier": "formal_bid_ready"}, {}, record_type="knowledge_asset"),
            "formal_bid_ready",
        )

    def test_staging_and_raw_records_are_not_formal_by_default(self):
        from scripts.rag.snapshot_taichang_asset_baseline import _quality_tier

        self.assertEqual(_quality_tier({}, {}, record_type="staging_asset_candidate"), "review_only")
        self.assertEqual(_quality_tier({}, {}, record_type="raw_enterprise_file"), "review_only")

    def test_allowed_for_bid_does_not_default_to_true(self):
        from scripts.rag.snapshot_taichang_asset_baseline import _allowed_for_bid

        self.assertFalse(_allowed_for_bid({}, {}, default=False))
        self.assertTrue(_allowed_for_bid({"allowed_for_bid": True}, {}, default=False))


if __name__ == "__main__":
    unittest.main()

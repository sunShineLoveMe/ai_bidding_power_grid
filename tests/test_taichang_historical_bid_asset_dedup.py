import hashlib
import io
import json
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.rag.deduplicate_taichang_historical_bid_assets import (  # noqa: E402
    dhash_bytes,
    hamming_distance,
    image_profile,
    visual_near_match,
)


DATA_DIR = ROOT_DIR / "docs/development/taichang-bid-v1-data"
MATRIX_PATH = DATA_DIR / "asset_dedup_matrix.json"
BASELINE_PATH = DATA_DIR / "current_asset_baseline.json"


def _png(*, mark: bool = False, blank: bool = False) -> bytes:
    image = Image.new("RGB", (400, 600), "white")
    if not blank:
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 50, 360, 550), outline="black", width=3)
        draw.line((80, 120, 320, 120), fill="black", width=4)
        if mark:
            draw.rectangle((280, 480, 320, 520), fill="red")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class TaichangHistoricalBidAssetDedupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        cls.records = cls.payload["records"]
        cls.by_id = {row["candidate_id"]: row for row in cls.records}

    def test_dhash_is_deterministic_and_exact_bytes_stay_exact(self):
        data = _png()
        self.assertEqual(dhash_bytes(data), dhash_bytes(data))
        self.assertEqual(hamming_distance(dhash_bytes(data), dhash_bytes(data)), 0)

    def test_visual_near_match_never_represents_automatic_merge(self):
        left = image_profile(_png())
        right = image_profile(_png(mark=True))
        matched, distance = visual_near_match(left, right, max_distance=64)
        self.assertTrue(matched)
        self.assertIsNotNone(distance)
        # 真实矩阵中的所有感知近似项都只能人工审核。
        near_rows = [row for row in self.records if row["dedup_status"] == "possible_visual_duplicate"]
        self.assertTrue(near_rows)
        self.assertTrue(all(row["manual_review_required"] is True for row in near_rows))
        self.assertTrue(all(row["promotion_eligible"] is False for row in near_rows))

    def test_blank_page_has_visual_protection(self):
        profile = image_profile(_png(blank=True))
        self.assertEqual(profile["protection_reason"], "blank_or_near_blank_page")

    def test_all_896_candidates_are_covered_and_blocked(self):
        metadata = self.payload["metadata"]
        self.assertEqual(metadata["candidate_count"], 896)
        self.assertEqual(len(self.records), 896)
        self.assertTrue(all(row["dedup_status"] for row in self.records))
        self.assertTrue(all(row["quality_tier"] == "review_only" for row in self.records))
        self.assertTrue(all(row["allowed_for_bid"] is False for row in self.records))
        self.assertTrue(all(row["promotion_eligible"] is False for row in self.records))
        self.assertFalse(metadata["database_written"])
        self.assertFalse(metadata["metadata_updated"])
        self.assertFalse(metadata["automatic_merge_performed"])

    def test_known_reports_share_one_evidence_bundle_with_baseline(self):
        known = {
            row["report_or_certificate_no"]: row
            for row in self.records
            if row["report_or_certificate_no"] in {"2024100312005501712", "2024100312005501713"}
        }
        self.assertEqual(set(known), {"2024100312005501712", "2024100312005501713"})
        for row in known.values():
            self.assertEqual(row["dedup_status"], "same_evidence_new_rendition")
            self.assertEqual(row["match_scope"], "existing_baseline")
            self.assertTrue(row["evidence_bundle_id"])
            self.assertTrue(row["manual_review_required"])

    def test_missing_report_evidence_is_not_misclassified_as_existing(self):
        rows = {
            row["report_or_certificate_no"]: row
            for row in self.records
            if row["report_or_certificate_no"] in {"2024400312005505333", "2025200312005503479"}
        }
        self.assertEqual(set(rows), {"2024400312005505333", "2025200312005503479"})
        for row in rows.values():
            self.assertEqual(row["dedup_status"], "new")
            self.assertTrue(row["manual_review_required"])
            self.assertFalse(row["promotion_eligible"])

    def test_project_identifiers_are_conflicts_not_reusable_facts(self):
        rows = [row for row in self.records if row["fact_kind"] in {"project_identifier", "fixed_parameter_id"}]
        self.assertTrue(rows)
        self.assertTrue(all(row["dedup_status"] == "fact_conflict" for row in rows))
        self.assertTrue(all("本次招标文件" in row["decision_reason"] for row in rows))

    def test_exact_duplicates_are_not_ingestion_candidates(self):
        rows = [row for row in self.records if row["dedup_status"] == "duplicate_exact"]
        self.assertTrue(rows)
        self.assertTrue(all(row["promotion_eligible"] is False for row in rows))

    def test_frozen_input_hashes_still_match_files(self):
        input_hashes = self.payload["metadata"]["input_sha256"]
        for raw_path, expected in input_hashes.items():
            path = Path(raw_path)
            if not path.is_absolute():
                path = ROOT_DIR / path
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, expected)
        self.assertIn(str(BASELINE_PATH.relative_to(ROOT_DIR)), input_hashes)


if __name__ == "__main__":
    unittest.main()

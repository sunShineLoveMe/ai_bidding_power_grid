import json
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.rag.classify_taichang_historical_bid_candidates import (  # noqa: E402
    classify,
    tag_dictionary,
    visible_field_violations,
)


DATA_DIR = ROOT_DIR / "docs/development/taichang-bid-v1-data"


class TaichangHistoricalBidCandidateClassificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads((DATA_DIR / "asset_classification_matrix.json").read_text(encoding="utf-8"))
        cls.records = cls.matrix["records"]
        cls.review = json.loads((DATA_DIR / "asset_review_queue.json").read_text(encoding="utf-8"))
        cls.ingestion = json.loads((DATA_DIR / "asset_ingestion_candidates.json").read_text(encoding="utf-8"))

    def test_dictionary_has_chinese_labels_and_promotion_policy(self):
        dictionary = tag_dictionary()
        for mapping_name in (
            "target_libraries",
            "evidence_types",
            "quality_tiers",
            "review_statuses",
            "sensitivity_levels",
            "dedup_statuses",
        ):
            mapping = dictionary[mapping_name]
            self.assertTrue(mapping)
            self.assertTrue(all(any("\u4e00" <= char <= "\u9fff" for char in label) for label in mapping.values()))
        self.assertTrue(dictionary["promotion_policy"]["requires_p0_06_approval"])
        self.assertFalse(dictionary["promotion_policy"]["possible_match_auto_merge_allowed"])

    def test_all_896_candidates_have_required_classification(self):
        self.assertEqual(len(self.records), 896)
        for row in self.records:
            for field in (
                "enterprise",
                "source_domain",
                "target_library",
                "target_library_label",
                "evidence_type",
                "evidence_type_label",
                "quality_tier",
                "review_status",
                "dedup_status_label",
                "title",
                "source_display_name",
                "category_label",
                "description",
            ):
                self.assertNotIn(row[field], (None, ""), f"{row['candidate_id']} missing {field}")
            self.assertFalse(row["fact_source_allowed_for_enterprise"])
            self.assertTrue(
                any("\u4e00" <= char <= "\u9fff" for char in row["dedup_status_label"]),
                row["candidate_id"],
            )

    def test_user_visible_fields_are_clean_chinese_business_names(self):
        for row in self.records:
            self.assertEqual(visible_field_violations(row), [], row["candidate_id"])
            self.assertEqual(row["visible_field_violations"], [])

    def test_exact_duplicates_and_conflicts_are_not_in_review_queue(self):
        statuses = {row["dedup_status"] for row in self.review["records"]}
        self.assertNotIn("duplicate_exact", statuses)
        self.assertNotIn("fact_conflict", statuses)
        self.assertEqual(len(self.review["records"]), 461)

    def test_possible_matches_stay_manual_and_never_ingestion_eligible(self):
        rows = [row for row in self.records if row["dedup_status"].startswith("possible_")]
        self.assertEqual(len(rows), 147)
        self.assertTrue(all(row["review_status"] == "needs_manual_review" for row in rows))
        self.assertTrue(all(row["manual_review_required"] is True for row in rows))
        self.assertTrue(all(row["ingestion_eligible"] is False for row in rows))

    def test_sensitive_material_is_restricted(self):
        rows = [row for row in self.records if row["sensitivity"] in {"sensitive", "restricted"}]
        self.assertTrue(rows)
        self.assertTrue(all(row["quality_tier"] == "restricted" for row in rows))
        self.assertTrue(all(row["ingestion_eligible"] is False for row in rows))

    def test_default_ingestion_candidates_are_empty_without_p0_06_approval(self):
        self.assertEqual(self.ingestion["records"], [])
        self.assertEqual(self.ingestion["metadata"]["approved_candidate_id_count"], 0)
        self.assertEqual(self.ingestion["metadata"]["ingestion_candidate_count"], 0)

    def test_candidate_id_approval_alone_cannot_bypass_quality_gate(self):
        dedup = json.loads((DATA_DIR / "asset_dedup_matrix.json").read_text(encoding="utf-8"))
        technical = json.loads((DATA_DIR / "taichang_technical_bid_candidate_inventory.json").read_text(encoding="utf-8"))
        business = json.loads((DATA_DIR / "taichang_business_bid_candidate_inventory.json").read_text(encoding="utf-8"))
        candidate = next(
            row for row in dedup["records"]
            if row["record_type"] == "media" and row["dedup_status"] == "new"
        )
        result = classify(dedup, [technical, business], approved_ids={candidate["candidate_id"]})
        approved_row = next(row for row in result["records"] if row["candidate_id"] == candidate["candidate_id"])
        self.assertTrue(approved_row["approved_candidate"])
        self.assertFalse(approved_row["ingestion_eligible"])
        self.assertIn("质量等级", approved_row["ingestion_block_reason"])
        self.assertEqual(result["ingestion_candidates"], [])

    def test_product_fact_cannot_be_formal_without_product_family(self):
        rows = [
            row for row in self.records
            if row["target_library"] == "product_library"
            and row["evidence_type"] in {"inspection_report", "product_parameter_table", "product_image"}
            and not row["product_families"]
        ]
        self.assertTrue(all(row["quality_tier"] != "formal_bid_ready" for row in rows))
        self.assertTrue(all(row["ingestion_eligible"] is False for row in rows))


if __name__ == "__main__":
    unittest.main()

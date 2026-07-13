import json
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.rag.build_taichang_evidence_bundles import (  # noqa: E402
    _page_audit,
    build_bundles,
    classify_source,
)


DATA_DIR = ROOT_DIR / "docs/development/taichang-bid-v1-data"
BASELINE_PATH = DATA_DIR / "current_asset_baseline.json"
OUTPUT_PATH = DATA_DIR / "p1_02_evidence_bundles/taichang_evidence_bundles.json"


class TaichangEvidenceBundlesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        cls.payload = build_bundles(baseline)
        cls.bundles = cls.payload["bundles"]
        cls.by_key = {item["business_key"]: item for item in cls.bundles}

    def test_p0_scope_has_one_business_object_per_evidence(self):
        self.assertEqual(self.payload["summary"]["bundle_count"], 16)
        self.assertEqual(len(self.by_key), len(self.bundles))
        self.assertEqual(
            self.payload["summary"]["by_kind"],
            {
                "audit_report": 3,
                "business_license": 1,
                "calibration_certificate": 6,
                "inspection_report": 2,
                "management_system_certificate": 3,
                "project_performance": 1,
            },
        )

    def test_all_primary_files_have_complete_ordered_page_assets(self):
        self.assertEqual(self.payload["summary"]["complete_bundle_count"], 16)
        for bundle in self.bundles:
            self.assertTrue(bundle["page_sequence_complete"], bundle["bundle_title"])
            self.assertEqual(bundle["missing_pages"], [])
            self.assertEqual(bundle["duplicate_pages"], [])
            for source in bundle["primary_sources"]:
                self.assertTrue(source["original_file_exists"])
                self.assertEqual(
                    source["asset_page_sequence"],
                    list(range(1, source["expected_page_count"] + 1)),
                )

    def test_known_reports_are_single_bundles_with_structured_summary(self):
        cases = {
            "report:2024100312005501712": ("MPP电缆保护管", 17),
            "report:2024100312005501713": ("CPVC电缆保护管", 19),
        }
        for key, (product, row_count) in cases.items():
            bundle = self.by_key[key]
            self.assertEqual(bundle["page_count"], 5)
            self.assertEqual(bundle["structured_summary"]["parameter_row_count"], row_count)
            self.assertIn(product, bundle["structured_summary"]["products"])
            self.assertEqual(len(bundle["primary_sources"]), 1)
            self.assertGreaterEqual(len(bundle["renditions"]), 4)
            self.assertTrue(all(not item["formal_page_source"] for item in bundle["renditions"]))

    def test_project_contract_and_award_notice_form_one_bundle(self):
        bundle = self.by_key["project:taichang-tianjin-2022-0322AB-package-2"]
        self.assertEqual(len(bundle["primary_sources"]), 2)
        self.assertEqual([item["component"] for item in bundle["primary_sources"]], ["中标通知书", "供货合同"])
        self.assertEqual(bundle["page_count"], 17)
        summary = bundle["structured_summary"]
        self.assertEqual(summary["structured_evidence_count"], 2)
        self.assertEqual(summary["quantity_m"], 54678.0)
        self.assertEqual(summary["amount_yuan"], 6372409.05)

    def test_expiry_and_conditional_evidence_cannot_auto_enter_bid(self):
        ohs = self.by_key["management-system:ohs"]
        self.assertFalse(ohs["allowed_for_bid"])
        self.assertEqual(ohs["usage_status"], "blocked_expired")
        self.assertEqual(ohs["structured_summary"]["valid_until"], "2026-06-18")
        for bundle in self.bundles:
            if bundle["bundle_kind"] in {"audit_report", "calibration_certificate", "management_system_certificate"}:
                self.assertFalse(bundle["allowed_for_bid"])

    def test_p0_06_uningested_historical_word_and_cross_domain_sources_are_excluded(self):
        self.assertEqual(self.payload["summary"]["p0_06_approved_candidate_count"], 169)
        self.assertEqual(self.payload["summary"]["p0_06_candidates_included_count"], 0)
        for bundle in self.bundles:
            self.assertEqual(bundle["source_domain"], "enterprise_fact")
            self.assertEqual(bundle["enterprise"], "泰昌")
            self.assertFalse(bundle["reference_only"])
            for source in bundle["primary_sources"] + bundle["renditions"]:
                self.assertNotIn("assets/template_words/", source["source_file"])
                self.assertNotIn("河北豪乾", source["source_file"])
                self.assertNotIn("辽宁", source["source_file"])

    def test_qualification_precheck_is_recorded_as_gap_not_fabricated_bundle(self):
        self.assertNotIn("prequalification_result", {item["evidence_type"] for item in self.bundles})
        self.assertEqual(self.payload["gaps"][0]["evidence_type"], "prequalification_result")
        self.assertEqual(self.payload["gaps"][0]["status"], "missing_original_evidence")

    def test_page_audit_detects_missing_and_duplicate_pages(self):
        source_file = self.by_key["report:2024100312005501713"]["primary_sources"][0]["source_file"]
        audit = _page_audit({
            "source_file": source_file,
            "asset_page_numbers": [1, 2, 2, 4, 5],
        })
        self.assertFalse(audit["complete"])
        self.assertEqual(audit["missing_pages"], [3])
        self.assertEqual(audit["duplicate_pages"], [2])
        out_of_order = _page_audit({
            "source_file": source_file,
            "asset_page_numbers": [1, 3, 2, 4, 5],
        })
        self.assertFalse(out_of_order["complete"])
        self.assertFalse(out_of_order["page_order_valid"])

    def test_bundle_ids_are_deterministic(self):
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        second = build_bundles(baseline)
        self.assertEqual(
            [(item["business_key"], item["evidence_bundle_id"]) for item in self.bundles],
            [(item["business_key"], item["evidence_bundle_id"]) for item in second["bundles"]],
        )

    def test_checked_in_output_matches_builder(self):
        checked_in = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(checked_in["summary"], self.payload["summary"])
        self.assertEqual(checked_in["bundles"], self.payload["bundles"])
        self.assertEqual(checked_in["pages"], self.payload["pages"])

    def test_source_classifier_does_not_expand_to_credit_report(self):
        result = classify_source("some/河北泰昌电力器材科技有限公司报告.pdf", "business_license")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

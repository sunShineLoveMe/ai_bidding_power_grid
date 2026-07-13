import json
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.rag.extract_taichang_historical_bid_tables import (  # noqa: E402
    DEFAULT_BUSINESS_DOCX,
    DEFAULT_EXISTING_PARAMETER_ROWS,
    DEFAULT_TECHNICAL_DOCX,
    build_evidence_register,
    build_technical_parameter_rows,
    extract_raw_tables,
    table_policy,
)


class TaichangHistoricalBidTableExtractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.technical = extract_raw_tables(DEFAULT_TECHNICAL_DOCX, "technical")
        cls.business = extract_raw_tables(DEFAULT_BUSINESS_DOCX, "business")
        cls.parameters = build_technical_parameter_rows(cls.technical)
        cls.existing = json.loads(DEFAULT_EXISTING_PARAMETER_ROWS.read_text(encoding="utf-8"))
        cls.evidence = build_evidence_register(cls.technical, cls.existing)

    def test_real_word_table_counts_and_source_hashes_are_stable(self):
        self.assertEqual(len(self.technical), 10)
        self.assertEqual(len(self.business), 4)
        self.assertEqual(
            self.technical[0]["source_file_sha256"],
            "2dd987a9742f92b8d81f3c490ce40958ceb7f664d823af17c300f755a030d80d",
        )
        self.assertEqual(
            self.business[0]["source_file_sha256"],
            "62423abdb77b1a54201d7a641d19d4172a6feffc8b52a911662b6db38d149135",
        )
        self.assertTrue(all(row["parser"] == "native_docx_ooxml" for row in self.technical + self.business))
        self.assertTrue(all(row["mineru_invoked"] is False for row in self.technical + self.business))

    def test_xinjiang_conductor_parameter_table_is_not_taichang_product_fact(self):
        table = self.technical[1]
        self.assertIn("1kV 架空绝缘导线 - 新疆", table["rows"][0][0])
        self.assertIn("SL265A-1402005-0007", table["rows"][0][0])
        placeholders = [row for row in self.parameters if row["source_table_index"] == 2]
        self.assertEqual(len(placeholders), 3)
        self.assertTrue(all(row["raw_unit"] == "" for row in placeholders))
        self.assertTrue(all(row["numeric_value"] is None for row in placeholders))
        self.assertTrue(all(row["fact_status"] == "not_a_parameter_fact" for row in placeholders))
        self.assertTrue(all(row["parameter_fact_allowed"] is False for row in placeholders))

    def test_dn_and_phi_are_preserved_without_mm_inference(self):
        pvc = [row for row in self.parameters if row["source_table_index"] == 4]
        spares = [row for row in self.parameters if row["source_table_index"] == 6]
        self.assertEqual([row["nominal_designation_raw"] for row in pvc], ["DN32", "DN50", "DN75", "DN110", "DN150"])
        self.assertTrue(all(row["raw_unit"] == "DN" for row in pvc))
        self.assertTrue(all(row["normalized_unit"] == "DN" for row in pvc))
        self.assertTrue(all(row["unit_conversion_performed"] is False for row in pvc + spares))
        self.assertTrue(all(row["raw_unit"] == "φ" for row in spares))
        self.assertNotIn("mm", {row["normalized_unit"] for row in self.parameters})

    def test_quantity_text_is_not_coerced_to_numeric_value(self):
        spares = [row for row in self.parameters if row["source_table_index"] == 6]
        self.assertEqual(len(spares), 12)
        self.assertTrue(all(row["quantity_unit"] == "米" for row in spares))
        self.assertTrue(all(row["quantity_raw"] == "以实际数量为准" for row in spares))
        self.assertTrue(all(row["quantity_numeric"] is None for row in spares))
        self.assertEqual(sum(row["fact_status"] == "partial_match_existing_inspection_report" for row in spares), 2)

    def test_only_two_report_numbers_link_to_existing_original_evidence(self):
        reports = {row["report_number"]: row for row in self.evidence if row["record_kind"] == "inspection_report_registry"}
        self.assertEqual(set(reports), {"2024100312005501712", "2024100312005501713", "2024400312005505333", "2025200312005503479"})
        self.assertEqual(reports["2024100312005501712"]["fact_status"], "verified_existing_report_number")
        self.assertEqual(reports["2024100312005501713"]["duplicate_action"], "link_existing_evidence_do_not_reingest")
        self.assertEqual(reports["2024400312005505333"]["fact_status"], "unverified_historical_report_claim")
        self.assertFalse(reports["2025200312005503479"]["fact_source_allowed_for_enterprise"])

    def test_expired_certificate_and_sensitive_tables_are_blocked(self):
        certificates = {row["certificate_number"]: row for row in self.evidence if row["record_kind"] == "management_system_certificate_claim"}
        self.assertEqual(certificates["626023S10219R0"]["validity_status"], "expired")
        restricted = []
        for table in self.technical + self.business:
            policy = table_policy(table)
            if policy["sensitivity"] == "restricted":
                restricted.append((table["bid_volume"], table["table_index"]))
            self.assertFalse(policy["fact_source_allowed_for_enterprise"])
            self.assertFalse(policy["allowed_for_bid"])
        self.assertEqual(restricted, [("technical", 8), ("business", 2), ("business", 3), ("business", 4)])

    def test_historical_candidates_never_override_report_parameter_facts(self):
        self.assertEqual(len(self.parameters), 20)
        self.assertTrue(all(row["fact_source_allowed_for_enterprise"] is False for row in self.parameters))
        self.assertTrue(all(row["parameter_fact_allowed"] is False for row in self.parameters))
        self.assertTrue(all(row["requires_original_evidence"] is True for row in self.parameters))


if __name__ == "__main__":
    unittest.main()

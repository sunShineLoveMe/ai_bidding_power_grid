import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/rag/build_taichang_chapter_evidence_mapping.py"
OUTPUT_DIR = ROOT / "docs/development/taichang-bid-v1-data/p1_04_chapter_evidence_mapping"
MAPPING_FILE = OUTPUT_DIR / "taichang_bid_evidence_mapping.json"
EVIDENCE_FILE = ROOT / "docs/development/taichang-bid-v1-data/p1_02_evidence_bundles/taichang_evidence_bundles.json"


class TaichangChapterEvidenceMappingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            [str(ROOT / ".venv/bin/python"), str(SCRIPT)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.payload = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
        cls.mapping = {row["mapping_id"]: row for row in cls.payload["mappings"]}

    def test_summary_and_required_volumes(self):
        summary = self.payload["summary"]
        self.assertEqual(summary["mapping_count"], 19)
        self.assertEqual(summary["technical_mapping_count"], 12)
        self.assertEqual(summary["business_mapping_count"], 7)
        self.assertEqual(summary["existing_count"], 5)
        self.assertEqual(summary["database_writes"], 0)
        self.assertEqual(summary["asset_copies"], 0)

    def test_existing_material_always_locates_fact_or_evidence(self):
        existing = [row for row in self.payload["mappings"] if row["existing_material"]]
        self.assertTrue(existing)
        for row in existing:
            self.assertTrue(
                row["fact_refs"] or row["evidence_bundle_ids"] or row["resolved_knowledge_asset_candidate_ids"],
                row["mapping_id"],
            )

    def test_all_evidence_bundle_ids_exist_and_are_reused(self):
        evidence = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
        known = {row["evidence_bundle_id"] for row in evidence["bundles"]}
        referenced = [bundle_id for row in self.payload["mappings"] for bundle_id in row["evidence_bundle_ids"]]
        self.assertTrue(set(referenced) <= known)
        self.assertGreater(len(referenced), len(set(referenced)))
        self.assertEqual(self.payload["summary"]["asset_copies"], 0)

    def test_mapping_uses_semantic_keys_without_fixed_chapter_numbers(self):
        self.assertEqual(self.payload["mapping_mode"], "semantic_dynamic_project_skeleton")
        self.assertFalse(self.payload["fixed_chapter_numbers"])
        for row in self.payload["mappings"]:
            self.assertIsNone(row["chapter_match"]["fixed_chapter_number"])
            aliases = " ".join(row["chapter_match"]["aliases"])
            self.assertIsNone(re.search(r"(^|\D)\d+(?:\.\d+)+(?=\D|$)", aliases), row["mapping_id"])

    def test_product_family_gaps_do_not_become_formal_facts(self):
        for mapping_id in ("TECH-PROCESS-NHAP", "TECH-PROCESS-UPVC"):
            row = self.mapping[mapping_id]
            self.assertEqual(row["material_status"], "missing_evidence")
            self.assertFalse(row["existing_material"])
            self.assertEqual(row["evidence_bundle_ids"], [])
            self.assertIn("不得生成正式参数", "".join(row["fact_refs"][0]["usage"]))

    def test_expired_certificate_and_restricted_personnel_are_excluded(self):
        serialized = json.dumps(self.payload, ensure_ascii=False)
        self.assertNotIn("management-system:ohs", serialized)
        self.assertNotIn("taichang-evidence-68219d67c5feb3ed96a4", serialized)
        self.assertNotRegex(serialized, r"T[0-9X]{16,20}")
        self.assertEqual(self.payload["source_snapshot"]["p1_03_restricted_rows_included"], 0)

    def test_authorization_is_manual_placeholder_only(self):
        row = self.mapping["BUS-AUTHORIZATION-SIGNATURE"]
        self.assertEqual(row["material_status"], "manual_confirmation")
        self.assertFalse(row["existing_material"])
        self.assertEqual(row["fact_refs"], [])
        self.assertEqual(row["evidence_bundle_ids"], [])
        self.assertIn("不得自动签字、盖章", row["generation_policy"])

    def test_service_commitments_are_not_invented(self):
        row = self.mapping["TECH-SERVICE-AFTERSALES"]
        self.assertEqual(row["material_status"], "partial")
        self.assertEqual(row["fact_refs"], [])
        self.assertIn("尚无独立核验", "".join(row["blockers"]))
        self.assertIn("质保期限", row["customer_confirmation_fields"])

    def test_generation_is_deterministic_except_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                [str(ROOT / ".venv/bin/python"), str(SCRIPT), "--output-dir", tmp],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            second = json.loads((Path(tmp) / "taichang_bid_evidence_mapping.json").read_text(encoding="utf-8"))
        self.assertEqual(self.payload["summary"], second["summary"])
        self.assertEqual(self.payload["mappings"], second["mappings"])


if __name__ == "__main__":
    unittest.main()

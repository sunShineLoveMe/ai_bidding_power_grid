import unittest

from scripts.rag.customer_metadata_policy import (
    normalize_customer_record_metadata,
    should_supersede,
)


class CustomerMetadataPolicyTest(unittest.TestCase):
    def _record(self, metadata):
        return {
            "source_file": "rag_seed/power_grid_resources/05_enterprise_documents/taichang/license.pdf",
            "doc_role": "enterprise_evidence",
            "sha256": "a" * 64,
            "metadata": {
                "seed_corpus": "power_grid_customer_corpus",
                "doc_version": 1,
                "source_file": "rag_seed/power_grid_resources/05_enterprise_documents/taichang/license.pdf",
                **metadata,
            },
        }

    def test_enterprise_fact_requires_fact_boundary_and_gets_citable_policy(self):
        metadata, warnings, errors = normalize_customer_record_metadata(
            self._record({
                "source_domain": "enterprise_fact",
                "enterprise": "泰昌",
                "doc_owner": "泰昌",
                "reference_only": False,
                "fact_source_allowed_for_enterprise": True,
            })
        )

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(metadata["citation_policy"], "enterprise_fact_citable")
        self.assertEqual(metadata["authority_level"], "enterprise_fact")
        self.assertEqual(metadata["source_sha256"], "a" * 64)
        self.assertTrue(metadata["doc_identity_key"])

    def test_tender_requirement_legacy_record_gets_safe_defaults(self):
        metadata, _warnings, errors = normalize_customer_record_metadata(
            self._record({
                "province": "辽宁",
                "doc_role": "technical_spec",
                "package_code": "2225AC",
            })
        )

        self.assertEqual(errors, [])
        self.assertEqual(metadata["source_domain"], "tender_requirement")
        self.assertEqual(metadata["reference_only"], False)
        self.assertEqual(metadata["fact_source_allowed_for_enterprise"], False)
        self.assertEqual(metadata["citation_policy"], "tender_requirement_citable")

    def test_reference_template_cannot_be_enterprise_fact_source(self):
        metadata, _warnings, errors = normalize_customer_record_metadata(
            self._record({
                "source_domain": "reference_template",
                "doc_owner": "河北豪乾电气设备科技有限公司",
                "reference_only": True,
                "fact_source_allowed_for_enterprise": False,
            })
        )

        self.assertEqual(errors, [])
        self.assertEqual(metadata["citation_policy"], "reference_style_only")
        self.assertEqual(metadata["authority_level"], "reference_template")

    def test_missing_version_or_sha_blocks_ingestion(self):
        record = self._record({
            "source_domain": "enterprise_fact",
            "enterprise": "泰昌",
            "doc_owner": "泰昌",
            "reference_only": False,
            "fact_source_allowed_for_enterprise": True,
        })
        record["sha256"] = ""
        record["metadata"].pop("doc_version")

        _metadata, _warnings, errors = normalize_customer_record_metadata(record)

        self.assertIn("missing doc_version", errors)
        self.assertIn("missing source sha256", errors)

    def test_newer_document_supersedes_same_identity_different_content(self):
        existing = {
            "doc_identity_key": "same-doc",
            "doc_version": 1,
            "source_sha256": "old",
            "status": "indexed",
        }
        new = {
            "doc_identity_key": "same-doc",
            "doc_version": 2,
            "source_sha256": "new",
        }

        self.assertTrue(should_supersede(existing, new))

    def test_same_content_or_different_identity_does_not_supersede(self):
        self.assertFalse(should_supersede(
            {"doc_identity_key": "same-doc", "doc_version": 1, "source_sha256": "same"},
            {"doc_identity_key": "same-doc", "doc_version": 2, "source_sha256": "same"},
        ))
        self.assertFalse(should_supersede(
            {"doc_identity_key": "other-doc", "doc_version": 1, "source_sha256": "old"},
            {"doc_identity_key": "same-doc", "doc_version": 2, "source_sha256": "new"},
        ))


if __name__ == "__main__":
    unittest.main()


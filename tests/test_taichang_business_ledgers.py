import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/development/taichang-bid-v1-data/p1_03_business_ledgers/taichang_p1_03_manifest.json"
PARAMETERS = ROOT / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/taichang_product_parameters/taichang_product_parameter_rows.json"


class TaichangBusinessLedgersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/rag/build_taichang_business_ledgers.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.rows = cls.payload["rows"]

    def test_counts_and_business_keys_are_stable(self):
        summary = self.payload["summary"]
        self.assertEqual(summary["business_ledger_rows"], 84)
        self.assertEqual(summary["published_rows"], 84)
        self.assertEqual(summary["private_project_visible_rows"], 84)
        self.assertEqual(summary["privacy_blocked_rows"], 0)
        self.assertEqual(summary["verified_product_parameter_rows"], 36)
        self.assertEqual(summary["project_performance_evidence_rows"], 2)
        self.assertEqual(summary["evidence_bundles"], 16)
        keys = [row["business_key"] for row in self.rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_equipment_uses_current_original_calibration_certificate(self):
        row = next(row for row in self.rows if row.get("equipment_name") == "微机控制电子万能试验机")
        self.assertEqual(row["equipment_model"], "WDW-1")
        self.assertEqual(row["equipment_no"], "TC-8")
        self.assertEqual(row["calibration_certificate_no"], "GL2605LX02282")
        self.assertEqual(row["calibration_date"], "2026-05-26")
        self.assertEqual(row["recalibration_due"], "2027-05-25")
        self.assertEqual(row["source_page"], 6)

    def test_expired_management_certificate_is_blocked(self):
        row = next(row for row in self.rows if row.get("certificate_name") == "职业健康安全管理体系认证证书")
        self.assertEqual(row["certificate_no"], "626023S10219R0")
        self.assertEqual(row["validity_status"], "expired")
        self.assertEqual(row["usage_status"], "blocked_expired")

    def test_audit_report_numbers_preserve_missing_2024_value(self):
        audit = {row["audit_year"]: row for row in self.rows if row.get("ledger_type") == "audit_report"}
        self.assertEqual(audit["2023"]["report_no"], "世仁审字〔2024〕第VE-73号")
        self.assertEqual(audit["2024"]["report_no"], "")
        self.assertEqual(audit["2024"]["report_no_status"], "needs_manual_review")
        self.assertEqual(audit["2025"]["report_no"], "世仁审字〔2026〕第St-050号")

    def test_personnel_details_are_included_for_private_project_queries(self):
        roster = [row for row in self.rows if row.get("ledger_type") == "personnel_roster"]
        certificates = [row for row in self.rows if row.get("ledger_type") == "personnel_certificate"]
        self.assertEqual(len(roster), 65)
        self.assertEqual(len(certificates), 2)
        self.assertTrue(all(row.get("quality_tier") == "knowledge_only" for row in [*roster, *certificates]))
        self.assertTrue(all(row.get("rag_visibility") == "taichang_private_project" for row in [*roster, *certificates]))
        certificate_by_name = {row["person_name"]: row for row in certificates}
        self.assertEqual(certificate_by_name["陈仙瑞"]["certificate_no"], "T130602197408170641")
        self.assertEqual(certificate_by_name["晁坤琳"]["certificate_no"], "T13060219980525061X")

        from backend.rag.business_ledgers import search_taichang_business_ledger_contexts

        contexts = search_taichang_business_ledger_contexts("泰昌陈仙瑞和晁坤琳的岗位、人员证书编号、准操项目和有效期是什么？")
        content = "\n".join(item["content"] for item in contexts)
        self.assertIn("陈仙瑞", content)
        self.assertIn("高压试验员", content)
        self.assertIn("T130602197408170641", content)
        self.assertIn("晁坤琳", content)
        self.assertIn("T13060219980525061X", content)

        roster_contexts = search_taichang_business_ledger_contexts("请列出泰昌公司人员花名册全部姓名、岗位、社保和劳动合同记录。")
        roster_content = "\n".join(item["content"] for item in roster_contexts)
        self.assertIn("共 65 条", roster_content)
        self.assertIn("晁坤琳｜董事长、试验员", roster_content)

    def test_missing_report_and_intellectual_property_are_explicitly_blocked(self):
        from backend.rag.business_ledgers import search_taichang_business_ledger_contexts

        reports = search_taichang_business_ledger_contexts("泰昌N-HAP和UPVC检验报告是否有原始报告？")
        report_content = "\n".join(item["content"] for item in reports)
        self.assertIn("2024400312005505333", report_content)
        self.assertIn("2025200312005503479", report_content)
        self.assertIn("不得生成正式参数", report_content)

        ip_contexts = search_taichang_business_ledger_contexts("泰昌有哪些专利和软件著作权？")
        self.assertEqual(len(ip_contexts), 1)
        self.assertIn("不得转为泰昌企业事实", ip_contexts[0]["content"])
        self.assertFalse(ip_contexts[0]["metadata"]["fact_source_allowed_for_enterprise"])

    def test_query_returns_equipment_source_page_and_certificate_status(self):
        from backend.rag.business_ledgers import search_taichang_business_ledger_contexts

        equipment = search_taichang_business_ledger_contexts("泰昌微机控制电子万能试验机的校准证书和复校日期是什么？")
        self.assertEqual(equipment[0]["retrieval_source"], "structured_business_ledger_json")
        self.assertIn("GL2605LX02282", equipment[0]["content"])
        self.assertIn("来源页码：第6页", equipment[0]["content"])

        certificate = search_taichang_business_ledger_contexts("泰昌职业健康安全管理体系认证证书是否有效？")
        self.assertIn("已过期", certificate[0]["content"])
        self.assertIn("626023S10219R0", certificate[0]["content"])

    def test_curation_keeps_multi_year_audits_and_both_missing_report_gaps(self):
        from backend.api.knowledge import _curate_pilot_enterprise_contexts
        from backend.rag.business_ledgers import search_taichang_business_ledger_contexts
        from backend.rag.display_names import sanitize_source_contexts

        audit_query = "泰昌2023、2024、2025年审计报告编号和完整性如何？"
        audit = sanitize_source_contexts(search_taichang_business_ledger_contexts(audit_query))
        self.assertEqual(len(_curate_pilot_enterprise_contexts(audit, limit=3, query=audit_query)), 3)

        report_query = "泰昌N-HAP和UPVC检验报告是否有原始报告？"
        reports = sanitize_source_contexts(search_taichang_business_ledger_contexts(report_query))
        curated = _curate_pilot_enterprise_contexts(reports, limit=3, query=report_query)
        content = "\n".join(row["content"] for row in curated)
        self.assertEqual(len(curated), 2)
        self.assertIn("2024400312005505333", content)
        self.assertIn("2025200312005503479", content)
        self.assertTrue(all(row["metadata"].get("is_fact_gap") for row in curated))

    def test_product_parameter_rows_keep_original_source_pages(self):
        rows = json.loads(PARAMETERS.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 36)
        self.assertEqual({row.get("source_page") for row in rows}, {3, 4})


if __name__ == "__main__":
    unittest.main()

import unittest


class TechnicalDeviationReportTest(unittest.TestCase):
    def test_missing_response_is_pending(self):
        from scripts.rag.generate_technical_deviation_report import judge_deviation

        result = judge_deviation("≥25MPa", "")

        self.assertEqual(result["deviation_status"], "pending_response")
        self.assertEqual(result["risk_level"], "medium")

    def test_numeric_minimum_negative_deviation(self):
        from scripts.rag.generate_technical_deviation_report import judge_deviation

        result = judge_deviation("≥25MPa", "22MPa")

        self.assertEqual(result["deviation_status"], "negative_deviation")
        self.assertEqual(result["risk_level"], "high")

    def test_numeric_minimum_positive_deviation(self):
        from scripts.rag.generate_technical_deviation_report import judge_deviation

        result = judge_deviation("≥25MPa", "30MPa")

        self.assertEqual(result["deviation_status"], "positive_deviation")
        self.assertEqual(result["risk_level"], "low")

    def test_compliance_text_is_no_deviation(self):
        from scripts.rag.generate_technical_deviation_report import judge_deviation

        result = judge_deviation("参照通用部分5.技术要求", "满足招标文件要求")

        self.assertEqual(result["deviation_status"], "no_deviation")
        self.assertEqual(result["risk_level"], "low")

    def test_unstructured_mismatch_needs_manual_review(self):
        from scripts.rag.generate_technical_deviation_report import judge_deviation

        result = judge_deviation("红色外观", "蓝色外观")

        self.assertEqual(result["deviation_status"], "manual_review")
        self.assertEqual(result["risk_level"], "medium")

    def test_build_rows_prefers_project_required_value_and_response(self):
        from scripts.rag.generate_technical_deviation_report import build_deviation_rows

        rows = build_deviation_rows([
            {
                "ingestion_batch_id": "batch",
                "material_category": "电缆保护管MPP",
                "parameter_name": "拉伸强度",
                "project_required_value": "≥25MPa",
                "bidder_response_value": "25MPa",
                "row_data": {"项目": "拉伸强度"},
            }
        ])

        self.assertEqual(rows[0]["required_value"], "≥25MPa")
        self.assertEqual(rows[0]["response_value"], "25MPa")
        self.assertEqual(rows[0]["deviation_status"], "no_deviation")


if __name__ == "__main__":
    unittest.main()

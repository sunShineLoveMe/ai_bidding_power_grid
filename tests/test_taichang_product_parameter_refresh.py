import unittest


class TaichangProductParameterRefreshTest(unittest.TestCase):
    def test_validate_extraction_report_accepts_current_shape(self):
        from scripts.rag.run_taichang_product_parameter_refresh import _validate_extraction_report

        report = {
            "parsed_documents": 2,
            "parameter_rows": 36,
            "by_product_family": {
                "CPVC电缆保护管": 19,
                "MPP电缆保护管": 17,
            },
            "qa_reference": {"scope": "qa_only_not_coverage_judgement"},
        }

        self.assertEqual(_validate_extraction_report(report), [])

    def test_validate_extraction_report_rejects_missing_boundary(self):
        from scripts.rag.run_taichang_product_parameter_refresh import _validate_extraction_report

        report = {
            "parsed_documents": 2,
            "parameter_rows": 36,
            "by_product_family": {
                "CPVC电缆保护管": 19,
                "MPP电缆保护管": 17,
            },
            "qa_reference": {"scope": "coverage_judgement"},
        }

        failures = _validate_extraction_report(report)

        self.assertTrue(any("qa_reference" in failure for failure in failures))

    def test_validate_stream_results_requires_key_values(self):
        from scripts.rag.run_taichang_product_parameter_refresh import _validate_stream_results

        results = {
            "mpp_ring_stiffness": {"done": True, "errors": [], "answer": "环刚度 66.40 kN/m2"},
            "cpvc_diameter_wall": {"done": True, "errors": [], "answer": "平均内径 250.2~250.4，壁厚 15.2~15.3"},
        }

        self.assertEqual(_validate_stream_results(results), [])


if __name__ == "__main__":
    unittest.main()

import os
import unittest


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


class IncrementalRegressionGateTest(unittest.TestCase):
    def test_gate_passes_when_required_metrics_meet_thresholds(self):
        from scripts.rag.run_incremental_regression_gate import DEFAULT_THRESHOLDS, _check_gate

        passing = {
            "base_qwen3": {
                "recall_at_5": 0.9667,
                "role_accuracy_top1": 1.0,
                "avg_cross_role_ratio": 0.0,
            },
            "customer_qwen3": {
                "recall_at_5": 1.0,
                "role_accuracy_top1": 1.0,
                "forbidden_hit_rate": 0.0,
                "avg_cross_role_ratio": 0.0,
                "rerank_scored_cases": 30,
            },
        }

        self.assertEqual(_check_gate(passing, DEFAULT_THRESHOLDS), [])

    def test_gate_fails_when_customer_rerank_did_not_run(self):
        from scripts.rag.run_incremental_regression_gate import DEFAULT_THRESHOLDS, _check_gate

        failing = {
            "base_qwen3": {
                "recall_at_5": 0.9667,
                "role_accuracy_top1": 1.0,
                "avg_cross_role_ratio": 0.0,
            },
            "customer_qwen3": {
                "recall_at_5": 1.0,
                "role_accuracy_top1": 1.0,
                "forbidden_hit_rate": 0.0,
                "avg_cross_role_ratio": 0.0,
                "rerank_scored_cases": 0,
            },
        }

        failures = _check_gate(failing, DEFAULT_THRESHOLDS)

        self.assertTrue(any("rerank scores" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()

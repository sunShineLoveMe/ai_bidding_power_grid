import unittest
from unittest.mock import patch

from backend.ai.semantic_compliance import build_semantic_compliance_report, select_semantic_review_rows


class SemanticComplianceReviewTest(unittest.TestCase):
    def test_selects_high_value_rows_first(self):
        rows = [
            {"id": "covered-req", "category": "要求条款", "status": "covered", "importance": "medium"},
            {"id": "missing-risk", "category": "风险项", "status": "missing", "importance": "high"},
            {"id": "partial-score", "category": "评分项", "status": "partial", "importance": "10分"},
        ]

        selected = select_semantic_review_rows(rows, limit=2)

        self.assertEqual([row["id"] for row in selected], ["missing-risk", "partial-score"])

    def test_build_report_uses_llm_result(self):
        payload = {
            "project": {"project_name": "测试工程"},
            "analysis": {"project_meta": {}},
            "requirements": [],
            "scoringItems": [
                {"id": "score-1", "item": "施工组织设计应包含质量安全保证措施。", "score": 10}
            ],
            "risks": [],
            "sections": [
                {
                    "id": "section-1",
                    "title": "施工组织设计",
                    "content": "本章已建立质量安全保证体系，明确安全检查、质量验收和整改闭环。",
                    "metadata": {"volume_type": "technical"},
                }
            ],
        }
        llm_payload = {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": '{"status":"covered","evidence":"已建立质量安全保证体系","confidence":0.86,"weight":"10分","suggestion":"补充页码索引。"}'
                        }
                    }
                ]
            }
        }

        with patch("backend.ai.compliance_checker.get_project_interpretation", return_value=payload), patch(
            "backend.ai.semantic_compliance.get_project_interpretation", return_value=payload
        ), patch("backend.ai.semantic_compliance.call_dashscope_api", return_value=llm_payload):
            report = build_semantic_compliance_report("project-id", use_llm=True)

        self.assertEqual(report["summary"]["total"], 1)
        self.assertEqual(report["reviews"][0]["status"], "covered")
        self.assertEqual(report["reviews"][0]["confidence"], 0.86)
        self.assertTrue(report["reviews"][0]["llmReviewed"])

    def test_llm_failure_falls_back_to_heuristic_review(self):
        payload = {
            "project": {"project_name": "测试工程"},
            "analysis": {"project_meta": {}},
            "requirements": [
                {"id": "req-1", "content": "投标人须提供安全生产许可证。", "priority": "high"}
            ],
            "scoringItems": [],
            "risks": [],
            "sections": [
                {
                    "id": "section-1",
                    "title": "资格审查资料",
                    "content": "本章列明安全生产许可证作为资格审查材料，并保留证书编号待补充。",
                    "metadata": {"volume_type": "qualification"},
                }
            ],
        }

        with patch("backend.ai.compliance_checker.get_project_interpretation", return_value=payload), patch(
            "backend.ai.semantic_compliance.get_project_interpretation", return_value=payload
        ), patch("backend.ai.semantic_compliance.call_dashscope_api", side_effect=RuntimeError("provider unavailable")):
            report = build_semantic_compliance_report("project-id", use_llm=True)

        self.assertEqual(report["summary"]["total"], 1)
        self.assertFalse(report["reviews"][0]["llmReviewed"])
        self.assertIn("规则兜底", report["reviews"][0]["suggestion"])


if __name__ == "__main__":
    unittest.main()

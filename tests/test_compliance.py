import unittest
from unittest.mock import patch

from backend.ai.compliance_checker import build_compliance_report


class ComplianceCheckerRegressionTest(unittest.TestCase):
    def test_generated_content_increases_requirement_coverage(self):
        payload = {
            "project": {"project_name": "测试水库工程"},
            "requirements": [
                {
                    "id": "req-1",
                    "content": "投标人须提供安全生产许可证和水利水电工程施工资质证书。",
                    "requirement_type": "qualification",
                    "priority": "high",
                }
            ],
            "scoringItems": [],
            "risks": [],
            "sections": [
                {
                    "id": "section-1",
                    "title": "资格审查资料",
                    "level": 1,
                    "content": "投标人须提供安全生产许可证和水利水电工程施工资质证书。我方已提供安全生产许可证，并附水利水电工程施工资质证书复印件，确保资格审查资料完整、真实、有效，满足招标文件资格审查要求。",
                    "mapped_requirements": [],
                    "metadata": {"volume_type": "qualification"},
                }
            ],
        }

        with patch("backend.ai.compliance_checker.get_project_interpretation", return_value=payload):
            report = build_compliance_report("project-smoke")

        self.assertEqual(report["summary"]["total"], 1)
        self.assertEqual(report["summary"]["covered"], 1)
        self.assertEqual(report["summary"]["missing"], 0)
        self.assertEqual(report["summary"]["percent"], 100)

    def test_missing_high_risk_item_is_reported(self):
        payload = {
            "project": {"project_name": "测试水库工程"},
            "requirements": [],
            "scoringItems": [],
            "risks": [
                {
                    "id": "risk-1",
                    "content": "未按招标文件要求缴纳投标保证金将被否决投标。",
                    "risk_level": "high",
                    "risk_type": "否决",
                }
            ],
            "sections": [
                {
                    "id": "section-1",
                    "title": "施工组织设计",
                    "level": 1,
                    "content": "本章说明施工组织、质量安全和进度计划。",
                    "metadata": {"volume_type": "technical"},
                }
            ],
        }

        with patch("backend.ai.compliance_checker.get_project_interpretation", return_value=payload):
            report = build_compliance_report("project-smoke")

        self.assertEqual(report["summary"]["missing"], 1)
        self.assertEqual(report["summary"]["highRiskMissing"], 1)
        self.assertEqual(report["rows"][0]["status"], "missing")

    def test_internal_volume_scope_reports_qualification_only(self):
        payload = {
            "project": {"project_name": "测试水库工程"},
            "requirements": [
                {
                    "id": "req-qualification",
                    "content": "投标人须提供水利水电工程施工资质证书。",
                    "requirement_type": "qualification",
                    "priority": "high",
                },
                {
                    "id": "req-technical",
                    "content": "施工组织设计应说明坝基防渗处理施工工艺。",
                    "requirement_type": "technical",
                    "priority": "high",
                },
            ],
            "scoringItems": [],
            "risks": [],
            "sections": [
                {
                    "id": "qualification-section",
                    "title": "资格审查资料",
                    "content": "本章提供水利水电工程施工资质证书，满足资格审查要求。",
                    "mapped_requirements": ["投标人须提供水利水电工程施工资质证书。"],
                    "metadata": {"volume_type": "qualification"},
                },
                {
                    "id": "technical-section",
                    "title": "施工组织设计",
                    "content": "本章说明坝基防渗处理施工工艺、质量控制和进度计划。",
                    "mapped_requirements": ["施工组织设计应说明坝基防渗处理施工工艺。"],
                    "metadata": {"volume_type": "technical"},
                },
            ],
        }

        with patch("backend.ai.compliance_checker.get_project_interpretation", return_value=payload):
            report = build_compliance_report("project-smoke", volume_type="qualification")

        self.assertEqual(report["summary"]["volumeType"], "qualification")
        self.assertEqual(report["summary"]["total"], 1)
        self.assertEqual(report["summary"]["covered"], 1)
        self.assertEqual(report["rows"][0]["volumeType"], "qualification")
        self.assertTrue(any(item["volumeType"] == "technical" for item in report["volumeSummaries"]))

    def test_business_delivery_scope_includes_qualification_and_price_risks(self):
        payload = {
            "project": {"project_name": "测试水库工程"},
            "requirements": [
                {
                    "id": "req-price",
                    "content": "报价文件须按工程量清单填报投标总价。",
                    "requirement_type": "price",
                    "priority": "medium",
                }
            ],
            "scoringItems": [],
            "risks": [
                {
                    "id": "risk-qualification",
                    "content": "未提供项目经理人员证书将导致资格审查不通过。",
                    "risk_level": "high",
                    "risk_type": "否决",
                }
            ],
            "sections": [
                {
                    "id": "business-section",
                    "title": "商务响应文件",
                    "content": "本章响应合同、付款和承诺要求。",
                    "metadata": {"volume_type": "business"},
                }
            ],
        }

        with patch("backend.ai.compliance_checker.get_project_interpretation", return_value=payload):
            report = build_compliance_report("project-smoke", volume_type="business")

        self.assertEqual(report["summary"]["volumeType"], "business")
        self.assertEqual(report["summary"]["total"], 2)
        self.assertEqual({row["volumeType"] for row in report["rows"]}, {"price", "qualification"})
        self.assertEqual(report["summary"]["highRiskMissing"], 1)


if __name__ == "__main__":
    unittest.main()

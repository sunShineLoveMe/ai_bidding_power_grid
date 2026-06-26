import os
import unittest
from unittest.mock import patch

os.environ.setdefault("APP_AUTH_ENABLED", "false")


class FormalBidCheckTest(unittest.TestCase):
    def _payload(self):
        return {
            "project": {"id": "11111111-1111-1111-1111-111111111111", "project_name": "国网辽宁电力电缆保护管采购"},
            "requirements": [{"id": "req-1", "content": "投标文件应提供技术偏差表。", "priority": "high"}],
            "risks": [{"id": "risk-1", "content": "未按要求缴纳投标保证金将被否决投标。", "risk_level": "high"}],
            "scoringItems": [{"id": "score-1", "item": "质量保证措施", "score": 10}],
            "sections": [
                {
                    "id": "s1",
                    "title": "投标函及投标函附录",
                    "content": "本章包含投标函、签章提示和法定代表人授权委托书。",
                    "metadata": {"volume_type": "business"},
                },
                {
                    "id": "s2",
                    "title": "资格审查资料",
                    "content": "本章提供营业执照、体系认证、项目业绩、检验报告和附件索引。",
                    "metadata": {"volume_type": "qualification"},
                },
                {
                    "id": "s3",
                    "title": "技术规范响应与技术偏差表",
                    "content": "本章说明技术规范响应、技术参数表、技术偏差表、质量保证、生产制造能力、试验检测能力、售后服务。",
                    "metadata": {"volume_type": "technical"},
                },
                {
                    "id": "s4",
                    "title": "报价文件",
                    "content": "本章包含报价文件、投标总价和价格说明。",
                    "metadata": {"volume_type": "price"},
                },
            ],
        }

    def _prefill_report(self, missing_price: bool = False):
        def field(key, value):
            return {"key": key, "label": key, "value": "" if missing_price and key == "total_bid_price" else value}

        return {
            "project": {"id": "11111111-1111-1111-1111-111111111111"},
            "summary": {"formalRequiredGaps": 0 if not missing_price else 1, "unresolvedPlaceholderCount": 0},
            "fields": [
                field("project_name", "国网辽宁电力电缆保护管采购"),
                field("project_no", "2225AC"),
                field("total_bid_price", "1000000元"),
                field("bid_bond_amount", "按招标文件要求"),
                field("authorized_representative", "张三"),
                field("authorized_representative_id", "130000000000000000"),
                field("signature_date", "2026年6月24日"),
                field("delivery_period", "按招标文件要求"),
                field("warranty_period", "按招标文件要求"),
                field("bid_validity_days", "90天"),
                field("package_no", "包2"),
                field("package_name", "电缆保护管CPVC"),
                field("material_category", "电缆保护管CPVC"),
                field("goods_list_summary", "包2 共 2 行需求"),
                field("technical_parameter_summary", "CPVC 技术参数候选"),
                field("technical_deviation_candidates", "技术偏差表候选"),
                field("taichang_parameter_match_summary", "泰昌检验报告参数佐证"),
                field("tax_rate", "13%"),
            ],
        }

    def _simulated_prefill_report(self):
        report = self._prefill_report()
        simulated = {
            "total_bid_price": "8888888.00 元（内部测试模拟值，非正式报价）",
            "bid_bond_amount": "100000.00 元（内部测试模拟值，非正式保证金金额）",
            "authorized_representative": "张三（内部测试模拟授权代表）",
            "authorized_representative_id": "110101199001011234（内部测试模拟身份证号）",
            "signature_date": "2026年06月19日（内部测试模拟签署日期）",
            "delivery_period": "内部测试模拟为合同签订后 30 日内完成供货。",
            "warranty_period": "内部测试模拟为到货验收合格后 12 个月。",
        }
        for field in report["fields"]:
            if field["key"] in simulated:
                field["value"] = simulated[field["key"]]
        return report

    def _assets(self):
        return [
            {"id": "a1", "title": "泰昌营业执照副本原图", "category": "基础证照"},
            {"id": "a2", "title": "质量管理体系认证证书", "category": "资质证书"},
            {"id": "a3", "title": "环境管理体系认证证书", "category": "资质证书"},
            {"id": "a4", "title": "职业健康安全管理体系认证证书", "category": "资质证书"},
            {"id": "a5", "title": "泰昌0322AB合同协议书和中标通知书", "category": "项目业绩"},
            {"id": "a6", "title": "泰昌CPVC电缆保护管检验报告", "category": "检验报告"},
            {"id": "a7", "title": "泰昌社保证明", "category": "人员证书"},
            {"id": "a8", "title": "泰昌ESG绿色供应链资料", "category": "绿色低碳资料"},
            {
                "id": "a9",
                "title": "泰昌官方Logo",
                "category": "品牌标识",
                "description": "河北泰昌电力器材科技有限公司品牌标识资料。",
                "specs": {
                    "enterprise": "泰昌",
                    "source_domain": "enterprise_fact",
                    "reference_only": False,
                    "do_not_mix_with": ["河北豪乾参考稿", "辽宁招标资料"],
                },
            },
        ]

    def test_blocker_rules_force_draft_export_when_customer_field_missing(self):
        from backend.services.formal_bid_check import build_formal_bid_check_report

        with patch("backend.services.formal_bid_check.get_project_interpretation", return_value=self._payload()), \
             patch("backend.services.formal_bid_check.build_bid_prefill_report", return_value=self._prefill_report(missing_price=True)), \
             patch("backend.services.formal_bid_check.build_compliance_report", return_value={"summary": {"percent": 80, "missing": 1, "highRiskMissing": 1}}), \
             patch("backend.services.formal_bid_check.list_knowledge_assets", return_value=self._assets()):
            report = build_formal_bid_check_report("11111111-1111-1111-1111-111111111111")

        self.assertEqual(report["summary"]["totalRules"], 60)
        self.assertFalse(report["summary"]["canFormalExport"])
        self.assertTrue(report["summary"]["draftExportAllowed"])
        by_id = {item["id"]: item for item in report["items"]}
        self.assertEqual(by_id["B-002"]["status"], "blocked")
        self.assertTrue(by_id["B-002"]["blocksFormalExport"])

    def test_enterprise_logo_do_not_mix_metadata_is_not_forbidden_source(self):
        from backend.services.formal_bid_check import build_formal_bid_check_report

        with patch("backend.services.formal_bid_check.get_project_interpretation", return_value=self._payload()), \
             patch("backend.services.formal_bid_check.build_bid_prefill_report", return_value=self._prefill_report()), \
             patch("backend.services.formal_bid_check.build_compliance_report", return_value={"summary": {"percent": 80, "missing": 1, "highRiskMissing": 1}}), \
             patch("backend.services.formal_bid_check.list_knowledge_assets", return_value=self._assets()):
            report = build_formal_bid_check_report("11111111-1111-1111-1111-111111111111")

        by_id = {item["id"]: item for item in report["items"]}
        self.assertEqual(by_id["D-003"]["status"], "passed")

    def test_simulated_customer_values_block_formal_export(self):
        from backend.services.formal_bid_check import build_formal_bid_check_report

        with patch("backend.services.formal_bid_check.get_project_interpretation", return_value=self._payload()), \
             patch("backend.services.formal_bid_check.build_bid_prefill_report", return_value=self._simulated_prefill_report()), \
             patch("backend.services.formal_bid_check.build_compliance_report", return_value={"summary": {"percent": 80, "missing": 1, "highRiskMissing": 1}}), \
             patch("backend.services.formal_bid_check.list_knowledge_assets", return_value=self._assets()):
            report = build_formal_bid_check_report("11111111-1111-1111-1111-111111111111")

        self.assertFalse(report["summary"]["canFormalExport"])
        by_id = {item["id"]: item for item in report["items"]}
        for rule_id in ("B-002", "B-003", "B-004", "B-005", "B-006", "B-007", "B-008", "P-005"):
            self.assertEqual(by_id[rule_id]["status"], "blocked")
            self.assertIn("非正式", by_id[rule_id]["evidence"])

    def test_report_items_include_processing_action_and_evidence_chain(self):
        from backend.services.formal_bid_check import build_formal_bid_check_report

        with patch("backend.services.formal_bid_check.get_project_interpretation", return_value=self._payload()), \
             patch("backend.services.formal_bid_check.build_bid_prefill_report", return_value=self._prefill_report(missing_price=True)), \
             patch("backend.services.formal_bid_check.build_compliance_report", return_value={"summary": {"percent": 80, "missing": 1, "highRiskMissing": 1}}), \
             patch("backend.services.formal_bid_check.list_knowledge_assets", return_value=self._assets()):
            report = build_formal_bid_check_report("11111111-1111-1111-1111-111111111111")

        by_id = {item["id"]: item for item in report["items"]}
        self.assertEqual(by_id["B-002"]["action"]["type"], "prefill")
        self.assertEqual(by_id["B-002"]["action"]["target"], "total_bid_price")
        self.assertEqual(by_id["Q-001"]["action"]["type"], "qualification_library")
        self.assertEqual(by_id["T-001"]["action"]["type"], "bid_editor")
        self.assertGreaterEqual(len(by_id["B-002"]["evidenceChain"]), 3)
        self.assertEqual(by_id["B-002"]["evidenceChain"][0]["label"], "规则依据")

    def test_rule_inventory_has_sixty_objective_rules(self):
        from backend.services.formal_bid_check import load_formal_check_rules

        rule_set = load_formal_check_rules()
        rules = rule_set["rules"]
        self.assertEqual(len(rules), 60)
        self.assertEqual(sum(1 for rule in rules if rule["category"] == "资格资料"), 10)
        self.assertEqual(sum(1 for rule in rules if rule["category"] == "商务响应"), 12)
        self.assertTrue(all(rule.get("source_level") and rule.get("source_ref") for rule in rules))
        self.assertTrue(all(rule.get("remediation") for rule in rules))

    def test_api_rejects_invalid_project_id(self):
        from main import app
        from backend.api.formal_check import get_project_formal_check

        with app.test_request_context("/api/bidding/projects/not-a-uuid/formal-check"):
            response, status = get_project_formal_check("not-a-uuid")

        self.assertEqual(status, 400)
        self.assertIn("项目 ID", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()

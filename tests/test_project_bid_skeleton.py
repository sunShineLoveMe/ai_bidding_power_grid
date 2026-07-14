import unittest
from pathlib import Path
from unittest.mock import patch

from backend.ai.chapter_planner import _build_rule_outline, _generate_outline_from_ai_or_rule
from backend.services.project_bid_skeleton import (
    build_project_bid_skeleton,
    build_project_rule_inventory,
    compare_with_historical_skeleton,
)
from scripts.rag.build_taichang_project_bid_skeleton import extract_format_rows


ROOT = Path(__file__).resolve().parents[1]
SL2655_TENDER = ROOT / "assets/template_words/包1_完整招标文件_92475576192439826/SL2655招标文件-预审.docx"


def _payload() -> dict:
    return {
        "project": {
            "id": "p2-01",
            "project_name": "当前电缆保护管投标项目",
            "project_no": "SL265A",
            "project_mode": "taichang_reuse",
        },
        "analysis": {"project_meta": {"project_name": "当前电缆保护管投标项目", "tender_no": "SL265A"}},
        "documentChunks": [{
            "content": (
                "投标文件格式。价格文件按包制作，商务文件按分标制作，技术文件按分标制作。"
                "投标人在资格预审项目提交的资格预审申请文件将作为投标文件的一部分。"
                "资质证书、试验报告在投标截止前到期的，应提供新的有效支持证明材料。"
                "本项目免收投标保证金，招标文件中保证金相关要求均不适用。不接收纸质投标文件。"
            )
        }],
        "requirements": [],
        "risks": [],
        "scoringItems": [],
        "project_rule_inputs": {
            "source_file": "当前招标文件.docx",
            "format_rows": [
                {
                    "sequence": "1", "title": "投标函及附件", "volume_type": "price",
                    "required_marker": "√", "submission_scope": "by_package", "strict_format_table": True,
                    "source_section": "投标文件组成清单", "source_page": 88,
                },
                {
                    "sequence": "2.1", "title": "商务偏差表", "volume_type": "business",
                    "required_marker": "√", "submission_scope": "by_lot", "strict_format_table": True,
                    "source_section": "投标文件组成清单", "source_page": 89,
                },
                {
                    "sequence": "2.2", "title": "投标保证金", "volume_type": "business",
                    "required_marker": "", "submission_scope": "by_lot", "strict_format_table": True,
                    "source_section": "投标文件组成清单", "source_page": 89,
                },
                {
                    "sequence": "3.1", "title": "技术偏差表", "volume_type": "technical",
                    "required_marker": "√", "submission_scope": "by_lot", "strict_format_table": True,
                    "source_section": "投标文件组成清单", "source_page": 90,
                },
                {
                    "sequence": "3.2", "title": "生产装备", "volume_type": "technical",
                    "required_marker": "", "submission_scope": "by_lot", "strict_format_table": True,
                    "source_section": "投标文件组成清单", "source_page": 90,
                },
            ],
        },
    }


class ProjectBidSkeletonTest(unittest.TestCase):
    def test_strict_format_markers_control_inclusion(self):
        skeleton = build_project_bid_skeleton(_payload())
        included = {chapter["title"] for volume in skeleton["volumes"] for chapter in volume["chapters"]}
        statuses = {rule["title"]: rule["status"] for rule in skeleton["rule_inventory"]}

        self.assertIn("投标函及附件", included)
        self.assertIn("商务偏差表", included)
        self.assertIn("技术偏差表", included)
        self.assertNotIn("生产装备", included)
        self.assertNotIn("投标保证金", included)
        self.assertEqual("not_applicable", statuses["生产装备"])
        self.assertEqual("not_applicable", statuses["投标保证金"])

    def test_prequalification_inheritance_update_and_forbidden_rules_are_preserved(self):
        rules = build_project_rule_inventory(_payload())
        by_id = {rule["rule_id"]: rule for rule in rules}

        self.assertEqual("inherited_from_prequalification", by_id["PREQUAL-INHERIT"]["status"])
        self.assertEqual("update_required", by_id["PREQUAL-UPDATE"]["status"])
        self.assertEqual("forbidden", by_id["FORBID-PAPER"]["status"])
        self.assertNotIn("资格预审申请文件", {
            chapter["title"] for volume in build_project_bid_skeleton(_payload())["volumes"] for chapter in volume["chapters"]
        })

    def test_price_and_business_technical_scopes_do_not_mix(self):
        scope = {row["volume_type"]: row for row in build_project_bid_skeleton(_payload())["scope_matrix"]}

        self.assertEqual("by_package", scope["price"]["submission_scope"])
        self.assertEqual("package", scope["price"]["rule_scope"])
        self.assertEqual("by_lot", scope["business"]["submission_scope"])
        self.assertEqual("by_lot", scope["technical"]["submission_scope"])

    def test_every_rule_has_complete_source_trace(self):
        for rule in build_project_rule_inventory(_payload()):
            source = rule["sources"][0]
            self.assertTrue(source["source_file"])
            self.assertTrue(source["source_section"])
            self.assertTrue(source["document_role"])
            self.assertTrue(source["detection_method"])
            self.assertIsInstance(source["confidence"], float)
            self.assertIn("source_page", source)

    def test_history_is_only_deterministic_difference_reference(self):
        difference = compare_with_historical_skeleton(build_project_rule_inventory(_payload()))

        self.assertTrue(difference["current_tender_precedence"])
        self.assertEqual("reference_only", difference["historical_role"])
        self.assertIn("no_fuzzy_similarity", difference["comparison_method"])
        self.assertGreater(difference["summary"]["deleted"], 0)

    def test_chapter_planner_skips_llm_for_current_tender_skeleton(self):
        payload = _payload()
        payload["analysis"]["summary"] = "MPP电缆保护管物资采购"
        with patch("backend.ai.chapter_planner.call_dashscope_api") as llm:
            outline = _generate_outline_from_ai_or_rule(payload)

        llm.assert_not_called()
        self.assertEqual("current_tender_project_skeleton", outline["artifact_role"])
        self.assertEqual("deterministic-current-tender-rules", outline["model"])
        self.assertFalse(any("生产装备" in str(item.get("title")) for item in outline["chapters"]))

    @unittest.skipUnless(SL2655_TENDER.exists(), "SL2655 真实验收样本不存在")
    def test_real_sl2655_format_table_keeps_unchecked_historical_sections_out(self):
        rows, clauses, text = extract_format_rows(SL2655_TENDER)
        payload = _payload()
        payload["documentChunks"] = [{"content": text}]
        payload["project_rule_inputs"] = {
            "source_file": str(SL2655_TENDER),
            "format_rows": rows,
            "clauses": clauses,
        }
        rules = build_project_rule_inventory(payload)
        statuses = {rule["canonical_title"]: rule["status"] for rule in rules}

        self.assertEqual("not_applicable", statuses["投标保证金"])
        self.assertEqual("not_applicable", statuses["生产装备"])
        self.assertEqual("not_applicable", statuses["试验检测设备"])
        self.assertEqual("not_applicable", statuses["检测检验报告"])
        self.assertEqual("required", statuses["技术特性参数表"])
        self.assertEqual("required", statuses["技术偏差表"])

    def test_rule_outline_uses_dynamic_project_skeleton_instead_of_history(self):
        payload = _payload()
        payload["analysis"]["summary"] = "MPP电缆保护管物资采购"
        outline = _build_rule_outline(payload)
        titles = [str(item.get("title") or "") for item in outline["chapters"]]

        self.assertEqual("project-bid-skeleton-v1", outline["version"])
        self.assertIn("商务偏差表", titles)
        self.assertNotIn("生产装备", titles)
        self.assertNotIn("施工组织设计", titles)


if __name__ == "__main__":
    unittest.main()

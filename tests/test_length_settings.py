import unittest
from unittest.mock import patch

from backend.ai.length_settings import (
    allocate_chapter_length_targets,
    apply_length_allocations_to_sections,
    evaluate_length_feasibility,
    normalize_length_settings,
)


class LengthSettingsTest(unittest.TestCase):
    def test_pages_mode_converts_to_volume_words(self):
        settings = normalize_length_settings({
            "mode": "pages",
            "technicalPages": 100,
            "businessPages": 50,
        })

        self.assertEqual(settings["technicalWords"], 70000)
        self.assertEqual(settings["businessWords"], 27500)

    def test_huge_target_returns_feasibility_warning(self):
        sections = [
            {"id": "technical-1", "title": "施工组织设计", "metadata": {"volume_type": "technical"}},
            {"id": "business-1", "title": "商务响应文件", "metadata": {"volume_type": "business"}},
        ]
        settings = normalize_length_settings({
            "mode": "pages",
            "technicalPages": 500,
            "businessPages": 120,
        })

        feasibility = evaluate_length_feasibility(settings, sections)

        self.assertEqual(feasibility["level"], "warning")
        self.assertGreaterEqual(len(feasibility["warnings"]), 2)

    def test_business_internal_volumes_are_capped(self):
        sections = [
            {
                "id": "business-1",
                "title": "商务响应文件",
                "level": 1,
                "mapped_requirements": ["合同条款响应", "付款承诺"],
                "metadata": {"volume_type": "business"},
            },
            {
                "id": "qualification-1",
                "title": "企业资质证书",
                "level": 2,
                "mapped_requirements": ["提供资质证书"],
                "metadata": {"volume_type": "qualification"},
            },
            {
                "id": "price-1",
                "title": "报价文件",
                "level": 2,
                "metadata": {"volume_type": "price"},
            },
        ]
        settings = normalize_length_settings({
            "mode": "pages",
            "technicalPages": 1,
            "businessPages": 100,
        })

        allocations = {item["sectionId"]: item["targetWords"] for item in allocate_chapter_length_targets(sections, settings)}

        self.assertLessEqual(allocations["qualification-1"], 1800)
        self.assertLessEqual(allocations["price-1"], 900)
        self.assertGreater(allocations["business-1"], allocations["qualification-1"])

    def test_allocations_write_chapter_writing_plan(self):
        sections = [
            {
                "id": "technical-1",
                "title": "施工组织设计",
                "level": 1,
                "metadata": {"volume_type": "technical"},
            }
        ]
        settings = normalize_length_settings({"mode": "pages", "technicalPages": 10, "businessPages": 1})
        allocations = allocate_chapter_length_targets(sections, settings)

        updated = apply_length_allocations_to_sections(sections, allocations, settings)

        self.assertEqual(updated[0]["metadata"]["writing_plan"]["target_words"], 7000)
        self.assertEqual(updated[0]["metadata"]["writing_plan"]["length_settings_source"], "project_length_settings")
        self.assertIn("allow_auto_expand", updated[0]["metadata"]["writing_plan"])
        self.assertIn("allowAutoExpand", updated[0]["metadata"]["length_settings"])

    def test_section_prompt_includes_target_words_and_no_padding_rule(self):
        from backend.ai.section_writer import build_section_prompt

        chapter = {
            "id": "technical-1",
            "title": "施工组织设计",
            "level": 1,
            "metadata": {
                "volume_type": "technical",
                "writing_plan": {"target_words": 7000, "suggested_pages": "10"},
            },
        }
        payload = {
            "project": {"project_name": "测试工程"},
            "analysis": {"project_meta": {}, "summary": "测试摘要"},
        }

        with patch("backend.ai.section_writer.get_project_interpretation", return_value=payload), patch(
            "backend.ai.section_writer.list_knowledge_assets", return_value=[]
        ):
            prompt = build_section_prompt("project-id", chapter)

        self.assertIn("目标字数：7000 字", prompt)
        self.assertIn("不得为了凑页数重复同义段落", prompt)
        self.assertIn("【待补充：...】", prompt)

    def test_section_supplement_prompt_is_chapter_scoped(self):
        from backend.ai.section_writer import build_section_supplement_prompt, estimate_bid_content_words

        chapter = {
            "id": "technical-1",
            "title": "施工组织设计",
            "level": 1,
            "response_points": ["施工进度保障"],
            "mapped_scoring_items": ["施工组织方案完整性"],
            "metadata": {
                "volume_type": "technical",
                "writing_plan": {
                    "target_words": 7000,
                    "suggested_pages": "10",
                    "allow_auto_expand": True,
                },
            },
        }
        payload = {
            "project": {"project_name": "测试工程"},
            "analysis": {"project_meta": {}, "summary": "测试摘要"},
        }

        with patch("backend.ai.section_writer.get_project_interpretation", return_value=payload), patch(
            "backend.ai.section_writer.list_knowledge_assets", return_value=[]
        ):
            prompt = build_section_supplement_prompt("project-id", chapter, "已有正文")

        self.assertIn("只输出“可直接追加到本章节末尾”的补写内容", prompt)
        self.assertIn("章节标题：施工组织设计", prompt)
        self.assertIn("章节目标字数：7000 字", prompt)
        self.assertIn("允许围绕评分点", prompt)
        self.assertGreater(estimate_bid_content_words("## 标题\n\n质量控制措施"), 0)


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from unittest.mock import MagicMock, patch

from backend.ai import interpreter


class SegmentedInterpreterTest(unittest.TestCase):
    def test_segment_chunks_merges_over_limit_groups_without_dropping_content(self):
        chunks = [{"content": "甲" * 10, "chunk_index": index} for index in range(6)]

        def fake_get_setting(key, default=None):
            values = {
                "interpretation_segment_max_chars": 25,
                "interpretation_segment_max_groups": 2,
            }
            return values.get(key, default)

        with patch("backend.ai.interpreter.get_setting", side_effect=fake_get_setting):
            groups = interpreter._segment_chunks(chunks)

        self.assertEqual(len(groups), 2)
        self.assertEqual(
            [chunk["chunk_index"] for group in groups for chunk in group],
            [0, 1, 2, 3, 4, 5],
        )

    def test_large_interpretation_uses_segmented_extract_and_merge(self):
        project_id = "project-1"
        chunks = [
            {"content": f"资格要求和评分办法正文 {index}", "chunk_index": index, "source_page": index + 1}
            for index in range(12)
        ]
        payload = {
            "project": {"id": project_id, "project_name": "测试水利项目"},
            "analysis": {"id": "analysis-1", "project_meta": {}, "summary": "测试摘要"},
            "requirements": [],
            "risks": [],
            "scoringItems": [],
            "chapterSuggestions": [],
        }

        def fake_get_setting(key, default=None):
            values = {
                "interpretation_segment_max_chars": 80,
                "interpretation_segment_max_groups": 24,
            }
            return values.get(key, default)

        def fake_llm_response(messages, model=None, json_mode=True, usage_context=None):
            stage = (usage_context or {}).get("stage")
            if stage == "ai_interpretation_segment":
                segment_index = usage_context["metadata"]["segment_index"]
                content = {
                    "executive_summary": [f"分段 {segment_index} 摘要"],
                    "qualification_review": [
                        {
                            "requirement": f"资格项 {segment_index}",
                            "judgement": "需准备",
                            "evidence": "原文依据",
                            "source_page": segment_index,
                            "action": "准备材料",
                        }
                    ],
                }
                response_model = "deepseek-v4-flash"
            else:
                content = {
                    "executive_summary": ["融合后摘要"],
                    "qualification_review": [
                        {
                            "requirement": "融合资格项",
                            "judgement": "需准备",
                            "evidence": "融合依据",
                            "source_page": 1,
                            "action": "准备材料",
                        }
                    ],
                    "next_actions": ["人工复核重点资格项"],
                }
                response_model = "deepseek-v4-pro"
            return {
                "model": response_model,
                "output": {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]},
            }

        update_execute = MagicMock(return_value=MagicMock(data=[{"id": "analysis-1"}]))
        update_chain = MagicMock()
        update_chain.update.return_value.eq.return_value.execute = update_execute
        supabase = MagicMock()
        supabase.table.return_value = update_chain

        with (
            patch("backend.ai.interpreter.get_project_interpretation", return_value=payload),
            patch("backend.ai.interpreter.list_project_document_chunks", return_value=chunks),
            patch("backend.ai.interpreter.get_setting", side_effect=fake_get_setting),
            patch("backend.ai.interpreter.get_stage_model", side_effect=lambda stage, default=None: {
                "interpretation": "deepseek-v4-pro",
                "interpretation_segment": "deepseek-v4-flash",
                "section_writing": "deepseek-v4-flash",
            }.get(stage, default or "deepseek-v4-flash")),
            patch("backend.ai.interpreter.call_dashscope_api", side_effect=fake_llm_response) as llm,
            patch("backend.ai.interpreter.get_supabase_client", return_value=supabase),
        ):
            report = interpreter.generate_ai_interpretation_report(project_id)

        stages = [call.kwargs["usage_context"]["stage"] for call in llm.call_args_list]
        self.assertIn("ai_interpretation_segment", stages)
        self.assertIn("ai_interpretation_merge", stages)
        self.assertEqual(report["executive_summary"], ["融合后摘要"])

        saved_meta = update_chain.update.call_args.args[0]["project_meta"]
        self.assertEqual(saved_meta["ai_report_generation"]["mode"], "segmented")
        self.assertEqual(saved_meta["ai_report_model"], "deepseek-v4-pro")
        self.assertGreater(saved_meta["ai_report_generation"]["segment_count"], 0)


if __name__ == "__main__":
    unittest.main()

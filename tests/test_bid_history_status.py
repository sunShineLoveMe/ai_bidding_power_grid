import os
import unittest


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_LOGIN_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


from backend.db.supabase_repo import (  # noqa: E402
    _history_generation_summary,
    _history_prefill_summary,
    _history_stage_action,
)


class BidHistoryStatusTest(unittest.TestCase):
    def test_outline_sections_without_prefill_route_to_confirmation(self):
        stage = _history_stage_action(
            project_status="uploaded",
            has_analysis=True,
            section_count=12,
            chunk_count=30,
            parse_status="indexed",
            generation_summary=_history_generation_summary(None),
            prefill_summary=_history_prefill_summary({}),
        )

        self.assertEqual(stage["stage"], "待投标确认")
        self.assertEqual(stage["next_step"], "prefill")
        self.assertEqual(stage["next_action"], "投标确认")

    def test_partial_generation_routes_to_resume(self):
        generation = _history_generation_summary({
            "id": "task-1",
            "status": "partial_failed",
            "items": [
                {"section_id": "s1", "status": "done"},
                {"section_id": "s2", "status": "partial_generated", "metadata": {"partial_review_required": True}},
            ],
        })
        stage = _history_stage_action(
            project_status="uploaded",
            has_analysis=True,
            section_count=2,
            chunk_count=30,
            parse_status="indexed",
            generation_summary=generation,
            prefill_summary=_history_prefill_summary({"bid_prefill": {"applied_at": "2026-06-26T10:00:00"}}),
        )

        self.assertEqual(generation["writing_partial_count"], 1)
        self.assertEqual(generation["writing_review_count"], 1)
        self.assertEqual(stage["stage"], "草稿待续写")
        self.assertEqual(stage["next_step"], "resume_partial")

    def test_completed_generation_routes_to_formal_check(self):
        generation = _history_generation_summary({
            "id": "task-2",
            "status": "completed",
            "total_count": 2,
            "done_count": 2,
            "items": [
                {"section_id": "s1", "status": "done"},
                {"section_id": "s2", "status": "done"},
            ],
        })
        stage = _history_stage_action(
            project_status="uploaded",
            has_analysis=True,
            section_count=2,
            chunk_count=30,
            parse_status="indexed",
            generation_summary=generation,
            prefill_summary=_history_prefill_summary({"bid_prefill": {"applied_at": "2026-06-26T10:00:00"}}),
        )

        self.assertEqual(stage["stage"], "正文初稿完成")
        self.assertEqual(stage["next_step"], "formal_check")
        self.assertEqual(stage["next_action"], "正式检查")


if __name__ == "__main__":
    unittest.main()

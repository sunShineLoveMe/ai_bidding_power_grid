import os
import unittest
from unittest.mock import patch


os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_LOGIN_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")

VALID_PROJECT_ID = "11111111-1111-4111-8111-111111111111"
VALID_TASK_ID = "22222222-2222-4222-8222-222222222222"


class InterpretationCeleryTaskTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.app = main.app
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_create_ai_report_task_dispatches_celery(self):
        created_task = {"id": VALID_TASK_ID, "project_id": VALID_PROJECT_ID, "status": "queued", "progress": 0}
        payload = {"analysis": {"id": "analysis-1", "project_meta": {}}, "project": {"id": VALID_PROJECT_ID}}

        with (
            patch("backend.api.interpret.get_project_interpretation", return_value=payload),
            patch("backend.api.interpret.create_bid_interpretation_task", return_value=created_task) as create_mock,
            patch("backend.tasks.interpretation_tasks.run_ai_interpretation_report.delay") as delay_mock,
        ):
            response = self.client.post(f"/api/bidding/interpretations/{VALID_PROJECT_ID}/ai-report-tasks")

        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["taskId"], VALID_TASK_ID)
        self.assertFalse(body["cached"])
        create_mock.assert_called_once()
        self.assertEqual(create_mock.call_args.kwargs["metadata"]["project_mode"], "general")
        self.assertFalse(create_mock.call_args.kwargs["metadata"]["historical_bid_reuse_enabled"])
        delay_mock.assert_called_once_with(VALID_PROJECT_ID, VALID_TASK_ID)

    def test_create_ai_report_task_returns_completed_when_cached(self):
        cached_report = {"executive_summary": ["已生成"]}
        created_task = {"id": VALID_TASK_ID, "project_id": VALID_PROJECT_ID, "status": "completed", "progress": 100}
        payload = {"analysis": {"id": "analysis-1", "project_meta": {"ai_report": cached_report}}, "project": {"id": VALID_PROJECT_ID}}

        with (
            patch("backend.api.interpret.get_project_interpretation", return_value=payload),
            patch("backend.api.interpret.create_bid_interpretation_task", return_value=created_task) as create_mock,
            patch("backend.tasks.interpretation_tasks.run_ai_interpretation_report.delay") as delay_mock,
        ):
            response = self.client.post(f"/api/bidding/interpretations/{VALID_PROJECT_ID}/ai-report-tasks")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["cached"])
        create_mock.assert_called_once()
        self.assertEqual(create_mock.call_args.kwargs["metadata"]["project_mode"], "general")
        delay_mock.assert_not_called()

    def test_get_ai_report_task_returns_task(self):
        task = {"id": VALID_TASK_ID, "project_id": VALID_PROJECT_ID, "status": "running", "progress": 45}
        with patch("backend.api.interpret.get_bid_interpretation_task", return_value=task):
            response = self.client.get(f"/api/bidding/interpretations/{VALID_PROJECT_ID}/ai-report-tasks/{VALID_TASK_ID}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["task"], task)

    def test_worker_success_path_marks_completed(self):
        from backend.tasks.interpretation_tasks import run_ai_interpretation_report

        updates = []

        def fake_update(project_id, task_id, patch_payload):
            updates.append(patch_payload)
            return {**patch_payload, "id": task_id, "project_id": project_id}

        def fake_generate(project_id, progress_callback=None):
            progress_callback({"stage": "segmenting", "segment_total": 2, "segment_done": 1, "message": "分段完成 1/2"})
            progress_callback({"stage": "merging", "segment_total": 2, "segment_done": 2, "message": "融合中"})
            return {"executive_summary": ["完成"], "_segmented_interpretation": {"segment_count": 2}}

        with (
            patch("backend.db.supabase_repo.update_bid_interpretation_task", side_effect=fake_update),
            patch("backend.ai.interpreter.generate_ai_interpretation_report", side_effect=fake_generate),
        ):
            result = run_ai_interpretation_report.apply(args=(VALID_PROJECT_ID, VALID_TASK_ID)).get()

        self.assertEqual(result["status"], "completed")
        statuses = [item.get("status") for item in updates if "status" in item]
        self.assertIn("running", statuses)
        self.assertIn("completed", statuses)
        self.assertTrue(any(item.get("progress") == 88 for item in updates))

    def test_worker_failure_path_marks_failed(self):
        from backend.tasks.interpretation_tasks import run_ai_interpretation_report

        updates = []

        def fake_update(project_id, task_id, patch_payload):
            updates.append(patch_payload)
            return {**patch_payload, "id": task_id, "project_id": project_id}

        with (
            patch("backend.db.supabase_repo.update_bid_interpretation_task", side_effect=fake_update),
            patch("backend.ai.interpreter.generate_ai_interpretation_report", side_effect=RuntimeError("boom")),
        ):
            result = run_ai_interpretation_report.apply(args=(VALID_PROJECT_ID, VALID_TASK_ID)).get()

        self.assertEqual(result["status"], "failed")
        self.assertIn("failed", [item.get("status") for item in updates if "status" in item])


if __name__ == "__main__":
    unittest.main()

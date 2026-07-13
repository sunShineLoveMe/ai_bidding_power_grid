import os
import unittest
from unittest.mock import patch


os.environ["APP_AUTH_ENABLED"] = "false"
os.environ["APP_LOGIN_ENABLED"] = "false"
os.environ["APP_EXPOSE_DEBUG_ERRORS"] = "false"
os.environ["REQUIRE_STRICT_CONFIG"] = "false"
os.environ["APP_ENV"] = "testing"


class SectionApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.app = main.app
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_sections_reject_invalid_project_id(self):
        response = self.client.get("/api/bidding/interpretations/not-a-uuid/sections")

        self.assertEqual(response.status_code, 400)
        self.assertIn("project_id", response.get_json().get("error", ""))

    @patch("backend.api.sections.upsert_bid_section")
    def test_save_section_returns_saved_section(self, upsert_mock):
        project_id = "11111111-1111-1111-1111-111111111111"
        upsert_mock.return_value = {
            "id": "22222222-2222-2222-2222-222222222222",
            "project_id": project_id,
            "title": "施工组织设计",
            "content": "正文",
        }

        response = self.client.post(
            f"/api/bidding/interpretations/{project_id}/sections",
            json={"title": "施工组织设计", "content": "正文"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["section"]["title"], "施工组织设计")
        upsert_mock.assert_called_once()

    @patch("backend.api.sections.reorder_bid_sections")
    def test_reorder_sections_returns_sorted_sections(self, reorder_mock):
        project_id = "11111111-1111-1111-1111-111111111111"
        reorder_mock.return_value = [{"id": "s1", "title": "一、投标函", "order": "1"}]

        response = self.client.post(
            f"/api/bidding/interpretations/{project_id}/sections/reorder",
            json={"sections": [{"id": "s1", "order": "1"}]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["sections"][0]["order"], "1")
        reorder_mock.assert_called_once()

    @patch("backend.api.sections.dispatch_section_generation_task")
    @patch("backend.api.sections.create_bid_generation_task")
    @patch("backend.api.sections.build_project_task_metadata")
    def test_create_section_generation_task_dispatches_celery(self, metadata_mock, create_mock, dispatch_mock):
        project_id = "11111111-1111-1111-1111-111111111111"
        task_id = "22222222-2222-2222-2222-222222222222"
        create_mock.return_value = {"id": task_id, "project_id": project_id, "status": "queued", "items": []}
        metadata_mock.return_value = {
            "project_mode": "general",
            "orchestration_profile": "general_v1",
            "historical_bid_reuse_enabled": False,
        }

        response = self.client.post(
            f"/api/bidding/interpretations/{project_id}/section-generation-tasks",
            json={
                "volumeType": "technical",
                "withImages": False,
                "items": [{"section_id": "33333333-3333-3333-3333-333333333333", "title": "施工组织设计"}],
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["task"]["id"], task_id)
        create_mock.assert_called_once()
        self.assertEqual(create_mock.call_args.kwargs["metadata"]["project_mode"], "general")
        dispatch_mock.assert_called_once_with(project_id, task_id)

    @patch("backend.api.sections.get_bid_generation_task")
    def test_get_section_generation_task_returns_task(self, get_mock):
        project_id = "11111111-1111-1111-1111-111111111111"
        task_id = "22222222-2222-2222-2222-222222222222"
        get_mock.return_value = {"id": task_id, "project_id": project_id, "status": "running"}

        response = self.client.get(f"/api/bidding/interpretations/{project_id}/section-generation-tasks/{task_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["task"]["status"], "running")

    def test_download_docx_rejects_invalid_project_id(self):
        response = self.client.post("/api/bidding/interpretations/not-a-uuid/download-docx", json={})

        self.assertEqual(response.status_code, 400)
        self.assertIn("project_id", response.get_json().get("error", ""))

    def test_export_task_rejects_invalid_task_id(self):
        project_id = "11111111-1111-1111-1111-111111111111"
        response = self.client.get(f"/api/bidding/interpretations/{project_id}/export-tasks/not-a-uuid")

        self.assertEqual(response.status_code, 400)
        self.assertIn("task_id", response.get_json().get("error", ""))


if __name__ == "__main__":
    unittest.main()

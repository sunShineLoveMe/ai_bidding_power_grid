import os
import unittest
from unittest.mock import patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


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

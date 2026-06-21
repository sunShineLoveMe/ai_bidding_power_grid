import os
import unittest
from unittest.mock import patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_LOGIN_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


class LatestInterpretationProjectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.app = main.app
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_latest_skips_projects_without_analysis(self):
        projects = [
            {"id": "project-new", "project_name": "最新但未完成解析"},
            {"id": "project-ready", "project_name": "最近已完成解读"},
        ]

        def fake_interpretation(project_id):
            if project_id == "project-new":
                return {"project": projects[0], "analysis": None}
            return {
                "project": projects[1],
                "analysis": {"id": "analysis-ready", "project_meta": {"project_name": "最近已完成解读"}},
                "requirements": [{"id": "req-1"}],
                "risks": [{"id": "risk-1"}],
                "scoringItems": [{"id": "score-1"}],
                "chapterSuggestions": [],
                "documentChunks": [],
            }

        with (
            patch("backend.api.projects.list_recent_bid_projects", return_value=projects) as list_mock,
            patch("backend.api.projects.get_project_interpretation", side_effect=fake_interpretation),
        ):
            response = self.client.get("/api/bidding/interpretations/latest")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["project"]["id"], "project-ready")
        self.assertEqual(body["analysis"]["id"], "analysis-ready")
        self.assertEqual(len(body["requirements"]), 1)
        list_mock.assert_called_once_with(limit=20)

    def test_latest_falls_back_to_most_recent_project_when_no_analysis_exists(self):
        projects = [{"id": "project-new", "project_name": "最新待解析"}]

        with (
            patch("backend.api.projects.list_recent_bid_projects", return_value=projects),
            patch("backend.api.projects.get_project_interpretation", return_value={"project": projects[0], "analysis": None}),
        ):
            response = self.client.get("/api/bidding/interpretations/latest")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["project"]["id"], "project-new")
        self.assertIsNone(body["analysis"])
        self.assertEqual(body["requirements"], [])
        self.assertEqual(body["risks"], [])
        self.assertEqual(body["scoringItems"], [])
        self.assertEqual(body["chapterSuggestions"], [])
        self.assertEqual(body["documentChunks"], [])


if __name__ == "__main__":
    unittest.main()

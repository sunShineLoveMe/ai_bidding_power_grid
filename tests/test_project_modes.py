import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.core.project_modes import (
    InvalidProjectModeError,
    ProjectModeUnavailableError,
    ensure_project_mode_available,
    merge_project_mode_metadata,
    normalize_project_mode,
)
from backend.services.project_mode_context import build_project_task_metadata_from_project
from backend.db.supabase_repo import create_bid_project_for_upload


class ProjectModeContractTest(unittest.TestCase):
    def test_legacy_or_unknown_project_mode_falls_back_to_general(self):
        self.assertEqual(normalize_project_mode(None), "general")
        self.assertEqual(normalize_project_mode(""), "general")
        self.assertEqual(normalize_project_mode("legacy_value"), "general")

    def test_new_project_rejects_unknown_mode(self):
        with self.assertRaises(InvalidProjectModeError):
            normalize_project_mode("legacy_value", strict=True)

    def test_taichang_feature_switch_never_blocks_general(self):
        with patch.dict(os.environ, {"TAICHANG_REUSE_ENABLED": "false"}):
            ensure_project_mode_available("general")
            with self.assertRaises(ProjectModeUnavailableError):
                ensure_project_mode_available("taichang_reuse")

    def test_server_project_mode_overrides_client_metadata(self):
        metadata = merge_project_mode_metadata(
            "general",
            {
                "project_mode": "taichang_reuse",
                "orchestration_profile": "taichang_reuse_v1",
                "historical_bid_reuse_enabled": True,
                "requested_from": "test",
            },
        )
        self.assertEqual(metadata["project_mode"], "general")
        self.assertEqual(metadata["orchestration_profile"], "general_v1")
        self.assertFalse(metadata["historical_bid_reuse_enabled"])
        self.assertEqual(metadata["requested_from"], "test")

    def test_taichang_project_context_enables_only_taichang_orchestration(self):
        metadata = build_project_task_metadata_from_project(
            {"id": "p1", "project_mode": "taichang_reuse"},
            {"requested_from": "test"},
        )
        self.assertEqual(metadata["project_mode"], "taichang_reuse")
        self.assertEqual(metadata["orchestration_profile"], "taichang_reuse_v1")
        self.assertTrue(metadata["historical_bid_reuse_enabled"])

    def test_project_context_requires_real_project(self):
        with self.assertRaisesRegex(RuntimeError, "项目不存在"):
            build_project_task_metadata_from_project(None)

    def test_general_project_uses_legacy_schema_fallback(self):
        client = MagicMock()
        execute = client.table.return_value.insert.return_value.execute
        execute.side_effect = [
            RuntimeError("Could not find the 'project_mode' column in the schema cache"),
            SimpleNamespace(data=[{"id": "p1", "project_name": "测试项目"}]),
        ]
        with patch("backend.db.supabase_repo.get_supabase_client", return_value=client):
            project = create_bid_project_for_upload("测试项目.docx")

        self.assertEqual(project["project_mode"], "general")
        first_payload = client.table.return_value.insert.call_args_list[0].args[0]
        second_payload = client.table.return_value.insert.call_args_list[1].args[0]
        self.assertEqual(first_payload["project_mode"], "general")
        self.assertNotIn("project_mode", second_payload)

    def test_taichang_project_never_silently_downgrades_on_legacy_schema(self):
        client = MagicMock()
        client.table.return_value.insert.return_value.execute.side_effect = RuntimeError(
            "Could not find the 'project_mode' column in the schema cache"
        )
        with (
            patch("backend.db.supabase_repo.get_supabase_client", return_value=client),
            self.assertRaisesRegex(RuntimeError, "项目模式迁移"),
        ):
            create_bid_project_for_upload("测试项目.docx", project_mode="taichang_reuse")

        self.assertEqual(client.table.return_value.insert.call_count, 1)


if __name__ == "__main__":
    unittest.main()

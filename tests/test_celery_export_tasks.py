"""DOCX 导出 Celery 迁移的集成冒烟测试（P1-1 第一批）。

目标：在缺乏 E2E 保护网的情况下，为被迁移的 DOCX 导出任务建立 HTTP 路由级
回归保护。测试以 Celery eager 模式运行（CELERY_TASK_ALWAYS_EAGER=true），
任务同步执行，无需独立 worker 进程；外部重型依赖（Markdown 构建、Word 转换、
LibreOffice 刷新、DB 写入）全部 mock 掉。

覆盖需求：
- 创建任务接口返回 201 且响应字段契约不变（task / taskId / projectId）。
- 任务成功路径把状态写为 completed。
- 任务失败路径把状态写为 failed（验证“重启不再无痕丢失”的失败可见性）。
- 查询任务接口返回当前状态，且 404 / 400 契约不变。
"""

import os
import unittest
from unittest.mock import patch

# 必须在导入 main / celery_app 之前设置，确保 Celery 以 eager 模式构建。
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_LOGIN_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")

VALID_PROJECT_ID = "11111111-1111-4111-8111-111111111111"
VALID_TASK_ID = "22222222-2222-4222-8222-222222222222"
VALID_SECTION_ID = "33333333-3333-4333-8333-333333333333"


def _formal_check_report(blocked=0):
    blockers = [
        {
            "id": "required_field_missing",
            "category": "客户确认字段",
            "severity": "blocker",
            "title": "正式必填字段未确认",
            "status": "blocked",
            "blocksFormalExport": True,
            "evidence": "投标总价未确认。",
            "suggestion": "请先完成投标确认。",
        }
    ][:blocked]
    return {
        "ruleSetVersion": "formal_bid_check_rules.v1",
        "generatedAt": "2026-06-25T00:00:00+00:00",
        "summary": {
            "blocked": blocked,
            "warnings": 0,
            "manualConfirm": 0,
            "canFormalExport": blocked == 0,
            "draftExportAllowed": True,
            "formalExportLabel": "允许正式版导出" if blocked == 0 else "仅允许草稿版导出",
            "formalRequiredGaps": blocked,
            "unresolvedPlaceholderCount": 0,
            "compliancePercent": 100,
            "highRiskMissing": 0,
        },
        "items": blockers,
    }


class DocxExportCeleryMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["APP_AUTH_ENABLED"] = "false"
        os.environ["APP_LOGIN_ENABLED"] = "false"
        import main

        cls.app = main.app
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def setUp(self):
        os.environ["APP_AUTH_ENABLED"] = "false"
        os.environ["APP_LOGIN_ENABLED"] = "false"

    def test_celery_app_runs_in_eager_mode_for_tests(self):
        from backend.tasks.celery_app import celery_app

        self.assertTrue(celery_app.conf.task_always_eager)

    def test_download_docx_dispatches_celery_task_and_keeps_contract(self):
        created_task = {"id": VALID_TASK_ID, "status": "queued", "progress": 0}

        with (
            patch("backend.api.export.create_bid_export_task", return_value=created_task) as create_mock,
            patch("backend.api.export.build_formal_bid_check_report", return_value=_formal_check_report(blocked=0)),
            patch("backend.tasks.export_tasks.run_bid_docx_export.delay") as delay_mock,
        ):
            response = self.client.post(
                f"/api/bidding/interpretations/{VALID_PROJECT_ID}/download-docx",
                json={"withImages": False},
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        # 契约字段保持不变
        self.assertEqual(payload["projectId"], VALID_PROJECT_ID)
        self.assertEqual(payload["taskId"], VALID_TASK_ID)
        self.assertEqual(payload["task"], created_task)
        create_mock.assert_called_once()
        self.assertEqual(payload["exportMode"], "formal")
        self.assertEqual(payload["formalExportGate"]["export_mode"], "formal")
        self.assertEqual(create_mock.call_args.kwargs["metadata"]["formal_export_gate"]["export_mode"], "formal")
        # 改为投递 Celery 任务，而不是起线程
        delay_mock.assert_called_once()

    def test_download_docx_defaults_to_with_images_for_taichang_mvp(self):
        created_task = {"id": VALID_TASK_ID, "status": "queued", "progress": 0}

        with (
            patch("backend.api.export.create_bid_export_task", return_value=created_task) as create_mock,
            patch("backend.api.export.build_formal_bid_check_report", return_value=_formal_check_report(blocked=0)),
            patch("backend.tasks.export_tasks.run_bid_docx_export.delay") as delay_mock,
        ):
            response = self.client.post(
                f"/api/bidding/interpretations/{VALID_PROJECT_ID}/download-docx",
                json={},
            )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.get_json()["withImages"])
        self.assertTrue(create_mock.call_args.kwargs["with_images"])
        self.assertTrue(delay_mock.call_args.args[3])

    def test_download_docx_marks_draft_when_formal_check_has_blockers(self):
        created_task = {"id": VALID_TASK_ID, "status": "queued", "progress": 0}

        with (
            patch("backend.api.export.create_bid_export_task", return_value=created_task) as create_mock,
            patch("backend.api.export.build_formal_bid_check_report", return_value=_formal_check_report(blocked=1)),
            patch("backend.tasks.export_tasks.run_bid_docx_export.delay") as delay_mock,
        ):
            response = self.client.post(
                f"/api/bidding/interpretations/{VALID_PROJECT_ID}/download-docx",
                json={"volumeType": "technical"},
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(payload["exportMode"], "draft")
        self.assertEqual(payload["formalExportGate"]["blocked_count"], 1)
        self.assertEqual(payload["formalExportGate"]["top_blockers"][0]["id"], "required_field_missing")
        self.assertEqual(create_mock.call_args.kwargs["scope"], "volume")
        self.assertEqual(create_mock.call_args.kwargs["metadata"]["formal_export_gate"]["export_mode"], "draft")
        self.assertEqual(delay_mock.call_args.args[6]["formal_export_gate"]["export_mode"], "draft")

    def test_section_docx_export_does_not_run_full_formal_gate(self):
        created_task = {"id": VALID_TASK_ID, "status": "queued", "progress": 0}

        with (
            patch("backend.api.export.create_bid_export_task", return_value=created_task) as create_mock,
            patch("backend.api.export.build_formal_bid_check_report") as formal_check_mock,
            patch("backend.tasks.export_tasks.run_bid_docx_export.delay") as delay_mock,
        ):
            response = self.client.post(
                f"/api/bidding/interpretations/{VALID_PROJECT_ID}/download-docx",
                json={"sectionId": VALID_SECTION_ID},
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        formal_check_mock.assert_not_called()
        self.assertEqual(payload["exportMode"], "section")
        self.assertEqual(payload["formalExportGate"]["checked"], False)
        self.assertEqual(create_mock.call_args.kwargs["scope"], "section")
        self.assertEqual(delay_mock.call_args.args[2], VALID_SECTION_ID)

    def test_download_docx_rejects_invalid_project_id(self):
        response = self.client.post(
            "/api/bidding/interpretations/not-a-uuid/download-docx",
            json={},
        )
        self.assertEqual(response.status_code, 400)

    def test_export_task_success_path_marks_completed(self):
        """eager 模式下直接执行任务，验证成功路径写 completed。"""
        from backend.tasks.export_tasks import run_bid_docx_export

        updates = []

        def fake_update(project_id, task_id, patch_payload):
            updates.append(patch_payload)
            return patch_payload

        from pathlib import Path as _Path

        with (
            patch(
                "backend.api.routes.build_project_bid_markdown",
                return_value=("/tmp/fake.md", "测试项目", {"found": 0}),
            ),
            patch(
                "backend.export.md_to_word.convert_md_to_word",
                return_value=("/tmp/fake.docx", {"inserted": 0}),
            ),
            patch(
                "backend.export.md_to_word.refresh_docx_fields_with_soffice",
                return_value=(_Path("/tmp/fake.docx"), {"status": "refreshed", "user_message": "ok"}),
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("backend.api.routes._output_url_for_path", return_value="/api/outputs/fake.docx"),
            patch("backend.db.supabase_repo.update_bid_export_task", side_effect=fake_update),
        ):
            result = run_bid_docx_export.apply(
                args=(VALID_PROJECT_ID, VALID_TASK_ID, None, False, None, None)
            ).get()

        self.assertEqual(result["status"], "completed")
        statuses = [u.get("status") for u in updates if "status" in u]
        self.assertIn("running", statuses)
        self.assertIn("completed", statuses)

    def test_export_task_preserves_initial_formal_gate_metadata(self):
        """任务完成时不覆盖导出前门禁 metadata，前端轮询仍能识别草稿版。"""
        from backend.tasks.export_tasks import run_bid_docx_export

        updates = []

        def fake_update(project_id, task_id, patch_payload):
            updates.append(patch_payload)
            return patch_payload

        from pathlib import Path as _Path

        initial_metadata = {
            "requested_from": "bid_editor",
            "formal_export_gate": {
                "export_mode": "draft",
                "blocked_count": 1,
            },
        }

        with (
            patch(
                "backend.api.routes.build_project_bid_markdown",
                return_value=("/tmp/fake.md", "测试项目", {"found": 0}),
            ),
            patch(
                "backend.export.md_to_word.convert_md_to_word",
                return_value=("/tmp/fake.docx", {"inserted": 0}),
            ),
            patch(
                "backend.export.md_to_word.refresh_docx_fields_with_soffice",
                return_value=(_Path("/tmp/fake.docx"), {"status": "refreshed", "user_message": "ok"}),
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("backend.api.routes._output_url_for_path", return_value="/api/outputs/fake.docx"),
            patch("backend.db.supabase_repo.update_bid_export_task", side_effect=fake_update),
        ):
            result = run_bid_docx_export.apply(
                args=(VALID_PROJECT_ID, VALID_TASK_ID, None, False, None, None, initial_metadata)
            ).get()

        self.assertEqual(result["status"], "completed")
        completed_update = next(update for update in updates if update.get("status") == "completed")
        self.assertEqual(completed_update["metadata"]["formal_export_gate"]["export_mode"], "draft")
        self.assertEqual(completed_update["metadata"]["formal_export_gate"]["blocked_count"], 1)

    def test_export_task_failure_path_marks_failed(self):
        """任务执行异常时写 failed 状态，保证重启场景失败可见、不再无痕丢失。"""
        from backend.tasks.export_tasks import run_bid_docx_export

        updates = []

        def fake_update(project_id, task_id, patch_payload):
            updates.append(patch_payload)
            return patch_payload

        with (
            patch(
                "backend.api.routes.build_project_bid_markdown",
                side_effect=RuntimeError("markdown build boom"),
            ),
            patch("backend.db.supabase_repo.update_bid_export_task", side_effect=fake_update),
        ):
            result = run_bid_docx_export.apply(
                args=(VALID_PROJECT_ID, VALID_TASK_ID, None, False, None, None)
            ).get()

        self.assertEqual(result["status"], "failed")
        statuses = [u.get("status") for u in updates if "status" in u]
        self.assertIn("failed", statuses)

    def test_get_export_task_returns_404_when_missing(self):
        with patch("backend.api.export.get_bid_export_task", return_value=None):
            response = self.client.get(
                f"/api/bidding/interpretations/{VALID_PROJECT_ID}/export-tasks/{VALID_TASK_ID}"
            )
        self.assertEqual(response.status_code, 404)

    def test_get_export_task_returns_task_when_found(self):
        task = {"id": VALID_TASK_ID, "status": "completed", "progress": 100}
        with patch("backend.api.export.get_bid_export_task", return_value=task):
            response = self.client.get(
                f"/api/bidding/interpretations/{VALID_PROJECT_ID}/export-tasks/{VALID_TASK_ID}"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["task"], task)


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_LOGIN_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")
# 解析状态文件型测试依赖本地 mineru_status.json，固定走 file 后端，
# 与生产默认的 db 后端隔离，保证这些测试语义不变。
os.environ.setdefault("PARSE_STATUS_BACKEND", "file")


class BackendSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main
        cls.app = main.app
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_health_check(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["version"]["app"], "ai-bidding-backend")
        self.assertIn("commit", payload["version"])
        self.assertRegex(response.headers.get("X-Request-Id", ""), r"^req_\d{14}_[a-f0-9]{10}$")

    def test_ready_reports_dependency_status(self):
        with (
            patch("backend.api.health._check_database", return_value={"status": "ok"}),
            patch("backend.api.health._check_redis", return_value={"status": "ok"}),
            patch("backend.api.health._check_storage", return_value={"status": "ok", "provider": "local"}),
            patch("backend.api.health._check_model_config", return_value={"status": "warn", "required": {}, "optional": {}}),
        ):
            response = self.client.get("/api/ready")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertIn("database", payload["checks"])
        self.assertIn("redis", payload["checks"])
        self.assertIn("storage", payload["checks"])
        self.assertIn("model_config", payload["checks"])

    def test_ready_fails_when_required_dependency_fails(self):
        with (
            patch("backend.api.health._check_database", return_value={"status": "fail", "message": "db down"}),
            patch("backend.api.health._check_redis", return_value={"status": "ok"}),
            patch("backend.api.health._check_storage", return_value={"status": "ok", "provider": "local"}),
            patch("backend.api.health._check_model_config", return_value={"status": "ok", "required": {}, "optional": {}}),
        ):
            response = self.client.get("/api/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["status"], "fail")

    def test_ready_bypasses_login_guard_for_deployment_probe(self):
        with (
            patch.dict(os.environ, {"APP_LOGIN_ENABLED": "true"}),
            patch("backend.api.health._check_database", return_value={"status": "ok"}),
            patch("backend.api.health._check_redis", return_value={"status": "ok"}),
            patch("backend.api.health._check_storage", return_value={"status": "ok", "provider": "local"}),
            patch("backend.api.health._check_model_config", return_value={"status": "warn", "required": {}, "optional": {}}),
        ):
            response = self.client.get("/api/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_security_sanitizer_redacts_common_secret_patterns(self):
        from backend.core.security import sanitize_exception_message

        raw = (
            "Authorization: Bearer secret-token "
            "postgresql://bidding:plain-password@db.example.com:5432/bidding "
            "OSS_ACCESS_KEY_SECRET=abc123"
        )

        sanitized = sanitize_exception_message(raw)

        self.assertNotIn("secret-token", sanitized)
        self.assertNotIn("plain-password", sanitized)
        self.assertNotIn("abc123", sanitized)
        self.assertIn("***", sanitized)

    def test_upload_rejects_disallowed_extension_before_external_services(self):
        response = self.client.post(
            "/api/bidding/upload",
            data={
                "userId": "smoke-user",
                "file": (BytesIO(b"not a tender"), "bad.exe"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("不在允许范围", response.get_json().get("error", ""))

    def test_safe_upload_filename_preserves_chinese_pdf_extension(self):
        from backend.core.security import safe_upload_filename

        self.assertEqual(safe_upload_filename("招标文件.pdf", "tender"), "tender.pdf")

    @patch("backend.api.mineru.get_bid_file", return_value=None)
    @patch("backend.tasks.parse_tasks.retry_mineru_download.delay")
    def test_parse_status_exposes_retryable_mineru_failure(self, retry_mock, _file_mock):
        file_id = "smoke-parse-status"
        status_dir = Path("parsed_outputs") / file_id
        status_dir.mkdir(parents=True, exist_ok=True)
        (status_dir / "mineru_status.json").write_text(
            json.dumps(
                {
                    "parse_status": "mineru_download_failed",
                    "batch_id": "batch-smoke",
                    "mineru_state": "done",
                    "retryable": True,
                    "failure_stage": "download",
                    "error_type": "MinerUDownloadError",
                    "user_message": "MinerU 结果下载失败，可断点重试。",
                    "download_retry_count": 2,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        response = self.client.get(f"/api/bidding/parse-status/{file_id}")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["parseStatus"], "mineru_download_retrying")
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["failureStage"], "download")
        self.assertEqual(payload["errorType"], "MinerUDownloadError")
        self.assertEqual(payload["downloadRetryCount"], 2)
        retry_mock.assert_called_once_with(file_id)

    @patch("backend.api.mineru.get_bid_file", return_value=None)
    def test_parse_status_treats_mineru_done_ingest_as_completed(self, _file_mock):
        file_id = "smoke-parse-completed"
        status_dir = Path("parsed_outputs") / file_id
        status_dir.mkdir(parents=True, exist_ok=True)
        (status_dir / "mineru_status.json").write_text(
            json.dumps(
                {
                    "parse_status": "mineru_done",
                    "artifacts": {"markdown_path": "parsed_outputs/demo/full.md"},
                    "supabase_ingest_status": "done",
                    "user_message": "后台解析任务未继续推进，系统正在自动恢复解析。",
                    "retryable": True,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        response = self.client.get(f"/api/bidding/parse-status/{file_id}")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["parseStatus"], "mineru_done")
        self.assertTrue(payload["parseCompleted"])
        self.assertIsNone(payload["userMessage"])
        self.assertFalse(payload["retryable"])

    @patch("backend.api.mineru.get_bid_file", return_value=None)
    def test_parse_status_treats_ingested_artifacts_as_completed_even_if_status_failed(self, _file_mock):
        file_id = "smoke-parse-completed-after-download-error"
        status_dir = Path("parsed_outputs") / file_id
        status_dir.mkdir(parents=True, exist_ok=True)
        (status_dir / "mineru_status.json").write_text(
            json.dumps(
                {
                    "parse_status": "mineru_download_failed",
                    "artifacts": {"markdown_path": "parsed_outputs/demo/full.md"},
                    "supabase_ingest_status": "done",
                    "user_message": "MinerU 已完成解析，但结果 zip 下载失败。",
                    "retryable": True,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        response = self.client.get(f"/api/bidding/parse-status/{file_id}")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["parseStatus"], "mineru_download_failed")
        self.assertTrue(payload["parseCompleted"])
        self.assertIsNone(payload["userMessage"])
        self.assertFalse(payload["retryable"])

    @patch("backend.tasks.parse_tasks.ingest_artifacts.delay")
    @patch("backend.api.mineru.get_bid_file", return_value=None)
    def test_parse_status_binds_project_and_triggers_ingest_for_orphan_artifacts(self, _file_mock, ingest_delay_mock):
        file_id = "smoke-parse-orphan-artifacts"
        project_id = "11111111-1111-4111-8111-111111111111"
        status_dir = Path("parsed_outputs") / file_id
        status_dir.mkdir(parents=True, exist_ok=True)
        (status_dir / "mineru_status.json").write_text(
            json.dumps(
                {
                    "parse_status": "mineru_done",
                    "artifacts": {"markdown_path": "parsed_outputs/demo/full.md"},
                    "supabase_ingest_status": "skipped",
                    "supabase_ingest_reason": "project_id is missing",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        response = self.client.get(f"/api/bidding/parse-status/{file_id}?projectId={project_id}")
        payload = response.get_json()
        status = json.loads((status_dir / "mineru_status.json").read_text(encoding="utf-8"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(status["project_id"], project_id)
        self.assertEqual(payload["parseStatus"], "mineru_done")
        self.assertFalse(payload["parseCompleted"])
        self.assertEqual(status["supabase_ingest_status"], "running")
        ingest_delay_mock.assert_called()


class DocxExportSmokeTest(unittest.TestCase):
    def test_missing_markdown_image_does_not_break_docx_export(self):
        from backend.export.md_to_word import convert_md_to_word

        with tempfile.TemporaryDirectory() as tmpdir:
            markdown_path = Path(tmpdir) / "missing-image.md"
            markdown_path.write_text(
                "# 测试项目\n\n## 章节\n\n![不存在图片](/tmp/not-exist-image.png)\n\n正文内容。\n",
                encoding="utf-8",
            )

            output_path, report = convert_md_to_word(markdown_path, return_report=True)

            self.assertTrue(output_path.exists())
            self.assertEqual(report["found"], 1)
            self.assertEqual(report["inserted"], 0)
            self.assertEqual(report["skipped"], 1)
            self.assertEqual(report["failed"], 0)


if __name__ == "__main__":
    unittest.main()

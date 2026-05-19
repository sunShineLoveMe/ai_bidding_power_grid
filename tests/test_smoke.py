import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


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
        self.assertEqual(response.get_json(), {"status": "ok"})

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
    @patch("backend.api.mineru.retry_mineru_result_download")
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

    @patch("backend.api.mineru.threading.Thread")
    @patch("backend.api.mineru.get_bid_file", return_value=None)
    def test_parse_status_binds_project_and_triggers_ingest_for_orphan_artifacts(self, _file_mock, thread_mock):
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
        thread_mock.assert_called()


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

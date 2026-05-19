import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from backend.parsing.document_parser import _should_use_mineru_first, import_mineru_result_zip, read_parse_status, write_parse_status
from backend.parsing.mineru_client import download_and_extract_zip


class MinerUStatusRegressionTest(unittest.TestCase):
    def test_pdf_without_saved_extension_still_uses_mineru_when_original_name_is_pdf(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            local_file = Path(tmpdir) / "uuid-pdf"
            local_file.write_bytes(b"%PDF-1.7\n")

            self.assertTrue(_should_use_mineru_first(str(local_file), "招标文件.pdf"))

    def test_manual_import_bad_zip_writes_import_failed_status(self):
        parse_id = "mineru-import-bad-zip-smoke"
        output_dir = Path("parsed_outputs") / parse_id
        output_dir.mkdir(parents=True, exist_ok=True)
        bad_zip = output_dir / "bad.zip"
        bad_zip.write_bytes(b"not a valid zip")

        with self.assertRaises(Exception):
            import_mineru_result_zip(parse_id, bad_zip)

        status = read_parse_status(parse_id) or {}
        self.assertEqual(status.get("parse_status"), "mineru_import_failed")
        self.assertEqual(status.get("failure_stage"), "manual_import")
        self.assertTrue(status.get("retryable"))
        self.assertIn("导入失败", status.get("user_message", ""))

    @patch("backend.parsing.mineru_client._host_uses_fake_ip", return_value=False)
    @patch("backend.parsing.mineru_client._download_session")
    def test_download_resume_uses_existing_partial_file(self, session_mock, _fake_ip_mock):
        captured_headers = {}

        class ResumeResponse:
            status_code = 206

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size=8192):
                yield b"-end"

        def fake_get(_url, **kwargs):
            captured_headers.update(kwargs.get("headers") or {})
            return ResumeResponse()

        session_mock.return_value.get.side_effect = fake_get
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "mineru_result.zip.part").write_bytes(b"partial")
            with patch.dict(
                "os.environ",
                {
                    "MINERU_DOWNLOAD_USE_CURL_FALLBACK": "false",
                    "MINERU_DOWNLOAD_KEEP_PARTIAL": "true",
                    "MINERU_DOWNLOAD_RESUME": "true",
                },
                clear=False,
            ):
                with self.assertRaises(Exception):
                    download_and_extract_zip("https://example.com/mineru.zip", tmpdir, timeout=1)

            zip_path = Path(tmpdir) / "mineru_result.zip"
            self.assertEqual(captured_headers.get("Range"), "bytes=7-")
            self.assertTrue(zip_path.exists())
            self.assertEqual(zip_path.read_bytes(), b"partial-end")

    @patch("backend.parsing.mineru_client.subprocess.run")
    @patch("backend.parsing.mineru_client._host_uses_fake_ip", return_value=True)
    @patch("backend.parsing.mineru_client._resolve_download_host", return_value=[])
    def test_curl_success_without_output_file_reports_download_error(self, _resolve_mock, _fake_ip_mock, run_mock):
        run_mock.return_value = Mock(returncode=0, stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(Exception) as ctx:
                download_and_extract_zip("https://example.com/mineru.zip", tmpdir, timeout=1)

        self.assertIn("output file was not created or is empty", str(ctx.exception))

    def test_extract_valid_zip_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "result.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("full.md", "# 解析结果\n\n正文")
                zf.writestr("demo_content_list.json", json.dumps([{"type": "text", "text": "正文"}], ensure_ascii=False))

            from backend.parsing.mineru_client import extract_zip_artifacts

            artifacts = extract_zip_artifacts(zip_path, Path(tmpdir) / "extract-output")

            self.assertTrue(artifacts["markdown_path"].endswith("full.md"))
            self.assertTrue(artifacts["content_list_path"].endswith("_content_list.json"))


if __name__ == "__main__":
    unittest.main()

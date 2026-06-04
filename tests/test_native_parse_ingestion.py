import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_LOGIN_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


class NativeParseIngestionTest(unittest.TestCase):
    def test_native_text_path_ingests_business_analysis_before_indexed(self):
        from backend.parsing import document_parser

        project_id = "11111111-1111-1111-1111-111111111111"
        file_id = "22222222-2222-2222-2222-222222222222"

        with tempfile.TemporaryDirectory() as tmp:
            doc_path = Path(tmp) / "招标文件.docx"
            doc_path.write_bytes(b"fake-docx")

            with (
                patch("backend.parsing.document_parser.has_mineru_token", return_value=False),
                patch("backend.parsing.document_parser.ensure_extractable_text", return_value=["招标编号：0526AB\n资格要求：投标人应具备相关资质。"]),
                patch("backend.parsing.document_parser.read_parse_status", return_value={"project_id": project_id, "supabase_file_id": file_id}),
                patch("backend.parsing.document_parser.write_parse_status") as write_status,
                patch("backend.parsing.document_parser._update_supabase_status") as update_status,
                patch("backend.parsing.document_parser.ingest_mineru_artifacts_to_supabase", return_value={"chunks": 1}) as ingest,
            ):
                document_parser.parse_and_index_tender_file(
                    file_path=str(doc_path),
                    original_filename="招标文件.docx",
                    parse_id=file_id,
                    supabase_file_id=file_id,
                )

        ingest.assert_called_once()
        kwargs = ingest.call_args.kwargs
        self.assertEqual(kwargs["project_id"], project_id)
        self.assertEqual(kwargs["bid_file_id"], file_id)
        self.assertTrue(kwargs["artifacts"]["markdown_path"].endswith("full.md"))
        update_status.assert_called_with(file_id, "indexed")
        indexed_payloads = [call.args[1] for call in write_status.call_args_list if call.args[1].get("parse_status") == "indexed"]
        self.assertTrue(indexed_payloads)
        self.assertEqual(indexed_payloads[-1]["parser"], "native_text")


if __name__ == "__main__":
    unittest.main()

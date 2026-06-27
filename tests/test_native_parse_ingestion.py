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
                patch("backend.parsing.document_parser.PARSED_OUTPUT_ROOT", Path(tmp) / "parsed_outputs"),
                patch("backend.parsing.document_parser.ensure_extractable_text", return_value=[
                    "\n".join([
                        "# 国网辽宁电力2025年第三次物资协议库存招标采购招标文件",
                        "招标编号：0526AB",
                        "分标编号：102-CPVC",
                        "分标名称：电缆保护管",
                        "包号：包1",
                        "包名称：CPVC电缆保护管包1",
                        "招标人：国网辽宁省电力有限公司",
                        "招标代理机构：国网辽宁招标有限公司",
                        "资格要求：投标人应具备相关资质。",
                    ])
                ]),
                patch("backend.parsing.document_parser.read_parse_status", return_value={"project_id": project_id, "supabase_file_id": file_id}),
                patch("backend.parsing.document_parser.write_parse_status") as write_status,
                patch("backend.parsing.document_parser._update_supabase_status") as update_status,
                patch("backend.parsing.bid_interpreter.replace_bid_analysis") as replace_analysis,
                patch("backend.parsing.bid_interpreter.replace_project_rows", return_value=[]),
                patch("backend.parsing.bid_interpreter.update_bid_project_metadata_fields") as update_project,
            ):
                document_parser.parse_and_index_tender_file(
                    file_path=str(doc_path),
                    original_filename="招标文件.docx",
                    parse_id=file_id,
                    supabase_file_id=file_id,
                )

        replace_analysis.assert_called_once()
        saved_analysis = replace_analysis.call_args.args[1]
        saved_meta = saved_analysis["project_meta"]
        self.assertEqual(saved_meta["cover_fields"]["招标编号"], "0526AB")
        self.assertEqual(saved_meta["cover_fields"]["分标编号"], "102-CPVC")
        self.assertEqual(saved_meta["cover_fields"]["包名称"], "CPVC电缆保护管包1")
        update_project.assert_called_once()
        self.assertEqual(update_project.call_args.args[0], project_id)
        self.assertEqual(update_project.call_args.args[1]["project_no"], "0526AB")
        update_status.assert_called_with(file_id, "indexed")
        indexed_payloads = [call.args[1] for call in write_status.call_args_list if call.args[1].get("parse_status") == "indexed"]
        self.assertTrue(indexed_payloads)
        self.assertEqual(indexed_payloads[-1]["parser"], "native_text")


if __name__ == "__main__":
    unittest.main()

"""招标解析 / 知识库入库 Celery 迁移的集成冒烟测试（P1-1 第二批）。

目标：在零 E2E 保护网下，为高风险的解析链路迁移建立 HTTP 路由级回归保护。
- 验证上传 / 重试解析 / 知识库上传都改为投递 Celery 任务，而非裸线程。
- 验证前端契约字段不变（fileId / projectId / supabaseFileId / documentId）。
- 验证 DB 后端 parse_status_store 的写合并 / 读 / 按文件查找语义。

外部重型依赖（Supabase 同步、MinerU、入库）全部 mock；DB store 用例需要本地
PostgreSQL（DATABASE_URL），无法连接时自动跳过，不阻塞其余用例。
"""

import os
import unittest
from unittest.mock import patch

os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["APP_AUTH_ENABLED"] = "false"
os.environ["APP_LOGIN_ENABLED"] = "false"
os.environ["APP_EXPOSE_DEBUG_ERRORS"] = "false"
os.environ["REQUIRE_STRICT_CONFIG"] = "false"
os.environ["APP_ENV"] = "testing"
# 路由调度类用例与 DB 无关，固定 file 后端避免误连 DB；DB 语义用例内部单独切 db。
os.environ.setdefault("PARSE_STATUS_BACKEND", "file")

VALID_PROJECT_ID = "33333333-3333-4333-8333-333333333333"
VALID_FILE_ID = "44444444-4444-4444-8444-444444444444"


class TenderParseDispatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.app = main.app
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_parse_task_modules_registered(self):
        from backend.tasks.celery_app import celery_app

        celery_app.loader.import_default_modules()
        names = set(celery_app.tasks.keys())
        for expected in [
            "bid.parse.sync_and_parse_tender",
            "bid.parse.parse_and_index_tender",
            "bid.parse.retry_download",
            "bid.parse.ingest_artifacts",
            "bid.knowledge.sync_and_parse",
            "bid.outline.refine",
        ]:
            self.assertIn(expected, names)

    def test_upload_dispatches_celery_and_keeps_contract(self):
        from io import BytesIO

        sync_result = {
            "project": {"id": VALID_PROJECT_ID},
            "file": {"id": VALID_FILE_ID},
        }
        with (
            patch("backend.api.projects.sync_uploaded_tender_to_supabase", return_value=sync_result),
            patch("backend.api.projects.write_parse_status"),
            patch("backend.tasks.parse_tasks.sync_and_parse_tender.delay") as delay_mock,
        ):
            response = self.client.post(
                "/api/bidding/upload",
                data={"userId": "tester", "file": (BytesIO(b"%PDF-1.4 fake"), "tender.pdf")},
                content_type="multipart/form-data",
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(payload["projectId"], VALID_PROJECT_ID)
        self.assertEqual(payload["projectMode"], "general")
        self.assertEqual(payload["supabaseFileId"], VALID_FILE_ID)
        self.assertIn("fileId", payload)
        self.assertIsNone(payload["biddingId"])
        delay_mock.assert_called_once()

    def test_upload_accepts_explicit_taichang_reuse_mode(self):
        from io import BytesIO

        sync_result = {
            "project": {"id": VALID_PROJECT_ID, "project_mode": "taichang_reuse"},
            "file": {"id": VALID_FILE_ID},
        }
        with (
            patch.dict(os.environ, {"TAICHANG_REUSE_ENABLED": "true"}),
            patch("backend.api.projects.sync_uploaded_tender_to_supabase", return_value=sync_result) as sync_mock,
            patch("backend.api.projects.write_parse_status"),
            patch("backend.tasks.parse_tasks.sync_and_parse_tender.delay"),
        ):
            response = self.client.post(
                "/api/bidding/upload",
                data={
                    "userId": "tester",
                    "projectMode": "taichang_reuse",
                    "file": (BytesIO(b"%PDF-1.4 fake"), "tender.pdf"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["projectMode"], "taichang_reuse")
        self.assertEqual(sync_mock.call_args.kwargs["project_mode"], "taichang_reuse")

    def test_disabled_taichang_mode_does_not_block_general_upload(self):
        from io import BytesIO

        sync_result = {
            "project": {"id": VALID_PROJECT_ID, "project_mode": "general"},
            "file": {"id": VALID_FILE_ID},
        }
        with (
            patch.dict(os.environ, {"TAICHANG_REUSE_ENABLED": "false"}),
            patch("backend.api.projects.sync_uploaded_tender_to_supabase", return_value=sync_result),
            patch("backend.api.projects.write_parse_status"),
            patch("backend.tasks.parse_tasks.sync_and_parse_tender.delay"),
        ):
            response = self.client.post(
                "/api/bidding/upload",
                data={"userId": "tester", "file": (BytesIO(b"%PDF-1.4 fake"), "tender.pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["projectMode"], "general")

    def test_upload_rejects_disabled_or_invalid_project_mode(self):
        from io import BytesIO

        with patch.dict(os.environ, {"TAICHANG_REUSE_ENABLED": "false"}):
            disabled = self.client.post(
                "/api/bidding/upload",
                data={
                    "userId": "tester",
                    "projectMode": "taichang_reuse",
                    "file": (BytesIO(b"%PDF-1.4 fake"), "tender.pdf"),
                },
                content_type="multipart/form-data",
            )
        invalid = self.client.post(
            "/api/bidding/upload",
            data={
                "userId": "tester",
                "projectMode": "unknown_mode",
                "file": (BytesIO(b"%PDF-1.4 fake"), "tender.pdf"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(disabled.status_code, 503)
        self.assertEqual(invalid.status_code, 400)

    def test_retry_parse_dispatches_celery(self):
        file_record = {"id": VALID_FILE_ID, "file_name": "tender.pdf"}
        with (
            patch("backend.api.projects.get_bid_project", return_value={"id": VALID_PROJECT_ID}),
            patch("backend.api.projects.get_latest_bid_file_for_project", return_value=file_record),
            patch("backend.api.projects._find_local_parse_status_for_supabase_file", return_value={}),
            patch("backend.api.projects.download_bid_file_to_local") as dl_mock,
            patch("backend.api.projects.update_bid_file_parse_status"),
            patch("backend.api.projects.write_parse_status"),
            patch("backend.tasks.parse_tasks.parse_and_index_tender.delay") as delay_mock,
        ):
            from pathlib import Path as _Path

            dl_mock.return_value = _Path("/tmp/tender.pdf")
            response = self.client.post(
                f"/api/bidding/history/{VALID_PROJECT_ID}/retry-parse",
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(payload["projectId"], VALID_PROJECT_ID)
        self.assertEqual(payload["supabaseFileId"], VALID_FILE_ID)
        self.assertIn("fileId", payload)
        delay_mock.assert_called_once()

    def test_knowledge_upload_dispatches_celery(self):
        from io import BytesIO

        with (
            patch("backend.api.knowledge.create_knowledge_document", return_value="doc-123"),
            patch("backend.tasks.parse_tasks.sync_and_parse_knowledge.delay") as delay_mock,
        ):
            response = self.client.post(
                "/api/knowledge/upload",
                data={"file": (BytesIO(b"%PDF-1.4 fake"), "kb.pdf")},
                content_type="multipart/form-data",
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(payload["documentId"], "doc-123")
        delay_mock.assert_called_once()


class ParseStatusDbStoreTest(unittest.TestCase):
    """DB 后端解析状态存储语义验证（需要本地 PostgreSQL）。"""

    @classmethod
    def setUpClass(cls):
        cls.database_url = os.getenv(
            "DATABASE_URL", "postgresql://bidding:bidding_local_dev@127.0.0.1:15432/bidding"
        )
        os.environ["DATABASE_URL"] = cls.database_url
        try:
            import psycopg

            with psycopg.connect(cls.database_url, connect_timeout=3) as conn:
                conn.execute("select 1 from public.bid_parse_tasks limit 1")
            cls.db_available = True
        except Exception:
            cls.db_available = False

    def setUp(self):
        if not self.db_available:
            self.skipTest("本地 PostgreSQL 或 bid_parse_tasks 不可用，跳过 DB store 用例")

    def _cleanup(self, prefix):
        import psycopg

        with psycopg.connect(self.database_url) as conn:
            conn.execute("delete from public.bid_parse_tasks where parse_id like %s", (prefix + "%",))

    def test_db_store_merges_and_finds(self):
        with patch.dict(os.environ, {"PARSE_STATUS_BACKEND": "db"}):
            from backend.parsing.parse_status_store import (
                write_parse_status,
                read_parse_status,
                find_parse_status_by_supabase_file,
            )

            pid = "utest-parse-db-001"
            self.addCleanup(self._cleanup, pid)
            write_parse_status(pid, {"parse_status": "uploaded", "supabase_file_id": "f-1", "file_name": "x.pdf"})
            write_parse_status(pid, {"parse_status": "mineru_running"})

            got = read_parse_status(pid)
            self.assertEqual(got["parse_status"], "mineru_running")
            # 浅合并保留早先写入的键
            self.assertEqual(got["supabase_file_id"], "f-1")
            self.assertEqual(got["file_name"], "x.pdf")
            self.assertIn("updated_at", got)

            found = find_parse_status_by_supabase_file("f-1")
            self.assertIsNotNone(found)
            self.assertEqual(found["_parse_id"], pid)

    def test_db_store_handles_non_uuid_split_key(self):
        with patch.dict(os.environ, {"PARSE_STATUS_BACKEND": "db"}):
            from backend.parsing.parse_status_store import write_parse_status, read_parse_status

            pid = "utest-parse-db-002_part001"
            self.addCleanup(self._cleanup, "utest-parse-db-002")
            write_parse_status(pid, {"parse_status": "mineru_submitted"})
            self.assertEqual(read_parse_status(pid)["parse_status"], "mineru_submitted")


if __name__ == "__main__":
    unittest.main()

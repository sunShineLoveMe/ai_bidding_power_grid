import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


class _FakeAuth:
    def __init__(self, key_id, key_secret):
        self.key_id = key_id
        self.key_secret = key_secret


class _FakeOssObject:
    def __init__(self, data: bytes):
        self.data = data

    def read(self):
        return self.data


class _FakeBucket:
    objects: dict[tuple[str, str], bytes] = {}
    uploaded_headers: dict[tuple[str, str], dict | None] = {}

    def __init__(self, _auth, _endpoint, bucket_name):
        self.bucket_name = bucket_name

    def put_object(self, key, data, headers=None):
        self.objects[(self.bucket_name, key)] = bytes(data)
        self.uploaded_headers[(self.bucket_name, key)] = headers

    def put_object_from_file(self, key, file_path, headers=None):
        self.objects[(self.bucket_name, key)] = Path(file_path).read_bytes()
        self.uploaded_headers[(self.bucket_name, key)] = headers

    def get_object(self, key):
        return _FakeOssObject(self.objects[(self.bucket_name, key)])

    def sign_url(self, method, key, expires):
        return f"https://signed.example/{self.bucket_name}/{key}?method={method}&expires={expires}"


class StorageProviderTest(unittest.TestCase):
    def test_local_storage_remains_default(self):
        from backend.db.postgres_compat import PostgresCompatClient

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"STORAGE_PROVIDER": "local", "LOCAL_STORAGE_ROOT": tmpdir}, clear=False):
                client = PostgresCompatClient()
                bucket = client.storage.from_("knowledge-files")
                bucket.upload("demo/file.txt", b"hello", {"content-type": "text/plain"})

                self.assertEqual((Path(tmpdir) / "knowledge-files/demo/file.txt").read_bytes(), b"hello")
                self.assertEqual(bucket.download("demo/file.txt"), b"hello")
                self.assertEqual(bucket.get_public_url("demo/file.txt"), "/local-storage/knowledge-files/demo/file.txt")

    def test_oss_storage_uses_configured_bucket_and_prefix(self):
        fake_oss2 = types.SimpleNamespace(Auth=_FakeAuth, Bucket=_FakeBucket)
        _FakeBucket.objects = {}
        _FakeBucket.uploaded_headers = {}

        from backend.db.postgres_compat import PostgresCompatClient

        env = {
            "STORAGE_PROVIDER": "oss",
            "OSS_ENDPOINT": "https://oss-cn-test.aliyuncs.com",
            "OSS_ACCESS_KEY_ID": "key-id",
            "OSS_ACCESS_KEY_SECRET": "key-secret",
            "OSS_KEY_PREFIX": "ai-bid/test",
            "OSS_SIGNED_URL_EXPIRES": "600",
        }
        with patch.dict(os.environ, env, clear=False), patch.dict(sys.modules, {"oss2": fake_oss2}):
            client = PostgresCompatClient()
            bucket = client.storage.from_("ai-bid-private")
            bucket.upload("knowledge/demo.txt", b"hello", {"content-type": "text/plain"})

            key = ("ai-bid-private", "ai-bid/test/knowledge/demo.txt")
            self.assertEqual(_FakeBucket.objects[key], b"hello")
            self.assertEqual(_FakeBucket.uploaded_headers[key], {"Content-Type": "text/plain"})
            self.assertEqual(bucket.download("knowledge/demo.txt"), b"hello")
            self.assertIn("expires=600", bucket.get_public_url("knowledge/demo.txt"))
            self.assertEqual(
                bucket.create_signed_urls(["knowledge/demo.txt"], 120)[0]["signedURL"],
                "https://signed.example/ai-bid-private/ai-bid/test/knowledge/demo.txt?method=GET&expires=120",
            )

    def test_oss_bucket_name_falls_back_to_shared_bucket(self):
        from backend.db.supabase_client import get_bucket_name

        env = {
            "STORAGE_PROVIDER": "oss",
            "OSS_BUCKET": "shared-bucket",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(get_bucket_name("knowledge"), "shared-bucket")

    def test_local_bucket_names_have_safe_defaults(self):
        from backend.db.supabase_client import get_bucket_name

        env = {
            "STORAGE_PROVIDER": "local",
            "SUPABASE_STORAGE_TENDER_BUCKET": "",
            "SUPABASE_STORAGE_GENERATED_BUCKET": "",
            "SUPABASE_STORAGE_KNOWLEDGE_BUCKET": "",
            "SUPABASE_STORAGE_QUALIFICATION_BUCKET": "",
            "SUPABASE_STORAGE_PRODUCT_BUCKET": "",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(get_bucket_name("tender"), "tender-files")
            self.assertEqual(get_bucket_name("generated"), "generated-docx")
            self.assertEqual(get_bucket_name("knowledge"), "knowledge-files")
            self.assertEqual(get_bucket_name("qualification"), "qualification-files")
            self.assertEqual(get_bucket_name("product"), "product-files")


if __name__ == "__main__":
    unittest.main()

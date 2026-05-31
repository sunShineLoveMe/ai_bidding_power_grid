import unittest
from unittest.mock import patch


class FakeConnection:
    def __init__(self):
        self.closed = False
        self.rollback_count = 0
        self.commit_count = 0
        self.close_count = 0

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = True
        self.close_count += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class PostgresPoolTest(unittest.TestCase):
    def tearDown(self):
        from backend.db.postgres_pool import reset_postgres_pools

        reset_postgres_pools()

    def test_pooled_connection_reuses_idle_connection(self):
        from backend.db.postgres_pool import pooled_connection

        created = []

        def fake_connect(*_args, **_kwargs):
            conn = FakeConnection()
            created.append(conn)
            return conn

        with patch("backend.db.postgres_pool.psycopg.connect", side_effect=fake_connect):
            with patch.dict("os.environ", {"POSTGRES_POOL_ENABLED": "true", "POSTGRES_POOL_MAX_SIZE": "2"}, clear=False):
                with pooled_connection("postgresql://example/db") as first:
                    self.assertIsInstance(first, FakeConnection)
                with pooled_connection("postgresql://example/db") as second:
                    self.assertIs(first, second)

        self.assertEqual(1, len(created))
        self.assertEqual(2, created[0].commit_count)
        self.assertEqual(0, created[0].rollback_count)
        self.assertFalse(created[0].closed)

    def test_pool_can_be_disabled(self):
        from backend.db.postgres_pool import pooled_connection

        created = []

        def fake_connect(*_args, **_kwargs):
            conn = FakeConnection()
            created.append(conn)
            return conn

        with patch("backend.db.postgres_pool.psycopg.connect", side_effect=fake_connect):
            with patch.dict("os.environ", {"POSTGRES_POOL_ENABLED": "false"}, clear=False):
                with pooled_connection("postgresql://example/db") as first:
                    self.assertIsInstance(first, FakeConnection)
                with pooled_connection("postgresql://example/db") as second:
                    self.assertIsInstance(second, FakeConnection)

        self.assertEqual(2, len(created))
        self.assertTrue(all(conn.closed for conn in created))


if __name__ == "__main__":
    unittest.main()

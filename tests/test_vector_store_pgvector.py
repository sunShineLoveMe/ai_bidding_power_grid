import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.rag import vector_store
from backend.rag.vector_store import EmptyDocumentContentError, ensure_extractable_text, get_embeddings


class VectorStorePgvectorTest(unittest.TestCase):
    """P1-9 回归：向量库统一到 pgvector 后，ChromaDB 写/读路径应彻底移除。"""

    def test_chromadb_symbols_are_removed(self):
        # 统一到 pgvector 后，ChromaDB 专属接口不应再存在。
        for symbol in ("file_to_chroma", "query_chroma", "init_chroma_client"):
            self.assertFalse(
                hasattr(vector_store, symbol),
                f"vector_store 不应再暴露 ChromaDB 接口 {symbol}",
            )

    def test_module_does_not_import_chromadb(self):
        # 模块源码不应再 import chromadb，确保依赖可彻底移除。
        source = Path(vector_store.__file__).read_text(encoding="utf-8")
        self.assertNotIn("chromadb", source)

    def test_ensure_extractable_text_returns_chunks_for_real_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            text_file = Path(tmpdir) / "tender.txt"
            text_file.write_text("电网工程招标文件正文内容。" * 50, encoding="utf-8")

            chunks = ensure_extractable_text(str(text_file))

            self.assertTrue(chunks)
            self.assertTrue(all(chunk.strip() for chunk in chunks))

    def test_ensure_extractable_text_raises_for_empty_scanned_like_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_file = Path(tmpdir) / "scanned.txt"
            empty_file.write_text("   \n  \n", encoding="utf-8")

            with self.assertRaises(EmptyDocumentContentError):
                ensure_extractable_text(str(empty_file))

    @patch("backend.rag.vector_store.record_ai_usage_log")
    @patch("backend.rag.vector_store.get_setting")
    @patch("backend.rag.vector_store.requests.post")
    def test_local_openai_compatible_embedding_uses_direct_request(self, post, get_setting, _usage_log):
        def fake_get_setting(key, default=None):
            return {
                "embedding_base_url": "http://localhost:11434/v1",
                "embedding_model": "qwen3-embedding:0.6b",
                "embedding_dimensions": 1024,
                "request_timeout_seconds": 120,
            }.get(key, default)

        response = Mock()
        response.json.return_value = {
            "model": "qwen3-embedding:0.6b",
            "data": [{"embedding": [0.1, 0.2, 0.3]}],
            "usage": {"total_tokens": 3},
        }
        response.raise_for_status.return_value = None
        post.return_value = response
        get_setting.side_effect = fake_get_setting

        embeddings = get_embeddings(Mock(), ["泰昌资质证书"])

        self.assertEqual(embeddings, [[0.1, 0.2, 0.3]])
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["json"]["input"], ["泰昌资质证书"])
        self.assertNotIn("dimensions", post.call_args.kwargs["json"])


if __name__ == "__main__":
    unittest.main()

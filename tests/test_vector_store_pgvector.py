import tempfile
import unittest
from pathlib import Path

from backend.rag import vector_store
from backend.rag.vector_store import EmptyDocumentContentError, ensure_extractable_text


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


if __name__ == "__main__":
    unittest.main()

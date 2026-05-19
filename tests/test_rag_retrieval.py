import os
import unittest
from unittest.mock import Mock, patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


class _ExecuteResult:
    def __init__(self, data):
        self.data = data


class _TableQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return _ExecuteResult(self.rows)


class _RpcClient:
    def __init__(self, rpc_rows=None, asset_rows=None):
        self.rpc_rows = rpc_rows or []
        self.asset_rows = asset_rows or []
        self.rpc_calls = []

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        return _TableQuery(self.rpc_rows)

    def table(self, name):
        if name != "knowledge_assets":
            raise AssertionError(f"unexpected table {name}")
        return _TableQuery(self.asset_rows)


class RagRetrievalQualityTest(unittest.TestCase):
    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.1, 0.2, 0.3]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_text_recall_uses_vector_rpc_and_rerank(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        rows = [
            {"content": "坝基防渗施工方案，包含高压旋喷桩工艺。", "similarity": 0.71},
            {"content": "商务承诺函模板。", "similarity": 0.42},
        ]
        client = _RpcClient(rpc_rows=rows)
        rerank_mock.return_value = [rows[0]]

        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_base("坝基防渗施工方案", match_threshold=0.3, match_count=1)

        self.assertEqual(result, [rows[0]])
        self.assertEqual(client.rpc_calls[0][0], "match_knowledge_chunks")
        self.assertEqual(client.rpc_calls[0][1]["match_threshold"], 0.3)
        rerank_mock.assert_called_once()

    @patch("backend.rag.retrieval.rerank_documents", return_value=[])
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.4, 0.5]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_asset_keyword_fallback_prefers_qualification_for_certificate_query(self, _ali, _embeddings, _rerank):
        from backend.rag import retrieval

        client = _RpcClient(
            rpc_rows=[],
            asset_rows=[
                {
                    "id": "product-1",
                    "title": "高压旋喷桩设备产品图",
                    "asset_type": "product_image",
                    "mime_type": "image/png",
                    "tags": ["产品图", "设备"],
                    "applicable_sections": ["施工组织设计"],
                },
                {
                    "id": "qualification-1",
                    "title": "脱敏营业执照样张",
                    "asset_type": "qualification_image",
                    "mime_type": "image/png",
                    "tags": ["营业执照", "资质证书"],
                    "applicable_sections": ["资格文件"],
                },
            ],
        )

        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_assets("资格文件需要营业执照图片", match_count=2)

        self.assertGreaterEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "qualification-1")
        self.assertGreater(result[0]["similarity"], 0)

    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.4, 0.5]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_asset_vector_recall_returns_strong_assets_without_keyword_fallback(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        strong_assets = [
            {"id": "a1", "title": "水库坝基防渗设备图", "similarity": 0.62, "searchable_text": "防渗设备"},
            {"id": "a2", "title": "帷幕灌浆施工设备图", "similarity": 0.55, "searchable_text": "帷幕灌浆"},
            {"id": "a3", "title": "高压旋喷桩设备图", "similarity": 0.51, "searchable_text": "旋喷桩"},
        ]
        rerank_mock.return_value = strong_assets
        client = _RpcClient(rpc_rows=strong_assets, asset_rows=[])

        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_assets("技术标需要防渗设备图片", match_count=3)

        self.assertEqual([asset["id"] for asset in result], ["a1", "a2", "a3"])
        self.assertEqual(client.rpc_calls[0][0], "match_knowledge_assets")

    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.4, 0.5]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_asset_recall_honors_explicit_applicable_volume_filter(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        def passthrough(_query, rows, **_kwargs):
            return rows

        rerank_mock.side_effect = passthrough
        client = _RpcClient(
            rpc_rows=[
                {"id": "tech", "title": "设备图", "similarity": 0.8, "applicable_volumes": ["technical"], "searchable_text": "设备"},
                {"id": "business", "title": "商务承诺函", "similarity": 0.9, "applicable_volumes": ["business"], "searchable_text": "承诺"},
                {"id": "legacy", "title": "未标注老资产", "similarity": 0.4, "searchable_text": "资料"},
            ],
            asset_rows=[],
        )

        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_assets("技术标设备资料", match_count=3, volume_type="technical")

        self.assertEqual([asset["id"] for asset in result], ["tech", "legacy"])
        self.assertEqual(client.rpc_calls[0][1]["filter_applicable_volume"], "technical")

    def test_knowledge_prompt_contains_sources_assets_and_image_urls(self):
        from backend.rag.retrieval import build_knowledge_prompt

        prompt, images = build_knowledge_prompt(
            "项目经理证书是否可用于资格文件？",
            contexts=[
                {
                    "content": "项目经理应提供注册建造师证书和安全生产考核合格证。",
                    "similarity": 0.82,
                    "metadata": {"source_file": "招标文件.pdf", "doc_type": "资格要求"},
                }
            ],
            assets=[
                {
                    "id": "asset-1",
                    "title": "脱敏项目经理身份证明材料样张",
                    "category": "人员证书",
                    "asset_type": "qualification_image",
                    "similarity": 0.73,
                    "applicable_sections": ["资格文件", "项目管理机构"],
                    "searchable_text": "项目经理证书、人员资料、脱敏示意图。",
                }
            ],
        )

        self.assertIn("招标文件.pdf", prompt)
        self.assertIn("图片资产1", prompt)
        self.assertIn("脱敏项目经理身份证明材料样张", prompt)
        self.assertIn("/api/knowledge/assets/asset-1/file", prompt)
        self.assertEqual(images[-1]["url"], "/api/knowledge/assets/asset-1/file")


if __name__ == "__main__":
    unittest.main()

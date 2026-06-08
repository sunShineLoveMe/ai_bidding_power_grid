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

    def range(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        return _ExecuteResult(self.rows)


class _RpcClient:
    def __init__(self, rpc_rows=None, asset_rows=None, parent_rows=None):
        self.rpc_rows = rpc_rows or []
        self.asset_rows = asset_rows or []
        self.chunk_rows = []
        self.parent_rows = parent_rows or []
        self.rpc_calls = []

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        if name == "get_parent_chunk":
            return _TableQuery(self.parent_rows)
        return _TableQuery(self.rpc_rows)

    def table(self, name):
        if name == "knowledge_assets":
            return _TableQuery(self.asset_rows)
        if name == "document_chunks":
            return _TableQuery(self.chunk_rows)
        raise AssertionError(f"unexpected table {name}")


class RagRetrievalQualityTest(unittest.TestCase):
    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.1, 0.2, 0.3]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_text_recall_uses_filtered_vector_rpc_and_rerank(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        rows = [
            {"content": "配网施工方案，包含接地装置施工工艺。", "similarity": 0.71},
            {"content": "商务承诺函模板。", "similarity": 0.42},
        ]
        client = _RpcClient(rpc_rows=rows)
        rerank_mock.return_value = [rows[0]]

        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_base("配网施工方案", match_threshold=0.3, match_count=1)

        self.assertEqual(result, [rows[0]])
        self.assertEqual(client.rpc_calls[0][0], "match_knowledge_chunks_filtered")
        self.assertEqual(client.rpc_calls[0][1]["match_threshold"], 0.3)
        self.assertEqual(client.rpc_calls[0][1]["filter_metadata"]["chunk_layer"], "child")
        rerank_mock.assert_called_once()

    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.1, 0.2, 0.3]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_writing_recall_can_return_parent_chunk(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        child = {
            "id": "child-1",
            "document_id": "00000000-0000-0000-0000-000000000001",
            "content": "技术响应子块",
            "similarity": 0.77,
            "source_section": "技术响应",
            "metadata": {"chunk_layer": "child", "parent_index": 3, "doc_role": "self_phrase"},
        }
        parent = {
            "id": "parent-1",
            "document_id": child["document_id"],
            "content": "完整技术响应父块上下文",
            "source_section": "技术响应",
            "metadata": {"chunk_layer": "parent", "doc_role": "self_phrase"},
        }
        client = _RpcClient(rpc_rows=[child], parent_rows=[parent])

        def passthrough(_query, rows, **_kwargs):
            return rows

        rerank_mock.side_effect = passthrough
        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_base("技术响应怎么写", scenario="writing", match_count=1)

        self.assertEqual(result[0]["id"], "parent-1")
        self.assertEqual(client.rpc_calls[0][0], "match_knowledge_chunks_filtered")
        self.assertEqual(client.rpc_calls[1][0], "get_parent_chunk")
        self.assertEqual(result[0]["metadata"]["retrieved_by_child"]["id"], "child-1")

    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.1, 0.2, 0.3]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_text_recall_uses_keyword_supplement_when_vector_misses(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        keyword_row = {
            "id": "sgcc-keyword",
            "content": "国家电网供应商管理规定：供应商发生不良行为的，按规定暂停中标资格。",
            "similarity": 0.0,
            "metadata": {
                "chunk_layer": "child",
                "doc_role": "sgcc_rule",
                "authority_level": "law_or_standard",
                "citation_policy": "law_or_standard_citable",
            },
        }
        client = _RpcClient(rpc_rows=[])
        client.chunk_rows = [keyword_row]

        def passthrough(_query, rows, **_kwargs):
            return rows

        rerank_mock.side_effect = passthrough
        retrieval._CHUNK_KEYWORD_CACHE = None
        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_base(
                "国家电网供应商管理对供应商不良行为如何处理？",
                match_threshold=0.3,
                match_count=1,
                metadata_filter={"doc_role": "sgcc_rule"},
            )

        self.assertEqual(result[0]["id"], "sgcc-keyword")
        self.assertEqual(result[0]["retrieval_source"], "keyword")

    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.1, 0.2, 0.3]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_quality_safety_writing_query_splits_domain_terms(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        keyword_row = {
            "id": "quality-safety",
            "content": "质量目标：验收合格。安全目标：落实安全生产责任制和风险预控。",
            "similarity": 0.0,
            "metadata": {
                "chunk_layer": "child",
                "doc_role": "self_phrase",
                "authority_level": "template",
                "citation_policy": "direct_quote_allowed",
            },
        }
        client = _RpcClient(rpc_rows=[])
        client.chunk_rows = [keyword_row]

        def passthrough(_query, rows, **_kwargs):
            return rows

        rerank_mock.side_effect = passthrough
        retrieval._CHUNK_KEYWORD_CACHE = None
        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_base(
                "质量安全环保响应的质量目标和安全目标怎么写？",
                scenario="writing",
                match_threshold=0.3,
                match_count=1,
                metadata_filter={"doc_role": "self_phrase"},
            )

        self.assertEqual(result[0]["id"], "quality-safety")
        self.assertIn("质量目标", retrieval._query_terms("质量安全环保响应的质量目标和安全目标怎么写？"))
        self.assertIn("安全目标", retrieval._query_terms("质量安全环保响应的质量目标和安全目标怎么写？"))

    def test_authority_ranking_pushes_reference_template_behind_citable_sources(self):
        from backend.rag.retrieval import _rank_rows

        rows = [
            {
                "id": "reference",
                "content": "施工工艺章节模板，可参考写法。",
                "similarity": 0.95,
                "metadata": {"authority_level": "reference_template", "citation_policy": "reference_style_only"},
            },
            {
                "id": "standard",
                "content": "配电网施工工艺规范要求施工应符合验收标准。",
                "similarity": 0.82,
                "metadata": {"authority_level": "law_or_standard", "citation_policy": "law_or_standard_citable"},
            },
        ]

        result = _rank_rows("配电网施工工艺规范对施工有哪些要求？", rows, 2)

        self.assertEqual([row["id"] for row in result], ["standard", "reference"])

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

    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.4, 0.5]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_asset_recall_honors_taichang_metadata_filter(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        def passthrough(_query, rows, **_kwargs):
            return rows

        rerank_mock.side_effect = passthrough
        client = _RpcClient(
            rpc_rows=[
                {
                    "id": "taichang",
                    "title": "泰昌营业执照图片",
                    "similarity": 0.8,
                    "searchable_text": "营业执照 泰昌",
                    "metadata": {"enterprise": "泰昌", "source_domain": "enterprise_fact", "reference_only": False},
                },
                {
                    "id": "reference",
                    "title": "河北豪乾营业执照参考图",
                    "similarity": 0.9,
                    "searchable_text": "营业执照 河北豪乾",
                    "metadata": {"enterprise": "河北豪乾", "source_domain": "reference_template", "reference_only": True},
                },
            ],
            asset_rows=[],
        )

        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_assets(
                "泰昌营业执照图片",
                match_count=2,
                metadata_filter={"enterprise": "泰昌", "source_domain": "enterprise_fact", "reference_only": False},
            )

        self.assertEqual([asset["id"] for asset in result], ["taichang"])

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

        self.assertIn("来源 招标文件", prompt)
        self.assertIn("图片资产1", prompt)
        self.assertIn("脱敏项目经理身份证明材料样张", prompt)
        self.assertIn("/api/knowledge/assets/asset-1/file", prompt)
        self.assertEqual(images[-1]["url"], "/api/knowledge/assets/asset-1/file")

    def test_pilot_enterprise_contexts_filter_dedupe_sort_and_limit_sources(self):
        from backend.api.knowledge import _curate_pilot_enterprise_contexts

        contexts = [
            {
                "id": "jiangxi",
                "content": "江西招标文件营业执照要求。",
                "similarity": 0.99,
                "metadata": {"source_file": "江西招标文件.docx", "source_domain": "tender_requirement", "province": "江西"},
            },
            {
                "id": "haoqian",
                "content": "河北豪乾参考稿营业执照。",
                "similarity": 0.98,
                "metadata": {"source_file": "河北豪乾参考稿.docx", "source_domain": "reference_template", "reference_only": True},
            },
            *[
                {
                    "id": f"tc-{index}",
                    "content": f"泰昌企业事实资料 {index}",
                    "similarity": similarity,
                    "metadata": {
                        "source_file": f"泰昌资料{index}.pdf",
                        "enterprise": "泰昌",
                        "source_domain": "enterprise_fact",
                        "fact_source_allowed_for_enterprise": True,
                        "reference_only": False,
                    },
                }
                for index, similarity in enumerate([0.71, 0.95, 0.83, 0.78, 0.66, 0.88], 1)
            ],
            {
                "id": "tc-duplicate-lower",
                "content": "泰昌企业事实资料 duplicate",
                "similarity": 0.52,
                "metadata": {
                    "source_file": "泰昌资料2.pdf",
                    "enterprise": "泰昌",
                    "source_domain": "enterprise_fact",
                    "fact_source_allowed_for_enterprise": True,
                    "reference_only": False,
                },
            },
        ]

        result = _curate_pilot_enterprise_contexts(contexts, limit=5)

        self.assertEqual(len(result), 5)
        self.assertEqual([item["id"] for item in result], ["tc-2", "tc-6", "tc-3", "tc-4", "tc-1"])
        self.assertNotIn("jiangxi", [item["id"] for item in result])
        self.assertNotIn("haoqian", [item["id"] for item in result])


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from unittest.mock import Mock, patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


class _ExecuteResult:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


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
        return _ExecuteResult(self.rows, count=len(self.rows))


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
    def test_invalidate_chunk_keyword_cache_clears_rows_and_fingerprint(self):
        from backend.rag import retrieval

        retrieval._CHUNK_KEYWORD_CACHE = [{"id": "cached"}]
        retrieval._CHUNK_KEYWORD_CACHE_FINGERPRINT = (1, "2026-06-16T00:00:00+08:00", "cached")

        retrieval.invalidate_chunk_keyword_cache("unit_test")

        self.assertIsNone(retrieval._CHUNK_KEYWORD_CACHE)
        self.assertIsNone(retrieval._CHUNK_KEYWORD_CACHE_FINGERPRINT)

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
    def test_keyword_cache_reloads_when_document_chunks_fingerprint_changes(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        old_row = {
            "id": "old-keyword",
            "created_at": "2026-06-16T00:00:00+08:00",
            "content": "国家电网供应商管理规定：旧资料要求暂停中标资格。",
            "similarity": 0.0,
            "metadata": {
                "chunk_layer": "child",
                "doc_role": "sgcc_rule",
                "authority_level": "law_or_standard",
            },
        }
        new_row = {
            "id": "new-keyword",
            "created_at": "2026-06-16T01:00:00+08:00",
            "content": "国家电网供应商管理规定：新增资料要求列入黑名单。",
            "similarity": 0.0,
            "metadata": {
                "chunk_layer": "child",
                "doc_role": "sgcc_rule",
                "authority_level": "law_or_standard",
            },
        }
        client = _RpcClient(rpc_rows=[])
        client.chunk_rows = [old_row]

        def passthrough(_query, rows, **_kwargs):
            return rows

        rerank_mock.side_effect = passthrough
        retrieval.invalidate_chunk_keyword_cache("unit_test_start")
        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            first = retrieval.search_knowledge_base(
                "国家电网供应商管理对供应商不良行为如何处理？",
                match_threshold=0.3,
                match_count=1,
                metadata_filter={"doc_role": "sgcc_rule"},
            )
            client.chunk_rows = [new_row]
            second = retrieval.search_knowledge_base(
                "国家电网供应商管理新增资料如何处理供应商不良行为？",
                match_threshold=0.3,
                match_count=1,
                metadata_filter={"doc_role": "sgcc_rule"},
            )

        self.assertEqual(first[0]["id"], "old-keyword")
        self.assertEqual(second[0]["id"], "new-keyword")
        self.assertEqual(retrieval._CHUNK_KEYWORD_CACHE[0]["id"], "new-keyword")

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

    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.1, 0.2, 0.3]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_transmission_line_workflow_query_splits_domain_terms(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        keyword_row = {
            "id": "transmission-workflow",
            "content": "输电线路：复测分坑、基础开挖浇筑、杆塔组立、架线放线、跨越施工、接地、附件安装、验收消缺。",
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
                "输电线路施工的主要工序有哪些？",
                scenario="writing",
                match_threshold=0.3,
                match_count=1,
                metadata_filter={"doc_role": "self_phrase"},
            )

        self.assertEqual(result[0]["id"], "transmission-workflow")
        terms = retrieval._query_terms("输电线路施工的主要工序有哪些？")
        self.assertIn("输电线路", terms)
        self.assertIn("杆塔组立", terms)
        self.assertIn("架线放线", terms)

    def test_required_evidence_coverage_keeps_contract_and_award_notice(self):
        from backend.rag import retrieval

        rows = [
            {"id": "contract-1", "content": "合同协议书 供货合同 电缆保护管 MPP"},
            {"id": "contract-2", "content": "供货合同 甲方 乙方 交货条款"},
            {"id": "award-1", "content": "中标通知书 招标编号：0322AB 中标单位：河北泰昌电力器材科技有限公司"},
        ]

        selected = retrieval._select_with_required_evidence_coverage(
            "有没有供货合同或中标通知书？",
            rows,
            text_getter=lambda row: row["content"],
            limit=2,
        )

        self.assertEqual({row["id"] for row in selected}, {"contract-1", "award-1"})

    def test_required_evidence_coverage_keeps_three_system_certificates(self):
        from backend.rag import retrieval

        rows = [
            {"id": "esg", "content": "ESG环境社会公司治理报告提到质量管理。"},
            {"id": "quality", "content": "质量管理体系认证证书"},
            {"id": "environment", "content": "环境管理体系认证证书"},
            {"id": "ohs", "content": "职业健康安全管理体系认证证书"},
        ]

        selected = retrieval._select_with_required_evidence_coverage(
            "泰昌有哪些资质证书和体系认证？",
            rows,
            text_getter=lambda row: row["content"],
            limit=3,
        )

        self.assertEqual({row["id"] for row in selected}, {"quality", "environment", "ohs"})

    def test_enterprise_evidence_coverage_prefers_explicit_social_security_asset(self):
        from backend.rag import retrieval

        rows = [
            {"id": "person", "title": "陈仙瑞人员证书", "searchable_text": "来源目录含劳动合同社保证明", "similarity": 0.9},
            {"id": "social", "title": "泰昌社保证明第1页", "searchable_text": "社保证明 参保证明", "similarity": 0.7},
            {"id": "license", "title": "泰昌营业执照副本原图", "searchable_text": "营业执照", "similarity": 0.8},
            {"id": "quality", "title": "质量管理体系认证证书", "searchable_text": "质量管理体系认证证书", "similarity": 0.8},
            {"id": "environment", "title": "环境管理体系认证证书", "searchable_text": "环境管理体系认证证书", "similarity": 0.8},
            {"id": "ohs", "title": "职业健康安全管理体系认证证书", "searchable_text": "职业健康安全管理体系认证证书", "similarity": 0.8},
        ]

        selected = retrieval._select_with_required_evidence_coverage(
            "泰昌有哪些企业证明材料？",
            rows,
            text_getter=lambda row: f"{row['title']} {row['searchable_text']}",
            limit=5,
        )

        self.assertEqual(
            {row["id"] for row in selected},
            {"social", "license", "quality", "environment", "ohs"},
        )

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
    def test_asset_recall_supplements_exact_uploaded_product_title(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        strong_assets = [
            {
                "id": "old-report-1",
                "title": "泰昌CPVC电缆保护管检验报告内径250第1页",
                "similarity": 0.81,
                "asset_type": "product_image",
                "searchable_text": "CPVC电缆保护管 检验报告 内径250",
                "metadata": {"target_library": "product_library", "evidence_type": "inspection_report"},
            },
            {
                "id": "old-report-2",
                "title": "泰昌CPVC电缆保护管检验报告内径250第2页",
                "similarity": 0.79,
                "asset_type": "product_image",
                "searchable_text": "CPVC电缆保护管 检验报告 壁厚",
                "metadata": {"target_library": "product_library", "evidence_type": "inspection_report"},
            },
            {
                "id": "old-report-3",
                "title": "泰昌CPVC电缆保护管检验报告内径250第3页",
                "similarity": 0.77,
                "asset_type": "product_image",
                "searchable_text": "CPVC电缆保护管 检验报告 环刚度",
                "metadata": {"target_library": "product_library", "evidence_type": "inspection_report"},
            },
        ]
        uploaded_asset = {
            "id": "uploaded-product",
            "title": "泰昌CPVC电缆保护管模拟产品图片-20260626065331",
            "similarity": 0.0,
            "asset_type": "product_image",
            "mime_type": "image/png",
            "searchable_text": "泰昌CPVC电缆保护管模拟产品图片-20260626065331 CPVC-DN250-模拟回归 电缆与附件 技术标",
            "tags": ["CPVC", "电缆保护管", "模拟回归"],
            "specs": {"product_model": "CPVC-DN250-模拟回归", "applicable_volumes": ["technical"]},
            "metadata": {"library_type": "product", "applicable_volumes": ["technical"]},
        }

        rerank_mock.return_value = strong_assets
        client = _RpcClient(rpc_rows=strong_assets, asset_rows=[*strong_assets, uploaded_asset])

        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_assets(
                "查询泰昌CPVC电缆保护管模拟产品图片-20260626065331的产品资料",
                match_count=3,
            )

        result_ids = [asset["id"] for asset in result]
        self.assertIn("uploaded-product", result_ids)
        self.assertEqual(result_ids[0], "uploaded-product")

    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.4, 0.5]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_certificate_asset_recall_prefers_full_page_over_mineru_crop(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        assets = [
            {
                "id": "crop",
                "title": "质量管理体系认证证书",
                "similarity": 0.91,
                "asset_type": "qualification_image",
                "mime_type": "image/jpeg",
                "source_type": "taichang_mvp_mineru_asset",
                "width": 240,
                "height": 220,
                "searchable_text": "质量管理体系认证证书 局部印章",
                "specs": {"bbox": [1, 2, 3, 4]},
                "metadata": {
                    "evidence_type": "certification",
                    "target_library": "qualification_library",
                },
            },
            {
                "id": "full-page",
                "title": "泰昌1.质量管理体系认证证书第1页",
                "similarity": 0.74,
                "asset_type": "qualification_image",
                "mime_type": "image/jpeg",
                "source_type": "customer_pdf_full_page_render",
                "width": 1191,
                "height": 1685,
                "searchable_text": "质量管理体系认证证书 客户原始资料",
                "metadata": {
                    "evidence_type": "certification",
                    "target_library": "qualification_library",
                    "asset_visual_type": "full_page_render",
                },
            },
        ]
        rerank_mock.return_value = assets
        client = _RpcClient(rpc_rows=assets, asset_rows=[])

        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_assets("泰昌有哪些资质证书？", match_count=2)

        self.assertEqual(result[0]["id"], "full-page")

    @patch("backend.rag.retrieval.rerank_documents")
    @patch("backend.rag.retrieval.get_embeddings", return_value=[[0.4, 0.5]])
    @patch("backend.rag.retrieval.init_ali_client", return_value=object())
    def test_asset_recall_supplements_multi_evidence_query(self, _ali, _embeddings, rerank_mock):
        from backend.rag import retrieval

        strong_assets = [
            {
                "id": "contract-1",
                "title": "泰昌TJ20220002363合同协议书第1页",
                "similarity": 0.82,
                "searchable_text": "合同协议书 项目业绩",
                "metadata": {"enterprise": "泰昌", "source_domain": "enterprise_fact", "reference_only": False},
            },
            {
                "id": "contract-2",
                "title": "泰昌TJ20220002363合同协议书第3页",
                "similarity": 0.78,
                "searchable_text": "合同协议书 供货合同",
                "metadata": {"enterprise": "泰昌", "source_domain": "enterprise_fact", "reference_only": False},
            },
            {
                "id": "contract-3",
                "title": "泰昌TJ20220002363合同协议书第14页",
                "similarity": 0.72,
                "searchable_text": "合同协议书 签章页",
                "metadata": {"enterprise": "泰昌", "source_domain": "enterprise_fact", "reference_only": False},
            },
        ]

        def fake_rerank(_query, rows, **_kwargs):
            return strong_assets if rows == strong_assets else rows

        rerank_mock.side_effect = fake_rerank
        client = _RpcClient(
            rpc_rows=strong_assets,
            asset_rows=[
                *strong_assets,
                {
                    "id": "award-1",
                    "title": "泰昌电缆保护管中标通知书第1页",
                    "asset_type": "qualification_image",
                    "mime_type": "image/jpeg",
                    "similarity": 0.0,
                    "searchable_text": "中标通知书 招标编号 0322AB 包号 157-保护管",
                    "tags": ["项目业绩", "中标通知书"],
                    "metadata": {"enterprise": "泰昌", "source_domain": "enterprise_fact", "reference_only": False},
                },
            ],
        )

        with patch("backend.rag.retrieval.get_supabase_client", return_value=client):
            result = retrieval.search_knowledge_assets(
                "泰昌补充资料里有没有同类产品供货合同或中标通知书？",
                match_count=8,
                metadata_filter={"enterprise": "泰昌", "source_domain": "enterprise_fact", "reference_only": False},
            )

        self.assertIn("award-1", [asset["id"] for asset in result])
        self.assertIn("contract-1", [asset["id"] for asset in result])

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
        self.assertNotIn("/api/knowledge/assets/asset-1/file", prompt)
        self.assertIn("必须逐项核对并分别回答", prompt)
        self.assertEqual(images[-1]["url"], "/api/knowledge/assets/asset-1/file")

    def test_knowledge_prompt_does_not_mark_original_enterprise_asset_as_redacted(self):
        from backend.rag.retrieval import build_knowledge_prompt

        prompt, _ = build_knowledge_prompt(
            "泰昌有哪些企业证明材料？",
            contexts=[],
            assets=[{
                "id": "license-1",
                "title": "taichang_business_license_private",
                "category": "business_license",
                "description": "来源路径 parsed_outputs/customer/license.jpg",
                "metadata": {
                    "source_display_name": "泰昌营业执照副本原图",
                    "evidence_type": "business_license",
                    "target_library": "qualification_library",
                    "anonymized": False,
                },
            }],
        )

        self.assertIn("泰昌营业执照副本原图", prompt)
        self.assertIn("资料属性：客户原始资料", prompt)
        self.assertNotIn("parsed_outputs", prompt)
        self.assertNotIn("taichang_business_license_private", prompt)

    def test_enterprise_evidence_prompt_uses_broad_business_scope(self):
        from backend.rag.retrieval import build_knowledge_prompt

        prompt, _ = build_knowledge_prompt(
            "泰昌有哪些企业证明材料？",
            contexts=[],
            assets=[],
        )

        self.assertIn("广义企业事实集合", prompt)
        self.assertIn("基础证照", prompt)
        self.assertIn("正式体系认证", prompt)
        self.assertIn("人员与社保证明", prompt)
        self.assertIn("不能把回答缩窄为“企业现场照片”", prompt)

    def test_certification_prompt_does_not_expand_to_missing_license_claims(self):
        from backend.rag.retrieval import build_knowledge_prompt

        prompt, _ = build_knowledge_prompt(
            "泰昌有哪些资质证书？",
            contexts=[],
            assets=[],
        )

        self.assertIn("只回答已命中的资质证书和体系认证", prompt)
        self.assertIn("不要输出“需要确认或补充”小节", prompt)
        self.assertIn("不得主动扩展到营业执照", prompt)
        self.assertIn("不能把“存在/已命中证书资料”表述为“有效/合格有效/在有效期内”", prompt)

    def test_inspection_report_prompt_binds_coverage_to_specification(self):
        from backend.rag.retrieval import build_knowledge_prompt

        prompt, _ = build_knowledge_prompt(
            "泰昌 CPVC 电缆保护管有哪些检验报告？",
            contexts=[],
            assets=[],
        )

        self.assertIn("覆盖范围必须绑定到产品族、规格型号、报告编号", prompt)
        self.assertIn("不得写“已覆盖全部 CPVC 规格”", prompt)
        self.assertIn("需补充对应规格报告或由客户确认", prompt)

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

    def test_pilot_enterprise_contexts_prioritize_formal_certificates(self):
        from backend.api.knowledge import _curate_pilot_enterprise_contexts

        common = {
            "enterprise": "泰昌",
            "source_domain": "enterprise_fact",
            "fact_source_allowed_for_enterprise": True,
            "reference_only": False,
        }
        contexts = [
            {"id": "esg", "content": "ESG报告提到质量管理", "similarity": 0.95, "metadata": {**common, "source_display_name": "ESG环境社会公司治理报告"}},
            {"id": "quality", "content": "质量管理体系认证证书", "similarity": 0.65, "metadata": {**common, "source_display_name": "质量管理体系认证证书", "evidence_type": "certification"}},
            {"id": "environment", "content": "环境管理体系认证证书", "similarity": 0.64, "metadata": {**common, "source_display_name": "环境管理体系认证证书", "evidence_type": "certification"}},
            {"id": "ohs", "content": "职业健康安全管理体系认证证书", "similarity": 0.63, "metadata": {**common, "source_display_name": "职业健康安全管理体系认证证书", "evidence_type": "certification"}},
        ]

        result = _curate_pilot_enterprise_contexts(
            contexts,
            limit=3,
            query="泰昌有哪些资质证书？",
        )

        self.assertEqual({item["id"] for item in result}, {"quality", "environment", "ohs"})

    def test_pilot_enterprise_contexts_do_not_fill_certificate_sources_with_green_reports(self):
        from backend.api.knowledge import _curate_pilot_enterprise_contexts

        common = {
            "enterprise": "泰昌",
            "source_domain": "enterprise_fact",
            "fact_source_allowed_for_enterprise": True,
            "reference_only": False,
        }
        contexts = [
            {
                "id": "quality",
                "content": "质量管理体系认证证书",
                "similarity": 0.7,
                "metadata": {**common, "source_display_name": "质量管理体系认证证书", "evidence_type": "certification"},
            },
            {
                "id": "esg",
                "content": "ESG环境社会公司治理报告提到质量和环保管理",
                "similarity": 0.99,
                "metadata": {**common, "source_display_name": "ESG环境社会公司治理报告", "evidence_type": "green_low_carbon"},
            },
            {
                "id": "waste",
                "content": "废水废气废固检测报告",
                "similarity": 0.98,
                "metadata": {**common, "source_display_name": "废水废气废固检测报告", "evidence_type": "green_low_carbon"},
            },
            {
                "id": "green-mislabeled",
                "content": "绿色发展规划报告 附件提到认证证书",
                "similarity": 0.97,
                "metadata": {**common, "source_display_name": "绿色发展规划报告", "evidence_type": "certification"},
            },
        ]

        result = _curate_pilot_enterprise_contexts(
            contexts,
            limit=5,
            query="泰昌有哪些资质证书？",
        )

        self.assertEqual([item["id"] for item in result], ["quality"])

    def test_pilot_enterprise_contexts_return_empty_when_certificate_query_only_hits_green_reports(self):
        from backend.api.knowledge import _curate_pilot_enterprise_contexts

        common = {
            "enterprise": "泰昌",
            "source_domain": "enterprise_fact",
            "fact_source_allowed_for_enterprise": True,
            "reference_only": False,
        }
        contexts = [
            {
                "id": "esg-mislabeled",
                "content": "ESG环境社会公司治理报告 附件提到认证证书",
                "similarity": 0.99,
                "metadata": {**common, "source_display_name": "ESG环境社会公司治理报告", "evidence_type": "certification"},
            },
            {
                "id": "waste-mislabeled",
                "content": "废水废气废固检测报告 认证证书材料归档",
                "similarity": 0.98,
                "metadata": {**common, "source_display_name": "废水废气废固检测报告", "evidence_type": "certification"},
            },
        ]

        result = _curate_pilot_enterprise_contexts(
            contexts,
            limit=5,
            query="泰昌有哪些资质证书？",
        )

        self.assertEqual(result, [])

    def test_formal_certification_asset_filter_rejects_mislabeled_green_assets(self):
        from backend.api.knowledge import _is_formal_certification_asset

        self.assertTrue(
            _is_formal_certification_asset(
                {
                    "title": "泰昌质量管理体系认证证书第1页",
                    "description": "质量管理体系认证证书",
                    "metadata": {"enterprise": "泰昌", "source_domain": "enterprise_fact", "evidence_type": "certification"},
                }
            )
        )
        self.assertFalse(
            _is_formal_certification_asset(
                {
                    "title": "泰昌绿色发展规划报告第1页",
                    "description": "绿色发展规划报告 附件提到认证证书",
                    "metadata": {"enterprise": "泰昌", "source_domain": "enterprise_fact", "evidence_type": "certification"},
                }
            )
        )

    def test_pilot_enterprise_contexts_scope_production_query_away_from_green_reports(self):
        from backend.api.knowledge import _curate_pilot_enterprise_contexts

        common = {
            "enterprise": "泰昌",
            "source_domain": "enterprise_fact",
            "fact_source_allowed_for_enterprise": True,
            "reference_only": False,
        }
        contexts = [
            {
                "id": "esg",
                "content": "ESG环境社会公司治理报告中提到生产节能。",
                "similarity": 0.99,
                "metadata": {**common, "source_display_name": "ESG环境社会公司治理报告", "evidence_type": "green_low_carbon"},
            },
            {
                "id": "factory",
                "content": "泰昌厂房、车间和生产线资料。",
                "similarity": 0.7,
                "metadata": {**common, "source_display_name": "厂房图片", "evidence_type": "production_capacity"},
            },
            {
                "id": "mpp-line",
                "content": "MPP生产线设备照片。",
                "similarity": 0.68,
                "metadata": {**common, "source_display_name": "MPP生产线", "evidence_type": "production_capacity"},
            },
        ]

        result = _curate_pilot_enterprise_contexts(
            contexts,
            limit=5,
            query="泰昌有哪些生产制造能力资料？",
        )

        self.assertEqual([item["id"] for item in result], ["factory", "mpp-line"])

    def test_pilot_enterprise_contexts_scope_personnel_query_away_from_certificates(self):
        from backend.api.knowledge import _curate_pilot_enterprise_contexts

        common = {
            "enterprise": "泰昌",
            "source_domain": "enterprise_fact",
            "fact_source_allowed_for_enterprise": True,
            "reference_only": False,
        }
        contexts = [
            {
                "id": "ohs",
                "content": "职业健康安全管理体系认证证书。",
                "similarity": 0.95,
                "metadata": {**common, "source_display_name": "职业健康安全管理体系认证证书", "evidence_type": "certification"},
            },
            {
                "id": "social-security",
                "content": "泰昌社保证明、参保证明。",
                "similarity": 0.7,
                "metadata": {**common, "source_display_name": "泰昌社保证明（第1页）", "evidence_type": "personnel_certificate"},
            },
            {
                "id": "roster",
                "content": "泰昌公司人员花名册。",
                "similarity": 0.68,
                "metadata": {**common, "source_display_name": "泰昌公司人员花名册", "evidence_type": "personnel_certificate"},
            },
        ]

        result = _curate_pilot_enterprise_contexts(
            contexts,
            limit=5,
            query="泰昌有哪些人员证书或社保证明？",
        )

        self.assertEqual([item["id"] for item in result], ["social-security", "roster"])

    def test_pilot_enterprise_contexts_scope_green_query_keeps_green_sources(self):
        from backend.api.knowledge import _curate_pilot_enterprise_contexts

        common = {
            "enterprise": "泰昌",
            "source_domain": "enterprise_fact",
            "fact_source_allowed_for_enterprise": True,
            "reference_only": False,
        }
        contexts = [
            {
                "id": "quality",
                "content": "质量管理体系认证证书。",
                "similarity": 0.99,
                "metadata": {**common, "source_display_name": "质量管理体系认证证书", "evidence_type": "certification"},
            },
            {
                "id": "green-plan",
                "content": "绿色发展规划报告。",
                "similarity": 0.7,
                "metadata": {**common, "source_display_name": "绿色发展规划报告", "evidence_type": "green_low_carbon"},
            },
            {
                "id": "green-chain",
                "content": "绿色供应链认证证书。",
                "similarity": 0.68,
                "metadata": {**common, "source_display_name": "绿色供应链认证证书", "evidence_type": "certification"},
            },
        ]

        result = _curate_pilot_enterprise_contexts(
            contexts,
            limit=5,
            query="泰昌有哪些绿色低碳资料？",
        )

        self.assertEqual([item["id"] for item in result], ["green-plan", "green-chain"])

    def test_asset_query_scope_filters_production_assets_away_from_green_assets(self):
        from backend.api.knowledge import _filter_assets_for_query_scope

        assets = [
            {
                "id": "green",
                "title": "泰昌ESG环境社会公司治理报告第7页",
                "description": "ESG环境社会公司治理报告",
                "metadata": {"enterprise": "泰昌", "source_domain": "enterprise_fact", "evidence_type": "green_low_carbon"},
            },
            {
                "id": "factory",
                "title": "厂房图片",
                "description": "生产制造能力资料",
                "metadata": {"enterprise": "泰昌", "source_domain": "enterprise_fact", "evidence_type": "production_capacity"},
            },
        ]

        result = _filter_assets_for_query_scope(assets, "泰昌有哪些生产制造能力资料？")

        self.assertEqual([asset["id"] for asset in result], ["factory"])


if __name__ == "__main__":
    unittest.main()

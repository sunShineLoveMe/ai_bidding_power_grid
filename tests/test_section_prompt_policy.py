from unittest.mock import patch


def _payload():
    return {
        "project": {"project_name": "测试项目", "project_no": "TEST-001"},
        "analysis": {"summary": "电缆保护管采购", "project_meta": {}},
    }


def _fact_pack():
    return {
        "enterprise": {
            "unified_social_credit_code": "91130607056539515C",
            "legal_representative": "李某",
        },
        "product_inspection": {
            "CPVC电缆保护管": {
                "report_no": "2024100312005501713",
                "specification_model": "DS 250x15x6000 SN16 PVC-C",
                "parameters": [
                    {"parameter": "平均内径", "inspection_result": "250.2~250.4", "unit": "mm"},
                    {"parameter": "壁厚", "inspection_result": "15.2~15.3", "unit": "mm"},
                ],
            }
        },
        "certifications": [
            {"name": "质量管理体系认证证书", "certificate_no": "CERT-001", "valid_until": "2027-01-01"}
        ],
    }


def test_prompt_policy_classifies_core_profiles():
    from backend.ai.section_prompt_policy import classify_section_prompt_profile

    assert classify_section_prompt_profile({"title": "23.2.1 编制依据"}).name == "simple_plan"
    assert classify_section_prompt_profile({"title": "CPVC 技术参数响应表"}).name == "technical_parameter"
    assert classify_section_prompt_profile({"title": "商务偏差表"}).name == "structured_table"
    assert classify_section_prompt_profile({"title": "附件清单及页码索引"}).name == "attachment_index"
    assert classify_section_prompt_profile({"title": "投标报价说明"}).name == "price_sensitive"
    assert classify_section_prompt_profile({"title": "企业资质证书"}).name == "fact_grounded"
    assert classify_section_prompt_profile({"title": "任意章节"}, continuation=True).name == "continuation_slim"


def test_simple_prompt_uses_slim_rag_budget_and_enforces_chars():
    from backend.ai.section_writer import build_section_prompt

    chapter = {
        "id": "section-1",
        "title": "编制依据",
        "purpose": "说明本投标文件编制依据",
        "mapped_requirements": [f"要求{i}" for i in range(30)],
        "mapped_scoring_items": [f"评分{i}" for i in range(20)],
        "metadata": {"volume_type": "technical", "writing_plan": {"target_words": 1200}},
    }
    rag_rows = [
        {
            "content": "国网物资投标文件应依据招标文件、技术规范书和合同条款编制。",
            "source_section": "编制依据",
            "metadata": {"source_file": "招标文件.md", "doc_role": "main_tender_file"},
        }
    ]

    with (
        patch("backend.ai.section_writer.get_project_interpretation", return_value=_payload()),
        patch("backend.ai.section_writer.list_knowledge_assets", return_value=[]),
        patch("backend.ai.section_writer.load_taichang_verified_fact_pack", return_value=_fact_pack()),
        patch("backend.rag.retrieval.search_knowledge_base", return_value=rag_rows) as search_mock,
    ):
        prompt = build_section_prompt("project-id", chapter)

    assert "Prompt profile：轻量方案（simple_plan）" in prompt
    assert "输入预算：prompt≤5000 字符；RAG 1 条；企业资料 1 条" in prompt
    assert len(prompt) <= 5000
    assert "要求5" not in prompt
    assert search_mock.call_args.kwargs["match_count"] == 1


def test_technical_parameter_prompt_keeps_report_number_and_parameter_facts():
    from backend.ai.section_writer import build_section_prompt

    chapter = {
        "id": "section-2",
        "title": "CPVC 电缆保护管技术参数响应表",
        "purpose": "响应技术参数和检验报告要求",
        "metadata": {"volume_type": "technical", "writing_plan": {"target_words": 1800}},
    }

    with (
        patch("backend.ai.section_writer.get_project_interpretation", return_value=_payload()),
        patch("backend.ai.section_writer.list_knowledge_assets", return_value=[]),
        patch("backend.ai.section_writer.load_taichang_verified_fact_pack", return_value=_fact_pack()),
        patch("backend.rag.retrieval.search_knowledge_base", return_value=[]),
    ):
        prompt = build_section_prompt("project-id", chapter)

    assert "Prompt profile：技术参数（technical_parameter）" in prompt
    assert "2024100312005501713" in prompt
    assert "平均内径 250.2~250.4mm" in prompt


def test_continuation_prompt_skips_rag_and_assets():
    from backend.ai.section_writer import build_section_continuation_prompt

    chapter = {
        "id": "section-3",
        "title": "生产制造能力",
        "metadata": {"volume_type": "technical", "writing_plan": {"target_words": 2200}},
    }

    with (
        patch("backend.ai.section_writer.get_project_interpretation", return_value=_payload()),
        patch("backend.ai.section_writer.list_knowledge_assets") as assets_mock,
        patch("backend.ai.section_writer.load_taichang_verified_fact_pack", return_value=_fact_pack()),
        patch("backend.rag.retrieval.search_knowledge_base") as search_mock,
    ):
        prompt = build_section_continuation_prompt("project-id", chapter, "## 生产制造能力\n\n已有草稿")

    assert "Prompt profile：草稿续写（continuation_slim" in prompt
    assert "不加载章节级 RAG" in prompt
    assert len(prompt) <= 4500
    assets_mock.assert_not_called()
    search_mock.assert_not_called()


def test_stream_start_event_exposes_prompt_profile_metadata():
    from backend.ai import section_writer

    chapter = {
        "id": "section-4",
        "title": "附件清单及页码索引",
        "metadata": {"volume_type": "attachment", "writing_plan": {"target_words": 300}},
    }
    with (
        patch("backend.ai.section_writer.get_project_interpretation", return_value=_payload()),
        patch("backend.ai.section_writer.list_knowledge_assets", return_value=[]),
        patch("backend.ai.section_writer.load_taichang_verified_fact_pack", return_value=_fact_pack()),
        patch("backend.rag.retrieval.search_knowledge_base", return_value=[]),
        patch("backend.ai.section_writer.stream_dashscope_api", return_value=iter(["索引内容"])),
        patch("backend.ai.section_writer.get_stage_model", return_value="test-model"),
        patch("backend.ai.section_writer._needs_length_supplement", return_value=False),
    ):
        events = list(section_writer.stream_bid_section("project-id", chapter))

    assert events[0]["type"] == "start"
    assert events[0]["prompt_profile"] == "attachment_index"
    assert events[0]["prompt_chars"] <= events[0]["max_prompt_chars"]

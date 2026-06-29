import unittest
import json
from unittest.mock import patch

from backend.ai.chapter_planner import (
    _build_prompt,
    _build_rule_outline,
    _build_split_child,
    _generate_outline_from_ai_or_rule,
    _outline_total_nodes,
    _refine_bid_outline_in_background,
    _reference_template_chapters_from_files,
    _supply_outline_reject_reason,
    stream_bid_outline,
)
from backend.db.supabase_repo import replace_bid_sections_from_outline


class ChapterPlannerRegressionTest(unittest.TestCase):
    def test_supply_bid_uses_customer_reference_structure_without_construction_topics(self):
        payload = {
            "project": {"id": "project-1", "project_name": "电缆保护管采购"},
            "analysis": {"summary": "CPVC、MPP电缆保护管物资采购", "project_meta": {}},
            "requirements": [{"content": "提交技术偏差表和技术特性参数表"}],
            "scoringItems": [],
            "risks": [],
        }

        outline = _build_rule_outline(payload)
        titles = [str(item.get("title") or "") for item in outline.get("chapters") or []]
        prompt = _build_prompt(payload)

        self.assertTrue(any("技术特性参数表" in title for title in titles))
        self.assertTrue(any("商务偏差表" in title for title in titles))
        self.assertFalse(any("施工组织设计" in title for title in titles))
        self.assertIn("河北豪乾同类标书仅作目录、格式和写法参考", prompt)
        self.assertIn("禁止生成施工组织设计", prompt)
        self.assertIn("河北泰昌电力器材科技有限公司", prompt)

    def test_supply_bid_prefers_parsed_customer_reference_template_outline(self):
        payload = {
            "project": {"id": "project-1", "project_name": "电缆保护管采购"},
            "analysis": {"summary": "CPVC、MPP电缆保护管物资采购", "project_meta": {}},
            "requirements": [{"content": "提交技术偏差表、商务偏差表和投标文件格式"}],
            "scoringItems": [],
            "risks": [],
        }

        outline = _build_rule_outline(payload)
        titles = [str(item.get("title") or "") for item in outline.get("chapters") or []]

        self.assertGreater(len(titles), 60)
        self.assertIn("商务响应文件", titles)
        self.assertIn("技术响应文件", titles)
        self.assertTrue(any("绿色低碳" in title for title in titles))
        self.assertTrue(any("售后服务" in title for title in titles))
        self.assertFalse(any("陕西云天创石化有限公司" in title for title in titles))
        self.assertFalse(any("电气施工用电线保护管道连接装置" in title for title in titles))
        self.assertFalse(any("施工组织设计" in title for title in titles))
        self.assertFalse(any("施工部署" in title for title in titles))
        self.assertIsNone(_supply_outline_reject_reason(outline))
        self.assertLessEqual(max(int(item.get("level") or 1) for item in outline.get("chapters") or []), 4)

    def test_supply_bid_uses_guarded_reference_outline_rules(self):
        payload = {
            "project": {"id": "project-1", "project_name": "电缆保护管采购"},
            "analysis": {"summary": "CPVC、MPP电缆保护管物资采购", "project_meta": {}},
            "requirements": [{"content": "提交技术偏差表、商务偏差表、技术特性参数表"}],
            "scoringItems": [],
            "risks": [],
        }

        outline = _build_rule_outline(payload)
        prompt = _build_prompt(payload)
        integration = outline.get("reference_outline_rules_integration") or {}
        annotated = [
            chapter for chapter in outline.get("chapters") or []
            if (chapter.get("metadata") or {}).get("reference_outline_rule_id")
        ]

        self.assertEqual("guarded_planner_hint", integration.get("mode"))
        self.assertGreaterEqual(integration.get("section_count"), 10)
        self.assertIn("结构化参考模板规则 reference_outline_rules", prompt)
        self.assertIn("不得覆盖招标文件、客户确认章节或供货类门禁", prompt)
        self.assertTrue(any((item.get("metadata") or {}).get("reference_outline_rule_id") == "technical_parameter_table" for item in annotated))
        self.assertTrue(any((item.get("metadata") or {}).get("reference_outline_rule_id") == "business_deviation_table" for item in annotated))
        self.assertLessEqual(_outline_total_nodes(outline), 140)
        self.assertIsNone(_supply_outline_reject_reason(outline))

    def test_overhead_insulated_conductor_bid_is_supply_only(self):
        payload = {
            "project": {"id": "project-1", "project_name": "10kV架空绝缘导线采购"},
            "analysis": {"summary": "国家电网10kV架空绝缘导线协议库存物资采购", "project_meta": {}},
            "requirements": [{"content": "提交技术偏差表、技术特性参数表和货物清单"}],
            "scoringItems": [],
            "risks": [],
        }

        outline = _build_rule_outline(payload)
        prompt = _build_prompt(payload)
        titles = [str(item.get("title") or "") for item in outline.get("chapters") or []]

        self.assertTrue(outline.get("preserve_reference_structure"))
        self.assertIn("结构化参考模板规则 reference_outline_rules", prompt)
        self.assertFalse(any("施工组织设计" in title or "施工部署" in title for title in titles))
        self.assertIsNone(_supply_outline_reject_reason(outline))

    def test_supply_ai_outline_over_cap_falls_back_to_reference_outline(self):
        payload = {
            "project": {"id": "project-1", "project_name": "电缆保护管采购"},
            "analysis": {"summary": "CPVC、MPP电缆保护管物资采购", "project_meta": {}},
            "requirements": [{"content": "提交技术偏差表、商务偏差表和投标文件格式"}],
            "scoringItems": [],
            "risks": [],
        }
        oversized_outline = {
            "version": "ai-volume-v1",
            "volumes": [
                {
                    "type": "technical",
                    "name": "技术标",
                    "chapters": [
                        {"title": f"技术响应章节 {index}", "purpose": "响应技术要求"}
                        for index in range(160)
                    ],
                }
            ],
            "chapters": [],
        }

        with (
            patch("backend.ai.chapter_planner._fetch_knowledge_context", return_value={
                "rag_snippets": [],
                "assets_summary": [],
                "has_qualification_assets": False,
                "has_product_assets": False,
                "has_case_assets": False,
                "qualification_titles": [],
                "product_titles": [],
            }),
            patch("backend.ai.chapter_planner.call_dashscope_api", return_value={
                "model": "test-model",
                "output": {"choices": [{"message": {"content": json.dumps(oversized_outline, ensure_ascii=False)}}]},
            }),
        ):
            outline = _generate_outline_from_ai_or_rule(payload)

        self.assertEqual("rule-v1-supply-guardrail", outline["version"])
        self.assertTrue(outline["preserve_reference_structure"])
        self.assertLessEqual(len(outline.get("chapters") or []), 140)
        self.assertIn("超过上限", outline["fallback_reason"])

    def test_supply_background_refinement_rejects_outline_growth(self):
        payload = {
            "project": {"id": "project-1", "project_name": "电缆保护管采购"},
            "analysis": {"summary": "CPVC、MPP电缆保护管物资采购", "project_meta": {}},
        }
        quick_chapters = [{"order": str(index), "title": f"快速章节 {index}", "level": 1} for index in range(1, 21)]
        analysis = {"project_meta": {"bid_outline": {"chapters": quick_chapters}}}
        ai_outline = {
            "chapters": [{"order": str(index), "title": f"精修章节 {index}", "level": 1} for index in range(1, 81)]
        }

        with (
            patch("backend.ai.chapter_planner._generate_outline_from_ai_or_rule", return_value=ai_outline),
            patch("backend.ai.chapter_planner.save_bid_outline") as save_mock,
            patch("backend.ai.chapter_planner.replace_bid_sections_from_outline") as replace_mock,
        ):
            _refine_bid_outline_in_background("project-1", payload, analysis)

        save_mock.assert_not_called()
        replace_mock.assert_not_called()

    def test_reference_template_parser_returns_expanded_structure(self):
        chapters = _reference_template_chapters_from_files()
        flattened: list[str] = []

        def visit(node):
            flattened.append(str(node.get("title") or ""))
            for child in node.get("children") or []:
                visit(child)

        for chapter in chapters:
            visit(chapter)

        self.assertGreater(len(flattened), 60)
        self.assertIn("商务响应文件", flattened)
        self.assertIn("技术响应文件", flattened)
        self.assertIn("报价文件及货物清单", flattened)

    def test_split_child_title_does_not_repeat_parent_prefix(self):
        child = _build_split_child(
            {
                "title": "企业基本资格资料",
                "order": "2.1",
                "level": 2,
                "metadata": {},
            },
            1,
            3,
            ("响应要求", "概述资格条件响应关系。"),
        )

        self.assertEqual("响应要求", child["title"])
        self.assertEqual("企业基本资格资料", child["metadata"]["split_from_parent_title"])

    def test_rule_outline_tolerates_string_material_checklist_items(self):
        payload = {
            "project": {"id": "project-1", "project_name": "测试项目"},
            "analysis": {
                "project_meta": {
                    "project_name": "测试项目",
                    "ai_report": {
                        "material_checklist": [
                            "营业执照",
                            "安全生产许可证",
                            {"material": "类似项目业绩证明", "category": "资格资料"},
                        ],
                    },
                }
            },
            "requirements": [
                {"content": "投标文件应提供营业执照和安全生产许可证", "source_section": "资格审查", "source_page": 8},
                "非结构化脏数据应被忽略",
            ],
            "scoringItems": ["非结构化评分项应被忽略"],
            "risks": ["非结构化风险项应被忽略"],
        }

        outline = _build_rule_outline(payload)
        chapters = outline.get("chapters") or []

        self.assertGreater(len(chapters), 0)
        self.assertTrue(any("资格" in chapter.get("title", "") for chapter in chapters))
        self.assertTrue(
            any("类似项目业绩证明" in material for chapter in chapters for material in chapter.get("required_materials") or [])
        )

    def test_replace_outline_writes_sections_in_one_locked_batch_with_generated_parent_ids(self):
        calls: list[tuple[str, str, list[dict] | None]] = []

        class FakeResponse:
            def __init__(self, data):
                self.data = data

        class FakeQuery:
            def __init__(self, table: str, action: str, rows: list[dict] | None = None):
                self.table = table
                self.action = action
                self.rows = rows

            def eq(self, *_args):
                return self

            def execute(self):
                calls.append((self.table, self.action, self.rows))
                if self.action == "insert":
                    return FakeResponse(self.rows)
                return FakeResponse([])

        class FakeTable:
            def __init__(self, name: str):
                self.name = name

            def delete(self):
                return FakeQuery(self.name, "delete")

            def insert(self, rows):
                return FakeQuery(self.name, "insert", rows)

        class FakeClient:
            def table(self, name: str):
                return FakeTable(name)

        outline = {
            "chapters": [
                {"order": "1", "title": "施工组织设计", "level": 1},
                {"order": "1.1", "title": "施工方案", "level": 2},
                {"order": "2", "title": "商务响应", "level": 1},
            ]
        }

        with patch("backend.db.supabase_repo.get_supabase_client", return_value=FakeClient()):
            rows = replace_bid_sections_from_outline(
                "1651fd88-11de-4df9-8cbc-53ecb5eb30fd",
                outline,
                respect_lock=False,
                reuse_existing_ids=False,
            )

        insert_calls = [call for call in calls if call[1] == "insert"]
        self.assertEqual(1, len(insert_calls))
        self.assertEqual(3, len(rows))
        root_id = rows[0]["id"]
        self.assertEqual(root_id, rows[1]["parent_id"])
        self.assertEqual([1, 2, 3], [row["order_index"] for row in rows])

    def test_replace_outline_keeps_unique_ids_when_llm_repeats_order(self):
        class FakeResponse:
            def __init__(self, data):
                self.data = data

        class FakeQuery:
            def __init__(self, rows: list[dict] | None = None):
                self.rows = rows

            def eq(self, *_args):
                return self

            def execute(self):
                return FakeResponse(self.rows or [])

        class FakeTable:
            def delete(self):
                return FakeQuery()

            def insert(self, rows):
                return FakeQuery(rows)

        class FakeClient:
            def table(self, _name: str):
                return FakeTable()

        outline = {
            "chapters": [
                {"order": "1", "title": "第一章", "level": 1},
                {"order": "1", "title": "重复第一章", "level": 1},
                {"order": "1.1", "title": "子章", "level": 2},
            ]
        }

        with patch("backend.db.supabase_repo.get_supabase_client", return_value=FakeClient()):
            rows = replace_bid_sections_from_outline(
                "1651fd88-11de-4df9-8cbc-53ecb5eb30fd",
                outline,
                respect_lock=False,
                reuse_existing_ids=False,
            )

        self.assertEqual(3, len({row["id"] for row in rows}))
        self.assertEqual(rows[0]["id"], rows[2]["parent_id"])

    def test_stream_outline_dispatches_refinement_to_celery(self):
        payload = {
            "project": {"id": "project-1", "project_name": "测试项目"},
            "analysis": {"project_meta": {"project_name": "测试项目"}},
            "requirements": [],
            "scoringItems": [],
            "risks": [],
        }
        quick_outline = {
            "chapters": [
                {"order": "1", "title": "技术标", "level": 1},
                {"order": "1.1", "title": "施工组织", "level": 2},
            ]
        }

        with (
            patch("backend.ai.chapter_planner.get_project_interpretation", return_value=payload),
            patch("backend.ai.chapter_planner._build_rule_outline", return_value=quick_outline),
            patch("backend.ai.chapter_planner.save_bid_outline"),
            patch("backend.ai.chapter_planner.replace_bid_sections_from_outline"),
            patch("backend.ai.chapter_planner.time.sleep"),
            patch("backend.tasks.outline_tasks.refine_bid_outline.delay") as delay_mock,
        ):
            events = list(stream_bid_outline("project-1"))

        self.assertTrue(any(event.get("type") == "done" for event in events))
        delay_mock.assert_called_once()
        args = delay_mock.call_args.args
        self.assertEqual("project-1", args[0])
        self.assertEqual(quick_outline, args[2]["project_meta"]["bid_outline"])


class OutlineLockRegressionTest(unittest.TestCase):
    def test_replace_outline_skipped_when_locked(self):
        """大纲锁定时，replace 不得执行删建，直接返回现有章节。"""
        existing = [{"id": "11111111-1111-4111-8111-111111111111", "title": "已固定章节", "order_index": 1}]

        with (
            patch("backend.db.supabase_repo.get_outline_lock", return_value=True),
            patch("backend.db.supabase_repo.list_bid_sections", return_value=existing) as list_mock,
            patch("backend.db.supabase_repo.get_supabase_client") as client_mock,
        ):
            rows = replace_bid_sections_from_outline(
                "1651fd88-11de-4df9-8cbc-53ecb5eb30fd",
                {"chapters": [{"order": "1", "title": "新章节", "level": 1}]},
            )

        self.assertEqual(existing, rows)
        list_mock.assert_called()
        # 锁定时不应触碰数据库写入
        client_mock.assert_not_called()

    def test_replace_outline_reuses_existing_ids_by_title(self):
        """AI 精修复用既有章节 ID（按 title 匹配），避免 ID 漂移。"""
        fixed_id = "aaaaaaaa-1111-4111-8111-111111111111"
        existing = [
            {"id": fixed_id, "title": "施工组织设计", "level": 1, "order_index": 1},
        ]
        inserted_holder: dict[str, list] = {}

        class FakeResponse:
            def __init__(self, data):
                self.data = data

        class FakeQuery:
            def __init__(self, rows=None):
                self.rows = rows

            def eq(self, *_a):
                return self

            def execute(self):
                return FakeResponse(self.rows or [])

        class FakeTable:
            def delete(self):
                return FakeQuery()

            def insert(self, rows):
                inserted_holder["rows"] = rows
                return FakeQuery(rows)

        class FakeClient:
            def table(self, _name):
                return FakeTable()

        outline = {"chapters": [{"order": "1", "title": "施工组织设计", "level": 1}]}

        with (
            patch("backend.db.supabase_repo.get_outline_lock", return_value=False),
            patch("backend.db.supabase_repo.list_bid_sections", return_value=existing),
            patch("backend.db.supabase_repo.get_supabase_client", return_value=FakeClient()),
        ):
            rows = replace_bid_sections_from_outline(
                "1651fd88-11de-4df9-8cbc-53ecb5eb30fd",
                outline,
            )

        # 复用既有 ID，而非生成新 UUID
        self.assertEqual(fixed_id, rows[0]["id"])


if __name__ == "__main__":
    unittest.main()

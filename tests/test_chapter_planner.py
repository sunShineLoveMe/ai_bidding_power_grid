import unittest
from unittest.mock import patch

from backend.ai.chapter_planner import _build_rule_outline
from backend.db.supabase_repo import replace_bid_sections_from_outline


class ChapterPlannerRegressionTest(unittest.TestCase):
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
            rows = replace_bid_sections_from_outline("1651fd88-11de-4df9-8cbc-53ecb5eb30fd", outline)

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
            rows = replace_bid_sections_from_outline("1651fd88-11de-4df9-8cbc-53ecb5eb30fd", outline)

        self.assertEqual(3, len({row["id"] for row in rows}))
        self.assertEqual(rows[0]["id"], rows[2]["parent_id"])


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

from scripts.rag.govern_bid_container_content import (
    build_governance_plan,
    build_governance_payload,
    classify_container_content,
    is_container_section,
)


class BidContainerContentGovernanceTest(unittest.TestCase):
    def test_classifies_internal_guidance_content(self):
        classification, hits = classify_container_content(
            "参考客户同类标书目录组织本节。\n\n### 编写要点\n需准备资料和风险与复核。"
        )

        self.assertEqual(classification, "internal_guidance")
        self.assertIn("编写要点", hits)
        self.assertIn("需准备资料", hits)

    def test_parent_id_marks_section_as_container(self):
        parent_ids = {"parent"}
        section = {"id": "parent", "metadata": {}}

        self.assertTrue(is_container_section(section, parent_ids))

    def test_governance_payload_clears_content_without_storing_full_text_in_metadata(self):
        section = {
            "id": "parent",
            "title": "商务响应文件",
            "content": "参考客户同类标书目录组织本节。\n\n### 编写要点\n内部提示不应进入正式正文。",
            "metadata": {"volume_type": "business"},
        }

        payload = build_governance_payload(
            section,
            run_id="run_test",
            timestamp="2026-06-29T00:00:00Z",
            classification="internal_guidance",
            guidance_hits=["编写要点"],
            backup_path=Path("docs/development/runs/run_test_container_content_backup.json"),
            clear_content=True,
        )

        metadata = payload["metadata"]
        serialized_metadata = str(metadata)
        self.assertEqual(payload["content"], "")
        self.assertEqual(metadata["section_role"], "container")
        self.assertFalse(metadata["leaf_generation"])
        self.assertEqual(metadata["container_content_policy"], "ignored_for_formal_export")
        self.assertEqual(metadata["container_content_governance"]["action"], "cleared_to_backup")
        self.assertIn("content_sha256", metadata["container_content_governance"])
        self.assertNotIn("内部提示不应进入正式正文", serialized_metadata)

    def test_build_governance_plan_only_updates_container_sections(self):
        sections = [
            {
                "id": "parent",
                "title": "商务响应文件",
                "content": "父级说明",
                "metadata": {},
            },
            {
                "id": "leaf",
                "parent_id": "parent",
                "title": "投标函",
                "content": "正式正文",
                "metadata": {},
            },
        ]

        containers, backups, updates = build_governance_plan(
            sections,
            run_id="run_test",
            timestamp="2026-06-29T00:00:00Z",
            backup_path=Path("docs/development/runs/run_test_container_content_backup.json"),
            clear_content=True,
        )

        self.assertEqual([item["id"] for item in containers], ["parent"])
        self.assertEqual([item["id"] for item in backups], ["parent"])
        self.assertEqual([item["id"] for item in updates], ["parent"])


if __name__ == "__main__":
    unittest.main()

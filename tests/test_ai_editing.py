import unittest
import os
from unittest.mock import patch


class AiEditingTest(unittest.TestCase):
    def test_edit_bid_section_text_calls_real_model_adapter_with_safety_context(self):
        from backend.services.ai_editing import edit_bid_section_text

        with (
            patch("backend.services.ai_editing.get_project_interpretation", return_value={
                "project": {"project_name": "国网辽宁电力2025年第三次物资协议库存招标采购"},
                "analysis": {"project_meta": {"tender_no": "2225AC"}},
            }),
            patch("backend.services.ai_editing.call_dashscope_api", return_value={
                "output": {"choices": [{"message": {"content": '{"revised_text":"我公司承诺按招标文件要求组织供货。","summary":"正式化承诺语气","warnings":[]}'}}]}
            }) as mocked_call,
        ):
            result = edit_bid_section_text("a1d853bc-ca4e-43b4-bbea-256f561c8a3d", {
                "action": "formalize",
                "sectionId": "section-1",
                "sectionTitle": "供货承诺",
                "sectionContext": "说明供货响应",
                "selectedText": "我们会按要求供货。",
                "fullContent": "我们会按要求供货。",
            })

        self.assertEqual("formalize", result["action"])
        self.assertEqual("正式化", result["actionLabel"])
        self.assertEqual("我公司承诺按招标文件要求组织供货。", result["revisedText"])
        _, kwargs = mocked_call.call_args
        self.assertTrue(kwargs["json_mode"])
        self.assertEqual("bid_ai_edit", kwargs["usage_context"]["stage"])
        prompt_text = "\n".join(message["content"] for message in mocked_call.call_args.args[0])
        self.assertIn("不得编造企业资质", prompt_text)
        self.assertIn("供货承诺", prompt_text)

    def test_edit_bid_section_text_rejects_missing_selection(self):
        from backend.services.ai_editing import edit_bid_section_text

        with self.assertRaises(ValueError):
            edit_bid_section_text("a1d853bc-ca4e-43b4-bbea-256f561c8a3d", {
                "action": "polish",
                "selectedText": "",
            })

    def test_ai_edit_route_returns_400_for_invalid_action(self):
        os.environ["APP_AUTH_ENABLED"] = "false"
        os.environ["APP_LOGIN_ENABLED"] = "false"
        import main as flask_main

        client = flask_main.app.test_client()
        response = client.post(
            "/api/bidding/interpretations/a1d853bc-ca4e-43b4-bbea-256f561c8a3d/sections/ai-edit",
            json={"action": "unknown", "selectedText": "文本"},
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("不支持", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()

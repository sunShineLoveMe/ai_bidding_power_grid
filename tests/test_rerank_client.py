import os
import unittest
from unittest.mock import Mock, patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")


class DashScopeRerankClientTest(unittest.TestCase):
    def _mock_response(self, payload):
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}, clear=False)
    @patch("backend.ai.rerank_client.record_ai_usage_log")
    @patch("backend.ai.rerank_client.requests.post")
    @patch("backend.ai.rerank_client.get_setting")
    def test_qwen3_rerank_uses_compatible_api(self, get_setting_mock, post_mock, _usage):
        from backend.ai import rerank_client

        def setting(name, default=None):
            return {
                "rerank_enabled": True,
                "rerank_model": "qwen3-rerank",
                "rerank_top_n": 2,
                "request_timeout_seconds": 30,
            }.get(name, default)

        get_setting_mock.side_effect = setting
        post_mock.return_value = self._mock_response(
            {
                "object": "list",
                "results": [
                    {"index": 1, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.72},
                ],
                "model": "qwen3-rerank",
                "usage": {"total_tokens": 42},
            }
        )

        rows = [{"content": "资格审查"}, {"content": "技术规范书响应"}]
        result = rerank_client.rerank_documents("电网投标", rows, text_key="content", top_n=2)

        self.assertEqual([item["content"] for item in result], ["技术规范书响应", "资格审查"])
        self.assertEqual(result[0]["rerank_score"], 0.91)
        self.assertEqual(post_mock.call_args.args[0], rerank_client.RERANK_COMPAT_ENDPOINT)
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "qwen3-rerank")
        self.assertEqual(payload["query"], "电网投标")
        self.assertEqual(payload["documents"], ["资格审查", "技术规范书响应"])
        self.assertEqual(payload["top_n"], 2)

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}, clear=False)
    @patch("backend.ai.rerank_client.record_ai_usage_log")
    @patch("backend.ai.rerank_client.requests.post")
    @patch("backend.ai.rerank_client.get_setting")
    def test_legacy_rerank_model_uses_text_rerank_api(self, get_setting_mock, post_mock, _usage):
        from backend.ai import rerank_client

        def setting(name, default=None):
            return {
                "rerank_enabled": True,
                "rerank_model": "gte-rerank-v2",
                "rerank_top_n": 1,
                "request_timeout_seconds": 30,
            }.get(name, default)

        get_setting_mock.side_effect = setting
        post_mock.return_value = self._mock_response(
            {
                "output": {"results": [{"index": 0, "relevance_score": 0.77}]},
                "usage": {"total_tokens": 21},
                "request_id": "req-test",
            }
        )

        rows = [{"content": "资格审查"}, {"content": "无关内容"}]
        result = rerank_client.rerank_documents("电网投标", rows, text_key="content", top_n=1)

        self.assertEqual(result[0]["content"], "资格审查")
        self.assertEqual(post_mock.call_args.args[0], rerank_client.RERANK_TEXT_ENDPOINT)
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "gte-rerank-v2")
        self.assertEqual(payload["input"]["query"], "电网投标")
        self.assertEqual(payload["input"]["documents"], ["资格审查", "无关内容"])
        self.assertEqual(payload["parameters"]["top_n"], 1)


if __name__ == "__main__":
    unittest.main()

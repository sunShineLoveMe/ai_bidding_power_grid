import unittest
from unittest.mock import MagicMock, Mock, patch

from backend.ai import qwen_client


def _setting(key, default=None):
    values = {
        "ai_provider": "deepseek",
        "text_model": "deepseek-v4-flash",
        "knowledge_model": "deepseek-v4-flash",
        "deepseek_base_url": "https://api.deepseek.com",
        "request_timeout_seconds": 120,
        "stream_connect_timeout_seconds": 15,
        "stream_read_timeout_seconds": 180,
        "max_retries": 0,
        "retry_status_codes": "429,500,502,503,504",
        "retry_base_delay_seconds": 1.5,
        "retry_max_delay_seconds": 12,
    }
    return values.get(key, default)


class DeepSeekClientCompatibilityTest(unittest.TestCase):
    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}, clear=False)
    @patch("backend.ai.qwen_client.record_ai_usage_log")
    @patch("backend.ai.qwen_client.requests.post")
    @patch("backend.ai.qwen_client.get_setting", side_effect=_setting)
    def test_deepseek_response_is_normalized_to_existing_payload_shape(
        self,
        _mock_setting,
        mock_post,
        mock_record_usage,
    ):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "id": "chatcmpl-test",
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "{\"ok\":true}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 5,
                "total_tokens": 17,
            },
        }
        mock_post.return_value = response

        payload = qwen_client.call_dashscope_api(
            [{"role": "user", "content": "返回 JSON"}],
            json_mode=True,
            usage_context={"project_id": "project-1", "stage": "unit_test"},
        )

        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["output"]["choices"][0]["message"]["content"], "{\"ok\":true}")
        request_body = mock_post.call_args.kwargs["json"]
        self.assertEqual(request_body["model"], "deepseek-v4-flash")
        self.assertEqual(request_body["response_format"], {"type": "json_object"})
        mock_record_usage.assert_called_once()
        usage_kwargs = mock_record_usage.call_args.kwargs
        self.assertEqual(usage_kwargs["provider"], "deepseek")
        self.assertEqual(usage_kwargs["api_protocol"], "openai_compatible")
        self.assertEqual(usage_kwargs["raw_usage"]["total_tokens"], 17)

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}, clear=False)
    @patch("backend.ai.qwen_client.record_ai_usage_log")
    @patch("backend.ai.qwen_client.requests.post")
    @patch("backend.ai.qwen_client.get_setting", side_effect=_setting)
    def test_deepseek_stream_records_usage_when_consumer_closes_generator(
        self,
        _mock_setting,
        mock_post,
        mock_record_usage,
    ):
        response = MagicMock()
        response.status_code = 200
        response.iter_lines.return_value = iter([
            'data: {"id":"chatcmpl-test","choices":[{"delta":{"content":"测试"}}]}',
            'data: {"id":"chatcmpl-test","choices":[{"delta":{"content":"继续"}}]}',
        ])
        mock_post.return_value.__enter__.return_value = response

        stream = qwen_client.stream_dashscope_api(
            [{"role": "user", "content": "写一段话"}],
            usage_context={"project_id": "project-1", "stage": "unit_stream_close"},
        )

        self.assertEqual(next(stream), "测试")
        stream.close()

        mock_record_usage.assert_called_once()
        usage_kwargs = mock_record_usage.call_args.kwargs
        self.assertEqual(usage_kwargs["provider"], "deepseek")
        self.assertEqual(usage_kwargs["stage"], "unit_stream_close")
        self.assertTrue(usage_kwargs["metadata"]["stream_closed_by_consumer"])
        self.assertTrue(usage_kwargs["metadata"]["partial_output"])
        self.assertEqual(usage_kwargs["output_text"], "测试")


if __name__ == "__main__":
    unittest.main()

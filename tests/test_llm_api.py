import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("llm_api_test_module", ROOT / "core/llm_api.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
LLMAPIClient = module.LLMAPIClient


def response(*, content="", finish_reason="stop", reasoning="", completion_tokens=0):
    payload = {
        "choices": [{
            "message": {"content": content, "reasoning_content": reasoning},
            "finish_reason": finish_reason,
        }],
        "usage": {"completion_tokens": completion_tokens},
    }
    mocked = Mock(status_code=200, text=json.dumps(payload))
    mocked.json.return_value = payload
    return mocked


class LLMAPIClientTests(unittest.TestCase):
    def setUp(self):
        self.client = LLMAPIClient("key", "https://example.test", "model")

    def test_strict_request_expands_token_budget_after_reasoning_truncation(self):
        responses = [
            response(finish_reason="length", reasoning="x" * 6946, completion_tokens=4096),
            response(content='{"summary":"ok"}', completion_tokens=5000),
        ]
        with patch.object(module.requests, "post", side_effect=responses) as post:
            result = self.client.chat_completion(
                [{"role": "user", "content": "summarize"}],
                strict=True, max_tokens=4096,
            )
        self.assertEqual(result, '{"summary":"ok"}')
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].kwargs["json"]["max_tokens"], 4096)
        self.assertEqual(post.call_args_list[1].kwargs["json"]["max_tokens"], 8192)

    def test_strict_request_reports_reasoning_after_retry_limit(self):
        responses = [
            response(finish_reason="length", reasoning="x", completion_tokens=4096),
            response(finish_reason="length", reasoning="y", completion_tokens=8192),
            response(finish_reason="length", reasoning="z", completion_tokens=16384),
        ]
        with patch.object(module.requests, "post", side_effect=responses):
            with self.assertRaisesRegex(
                    ValueError, r"after 3 attempts.*reasoning_chars=1"):
                self.client.chat_completion(
                    [{"role": "user", "content": "summarize"}],
                    strict=True, max_tokens=4096,
                )


if __name__ == "__main__":
    unittest.main()

import importlib.util
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("deepseek_search_module", ROOT / "core" / "deepseek_search.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DeepSeekSearchClient = module.DeepSeekSearchClient


class DeepSeekSearchClientTests(unittest.TestCase):
    def setUp(self):
        self.client = DeepSeekSearchClient(api_key="test-key", base_url="https://api.deepseek.com")

    def test_search_parameter_validation_and_payload(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {"results": []}
            )

            # 超过 128 字符截断，count 限制在 1~50
            long_query = "a" * 200
            self.client.search(
                query=long_query,
                count=100,
                ori_question="用户的问题" * 30,
                need_content=True,
                localization="1.1.1.1"
            )

            self.assertTrue(mock_post.called)
            call_kwargs = mock_post.call_args[1]
            payload = call_kwargs["json"]

            self.assertEqual(len(payload["query"]), 128)
            self.assertEqual(payload["count"], 50)
            self.assertEqual(len(payload["ori_question"]), 128)
            self.assertTrue(payload["need_content"])
            self.assertEqual(payload["localization"], "1.1.1.1")
            self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer test-key")

    def test_search_format_success_with_rerank_and_authority(self):
        sample_results = {
            "results": [
                {
                    "title": "DeepSeek 官方搜索测试",
                    "url": "https://example.com/test",
                    "rerank_score": 2.5,
                    "authority": 3,
                    "date": "2026-10-23T00:00:00Z",
                    "site_name": "DeepSeek",
                    "summary": "这是模型阅读的长摘要内容。",
                    "content": "这是网页正文内容。"
                }
            ]
        }
        with patch("requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200, json=lambda: sample_results)
            formatted = self.client.search_and_format(query="DeepSeek", need_content=True)

            self.assertIn("DeepSeek 官方搜索测试", formatted)
            self.assertIn("相关性评分: 2.50 (优质)", formatted)
            self.assertIn("权威度: 极权威", formatted)
            self.assertIn("这是模型阅读的长摘要内容。", formatted)
            self.assertIn("这是网页正文内容。", formatted)

    def test_search_empty_results(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200, json=lambda: {"results": []})
            formatted = self.client.search_and_format(query="不存在的内容xyz")
            self.assertIn("未检索到关于「不存在的内容xyz」的相关网页结果", formatted)

    def test_fetch_success_markdown(self):
        sample_fetch = {
            "title": "测试文章",
            "content": "# 测试标题\n\n这是抓取到的 Markdown 内容。"
        }
        with patch("requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200, json=lambda: sample_fetch)
            formatted = self.client.fetch_and_format("https://example.com/article")

            self.assertIn("测试文章", formatted)
            self.assertIn("这是抓取到的 Markdown 内容。", formatted)

    def test_error_handling_mapping(self):
        # 测试 401
        with patch("requests.post") as mock_post:
            mock_post.return_value = Mock(
                status_code=401,
                text=json.dumps({"error": {"message": "Invalid API key"}})
            )
            res = self.client.search("test")
            self.assertIn("error", res)
            self.assertIn("API Key 缺失或无效", res["error"])

        # 测试 429 限速
        with patch("requests.post") as mock_post:
            mock_post.return_value = Mock(
                status_code=429,
                text=json.dumps({"error": {"message": "Rate limit exceeded"}})
            )
            res = self.client.fetch("https://example.com")
            self.assertIn("error", res)
            self.assertIn("429", res["error"])


if __name__ == "__main__":
    unittest.main()

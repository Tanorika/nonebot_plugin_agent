import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("summary_test_module", ROOT / "core/memory_summarizer.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ModelSummarizer = module.ModelSummarizer


class ModelSummarizerTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock(model="summary-model")
        self.summarizer = ModelSummarizer(self.client)

    def test_separate_prompt_and_strict_json_contract(self):
        self.client.chat_completion.return_value = '{"summary":"模型归纳内容"}'
        self.assertEqual(self.summarizer([{"text": "original"}], 700), "模型归纳内容")
        args = self.client.chat_completion.call_args.kwargs
        self.assertTrue(args["strict"])
        self.assertEqual(args["max_tokens"], ModelSummarizer.MAX_TOKENS)
        self.assertIn("original", args["messages"][1]["content"])
        self.assertIn("700", args["messages"][0]["content"])

    def test_failed_chat_reply_cannot_become_a_memory(self):
        for response in ('{"reply":"API failure", "action":null}', '{"summary":""}',
                         '[]', 'not json', json.dumps({"summary": "x" * 701})):
            self.client.chat_completion.return_value = response
            with self.assertRaises(ValueError):
                self.summarizer([{"text": "original"}], 700)

    def test_overlong_summary_is_repaired_once(self):
        self.client.chat_completion.side_effect = [
            json.dumps({"summary": "x" * 701}),
            '{"summary":"compressed"}',
        ]
        self.assertEqual(self.summarizer([{"text": "original"}], 700), "compressed")
        self.assertEqual(self.client.chat_completion.call_count, 2)
        repair_prompt = self.client.chat_completion.call_args_list[1].kwargs["messages"][0]["content"]
        self.assertIn("701", repair_prompt)
        self.assertIn("595", repair_prompt)

    def test_long_source_includes_middle_and_end_in_chunk_requests(self):
        self.client.chat_completion.return_value = '{"summary":"condensed"}'
        source = "FIRST-" + "x" * 18000 + "MIDDLE-" + "y" * 18000 + "LAST"
        self.summarizer([{"text": source}], 700)
        requests = [call.kwargs["messages"][1]["content"]
                    for call in self.client.chat_completion.call_args_list]
        self.assertTrue(any("FIRST-" in request for request in requests))
        self.assertTrue(any("MIDDLE-" in request for request in requests))
        self.assertTrue(any("LAST" in request for request in requests))
        self.assertTrue(all(len(request) <= ModelSummarizer.INPUT_CHARS for request in requests))
        self.assertIn("ordered_fragment_summaries", requests[-1])


if __name__ == "__main__":
    unittest.main()

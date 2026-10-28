import ast
from datetime import datetime
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


class MemoryWindowTests(unittest.TestCase):
    def make_client(self, enabled=True):
        source = ast.parse((ROOT / "core/llm_client.py").read_text(encoding="utf-8"))
        cls = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "LLMClient")
        config = SimpleNamespace(
            preset="{LongMemory}", memory_tree_enabled=enabled,
            max_history=3, memory_tree_recent_messages=7, memory_tree_max_chars=3000,
        )
        namespace = {"datetime": datetime, "json": json, "re": re, "plugin_config": config,
                     "LLMAPIClient": Mock,
                     "SkillManager": Mock(), "TaskManager": Mock(),
                     "JsonResponseParser": Mock()}
        namespace["JsonResponseParser"].parse.return_value = None
        namespace["SkillManager"].list_skills.return_value = "skills"
        namespace["TaskManager"].return_value.get_executing.return_value = "tasks"
        namespace["TaskManager"].return_value.list_scheduled_tasks.return_value = "scheduled"
        exec(compile(ast.Module(body=[cls], type_ignores=[]), "llm_client.py", "exec"), namespace)
        client = namespace["LLMClient"].__new__(namespace["LLMClient"])
        client.user_id = "123"
        memory = SimpleNamespace(
            history=[{"role": "system", "content": "stale preset"}]
                    + [{"role": "user", "content": str(i)} for i in range(50)],
            long_mem=Mock(), similarity_ctrl=Mock(), memory_tree_context=Mock(),
        )
        memory.long_mem.load_all.return_value = "independent long-term facts"
        memory.similarity_ctrl.get_vector.return_value = []
        memory.add_history = lambda role, content, vector=None: memory.history.append({"role": role, "content": content})
        client.memory = memory
        api = Mock()
        api.chat_completion.return_value = "answer"
        client._create_api_client = Mock(return_value=api)
        return client, memory, api

    def test_tree_and_recent_tail_share_current_input_boundary(self):
        client, memory, api = self.make_client()

        def context(**kwargs):
            self.assertIn("CURRENT", memory.history[-1]["content"])
            self.assertEqual(kwargs["recent_messages"], 7)
            return "DERIVED OLD HISTORY"

        memory.memory_tree_context.side_effect = context
        client.chat("CURRENT")
        messages = api.chat_completion.call_args.kwargs["messages"]
        self.assertEqual(len(messages), 9)  # preset + derived view + 7 originals
        self.assertEqual(messages[0]["content"], "independent long-term facts")
        self.assertEqual(messages[1], {"role": "user", "content": "DERIVED OLD HISTORY"})
        self.assertEqual(messages[2]["content"], "44")
        self.assertIn("CURRENT", messages[-1]["content"])
        self.assertFalse(any(item["content"] == "DERIVED OLD HISTORY" for item in memory.history))

    def test_disabled_tree_uses_original_max_history(self):
        client, memory, api = self.make_client(enabled=False)
        client.chat("CURRENT")
        memory.memory_tree_context.assert_not_called()
        self.assertEqual(len(api.chat_completion.call_args.kwargs["messages"]), 4)

    def test_vision_only_attaches_to_current_input(self):
        client, memory, api = self.make_client()
        memory.memory_tree_context.return_value = "HISTORY"
        parts = [{"type": "text", "text": "CURRENT"},
                 {"type": "image_url", "image_url": {"url": "https://example.test/image"}}]
        client.chat("CURRENT", content_parts=parts)
        messages = api.chat_completion.call_args.kwargs["messages"]
        self.assertEqual(messages[-1]["content"], parts)
        self.assertTrue(all(isinstance(item["content"], str) for item in messages[:-1]))
        self.assertTrue(all(isinstance(item["content"], str) for item in memory.history))


if __name__ == "__main__":
    unittest.main()

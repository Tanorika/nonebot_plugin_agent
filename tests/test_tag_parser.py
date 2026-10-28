import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tag_parser", ROOT / "core" / "tag_parser.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
JsonResponseParser = module.JsonResponseParser


class JsonResponseParserTests(unittest.TestCase):
    def test_parses_strict_contract(self):
        result = JsonResponseParser.parse('{"reply":"ok","action":"task_finish","params":{}}')
        self.assertEqual(result["reply"], "ok")
        self.assertEqual(result["pending_action"], {"action": "task_finish", "params": {}})

    def test_extracts_contract_after_natural_language_and_action_example(self):
        text = (
            "[STICKER:11] 好的，先查看目录。\n\n"
            '{"action": "base_exec", "params": {"command": "echo hi"}}\n\n'
            '{"reply": "开始查看目录。", "action": "base_exec", '
            '"params": {"command": "cmd /c dir G:/StableDiffusion /b"}}'
        )
        result = JsonResponseParser.parse(text)
        self.assertEqual(result["reply"], "开始查看目录。")
        self.assertEqual(result["pending_action"]["action"], "base_exec")
        self.assertEqual(result["pending_action"]["params"]["command"], "cmd /c dir G:/StableDiffusion /b")

    def test_does_not_treat_json_inside_reply_string_as_action(self):
        result = JsonResponseParser.parse(
            '{"reply":"示例是 {\\"action\\": null}","action":null,"params":{}}'
        )
        self.assertEqual(result["reply"], '示例是 {"action": null}')
        self.assertIsNone(result["pending_action"]["action"])

    def test_extracts_standalone_action_after_reply_text(self):
        result = JsonResponseParser.parse(
            '[STICKER:11] 好的，正在检查状态。\n\n'
            '{"action": "base_exec", "params": {"command": "Get-ChildItem core"}}'
        )
        self.assertEqual(result["reply"], "[STICKER:11] 好的，正在检查状态。")
        self.assertEqual(result["pending_action"]["action"], "base_exec")
        self.assertEqual(result["pending_action"]["params"]["command"], "Get-ChildItem core")


if __name__ == "__main__":
    unittest.main()

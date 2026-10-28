import ast
import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


task_module = load_module("test_task_manager", ROOT / "tools/task_manager.py")
parser_module = load_module("test_tag_parser", ROOT / "core/tag_parser.py")


def load_definitions(path, names, namespace):
    # Isolate production logic from NoneBot startup and live API credentials.
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if getattr(node, "name", None) in names]
    for node in nodes:
        node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)


class DelayedTaskTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_dir = task_module.TASK_DIR
        task_module.TASK_DIR = self.temp.name
        self.manager = task_module.TaskManager("123")
        self.sender = AsyncMock()
        self.client = Mock()
        self.client.memory = SimpleNamespace(history=[], add_history=Mock())
        self.namespace = {
            "Dict": dict, "Any": object, "datetime": task_module.datetime,
            "logger": Mock(), "LLMClient": Mock(return_value=self.client),
            "BaseTools": Mock(), "SkillManager": Mock(),
            "TaskManager": task_module.TaskManager,
            "JsonResponseParser": parser_module.JsonResponseParser,
            "send_multimedia_message": self.sender,
            "plugin_config": SimpleNamespace(safe_commands=[], skill_safe_mode=1,
                                             whitelist_skills=["check"], blacklist_skills=[]),
        }
        load_definitions(ROOT / "core/agent_loop.py", {"AgentExecutor"}, self.namespace)
        self.executor = self.namespace["AgentExecutor"]("123")

    def tearDown(self):
        task_module.TASK_DIR = self.original_dir
        self.temp.cleanup()

    def answer(self, action=None, params=None, reply=""):
        return json.dumps({"reply": reply, "action": action, "params": params or {}})

    def test_validation_and_persistence(self):
        for delay in (-1, 0.5, "nan", True, None):
            self.assertTrue(self.manager.schedule_delayed_task("resume", delay).startswith("❌"))
        self.assertTrue(self.manager.schedule_delayed_task("", 0).startswith("❌"))
        self.manager.schedule_delayed_task("", 0, "check", "inspect result", "original goal")
        restored = task_module.TaskManager("123")
        due = restored.get_due_tasks()
        self.assertEqual(due[0][1]["context"], "original goal")
        self.assertEqual(due[0][1]["callback_prompt"], "inspect result")
        restored.update_status("check", "running")
        self.assertEqual(restored.get_due_tasks(), [])
        restored.recover_interrupted_tasks()
        self.assertEqual(len(restored.get_due_tasks()), 1)

    def test_cancellation_and_user_isolation(self):
        self.manager.schedule_delayed_task("resume", 0, "same")
        other = task_module.TaskManager("456")
        other.schedule_delayed_task("other goal", 0, "same")
        self.manager.cancel_scheduled_task("same")
        self.assertEqual(self.manager.get_due_tasks(), [])
        self.assertEqual(other.get_due_tasks()[0][1]["callback_prompt"], "other goal")

    async def test_schedule_ends_current_llm_round(self):
        self.client.memory.history = [{"role": "user", "content": "check after waiting"}]
        self.client.chat.return_value = self.answer("task_schedule", {
            "callback_prompt": "inspect result", "delay_seconds": 0,
        }, "waiting")
        result = await self.executor.run("check after waiting", object())
        self.assertTrue(result["suspended"])
        self.assertEqual(self.client.chat.call_count, 1)
        self.assertEqual(len(self.manager.get_due_tasks()), 1)
        self.sender.assert_awaited_once()

    async def test_resumed_task_can_execute_skill(self):
        self.client.chat.side_effect = [
            self.answer("skill_exec", {"name": "check"}), self.answer(reply="result checked"),
        ]
        self.executor.skill.execute_skill.return_value = "ready"
        result = await self.executor.run("resume check", object(), role="system")
        self.assertEqual(result["reply"], "result checked")
        self.executor.skill.execute_skill.assert_called_once_with("check", {})
        self.assertEqual(self.client.chat.call_args_list[0].kwargs["role"], "system")

    async def test_resumed_task_requires_authorization(self):
        self.client.chat.return_value = self.answer("base_write", {"path": "example"})
        result = await self.executor.run("resume write", object())
        self.assertEqual(result["pending_action"]["action"], "base_write")
        self.executor.base.write_file.assert_not_called()

    def controller(self):
        namespace = {
            "Matcher": object, "AgentExecutor": self.namespace["AgentExecutor"],
            "logger": Mock(), "sessions": {"123": {"executor": self.executor, "task_id": "callback"}},
            "smart_split_send": self.sender,
            "FinishedException": type("Finished", (Exception,), {}),
            "PausedException": type("Paused", (Exception,), {}),
            "RejectedException": type("Rejected", (Exception,), {}),
        }
        self.manager.schedule_delayed_task("resume", 0, "callback")
        self.manager.update_status("callback", "running")
        load_definitions(ROOT / "__init__.py", {"run_agent_loop"}, namespace)
        return namespace

    async def test_controller_keeps_confirmation_session(self):
        namespace = self.controller()
        self.client.chat.return_value = self.answer("base_write", {"path": "example"})
        await namespace["run_agent_loop"](object(), "123", "resume", role="system")
        self.assertEqual(namespace["sessions"]["123"]["pending_action"]["action"], "base_write")
        self.assertEqual(self.manager._get_data()["scheduled"]["callback"]["status"], "awaiting_confirmation")

    async def test_controller_reports_callback_failure(self):
        namespace = self.controller()
        self.client.chat.side_effect = RuntimeError("model unavailable")
        await namespace["run_agent_loop"](object(), "123", "resume", role="system")
        record = self.manager._get_data()["scheduled"]["callback"]
        self.assertEqual(record["status"], "failed")
        self.assertIn("model unavailable", record["error"])
        self.assertNotIn("123", namespace["sessions"])

    async def test_worker_preserves_offline_tasks_then_resumes_once(self):
        self.manager.schedule_delayed_task("resume", 0, "callback")
        bot = object()
        bots = Mock(side_effect=[{}, {"bot": bot}])
        callback = AsyncMock()

        async def execute(sender, user_id, event, role):
            self.assertIs(sender, bot)
            self.assertEqual(role, "system")
            self.assertIn("resume", event)
            self.manager.update_status("callback", "completed")
            namespace["sessions"].pop(user_id)

        callback.side_effect = execute
        namespace = {
            "asyncio": SimpleNamespace(sleep=AsyncMock(side_effect=[None, None, asyncio.CancelledError()]),
                                       CancelledError=asyncio.CancelledError, Lock=asyncio.Lock),
            "get_bots": bots, "Bot": object, "TaskManager": task_module.TaskManager,
            "sessions": {}, "user_locks": {}, "logger": Mock(),
            "AgentExecutor": Mock(return_value=self.executor), "run_agent_loop": callback,
        }
        load_definitions(ROOT / "__init__.py", {"user_lock", "resume_scheduled_tasks"}, namespace)
        with self.assertRaises(asyncio.CancelledError):
            await namespace["resume_scheduled_tasks"]()
        callback.assert_awaited_once()
        self.assertEqual(self.manager._get_data()["scheduled"]["callback"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()

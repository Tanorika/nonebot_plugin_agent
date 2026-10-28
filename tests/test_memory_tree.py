import importlib.util
import ast
import json
import math
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("memory_tree_test_module", ROOT / "core/memory_tree.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MemoryTree = module.MemoryTree


def history(count):
    return [{"role": "system", "content": "changing preset"}] + [
        {"role": "user" if index % 2 == 0 else "assistant",
         "content": f"original message {index}"} for index in range(count)]


class MemoryTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "tree.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_nary_carry_and_model_parents(self):
        tree = MemoryTree(self.path, history(16), fanout=4)
        calls = []

        def summarize(children, limit):
            calls.append(children)
            return f"MODEL summary {len(calls)}"

        self.assertEqual(tree.summarize_pending(summarize), 5)
        self.assertEqual(len(tree.data["frontier"]), 1)
        root = tree.data["nodes"][tree.data["frontier"][0]]
        self.assertEqual(root["summary"], "MODEL summary 5")
        self.assertEqual(len(root["children"]), 4)
        self.assertTrue(all(child["text"].startswith("MODEL summary") for child in calls[-1]))
        self.assertIn("original message 2", calls[0][2]["text"])
        self.assertEqual(tree.stats()["leaves"], 16)

    def test_no_parent_before_fanout_is_reached(self):
        tree = MemoryTree(self.path, history(3), fanout=4)
        summarizer = Mock()
        self.assertEqual(tree.summarize_pending(summarizer), 0)
        tree.add_message(4, "assistant", "fourth")
        self.assertEqual(tree.stats()["parents"], 1)
        summarizer.assert_not_called()

    def test_restart_reuses_completed_summaries_and_resumes_pending(self):
        tree = MemoryTree(self.path, history(16))
        tree.summarize_pending(lambda children, limit: "completed", max_nodes=2)
        restored = MemoryTree(self.path, history(17))
        self.assertEqual(restored.stats()["ready"], 2)
        summarizer = Mock(return_value="remaining", model="test-model", PROMPT_VERSION=1)
        self.assertEqual(restored.summarize_pending(summarizer), 3)
        self.assertEqual(restored.stats()["leaves"], 17)

    def test_runtime_and_offline_use_same_completed_index(self):
        path = module.tree_index_path(self.temp.name, "123", 4, 700)
        source = history(16)
        tree = MemoryTree(path, source)
        tree.summarize_pending(lambda children, limit: "already paid for")
        # Exercise the actual runtime configure_tree method without loading NoneBot.
        parsed = ast.parse((ROOT / "core/memory_manager.py").read_text(encoding="utf-8"))
        cls = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "MemoryManager")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "configure_tree")
        namespace = {"shared_tree": module.shared_tree, "tree_index_path": module.tree_index_path,
                     "TREE_MEM_DIR": self.temp.name}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "configure_tree", "exec"), namespace)
        from types import SimpleNamespace
        manager = SimpleNamespace(user_id="123", history=source)
        summarizer = Mock(return_value="new summary", model="test", PROMPT_VERSION=1)
        namespace["configure_tree"](manager, summarizer)
        summarizer.assert_not_called()
        self.assertEqual(manager.memory_tree.stats()["ready"], 5)
        offline = (ROOT / "tools/build_memory_tree.py").read_text(encoding="utf-8")
        self.assertIn("tree_module.tree_index_path(", offline)

    def test_repeated_chat_sync_and_restart_do_not_resummarize(self):
        source = history(16)
        for item in source[1:]:
            item["created_at"] = "2026-10-21T20:00:00+08:00"
        tree = MemoryTree(self.path, source)
        tree.summarize_pending(lambda children, limit: "already paid for")
        summarizer = Mock(return_value="new summary", model="test", PROMPT_VERSION=1)
        for count in range(17, 24):
            source.append({"role": "user", "content": str(count),
                           "created_at": "2026-10-21T21:00:00+08:00"})
            tree = MemoryTree(self.path, json.loads(json.dumps(source)))
            tree.sync(source)
            tree.summarize_pending(summarizer)
        # Seven appended messages form just one new four-message parent.
        self.assertEqual(summarizer.call_count, 1)
        self.assertEqual(tree.stats()["ready"], 6)

    def test_model_failure_keeps_originals_and_pending_jobs(self):
        tree = MemoryTree(self.path, history(16))
        with self.assertRaises(TimeoutError):
            tree.summarize_pending(Mock(side_effect=TimeoutError()))
        restored = MemoryTree(self.path, history(16))
        self.assertEqual(restored.stats()["ready"], 0)
        root = restored.data["frontier"][0]
        self.assertIn("original message 8", restored.expand(root, depth=3))
        self.assertEqual(restored.summarize_pending(lambda children, limit: "recovered"), 5)

    def test_invalid_model_summary_is_not_saved(self):
        tree = MemoryTree(self.path, history(4), summary_chars=128)
        for invalid in ("", "x" * 129, None):
            with self.assertRaises(ValueError):
                tree.summarize_pending(lambda children, limit: invalid)
            self.assertEqual(tree.stats()["ready"], 0)

    def test_window_covers_all_old_messages_once_at_power_boundaries(self):
        for fanout in (2, 3, 4, 8):
            tree = MemoryTree(self.path, history(0), fanout=fanout)
            source = history(0)
            for count in range(1, 260):
                item = {"role": "user", "content": str(count)}
                tree.add_message(len(source), **item)
                source.append(item)
                for recent in (1, 7, 40):
                    nodes = tree.window_nodes(recent)
                    ranges = [index for node in nodes for index in range(node["start"], node["end"])]
                    self.assertEqual(ranges, list(range(max(0, count - recent))))
                    # A prefix of the base-b frontier has at most two boundary
                    # paths per level, independent of the raw history length.
                    bound = 2 * (fanout - 1) * (1 + math.ceil(math.log(max(2, count), fanout)))
                    self.assertLessEqual(len(nodes), bound)

    def test_small_budget_retains_every_reference(self):
        tree = MemoryTree(self.path, history(127), summary_chars=700)
        tree.summarize_pending(lambda children, limit: "s" * 700)
        context = tree.context(max_chars=1000, recent_messages=7)
        self.assertLessEqual(len(context), 1000)
        for node in tree.window_nodes(7):
            self.assertIn(f"[{node['id']} ", context)

    def test_leaf_expansion_paginates_original_without_1400_char_cutoff(self):
        text = "start" + "x" * 5000 + "END-original"
        tree = MemoryTree(self.path, [{"role": "user", "content": text}])
        ref = tree.data["frontier"][0]
        pages = [tree.expand(ref, depth=0, max_chars=1000, offset=offset)
                 for offset in range(0, 5500, 820)]
        self.assertIn("END-original", "".join(pages))
        self.assertTrue(all(len(page) <= 1000 for page in pages))
        self.assertIn("offset=", pages[0])

    def test_log_edit_invalidates_summaries_but_preset_edit_does_not(self):
        source = history(4)
        tree = MemoryTree(self.path, source)
        tree.summarize_pending(lambda children, limit: "old")
        source[0]["content"] = "new preset"
        tree.sync(source)
        self.assertEqual(tree.stats()["ready"], 1)
        source[2]["content"] = "corrected original"
        tree.sync(source)
        self.assertEqual(tree.stats()["ready"], 0)

    def test_source_edit_during_model_call_discards_stale_response(self):
        source = history(4)
        tree = MemoryTree(self.path, source)
        calls = []

        def summarize(children, limit):
            calls.append(children)
            if len(calls) == 1:
                source[2]["content"] = "corrected original"
                tree.sync(source)
                return "STALE"
            return "CORRECTED"

        tree.summarize_pending(summarize)
        self.assertEqual(tree.data["nodes"][tree.data["frontier"][0]]["summary"], "CORRECTED")

    def test_single_background_worker_survives_new_executor_and_append(self):
        tree = module.shared_tree(self.path, history(4), fanout=4)
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def summarize(children, limit):
            calls.append(children)
            entered.set()
            self.assertTrue(release.wait(5))
            return "background summary"

        tree.start_background(summarize)
        self.assertTrue(entered.wait(5))
        same = module.shared_tree(self.path, history(8), fanout=4)
        self.assertIs(tree, same)
        same.start_background(summarize)
        release.set()
        tree._worker.join(5)
        self.assertFalse(tree._worker.is_alive())
        self.assertEqual(len(calls), 2)
        self.assertEqual(tree.stats()["ready"], 2)

    def test_v1_index_is_rebuilt_instead_of_reusing_string_concatenation(self):
        Path(self.path).write_text(json.dumps({"version": 1, "nodes": {}}), encoding="utf-8")
        tree = MemoryTree(self.path, history(8))
        self.assertEqual(tree.stats()["ready"], 0)
        self.assertEqual(tree.stats()["leaves"], 8)


if __name__ == "__main__":
    unittest.main()

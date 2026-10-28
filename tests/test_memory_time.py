import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("memory_time_test_module", ROOT / "core/memory_time.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MemoryTimeTests(unittest.TestCase):
    def test_legacy_timestamp_moves_out_of_content(self):
        item = module.normalize({"role": "user", "content": "[2026-01-02 03:04:05] 旧消息"})
        self.assertEqual(item["content"], "旧消息")
        self.assertEqual(item["created_at"], "2026-01-02T03:04:05")

    def test_interval_uses_month_language_for_long_gap(self):
        self.assertEqual(
            module.interval("2026-01-01T00:00:00+08:00", "2026-04-01T00:00:00+08:00"),
            "约 3 个月",
        )

    def test_label_keeps_exact_time(self):
        result = module.label("2026-10-21T10:20:30+08:00")
        self.assertIn("2026-10-21 10:20:30 +0800", result)
        self.assertIn("会话开始", result)

    def test_presentation_prefers_relative_language(self):
        result = module.presentation(
            "2026-10-21T10:20:30+08:00", "2026-10-21T10:19:30+08:00"
        )
        self.assertIn("今天 10:20", result)
        self.assertIn("约 1 分钟", result)
        self.assertNotIn("精确时间", result)

    def test_range_label_describes_period(self):
        result = module.range_label(
            "2026-01-01T00:00:00+08:00", "2026-04-01T00:00:00+08:00"
        )
        self.assertIn("2026年01月01日 00:00", result)
        self.assertIn("持续约 3 个月", result)


if __name__ == "__main__":
    unittest.main()

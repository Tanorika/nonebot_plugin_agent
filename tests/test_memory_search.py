import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("memory_search_core")
package.__path__ = [str(ROOT / "core")]
sys.modules[package.__name__] = package
embedding = types.ModuleType("memory_search_core.embedding_client")
embedding.request_vector = lambda text: {"data": [{"index": 0, "embedding": [1.0, 0.0]}]}
sys.modules[embedding.__name__] = embedding
spec = importlib.util.spec_from_file_location(
    "memory_search_core.Similarity", ROOT / "core" / "Similarity.py"
)
similarity_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(similarity_module)
SimilarityController = similarity_module.SimilarityController


class MemorySearchTests(unittest.TestCase):
    def setUp(self):
        self.controller = SimilarityController()

    def test_keyword_finds_unembedded_chinese_memory(self):
        results = self.controller.query_similar_history(
            [{"role": "user", "content": "用户说咩呀是她的专属口头禅"}],
            "咩呀", mode="keyword"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["keyword_score"], 1.0)

    def test_hybrid_combines_keyword_and_semantic_candidates(self):
        results = self.controller.query_similar_history([
            {"role": "user", "content": "完全不同的语义描述", "vector": [1.0, 0.0]},
            {"role": "user", "content": "提到咩呀这个词"},
        ], "咩呀", mode="hybrid", count=2)
        self.assertEqual(results[0]["content"], "提到咩呀这个词")
        self.assertEqual(len(results), 1)

    def test_semantic_mode_excludes_keyword_only_matches(self):
        results = self.controller.query_similar_history(
            [{"role": "user", "content": "提到咩呀这个词"}],
            "咩呀", mode="semantic"
        )
        self.assertEqual(results[0]["keyword_score"], 1.0)


if __name__ == "__main__":
    unittest.main()

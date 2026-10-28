<<<<<<< HEAD
import numpy as np
from typing import Union, List
from .embedding_client import request_vector 
=======
import re
from typing import Union, List
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

class SimilarityController:
    def __init__(self):
        pass

    def get_vector(self, text: Union[str, List[str]]) -> List[List[float]]:
<<<<<<< HEAD
        """获取向量封装"""
        raw_json = request_vector(text)
        if not raw_json or "data" not in raw_json:
            return []
        data_list = sorted(raw_json["data"], key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in data_list]

    def _ensure_matrix(self, data: Union[str, List[str], List]) -> np.ndarray:
=======
        """Compatibility shim: recall no longer depends on a remote embedding API."""
        return []

    def _ensure_matrix(self, data: Union[str, List[str], List]):
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        """统一转化为 Numpy 矩阵"""
        if isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], (int, float)): 
                return np.array([data])
            if isinstance(data[0], list): 
                return np.array(data)
<<<<<<< HEAD
        vectors = self.get_vector(data)
        return np.array(vectors)

    def query_similar_history(self, history_data: list, query_text: str, count: int = 3):
=======
        return []

    @staticmethod
    def _keyword_score(query_text: str, content: str) -> float:
        """Score exact terms and Chinese character bigrams without external dependencies."""
        query = query_text.casefold().strip()
        text = content.casefold()
        if not query or not text:
            return 0.0
        if query in text:
            return 1.0

        words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", query)
        terms = set()
        for word in words:
            if re.fullmatch(r"[\u4e00-\u9fff]+", word):
                terms.update(word[i:i + 2] for i in range(len(word) - 1))
                if len(word) == 1:
                    terms.add(word)
            else:
                terms.add(word)
        if not terms:
            return 0.0
        matched = sum(1 for term in terms if term in text)
        return matched / len(terms)

    def query_similar_history(self, history_data: list, query_text: str, count: int = 3,
                              mode: str = "keyword", keyword_weight: float = 0.6):
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        """
        核心检索函数：从历史 JSON 列表中寻找最相似的记录
        """
        if not history_data:
            return []

<<<<<<< HEAD
        # 1. 将查询文本转化为向量
        target_vec = self._ensure_matrix(query_text) # shape: (1, 1024)
=======
        # Semantic/hybrid are retained as compatibility values, but no longer
        # call the retired remote RAG service.
        mode = "keyword"
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        
        results = []
        for item in history_data:
            # 只检索有向量记录的消息，且排除 system 提示词
<<<<<<< HEAD
            if "vector" not in item:
                continue
                
            vec = np.array(item["vector"])
            # 计算余弦相似度
            similarity = np.dot(target_vec, vec.T)
            item_copy = item.copy()
            item_copy["current_similarity"] = float(np.max(similarity))
            results.append(item_copy)

        # 2. 按相似度排序
        results.sort(key=lambda x: x["current_similarity"], reverse=True)
        
        # 3. 返回前 count 条
        return results[:count]
=======
            item_copy = item.copy()
            content = str(item.get("content", ""))
            keyword_score = self._keyword_score(query_text, content)
            semantic_score = 0.0
            score = keyword_score
            item_copy["current_similarity"] = score
            item_copy["keyword_score"] = keyword_score
            item_copy["semantic_score"] = semantic_score
            if score > 0:
                results.append(item_copy)

        # 2. 按相似度排序
        results.sort(key=lambda x: (x["current_similarity"], x["keyword_score"]), reverse=True)
        
        # 3. 返回前 count 条
        return results[:count]
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

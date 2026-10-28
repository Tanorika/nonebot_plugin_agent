import os
import json
import base64       
import numpy as np
<<<<<<< HEAD
from datetime import datetime
from .Similarity import SimilarityController
=======
from .Similarity import SimilarityController
from .memory_tree import shared_tree, tree_index_path
from .memory_time import normalize, now, label, presentation
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONG_MEM_DIR = os.path.join(PLUGIN_DIR, "memory", "long_term")
SHORT_MEM_DIR = os.path.join(PLUGIN_DIR, "memory")
<<<<<<< HEAD
=======
TREE_MEM_DIR = os.path.join(PLUGIN_DIR, "memory", "trees")
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

class LongMemory:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.file_path = os.path.join(LONG_MEM_DIR, f"{user_id}_longmem.json")
        os.makedirs(LONG_MEM_DIR, exist_ok=True)

    def save(self, content: str) -> str:
<<<<<<< HEAD
        """存入一条重要记忆（添加时间戳）"""
        memories = self._get_raw_list()
        timestamped_content = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {content}"
        
        # 检查原始内容是否已存在
        if content not in [mem.split('] ', 1)[-1] for mem in memories]:
            memories.append(timestamped_content)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(memories, f, ensure_ascii=False, indent=4)
            return f"已将内容存入长期记忆：'{content}'"
        return "该内容已存在于记忆中。"
=======
        """存入一条带结构化时间元数据的重要记忆。"""
        memories = self._get_raw_list()
        if content not in [self._memory_content(mem) for mem in memories]:
            memories.append({"content": content, "created_at": now()})
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(memories, f, ensure_ascii=False, indent=4)
            return f"✅ 已成功存入长期记忆：'{content}'"
        return "⚠️ 该内容已在长期记忆中，无需重复记录。"
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

    def _get_raw_list(self) -> list:
        """内部私有方法：获取原始记忆列表数据"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
<<<<<<< HEAD
                    return json.load(f)
            except:
                return []
        return []
=======
                    value = json.load(f)
                    return [normalize(item if isinstance(item, dict) else {"content": item})
                            for item in value if isinstance(item, (dict, str))]
            except:
                return []
        return []

    @staticmethod
    def _memory_content(item) -> str:
        return str(item.get("content", "")) if isinstance(item, dict) else str(item)
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
    
    def load_all(self) -> str:
        """获取带编号的记忆字符串，直接供 LLM 使用"""
        mems = self._get_raw_list()
        if not mems:
<<<<<<< HEAD
            return "（目前还没有特殊的长期记忆）"
        # 直接返回带 [1], [2] 编号的字符串
        return "\n".join([f"[{i+1}] {content}" for i, content in enumerate(mems)])
=======
            return "（暂无长期记忆记录）"
        # 直接返回带 [1], [2] 编号的字符串
        lines = []
        previous = None
        for i, item in enumerate(mems):
            compact = presentation(item['created_at'], previous)
            include_exact = previous is None or "个月" in compact or "年" in compact
            lines.append(f"[{i + 1}] 【记录时间：{presentation(item['created_at'], previous, include_exact=include_exact)}】\n"
                         f"{self._memory_content(item)}")
            previous = item["created_at"]
        return "\n".join(lines)
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

    def delete_by_index(self, index: int) -> str:
        """根据索引编号删除记忆"""
        mems = self._get_raw_list()
        try:
            idx = int(index) - 1  # AI 传来的编号转为 0 轴索引
            if 0 <= idx < len(mems):
                removed = mems.pop(idx)
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump(mems, f, ensure_ascii=False, indent=4)
<<<<<<< HEAD
                return f"已删除第 {index} 条记忆：'{removed}'"
            return f"找不到编号为 {index} 的记忆。"
        except (ValueError, TypeError):
            return "编号格式错误，请输入数字。"
=======
                return f"✅ 已成功删除第 {index} 条记忆：'{self._memory_content(removed)}'"
            return f"❌ 未找到编号为 {index} 的记忆。"
        except (ValueError, TypeError):
            return "❌ 编号格式错误，请输入有效的数字。"
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

class MemoryManager:
    """统一记忆管理器：同时接管短期上下文和长期记忆"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.short_mem_path = os.path.join(SHORT_MEM_DIR, f"{user_id}.json")
        self.long_mem = LongMemory(user_id)
        self.similarity_ctrl = SimilarityController()
        # 加载时会自动调用 _base64_to_vector
        self.history = self._load_short_memory()
<<<<<<< HEAD
=======
        self.memory_tree = None
        self.tree_summarizer = None

    def configure_tree(self, summarizer, fanout: int = 4, summary_chars: int = 700):
        """The model-backed index is optional; memlong is always independent."""
        self.memory_tree = shared_tree(
            tree_index_path(TREE_MEM_DIR, self.user_id, fanout, summary_chars),
            self.history, fanout=fanout, summary_chars=summary_chars,
        )
        self.tree_summarizer = summarizer
        self.memory_tree.start_background(summarizer)
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

    def _vector_to_base64(self, vector: list) -> str:
        """将 float 列表转为 base64 字符串 (使用 float32 节省空间)"""
        if vector is None: return None
        arr = np.array(vector, dtype=np.float32)
        return base64.b64encode(arr.tobytes()).decode('utf-8')

    def _base64_to_vector(self, b64_str: str) -> list:
        """将 base64 字符串还原为 float 列表"""
        if b64_str is None: return None
        try:
            data = base64.b64decode(b64_str)
            return np.frombuffer(data, dtype=np.float32).tolist()
        except:
            return None

    def _load_short_memory(self) -> list:
        if os.path.exists(self.short_mem_path):
            try:
                with open(self.short_mem_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 🚀 读取时解密向量
<<<<<<< HEAD
                    for item in data:
                        if isinstance(item.get("vector"), str):
                            item["vector"] = self._base64_to_vector(item["vector"])
                    return data
=======
                    normalized = [normalize(item if isinstance(item, dict) else {"content": item})
                                  for item in data]
                    for item in normalized:
                        if isinstance(item.get("vector"), str):
                            item["vector"] = self._base64_to_vector(item["vector"])
                    return normalized
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
            except Exception as e:
                return []
        return []

    def save_short_memory(self):
        """保存短期记忆，保存前进行编码"""
        import copy
        # 使用深拷贝防止污染内存中正在使用的 list 格式向量
        temp_history = copy.deepcopy(self.history)
        for item in temp_history:
            if isinstance(item.get("vector"), list):
                item["vector"] = self._vector_to_base64(item["vector"])
                
        with open(self.short_mem_path, 'w', encoding='utf-8') as f:
            json.dump(temp_history, f, ensure_ascii=False, indent=4)

    def add_history(self, role: str, content: str, vector: list = None):
        """添加一条对话记录"""
        self.history.append({
            "role": role,
            "content": content,
<<<<<<< HEAD
            "vector": vector
        })
        self.save_short_memory()

    def mem_rag(self, target: str, count: int = 5) -> str:
=======
            "created_at": now(),
            "vector": vector
        })
        self.save_short_memory()
        if self.memory_tree is not None:
            self.memory_tree.sync(self.history)
            self.memory_tree.start_background(self.tree_summarizer)

    def memory_tree_context(self, max_chars: int = 6000, recent_messages: int = 40) -> str:
        """Return a compact view of older conversation history."""
        if self.memory_tree is None:
            return ""
        return self.memory_tree.context(max_chars=max_chars, recent_messages=recent_messages)

    def memory_tree_expand(self, node_id: str, depth: int = 1, max_chars: int = 10000,
                           offset: int = 0) -> str:
        """Expand a tree reference back toward original conversation messages."""
        if self.memory_tree is None:
            return "会话记忆树未启用，可使用 mem_rag 检索原始历史。"
        return self.memory_tree.expand(
            node_id,
            self.history,
            depth=depth,
            max_chars=max_chars,
            offset=offset,
        )

    def mem_rag(self, target: str, count: int = 5, mode: str = "hybrid",
                expand=None, window: int = 2, max_chars: int = 5000) -> str:
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        """
        Agent 主动检索记忆的接口
        综合检索短期上下文中的高相似度对话
        (如果你也想检索长期记忆，可以在这里把 long_mem 的数据也向量化并合并搜索)
        """
<<<<<<< HEAD
        count = int(count)
        
        # 使用相似度控制器在当前 history 中搜索
        similar_results = self.similarity_ctrl.query_similar_history(self.history, target, count=count)
        
        if not similar_results:
            return f"检索记忆，未找到关于 '{target}' 的相关记录。"
            
        # 格式化输出给 Agent
        result_text = f"🔍 关于 '{target}' 的检索结果：\n"
        for i, item in enumerate(similar_results):
            # 过滤掉过长的系统提示词，提取核心内容
            content = item['content']
            if len(content) > 200:
                content = content[:200] + "..."
            result_text += f"[{i+1}] (相似度: {item.get('current_similarity', 0):.2f}) {item['role']}: {content}\n"
=======
        count = max(1, min(int(count or 5), 20))
        window = max(0, min(int(window or 2), 5))
        max_chars = max(500, min(int(max_chars or 5000), 12000))
        if isinstance(expand, (str, int)):
            expand = [expand]
        expand = {str(ref) for ref in (expand or [])}
        
        # Search short and long memory together; long-memory entries do not need vectors.
        candidates = []
        for index, item in enumerate(self.history):
            if item.get("role") != "system":
                candidate = item.copy()
                candidate["_ref"] = f"S{index}"
                candidate["_history_index"] = index
                candidates.append(candidate)
        candidates.extend({"role": "long_term", **item, "_ref": f"L{index + 1}"}
                          for index, item in enumerate(self.long_mem._get_raw_list()))
        similar_results = self.similarity_ctrl.query_similar_history(
            candidates, target, count=count, mode="keyword"
        )
        
        if not similar_results:
            return f"❌ 未检索到与 '{target}' 相关的历史记忆记录。"
            
        # 格式化输出给 Agent
        result_text = f"🔍 关于 '{target}' 的检索结果（keyword）：\n"
        used_chars = len(result_text)
        expanded_indices = {int(ref[1:]) for ref in expand if ref.startswith("S") and ref[1:].isdigit()}
        expanded_refs = set()
        for i, item in enumerate(similar_results):
            # 过滤掉过长的系统提示词，提取核心内容
            content = str(item['content']).splitlines()[0][:240]
            if len(str(item['content']).splitlines()[0]) > 240:
                content += "..."
            ref = item.get("_ref", f"R{i + 1}")
            result_text += (f"[{ref}] 【记录时间：{label(item.get('created_at', ''), None)}】 "
                            f"(综合: {item.get('current_similarity', 0):.2f}; "
                            f"关键词: {item.get('keyword_score', 0):.2f}) "
                            f"{item['role']}: {content}\n")
            if item.get("_history_index") in expanded_indices:
                expanded_refs.add(ref)
                start = max(0, item["_history_index"] - window)
                end = min(len(self.history), item["_history_index"] + window + 1)
                context_lines = []
                for neighbor_index in range(start, end):
                    neighbor = self.history[neighbor_index]
                    if neighbor.get("role") == "system":
                        continue
                    neighbor_content = str(neighbor.get("content", ""))[:500]
                    if len(str(neighbor.get("content", ""))) > 500:
                        neighbor_content += "..."
                    context_lines.append(f"  [S{neighbor_index}] {neighbor.get('role')}: {neighbor_content}")
                context = "展开上下文（前后各最多 %d 条）：\n%s\n" % (window, "\n".join(context_lines))
                if used_chars + len(context) <= max_chars:
                    result_text += context
                    used_chars += len(context)
        if expand:
            missing = expand - expanded_refs
            if missing:
                result_text += f"⚠️ 未找到可展开的引用：{', '.join(sorted(missing))}\n"
        result_text += "提示：需要语境时，可将结果中的引用放入 expand，例如 expand=['S42']。"
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
            
        return result_text
        

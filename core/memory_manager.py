import os
import json

# 记忆存储目录
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONG_MEM_DIR = os.path.join(PLUGIN_DIR, "memory", "long_term")

class LongMemory:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.file_path = os.path.join(LONG_MEM_DIR, f"{user_id}_longmem.json")
        os.makedirs(LONG_MEM_DIR, exist_ok=True)

    def save(self, content: str) -> str:
        """存入一条重要记忆"""
        memories = self._get_raw_list()
        if content not in memories:
            memories.append(content)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(memories, f, ensure_ascii=False, indent=4)
            return f"✅ 已成功保存记忆：'{content}'"
        return "⚠️ 该记忆已存在。"

    def _get_raw_list(self) -> list:
        """内部私有方法：获取原始记忆列表数据"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def load_all(self) -> str:
        """获取带编号的记忆字符串，直接供 LLM 使用"""
        mems = self._get_raw_list()
        if not mems:
            return "（目前还没有特殊的长期记忆）"
        # 直接返回带 [1], [2] 编号的字符串
        return "\n".join([f"[{i+1}] {content}" for i, content in enumerate(mems)])

    def delete_by_index(self, index: int) -> str:
        """根据索引编号删除记忆"""
        mems = self._get_raw_list()
        try:
            idx = int(index) - 1  # AI 传来的编号转为 0 轴索引
            if 0 <= idx < len(mems):
                removed = mems.pop(idx)
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump(mems, f, ensure_ascii=False, indent=4)
                return f"✅ 已成功删除第 {index} 条记忆：'{removed}'"
            return f"❌ 找不到编号为 {index} 的记忆。"
        except (ValueError, TypeError):
            return "❌ 编号格式不正确，请输入数字。"
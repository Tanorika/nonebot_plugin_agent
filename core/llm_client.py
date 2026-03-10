import os
import json
import requests
import re
from ..config import Config
from nonebot import get_plugin_config
from .memory_manager import LongMemory
plugin_config = get_plugin_config(Config)

# 获取插件根目录并创建 memory 文件夹
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(PLUGIN_DIR, "memory")

class LLMClient:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory_path = os.path.join(MEMORY_DIR, f"{user_id}.json")
        self.history = self._load_memory()

    def _load_memory(self):
        """从文件加载记忆，如果不存在则初始化"""
        os.makedirs(MEMORY_DIR, exist_ok=True)
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        # 初始设定
        return [{"role": "system", "content": plugin_config.preset}]

    def _save_memory(self):
        """将当前历史记录持久化到文件"""
        try:
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"❌ 记忆写入失败: {e}")

    def chat(self, user_input: str, role: str = "user") -> str:
        long_mem_manager = LongMemory(self.user_id)
        memory_text = long_mem_manager.load_all()

        preset = plugin_config.preset.replace("{LongMemory}", memory_text)
        #保证第一条必须为最新system prompt
        if len(self.history) > 0:
            self.history[0] = {"role": "system", "content": preset}
        else:
            self.history.append({"role": "system", "content": preset})
        # 记录用户输入
        self.history.append({"role": role, "content": user_input})
        n=plugin_config.max_history
        if len(self.history) > n+1:
            messages=[self.history[0]]+self.history[-n:]
        else:
            messages=self.history
        # 发送请求
        headers = {
            "Authorization": f"Bearer {plugin_config.api_key}", 
            "Content-Type": "application/json"
        }
        # 这里的 history 已经包含了新输入
        data = {
            "model": plugin_config.model, 
            "messages": messages, 
            "stream": False, 
            "temperature": plugin_config.temperature
        }

        try:
            res = requests.post(url=plugin_config.url, headers=headers, json=data, timeout=60)
            if res.status_code == 200:
                full_content = res.json()['choices'][0]['message']['content']
                cleaned = re.sub(r'<think>.*?</think>', '', full_content, flags=re.DOTALL).strip()
                
                # 记录 AI 回复并持久化
                self.history.append({'role': 'assistant', 'content': cleaned})
                self._save_memory() # 立即保存
                return cleaned
            
            return f"❌ API 错误: {res.status_code}"
        except Exception as e:
            return f"❌ 请求异常: {str(e)}"
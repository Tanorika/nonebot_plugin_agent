"""
LLM 客户端模块
负责记忆管理、任务注入、系统提示词生成等核心逻辑
API 请求逻辑已分离到 llm_api.py
"""
import os
import json
import re
from datetime import datetime
from ..config import Config
from nonebot import get_plugin_config
from .memory_manager import LongMemory,MemoryManager
from ..tools.skill_manager import SkillManager
from ..tools.task_manager import TaskManager
from .llm_api import LLMAPIClient
<<<<<<< HEAD
=======
from .memory_summarizer import ModelSummarizer
from .tag_parser import JsonResponseParser
from .memory_time import presentation
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

plugin_config = get_plugin_config(Config)

# 获取插件根目录并创建 memory 文件夹
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(PLUGIN_DIR, "memory")

class LLMClient:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory = MemoryManager(user_id)
<<<<<<< HEAD

    # _load_memory 和 _save_memory 保持原样，json.dump 会自动处理 vector 列表

    def chat(self, user_input: str, role: str = "user") -> str:
        # 0. 计算当前输入的向量
        current_vecs = self.memory.similarity_ctrl.get_vector(user_input)
        current_vec = current_vecs[0] if current_vecs else None

        # 1. 自动 RAG 检索
        rag_count = plugin_config.rag_count
        similar_memory = self.memory.similarity_ctrl.query_similar_history(
            self.memory.history, user_input, count=rag_count
        )
        
        rag_context = "\n".join([f"{m['content']}" for m in similar_memory]) if similar_memory else ""
=======
        if plugin_config.memory_tree_enabled:
            summary_client = LLMAPIClient(
                api_key=plugin_config.memory_tree_api_key or plugin_config.api_key,
                base_url=plugin_config.memory_tree_base_url or plugin_config.base_url,
                model=plugin_config.memory_tree_model or plugin_config.model,
            )
            self.memory.configure_tree(
                ModelSummarizer(summary_client, timeout=plugin_config.memory_tree_timeout),
                fanout=plugin_config.memory_tree_fanout,
                summary_chars=plugin_config.memory_tree_summary_chars,
            )

    # _load_memory 和 _save_memory 保持原样，json.dump 会自动处理 vector 列表

    def chat(self, user_input: str, role: str = "user", content_parts: list[dict] | None = None) -> str:
        # 0. 计算当前输入的向量
        current_vec = None
        # Memory is recalled explicitly through mem_rag. Automatic injection
        # caused unrelated history to pollute every prompt.
        rag_context = ""
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

        # 2. 常规组件加载
        skills_list = SkillManager.list_skills() 
        memory_text = self.memory.long_mem.load_all() # 从统一管理器调用长期记忆
        tm = TaskManager(self.user_id)
        
        # 3. 注入系统提示词 (注意引用路径)
        preset = plugin_config.preset.replace("{Skills}", SkillManager.list_skills()) \
                                    .replace("{tasks}", TaskManager(self.user_id).get_executing() or "自由待机") \
<<<<<<< HEAD
                                    .replace("{LongMemory}", self.memory.long_mem.load_all())
        
        if len(self.memory.history) > 0:
=======
                                    .replace("{LongMemory}", self.memory.long_mem.load_all()) \
                                    .replace("{scheduled_tasks}", tm.list_scheduled_tasks())

        if content_parts and any(p.get("type") == "image_url" for p in content_parts):
            preset += (
                "\n### 视觉输入规则：\n"
                "本轮用户消息已经附带真实图片。请直接使用你的视觉能力分析图片并回答，"
                "不要调用 image_recognition 技能，也不要让用户提供图片路径；除非图片无法读取，"
                "否则只需按用户问题正常回复。\n"
            )
        
        if self.memory.history and self.memory.history[0].get("role") == "system":
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
            self.memory.history[0] = {"role": "system", "content": preset}
        else:
            self.memory.history.insert(0, {"role": "system", "content": preset})

        # 4. 保存用户输入
<<<<<<< HEAD
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.memory.add_history(role, f"[{timestamp}] {user_input}", current_vec)
        
        # 5. 准备发送给 LLM 的消息 (修正变量名)
        n = plugin_config.max_history
        # 保证第一个是 system prompt，后面跟最近 n 条
        raw_messages = [self.memory.history[0]] + self.memory.history[-n:] if len(self.memory.history) > n + 1 else self.memory.history
        
        messages_for_llm = [{"role": m["role"], "content": m["content"]} for m in raw_messages]
        if rag_context:
            messages_for_llm.append({"role": "system", "content": f"【自动 RAG 记忆参考】：\n{rag_context}"})

=======
        self.memory.add_history(role, user_input, current_vec)
        
        # 5. 准备发送给 LLM 的消息 (修正变量名)
        n = max(1, plugin_config.memory_tree_recent_messages if plugin_config.memory_tree_enabled
                else plugin_config.max_history)
        conversation = [item for item in self.memory.history if item.get("role") != "system"]
        raw_messages = [self.memory.history[0]] + conversation[-n:]
        # Compute after saving the current input so summaries and the verbatim
        # tail share exactly the same boundary (no one-message gap each turn).
        tree_context = self.memory.memory_tree_context(
            max_chars=plugin_config.memory_tree_max_chars, recent_messages=n,
        ) if plugin_config.memory_tree_enabled else ""
        
        messages_for_llm = [
            {"role": m["role"], "content": self._format_message(m, raw_messages[index - 1] if index else None)}
            for index, m in enumerate(raw_messages)
        ]
        if tree_context:
            # Keep the tree out of the append-only history.  It is a derived
            # view and will be rebuilt if the raw conversation changes.
            messages_for_llm.insert(1, {"role": "user", "content": tree_context})
        # DeepSeek Vision follows the OpenAI multimodal message format. Only
        # attach images to the current user turn; keeping URLs out of memory
        # avoids persisting large/base64 payloads in the short-memory JSON.
        if content_parts:
            for message in reversed(messages_for_llm):
                if (message.get("role") == role and
                        (message.get("content", "") == user_input or
                         message.get("content", "").endswith("\n" + user_input))):
                    # Preserve the exact text/image ordering received from OneBot.
                    message["content"] = content_parts
                    break
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        # 6. 调用 API
        api_client = self._create_api_client()
        full_content = api_client.chat_completion(messages=messages_for_llm, stream=True)
        
        # 7. 清理并保存 AI 回复
        cleaned = re.sub(r'<think>.*?</think>', '', full_content, flags=re.DOTALL).strip()
<<<<<<< HEAD
=======
        parsed = JsonResponseParser.parse(cleaned)
        if parsed is not None:
            pending = parsed.get("pending_action", {})
            cleaned = json.dumps({
                "reply": parsed.get("reply", ""),
                "action": pending.get("action"),
                "params": pending.get("params", {})
            }, ensure_ascii=False)
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        ai_vecs = self.memory.similarity_ctrl.get_vector(cleaned)
        
        # 统一由 add_history 处理保存
        self.memory.add_history("assistant", f" {cleaned}", ai_vecs[0] if ai_vecs else None)
        
        return cleaned
<<<<<<< HEAD
=======

    @staticmethod
    def _format_message(item, previous=None):
        """Add temporal context only at the model presentation boundary."""
        content = item.get("content", "")
        created_at = item.get("created_at")
        if not created_at:
            return content
        previous_time = previous.get("created_at") if previous else None
        compact = presentation(created_at, previous_time)
        include_exact = previous_time is None or "个月" in compact or "年" in compact
        return f"【时间：{presentation(created_at, previous_time, include_exact=include_exact)}】\n{content}"
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
    
    def _create_api_client(self) -> LLMAPIClient:
        """
        创建 API 客户端实例
        
        Returns:
            LLMAPIClient 实例
        """
        api_key=plugin_config.api_key
        base_url=plugin_config.base_url
        model=plugin_config.model
        
        return LLMAPIClient(
            api_key=api_key,
            base_url=base_url,
            model=model
<<<<<<< HEAD
        )
=======
        )
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

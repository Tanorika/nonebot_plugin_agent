from typing import Dict, Any
from datetime import datetime
from nonebot.log import logger
from .llm_client import LLMClient
from ..tools.base_tools import BaseTools
from ..tools.skill_manager import SkillManager
from ..tools.task_manager import TaskManager
from .tag_parser import JsonResponseParser
from ..config import Config
from ..utils.message_sender import send_multimedia_message
from nonebot import get_plugin_config

plugin_config = get_plugin_config(Config)

class AgentExecutor:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.client = LLMClient(user_id) 
        self.memory = self.client.memory
        self.base = BaseTools()
        self.tm = TaskManager(user_id)
        self.skill = SkillManager()
        
        # 隐式动作基础列表（直接执行无需二次确认）
        self.silent_actions = [
            "base_read", "skill_detail", "mem_rag", "mem_expand", "mem_save", "mem_delete",
            "task_set", "task_finish", "task_schedule", "task_clear", "task_list", "task_cancel",
            "deepseek_search", "deepseek_fetch", "web_search"
        ]

    def is_silent(self, action_type: str, params: dict) -> bool:
        """判断当前动作是否可以直接执行而无需授权"""
        if action_type in self.silent_actions:
            return True
        if action_type == "base_exec":
            cmd = params.get("command", "").split()[0]
            if cmd in plugin_config.safe_commands:
                return True
        if action_type == "skill_exec":
            skill_name = params.get("name")
            if plugin_config.skill_safe_mode == 0:
                if skill_name not in plugin_config.blacklist_skills:
                    return True
            elif plugin_config.skill_safe_mode == 1:
                if skill_name in plugin_config.whitelist_skills:
                    return True
        return False

    async def run(self, user_input: str, matcher: Any, role: str = "user", content_parts: list[dict] | None = None) -> Dict[str, Any]:
        """
        Agent 决策中枢：引入 matcher 上下文，全面接管显隐式动作循环
        """
        current_input = user_input
        current_role = role

        # 核心循环：允许 AI 在后台自发工作最多 10 次
        for _ in range(10):
            ai_raw_res = self.client.chat(current_input, role=current_role, content_parts=content_parts)
            content_parts = None
            logger.info(f"[AGENT] Raw 回答: {ai_raw_res}")
            data = JsonResponseParser.parse(ai_raw_res)

            # 1. 如果解析失败，返回原始文本
            if not data:
                return {"reply": ai_raw_res, "pending_action": None}
            
            # 2. 提取回复内容
            reply_text = data.get("reply", "")
            action = data.get("pending_action", {}).get("action")
            params = data.get("pending_action", {}).get("params", {})
            
            # 3. 如果没有动作，直接返回回复
            if not action:
                return {"reply": reply_text, "pending_action": None}

            # 4. 判断是否为隐式/静默动作
            if self.is_silent(action, params):
                if reply_text and reply_text.strip():
                    logger.info(f"[AGENT] 发现隐式动作自带回复，正在发送: {reply_text}")
                    await send_multimedia_message(matcher, int(self.user_id), reply_text, is_finish=False)
                
                # 执行动作并拿到系统观测回显
                observation = await self._dispatch_action(action, params)
                obs_str = str(observation) if observation is not None else "✅ 动作已执行"
                logger.info(f"[AGENT] 执行隐式动作: {action} | 回显长度: {len(obs_str)}")

                if action == "task_schedule" and obs_str.startswith("✅"):
                    self.memory.add_history("user", f"【系统观测回显】：{obs_str}")
                    return {"reply": "", "pending_action": None, "suspended": True}
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                current_input = f"【系统观测回显】：\n[{timestamp}] {obs_str}"
                current_role = "user"
                continue

            # 5. 如果是显式动作 (Confirmed)，暂停并返回给外层等待用户授权
            return {
                "reply": reply_text or "正在申请执行权限...",
                "pending_action": data.get("pending_action", {})
            }

        return {"reply": "⚠️ 运行超时，未能在规定动作轮次内完成任务。", "pending_action": None, "error": "Agent 达到动作轮次上限"}

    async def _dispatch_action(self, action: str, params: Dict) -> str:
        """核心路由逻辑"""
        if action == "base_read": return self.base.read_file(params.get("path"))
        if action == "base_write": return self.base.write_file(params.get("path"), params.get("content"))
        if action == "base_modify": 
            return self.base.modify_file(
                params.get("path"),
                instruction=params.get("instruction"),
                line_number=params.get("line_number"),
                start_line=params.get("start_line"),
                end_line=params.get("end_line"),
                new_content=params.get("new_content"),
                search_text=params.get("search_text"),
                replace_text=params.get("replace_text")
            )
        if action == "base_exec": return self.base.execute_command(params.get("command"))
        if action == "mem_rag": return self.memory.mem_rag(
            params.get("target"), params.get("count"), params.get("mode", "hybrid"),
            params.get("expand"), params.get("window", 2), params.get("max_chars", 5000)
        )
        if action == "mem_expand": return self.memory.memory_tree_expand(
            params.get("node_id", ""), params.get("depth", 1), params.get("max_chars", 10000),
            params.get("offset", 0),
        )
        if action == "mem_save": return self.memory.long_mem.save(params.get("content", ""))
        if action == "mem_delete": return self.memory.long_mem.delete_by_index(params.get("index"))
        if action == "task_set":
            self.tm.set_executing(params.get("text", ""))
            return "✅ 任务已锁定，正在专注执行。"
        if action == "task_finish":
            self.tm.clear_executing()
            return "✅ 任务已标记完成。"
        if action == "task_schedule":
            message = params.get("message", "")
            delay = params.get("delay_seconds", 60)
            task_name = params.get("task_name")
            context = "\n".join(
                f"{item['role']}: {item['content']}"
                for item in self.memory.history[-10:] if item.get("role") != "system"
            )
            return self.tm.schedule_delayed_task(
                message, delay, task_name,
                callback_prompt=params.get("callback_prompt"), context=context,
            )
        if action == "task_cancel":
            task_id = params.get("task_id")
            if not task_id: return "❌ 错误：请提供任务ID (task_id)"
            return self.tm.cancel_scheduled_task(task_id)
        if action == "task_list": return self.tm.list_scheduled_tasks()
        if action == "task_clear": return self.tm.clear_scheduled_tasks()
        if action == "skill_detail": return self.skill.get_skill_detail(params.get("name"))
        if action == "skill_create":
            return self.skill.create_skill(params.get("name"), params.get("desc"), params.get("usage"), params.get("script"))
        if action == "skill_modify":
            return self.skill.modify_skill(params.get("name"), params.get("script"), params.get("usage"), params.get("desc"))
        if action == "skill_delete": return self.skill.delete_skill(params.get("name"))
        if action == "skill_exec": 
            skill_name = params.get("name")
            skill_params = {k: v for k, v in params.items() if k != "name"}
            return self.skill.execute_skill(skill_name, skill_params)
        if action in ("deepseek_search", "web_search"):
            from .deepseek_search import DeepSeekSearchClient
            client = DeepSeekSearchClient()
            return client.search_and_format(
                query=params.get("query", ""),
                count=int(params.get("count", 5)),
                ori_question=params.get("ori_question"),
                need_content=bool(params.get("need_content", False)),
                localization=params.get("localization", "")
            )
        if action == "deepseek_fetch":
            from .deepseek_search import DeepSeekSearchClient
            client = DeepSeekSearchClient()
            return client.fetch_and_format(
                url=params.get("url", ""),
                max_chars=int(params.get("max_chars", 4000))
            )

        return f"❌ 未知的动作类型: {action}"

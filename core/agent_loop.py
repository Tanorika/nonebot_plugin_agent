import json
import re
from typing import Dict, Any, Tuple, Optional
from .llm_client import LLMClient
from ..tools.base_tools import BaseTools
from ..tools.skill_manager import SkillManager
from .memory_manager import LongMemory

class AgentExecutor:
    def __init__(self, user_id: str):
        self.client = LLMClient(user_id) # 传入用户ID
        self.base = BaseTools()
        self.skill = SkillManager()
        self.long_mem = LongMemory(user_id)
        
        # 隐式动作列表：这些动作完成后直接回传给 AI，不干扰用户
        self.silent_actions = ["base_read", "skill_list", "skill_detail","mem_save","mem_delete"]

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """提取并解析 JSON """
        try:
            json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            json_str = json_match.group(1) if json_match else text
            return json.loads(json_str.strip())
        except:
            return None

    async def run(self, user_input: str, role: str = "user") -> Dict[str, Any]:
        """
        Agent 决策中枢：处理用户的话或系统回显，直到产生最终回复或需要 Y/N
        """
        current_input = user_input
        current_role = role

        # 核心循环：允许 AI 在后台自发工作最多 5 次
        for _ in range(5):
            ai_raw_res = self.client.chat(current_input, role=current_role)
            data = self._parse_json(ai_raw_res)

            # 1. 如果解析不出 JSON，说明是普通对话，直接结束
            if not data or "action" not in data:
                return {"reply": ai_raw_res, "pending_action": None}

            action = data.get("action")
            params = data.get("params", {})

            # 2. 如果是隐式动作 (Silent)，执行后递归/循环，不打扰用户
            if action in self.silent_actions:
                observation = await self._dispatch_action(action, params)
                current_input = f"【系统观测回显】：\n{observation}"
                current_role = "user" # 以用户视角喂回结果
                continue

            # 3. 如果是显式动作 (Confirmed)，暂停并返回，等待 Y/N
            return {
                "reply": data.get("reply", data.get("thought", "正在申请执行权限...")),
                "pending_action": data
            }

        return {"reply": "运行超时，可能是 AI 出错了。", "pending_action": None}

    async def _dispatch_action(self, action: str, params: Dict) -> str:
        """
        核心路由逻辑
        """
        # Base 能力
        if action == "base_read": return self.base.read_file(params.get("path"))
        if action == "base_write": return self.base.write_file(params.get("path"), params.get("content"))
        if action == "base_exec": return self.base.execute_command(params.get("command"))
        if action == "mem_save": return self.long_mem.save(params.get("content",""))
        if action == "mem_delete":return self.long_mem.delete_by_index(params.get("index"))
        
        # Skill 能力
        if action == "skill_list": return self.skill.list_skills()
        if action == "skill_detail": return self.skill.get_skill_detail(params.get("name"))
        if action == "skill_create":
            return self.skill.create_skill(params.get("name"), params.get("desc"), params.get("usage"), params.get("script"))
        if action == "skill_modify":
            return self.skill.modify_skill(params.get("name"), params.get("script"), params.get("usage"), params.get("desc"))
        if action == "skill_delete": return self.skill.delete_skill(params.get("name"))

        return f"❌ 未知的动作类型: {action}"
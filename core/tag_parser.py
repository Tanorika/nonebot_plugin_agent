<<<<<<< HEAD
import re
import json
from typing import Dict, Any, Optional

class TagParser:
    @staticmethod
    def extract_tag(text: str, tag_name: str, default: str = "") -> Optional[str]:
        """提取标签内容，如 [REPLY]内容[/REPLY]"""
        pattern = f"\\[{tag_name}\\](.*?)\\[/{tag_name}\\]"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            return content if content else None
        return None

    @classmethod
    def parse(cls, text: str) -> Optional[Dict[str, Any]]:
        """将标签文本转为 AgentExecutor 可理解的字典"""
        # 提取各个部分
        thought = cls.extract_tag(text, "THOUGHT")
        reply = cls.extract_tag(text, "REPLY")
        action = cls.extract_tag(text, "ACTION")
        params_raw = cls.extract_tag(text, "PARAMS")

        # 如果没有有效的标签内容，返回 None
        if not (thought or reply or action):
            return None

        # 处理参数：Params 内部依然建议保留简单的 JSON 结构或键值对
        params = {}
        if params_raw:
            try:
                # 尝试解析为 JSON
                params = json.loads(params_raw)
            except json.JSONDecodeError:
                # 如果不是 JSON，尝试简单的 key=value 行解析
                for line in params_raw.split('\n'):
                    line = line.strip()
                    if '=' in line:
                        k, v = line.split('=', 1)
                        params[k.strip()] = v.strip()

        return {
            "thought": thought,
            "reply": reply,
            "pending_action": {
                "action": action if action else None,
                "params": params
            }
        }
=======
import json
import re
from typing import Dict, Any, Optional

class JsonResponseParser:
    @classmethod
    def parse(cls, text: str) -> Optional[Dict[str, Any]]:
        """Parse the strict JSON response contract."""
        if not text or not text.strip():
            return None
        raw = text.strip()
        payload = None
        # Models sometimes prepend commentary or emit an action object after
        # the conversational text. Scan balanced JSON values and prefer the
        # last complete response-contract object in that mixed output.
        decoder = json.JSONDecoder()
        candidates = []
        action_only_candidates = []
        for match in re.finditer(r"\{", raw):
            try:
                value, _ = decoder.raw_decode(raw[match.start():])
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if isinstance(value, dict) and {"reply", "action", "params"}.issubset(value):
                candidates.append(value)
            elif isinstance(value, dict) and {"action", "params"}.issubset(value):
                # Some models put the conversational text before a standalone
                # action object instead of using the full response contract.
                # Keep the object's offset so the text can be recovered as the
                # user-visible reply without leaking the JSON payload.
                action_only_candidates.append((match.start(), value))
        if candidates:
            payload = candidates[-1]
        elif action_only_candidates:
            action_start, action_payload = action_only_candidates[-1]
            payload = {
                "reply": raw[:action_start].strip(),
                "action": action_payload.get("action"),
                "params": action_payload.get("params"),
            }
        else:
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                return None
        if not isinstance(payload, dict):
            return None
        reply = payload.get("reply", "")
        action = payload.get("action")
        params = payload.get("params", {})
        if action is not None and not isinstance(action, str):
            return None
        if not isinstance(params, dict):
            return None
        return {
            "reply": str(reply or ""),
            "pending_action": {"action": action or None, "params": params}
        }
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

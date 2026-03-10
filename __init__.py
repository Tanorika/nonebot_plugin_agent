import re
import os
import asyncio
from typing import Dict, Any
from nonebot import on_message, get_plugin_config
from nonebot.log import logger  # 引入 NoneBot 官方控制台日志
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.exception import FinishedException, PausedException, RejectedException
from nonebot.matcher import Matcher
from nonebot.rule import to_me
from nonebot.typing import T_State
import json

# 导入我们重构后的核心模块
from .core.agent_loop import AgentExecutor
from .config import Config

plugin_config = get_plugin_config(Config)

# 注册消息处理器
reply = on_message(priority=99, rule=to_me())

# 全局会话字典
# 结构: {"user_id": {"executor": AgentExecutor, "pending_action": dict}}
sessions: Dict[str, Dict[str, Any]] = {}

# 路径定义
plugin_dir = os.path.dirname(__file__)
sticker_base_dir = os.path.join(plugin_dir, "stickers")
index_path = os.path.join(sticker_base_dir, "stickers.json")


async def smart_split_send(matcher: Matcher,full_text: str, is_finish: bool = True):
    """
    全类型自适应分段发送器
    """
    pattern = r'\[(IMG|VOICE|VIDEO|FACE|STICKER):(.*?)\]'
    cursor = 0
    matches = list(re.finditer(pattern, full_text))

    try:
        for match in matches:
            # 1. 发送标签前的文字
            text_before = full_text[cursor:match.start()].strip()
            if text_before:
                await matcher.send(MessageSegment.text(text_before))
                await asyncio.sleep(0.2)
                
            # 2. 解析标签内容
            m_type = match.group(1)
            m_val = match.group(2).strip()
            
            # 路径类处理逻辑 (保持不变...)
            if m_type in ["IMG", "VOICE", "VIDEO", "FILE","STICKER"]:
                path = ""
                if m_type == "STICKER":
                    try:
                        if os.path.exists(index_path):
                            with open(index_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                # 在 stickers.json 列表中查找匹配 id 的项
                                sticker_item = next((s for s in data.get("stickers", []) if s["id"] == m_val), None)
                                if sticker_item:
                                    # 拼接绝对路径
                                    path = os.path.join(sticker_base_dir, sticker_item["file"])
                                else:
                                    logger.warning(f"[Agent] 未找到 ID 为 {m_val} 的表情包")
                        else:
                            logger.error(f"[Agent] 表情包索引文件不存在: {index_path}")
                    except Exception as e:
                        logger.error(f"[Agent] 解析表情包索引失败: {e}")
                else:
                    # 原有的 IMG/VOICE 等路径处理
                    path = m_val.replace("\\", "/")
                if not path.startswith(("http", "file")):
                    path = f"file:///{path}"
                if m_type == "IMG": await matcher.send(MessageSegment.image(path))
                elif m_type == "VOICE": await matcher.send(MessageSegment.record(path))
                elif m_type == "VIDEO": await matcher.send(MessageSegment.video(path))
                elif m_type == "FILE": await matcher.send(MessageSegment("file", {"file": path, "name": os.path.basename(m_val)}))
                elif m_type == "STICKER": await matcher.send(MessageSegment.image(path))
            
            cursor = match.end()

        remaining = full_text[cursor:].strip()
        if is_finish:
            # 这里的 finish 会抛出 FinishedException
            await matcher.finish(MessageSegment.text(remaining) if remaining else None)
        else:
            # 这里的 pause 会抛出 PausedException
            await matcher.pause(MessageSegment.text(remaining) if remaining else None)

    except (FinishedException, PausedException, RejectedException):
        raise 
    except Exception as e:
        logger.error(f"[Agent] 发送链路崩溃：{e}")
        # 这里用 send 而不是 finish，避免二次触发异常
        await matcher.send(f"❌ 发送消息时发生错误：{str(e)}")

@reply.handle()
async def main_entry(matcher: Matcher, event: MessageEvent, state: T_State):
    user_id = str(event.get_user_id())
    user_msg = str(event.get_message()).strip()
    clean_msg = re.sub(r"\[CQ:at,qq=\d+\]", "", user_msg).strip()

    if not clean_msg:
        return

    # 1. 检查用户是否处于“等待 Y/N 确认”的状态
    if user_id in sessions and sessions[user_id].get("pending_action"):
        confirm = clean_msg.upper()
        pending_action = sessions[user_id]["pending_action"]
        executor = sessions[user_id]["executor"]
        
        if confirm == "Y":
            # 清除等待状态
            sessions[user_id]["pending_action"] = None
            logger.info(f"[Agent] 用户 {user_id} 授权执行动作: {pending_action['action']}")
            await matcher.send("📦 正在执行...")
            
            # 显式调用执行
            try:
                observation = await executor._dispatch_action(
                    pending_action["action"], 
                    pending_action["params"]
                )
                logger.info(f"[Agent] 动作执行完毕，回显长度: {len(observation)}")
                
                # 将结果喂回 Agent
                feedback_msg = f"【系统观测回显】：\n{observation}"
                await run_agent_loop(matcher, user_id, feedback_msg)
            except (FinishedException, PausedException, RejectedException):
                raise 
            except Exception as e:
                logger.error(f"[Agent] 动作执行崩溃: {e}")
                sessions.pop(user_id, None)
                await matcher.send(f"❌ 运行崩溃：{str(e)}")
            return
            
        elif confirm == "N":
            logger.info(f"[Agent] 用户 {user_id} 拒绝了动作执行。")
            sessions.pop(user_id, None)
            await matcher.finish("好的，任务已取消。")
            return
        else:
            logger.warning(f"[Agent] 用户 {user_id} 在等待授权时输入了无效指令: {clean_msg}")
            await matcher.finish("请输入 Y 允许或 N 拒绝！（本次任务已取消）")
            return

    # 2. 如果不是等待状态，则作为全新的对话处理
    logger.info(f"[Agent] 用户 {user_id} 开启了新一轮 Agent 任务。")
    sessions[user_id] = {
        "executor": AgentExecutor(user_id=user_id),
        "pending_action": None
    }
    
    await run_agent_loop(matcher, user_id, clean_msg)


async def run_agent_loop(matcher: Matcher, user_id: str, input_text: str):
    """
    Agent 执行闭环
    """
    executor: AgentExecutor = sessions[user_id]["executor"]
    
    try:
        logger.debug(f"[Agent] Agent 开始思考，输入文本: {input_text[:50]}...")
        result = await executor.run(input_text)
        
        reply_text = result["reply"]
        pending_action = result["pending_action"]
        
        # 拦截错误动作
        if pending_action and pending_action.get("action") == "error":
            logger.error(f"[Agent] Agent 输出 JSON 异常: {pending_action}")
            sessions.pop(user_id, None)
            await matcher.send(f"❌ Agent 响应异常：\n{pending_action.get('params', {}).get('message')}")
            return

        # 如果有需要确认的动作
        if pending_action and pending_action.get("action"):
            action_type = pending_action["action"]
            params = pending_action.get("params", {})
            is_safe = False
            if action_type == "base_exec":
                cmd = params.get("command", "").strip().lower()
                # 检查命令是否以白名单中的任何一个开头
                if any(cmd.startswith(safe_cmd.lower()) for safe_cmd in plugin_config.safe_commands):
                    is_safe = True
            if is_safe:
                logger.info(f"[Agent] 匹配到安全指令: {params.get('command')}，自动执行中...")
                observation = await executor._dispatch_action(action_type, params)
                # 执行完后，把结果当做新的输入重新喂给 Agent，让它继续组织语言回复
                await run_agent_loop(matcher, user_id, f"【系统观测回显】：\n{observation}")
                return
            
            # 保存到全局 Session 中锁定状态
            sessions[user_id]["pending_action"] = pending_action
            logger.info(f"[Agent] Agent 挂起，等待授权: {action_type} - {params}")
            
            # 构建 UI
            task_desc = ""
            if action_type == "base_exec":
                task_desc = f"指令：{params.get('command')}"
            elif action_type == "base_write":
                task_desc = f"写入：{params.get('path')}"
            elif action_type == "skill_create":
                task_desc = f"技能：{params.get('name')}"
            else:
                task_desc = f"{action_type}"

            prompt = f"{reply_text}\n\n🛠️ **Agent 想要执行：**\n{task_desc}\n---\n确认执行吗？(Y/N)"
            await smart_split_send(matcher, prompt)
            
        else:
            # 任务闭环完成，清理 Session
            logger.success(f"[Agent] Agent 任务结束，返回最终回复。")
            sessions.pop(user_id, None)
            await smart_split_send(matcher, reply_text)
    except (FinishedException, PausedException, RejectedException):
            raise 
    except Exception as e:
        logger.error(f"[Agent] run_agent_loop 崩溃: {str(e)}")
        sessions.pop(user_id, None)
        await matcher.send(f"❌ 思考过程异常：{str(e)}")
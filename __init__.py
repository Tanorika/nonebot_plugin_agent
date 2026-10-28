import re
import os
import base64
import mimetypes
import time
import requests
import asyncio
from typing import Dict, Any
from nonebot import on_message, get_plugin_config, get_driver, get_bots
from nonebot.log import logger  
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.exception import FinishedException, PausedException, RejectedException
from nonebot.matcher import Matcher
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me
from nonebot.typing import T_State

from .core.agent_loop import AgentExecutor
from .config import Config
from .utils.message_sender import send_multimedia_message
from .core.message_batcher import MessageBatch, MessageBatcher, MessagePart
from .tools.task_manager import TaskManager

__plugin_meta__ = PluginMetadata(
    name="Agent",
    description="基于大语言模型、记忆树与自主工具调用的通用智能体插件",
    usage="在群聊中 @机器人 或私聊直接发送消息，支持工具调用、长任务规划与记忆检索",
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

plugin_config = get_plugin_config(Config)
reply = on_message(priority=99, rule=to_me())
sessions: Dict[str, Dict[str, Any]] = {}
message_batcher = MessageBatcher()
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_TEMP_DIR = os.path.join(PLUGIN_DIR, "temp", "images")
user_locks: Dict[str, asyncio.Lock] = {}
scheduled_worker: asyncio.Task | None = None


def user_lock(user_id: str) -> asyncio.Lock:
    return user_locks.setdefault(user_id, asyncio.Lock())


async def resume_scheduled_tasks():
    # 仅在启动时恢复中断的任务
    for user_id in TaskManager.user_ids():
        TaskManager(user_id).recover_interrupted_tasks()
    while True:
        await asyncio.sleep(1)
        bot = next((candidate for candidate in get_bots().values() if isinstance(candidate, Bot)), None)
        if bot is None:
            continue
        for user_id in TaskManager.user_ids():
            try:
                if user_id in sessions or user_lock(user_id).locked():
                    continue
                async with user_lock(user_id):
                    manager = TaskManager(user_id)
                    due = manager.get_due_tasks()
                    if not due:
                        continue
                    task_id, info = due[0]
                    executor = AgentExecutor(user_id)
                    sessions[user_id] = {
                        "executor": executor, "pending_action": None, "task_id": task_id,
                    }
                    manager.update_status(task_id, "running")
                    instruction = info.get("callback_prompt")
                    if instruction is None:
                        instruction = f"请向用户发送以下提醒：{info.get('message', '')}"
                    event = (
                        f"【系统事件：挂起任务到期】\n任务 ID：{task_id}\n"
                        f"计划恢复时间：{info['scheduled_time']}\n"
                        f"挂起时的上下文（历史记录，仅作参考）：\n{info.get('context', '')}\n"
                        f"请结合当前对话上下文恢复任务，继续使用正常的动作和授权流程。\n"
                        f"恢复指令：{instruction}"
                    )
                    await run_agent_loop(bot, user_id, event, role="system")
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.error(f"[AGENT] 恢复用户 {user_id} 的挂起任务失败: {error}")
                session = sessions.pop(user_id, None)
                if session and session.get("task_id"):
                    session["executor"].tm.update_status(session["task_id"], "failed", str(error))


@get_driver().on_startup
async def start_scheduled_worker():
    global scheduled_worker
    scheduled_worker = asyncio.create_task(resume_scheduled_tasks())


@get_driver().on_shutdown
async def stop_scheduled_worker():
    if scheduled_worker:
        scheduled_worker.cancel()
        try:
            await scheduled_worker
        except asyncio.CancelledError:
            pass


def _detect_image_mime(raw: bytes) -> str | None:
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def _image_segment_data_url(value: str) -> str | None:
    """下载并保存图片到本地临时目录，返回兼容的 data URL。"""
    if not value:
        return None
    os.makedirs(IMAGE_TEMP_DIR, exist_ok=True)
    source_name = value.split("?", 1)[0].split("/", 1)[-1] or "image.jpg"
    mime = mimetypes.guess_type(source_name)[0] or "image/jpeg"
    try:
        if value.startswith("data:"):
            header, encoded = value.split(",", 1)
            mime = header[5:].split(";", 1)[0] or mime
            raw = base64.b64decode(encoded)
        else:
            path = value[7:] if value.startswith("file://") else value
            if os.path.isfile(path):
                with open(path, "rb") as image_file:
                    raw = image_file.read()
            elif value.startswith(("http://", "https://")):
                response = requests.get(
                    value,
                    headers={"User-Agent": "Mozilla/5.0", "Accept": "image/*"},
                    timeout=(5, 30),
                )
                response.raise_for_status()
                raw = response.content
                mime = response.headers.get("Content-Type", "").split(";", 1)[0] or mime
            else:
                return None
        if not raw or len(raw) > 32 * 1024 * 1024:
            logger.warning("[AGENT] 图片为空或超过 32 MiB 限制")
            return None
        detected_mime = _detect_image_mime(raw)
        if not detected_mime:
            logger.warning("[AGENT] 下载内容不是支持的 JPEG/PNG/GIF/WebP 图片")
            return None
        mime = detected_mime
        suffix = mimetypes.guess_extension(mime) or ".jpg"
        temp_path = os.path.join(IMAGE_TEMP_DIR, f"{int(time.time() * 1000)}{suffix}")
        with open(temp_path, "wb") as temp_file:
            temp_file.write(raw)
        with open(temp_path, "rb") as temp_file:
            encoded = base64.b64encode(temp_file.read()).decode("ascii")
        logger.info(f"[AGENT] 图片已保存并编码: {temp_path} ({len(raw)} bytes, {mime})")
        return f"data:{mime};base64,{encoded}"
    except Exception as exc:
        logger.warning(f"[AGENT] 保存/读取图片失败: {exc}")
        return None


async def smart_split_send(matcher: Matcher, full_text: str, user_id: int, is_finish: bool = True):
    """自适应分段发送器（默认终结会话）"""
    await send_multimedia_message(matcher, user_id, full_text, is_finish)


@reply.handle()
async def main_entry(matcher: Matcher, event: MessageEvent, state: T_State):
    user_id = str(event.get_user_id())
    message_parts = []
    for segment in event.get_message():
        data = getattr(segment, "data", {}) or {}
        segment_type = getattr(segment, "type", None)
        if segment_type == "text":
            text = re.sub(r"\[CQ:at,qq=\d+\]", "", data.get("text", "")).strip()
            if text:
                message_parts.append(MessagePart.from_text(text))
        elif segment_type == "image":
            image_url = await asyncio.to_thread(
                _image_segment_data_url, data.get("url") or data.get("file")
            )
            if image_url:
                message_parts.append(MessagePart.from_image(image_url))
        elif segment_type == "face":
            message_parts.append(MessagePart.from_text("[用户发送了一个表情]"))

    if not message_parts:
        return

    clean_msg = "\n".join(
        part.text for part in message_parts if part.type == "text" and part.text
    ).strip()

    # 1. 检查用户是否处于“等待 Y/N 确认”的状态
    if user_id in sessions and sessions[user_id].get("pending_action"):
        confirm = clean_msg.upper()
        pending_action = sessions[user_id]["pending_action"]
        executor = sessions[user_id]["executor"]
        
        if confirm == "Y":
            sessions[user_id]["pending_action"] = None
            logger.info(f"[AGENT] 用户 {user_id} 授权执行动作: {pending_action['action']}")
            await matcher.send("📦 Agent 正在执行...")
            
            try:
                observation = await executor._dispatch_action(
                    pending_action["action"], 
                    pending_action["params"]
                )
                feedback_msg = f"【系统观测回显】：\n{observation}"
                await run_agent_loop(matcher, user_id, feedback_msg)
            except (FinishedException, PausedException, RejectedException):
                raise 
            except Exception as e:
                logger.error(f"[AGENT] 动作执行崩溃: {e}")
                task_id = sessions.get(user_id, {}).get("task_id")
                if task_id:
                    executor.tm.update_status(task_id, "failed", str(e))
                sessions.pop(user_id, None)
                await matcher.send(f"❌ 运行异常：{str(e)}")
            return
            
        elif confirm == "N":
            logger.info(f"[AGENT] 用户 {user_id} 拒绝了动作执行。")
            task_id = sessions.get(user_id, {}).get("task_id")
            if task_id:
                executor.tm.update_status(task_id, "cancelled")
            sessions.pop(user_id, None)
            await matcher.finish("好的，已取消本次执行。")
            return
        else:
            await matcher.send("请输入 Y 确认执行，或 N 取消执行。")
            return

    # 2. 普通聊天先交给独立聚合层，连续文字/图片会合并成一个对话轮次
    async def handle_batch(batch: MessageBatch) -> None:
        logger.info(
            f"[AGENT] 用户 {user_id} 消息聚合完成: "
            f"{len(batch.parts)} 个内容块, {batch.image_count} 张图片"
        )
        async with user_lock(user_id):
            if sessions.get(user_id, {}).get("pending_action"):
                await matcher.send("请先输入 Y 允许或 N 拒绝当前挂起的操作。")
                return
            sessions[user_id] = {
                "executor": AgentExecutor(user_id=user_id),
                "pending_action": None,
            }
            await run_agent_loop(
                matcher,
                user_id,
                batch.memory_text or "请描述你看到的图片。",
                batch.api_parts,
            )

    await message_batcher.submit(user_id, message_parts, handle_batch)


async def run_agent_loop(matcher: Matcher, user_id: str, input_text: str, content_parts: list[dict] | None = None, role: str = "user"):
    """Agent 执行闭环控制器"""
    executor: AgentExecutor = sessions[user_id]["executor"]
    
    try:
        logger.debug(f"[AGENT] Agent 开始思考，输入文本: {input_text[:50]}...")
        result = await executor.run(input_text, matcher, role=role, content_parts=content_parts)
        
        reply_text = result["reply"]
        pending_action = result["pending_action"]
        
        if pending_action and pending_action.get("action") == "error":
            logger.error(f"[AGENT] Agent 输出 JSON 异常: {pending_action}")
            task_id = sessions.get(user_id, {}).get("task_id")
            if task_id:
                executor.tm.update_status(task_id, "failed", str(pending_action))
            sessions.pop(user_id, None)
            await smart_split_send(matcher, f"❌ 输出解析异常：\n{pending_action.get('params', {}).get('message')}", int(user_id), is_finish=False)
            return

        # 需要显式 Y/N 授权的动作
        if pending_action and pending_action.get("action"):
            action_type = pending_action["action"]
            params = pending_action.get("params", {})
                    
            sessions[user_id]["pending_action"] = pending_action
            if sessions[user_id].get("task_id"):
                executor.tm.update_status(sessions[user_id]["task_id"], "awaiting_confirmation")
            logger.info(f"[AGENT] Agent 挂起，等待授权: {action_type} - {params}")
            
            task_desc = ""
            if action_type == "base_exec": task_desc = f"指令：{params.get('command')}"
            elif action_type == "base_write": task_desc = f"写入文件：{params.get('path')}"
            elif action_type == "skill_create": task_desc = f"创建技能：{params.get('name')}"
            else: task_desc = f"{action_type}"

            prompt = f"{reply_text}\n\n🛠️ **Agent 请求执行以下操作：**\n{task_desc}\n---\n确认执行吗？(Y/N)"
            await smart_split_send(matcher, prompt, int(user_id), is_finish=True)
            
        else:
            # 最终无动作，宣告闭环正常结束，清除临时 Session
            logger.success(f"[AGENT] Agent 任务结束，返回最终回复。")
            task_id = sessions.get(user_id, {}).get("task_id")
            if task_id:
                executor.tm.update_status(task_id, "failed" if result.get("error") else "completed", result.get("error"))
            sessions.pop(user_id, None)
            await smart_split_send(matcher, reply_text, int(user_id), is_finish=True)

    except (FinishedException, PausedException, RejectedException):
        raise 
    except Exception as e:
        logger.error(f"[AGENT] run_agent_loop 崩溃: {str(e)}")
        task_id = sessions.get(user_id, {}).get("task_id")
        if task_id:
            executor.tm.update_status(task_id, "failed", str(e))
        sessions.pop(user_id, None)
        await smart_split_send(matcher, f"❌ 思考过程发生异常：{str(e)}", int(user_id), is_finish=False)

"""
统一的消息发送工具模块
支持多媒体标签和分段控件
"""
import re
import os
import json
import asyncio
from typing import Union
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.matcher import Matcher
from nonebot.exception import FinishedException
from nonebot.log import logger


# 路径定义
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STICKER_BASE_DIR = os.path.join(PLUGIN_DIR, "stickers")
INDEX_PATH = os.path.join(STICKER_BASE_DIR, "stickers.json")


async def send_multimedia_message(
    sender: Union[Bot, Matcher],
    user_id: int,
    full_text: str,
    is_finish: bool = True
):
    """
    统一的消息发送函数
    支持 [SEND] 分段控件和多媒体标签
    
    Args:
        sender: Bot 对象或 Matcher 对象
        user_id: 用户ID
        full_text: 要发送的完整文本
        is_finish: 是否是最后一条消息
    """
    # 先处理 [SEND] 分段控件
    parts = full_text.split('[SEND]')
    
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        
        # 如果是最后一段，使用 finish，否则使用 send（保持对话）
        is_last_part = (i == len(parts) - 1)
        current_is_finish = is_finish and is_last_part
        
        # 处理当前分段中的多媒体标签
        await _send_segment(sender, user_id, part, current_is_finish)
        
        # 如果不是最后一段，等待一小段时间（模拟真人打字停顿）
        if not is_last_part:
            await asyncio.sleep(0.5)


async def _send_segment(
    sender: Union[Bot, Matcher],
    user_id: int,
    text: str,
    is_finish: bool = True
):
    """
    发送包含多媒体标签的段落
    以标签为单位挨个发送
    """
    pattern = r'\[(IMG|VOICE|VIDEO|FACE|STICKER|FILE):(.*?)\]'
    cursor = 0
    matches = list(re.finditer(pattern, text))

    try:
        for match in matches:
            # 1. 发送标签前的文字
            text_before = text[cursor:match.start()].strip()
            if text_before:
                await _send_text(sender, user_id, text_before)
                await asyncio.sleep(0.2)
                
            # 2. 解析标签内容
            m_type = match.group(1)
            m_val = match.group(2).strip()
            
            # 路径类处理逻辑
            if m_type in ["IMG", "VOICE", "VIDEO", "FILE", "STICKER"]:
                path = await _resolve_media_path(m_type, m_val)
                
                if path:
                    # 构建消息段（恢复旧版本的简单逻辑）
                    if m_type == "IMG": 
                        msgsegment = MessageSegment.image(path)
                    elif m_type == "VOICE": 
                        msgsegment = MessageSegment.record(path)
                    elif m_type == "VIDEO": 
                        msgsegment = MessageSegment.video(path)
                    elif m_type == "FILE":
                        msgsegment = MessageSegment("file", {"file": path, "name": os.path.basename(m_val)})
                    elif m_type == "STICKER": 
                        msgsegment = MessageSegment.image(path)
                    
                    # 发送消息段
                    await _send_media(sender, user_id, msgsegment)
                    await asyncio.sleep(0.2)
            
            cursor = match.end()

        # 发送剩余的文字
        remaining = text[cursor:].strip()
        if remaining:
            if is_finish:
                await _finish(sender, user_id, remaining)
            else:
                await _send_text(sender, user_id, remaining)
        elif is_finish:
            # 如果没有剩余文字但是需要 finish
            await _finish(sender, user_id, None)

    except FinishedException:
        # FinishedException 是 NoneBot 的正常行为，用于结束匹配器
        # 直接 raise，不要处理
        raise
    except Exception as e:
        logger.error(f"[AGENT] 发送链路崩溃：{e}")
        # 发送错误提示
<<<<<<< HEAD
        error_msg = f"发送消息时出错: {str(e)}"
=======
        error_msg = f"❌ 发送消息时发生异常：{str(e)}"
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        await _send_text(sender, user_id, error_msg)


async def _resolve_media_path(m_type: str, m_val: str) -> str:
    """
    解析多媒体标签的路径
    
    Args:
        m_type: 多媒体类型 (IMG, VOICE, VIDEO, FILE, STICKER)
        m_val: 多媒体值 (路径或 ID)
    
    Returns:
        解析后的路径
    """
    path = ""
    
    if m_type == "STICKER":
        try:
            if os.path.exists(INDEX_PATH):
                with open(INDEX_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 在 stickers.json 列表中查找匹配 id 的项
                    sticker_item = next(
                        (s for s in data.get("stickers", []) if s["id"] == m_val),
                        None
                    )
                    if sticker_item:
                        # 拼接绝对路径
                        path = os.path.join(STICKER_BASE_DIR, sticker_item["file"])
                    else:
                        logger.warning(f"[AGENT] 未找到 ID 为 {m_val} 的表情包")
            else:
                logger.error(f"[AGENT] 表情包索引文件不存在: {INDEX_PATH}")
        except Exception as e:
            logger.error(f"[AGENT] 解析表情包索引失败: {e}")
    else:
        # 原有的 IMG/VOICE/VIDEO/FILE 路径处理
        path = m_val.replace("\\", "/")
    
    # 添加 file:// 协议（如果需要）- 恢复旧版本逻辑
    if path and not path.startswith(("http", "file")):
        path = f"file:///{path}"
    
    return path


async def _send_text(sender: Union[Bot, Matcher], user_id: int, text: str):
    """
    发送文本消息
    """
    if isinstance(sender, Bot):
        # 使用 Bot API 发送
        await sender.call_api(
            "send_private_msg",
            user_id=user_id,
            message=text
        )
    else:
        # 使用 Matcher 发送
        await sender.send(MessageSegment.text(text))


async def _send_media(sender: Union[Bot, Matcher], user_id: int, msgsegment: MessageSegment):
    """
    发送多媒体消息
    """
    if isinstance(sender, Bot):
        # 使用 Bot API 发送（序列化消息段）
        await sender.call_api(
            "send_private_msg",
            user_id=user_id,
            message=str(msgsegment)
        )
    else:
        # 使用 Matcher 发送
        await sender.send(msgsegment)


async def _finish(sender: Union[Bot, Matcher], user_id: int, text: str = None):
    """
    完成消息发送（仅在 Matcher 模式下使用）
    """
    if isinstance(sender, Bot):
        # Bot 模式下直接发送
        if text:
            await sender.call_api(
                "send_private_msg",
                user_id=user_id,
                message=text
            )
    else:
        # Matcher 模式下使用 finish
        if text:
            await sender.finish(MessageSegment.text(text))
        else:
            await sender.finish()

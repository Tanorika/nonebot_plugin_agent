"""消息聚合层。

把用户连续发送的文字、图片和表情整理成一个对话轮次，再交给 Agent。
该模块不依赖 NoneBot，便于单独关闭或回退到逐条处理。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal


@dataclass(frozen=True)
class MessagePart:
    type: Literal["text", "image_url"]
    text: str | None = None
    url: str | None = None

    @classmethod
    def from_text(cls, text: str) -> "MessagePart":
        return cls(type="text", text=text)

    @classmethod
    def from_image(cls, url: str) -> "MessagePart":
        return cls(type="image_url", url=url)

    def to_api_block(self) -> dict[str, Any]:
        if self.type == "image_url":
            return {"type": "image_url", "image_url": {"url": self.url}}
        return {"type": "text", "text": self.text or ""}

    def to_memory_text(self) -> str:
        return self.text or "[用户发送了一张图片]"


@dataclass
class MessageBatch:
    user_id: str
    parts: list[MessagePart] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(
            part.text for part in self.parts
            if part.type == "text" and part.text
        ).strip()

    @property
    def memory_text(self) -> str:
        return "\n".join(part.to_memory_text() for part in self.parts).strip()

    @property
    def api_parts(self) -> list[dict[str, Any]]:
        return [part.to_api_block() for part in self.parts]

    @property
    def image_count(self) -> int:
        return sum(part.type == "image_url" for part in self.parts)


@dataclass
class _Pending:
    batch: MessageBatch
    callback: Callable[[MessageBatch], Awaitable[None]]
    task: asyncio.Task | None = None
    started_at: float = 0.0
    acknowledgement_sent: bool = False


class MessageBatcher:
    """按用户聚合消息，采用可回退的异步防抖策略。"""

    def __init__(
        self,
        quiet_seconds: float = 8.0,
        max_wait_seconds: float = 45.0,
        on_ack: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self.quiet_seconds = quiet_seconds
        self.max_wait_seconds = max_wait_seconds
        self.on_ack = on_ack
        self._pending: dict[str, _Pending] = {}

    async def submit(
        self,
        user_id: str,
        parts: list[MessagePart],
        callback: Callable[[MessageBatch], Awaitable[None]],
    ) -> None:
        loop = asyncio.get_running_loop()
        pending = self._pending.get(user_id)
        if pending is None:
            pending = _Pending(
                batch=MessageBatch(user_id=user_id),
                callback=callback,
                started_at=loop.time(),
            )
            self._pending[user_id] = pending

        pending.batch.parts.extend(parts)

        if pending.task and not pending.task.done():
            pending.task.cancel()
        elapsed = loop.time() - pending.started_at
        delay = max(0.0, min(self.quiet_seconds, self.max_wait_seconds - elapsed))
        pending.task = asyncio.create_task(self._flush_after(user_id, delay))

    async def _flush_after(self, user_id: str, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            pending = self._pending.pop(user_id, None)
            if pending is None:
                return
            await pending.callback(pending.batch)
        except asyncio.CancelledError:
            return

    async def flush(self, user_id: str) -> None:
        """立即发送某用户的待处理批次。"""
        pending = self._pending.pop(user_id, None)
        if pending is None:
            return
        if pending.task and not pending.task.done():
            pending.task.cancel()
        await pending.callback(pending.batch)

    def cancel(self, user_id: str) -> None:
        pending = self._pending.pop(user_id, None)
        if pending and pending.task and not pending.task.done():
            pending.task.cancel()

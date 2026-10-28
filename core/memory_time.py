"""Time metadata and human-readable presentation for conversation memory."""

from __future__ import annotations

from datetime import datetime
import re


LEGACY_TIMESTAMP = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*")


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize(item: dict, timestamp: str | None = None) -> dict:
    """Move legacy leading timestamps out of message content."""
    result = dict(item)
    content = str(result.get("content", ""))
    created_at = result.get("created_at") or timestamp
    if not created_at:
        match = LEGACY_TIMESTAMP.match(content)
        if match:
            created_at = match.group(1).replace(" ", "T")
            content = content[match.end():]
    result["content"] = content
    result["created_at"] = str(created_at or "")
    return result


def parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed.astimezone()


def exact(value: str) -> str:
    parsed = parse(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S %z") if parsed else value


def interval(previous: str | None, current: str) -> str:
    if not previous:
        return "会话开始"
    before, after = parse(previous), parse(current)
    if not before or not after:
        return "时间间隔未知"
    seconds = max(0, int((after - before).total_seconds()))
    if seconds < 60:
        return f"约 {seconds} 秒"
    if seconds < 3600:
        return f"约 {seconds // 60} 分钟"
    if seconds < 86400:
        return f"约 {seconds // 3600} 小时 {seconds % 3600 // 60} 分钟"
    days = seconds // 86400
    if days < 60:
        return f"约 {days} 天"
    months = days // 30
    if months < 24:
        return f"约 {months} 个月"
    return f"约 {days // 365} 年"


def label(created_at: str, previous: str | None = None) -> str:
    parsed = parse(created_at)
    readable = parsed.strftime("%Y年%m月%d日 %H:%M") if parsed else created_at
    return f"{readable}（精确时间 {exact(created_at)}；距上一条{interval(previous, created_at)}）"


def presentation(created_at: str, previous: str | None = None,
                 *, include_exact: bool = False) -> str:
    """Compact temporal context for prompts; storage keeps the exact value."""
    parsed = parse(created_at)
    if parsed is None:
        return created_at or "时间未知"
    previous_parsed = parse(previous) if previous else None
    gap = interval(previous, created_at)
    if previous_parsed and gap in {"约 0 秒", "约 1 秒"}:
        readable = "刚才"
    elif previous_parsed and parsed.date() == previous_parsed.date():
        readable = f"今天 {parsed:%H:%M}"
    else:
        readable = parsed.strftime("%Y年%m月%d日 %H:%M")
    if previous:
        readable += f"（距上一条{gap}）"
    if include_exact:
        readable += f"（精确时间 {exact(created_at)}）"
    return readable


def range_label(start: str, end: str) -> str:
    """Describe a node's covered period without repeating raw timestamps."""
    first, last = parse(start), parse(end)
    if not first or not last:
        return f"时间范围：{start or '未知'} 至 {end or '未知'}"
    if first.date() == last.date():
        span = f"{first:%Y年%m月%d日} {first:%H:%M}—{last:%H:%M}"
    else:
        span = f"{first:%Y年%m月%d日 %H:%M}—{last:%Y年%m月%d日 %H:%M}"
    duration = interval(start, end) if first != last else "约 0 秒"
    return f"时间范围：{span}（持续{duration}）"


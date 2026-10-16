"""
General helper utilities for AEGIS ULTIMATE ESPORTS BOT.
"""

from __future__ import annotations

import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import discord


def utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def generate_case_id(prefix: str = "CASE") -> str:
    """Generate a short unique case / ticket / reference ID."""
    alphabet = string.ascii_uppercase + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{prefix}-{random_part}"


def generate_token(length: int = 32) -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(length)


def parse_duration(duration_str: str) -> Optional[timedelta]:
    """
    Parse a human-readable duration string into a timedelta.
    Supports: 30s, 5m, 2h, 1d, 1w
    Returns None if invalid.
    """
    duration_str = duration_str.strip().lower()
    match = re.fullmatch(r"(\d+)(s|m|h|d|w)", duration_str)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return timedelta(seconds=value)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    if unit == "w":
        return timedelta(weeks=value)
    return None


def format_duration(delta: timedelta) -> str:
    """Convert a timedelta into a human-readable string."""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return "0s"

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


def format_uptime(seconds: float) -> str:
    """Format bot uptime in a readable way."""
    return format_duration(timedelta(seconds=int(seconds)))


def truncate(text: str, max_length: int = 1024, suffix: str = "...") -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def escape_markdown(text: str) -> str:
    """Escape Discord markdown characters."""
    escape_chars = r"\*_`\~|>"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def get_member_display(member: Union[discord.Member, discord.User]) -> str:
    """Return a consistent display string for a user/member."""
    return f"{member} (`{member.id}`)"


def chunk_list(items: list, size: int) -> list[list]:
    """Split a list into chunks of given size."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def is_valid_url(url: str) -> bool:
    """Basic URL validation (does not fetch the URL)."""
    pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(pattern.match(url))


def clean_reason(reason: Optional[str], max_length: int = 512) -> str:
    """Normalize and truncate a moderation reason."""
    if not reason or not reason.strip():
        return "No reason provided"
    return truncate(reason.strip(), max_length)

"""
Standard embed builders for AEGIS ULTIMATE ESPORTS BOT.
Consistent colors and styling across the entire bot.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord


# Brand colors
COLOR_SUCCESS = 0x2ECC71   # Green
COLOR_ERROR = 0xE74C3C     # Red
COLOR_WARNING = 0xF39C12   # Orange
COLOR_INFO = 0x3498DB      # Blue
COLOR_PRIMARY = 0x9B59B6   # Purple (Aegis brand)
COLOR_SECONDARY = 0x95A5A6 # Gray


def _base_embed(
    title: Optional[str] = None,
    description: Optional[str] = None,
    color: int = COLOR_PRIMARY,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    return embed


def success_embed(
    title: str = "Success",
    description: Optional[str] = None,
) -> discord.Embed:
    """Green success embed."""
    embed = _base_embed(title=f"✅ {title}", description=description, color=COLOR_SUCCESS)
    return embed


def error_embed(
    title: str = "Error",
    description: Optional[str] = None,
) -> discord.Embed:
    """Red error embed."""
    embed = _base_embed(title=f"❌ {title}", description=description, color=COLOR_ERROR)
    return embed


def warning_embed(
    title: str = "Warning",
    description: Optional[str] = None,
) -> discord.Embed:
    """Orange warning embed."""
    embed = _base_embed(title=f"⚠️ {title}", description=description, color=COLOR_WARNING)
    return embed


def info_embed(
    title: str = "Information",
    description: Optional[str] = None,
) -> discord.Embed:
    """Blue information embed."""
    embed = _base_embed(title=f"ℹ️ {title}", description=description, color=COLOR_INFO)
    return embed


def primary_embed(
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> discord.Embed:
    """Purple brand embed for general use."""
    return _base_embed(title=title, description=description, color=COLOR_PRIMARY)


def moderation_embed(
    action: str,
    target: discord.abc.User,
    moderator: discord.abc.User,
    reason: Optional[str] = None,
    case_id: Optional[str] = None,
    duration: Optional[str] = None,
) -> discord.Embed:
    """Standard moderation action embed."""
    embed = discord.Embed(
        title=f"Moderation • {action}",
        color=COLOR_ERROR,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="User", value=f"{target.mention} (`{target.id}`)", inline=True)
    embed.add_field(name="Moderator", value=f"{moderator.mention}", inline=True)

    if case_id:
        embed.add_field(name="Case ID", value=f"`{case_id}`", inline=True)
    if duration:
        embed.add_field(name="Duration", value=duration, inline=True)
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)

    embed.set_thumbnail(url=target.display_avatar.url)
    return embed


def security_embed(
    title: str,
    description: Optional[str] = None,
    severity: str = "medium",
) -> discord.Embed:
    """Security alert embed with severity-based color."""
    color_map = {
        "low": COLOR_INFO,
        "medium": COLOR_WARNING,
        "high": COLOR_ERROR,
        "critical": 0x8B0000,  # Dark red
    }
    color = color_map.get(severity.lower(), COLOR_WARNING)

    embed = _base_embed(
        title=f"🛡️ Security • {title}",
        description=description,
        color=color,
    )
    embed.add_field(name="Severity", value=severity.upper(), inline=True)
    return embed

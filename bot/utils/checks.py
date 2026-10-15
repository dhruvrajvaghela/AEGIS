"""
Permission and authorization checks for AEGIS ULTIMATE ESPORTS BOT.
Used by both prefix commands and slash commands.
"""

from __future__ import annotations

from typing import Optional, Union

import discord
from discord.ext import commands

from bot.config import config


def is_owner(user: Union[discord.User, discord.Member, discord.Object, int]) -> bool:
    """Strict owner check using Discord user ID only."""
    user_id = user.id if hasattr(user, "id") else int(user)
    return config.is_owner(user_id)


async def is_guild_admin(member: discord.Member) -> bool:
    """Check if member has administrator permission or is the guild owner."""
    if member.guild is None:
        return False
    if member.guild.owner_id == member.id:
        return True
    return member.guild_permissions.administrator


async def has_mod_permissions(
    member: discord.Member,
    *,
    ban_members: bool = False,
    kick_members: bool = False,
    manage_messages: bool = False,
    moderate_members: bool = False,
    manage_roles: bool = False,
    manage_channels: bool = False,
) -> bool:
    """
    Check common moderation permissions.
    Returns True if the member has administrator or the requested permissions.
    """
    if member.guild is None:
        return False

    if await is_guild_admin(member):
        return True

    perms = member.guild_permissions

    if ban_members and not perms.ban_members:
        return False
    if kick_members and not perms.kick_members:
        return False
    if manage_messages and not perms.manage_messages:
        return False
    if moderate_members and not perms.moderate_members:
        return False
    if manage_roles and not perms.manage_roles:
        return False
    if manage_channels and not perms.manage_channels:
        return False

    # If no specific flags were requested, require at least one mod permission
    if not any(
        [ban_members, kick_members, manage_messages, moderate_members, manage_roles, manage_channels]
    ):
        return (
            perms.ban_members
            or perms.kick_members
            or perms.manage_messages
            or perms.moderate_members
            or perms.manage_roles
        )

    return True


def can_moderate_target(
    moderator: discord.Member,
    target: discord.Member,
) -> tuple[bool, Optional[str]]:
    """
    Check role hierarchy and ownership before allowing moderation actions.
    Returns (allowed, reason_if_denied).
    """
    if moderator.guild is None or target.guild is None:
        return False, "Invalid guild context."

    if moderator.id == target.id:
        return False, "You cannot moderate yourself."

    if target.id == moderator.guild.owner_id:
        return False, "You cannot moderate the server owner."

    if is_owner(target):
        return False, "You cannot moderate the bot owner."

    # Bot cannot moderate someone higher or equal in hierarchy
    me = moderator.guild.me
    if me is None:
        return False, "Bot member not found."

    if target.top_role >= me.top_role and moderator.guild.owner_id != me.id:
        return False, "I cannot moderate this user due to role hierarchy."

    # Moderator cannot moderate someone higher or equal (unless guild owner)
    if moderator.guild.owner_id != moderator.id:
        if target.top_role >= moderator.top_role:
            return False, "You cannot moderate this user due to role hierarchy."

    return True, None


# -------------------- Discord.py Check Decorators --------------------

def owner_only():
    """Command check: only the configured bot owner may use this command."""

    async def predicate(ctx: commands.Context) -> bool:
        if not is_owner(ctx.author):
            raise commands.CheckFailure("This command is restricted to the bot owner.")
        return True

    return commands.check(predicate)


def guild_admin_only():
    """Command check: guild administrator or guild owner only."""

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("This command can only be used in a server.")
        if not isinstance(ctx.author, discord.Member):
            raise commands.CheckFailure("Could not resolve member permissions.")
        if not await is_guild_admin(ctx.author):
            raise commands.CheckFailure("You need Administrator permission to use this command.")
        return True

    return commands.check(predicate)


def mod_only(
    *,
    ban_members: bool = False,
    kick_members: bool = False,
    manage_messages: bool = False,
    moderate_members: bool = False,
):
    """Command check for common moderator permissions."""

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("This command can only be used in a server.")
        if not isinstance(ctx.author, discord.Member):
            raise commands.CheckFailure("Could not resolve member permissions.")
        if not await has_mod_permissions(
            ctx.author,
            ban_members=ban_members,
            kick_members=kick_members,
            manage_messages=manage_messages,
            moderate_members=moderate_members,
        ):
            raise commands.CheckFailure("You do not have the required moderation permissions.")
        return True

    return commands.check(predicate)


def not_in_maintenance():
    """Block commands when the bot is in maintenance mode (owner bypasses)."""

    async def predicate(ctx: commands.Context) -> bool:
        if config.maintenance_mode and not is_owner(ctx.author):
            raise commands.CheckFailure(
                "The bot is currently in maintenance mode. Please try again later."
            )
        return True

    return commands.check(predicate)

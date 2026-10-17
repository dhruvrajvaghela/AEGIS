"""
Moderation commands for AEGIS ULTIMATE ESPORTS BOT.
Ban, kick, timeout, warn, purge, and case history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_db
from bot.utils.checks import can_moderate_target, has_mod_permissions, is_guild_admin
from bot.utils.embeds import success_embed, error_embed, moderation_embed, info_embed
from bot.utils.helpers import clean_reason, generate_case_id, parse_duration, format_duration
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class Moderation(commands.Cog):
    """Moderation commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _create_case(
        self,
        guild_id: int,
        user_id: int,
        moderator_id: int,
        action: str,
        reason: str,
        duration_seconds: Optional[int] = None,
    ) -> str:
        case_id = generate_case_id("MOD")
        db = get_db()
        await db.execute(
            """
            INSERT INTO mod_cases
                (case_id, guild_id, user_id, moderator_id, action, reason, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (case_id, guild_id, user_id, moderator_id, action, reason, duration_seconds),
        )
        return case_id

    async def _check_mod(
        self,
        ctx: commands.Context,
        target: discord.Member,
        *,
        ban: bool = False,
        kick: bool = False,
        moderate: bool = False,
    ) -> bool:
        if not isinstance(ctx.author, discord.Member):
            await ctx.send(embed=error_embed("Error", "Could not resolve permissions."), ephemeral=True)
            return False

        if not await has_mod_permissions(
            ctx.author,
            ban_members=ban,
            kick_members=kick,
            moderate_members=moderate,
        ):
            await ctx.send(
                embed=error_embed("Permission Denied", "You lack the required moderation permissions."),
                ephemeral=True,
            )
            return False

        allowed, reason = can_moderate_target(ctx.author, target)
        if not allowed:
            await ctx.send(embed=error_embed("Cannot Moderate", reason or "Hierarchy check failed."), ephemeral=True)
            return False

        return True

    # -------------------- BAN --------------------

    @commands.hybrid_command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for the ban", delete_days="Days of messages to delete (0-7)")
    @commands.guild_only()
    async def ban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        reason: Optional[str] = None,
        delete_days: int = 0,
    ) -> None:
        if not await self._check_mod(ctx, member, ban=True):
            return

        reason = clean_reason(reason)
        delete_days = max(0, min(delete_days, 7))

        try:
            await member.ban(reason=f"{ctx.author} | {reason}", delete_message_days=delete_days)
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Failed", "I lack permission to ban this member."))
            return
        except discord.HTTPException as e:
            await ctx.send(embed=error_embed("Failed", str(e)))
            return

        case_id = await self._create_case(ctx.guild.id, member.id, ctx.author.id, "ban", reason)
        embed = moderation_embed("Ban", member, ctx.author, reason=reason, case_id=case_id)
        await ctx.send(embed=embed)

    # -------------------- UNBAN --------------------

    @commands.hybrid_command(name="unban", description="Unban a user by ID")
    @app_commands.describe(user_id="Discord user ID to unban", reason="Reason")
    @commands.guild_only()
    async def unban(
        self,
        ctx: commands.Context,
        user_id: str,
        reason: Optional[str] = None,
    ) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not await has_mod_permissions(ctx.author, ban_members=True):
            await ctx.send(embed=error_embed("Permission Denied", "You need Ban Members permission."), ephemeral=True)
            return

        reason = clean_reason(reason)
        try:
            uid = int(user_id)
        except ValueError:
            await ctx.send(embed=error_embed("Invalid ID", "Please provide a numeric user ID."))
            return

        try:
            user = await self.bot.fetch_user(uid)
            await ctx.guild.unban(user, reason=f"{ctx.author} | {reason}")
        except discord.NotFound:
            await ctx.send(embed=error_embed("Not Found", "User is not banned or does not exist."))
            return
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Failed", "I lack permission to unban."))
            return

        case_id = await self._create_case(ctx.guild.id, uid, ctx.author.id, "unban", reason)
        await ctx.send(embed=success_embed("Unbanned", f"Unbanned `{uid}`.\nCase: `{case_id}`"))

    # -------------------- KICK --------------------

    @commands.hybrid_command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason")
    @commands.guild_only()
    async def kick(
        self,
        ctx: commands.Context,
        member: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        if not await self._check_mod(ctx, member, kick=True):
            return

        reason = clean_reason(reason)
        try:
            await member.kick(reason=f"{ctx.author} | {reason}")
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Failed", "I lack permission to kick this member."))
            return

        case_id = await self._create_case(ctx.guild.id, member.id, ctx.author.id, "kick", reason)
        embed = moderation_embed("Kick", member, ctx.author, reason=reason, case_id=case_id)
        await ctx.send(embed=embed)

    # -------------------- TIMEOUT --------------------

    @commands.hybrid_command(name="timeout", description="Timeout a member")
    @app_commands.describe(member="Member to timeout", duration="Duration (e.g. 10m, 1h, 1d)", reason="Reason")
    @commands.guild_only()
    async def timeout(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: str,
        reason: Optional[str] = None,
    ) -> None:
        if not await self._check_mod(ctx, member, moderate=True):
            return

        delta = parse_duration(duration)
        if delta is None or delta.total_seconds() < 1:
            await ctx.send(embed=error_embed("Invalid Duration", "Use format like `10m`, `1h`, `1d`."))
            return

        # Discord max timeout is 28 days
        if delta.total_seconds() > 28 * 86400:
            await ctx.send(embed=error_embed("Too Long", "Maximum timeout is 28 days."))
            return

        reason = clean_reason(reason)
        until = datetime.now(timezone.utc) + delta

        try:
            await member.timeout(until, reason=f"{ctx.author} | {reason}")
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Failed", "I lack permission to timeout this member."))
            return

        case_id = await self._create_case(
            ctx.guild.id, member.id, ctx.author.id, "timeout", reason, int(delta.total_seconds())
        )
        embed = moderation_embed(
            "Timeout", member, ctx.author, reason=reason, case_id=case_id, duration=format_duration(delta)
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="untimeout", description="Remove timeout from a member")
    @app_commands.describe(member="Member to remove timeout from", reason="Reason")
    @commands.guild_only()
    async def untimeout(
        self,
        ctx: commands.Context,
        member: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        if not await self._check_mod(ctx, member, moderate=True):
            return

        reason = clean_reason(reason)
        try:
            await member.timeout(None, reason=f"{ctx.author} | {reason}")
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Failed", "I lack permission to remove timeout."))
            return

        case_id = await self._create_case(ctx.guild.id, member.id, ctx.author.id, "untimeout", reason)
        await ctx.send(embed=success_embed("Timeout Removed", f"Removed timeout from {member.mention}.\nCase: `{case_id}`"))

    # -------------------- WARN --------------------

    @commands.hybrid_command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason")
    @commands.guild_only()
    async def warn(
        self,
        ctx: commands.Context,
        member: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        if not await self._check_mod(ctx, member, moderate=True):
            return

        reason = clean_reason(reason)
        case_id = await self._create_case(ctx.guild.id, member.id, ctx.author.id, "warn", reason)

        db = get_db()
        await db.execute(
            """
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, points, case_id)
            VALUES (?, ?, ?, ?, 1, ?);
            """,
            (ctx.guild.id, member.id, ctx.author.id, reason, case_id),
        )

        embed = moderation_embed("Warn", member, ctx.author, reason=reason, case_id=case_id)
        await ctx.send(embed=embed)

        try:
            await member.send(f"You have been warned in **{ctx.guild.name}**.\nReason: {reason}")
        except discord.HTTPException:
            pass

    @commands.hybrid_command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="Member to check")
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, member: discord.Member) -> None:
        db = get_db()
        rows = await db.fetchall(
            """
            SELECT reason, points, moderator_id, created_at, case_id
            FROM warnings
            WHERE guild_id = ? AND user_id = ?
            ORDER BY created_at DESC
            LIMIT 20;
            """,
            (ctx.guild.id, member.id),
        )

        if not rows:
            await ctx.send(embed=info_embed("Warnings", f"{member.mention} has no warnings."))
            return

        total = sum(r["points"] for r in rows)
        lines = [
            f"`{r['created_at'][:10]}` — {r['reason'] or 'No reason'} ({r['points']} pt) [{r['case_id']}]"
            for r in rows
        ]
        embed = info_embed(
            f"Warnings for {member}",
            f"Total points: **{total}**\n\n" + "\n".join(lines),
        )
        await ctx.send(embed=embed)

    # -------------------- PURGE --------------------

    @commands.hybrid_command(name="purge", description="Delete multiple messages")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @commands.guild_only()
    async def purge(self, ctx: commands.Context, amount: int) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not await has_mod_permissions(ctx.author, manage_messages=True):
            await ctx.send(
                embed=error_embed("Permission Denied", "You need Manage Messages permission."),
                ephemeral=True,
            )
            return

        amount = max(1, min(amount, 100))

        if ctx.interaction:
            await ctx.defer(ephemeral=True)

        deleted = await ctx.channel.purge(limit=amount + (0 if ctx.interaction else 1))
        count = len(deleted)

        case_id = await self._create_case(
            ctx.guild.id, ctx.author.id, ctx.author.id, "purge", f"Purged {count} messages"
        )

        msg = f"Deleted **{count}** messages.\nCase: `{case_id}`"
        if ctx.interaction:
            await ctx.send(embed=success_embed("Purged", msg), ephemeral=True)
        else:
            await ctx.send(embed=success_embed("Purged", msg), delete_after=5)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))

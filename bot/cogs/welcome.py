"""
Welcome and leave system for AEGIS ULTIMATE ESPORTS BOT.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_db
from bot.utils.checks import is_guild_admin, is_owner
from bot.utils.embeds import success_embed, error_embed, primary_embed, info_embed
from bot.utils.i18n import t
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class Welcome(commands.Cog):
    """Welcome messages, leave logs, and related configuration."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _ensure_guild(self, guild_id: int) -> None:
        db = get_db()
        row = await db.fetchone("SELECT guild_id FROM guilds WHERE guild_id = ?;", (guild_id,))
        if not row:
            await db.execute("INSERT INTO guilds (guild_id) VALUES (?);", (guild_id,))

    async def _get_guild(self, guild_id: int) -> Optional[dict]:
        await self._ensure_guild(guild_id)
        db = get_db()
        row = await db.fetchone("SELECT * FROM guilds WHERE guild_id = ?;", (guild_id,))
        return dict(row) if row else None

    # -------------------- EVENTS --------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return

        guild_data = await self._get_guild(member.guild.id)
        if not guild_data:
            return

        channel_id = guild_data.get("welcome_channel_id")
        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        lang = guild_data.get("language", "en")
        message = t(
            "welcome.default_message",
            lang=lang,
            user=member.mention,
            server=member.guild.name,
        )

        embed = primary_embed(description=message)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{member.guild.member_count}")

        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            logger.warning("Failed to send welcome in %s: %s", member.guild.id, e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guild_data = await self._get_guild(member.guild.id)
        if not guild_data:
            return

        channel_id = guild_data.get("leave_channel_id") or guild_data.get("log_channel_id")
        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        lang = guild_data.get("language", "en")
        message = t(
            "welcome.leave_message",
            lang=lang,
            user=str(member),
        )

        embed = info_embed("Member Left", message)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Members", value=str(member.guild.member_count), inline=True)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            logger.warning("Failed to send leave log in %s: %s", member.guild.id, e)

    # -------------------- CONFIG COMMANDS --------------------

    @commands.hybrid_command(name="setwelcome", description="Set the welcome channel")
    @app_commands.describe(channel="Channel for welcome messages")
    @commands.guild_only()
    async def setwelcome(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            await ctx.send(
                embed=error_embed("Permission Denied", "Administrator only."),
                ephemeral=True,
            )
            return

        await self._ensure_guild(ctx.guild.id)
        db = get_db()
        await db.execute(
            """
            UPDATE guilds SET welcome_channel_id = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (channel.id, ctx.guild.id),
        )
        await ctx.send(
            embed=success_embed("Welcome Channel Set", f"Welcome messages will go to {channel.mention}.")
        )

    @commands.hybrid_command(name="setleave", description="Set the leave log channel")
    @app_commands.describe(channel="Channel for leave messages")
    @commands.guild_only()
    async def setleave(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            await ctx.send(
                embed=error_embed("Permission Denied", "Administrator only."),
                ephemeral=True,
            )
            return

        await self._ensure_guild(ctx.guild.id)
        db = get_db()
        await db.execute(
            """
            UPDATE guilds SET leave_channel_id = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (channel.id, ctx.guild.id),
        )
        await ctx.send(
            embed=success_embed("Leave Channel Set", f"Leave messages will go to {channel.mention}.")
        )

    @commands.hybrid_command(name="welcometest", description="Send a test welcome message")
    @commands.guild_only()
    async def welcometest(self, ctx: commands.Context) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            await ctx.send(
                embed=error_embed("Permission Denied", "Administrator only."),
                ephemeral=True,
            )
            return

        guild_data = await self._get_guild(ctx.guild.id)
        lang = (guild_data or {}).get("language", "en")
        message = t(
            "welcome.default_message",
            lang=lang,
            user=ctx.author.mention,
            server=ctx.guild.name,
        )
        embed = primary_embed(description=message)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="Test welcome message")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))

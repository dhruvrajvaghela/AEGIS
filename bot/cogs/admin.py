"""
Admin / server configuration commands for AEGIS ULTIMATE ESPORTS BOT.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_db
from bot.utils.checks import is_guild_admin, is_owner
from bot.utils.embeds import success_embed, error_embed, info_embed, primary_embed
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class Admin(commands.Cog):
    """Server configuration and admin utilities."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _ensure_guild(self, guild_id: int) -> None:
        db = get_db()
        row = await db.fetchone("SELECT guild_id FROM guilds WHERE guild_id = ?;", (guild_id,))
        if not row:
            await db.execute(
                "INSERT INTO guilds (guild_id) VALUES (?);",
                (guild_id,),
            )

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("This command can only be used in a server.")
        if not isinstance(ctx.author, discord.Member):
            raise commands.CheckFailure("Could not resolve member.")
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            raise commands.CheckFailure("Administrator permission required.")
        return True

    # -------------------- PREFIX --------------------

    @commands.hybrid_command(name="setprefix", description="Set the command prefix for this server")
    @app_commands.describe(prefix="New prefix (1-5 characters)")
    async def setprefix(self, ctx: commands.Context, prefix: str) -> None:
        prefix = prefix.strip()
        if not prefix or len(prefix) > 5:
            await ctx.send(embed=error_embed("Invalid Prefix", "Prefix must be 1–5 characters."))
            return

        await self._ensure_guild(ctx.guild.id)
        db = get_db()
        await db.execute(
            """
            UPDATE guilds SET prefix = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (prefix, ctx.guild.id),
        )
        await ctx.send(embed=success_embed("Prefix Updated", f"New prefix: `{prefix}`"))

    # -------------------- LANGUAGE --------------------

    @commands.hybrid_command(name="setlanguage", description="Set the bot language for this server")
    @app_commands.describe(language="en or hi")
    async def setlanguage(self, ctx: commands.Context, language: str) -> None:
        language = language.lower().strip()
        if language not in ("en", "hi"):
            await ctx.send(embed=error_embed("Invalid Language", "Supported: `en`, `hi`."))
            return

        await self._ensure_guild(ctx.guild.id)
        db = get_db()
        await db.execute(
            """
            UPDATE guilds SET language = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (language, ctx.guild.id),
        )
        await ctx.send(
            embed=success_embed("Language Updated", f"Server language set to **{language}**.")
        )

    # -------------------- LOG CHANNEL --------------------

    @commands.hybrid_command(name="setlogchannel", description="Set the moderation log channel")
    @app_commands.describe(channel="Channel for moderation logs")
    async def setlogchannel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        await self._ensure_guild(ctx.guild.id)
        db = get_db()
        await db.execute(
            """
            UPDATE guilds SET log_channel_id = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (channel.id, ctx.guild.id),
        )
        await ctx.send(
            embed=success_embed("Log Channel Set", f"Moderation logs will go to {channel.mention}.")
        )

    @commands.hybrid_command(name="setsecuritylog", description="Set the security log channel")
    @app_commands.describe(channel="Channel for security alerts")
    async def setsecuritylog(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        await self._ensure_guild(ctx.guild.id)
        db = get_db()
        await db.execute(
            """
            UPDATE guilds SET security_log_channel_id = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (channel.id, ctx.guild.id),
        )
        await ctx.send(
            embed=success_embed(
                "Security Log Channel Set",
                f"Security alerts will go to {channel.mention}.",
            )
        )

    # -------------------- CONFIG VIEW --------------------

    @commands.hybrid_command(name="config", description="View server configuration")
    async def view_config(self, ctx: commands.Context) -> None:
        await self._ensure_guild(ctx.guild.id)
        db = get_db()
        row = await db.fetchone(
            "SELECT * FROM guilds WHERE guild_id = ?;",
            (ctx.guild.id,),
        )
        if not row:
            await ctx.send(embed=error_embed("Error", "Could not load config."))
            return

        g = dict(row)
        embed = primary_embed(title=f"Config — {ctx.guild.name}")
        embed.add_field(name="Prefix", value=f"`{g['prefix']}`", inline=True)
        embed.add_field(name="Language", value=g["language"], inline=True)
        embed.add_field(
            name="Log Channel",
            value=f"<#{g['log_channel_id']}>" if g["log_channel_id"] else "Not set",
            inline=True,
        )
        embed.add_field(
            name="Security Log",
            value=f"<#{g['security_log_channel_id']}>" if g["security_log_channel_id"] else "Not set",
            inline=True,
        )
        embed.add_field(
            name="Welcome Channel",
            value=f"<#{g['welcome_channel_id']}>" if g["welcome_channel_id"] else "Not set",
            inline=True,
        )
        embed.add_field(
            name="Verified Role",
            value=f"<@&{g['verified_role_id']}>" if g["verified_role_id"] else "Not set",
            inline=True,
        )
        await ctx.send(embed=embed)

    # -------------------- SLOWMODE --------------------

    @commands.hybrid_command(name="slowmode", description="Set channel slowmode")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)")
    async def slowmode(self, ctx: commands.Context, seconds: int) -> None:
        seconds = max(0, min(seconds, 21600))
        try:
            await ctx.channel.edit(slowmode_delay=seconds)
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Failed", "I lack permission to edit this channel."))
            return

        if seconds == 0:
            await ctx.send(embed=success_embed("Slowmode Disabled", "Slowmode has been turned off."))
        else:
            await ctx.send(
                embed=success_embed("Slowmode Set", f"Slowmode is now **{seconds}** seconds.")
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))

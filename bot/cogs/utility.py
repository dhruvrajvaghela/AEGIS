"""
Utility commands for AEGIS ULTIMATE ESPORTS BOT.
Ping, uptime, help, userinfo, serverinfo, avatar, etc.
"""

from __future__ import annotations

import platform
import time
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import config
from bot.utils.embeds import info_embed, primary_embed, error_embed
from bot.utils.helpers import format_uptime
from bot.utils.i18n import t
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class Utility(commands.Cog):
    """General utility commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # -------------------- PING --------------------

    @commands.hybrid_command(name="ping", description="Check bot latency")
    async def ping(self, ctx: commands.Context) -> None:
        latency = round(self.bot.latency * 1000)
        embed = info_embed(
            t("utility.ping", latency=latency),
            f"WebSocket latency: **{latency}ms**",
        )
        await ctx.send(embed=embed)

    # -------------------- UPTIME --------------------

    @commands.hybrid_command(name="uptime", description="Show bot uptime")
    async def uptime(self, ctx: commands.Context) -> None:
        delta = datetime.now(timezone.utc) - self.bot.start_time
        uptime_str = format_uptime(delta.total_seconds())
        embed = info_embed(
            t("utility.uptime", uptime=uptime_str),
            f"Online since <t:{int(self.bot.start_time.timestamp())}:F>",
        )
        await ctx.send(embed=embed)

    # -------------------- BOT INFO / STATS --------------------

    @commands.hybrid_command(name="botinfo", description="Show bot statistics")
    async def botinfo(self, ctx: commands.Context) -> None:
        delta = datetime.now(timezone.utc) - self.bot.start_time
        embed = primary_embed(
            title="AEGIS ULTIMATE ESPORTS BOT",
            description="Professional esports tournament & security platform.",
        )
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Users", value=str(len(self.bot.users)), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Uptime", value=format_uptime(delta.total_seconds()), inline=True)
        embed.add_field(name="Prefix", value=f"`{config.default_prefix}`", inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        embed.set_footer(text=f"Owner ID: {config.owner_id}")
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)

    # -------------------- USER INFO --------------------

    @commands.hybrid_command(name="userinfo", description="Show information about a user")
    @app_commands.describe(user="The user to look up")
    async def userinfo(
        self, ctx: commands.Context, user: Optional[discord.Member] = None
    ) -> None:
        target = user or ctx.author
        embed = primary_embed(title=t("utility.userinfo_title"))
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Username", value=str(target), inline=True)
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
        embed.add_field(
            name="Created",
            value=f"<t:{int(target.created_at.timestamp())}:R>",
            inline=True,
        )

        if isinstance(target, discord.Member) and target.joined_at:
            embed.add_field(
                name="Joined",
                value=f"<t:{int(target.joined_at.timestamp())}:R>",
                inline=True,
            )
            roles = [r.mention for r in reversed(target.roles) if r != ctx.guild.default_role]
            if roles:
                embed.add_field(
                    name=f"Roles ({len(roles)})",
                    value=" ".join(roles[:15]) + (" ..." if len(roles) > 15 else ""),
                    inline=False,
                )
            embed.add_field(
                name="Top Role",
                value=target.top_role.mention,
                inline=True,
            )

        await ctx.send(embed=embed)

    # -------------------- SERVER INFO --------------------

    @commands.hybrid_command(name="serverinfo", description="Show server information")
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if guild is None:
            return

        embed = primary_embed(title=t("utility.serverinfo_title"))
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Name", value=guild.name, inline=True)
        embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="Owner", value=str(guild.owner) if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(
            name="Channels",
            value=f"Text: {len(guild.text_channels)} | Voice: {len(guild.voice_channels)}",
            inline=True,
        )
        embed.add_field(
            name="Created",
            value=f"<t:{int(guild.created_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(
            name="Boost Level",
            value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)",
            inline=True,
        )
        await ctx.send(embed=embed)

    # -------------------- AVATAR --------------------

    @commands.hybrid_command(name="avatar", description="Show a user's avatar")
    @app_commands.describe(user="The user whose avatar to show")
    async def avatar(
        self, ctx: commands.Context, user: Optional[discord.User] = None
    ) -> None:
        target = user or ctx.author
        embed = primary_embed(title=f"Avatar — {target}")
        embed.set_image(url=target.display_avatar.replace(size=4096).url)
        embed.add_field(name="User", value=f"{target.mention} (`{target.id}`)")
        await ctx.send(embed=embed)

    # -------------------- HELP --------------------

    @commands.hybrid_command(name="help", description="Show help information")
    @app_commands.describe(command="Specific command to get help for")
    async def help_command(
        self, ctx: commands.Context, command: Optional[str] = None
    ) -> None:
        if command:
            cmd = self.bot.get_command(command)
            if cmd is None:
                await ctx.send(
                    embed=error_embed(t("help.no_command"), f"`{command}` was not found."),
                    ephemeral=True if ctx.interaction else False,
                )
                return

            embed = primary_embed(title=f"Help — {cmd.qualified_name}")
            embed.description = cmd.help or cmd.description or "No description."
            if cmd.signature:
                embed.add_field(
                    name="Usage",
                    value=f"`{config.default_prefix}{cmd.qualified_name} {cmd.signature}`",
                    inline=False,
                )
            await ctx.send(embed=embed)
            return

        embed = primary_embed(
            title=t("help.title"),
            description=t("help.description"),
        )
        categories = {
            "Utility": ["ping", "uptime", "botinfo", "userinfo", "serverinfo", "avatar", "help"],
            "Moderation": ["ban", "unban", "kick", "timeout", "warn", "purge"],
            "Security": ["lockdown", "security", "antinuke"],
            "Tickets": ["ticket", "close", "claim"],
            "Esports": ["tournament", "scrim", "team", "leaderboard"],
            "Owner": ["eval", "shutdown", "maintenance", "backup"],
        }
        for cat, cmds in categories.items():
            embed.add_field(
                name=cat,
                value=", ".join(f"`{c}`" for c in cmds),
                inline=False,
            )
        embed.set_footer(text=f"Prefix: {config.default_prefix} | Also supports slash commands")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))

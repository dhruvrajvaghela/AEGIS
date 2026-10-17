"""
Owner-only commands for AEGIS ULTIMATE ESPORTS BOT.
All commands are restricted to the configured DISCORD_OWNER_ID.
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import config
from bot.database.backup import create_backup, list_backups, cleanup_old_backups
from bot.database.connection import get_db
from bot.utils.checks import owner_only, is_owner
from bot.utils.embeds import success_embed, error_embed, info_embed, warning_embed, primary_embed
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class Owner(commands.Cog):
    """Owner-only control commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Global check for every command in this cog."""
        if not is_owner(ctx.author):
            raise commands.CheckFailure("This command is restricted to the bot owner.")
        return True

    # -------------------- STATUS / DIAGNOSTICS --------------------

    @commands.hybrid_command(name="diagnostics", description="Run system diagnostics")
    async def diagnostics(self, ctx: commands.Context) -> None:
        db = get_db()
        db_ok = False
        integrity = False
        tables = 0
        try:
            await db.fetchone("SELECT 1;")
            db_ok = True
            integrity = await db.integrity_check()
            tables = len(await db.get_table_names())
        except Exception as e:
            logger.error("Diagnostics DB error: %s", e)

        embed = primary_embed(title="System Diagnostics")
        embed.add_field(name="Database", value="✅ Connected" if db_ok else "❌ Failed", inline=True)
        embed.add_field(name="Integrity", value="✅ OK" if integrity else "❌ Fail", inline=True)
        embed.add_field(name="Tables", value=str(tables), inline=True)
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(
            name="Maintenance",
            value="ON" if config.maintenance_mode else "OFF",
            inline=True,
        )
        embed.add_field(name="DB Path", value=f"`{config.database_path}`", inline=False)
        await ctx.send(embed=embed)

    # -------------------- MAINTENANCE --------------------

    @commands.hybrid_command(name="maintenance", description="Toggle maintenance mode status message")
    @app_commands.describe(state="on or off")
    async def maintenance(self, ctx: commands.Context, state: str) -> None:
        state = state.lower()
        if state not in ("on", "off"):
            await ctx.send(embed=error_embed("Invalid value", "Use `on` or `off`."))
            return

        # Note: true persistence requires environment variable change + restart
        msg = (
            f"Maintenance mode **{state}** requested.\n"
            f"Set `MAINTENANCE_MODE={'true' if state == 'on' else 'false'}` "
            f"in your environment and restart the service for full effect."
        )
        logger.warning("Maintenance %s requested by owner %s", state, ctx.author.id)
        await ctx.send(embed=warning_embed("Maintenance Mode", msg))

    # -------------------- BACKUP --------------------

    @commands.hybrid_command(name="backup", description="Create a database backup")
    @app_commands.describe(note="Optional note for this backup")
    async def backup(self, ctx: commands.Context, note: Optional[str] = None) -> None:
        await ctx.defer()
        try:
            path = await create_backup(note=note, created_by=ctx.author.id)
            await ctx.send(
                embed=success_embed("Backup Created", f"Saved to:\n`{path}`")
            )
        except Exception as e:
            logger.error("Backup failed: %s", e)
            await ctx.send(embed=error_embed("Backup Failed", str(e)))

    @commands.hybrid_command(name="backups", description="List recent database backups")
    async def backups_list(self, ctx: commands.Context) -> None:
        try:
            items = await list_backups()
        except Exception as e:
            await ctx.send(embed=error_embed("Error", str(e)))
            return

        if not items:
            await ctx.send(embed=info_embed("Backups", "No backups found."))
            return

        lines = []
        for b in items[:15]:
            size_kb = (b.get("size_bytes") or 0) / 1024
            lines.append(
                f"`{b['filename']}` — {size_kb:.1f} KB — {b.get('created_at', '?')}"
            )

        embed = info_embed("Recent Backups", "\n".join(lines))
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="cleanup_backups", description="Delete old backups")
    @app_commands.describe(keep="Number of newest backups to keep (default 10)")
    async def cleanup_backups_cmd(self, ctx: commands.Context, keep: int = 10) -> None:
        keep = max(3, min(keep, 50))
        try:
            deleted = await cleanup_old_backups(keep=keep)
            await ctx.send(
                embed=success_embed(
                    "Cleanup Complete",
                    f"Deleted **{deleted}** old backup(s). Kept newest {keep}.",
                )
            )
        except Exception as e:
            await ctx.send(embed=error_embed("Cleanup Failed", str(e)))

    # -------------------- SYNC --------------------

    @commands.hybrid_command(name="sync", description="Sync slash commands")
    @app_commands.describe(scope="guild or global")
    async def sync(self, ctx: commands.Context, scope: str = "guild") -> None:
        scope = scope.lower()
        await ctx.defer()

        try:
            if scope == "global":
                synced = await self.bot.tree.sync()
                msg = f"Synced **{len(synced)}** commands globally."
            else:
                if ctx.guild is None:
                    await ctx.send(embed=error_embed("Error", "Guild scope requires a server."))
                    return
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
                msg = f"Synced **{len(synced)}** commands to this guild."
            await ctx.send(embed=success_embed("Slash Commands Synced", msg))
        except Exception as e:
            logger.error("Sync failed: %s", e)
            await ctx.send(embed=error_embed("Sync Failed", str(e)))

    # -------------------- SHUTDOWN --------------------

    @commands.hybrid_command(name="shutdown", description="Gracefully shut down the bot")
    async def shutdown(self, ctx: commands.Context) -> None:
        await ctx.send(embed=warning_embed("Shutting Down", "Bot is shutting down..."))
        logger.warning("Shutdown requested by owner %s", ctx.author.id)
        await self.bot.close()

    # -------------------- SAY / ANNOUNCE --------------------

    @commands.command(name="say")
    async def say(self, ctx: commands.Context, *, message: str) -> None:
        """Make the bot say something (owner only, prefix only)."""
        await ctx.message.delete(delay=0.5)
        await ctx.send(message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Owner(bot))

"""
Core bot class for AEGIS ULTIMATE ESPORTS BOT.
"""

from __future__ import annotations

import asyncio
import os
import traceback
from datetime import datetime, timezone
from typing import Any, List, Optional

import discord
from discord.ext import commands

from bot.config import config
from bot.database.connection import get_db, init_db
from bot.database.migrations.runner import run_migrations
from bot.utils.embeds import error_embed
from bot.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


class AegisBot(commands.Bot):
    """
    Main bot class.
    Supports both prefix commands (&) and slash commands.
    """

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.moderation = True

        super().__init__(
            command_prefix=self._get_prefix,
            intents=intents,
            help_command=None,  # We use a custom help cog
            case_insensitive=True,
            strip_after_prefix=True,
            activity=self._build_activity(),
        )

        self.start_time: datetime = datetime.now(timezone.utc)
        self.db = get_db()
        self._initial_cogs_loaded = False

    async def _get_prefix(self, bot: commands.Bot, message: discord.Message) -> List[str]:
        """Dynamic prefix lookup (per-guild support later)."""
        # Default prefix from config; per-guild override can be added via database
        return [config.default_prefix, f"<@!{bot.user.id}> ", f"<@{bot.user.id}> "]

    def _build_activity(self) -> discord.Activity:
        activity_type_map = {
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening,
            "competing": discord.ActivityType.competing,
        }
        activity_type = activity_type_map.get(
            config.activity_type.lower(), discord.ActivityType.watching
        )
        return discord.Activity(type=activity_type, name=config.activity_text)

    async def setup_hook(self) -> None:
        """Called when the bot is starting up (before reconnect)."""
        setup_logging()
        logger.info("Starting AEGIS ULTIMATE ESPORTS BOT v%s", "1.0.0")

        # Database
        config.ensure_data_directory()
        await init_db()
        await run_migrations(self.db)

        # Load cogs
        await self.load_all_cogs()

        # Sync slash commands
        await self.sync_commands()

    async def load_all_cogs(self) -> None:
        """Load all cogs from the cogs package."""
        cog_modules = [
            "bot.cogs.owner",
            "bot.cogs.admin",
            "bot.cogs.utility",
            "bot.cogs.moderation",
            "bot.cogs.security",
            "bot.cogs.automod",
            "bot.cogs.staff",
            "bot.cogs.welcome",
            "bot.cogs.verification",
            "bot.cogs.roles",
            "bot.cogs.tickets",
            "bot.cogs.community",
            "bot.cogs.invites",
            "bot.cogs.esports.tournaments",
            "bot.cogs.esports.scrims",
            "bot.cogs.esports.teams",
            "bot.cogs.esports.matches",
            "bot.cogs.esports.rankings",
        ]

        for module in cog_modules:
            try:
                await self.load_extension(module)
                logger.info("Loaded cog: %s", module)
            except Exception as e:
                logger.error("Failed to load cog %s: %s", module, e)
                logger.debug(traceback.format_exc())

        self._initial_cogs_loaded = True

    async def sync_commands(self) -> None:
        """
        Sync application (slash) commands.
        Uses DEV_GUILD_ID for fast sync during development when set.
        """
        try:
            if config.dev_guild_id:
                guild = discord.Object(id=config.dev_guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(
                    "Synced %s slash commands to development guild %s",
                    len(synced),
                    config.dev_guild_id,
                )
            else:
                synced = await self.tree.sync()
                logger.info("Synced %s global slash commands", len(synced))
        except Exception as e:
            logger.error("Failed to sync slash commands: %s", e)

    async def on_ready(self) -> None:
        logger.info(
            "Logged in as %s (ID: %s) | Guilds: %s",
            self.user,
            self.user.id if self.user else "?",
            len(self.guilds),
        )
        logger.info("Prefix: %s | Owner ID: %s", config.default_prefix, config.owner_id)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Global error handler for prefix commands."""
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CheckFailure):
            embed = error_embed("Permission Denied", str(error))
            await ctx.send(embed=embed, delete_after=15)
            return

        if isinstance(error, commands.MissingRequiredArgument):
            embed = error_embed(
                "Missing Argument",
                f"Missing required argument: `{error.param.name}`\n"
                f"Use `{config.default_prefix}help {ctx.command}` for usage.",
            )
            await ctx.send(embed=embed, delete_after=20)
            return

        if isinstance(error, commands.BadArgument):
            embed = error_embed("Invalid Argument", str(error))
            await ctx.send(embed=embed, delete_after=15)
            return

        if isinstance(error, commands.CommandOnCooldown):
            embed = error_embed(
                "Cooldown",
                f"Try again in {error.retry_after:.1f} seconds.",
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        if isinstance(error, commands.NoPrivateMessage):
            embed = error_embed("Server Only", "This command can only be used in a server.")
            await ctx.send(embed=embed, delete_after=10)
            return

        # Unexpected errors
        logger.error("Command error in %s: %s", ctx.command, error)
        logger.debug(traceback.format_exc())

        embed = error_embed(
            "Unexpected Error",
            "An unexpected error occurred while executing this command.",
        )
        try:
            await ctx.send(embed=embed, delete_after=15)
        except Exception:
            pass

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError
    ) -> None:
        """Global error handler for slash commands."""
        if isinstance(error, discord.app_commands.CheckFailure):
            msg = str(error) or "You do not have permission to use this command."
            embed = error_embed("Permission Denied", msg)
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        logger.error("Slash command error: %s", error)
        logger.debug(traceback.format_exc())

        embed = error_embed("Unexpected Error", "An unexpected error occurred.")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            pass

    async def close(self) -> None:
        """Graceful shutdown."""
        logger.info("Shutting down bot...")
        try:
            await self.db.close()
        except Exception as e:
            logger.error("Error closing database: %s", e)
        await super().close()
        logger.info("Bot shutdown complete")


async def create_bot() -> AegisBot:
    """Factory function to create and return the bot instance."""
    bot = AegisBot()
    return bot

"""
Security and anti-nuke commands for AEGIS ULTIMATE ESPORTS BOT.
Lockdown, security status, and configuration.
"""

from __future__ import annotations

import json
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_db
from bot.utils.checks import is_guild_admin, is_owner
from bot.utils.embeds import success_embed, error_embed, warning_embed, security_embed, info_embed, primary_embed
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class Security(commands.Cog):
    """Security and anti-nuke commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _ensure_config(self, guild_id: int) -> dict:
        """Get or create security config for a guild."""
        db = get_db()
        row = await db.fetchone(
            "SELECT * FROM security_config WHERE guild_id = ?;",
            (guild_id,),
        )
        if row:
            return dict(row)

        await db.execute(
            """
            INSERT INTO security_config (guild_id)
            VALUES (?);
            """,
            (guild_id,),
        )
        row = await db.fetchone(
            "SELECT * FROM security_config WHERE guild_id = ?;",
            (guild_id,),
        )
        return dict(row) if row else {}

    async def _log_event(
        self,
        guild_id: int,
        event_type: str,
        severity: str = "medium",
        actor_id: Optional[int] = None,
        target_id: Optional[int] = None,
        details: Optional[str] = None,
    ) -> None:
        db = get_db()
        await db.execute(
            """
            INSERT INTO security_events
                (guild_id, event_type, severity, actor_id, target_id, details)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (guild_id, event_type, severity, actor_id, target_id, details),
        )

    # -------------------- STATUS --------------------

    @commands.hybrid_command(name="security", description="Show security status for this server")
    @commands.guild_only()
    async def security_status(self, ctx: commands.Context) -> None:
        cfg = await self._ensure_config(ctx.guild.id)

        embed = primary_embed(title="Security Status")
        embed.add_field(
            name="Anti-Nuke",
            value="✅ Enabled" if cfg.get("anti_nuke_enabled") else "❌ Disabled",
            inline=True,
        )
        embed.add_field(
            name="Anti-Raid",
            value="✅ Enabled" if cfg.get("anti_raid_enabled") else "❌ Disabled",
            inline=True,
        )
        embed.add_field(
            name="Anti-Spam",
            value="✅ Enabled" if cfg.get("anti_spam_enabled") else "❌ Disabled",
            inline=True,
        )
        embed.add_field(
            name="Lockdown",
            value="🔒 ACTIVE" if cfg.get("lockdown") else "🔓 Off",
            inline=True,
        )
        if cfg.get("lockdown") and cfg.get("lockdown_reason"):
            embed.add_field(name="Lockdown Reason", value=cfg["lockdown_reason"], inline=False)

        # Recent events
        db = get_db()
        events = await db.fetchall(
            """
            SELECT event_type, severity, created_at
            FROM security_events
            WHERE guild_id = ? AND resolved = 0
            ORDER BY created_at DESC
            LIMIT 5;
            """,
            (ctx.guild.id,),
        )
        if events:
            lines = [f"`{e['created_at'][:16]}` [{e['severity']}] {e['event_type']}" for e in events]
            embed.add_field(name="Recent Unresolved Events", value="\n".join(lines), inline=False)

        await ctx.send(embed=embed)

    # -------------------- LOCKDOWN --------------------

    @commands.hybrid_command(name="lockdown", description="Enable emergency lockdown")
    @app_commands.describe(reason="Reason for lockdown")
    @commands.guild_only()
    async def lockdown(self, ctx: commands.Context, reason: Optional[str] = None) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            await ctx.send(
                embed=error_embed("Permission Denied", "Only administrators can enable lockdown."),
                ephemeral=True,
            )
            return

        reason = reason or "Emergency lockdown"
        db = get_db()
        await self._ensure_config(ctx.guild.id)
        await db.execute(
            """
            UPDATE security_config
            SET lockdown = 1, lockdown_reason = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (reason, ctx.guild.id),
        )

        await self._log_event(
            ctx.guild.id,
            "lockdown_enabled",
            severity="high",
            actor_id=ctx.author.id,
            details=reason,
        )

        # Attempt to lock text channels the bot can manage
        locked = 0
        for channel in ctx.guild.text_channels:
            try:
                overwrite = channel.overwrites_for(ctx.guild.default_role)
                if overwrite.send_messages is not False:
                    overwrite.send_messages = False
                    await channel.set_permissions(
                        ctx.guild.default_role,
                        overwrite=overwrite,
                        reason=f"Lockdown by {ctx.author}",
                    )
                    locked += 1
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                continue

        embed = security_embed(
            "Lockdown Enabled",
            f"**Reason:** {reason}\n**Channels locked:** {locked}",
            severity="high",
        )
        await ctx.send(embed=embed)
        logger.warning("Lockdown enabled in guild %s by %s", ctx.guild.id, ctx.author.id)

    @commands.hybrid_command(name="unlock", description="Disable emergency lockdown")
    @commands.guild_only()
    async def unlock(self, ctx: commands.Context) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            await ctx.send(
                embed=error_embed("Permission Denied", "Only administrators can disable lockdown."),
                ephemeral=True,
            )
            return

        db = get_db()
        await self._ensure_config(ctx.guild.id)
        await db.execute(
            """
            UPDATE security_config
            SET lockdown = 0, lockdown_reason = NULL,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (ctx.guild.id,),
        )

        await self._log_event(
            ctx.guild.id,
            "lockdown_disabled",
            severity="medium",
            actor_id=ctx.author.id,
        )

        # Restore send_messages for @everyone where we set it False
        unlocked = 0
        for channel in ctx.guild.text_channels:
            try:
                overwrite = channel.overwrites_for(ctx.guild.default_role)
                if overwrite.send_messages is False:
                    overwrite.send_messages = None  # reset to default
                    await channel.set_permissions(
                        ctx.guild.default_role,
                        overwrite=overwrite,
                        reason=f"Unlock by {ctx.author}",
                    )
                    unlocked += 1
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                continue

        await ctx.send(
            embed=success_embed(
                "Lockdown Lifted",
                f"Lockdown has been disabled.\nChannels restored: {unlocked}",
            )
        )
        logger.info("Lockdown disabled in guild %s by %s", ctx.guild.id, ctx.author.id)

    # -------------------- TOGGLE FEATURES --------------------

    @commands.hybrid_command(name="antinuke", description="Toggle anti-nuke protection")
    @app_commands.describe(state="on or off")
    @commands.guild_only()
    async def antinuke(self, ctx: commands.Context, state: str) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            await ctx.send(
                embed=error_embed("Permission Denied", "Administrator only."),
                ephemeral=True,
            )
            return

        state = state.lower()
        if state not in ("on", "off"):
            await ctx.send(embed=error_embed("Invalid", "Use `on` or `off`."))
            return

        enabled = 1 if state == "on" else 0
        await self._ensure_config(ctx.guild.id)
        db = get_db()
        await db.execute(
            """
            UPDATE security_config
            SET anti_nuke_enabled = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (enabled, ctx.guild.id),
        )
        await ctx.send(
            embed=success_embed(
                "Anti-Nuke",
                f"Anti-nuke protection is now **{'enabled' if enabled else 'disabled'}**.",
            )
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Security(bot))

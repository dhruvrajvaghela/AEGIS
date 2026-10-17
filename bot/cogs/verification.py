"""
Verification system for AEGIS ULTIMATE ESPORTS BOT.
Button-based verification with configurable verified / quarantine roles.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_db
from bot.utils.checks import is_guild_admin, is_owner
from bot.utils.embeds import success_embed, error_embed, info_embed, primary_embed
from bot.utils.i18n import t
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class VerifyButton(discord.ui.View):
    """Persistent verification button."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.success,
        custom_id="aegis:verify",
        emoji="✅",
    )
    async def verify_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Verification is only available in servers.", ephemeral=True
            )
            return

        db = get_db()
        row = await db.fetchone(
            "SELECT verified_role_id, quarantine_role_id, language FROM guilds WHERE guild_id = ?;",
            (interaction.guild.id,),
        )
        if not row or not row["verified_role_id"]:
            await interaction.response.send_message(
                "Verification is not configured on this server.", ephemeral=True
            )
            return

        verified_role = interaction.guild.get_role(row["verified_role_id"])
        if verified_role is None:
            await interaction.response.send_message(
                "Verified role no longer exists. Please contact staff.", ephemeral=True
            )
            return

        member = interaction.user
        lang = row["language"] or "en"

        if verified_role in member.roles:
            await interaction.response.send_message(
                t("verification.already_verified", lang=lang), ephemeral=True
            )
            return

        try:
            await member.add_roles(verified_role, reason="Button verification")
        except discord.Forbidden:
            await interaction.response.send_message(
                "I lack permission to assign the verified role.", ephemeral=True
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                t("verification.failed", lang=lang), ephemeral=True
            )
            return

        # Remove quarantine role if present
        if row["quarantine_role_id"]:
            quarantine = interaction.guild.get_role(row["quarantine_role_id"])
            if quarantine and quarantine in member.roles:
                try:
                    await member.remove_roles(quarantine, reason="Verified")
                except discord.HTTPException:
                    pass

        await interaction.response.send_message(
            t("verification.success", lang=lang), ephemeral=True
        )


class Verification(commands.Cog):
    """Verification panel and configuration."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        # Register persistent view
        self.bot.add_view(VerifyButton())

    async def _ensure_guild(self, guild_id: int) -> None:
        db = get_db()
        row = await db.fetchone("SELECT guild_id FROM guilds WHERE guild_id = ?;", (guild_id,))
        if not row:
            await db.execute("INSERT INTO guilds (guild_id) VALUES (?);", (guild_id,))

    @commands.hybrid_command(name="setverifiedrole", description="Set the role given on verification")
    @app_commands.describe(role="Role to assign when a member verifies")
    @commands.guild_only()
    async def setverifiedrole(self, ctx: commands.Context, role: discord.Role) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            await ctx.send(embed=error_embed("Permission Denied", "Administrator only."), ephemeral=True)
            return

        # Hierarchy check
        if role >= ctx.guild.me.top_role:
            await ctx.send(
                embed=error_embed("Hierarchy", "I cannot assign a role that is higher than or equal to my top role.")
            )
            return

        await self._ensure_guild(ctx.guild.id)
        db = get_db()
        await db.execute(
            """
            UPDATE guilds SET verified_role_id = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (role.id, ctx.guild.id),
        )
        await ctx.send(
            embed=success_embed("Verified Role Set", f"Members will receive {role.mention} on verification.")
        )

    @commands.hybrid_command(name="setquarantinerole", description="Set the quarantine / unverified role")
    @app_commands.describe(role="Role given to unverified members")
    @commands.guild_only()
    async def setquarantinerole(self, ctx: commands.Context, role: discord.Role) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            await ctx.send(embed=error_embed("Permission Denied", "Administrator only."), ephemeral=True)
            return

        await self._ensure_guild(ctx.guild.id)
        db = get_db()
        await db.execute(
            """
            UPDATE guilds SET quarantine_role_id = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE guild_id = ?;
            """,
            (role.id, ctx.guild.id),
        )
        await ctx.send(
            embed=success_embed("Quarantine Role Set", f"Unverified role: {role.mention}")
        )

    @commands.hybrid_command(name="verifypanel", description="Post a verification panel with button")
    @commands.guild_only()
    async def verifypanel(self, ctx: commands.Context) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            await ctx.send(embed=error_embed("Permission Denied", "Administrator only."), ephemeral=True)
            return

        db = get_db()
        row = await db.fetchone(
            "SELECT verified_role_id FROM guilds WHERE guild_id = ?;",
            (ctx.guild.id,),
        )
        if not row or not row["verified_role_id"]:
            await ctx.send(
                embed=error_embed(
                    "Not Configured",
                    "Set a verified role first with `&setverifiedrole @Role`.",
                )
            )
            return

        embed = primary_embed(
            title="Verification",
            description=(
                "Click the **Verify** button below to gain access to the server.\n\n"
                "By verifying you agree to follow the server rules."
            ),
        )
        view = VerifyButton()
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Verification(bot))

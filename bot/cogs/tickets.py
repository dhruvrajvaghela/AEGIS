"""
Ticket system for AEGIS ULTIMATE ESPORTS BOT.
Create, claim, close, and transcript support.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_db
from bot.utils.checks import is_guild_admin, is_owner, has_mod_permissions
from bot.utils.embeds import success_embed, error_embed, info_embed, primary_embed, warning_embed
from bot.utils.helpers import generate_case_id
from bot.utils.i18n import t
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class TicketCreateButton(discord.ui.View):
    """Persistent button to open a new ticket."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.primary,
        custom_id="aegis:ticket_create",
        emoji="🎫",
    )
    async def create_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Tickets are server-only.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        db = get_db()

        # Check for existing open ticket
        existing = await db.fetchone(
            """
            SELECT ticket_id, channel_id FROM tickets
            WHERE guild_id = ? AND opener_id = ? AND status IN ('open', 'claimed');
            """,
            (interaction.guild.id, interaction.user.id),
        )
        if existing:
            await interaction.followup.send(
                f"You already have an open ticket: <#{existing['channel_id']}>",
                ephemeral=True,
            )
            return

        # Find panel config for category
        panel = await db.fetchone(
            "SELECT category_id, support_role_ids FROM ticket_panels WHERE guild_id = ? LIMIT 1;",
            (interaction.guild.id,),
        )
        category = None
        support_roles = []
        if panel and panel["category_id"]:
            category = interaction.guild.get_channel(panel["category_id"])
            if panel["support_role_ids"]:
                try:
                    import json
                    support_roles = json.loads(panel["support_role_ids"])
                except Exception:
                    support_roles = []

        ticket_id = generate_case_id("TKT")
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, attach_files=True, read_message_history=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
        }
        for role_id in support_roles:
            role = interaction.guild.get_role(int(role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )

        try:
            channel = await interaction.guild.create_text_channel(
                name=f"ticket-{interaction.user.name}"[:30],
                category=category if isinstance(category, discord.CategoryChannel) else None,
                overwrites=overwrites,
                reason=f"Ticket {ticket_id} by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "I lack permission to create ticket channels.", ephemeral=True
            )
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"Failed to create ticket: {e}", ephemeral=True)
            return

        await db.execute(
            """
            INSERT INTO tickets
                (ticket_id, guild_id, channel_id, opener_id, category, status)
            VALUES (?, ?, ?, ?, 'support', 'open');
            """,
            (ticket_id, interaction.guild.id, channel.id, interaction.user.id),
        )

        embed = primary_embed(
            title=f"Ticket {ticket_id}",
            description=(
                f"Hello {interaction.user.mention}, a staff member will assist you shortly.\n"
                f"Use `&close` or the button below to close this ticket."
            ),
        )
        embed.set_footer(text=f"Opened by {interaction.user}")

        view = TicketControlView()
        await channel.send(content=interaction.user.mention, embed=embed, view=view)
        await interaction.followup.send(
            f"Ticket created: {channel.mention}", ephemeral=True
        )


class TicketControlView(discord.ui.View):
    """Buttons inside a ticket channel."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.secondary,
        custom_id="aegis:ticket_claim",
        emoji="✋",
    )
    async def claim(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return

        db = get_db()
        ticket = await db.fetchone(
            "SELECT * FROM tickets WHERE channel_id = ? AND status IN ('open', 'claimed');",
            (interaction.channel_id,),
        )
        if not ticket:
            await interaction.response.send_message("No active ticket here.", ephemeral=True)
            return

        if ticket["claimed_by"]:
            await interaction.response.send_message(
                f"Already claimed by <@{ticket['claimed_by']}>.", ephemeral=True
            )
            return

        await db.execute(
            "UPDATE tickets SET claimed_by = ?, status = 'claimed' WHERE ticket_id = ?;",
            (interaction.user.id, ticket["ticket_id"]),
        )
        await interaction.response.send_message(
            f"Ticket claimed by {interaction.user.mention}."
        )

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        custom_id="aegis:ticket_close",
        emoji="🔒",
    )
    async def close(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return

        db = get_db()
        ticket = await db.fetchone(
            "SELECT * FROM tickets WHERE channel_id = ? AND status IN ('open', 'claimed');",
            (interaction.channel_id,),
        )
        if not ticket:
            await interaction.response.send_message("No active ticket here.", ephemeral=True)
            return

        # Allow opener or staff
        is_staff = await has_mod_permissions(interaction.user) or await is_guild_admin(interaction.user)
        if interaction.user.id != ticket["opener_id"] and not is_staff and not is_owner(interaction.user):
            await interaction.response.send_message(
                "Only the ticket opener or staff can close this.", ephemeral=True
            )
            return

        await interaction.response.send_message("Closing ticket and saving transcript...")

        # Build simple transcript
        messages = []
        try:
            async for msg in interaction.channel.history(limit=200, oldest_first=True):
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M")
                messages.append(f"[{ts}] {msg.author}: {msg.content}")
        except discord.HTTPException:
            pass

        transcript_text = "\n".join(messages) if messages else "(empty)"
        await db.execute(
            """
            INSERT OR REPLACE INTO ticket_transcripts (ticket_id, guild_id, content)
            VALUES (?, ?, ?);
            """,
            (ticket["ticket_id"], interaction.guild.id, transcript_text),
        )
        await db.execute(
            """
            UPDATE tickets SET status = 'closed',
                closed_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
                close_reason = 'Closed via button'
            WHERE ticket_id = ?;
            """,
            (ticket["ticket_id"],),
        )

        try:
            await interaction.channel.delete(reason=f"Ticket {ticket['ticket_id']} closed")
        except discord.HTTPException as e:
            logger.warning("Failed to delete ticket channel: %s", e)


class Tickets(commands.Cog):
    """Ticket system commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(TicketCreateButton())
        self.bot.add_view(TicketControlView())

    @commands.hybrid_command(name="ticketpanel", description="Post a ticket creation panel")
    @commands.guild_only()
    async def ticketpanel(
        self,
        ctx: commands.Context,
        category: Optional[discord.CategoryChannel] = None,
    ) -> None:
        if not isinstance(ctx.author, discord.Member):
            return
        if not (await is_guild_admin(ctx.author) or is_owner(ctx.author)):
            await ctx.send(embed=error_embed("Permission Denied", "Administrator only."), ephemeral=True)
            return

        db = get_db()
        await db.execute(
            """
            INSERT INTO ticket_panels (guild_id, channel_id, category_id, title, description)
            VALUES (?, ?, ?, 'Support Tickets', 'Click below to create a ticket.');
            """,
            (ctx.guild.id, ctx.channel.id, category.id if category else None),
        )

        embed = primary_embed(
            title="Support Tickets",
            description="Need help? Click the button below to open a private support ticket.",
        )
        view = TicketCreateButton()
        msg = await ctx.send(embed=embed, view=view)

        await db.execute(
            "UPDATE ticket_panels SET message_id = ? WHERE guild_id = ? AND channel_id = ?;",
            (msg.id, ctx.guild.id, ctx.channel.id),
        )

    @commands.hybrid_command(name="close", description="Close the current ticket")
    @commands.guild_only()
    async def close_ticket(self, ctx: commands.Context, reason: Optional[str] = None) -> None:
        db = get_db()
        ticket = await db.fetchone(
            "SELECT * FROM tickets WHERE channel_id = ? AND status IN ('open', 'claimed');",
            (ctx.channel.id,),
        )
        if not ticket:
            await ctx.send(embed=error_embed("Not a Ticket", "This channel is not an active ticket."))
            return

        is_staff = False
        if isinstance(ctx.author, discord.Member):
            is_staff = (
                await has_mod_permissions(ctx.author)
                or await is_guild_admin(ctx.author)
                or is_owner(ctx.author)
            )

        if ctx.author.id != ticket["opener_id"] and not is_staff:
            await ctx.send(embed=error_embed("Permission Denied", "Only the opener or staff can close."))
            return

        reason = reason or "Closed by command"
        await ctx.send(embed=warning_embed("Closing", "Saving transcript and closing..."))

        messages = []
        try:
            async for msg in ctx.channel.history(limit=200, oldest_first=True):
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M")
                messages.append(f"[{ts}] {msg.author}: {msg.content}")
        except discord.HTTPException:
            pass

        transcript_text = "\n".join(messages) if messages else "(empty)"
        await db.execute(
            """
            INSERT OR REPLACE INTO ticket_transcripts (ticket_id, guild_id, content)
            VALUES (?, ?, ?);
            """,
            (ticket["ticket_id"], ctx.guild.id, transcript_text),
        )
        await db.execute(
            """
            UPDATE tickets SET status = 'closed',
                closed_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
                close_reason = ?
            WHERE ticket_id = ?;
            """,
            (reason, ticket["ticket_id"]),
        )

        try:
            await ctx.channel.delete(reason=f"Ticket {ticket['ticket_id']} closed")
        except discord.HTTPException as e:
            await ctx.send(embed=error_embed("Error", f"Closed in DB but failed to delete channel: {e}"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))

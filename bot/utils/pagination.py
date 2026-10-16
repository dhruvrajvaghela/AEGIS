"""
Pagination helpers for AEGIS ULTIMATE ESPORTS BOT.
Supports both button-based and reaction-style pagination for embeds.
"""

from __future__ import annotations

from typing import List, Optional

import discord
from discord.ext import commands


class PaginatedEmbedView(discord.ui.View):
    """
    Button-based paginator for a list of embeds.
    Works with both slash commands and prefix commands.
    """

    def __init__(
        self,
        embeds: List[discord.Embed],
        *,
        author_id: int,
        timeout: float = 120.0,
    ):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.author_id = author_id
        self.current_page = 0
        self.message: Optional[discord.Message] = None

        self._update_buttons()

    def _update_buttons(self) -> None:
        """Enable/disable navigation buttons based on current page."""
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= len(self.embeds) - 1
        self.last_page.disabled = self.current_page >= len(self.embeds) - 1

        # Update page counter label
        self.page_label.label = f"{self.current_page + 1}/{len(self.embeds)}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the command author can control this menu.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This button is only a label
        await interaction.response.defer()

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(len(self.embeds) - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = len(self.embeds) - 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


async def send_paginated(
    destination: commands.Context | discord.Interaction,
    embeds: List[discord.Embed],
    *,
    ephemeral: bool = False,
) -> None:
    """
    Send a paginated embed view.
    Accepts both Context (prefix) and Interaction (slash).
    """
    if not embeds:
        return

    # Single page — no need for buttons
    if len(embeds) == 1:
        if isinstance(destination, discord.Interaction):
            if destination.response.is_done():
                await destination.followup.send(embed=embeds[0], ephemeral=ephemeral)
            else:
                await destination.response.send_message(embed=embeds[0], ephemeral=ephemeral)
        else:
            await destination.send(embed=embeds[0])
        return

    author_id = (
        destination.user.id
        if isinstance(destination, discord.Interaction)
        else destination.author.id
    )

    view = PaginatedEmbedView(embeds, author_id=author_id)

    if isinstance(destination, discord.Interaction):
        if destination.response.is_done():
            message = await destination.followup.send(
                embed=embeds[0], view=view, ephemeral=ephemeral
            )
        else:
            await destination.response.send_message(
                embed=embeds[0], view=view, ephemeral=ephemeral
            )
            message = await destination.original_response()
        view.message = message
    else:
        message = await destination.send(embed=embeds[0], view=view)
        view.message = message

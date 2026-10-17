"""
Team management commands for AEGIS ULTIMATE ESPORTS BOT.
Create teams, manage roster, join requests.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_db
from bot.utils.embeds import success_embed, error_embed, info_embed, primary_embed
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class Teams(commands.Cog):
    """Team management for esports."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # -------------------- CREATE TEAM --------------------

    @commands.hybrid_command(name="createteam", description="Create a new team")
    @app_commands.describe(name="Team name", tag="Short tag (optional)")
    @commands.guild_only()
    async def createteam(
        self,
        ctx: commands.Context,
        name: str,
        tag: Optional[str] = None,
    ) -> None:
        name = name.strip()[:64]
        if len(name) < 2:
            await ctx.send(embed=error_embed("Invalid Name", "Team name must be at least 2 characters."))
            return

        tag = tag.strip()[:8] if tag else None
        db = get_db()

        # Check if user already captains a team in this guild
        existing = await db.fetchone(
            "SELECT id, name FROM teams WHERE guild_id = ? AND captain_id = ?;",
            (ctx.guild.id, ctx.author.id),
        )
        if existing:
            await ctx.send(
                embed=error_embed(
                    "Already Captain",
                    f"You already captain **{existing['name']}**. Leave or transfer first.",
                )
            )
            return

        # Unique name check
        dup = await db.fetchone(
            "SELECT id FROM teams WHERE guild_id = ? AND name = ?;",
            (ctx.guild.id, name),
        )
        if dup:
            await ctx.send(embed=error_embed("Name Taken", "A team with that name already exists."))
            return

        cursor = await db.execute(
            """
            INSERT INTO teams (guild_id, name, tag, captain_id)
            VALUES (?, ?, ?, ?);
            """,
            (ctx.guild.id, name, tag, ctx.author.id),
        )
        # Get last inserted id
        row = await db.fetchone("SELECT last_insert_rowid() AS id;")
        team_id = row["id"]

        # Add captain as member
        await db.execute(
            """
            INSERT INTO team_members (team_id, user_id, role)
            VALUES (?, ?, 'captain');
            """,
            (team_id, ctx.author.id),
        )

        embed = success_embed(
            "Team Created",
            f"**{name}**" + (f" [{tag}]" if tag else "") + f"\nCaptain: {ctx.author.mention}\nTeam ID: `{team_id}`",
        )
        await ctx.send(embed=embed)

    # -------------------- TEAM INFO --------------------

    @commands.hybrid_command(name="team", description="View team information")
    @app_commands.describe(name="Team name (leave empty for your team)")
    @commands.guild_only()
    async def team_info(self, ctx: commands.Context, name: Optional[str] = None) -> None:
        db = get_db()

        if name:
            team = await db.fetchone(
                "SELECT * FROM teams WHERE guild_id = ? AND name = ?;",
                (ctx.guild.id, name.strip()),
            )
        else:
            # Find team the user is in
            team = await db.fetchone(
                """
                SELECT t.* FROM teams t
                JOIN team_members tm ON tm.team_id = t.id
                WHERE t.guild_id = ? AND tm.user_id = ?
                LIMIT 1;
                """,
                (ctx.guild.id, ctx.author.id),
            )

        if not team:
            await ctx.send(embed=error_embed("Not Found", "Team not found."))
            return

        members = await db.fetchall(
            """
            SELECT user_id, ign, bgmi_uid, role, is_substitute
            FROM team_members
            WHERE team_id = ?
            ORDER BY is_substitute ASC, role ASC;
            """,
            (team["id"],),
        )

        embed = primary_embed(title=f"Team — {team['name']}" + (f" [{team['tag']}]" if team["tag"] else ""))
        embed.add_field(name="Captain", value=f"<@{team['captain_id']}>", inline=True)
        embed.add_field(name="Team ID", value=f"`{team['id']}`", inline=True)
        embed.add_field(name="Created", value=team["created_at"][:10], inline=True)

        if members:
            roster_lines = []
            for m in members:
                role_label = m["role"]
                if m["is_substitute"]:
                    role_label += " (sub)"
                ign = f" — {m['ign']}" if m["ign"] else ""
                roster_lines.append(f"<@{m['user_id']}> `{role_label}`{ign}")
            embed.add_field(name=f"Roster ({len(members)})", value="\n".join(roster_lines), inline=False)

        if team["logo_url"]:
            embed.set_thumbnail(url=team["logo_url"])

        await ctx.send(embed=embed)

    # -------------------- ADD MEMBER --------------------

    @commands.hybrid_command(name="teamadd", description="Add a member to your team")
    @app_commands.describe(member="Member to add", ign="In-game name (optional)")
    @commands.guild_only()
    async def teamadd(
        self,
        ctx: commands.Context,
        member: discord.Member,
        ign: Optional[str] = None,
    ) -> None:
        db = get_db()
        team = await db.fetchone(
            "SELECT * FROM teams WHERE guild_id = ? AND captain_id = ?;",
            (ctx.guild.id, ctx.author.id),
        )
        if not team:
            await ctx.send(embed=error_embed("Not Captain", "You must be a team captain to add members."))
            return

        existing = await db.fetchone(
            "SELECT id FROM team_members WHERE team_id = ? AND user_id = ?;",
            (team["id"], member.id),
        )
        if existing:
            await ctx.send(embed=error_embed("Already Member", f"{member.mention} is already on the team."))
            return

        # Also prevent joining another team in same guild
        other = await db.fetchone(
            """
            SELECT t.name FROM team_members tm
            JOIN teams t ON t.id = tm.team_id
            WHERE t.guild_id = ? AND tm.user_id = ?;
            """,
            (ctx.guild.id, member.id),
        )
        if other:
            await ctx.send(
                embed=error_embed("Already on a Team", f"{member.mention} is already on **{other['name']}**.")
            )
            return

        await db.execute(
            """
            INSERT INTO team_members (team_id, user_id, ign, role)
            VALUES (?, ?, ?, 'player');
            """,
            (team["id"], member.id, ign),
        )
        await ctx.send(
            embed=success_embed("Member Added", f"{member.mention} added to **{team['name']}**.")
        )

    # -------------------- REMOVE MEMBER --------------------

    @commands.hybrid_command(name="teamremove", description="Remove a member from your team")
    @app_commands.describe(member="Member to remove")
    @commands.guild_only()
    async def teamremove(self, ctx: commands.Context, member: discord.Member) -> None:
        db = get_db()
        team = await db.fetchone(
            "SELECT * FROM teams WHERE guild_id = ? AND captain_id = ?;",
            (ctx.guild.id, ctx.author.id),
        )
        if not team:
            await ctx.send(embed=error_embed("Not Captain", "You must be a team captain."))
            return

        if member.id == ctx.author.id:
            await ctx.send(embed=error_embed("Invalid", "You cannot remove yourself. Transfer captain or disband."))
            return

        result = await db.execute(
            "DELETE FROM team_members WHERE team_id = ? AND user_id = ?;",
            (team["id"], member.id),
        )
        await ctx.send(
            embed=success_embed("Member Removed", f"{member.mention} removed from **{team['name']}**.")
        )

    # -------------------- SET IGN --------------------

    @commands.hybrid_command(name="setign", description="Set your in-game name on your team")
    @app_commands.describe(ign="Your in-game name", bgmi_uid="BGMI UID (optional)")
    @commands.guild_only()
    async def setign(
        self,
        ctx: commands.Context,
        ign: str,
        bgmi_uid: Optional[str] = None,
    ) -> None:
        db = get_db()
        membership = await db.fetchone(
            """
            SELECT tm.id, t.name FROM team_members tm
            JOIN teams t ON t.id = tm.team_id
            WHERE t.guild_id = ? AND tm.user_id = ?;
            """,
            (ctx.guild.id, ctx.author.id),
        )
        if not membership:
            await ctx.send(embed=error_embed("No Team", "You are not on a team in this server."))
            return

        await db.execute(
            "UPDATE team_members SET ign = ?, bgmi_uid = ? WHERE id = ?;",
            (ign.strip()[:64], bgmi_uid, membership["id"]),
        )
        await ctx.send(
            embed=success_embed("IGN Updated", f"Your IGN on **{membership['name']}** is now **{ign}**.")
        )

    # -------------------- LEAVE TEAM --------------------

    @commands.hybrid_command(name="leaveteam", description="Leave your current team")
    @commands.guild_only()
    async def leaveteam(self, ctx: commands.Context) -> None:
        db = get_db()
        membership = await db.fetchone(
            """
            SELECT tm.id, tm.role, t.id AS team_id, t.name, t.captain_id
            FROM team_members tm
            JOIN teams t ON t.id = tm.team_id
            WHERE t.guild_id = ? AND tm.user_id = ?;
            """,
            (ctx.guild.id, ctx.author.id),
        )
        if not membership:
            await ctx.send(embed=error_embed("No Team", "You are not on a team."))
            return

        if membership["captain_id"] == ctx.author.id:
            await ctx.send(
                embed=error_embed(
                    "Captain",
                    "Captains cannot leave. Transfer captaincy or disband the team first.",
                )
            )
            return

        await db.execute("DELETE FROM team_members WHERE id = ?;", (membership["id"],))
        await ctx.send(embed=success_embed("Left Team", f"You left **{membership['name']}**."))

    # -------------------- LIST TEAMS --------------------

    @commands.hybrid_command(name="teams", description="List teams in this server")
    @commands.guild_only()
    async def list_teams(self, ctx: commands.Context) -> None:
        db = get_db()
        rows = await db.fetchall(
            """
            SELECT t.id, t.name, t.tag, t.captain_id,
                   (SELECT COUNT(*) FROM team_members tm WHERE tm.team_id = t.id) AS members
            FROM teams t
            WHERE t.guild_id = ?
            ORDER BY t.name
            LIMIT 30;
            """,
            (ctx.guild.id,),
        )
        if not rows:
            await ctx.send(embed=info_embed("Teams", "No teams yet. Use `&createteam` to create one."))
            return

        lines = [
            f"**{r['name']}**" + (f" [{r['tag']}]" if r["tag"] else "") + f" — <@{r['captain_id']}> ({r['members']} members)"
            for r in rows
        ]
        embed = primary_embed(title=f"Teams in {ctx.guild.name}", description="\n".join(lines))
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Teams(bot))

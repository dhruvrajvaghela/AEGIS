"""
Server (guild) management routes for the AEGIS dashboard.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash

from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

servers_bp = Blueprint("servers", __name__, url_prefix="/dashboard/servers")


@servers_bp.route("/")
@owner_required
async def list_servers():
    """List all guilds known to the bot."""
    db = get_db()

    try:
        rows = await db.fetchall(
            """
            SELECT guild_id, prefix, language, welcome_channel_id,
                   log_channel_id, created_at, updated_at
            FROM guilds
            ORDER BY created_at DESC;
            """
        )
        guilds = [dict(row) for row in rows]
    except Exception as e:
        logger.error("Failed to fetch guilds: %s", e)
        guilds = []

    return render_template("dashboard/servers.html", guilds=guilds)


@servers_bp.route("/<int:guild_id>")
@owner_required
async def server_detail(guild_id: int):
    """Show detailed configuration for a single guild."""
    db = get_db()

    guild = await db.fetchone(
        "SELECT * FROM guilds WHERE guild_id = ?;",
        (guild_id,),
    )
    if not guild:
        return render_template(
            "error.html", code=404, message="Server not found in database."
        ), 404

    # Security config
    security = await db.fetchone(
        "SELECT * FROM security_config WHERE guild_id = ?;",
        (guild_id,),
    )

    # Open tickets count
    ticket_row = await db.fetchone(
        "SELECT COUNT(*) AS c FROM tickets WHERE guild_id = ? AND status = 'open';",
        (guild_id,),
    )
    open_tickets = ticket_row["c"] if ticket_row else 0

    # Recent mod cases
    cases = await db.fetchall(
        """
        SELECT case_id, user_id, action, reason, created_at
        FROM mod_cases
        WHERE guild_id = ?
        ORDER BY created_at DESC
        LIMIT 10;
        """,
        (guild_id,),
    )

    return render_template(
        "dashboard/server_detail.html",
        guild=dict(guild),
        security=dict(security) if security else None,
        open_tickets=open_tickets,
        recent_cases=[dict(c) for c in cases],
        )

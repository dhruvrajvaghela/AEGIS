"""
Overview / home dashboard routes for AEGIS ULTIMATE ESPORTS BOT.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, render_template, session

from bot.config import config
from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

overview_bp = Blueprint("overview", __name__)


@overview_bp.route("/dashboard")
@owner_required
async def dashboard():
    """
    Main overview page.
    Shows high-level stats and system status.
    """
    db = get_db()

    # Basic counts (safe defaults if tables are empty)
    try:
        guild_count_row = await db.fetchone("SELECT COUNT(*) AS c FROM guilds;")
        guild_count = guild_count_row["c"] if guild_count_row else 0
    except Exception:
        guild_count = 0

    try:
        case_count_row = await db.fetchone("SELECT COUNT(*) AS c FROM mod_cases;")
        case_count = case_count_row["c"] if case_count_row else 0
    except Exception:
        case_count = 0

    try:
        ticket_count_row = await db.fetchone(
            "SELECT COUNT(*) AS c FROM tickets WHERE status = 'open';"
        )
        open_tickets = ticket_count_row["c"] if ticket_count_row else 0
    except Exception:
        open_tickets = 0

    try:
        tournament_row = await db.fetchone(
            "SELECT COUNT(*) AS c FROM tournaments WHERE status != 'cancelled';"
        )
        tournaments = tournament_row["c"] if tournament_row else 0
    except Exception:
        tournaments = 0

    try:
        security_row = await db.fetchone(
            "SELECT COUNT(*) AS c FROM security_events WHERE resolved = 0;"
        )
        open_security_events = security_row["c"] if security_row else 0
    except Exception:
        open_security_events = 0

    stats = {
        "guilds": guild_count,
        "mod_cases": case_count,
        "open_tickets": open_tickets,
        "tournaments": tournaments,
        "open_security_events": open_security_events,
    }

    system = {
        "maintenance_mode": config.maintenance_mode,
        "database_path": config.database_path,
        "default_prefix": config.default_prefix,
        "default_language": config.default_language,
        "features": {
            "esports": config.features.esports,
            "security": config.features.security,
            "moderation": config.features.moderation,
            "staff": config.features.staff,
            "tickets": config.features.tickets,
            "welcome": config.features.welcome,
            "verification": config.features.verification,
            "automod": config.features.automod,
            "invites": config.features.invites,
            "community": config.features.community,
        },
    }

    return render_template(
        "dashboard/overview.html",
        stats=stats,
        system=system,
        username=session.get("username", "Owner"),
        current_time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

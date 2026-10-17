"""
Security management routes for the AEGIS dashboard (owner only).
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash

from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

security_bp = Blueprint("security", __name__, url_prefix="/dashboard/security")


@security_bp.route("/")
@owner_required
async def security_overview():
    """Security overview across all guilds."""
    db = get_db()

    # Guilds currently in lockdown
    try:
        lockdowns = await db.fetchall(
            """
            SELECT guild_id, lockdown_reason, updated_at
            FROM security_config
            WHERE lockdown = 1
            ORDER BY updated_at DESC;
            """
        )
        lockdown_list = [dict(r) for r in lockdowns]
    except Exception:
        lockdown_list = []

    # Recent unresolved security events
    try:
        events = await db.fetchall(
            """
            SELECT id, guild_id, event_type, severity, actor_id, target_id,
                   details, created_at
            FROM security_events
            WHERE resolved = 0
            ORDER BY created_at DESC
            LIMIT 50;
            """
        )
        event_list = [dict(e) for e in events]
    except Exception:
        event_list = []

    # Counts by severity
    try:
        severity_rows = await db.fetchall(
            """
            SELECT severity, COUNT(*) AS c
            FROM security_events
            WHERE resolved = 0
            GROUP BY severity;
            """
        )
        severity_counts = {row["severity"]: row["c"] for row in severity_rows}
    except Exception:
        severity_counts = {}

    return render_template(
        "dashboard/security.html",
        lockdowns=lockdown_list,
        events=event_list,
        severity_counts=severity_counts,
    )


@security_bp.route("/events/<int:event_id>/resolve", methods=["POST"])
@owner_required
async def resolve_event(event_id: int):
    """Mark a security event as resolved."""
    db = get_db()
    try:
        await db.execute(
            "UPDATE security_events SET resolved = 1 WHERE id = ?;",
            (event_id,),
        )
        flash(f"Security event #{event_id} marked as resolved.", "success")
    except Exception as e:
        logger.error("Failed to resolve security event %s: %s", event_id, e)
        flash("Failed to resolve event.", "error")

    return redirect(url_for("security.security_overview"))


@security_bp.route("/guild/<int:guild_id>")
@owner_required
async def guild_security(guild_id: int):
    """Detailed security config and events for one guild."""
    db = get_db()

    config_row = await db.fetchone(
        "SELECT * FROM security_config WHERE guild_id = ?;",
        (guild_id,),
    )
    if not config_row:
        # Return empty defaults if no config exists yet
        security_config = {
            "guild_id": guild_id,
            "anti_nuke_enabled": 1,
            "anti_raid_enabled": 1,
            "anti_spam_enabled": 1,
            "lockdown": 0,
            "lockdown_reason": None,
            "thresholds": "{}",
            "allowlist_users": "[]",
            "allowlist_roles": "[]",
        }
    else:
        security_config = dict(config_row)

    events = await db.fetchall(
        """
        SELECT id, event_type, severity, actor_id, target_id, details,
               resolved, created_at
        FROM security_events
        WHERE guild_id = ?
        ORDER BY created_at DESC
        LIMIT 30;
        """,
        (guild_id,),
    )

    return render_template(
        "dashboard/guild_security.html",
        guild_id=guild_id,
        config=security_config,
        events=[dict(e) for e in events],
    )
